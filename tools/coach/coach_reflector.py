#!/usr/bin/env python3
"""Coach self-reflection tool for the Sage system.

Analyzes coach error patterns and evaluates behavioral insight effectiveness.

Commands:
    reflect <path>     Cluster coach errors, propose behavioral rules
    evaluate <path>    Check if active insights reduced error recurrence

Zero external dependencies — Python 3.8+ stdlib only.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

ENTRY_RE = re.compile(r"^##\s+(CE|CP)-(\d+)\s*[—–-]\s*(.+)$")
FIELD_RE = re.compile(r"^\*\*([^*:]+?)(?::\*\*|\*\*:)\s*(.*)$")

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "and", "but", "or", "nor", "not", "so", "yet", "both",
    "either", "neither", "each", "every", "all", "any", "few", "more",
    "most", "other", "some", "such", "no", "only", "own", "same", "than",
    "too", "very", "just", "about", "up", "its", "it", "that", "this",
    "these", "those", "what", "which", "who", "whom", "when", "where",
    "why", "how", "if", "because", "until", "while", "although", "though",
}


def parse_coach_errors(path: Path) -> List[Dict[str, Any]]:
    """Parse coach-errors.md into structured entries."""
    errors_file = path / "coach-errors.md"
    if not errors_file.exists():
        return []

    text = errors_file.read_text(encoding="utf-8")
    lines = text.split("\n")
    entries: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    current_field: Optional[str] = None

    for line in lines:
        heading = ENTRY_RE.match(line.strip())
        if heading:
            if current:
                entries.append(current)
            kind = heading.group(1)
            num = int(heading.group(2))
            title = heading.group(3).strip()
            current = {
                "id": f"{kind}-{num}",
                "kind": kind,
                "number": num,
                "title": title,
                "session": 0,
                "what_happened": "",
                "correction": "",
                "root_cause": "",
                "status": "",
            }
            current_field = None
            continue

        if current is None:
            continue

        field = FIELD_RE.match(line.strip())
        if field:
            key = field.group(1).strip().lower().replace(" ", "_")
            value = field.group(2).strip()
            if key == "session":
                m = re.match(r"(\d+)", value)
                current["session"] = int(m.group(1)) if m else 0
            elif key in current:
                current[key] = value
            current_field = key
        elif current_field and line.strip():
            if current_field in current and isinstance(current.get(current_field), str):
                current[current_field] += " " + line.strip()

    if current:
        entries.append(current)

    return entries


def parse_coach_insights(path: Path) -> List[Dict[str, Any]]:
    """Parse coach-insights.md into structured CI-# entries."""
    insights_file = path / "coach-insights.md"
    if not insights_file.exists():
        return []

    text = insights_file.read_text(encoding="utf-8")
    lines = text.split("\n")
    insights: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    ci_re = re.compile(r"^###\s+CI-(\d+):\s*(.+)$")

    for line in lines:
        heading = ci_re.match(line.strip())
        if heading:
            if current:
                insights.append(current)
            current = {
                "id": f"CI-{heading.group(1)}",
                "number": int(heading.group(1)),
                "title": heading.group(2).strip(),
                "source": "",
                "rule": "",
                "adopted": 0,
                "status": "",
            }
            continue

        if current is None:
            continue

        # Strip leading "- " for list-style fields
        stripped = re.sub(r"^-\s+", "", line.strip())
        field = FIELD_RE.match(stripped)
        if field:
            key = field.group(1).strip().lower().replace(" ", "_")
            value = field.group(2).strip()
            if key == "adopted":
                m = re.match(r"Session\s+(\d+)", value, re.IGNORECASE)
                current["adopted"] = int(m.group(1)) if m else 0
            elif key == "source":
                current["source"] = value
            elif key == "rule":
                current["rule"] = value
            elif key == "status":
                current["status"] = value.lower()

    if current:
        insights.append(current)

    return insights


def parse_current_session(path: Path) -> int:
    """Determine current session number from journal/index.md."""
    index = path / "journal" / "index.md"
    if not index.exists():
        return 0

    text = index.read_text(encoding="utf-8")
    max_session = 0
    for line in text.split("\n"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().split("|")[1:-1]]
        if not cells or cells[0] == "#" or "---" in cells[0]:
            continue
        m = re.match(r"(\d+)", cells[0])
        if m:
            max_session = max(max_session, int(m.group(1)))

    return max_session


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def tokenize(text: str) -> Set[str]:
    """Extract meaningful keywords from text."""
    text = re.sub(r"[(){}[\]\"',;:!?.]", " ", text.lower())
    words = re.findall(r"[a-z][a-z0-9_@-]+", text)
    return {w for w in words if w not in STOP_WORDS and len(w) > 2}


def entry_keywords(entry: Dict[str, Any]) -> Set[str]:
    """Extract keywords from an error entry's key fields."""
    combined = f"{entry['title']} {entry['what_happened']} {entry['correction']}"
    return tokenize(combined)


def compute_similarity(kw1: Set[str], kw2: Set[str]) -> float:
    """Overlap coefficient: shared keywords / smaller set size.

    More robust than Jaccard for entries with many unique words — a small
    entry sharing 3 keywords with a large entry scores 3/5, not 3/22.
    """
    if not kw1 or not kw2:
        return 0.0
    intersection = kw1 & kw2
    return len(intersection) / min(len(kw1), len(kw2))


def cluster_errors(entries: List[Dict[str, Any]],
                   threshold: float = 0.20) -> List[List[Dict[str, Any]]]:
    """Group error entries by keyword similarity. Simple greedy clustering."""
    if not entries:
        return []

    keywords = [entry_keywords(e) for e in entries]
    assigned = [False] * len(entries)
    clusters: List[List[Dict[str, Any]]] = []

    for i in range(len(entries)):
        if assigned[i]:
            continue

        cluster = [entries[i]]
        assigned[i] = True
        cluster_kw = set(keywords[i])

        for j in range(i + 1, len(entries)):
            if assigned[j]:
                continue
            sim = compute_similarity(cluster_kw, keywords[j])
            if sim >= threshold:
                cluster.append(entries[j])
                assigned[j] = True
                cluster_kw |= keywords[j]

        clusters.append(cluster)

    return clusters


def label_cluster(cluster: List[Dict[str, Any]]) -> str:
    """Generate a descriptive label for a cluster based on shared keywords."""
    all_kw: Dict[str, int] = defaultdict(int)
    for entry in cluster:
        for kw in entry_keywords(entry):
            all_kw[kw] += 1

    # Keywords that appear in most entries
    min_count = max(1, len(cluster) // 2)
    common = sorted(
        [(kw, count) for kw, count in all_kw.items() if count >= min_count],
        key=lambda x: -x[1],
    )

    top = [kw for kw, _ in common[:5]]
    if top:
        return " ".join(top) + " errors"
    return "miscellaneous errors"


def propose_rule(cluster: List[Dict[str, Any]]) -> str:
    """Generate a candidate behavioral rule from a cluster of errors."""
    corrections = [e["correction"] for e in cluster if e["correction"]]
    if not corrections:
        return "Review and verify before teaching"

    # Find common theme from corrections
    all_kw: Dict[str, int] = defaultdict(int)
    for c in corrections:
        for kw in tokenize(c):
            all_kw[kw] += 1

    common = sorted(all_kw.items(), key=lambda x: -x[1])
    top_keywords = [kw for kw, _ in common[:6]]

    kinds = set(e["kind"] for e in cluster)
    if "CP" in kinds and "CE" not in kinds:
        return f"Process check: verify {', '.join(top_keywords[:3])} before proceeding"

    return f"Verify {', '.join(top_keywords[:3])} claims before teaching"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_reflect(path: Path) -> None:
    """Analyze coach errors and propose behavioral rules."""
    entries = parse_coach_errors(path)

    if len(entries) < 2:
        print(json.dumps({
            "candidates": [],
            "message": "Insufficient data for reflection",
            "total_errors_analyzed": len(entries),
        }, indent=2))
        return

    clusters = cluster_errors(entries)
    # Only propose rules for clusters with 2+ entries
    candidates = []
    skipped = []

    for cluster in clusters:
        if len(cluster) < 2:
            skipped.append({
                "entry": cluster[0]["id"],
                "reason": "singleton — no pattern",
            })
            continue

        source_ids = [e["id"] for e in cluster]
        pattern = label_cluster(cluster)
        rule = propose_rule(cluster)

        confidence = "high" if len(cluster) >= 4 else "medium" if len(cluster) >= 3 else "low"

        candidates.append({
            "pattern": pattern,
            "source_entries": source_ids,
            "proposed_rule": rule,
            "confidence": confidence,
            "error_count": len(cluster),
        })

    # Sort by error count descending
    candidates.sort(key=lambda x: -x["error_count"])

    print(json.dumps({
        "candidates": candidates,
        "skipped_clusters": skipped,
        "total_errors_analyzed": len(entries),
    }, indent=2))


def cmd_evaluate(path: Path) -> None:
    """Evaluate whether active insights have reduced error recurrence."""
    insights = parse_coach_insights(path)

    if not insights:
        print(json.dumps({
            "evaluations": [],
            "message": "No insights to evaluate",
        }, indent=2))
        return

    errors = parse_coach_errors(path)
    current_session = parse_current_session(path)

    # Build keyword fingerprints for each CI-#'s source errors
    error_by_id = {e["id"]: e for e in errors}

    evaluations = []
    for insight in insights:
        if insight["status"] not in ("active", "validated"):
            continue

        adopted = insight["adopted"]
        sessions_since = current_session - adopted if current_session > adopted else 0

        # Find source entry IDs from the Source field
        source_ids = re.findall(r"(CE-\d+|CP-\d+)", insight["source"])
        source_keywords: Set[str] = set()
        for sid in source_ids:
            if sid in error_by_id:
                source_keywords |= entry_keywords(error_by_id[sid])

        # Check for errors after adoption that match the pattern
        errors_since = 0
        for e in errors:
            if e["session"] <= adopted:
                continue
            if not source_keywords:
                continue
            sim = compute_similarity(source_keywords, entry_keywords(e))
            if sim >= 0.15:
                errors_since += 1

        if sessions_since >= 5 and errors_since == 0:
            recommended = "validated"
        elif errors_since > 0:
            recommended = "ineffective"
        else:
            recommended = insight["status"]

        evaluations.append({
            "id": insight["id"],
            "current_status": insight["status"],
            "sessions_since_adoption": sessions_since,
            "errors_since_adoption": errors_since,
            "recommended_status": recommended,
        })

    print(json.dumps({"evaluations": evaluations}, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_path(path_arg: str) -> Path:
    p = Path(path_arg).expanduser()
    return p


def main() -> None:
    parser = argparse.ArgumentParser(description="Coach self-reflection tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_ref = subparsers.add_parser("reflect", help="Analyze errors and propose rules")
    p_ref.add_argument("path", help="Path to learning directory")

    p_eval = subparsers.add_parser("evaluate", help="Evaluate insight effectiveness")
    p_eval.add_argument("path", help="Path to learning directory")

    args = parser.parse_args()
    path = _resolve_path(args.path)

    if args.command == "reflect":
        cmd_reflect(path)
    elif args.command == "evaluate":
        cmd_evaluate(path)


if __name__ == "__main__":
    main()
