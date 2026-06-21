#!/usr/bin/env python3
"""Assessment Engine — Adaptive question bank management for ultralearning.

Manages a per-topic question bank (questions.json), implements adaptive
selection based on concept mastery and learner performance, records results,
and tracks coverage.

Commands:
    init <path>                          Create questions.json from knowledge-map
    add <path> --concept C --difficulty D --type T --text Q --answer A
    add-batch <path>                     Add questions from stdin (JSON array)
    select <path> [--concept C] [--count N] [--min-mastery L]  Adaptive question selection
    record <path> <qid> <score> [--session N] [--quality Q] [--notes TEXT]
    coverage <path>                      Per-concept coverage report
    stats <path>                         Aggregate statistics
    calibrate <path>                     Recompute learner calibration

All commands output markdown by default, --json for machine-readable output.
Zero external dependencies — Python 3.8+ stdlib only.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

QUESTION_TYPES = ["free_recall", "conceptual", "application", "analysis", "transfer", "reverse"]

MASTERY_TO_TYPES = {
    "not started": ["free_recall", "conceptual"],
    "introduced": ["free_recall", "conceptual"],
    "developing": ["application", "conceptual", "free_recall"],
    "solid": ["analysis", "transfer", "application"],
    "mastered": ["transfer", "reverse", "analysis"],
}

MASTERY_TO_BASE_DIFFICULTY = {
    "not started": 1,
    "introduced": 1,
    "developing": 2,
    "solid": 3,
    "mastered": 4,
}

MASTERY_ORDER = ["not started", "introduced", "developing", "solid", "mastered"]


# ---------------------------------------------------------------------------
# Knowledge Map Reader — parses knowledge-map.md (read-only)
# ---------------------------------------------------------------------------

class KnowledgeMapReader:
    """Parse knowledge-map.md to extract concept statuses."""

    TABLE_ROW_RE = re.compile(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|$")

    @staticmethod
    def parse(text: str) -> Dict[str, Dict[str, str]]:
        """Parse knowledge-map markdown table.

        Returns:
            Dict mapping concept name -> {status, last_tested, notes}
        """
        concepts = {}
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("|--") or line.startswith("| Concept"):
                continue
            match = KnowledgeMapReader.TABLE_ROW_RE.match(line)
            if match:
                concept = match.group(1).strip()
                status = match.group(2).strip().lower()
                last_tested = match.group(3).strip()
                notes = match.group(4).strip()
                if status in MASTERY_ORDER:
                    concepts[concept] = {
                        "status": status,
                        "last_tested": last_tested,
                        "notes": notes,
                    }
        return concepts

    @staticmethod
    def read_from_path(path: Path) -> Dict[str, Dict[str, str]]:
        """Read and parse knowledge-map.md from a learning directory."""
        km_path = path / "knowledge-map.md" if path.is_dir() else path
        if not km_path.exists():
            return {}
        return KnowledgeMapReader.parse(km_path.read_text())


# ---------------------------------------------------------------------------
# Question Bank — manages questions.json
# ---------------------------------------------------------------------------

class QuestionBank:
    """Manages the questions.json question bank."""

    VERSION = "1.0"

    @staticmethod
    def bank_path(topic_dir: Path) -> Path:
        return topic_dir / "questions.json"

    @staticmethod
    def create(topic: str, concepts: Dict[str, Dict[str, str]], today: str) -> Dict[str, Any]:
        """Create a new empty question bank."""
        coverage = {}
        for concept in concepts:
            coverage[concept] = {
                "total_questions": 0,
                "questions_by_difficulty": {},
                "questions_by_type": {},
                "last_assessed": None,
                "assessment_count": 0,
            }
        return {
            "version": QuestionBank.VERSION,
            "topic": topic,
            "created": today,
            "last_updated": today,
            "learner_calibration": {
                "estimated_level": 3.0,
                "total_questions_answered": 0,
                "level_history": [],
            },
            "questions": {},
            "coverage": coverage,
        }

    @staticmethod
    def load(path: Path) -> Dict[str, Any]:
        with open(path, "r") as f:
            return json.load(f)

    @staticmethod
    def save(path: Path, data: Dict[str, Any]) -> None:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    @staticmethod
    def next_id(bank: Dict[str, Any]) -> str:
        """Get the next sequential question ID."""
        existing = bank.get("questions", {})
        if not existing:
            return "q-1"
        max_num = max(int(k.split("-")[1]) for k in existing)
        return f"q-{max_num + 1}"

    @staticmethod
    def add_question(bank: Dict[str, Any], concept: str, difficulty: int,
                     qtype: str, text: str, answer: str, tags: Optional[List[str]] = None,
                     today: Optional[str] = None) -> str:
        """Add a question to the bank. Returns the assigned ID."""
        today = today or date.today().isoformat()
        qid = QuestionBank.next_id(bank)
        bank["questions"][qid] = {
            "question_id": qid,
            "concept": concept,
            "difficulty": difficulty,
            "question_type": qtype,
            "question_text": text,
            "expected_answer_summary": answer,
            "tags": tags or [concept],
            "created": today,
            "created_by": "agent",
            "times_asked": 0,
            "times_correct": 0,
            "success_rate": 0.0,
            "last_asked": None,
            "result_history": [],
            "retired": False,
        }
        # Update coverage
        QuestionBank._update_coverage_on_add(bank, concept, difficulty, qtype)
        bank["last_updated"] = today
        return qid

    @staticmethod
    def _update_coverage_on_add(bank: Dict[str, Any], concept: str,
                                difficulty: int, qtype: str) -> None:
        if concept not in bank["coverage"]:
            bank["coverage"][concept] = {
                "total_questions": 0,
                "questions_by_difficulty": {},
                "questions_by_type": {},
                "last_assessed": None,
                "assessment_count": 0,
            }
        cov = bank["coverage"][concept]
        cov["total_questions"] += 1
        d_key = str(difficulty)
        cov["questions_by_difficulty"][d_key] = cov["questions_by_difficulty"].get(d_key, 0) + 1
        cov["questions_by_type"][qtype] = cov["questions_by_type"].get(qtype, 0) + 1

    @staticmethod
    def record_result(bank: Dict[str, Any], qid: str, score: int,
                      session: Optional[int] = None, quality: str = "partial",
                      notes: str = "", today: Optional[str] = None) -> None:
        """Record an assessment result for a question."""
        today = today or date.today().isoformat()
        q = bank["questions"][qid]
        q["times_asked"] += 1
        if score > 0:
            q["times_correct"] += 1
        q["success_rate"] = round(q["times_correct"] / q["times_asked"], 4) if q["times_asked"] > 0 else 0.0
        q["last_asked"] = today

        entry = {
            "date": today,
            "session": session,
            "score": score,
            "max_score": 1,
            "response_quality": quality,
            "notes": notes,
        }
        q["result_history"].append(entry)
        if len(q["result_history"]) > 30:
            q["result_history"] = q["result_history"][-30:]

        # Update coverage
        concept = q["concept"]
        if concept in bank["coverage"]:
            bank["coverage"][concept]["last_assessed"] = today
            bank["coverage"][concept]["assessment_count"] += 1

        # Update learner calibration
        cal = bank["learner_calibration"]
        cal["total_questions_answered"] += 1
        bank["last_updated"] = today

    @staticmethod
    def calibrate(bank: Dict[str, Any]) -> float:
        """Recompute learner calibration from all result history."""
        total_weighted = 0.0
        total_weight = 0.0
        for q in bank["questions"].values():
            if q["retired"] or q["times_asked"] == 0:
                continue
            difficulty = q["difficulty"]
            for result in q["result_history"]:
                weight = difficulty  # harder questions weigh more
                if result["score"] > 0:
                    total_weighted += difficulty * weight
                total_weight += weight

        if total_weight > 0:
            level = round(total_weighted / total_weight, 2)
            level = max(1.0, min(5.0, level))
        else:
            level = 3.0

        bank["learner_calibration"]["estimated_level"] = level
        bank["learner_calibration"]["level_history"].append({
            "date": date.today().isoformat(),
            "level": level,
        })
        return level


# ---------------------------------------------------------------------------
# Adaptive Selector — stateless selection algorithm
# ---------------------------------------------------------------------------

class AdaptiveSelector:
    """Implements the 4-step adaptive selection algorithm."""

    @staticmethod
    def concept_priority(concept: str, bank: Dict[str, Any],
                         mastery: str, today: str) -> float:
        """Compute priority score for a concept."""
        cov = bank.get("coverage", {}).get(concept, {})

        # Recency weight
        last_assessed = cov.get("last_assessed")
        if not last_assessed:
            recency_weight = 5.0
        else:
            days = (date.fromisoformat(today) - date.fromisoformat(last_assessed)).days
            recency_weight = min(days / 7.0, 3.0)

        # Weakness weight
        concept_questions = [q for q in bank.get("questions", {}).values()
                             if q["concept"] == concept and not q["retired"] and q["times_asked"] > 0]
        if concept_questions:
            avg_success = sum(q["success_rate"] for q in concept_questions) / len(concept_questions)
            if avg_success < 0.5:
                weakness_weight = 3.0
            elif avg_success < 0.7:
                weakness_weight = 1.5
            else:
                weakness_weight = 0.0
        else:
            weakness_weight = 0.0

        # Coverage weight
        total_q = cov.get("total_questions", 0)
        if total_q < 3:
            coverage_weight = 2.0
        elif total_q < 5:
            coverage_weight = 1.0
        else:
            coverage_weight = 0.0

        return recency_weight + weakness_weight + coverage_weight

    @staticmethod
    def target_difficulty(concept: str, bank: Dict[str, Any], mastery: str) -> int:
        """Compute target difficulty for a concept."""
        base = MASTERY_TO_BASE_DIFFICULTY.get(mastery, 2)

        # Performance adjustment from last 3 results
        concept_results = []
        for q in bank.get("questions", {}).values():
            if q["concept"] == concept and not q["retired"]:
                for r in q.get("result_history", []):
                    concept_results.append(r)

        concept_results.sort(key=lambda r: r.get("date", ""), reverse=True)
        last_3 = concept_results[:3]

        if len(last_3) >= 3:
            correct = sum(1 for r in last_3 if r["score"] > 0)
            if correct == 3:
                adjustment = 1
            elif correct == 0:
                adjustment = -1
            else:
                adjustment = 0
        else:
            adjustment = 0

        return max(1, min(5, base + adjustment))

    @staticmethod
    def select_question_type(mastery: str, bank: Dict[str, Any],
                             concept: str) -> str:
        """Select question type based on mastery and coverage gaps."""
        valid_types = MASTERY_TO_TYPES.get(mastery, ["free_recall", "conceptual"])
        cov = bank.get("coverage", {}).get(concept, {})
        type_counts = cov.get("questions_by_type", {})

        # Prefer types with fewer questions asked
        scored = []
        for t in valid_types:
            count = type_counts.get(t, 0)
            scored.append((count, t))
        scored.sort()
        return scored[0][1]

    @staticmethod
    def select_from_bank(bank: Dict[str, Any], concept: str,
                         difficulty: int, qtype: str,
                         today: str) -> Optional[Dict[str, Any]]:
        """Find the best existing question from the bank.

        Returns the question dict, or None if no suitable question exists.
        """
        candidates = []
        for q in bank.get("questions", {}).values():
            if q["retired"]:
                continue
            if q["concept"] != concept:
                continue
            if abs(q["difficulty"] - difficulty) > 1:
                continue
            if q["question_type"] != qtype:
                continue
            candidates.append(q)

        if not candidates:
            return None

        # Sort: prefer unasked, then oldest asked, then lowest success rate
        def sort_key(q):
            asked = q["times_asked"]
            last = q.get("last_asked") or "0000-00-00"
            success = q["success_rate"]
            return (0 if asked == 0 else 1, last, success)

        candidates.sort(key=sort_key)
        return candidates[0]

    @staticmethod
    def select(bank: Dict[str, Any], knowledge_map: Dict[str, Dict[str, str]],
               today: str, count: int = 1,
               filter_concept: Optional[str] = None,
               min_mastery: Optional[str] = None) -> List[Dict[str, Any]]:
        """Run the full 4-step adaptive selection.

        Returns a list of recommendation dicts, each with either:
        - action: "ask", question_id, question_text, ...  (existing question)
        - action: "generate", concept, difficulty, question_type  (needs generation)
        """
        recommendations = []
        used_qids = set()

        # Build concept list with priorities
        concepts = {}
        if filter_concept:
            if filter_concept in knowledge_map:
                concepts[filter_concept] = knowledge_map[filter_concept]
            else:
                concepts[filter_concept] = {"status": "introduced"}
        else:
            concepts = knowledge_map

        # Filter by minimum mastery level if specified
        if min_mastery:
            min_idx = MASTERY_ORDER.index(min_mastery)
            concepts = {c: v for c, v in concepts.items()
                        if MASTERY_ORDER.index(v.get("status", "not started")) >= min_idx}

        if not concepts:
            return []

        for _ in range(count):
            # Step 1: Concept priority
            scored = []
            for c, info in concepts.items():
                mastery = info.get("status", "introduced")
                priority = AdaptiveSelector.concept_priority(c, bank, mastery, today)
                scored.append((priority, MASTERY_ORDER.index(mastery) if mastery in MASTERY_ORDER else 0, c))
            # Sort by priority desc, then mastery asc (lower mastery = more need)
            scored.sort(key=lambda x: (-x[0], x[1]))

            if not scored:
                break

            _, _, concept = scored[0]
            mastery = concepts[concept].get("status", "introduced")

            # Step 2: Difficulty
            difficulty = AdaptiveSelector.target_difficulty(concept, bank, mastery)

            # Step 3: Question type
            qtype = AdaptiveSelector.select_question_type(mastery, bank, concept)

            # Step 4: Bank lookup
            question = AdaptiveSelector.select_from_bank(bank, concept, difficulty, qtype, today)

            if question and question["question_id"] not in used_qids:
                used_qids.add(question["question_id"])
                recommendations.append({
                    "action": "ask",
                    "question_id": question["question_id"],
                    "concept": concept,
                    "difficulty": question["difficulty"],
                    "question_type": question["question_type"],
                    "question_text": question["question_text"],
                    "expected_answer_summary": question["expected_answer_summary"],
                })
            else:
                recommendations.append({
                    "action": "generate",
                    "concept": concept,
                    "difficulty": difficulty,
                    "question_type": qtype,
                })

            # Reduce priority for this concept in subsequent iterations
            if concept in concepts and len(concepts) > 1:
                concepts = {c: v for c, v in concepts.items() if c != concept}

        return recommendations


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

class MarkdownFormatter:

    @staticmethod
    def init_result(count: int, path: str) -> str:
        return f"Initialized assessment bank with {count} concepts at `{path}`."

    @staticmethod
    def add_result(qid: str, concept: str, difficulty: int, qtype: str) -> str:
        return f"Added **{qid}**: {concept} (difficulty {difficulty}, {qtype})"

    @staticmethod
    def select_list(recs: List[Dict[str, Any]]) -> str:
        if not recs:
            return "No questions to recommend. Add concepts to the knowledge map first."
        lines = ["## Assessment Recommendations", ""]
        for i, r in enumerate(recs, 1):
            if r["action"] == "ask":
                lines.append(f"### {i}. {r['question_id']} ({r['concept']}, difficulty {r['difficulty']}, {r['question_type']})")
                lines.append(f"**Q:** {r['question_text']}")
                lines.append("")
            else:
                lines.append(f"### {i}. [GENERATE] ({r['concept']}, difficulty {r['difficulty']}, {r['question_type']})")
                lines.append(f"No suitable question in bank. Generate a new {r['question_type']} question for **{r['concept']}** at difficulty {r['difficulty']}.")
                lines.append("")
        return "\n".join(lines)

    @staticmethod
    def record_result(qid: str, score: int, quality: str) -> str:
        status = "correct" if score > 0 else "incorrect"
        return f"Recorded: **{qid}** — {status} ({quality})"

    @staticmethod
    def coverage(bank: Dict[str, Any]) -> str:
        cov = bank.get("coverage", {})
        if not cov:
            return "No coverage data. Run `init` first."
        lines = ["## Assessment Coverage", ""]
        lines.append("| Concept | Questions | By Difficulty | Last Assessed | Assessments |")
        lines.append("|---------|-----------|---------------|---------------|-------------|")
        for concept, data in sorted(cov.items()):
            total = data.get("total_questions", 0)
            by_diff = data.get("questions_by_difficulty", {})
            diff_str = ", ".join(f"D{k}:{v}" for k, v in sorted(by_diff.items()))
            last = data.get("last_assessed") or "never"
            count = data.get("assessment_count", 0)
            lines.append(f"| {concept} | {total} | {diff_str} | {last} | {count} |")

        # Summary
        total_q = sum(d.get("total_questions", 0) for d in cov.values())
        never_assessed = sum(1 for d in cov.values() if not d.get("last_assessed"))
        lines.append("")
        lines.append(f"**Total:** {total_q} questions across {len(cov)} concepts. {never_assessed} concepts never assessed.")
        return "\n".join(lines)

    @staticmethod
    def stats(bank: Dict[str, Any]) -> str:
        questions = bank.get("questions", {})
        active = {k: v for k, v in questions.items() if not v.get("retired")}
        retired = len(questions) - len(active)
        cal = bank.get("learner_calibration", {})

        by_diff: Dict[int, int] = {}
        by_type: Dict[str, int] = {}
        total_asked = 0
        total_correct = 0
        for q in active.values():
            d = q.get("difficulty", 0)
            by_diff[d] = by_diff.get(d, 0) + 1
            t = q.get("question_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
            total_asked += q.get("times_asked", 0)
            total_correct += q.get("times_correct", 0)

        overall_rate = round(total_correct / total_asked, 2) if total_asked > 0 else 0.0

        lines = [
            f"## Assessment Statistics: {bank.get('topic', 'unknown')}",
            "",
            f"- **Total questions:** {len(questions)} ({len(active)} active, {retired} retired)",
            f"- **By difficulty:** {', '.join(f'D{k}: {v}' for k, v in sorted(by_diff.items()))}",
            f"- **By type:** {', '.join(f'{k}: {v}' for k, v in sorted(by_type.items()))}",
            f"- **Total assessments:** {total_asked}",
            f"- **Overall success rate:** {overall_rate}",
            f"- **Learner level:** {cal.get('estimated_level', '?')}",
            f"- **Created:** {bank.get('created', '?')}",
            f"- **Last updated:** {bank.get('last_updated', '?')}",
        ]
        return "\n".join(lines)

    @staticmethod
    def calibrate_result(level: float) -> str:
        return f"Learner calibration recomputed: **level {level:.2f}**"


class JsonFormatter:
    @staticmethod
    def output(data: Any) -> str:
        return json.dumps(data, indent=2, default=str)


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------

def _resolve_path(path_arg: str) -> Path:
    p = Path(path_arg)
    if p.is_dir():
        return p
    return p.parent


def _derive_topic(path: Path) -> str:
    parts = path.parts
    for i, part in enumerate(parts):
        if part == "learning" and i + 1 < len(parts):
            return parts[i + 1]
    return path.name or "unknown"


def _today() -> str:
    return date.today().isoformat()


def cmd_init(args: argparse.Namespace) -> str:
    path = _resolve_path(args.path)
    bp = QuestionBank.bank_path(path)

    if bp.exists() and not getattr(args, "force", False):
        return f"Error: {bp} already exists. Use --force to overwrite."

    knowledge_map = KnowledgeMapReader.read_from_path(path)
    topic = _derive_topic(path)
    today = _today()
    bank = QuestionBank.create(topic, knowledge_map, today)
    QuestionBank.save(bp, bank)

    if args.json:
        return JsonFormatter.output({"action": "init", "concepts": len(knowledge_map), "path": str(bp)})
    return MarkdownFormatter.init_result(len(knowledge_map), str(bp))


def cmd_add(args: argparse.Namespace) -> str:
    path = _resolve_path(args.path)
    bp = QuestionBank.bank_path(path)
    if not bp.exists():
        return f"Error: {bp} not found. Run `init` first."

    bank = QuestionBank.load(bp)
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
    qid = QuestionBank.add_question(
        bank, args.concept, args.difficulty, args.type,
        args.text, args.answer, tags, _today()
    )
    QuestionBank.save(bp, bank)

    if args.json:
        return JsonFormatter.output({"action": "add", "question_id": qid, "concept": args.concept})
    return MarkdownFormatter.add_result(qid, args.concept, args.difficulty, args.type)


def cmd_add_batch(args: argparse.Namespace) -> str:
    path = _resolve_path(args.path)
    bp = QuestionBank.bank_path(path)
    if not bp.exists():
        return f"Error: {bp} not found. Run `init` first."

    bank = QuestionBank.load(bp)
    data = json.loads(sys.stdin.read())
    today = _today()
    added = []
    for item in data:
        qid = QuestionBank.add_question(
            bank, item["concept"], item["difficulty"], item["question_type"],
            item["question_text"], item["expected_answer_summary"],
            item.get("tags"), today
        )
        added.append(qid)
    QuestionBank.save(bp, bank)

    if args.json:
        return JsonFormatter.output({"action": "add-batch", "added": added, "count": len(added)})
    return f"Added {len(added)} questions: {', '.join(added)}"


def cmd_select(args: argparse.Namespace) -> str:
    path = _resolve_path(args.path)
    bp = QuestionBank.bank_path(path)
    if not bp.exists():
        return f"Error: {bp} not found. Run `init` first."

    bank = QuestionBank.load(bp)
    knowledge_map = KnowledgeMapReader.read_from_path(path)
    today = _today()
    count = args.count or 3
    concept = args.concept if hasattr(args, "concept") and args.concept else None

    min_mastery = getattr(args, "min_mastery", None)
    recs = AdaptiveSelector.select(bank, knowledge_map, today, count, concept, min_mastery)

    if args.json:
        return JsonFormatter.output({"action": "select", "count": len(recs), "recommendations": recs})
    return MarkdownFormatter.select_list(recs)


def cmd_record(args: argparse.Namespace) -> str:
    path = _resolve_path(args.path)
    bp = QuestionBank.bank_path(path)
    if not bp.exists():
        return f"Error: {bp} not found. Run `init` first."

    bank = QuestionBank.load(bp)
    qid = args.question_id
    if qid not in bank["questions"]:
        return f"Error: Question '{qid}' not found."

    score = args.score
    if score not in (0, 1):
        return "Error: Score must be 0 or 1."

    quality = args.quality or "partial"
    session = args.session
    notes = args.notes or ""

    QuestionBank.record_result(bank, qid, score, session, quality, notes, _today())
    QuestionBank.save(bp, bank)

    if args.json:
        q = bank["questions"][qid]
        return JsonFormatter.output({
            "action": "record", "question_id": qid, "score": score,
            "quality": quality, "success_rate": q["success_rate"],
            "times_asked": q["times_asked"],
        })
    return MarkdownFormatter.record_result(qid, score, quality)


def cmd_coverage(args: argparse.Namespace) -> str:
    path = _resolve_path(args.path)
    bp = QuestionBank.bank_path(path)
    if not bp.exists():
        return f"Error: {bp} not found. Run `init` first."

    bank = QuestionBank.load(bp)
    if args.json:
        return JsonFormatter.output({"action": "coverage", "coverage": bank.get("coverage", {})})
    return MarkdownFormatter.coverage(bank)


def cmd_stats(args: argparse.Namespace) -> str:
    path = _resolve_path(args.path)
    bp = QuestionBank.bank_path(path)
    if not bp.exists():
        return f"Error: {bp} not found. Run `init` first."

    bank = QuestionBank.load(bp)
    if args.json:
        questions = bank["questions"]
        active = {k: v for k, v in questions.items() if not v.get("retired")}
        return JsonFormatter.output({
            "action": "stats",
            "total": len(questions),
            "active": len(active),
            "retired": len(questions) - len(active),
            "total_assessments": sum(q.get("times_asked", 0) for q in active.values()),
            "learner_level": bank.get("learner_calibration", {}).get("estimated_level"),
        })
    return MarkdownFormatter.stats(bank)


def cmd_calibrate(args: argparse.Namespace) -> str:
    path = _resolve_path(args.path)
    bp = QuestionBank.bank_path(path)
    if not bp.exists():
        return f"Error: {bp} not found. Run `init` first."

    bank = QuestionBank.load(bp)
    level = QuestionBank.calibrate(bank)
    QuestionBank.save(bp, bank)

    if args.json:
        return JsonFormatter.output({"action": "calibrate", "level": level})
    return MarkdownFormatter.calibrate_result(level)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="assessment_engine",
        description="Adaptive Assessment Engine for Ultralearning",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p = subparsers.add_parser("init", help="Create questions.json")
    p.add_argument("path", help="Path to learning/<topic-slug>/ directory")
    p.add_argument("--json", action="store_true")
    p.add_argument("--force", action="store_true")

    # add
    p = subparsers.add_parser("add", help="Add a question")
    p.add_argument("path")
    p.add_argument("--concept", required=True)
    p.add_argument("--difficulty", type=int, required=True)
    p.add_argument("--type", required=True, choices=QUESTION_TYPES)
    p.add_argument("--text", required=True)
    p.add_argument("--answer", required=True)
    p.add_argument("--tags", default=None)
    p.add_argument("--json", action="store_true")

    # add-batch
    p = subparsers.add_parser("add-batch", help="Add questions from stdin JSON")
    p.add_argument("path")
    p.add_argument("--json", action="store_true")

    # select
    p = subparsers.add_parser("select", help="Adaptive question selection")
    p.add_argument("path")
    p.add_argument("--concept", default=None)
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--min-mastery", default=None,
                   choices=["introduced", "developing", "solid", "mastered"],
                   help="Exclude concepts below this mastery level from selection")
    p.add_argument("--json", action="store_true")

    # record
    p = subparsers.add_parser("record", help="Record an assessment result")
    p.add_argument("path")
    p.add_argument("question_id")
    p.add_argument("score", type=int)
    p.add_argument("--session", type=int, default=None)
    p.add_argument("--quality", default="partial", choices=["strong", "partial", "weak", "wrong"])
    p.add_argument("--notes", default="")
    p.add_argument("--json", action="store_true")

    # coverage
    p = subparsers.add_parser("coverage", help="Coverage report")
    p.add_argument("path")
    p.add_argument("--json", action="store_true")

    # stats
    p = subparsers.add_parser("stats", help="Aggregate statistics")
    p.add_argument("path")
    p.add_argument("--json", action="store_true")

    # calibrate
    p = subparsers.add_parser("calibrate", help="Recompute learner calibration")
    p.add_argument("path")
    p.add_argument("--json", action="store_true")

    return parser


COMMANDS = {
    "init": cmd_init,
    "add": cmd_add,
    "add-batch": cmd_add_batch,
    "select": cmd_select,
    "record": cmd_record,
    "coverage": cmd_coverage,
    "stats": cmd_stats,
    "calibrate": cmd_calibrate,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = COMMANDS.get(args.command)
    if not handler:
        parser.print_help()
        return 1
    try:
        result = handler(args)
        print(result)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
