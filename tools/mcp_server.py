#!/usr/bin/env python3
"""Ultralearn MCP server — stdlib-only, wraps existing CLI tools via subprocess."""

import json
import os
import subprocess
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Tool registry — each entry maps an MCP tool name to a CLI invocation
# ---------------------------------------------------------------------------

TOOL_DEFS = [
    # --- SRS Engine ---
    {
        "name": "srs_init",
        "description": "Create cards.srs.json from cards.md. Run once when starting SRS for a topic.",
        "script": "srs/srs_engine.py",
        "subcommand": "init",
        "args": [
            {"name": "path", "type": "string", "description": "Path to cards.md or its parent directory", "required": True, "positional": True},
            {"name": "force", "type": "boolean", "description": "Overwrite existing srs.json", "cli": "--force"},
        ],
        "json_flag": True,
    },
    {
        "name": "srs_sync",
        "description": "Sync new/changed cards from cards.md into cards.srs.json.",
        "script": "srs/srs_engine.py",
        "subcommand": "sync",
        "args": [
            {"name": "path", "type": "string", "description": "Path to cards.md or its parent directory", "required": True, "positional": True},
        ],
        "json_flag": True,
    },
    {
        "name": "srs_due",
        "description": "List cards due for review. Returns card IDs, question previews, and due dates.",
        "script": "srs/srs_engine.py",
        "subcommand": "due",
        "args": [
            {"name": "path", "type": "string", "description": "Path to cards.md or its parent directory", "required": True, "positional": True},
            {"name": "date", "type": "string", "description": "Check date (YYYY-MM-DD), defaults to today", "cli": "--date"},
        ],
        "json_flag": True,
    },
    {
        "name": "srs_grade",
        "description": "Grade a card (0-5) using the SM-2 algorithm. Updates the card's schedule.",
        "script": "srs/srs_engine.py",
        "subcommand": "grade",
        "args": [
            {"name": "path", "type": "string", "description": "Path to cards.md or its parent directory", "required": True, "positional": True},
            {"name": "card_id", "type": "string", "description": "Card ID (e.g., card-1)", "required": True, "positional": True},
            {"name": "quality", "type": "integer", "description": "Quality grade (0-5)", "required": True, "positional": True},
            {"name": "date", "type": "string", "description": "Review date (YYYY-MM-DD), defaults to today", "cli": "--date"},
        ],
        "json_flag": True,
    },
    {
        "name": "srs_stats",
        "description": "Show aggregate SRS statistics: total cards, average EF, lapses, etc.",
        "script": "srs/srs_engine.py",
        "subcommand": "stats",
        "args": [
            {"name": "path", "type": "string", "description": "Path to cards.md or its parent directory", "required": True, "positional": True},
        ],
        "json_flag": True,
    },
    {
        "name": "srs_forecast",
        "description": "Show review forecast — how many cards are due each day.",
        "script": "srs/srs_engine.py",
        "subcommand": "forecast",
        "args": [
            {"name": "path", "type": "string", "description": "Path to cards.md or its parent directory", "required": True, "positional": True},
            {"name": "days", "type": "integer", "description": "Number of days to forecast (default: 7)", "cli": "--days"},
        ],
        "json_flag": True,
    },
    # --- Card Writer ---
    {
        "name": "card_append",
        "description": "Append new cards to cards.md from a JSON array of card objects. Each object needs: question, answer, tags (array).",
        "script": "srs/card_writer.py",
        "subcommand": "append",
        "args": [
            {"name": "path", "type": "string", "description": "Path to cards.md or its parent directory", "required": True, "positional": True},
            {"name": "data", "type": "string", "description": "JSON array of card objects", "required": True, "stdin": True},
        ],
    },
    {
        "name": "card_validate",
        "description": "Check cards.md for format violations.",
        "script": "srs/card_writer.py",
        "subcommand": "validate",
        "args": [
            {"name": "path", "type": "string", "description": "Path to cards.md or its parent directory", "required": True, "positional": True},
        ],
    },
    {
        "name": "card_fix",
        "description": "Normalize cards.md to canonical compact format. Fixes formatting drift.",
        "script": "srs/card_writer.py",
        "subcommand": "fix",
        "args": [
            {"name": "path", "type": "string", "description": "Path to cards.md", "required": True, "positional": True},
        ],
    },
    # --- Journal Writer ---
    {
        "name": "journal_append",
        "description": "Append a session row to journal/index.md. JSON object needs: session_number, date, focus. Optional: type, review_count, avg_grade, summary.",
        "script": "srs/journal_writer.py",
        "subcommand": "append",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
            {"name": "data", "type": "string", "description": "JSON object with session data", "required": True, "stdin": True},
        ],
    },
    {
        "name": "journal_validate",
        "description": "Check journal/index.md for format violations.",
        "script": "srs/journal_writer.py",
        "subcommand": "validate",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
        ],
    },
    {
        "name": "journal_fix",
        "description": "Normalize journal/index.md to canonical 8-column format.",
        "script": "srs/journal_writer.py",
        "subcommand": "fix",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
        ],
    },
    # --- Knowledge Map Writer ---
    {
        "name": "kmap_add_concept",
        "description": "Add a new concept row to knowledge-map.md. JSON needs: concept, status, introduced, last_tested, notes.",
        "script": "srs/kmap_writer.py",
        "subcommand": "add-concept",
        "args": [
            {"name": "path", "type": "string", "description": "Path to knowledge-map.md or learning directory", "required": True, "positional": True},
            {"name": "data", "type": "string", "description": "JSON object with concept data", "required": True, "stdin": True},
        ],
    },
    {
        "name": "kmap_update_status",
        "description": "Update an existing concept's status in knowledge-map.md. JSON needs: concept, status, last_tested, notes. Preserves the Introduced column.",
        "script": "srs/kmap_writer.py",
        "subcommand": "update-status",
        "args": [
            {"name": "path", "type": "string", "description": "Path to knowledge-map.md or learning directory", "required": True, "positional": True},
            {"name": "data", "type": "string", "description": "JSON object with status update", "required": True, "stdin": True},
        ],
    },
    {
        "name": "kmap_changelog_append",
        "description": "Append status changelog rows to knowledge-map.md. JSON array of: date, concept, from_status, to_status, session.",
        "script": "srs/kmap_writer.py",
        "subcommand": "changelog-append",
        "args": [
            {"name": "path", "type": "string", "description": "Path to knowledge-map.md or learning directory", "required": True, "positional": True},
            {"name": "data", "type": "string", "description": "JSON array of changelog entries", "required": True, "stdin": True},
        ],
    },
    {
        "name": "kmap_fix_legend",
        "description": "Normalize the Status Legend section in knowledge-map.md.",
        "script": "srs/kmap_writer.py",
        "subcommand": "fix-legend",
        "args": [
            {"name": "path", "type": "string", "description": "Path to knowledge-map.md or learning directory", "required": True, "positional": True},
        ],
    },
    {
        "name": "kmap_ensure_sections",
        "description": "Create missing sections in knowledge-map.md.",
        "script": "srs/kmap_writer.py",
        "subcommand": "ensure-sections",
        "args": [
            {"name": "path", "type": "string", "description": "Path to knowledge-map.md or learning directory", "required": True, "positional": True},
        ],
    },
    {
        "name": "kmap_validate",
        "description": "Check knowledge-map.md for format violations.",
        "script": "srs/kmap_writer.py",
        "subcommand": "validate",
        "args": [
            {"name": "path", "type": "string", "description": "Path to knowledge-map.md or learning directory", "required": True, "positional": True},
        ],
    },
    # --- Weak Spot Writer ---
    {
        "name": "weak_spot_append",
        "description": "Append a new weak spot or coach error entry. Kind determines target file and ID prefix: WS/M -> weak-spots.md, CE/CP -> coach-errors.md.",
        "script": "srs/weak_spot_writer.py",
        "subcommand": "append",
        "args": [
            {"name": "path", "type": "string", "description": "Path to file or learning directory", "required": True, "positional": True},
            {"name": "kind", "type": "string", "description": "Entry kind: WS (weak spot), M (wrong-model alias), CE (coach content error), CP (coach process failure)", "required": True, "cli": "--kind", "enum": ["WS", "M", "CE", "CP"]},
            {"name": "data", "type": "string", "description": "JSON object with entry data", "required": True, "stdin": True},
        ],
    },
    {
        "name": "weak_spot_validate",
        "description": "Check weak-spots.md or coach-errors.md for format violations.",
        "script": "srs/weak_spot_writer.py",
        "subcommand": "validate",
        "args": [
            {"name": "path", "type": "string", "description": "Path to file or learning directory", "required": True, "positional": True},
        ],
    },
    {
        "name": "weak_spot_fix",
        "description": "Normalize weak-spots.md or coach-errors.md to canonical format.",
        "script": "srs/weak_spot_writer.py",
        "subcommand": "fix",
        "args": [
            {"name": "path", "type": "string", "description": "Path to file or learning directory", "required": True, "positional": True},
        ],
    },
    # --- Assessment Engine ---
    {
        "name": "assessment_init",
        "description": "Create questions.json for a new learning topic.",
        "script": "assessment/assessment_engine.py",
        "subcommand": "init",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
        ],
        "json_flag": True,
    },
    {
        "name": "assessment_add",
        "description": "Add a single assessment question to the question bank.",
        "script": "assessment/assessment_engine.py",
        "subcommand": "add",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
            {"name": "concept", "type": "string", "description": "Concept name", "required": True, "cli": "--concept"},
            {"name": "difficulty", "type": "integer", "description": "Difficulty level (1-5)", "required": True, "cli": "--difficulty"},
            {"name": "question_type", "type": "string", "description": "Question type", "required": True, "cli": "--type",
             "enum": ["free_recall", "conceptual", "application", "analysis", "transfer", "reverse"]},
            {"name": "text", "type": "string", "description": "Question text", "required": True, "cli": "--text"},
            {"name": "answer", "type": "string", "description": "Expected answer summary", "required": True, "cli": "--answer"},
            {"name": "tags", "type": "string", "description": "Comma-separated tags", "cli": "--tags"},
        ],
        "json_flag": True,
    },
    {
        "name": "assessment_add_batch",
        "description": "Add multiple assessment questions from a JSON array.",
        "script": "assessment/assessment_engine.py",
        "subcommand": "add-batch",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
            {"name": "data", "type": "string", "description": "JSON array of question objects", "required": True, "stdin": True},
        ],
        "json_flag": True,
    },
    {
        "name": "assessment_select",
        "description": "Adaptive question selection — recommends questions based on learner state.",
        "script": "assessment/assessment_engine.py",
        "subcommand": "select",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
            {"name": "count", "type": "integer", "description": "Number of questions to select", "cli": "--count"},
            {"name": "concept", "type": "string", "description": "Filter to specific concept", "cli": "--concept"},
            {"name": "min_mastery", "type": "string", "description": "Exclude concepts below this mastery level", "cli": "--min-mastery",
             "enum": ["introduced", "developing", "solid", "mastered"]},
        ],
        "json_flag": True,
    },
    {
        "name": "assessment_record",
        "description": "Record an assessment result for a question.",
        "script": "assessment/assessment_engine.py",
        "subcommand": "record",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
            {"name": "question_id", "type": "string", "description": "Question ID (e.g., q-1)", "required": True, "positional": True},
            {"name": "score", "type": "integer", "description": "Score: 0 (incorrect) or 1 (correct)", "required": True, "positional": True},
            {"name": "session", "type": "integer", "description": "Session number", "cli": "--session"},
            {"name": "quality", "type": "string", "description": "Response quality", "cli": "--quality",
             "enum": ["strong", "partial", "weak", "wrong"]},
            {"name": "notes", "type": "string", "description": "Brief evaluation notes", "cli": "--notes"},
        ],
        "json_flag": True,
    },
    {
        "name": "assessment_coverage",
        "description": "Coverage report — which concepts have questions and which don't.",
        "script": "assessment/assessment_engine.py",
        "subcommand": "coverage",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
        ],
        "json_flag": True,
    },
    {
        "name": "assessment_stats",
        "description": "Aggregate assessment statistics.",
        "script": "assessment/assessment_engine.py",
        "subcommand": "stats",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
        ],
        "json_flag": True,
    },
    {
        "name": "assessment_calibrate",
        "description": "Recompute learner calibration from assessment history.",
        "script": "assessment/assessment_engine.py",
        "subcommand": "calibrate",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
        ],
        "json_flag": True,
    },
    # --- Plateau Detector ---
    {
        "name": "plateau_detect",
        "description": "Detect learning plateaus from journal, SRS, and weak spot data. Returns signal (PLATEAU_LIKELY/NO_PLATEAU_DETECTED), recommended mode, and candidate modes.",
        "script": "plateau/plateau_detector.py",
        "subcommand": None,
        "args": [
            {"name": "journal_dir", "type": "string", "description": "Path to journal/ directory", "required": True, "cli": "--journal-dir"},
            {"name": "srs", "type": "string", "description": "Path to cards.srs.json", "required": True, "cli": "--srs"},
            {"name": "weak_spots", "type": "string", "description": "Path to weak-spots.md", "required": True, "cli": "--weak-spots"},
            {"name": "stale_ws_threshold", "type": "integer", "description": "Sessions before a weak spot is considered stale", "cli": "--stale-ws-threshold"},
            {"name": "flat_grade_window", "type": "integer", "description": "Number of recent grades to check for flatness", "cli": "--flat-grade-window"},
            {"name": "flat_grade_threshold", "type": "number", "description": "Grade variance threshold for flatness", "cli": "--flat-grade-threshold"},
        ],
    },
    # --- Coach Metrics ---
    {
        "name": "coach_snapshot",
        "description": "Compute a metrics snapshot. Creates metrics/ directory on first run, updates dashboard.md and history.json.",
        "script": "coach/coach_metrics.py",
        "subcommand": "snapshot",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
        ],
    },
    {
        "name": "coach_trends",
        "description": "Analyze metric trends over time.",
        "script": "coach/coach_metrics.py",
        "subcommand": "trends",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
        ],
    },
    {
        "name": "coach_compare",
        "description": "Compare metrics between two learning projects.",
        "script": "coach/coach_metrics.py",
        "subcommand": "compare",
        "args": [
            {"name": "path", "type": "string", "description": "Path to first learning directory", "required": True, "positional": True},
            {"name": "path2", "type": "string", "description": "Path to second learning directory", "required": True, "positional": True},
        ],
    },
    # --- Coach Reflector ---
    {
        "name": "coach_reflect",
        "description": "Analyze coach errors and propose behavioral rules. Returns candidates for coach review.",
        "script": "coach/coach_reflector.py",
        "subcommand": "reflect",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
        ],
    },
    {
        "name": "coach_evaluate",
        "description": "Evaluate effectiveness of existing coach insight rules.",
        "script": "coach/coach_reflector.py",
        "subcommand": "evaluate",
        "args": [
            {"name": "path", "type": "string", "description": "Path to learning directory", "required": True, "positional": True},
        ],
    },
    # --- Demo Index Writer ---
    {
        "name": "demo_append",
        "description": "Append a demo entry to docs/demos/index.html. JSON needs: weak_spot_id, weak_spot_description, demo_title, demo_filename, created_date.",
        "script": "demo/demo_index_writer.py",
        "subcommand": "append",
        "args": [
            {"name": "path", "type": "string", "description": "Path to docs/demos/ directory", "required": True, "positional": True},
            {"name": "data", "type": "string", "description": "JSON object with demo metadata", "required": True, "stdin": True},
        ],
    },
    {
        "name": "demo_validate",
        "description": "Check docs/demos/index.html for issues.",
        "script": "demo/demo_index_writer.py",
        "subcommand": "validate",
        "args": [
            {"name": "path", "type": "string", "description": "Path to docs/demos/ directory", "required": True, "positional": True},
        ],
    },
    # --- Session Metrics ---
    {
        "name": "session_metrics",
        "description": "Aggregate token consumption for a session (main context + subagents). Reads Claude Code session metrics and subagent token logs, writes a summary file for the clerk.",
        "script": "session_metrics.py",
        "subcommand": None,
        "args": [
            {"name": "session_id", "type": "string", "description": "Claude Code session ID. If omitted, reads the default /tmp/claude-session-metrics.json."},
            {"name": "topic_slug", "type": "string", "description": "Topic slug for the metrics output file name (e.g., react-hooks). Writes to /tmp/session-metrics-<slug>.txt.", "required": True},
            {"name": "learning_path", "type": "string", "description": "Path to the learning directory (for finding subagent-tokens.jsonl)"},
        ],
        "custom_dispatch": True,
    },
]


# ---------------------------------------------------------------------------
# Build MCP tool schemas from registry
# ---------------------------------------------------------------------------

def build_input_schema(tool_def):
    properties = {}
    required = []
    for arg in tool_def["args"]:
        prop = {"type": arg["type"], "description": arg["description"]}
        if "enum" in arg:
            prop["enum"] = arg["enum"]
        properties[arg["name"]] = prop
        if arg.get("required"):
            required.append(arg["name"])
    return {"type": "object", "properties": properties, "required": required}


def build_tools_list():
    tools = []
    for t in TOOL_DEFS:
        tools.append({
            "name": t["name"],
            "description": t["description"],
            "inputSchema": build_input_schema(t),
        })
    return tools


# ---------------------------------------------------------------------------
# Custom dispatch for tools that use Python modules directly
# ---------------------------------------------------------------------------

def dispatch_custom(tool_name, arguments):
    if tool_name == "session_metrics":
        try:
            from session_metrics import run as session_metrics_run
            result = session_metrics_run(
                session_id=arguments.get("session_id", ""),
                topic_slug=arguments.get("topic_slug", ""),
                learning_path=arguments.get("learning_path", ""),
            )
            if "error" in result:
                return False, result["error"]
            return True, result["summary"]
        except Exception as e:
            return False, f"session_metrics failed: {e}"
    return False, f"No custom dispatch for: {tool_name}"


# ---------------------------------------------------------------------------
# Dispatch: MCP tool call -> subprocess
# ---------------------------------------------------------------------------

def dispatch(tool_name, arguments):
    tool_def = None
    for t in TOOL_DEFS:
        if t["name"] == tool_name:
            tool_def = t
            break
    if tool_def is None:
        return False, f"Unknown tool: {tool_name}"

    if tool_def.get("custom_dispatch"):
        return dispatch_custom(tool_name, arguments)

    script = os.path.join(TOOLS_DIR, tool_def["script"])
    cmd = [sys.executable, script]

    if tool_def.get("subcommand"):
        cmd.append(tool_def["subcommand"])

    stdin_data = None

    for arg in tool_def["args"]:
        name = arg["name"]
        value = arguments.get(name)
        if value is None:
            continue

        if arg.get("stdin"):
            stdin_data = value if isinstance(value, str) else json.dumps(value)
            cmd.append("--stdin")
        elif arg.get("positional"):
            cmd.append(str(value))
        elif arg.get("cli"):
            if arg["type"] == "boolean":
                if value:
                    cmd.append(arg["cli"])
            else:
                cmd.extend([arg["cli"], str(value)])

    if tool_def.get("json_flag"):
        cmd.append("--json")

    try:
        result = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout
        if result.returncode != 0:
            error_msg = result.stderr.strip() or f"Exit code {result.returncode}"
            if output:
                output += f"\n\nSTDERR: {error_msg}"
            else:
                output = f"Error: {error_msg}"
        return True, output.strip() if output else "(no output)"
    except subprocess.TimeoutExpired:
        return False, "Tool execution timed out (30s)"
    except Exception as e:
        return False, f"Execution failed: {e}"


# ---------------------------------------------------------------------------
# MCP stdio transport — Content-Length framing (JSON-RPC 2.0)
# ---------------------------------------------------------------------------

def read_message():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.decode("utf-8")
        if line == "\r\n" or line == "\n":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()

    content_length = int(headers.get("Content-Length", 0))
    if content_length == 0:
        return None

    body = sys.stdin.buffer.read(content_length)
    return json.loads(body.decode("utf-8"))


def write_message(msg):
    body = json.dumps(msg)
    encoded = body.encode("utf-8")
    header = f"Content-Length: {len(encoded)}\r\n\r\n"
    sys.stdout.buffer.write(header.encode("utf-8"))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


# ---------------------------------------------------------------------------
# JSON-RPC handlers
# ---------------------------------------------------------------------------

def handle_initialize(request):
    return {
        "jsonrpc": "2.0",
        "id": request["id"],
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "ultralearn-tools", "version": "1.0.0"},
        },
    }


def handle_tools_list(request):
    return {
        "jsonrpc": "2.0",
        "id": request["id"],
        "result": {"tools": build_tools_list()},
    }


def handle_tools_call(request):
    name = request["params"]["name"]
    arguments = request["params"].get("arguments", {})
    ok, output = dispatch(name, arguments)
    if ok:
        return {
            "jsonrpc": "2.0",
            "id": request["id"],
            "result": {"content": [{"type": "text", "text": output}]},
        }
    else:
        return {
            "jsonrpc": "2.0",
            "id": request["id"],
            "result": {
                "content": [{"type": "text", "text": output}],
                "isError": True,
            },
        }


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    while True:
        msg = read_message()
        if msg is None:
            break

        method = msg.get("method", "")

        if method == "initialize":
            write_message(handle_initialize(msg))
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            write_message(handle_tools_list(msg))
        elif method == "tools/call":
            write_message(handle_tools_call(msg))
        elif "id" in msg:
            write_message({
                "jsonrpc": "2.0",
                "id": msg["id"],
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })


if __name__ == "__main__":
    main()
