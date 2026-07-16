#!/usr/bin/env python3
"""Session wrapup for Sage.

Bundles post-checkpoint scripts into a single invocation:
  1. coach_metrics.py snapshot
  2. coach_reflector.py evaluate
  3. session_duration.py (current-sitting wall time from the transcript)

Each step catches failures independently — partial results are returned.

Usage:
    python3 session_wrapup.py <sage_root> <topic_path> <topic_slug> [--session-id SESSION_ID]

Zero external dependencies — Python 3.8+ stdlib only.
"""

import json
import subprocess
import sys
import os


def run_script(cmd, label):
    """Run a script, return (ok, output_or_error)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip() or result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, f"{label} timed out after 30s"
    except Exception as e:
        return False, f"{label} failed: {e}"


def run(sage_root, topic_path, topic_slug, session_id=""):
    errors = []
    coach_metrics_flags = []
    insight_updates = []

    # 1. Coach metrics snapshot
    coach_metrics_ok, coach_metrics_out = run_script(
        ["python3", os.path.join(sage_root, "tools", "coach", "coach_metrics.py"),
         "snapshot", topic_path],
        "coach_metrics",
    )
    if not coach_metrics_ok:
        errors.append(f"coach_metrics: {coach_metrics_out}")
    else:
        for line in coach_metrics_out.splitlines():
            if "flag:" in line.lower() or "warning:" in line.lower():
                coach_metrics_flags.append(line.strip())

    # 2. Coach reflector evaluate
    insights_file = os.path.join(topic_path, "coach-insights.md")
    if os.path.isfile(insights_file):
        insights_ok, insights_out = run_script(
            ["python3", os.path.join(sage_root, "tools", "coach", "coach_reflector.py"),
             "evaluate", topic_path],
            "coach_reflector",
        )
        if not insights_ok:
            errors.append(f"coach_reflector: {insights_out}")
        else:
            for line in insights_out.splitlines():
                if "recommended" in line.lower() and "status" in line.lower():
                    insight_updates.append(line.strip())
    else:
        insights_ok = True

    # 3. Session duration (current-sitting wall time from the transcript)
    duration_cmd = [
        "python3", os.path.join(sage_root, "tools", "session_duration.py"),
    ]
    if session_id:
        duration_cmd.append(session_id)

    duration_ok, duration_out = run_script(duration_cmd, "session_duration")
    duration = duration_out if duration_ok and duration_out else None
    if not duration_ok:
        # Non-blocking: duration is best-effort. The clerk falls back to asking the learner.
        errors.append(f"session_duration: {duration_out}")

    return {
        "duration": duration,
        "coach_metrics_ok": coach_metrics_ok,
        "coach_metrics_flags": coach_metrics_flags,
        "insights_ok": insights_ok,
        "insight_updates": insight_updates,
        "errors": errors,
    }


def main():
    if len(sys.argv) < 4:
        print(
            "Usage: session_wrapup.py <sage_root> <topic_path> <topic_slug> [--session-id ID]",
            file=sys.stderr,
        )
        sys.exit(1)

    sage_root = sys.argv[1]
    topic_path = sys.argv[2]
    topic_slug = sys.argv[3]

    session_id = ""
    if "--session-id" in sys.argv:
        idx = sys.argv.index("--session-id")
        if idx + 1 < len(sys.argv):
            session_id = sys.argv[idx + 1]

    result = run(sage_root, topic_path, topic_slug, session_id)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
