#!/usr/bin/env python3
"""Aggregates token consumption for a session (main + subagents).

Python port of utils/session-tokens.sh for MCP server integration.
"""

import json
import os
import re
import sys


def find_metrics_file(session_id=""):
    if session_id:
        candidate = f"/tmp/claude-session-metrics-{session_id}.json"
        if os.path.isfile(candidate):
            return candidate
    fallback = "/tmp/claude-session-metrics.json"
    if os.path.isfile(fallback):
        return fallback
    return None


def find_subagent_log(learning_path="", project_dir=""):
    candidates = [learning_path, project_dir, os.environ.get("CLAUDE_PROJECT_DIR", ""), os.getcwd()]
    for d in candidates:
        if not d:
            continue
        path = os.path.join(d, "logs", "subagent-tokens.jsonl") if "learning" in d else os.path.join(d, "learning", "logs", "subagent-tokens.jsonl")
        if os.path.isfile(path):
            return path
    return None


def parse_subagent_log(path, session_id=""):
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if session_id and entry.get("session_id") != session_id:
                continue
            entry["fresh"] = (
                entry.get("input_tokens", 0)
                + entry.get("output_tokens", 0)
                + entry.get("cache_creation_tokens", 0)
            )
            entries.append(entry)
    return entries


def group_by_agent(entries):
    groups = {}
    for e in entries:
        agent_type = e.get("agent_type", "unknown")
        if agent_type not in groups:
            groups[agent_type] = []
        groups[agent_type].append(e)

    result = []
    for agent_type, items in groups.items():
        group = {
            "agent_type": agent_type,
            "calls": len(items),
            "input": sum(i.get("input_tokens", 0) for i in items),
            "output": sum(i.get("output_tokens", 0) for i in items),
            "cache_create": sum(i.get("cache_creation_tokens", 0) for i in items),
            "cache_read": sum(i.get("cache_read_tokens", 0) for i in items),
            "fresh": sum(i.get("fresh", 0) for i in items),
            "invocations": [
                {
                    "timestamp": i.get("timestamp", ""),
                    "fresh": i.get("fresh", 0),
                    "input": i.get("input_tokens", 0),
                    "output": i.get("output_tokens", 0),
                    "cache_create": i.get("cache_creation_tokens", 0),
                    "cache_read": i.get("cache_read_tokens", 0),
                }
                for i in items
            ],
        }
        result.append(group)
    result.sort(key=lambda g: -g["fresh"])
    return result


def get_agent_model(agent_type, agents_dir=""):
    if not agents_dir:
        agents_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents")
    agent_file = os.path.join(agents_dir, f"{agent_type}.md")
    if not os.path.isfile(agent_file):
        return "opus"
    try:
        with open(agent_file) as f:
            content = f.read(500)
        match = re.search(r"^model:\s*(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    return "opus"


def fmt_tokens(t):
    if t >= 1_000_000:
        return f"{t / 1_000_000:.1f}M"
    elif t >= 1_000:
        return f"{t / 1_000:.1f}K"
    return str(t)


def fmt_duration(ms):
    total_sec = ms // 1000
    hours = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours}h{mins:02d}m{secs:02d}s"
    elif mins > 0:
        return f"{mins}m{secs:02d}s"
    return f"{secs}s"


def run(session_id="", topic_slug="", learning_path=""):
    metrics_file = find_metrics_file(session_id)
    if not metrics_file:
        return {"error": "No session metrics found"}

    with open(metrics_file) as f:
        main = json.load(f)

    main_in = main.get("input_tokens", 0)
    main_out = main.get("output_tokens", 0)
    ctx_size = main.get("context_window_size", 0)
    used_pct = main.get("used_percentage", 0)
    duration_ms = main.get("duration_ms", 0)
    main_ctx = (ctx_size * used_pct // 100) if ctx_size > 0 and used_pct > 0 else 0

    sub_log = find_subagent_log(learning_path)
    sub_total = 0
    sub_groups = []

    if sub_log:
        entries = parse_subagent_log(sub_log, session_id)
        sub_groups = group_by_agent(entries)
        sub_total = sum(g["fresh"] for g in sub_groups)

    grand_total = main_ctx + sub_total

    lines = ["=== Session Token Summary ===", ""]
    lines.append("Main session:")
    if duration_ms > 0:
        lines.append(f"  Duration:        {fmt_duration(duration_ms)}")
    lines.append(f"  Context window:  {fmt_tokens(ctx_size)} ({used_pct}% used = {main_ctx} tokens)")
    lines.append(f"  Conversation:    📥 {main_in} in / 📤 {main_out} out")
    lines.append("")

    if sub_groups:
        lines.append("Subagents:")
        for g in sub_groups:
            model = get_agent_model(g["agent_type"])
            lines.append(
                f"  {g['agent_type']}/{model} (x{g['calls']}): {g['fresh']} fresh "
                f"(in:{g['input']} out:{g['output']} cache-create:{g['cache_create']} cache-read:{g['cache_read']})"
            )
            for inv in g["invocations"]:
                lines.append(
                    f"    [{inv['timestamp']}] {inv['fresh']} fresh "
                    f"(in:{inv['input']} out:{inv['output']} cache-create:{inv['cache_create']} cache-read:{inv['cache_read']})"
                )
        lines.append("  ─────────────────")
        lines.append(f"  Subagent total:  {sub_total} fresh")
        lines.append("")

    lines.append(f"Grand total:       {grand_total}")

    summary = "\n".join(lines)

    if topic_slug:
        metrics_out = f"/tmp/session-metrics-{topic_slug}.txt"
        clerk_lines = []
        clerk_lines.append(f"- Duration: {fmt_duration(duration_ms)}")
        clerk_lines.append(f"- Context: {used_pct}% of {fmt_tokens(ctx_size)} ({main_ctx} tokens)")
        clerk_lines.append(f"- Conversation: 📥 {main_in} in / 📤 {main_out} out")
        if sub_groups:
            clerk_lines.append(f"- Subagents: {sub_total} fresh")
            for g in sub_groups:
                model = get_agent_model(g["agent_type"])
                clerk_lines.append(
                    f"  - {g['agent_type']}/{model} (x{g['calls']}): {g['fresh']} fresh "
                    f"(in:{g['input']} out:{g['output']} cache-create:{g['cache_create']} cache-read:{g['cache_read']})"
                )
                for inv in g["invocations"]:
                    clerk_lines.append(
                        f"    - [{inv['timestamp']}] {inv['fresh']} fresh "
                        f"(in:{inv['input']} out:{inv['output']} cache-create:{inv['cache_create']} cache-read:{inv['cache_read']})"
                    )
        else:
            clerk_lines.append("- Subagents: 0 fresh")
        clerk_lines.append(f"- Grand total: {grand_total}")

        with open(metrics_out, "w") as f:
            f.write("\n".join(clerk_lines) + "\n")
        summary += f"\n\nMetrics file written: {metrics_out}"

    return {"summary": summary, "grand_total": grand_total, "metrics_file": f"/tmp/session-metrics-{topic_slug}.txt" if topic_slug else None}


def main():
    session_id = sys.argv[1] if len(sys.argv) > 1 else ""
    topic_slug = sys.argv[2] if len(sys.argv) > 2 else ""
    result = run(session_id=session_id, topic_slug=topic_slug)
    if "error" in result:
        print(result["error"], file=sys.stderr)
        sys.exit(1)
    print(result["summary"])


if __name__ == "__main__":
    main()
