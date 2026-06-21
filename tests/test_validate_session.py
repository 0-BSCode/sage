#!/usr/bin/env python3
"""Tests for tools/lateral/validate_session.py"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "lateral" / "validate_session.py"

PASS = 0
FAIL = 0


def run(session_text: str) -> dict:
    """Write session_text to a temp file and run validate on it."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(session_text)
        f.flush()
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate", f.name],
            capture_output=True, text=True,
        )
    return json.loads(result.stdout)


def assert_eq(test_name: str, expected, actual):
    global PASS, FAIL
    if expected == actual:
        print(f"  PASS: {test_name}")
        PASS += 1
    else:
        print(f"  FAIL: {test_name}")
        print(f"    expected: {expected}")
        print(f"    got: {actual}")
        FAIL += 1


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

COMPLETE_RANDOM_ENTRY = """\
# Session 1: How to reduce deployment friction
**Date:** 2026-04-01
**Format:** Random Entry (15 min)
**Status:** complete

---

## Phase 1: Focus (0:00-2:00)

**Problem statement:**
Deployments take too long and require manual steps that cause errors.

**Is this the real problem, or a symptom?**
It's a symptom of missing automation in the CI pipeline.

**Dominant assumption:**
We need more engineers to review deployments.

**Success looks like:**
One-click deploy with automated rollback.

---

## Phase 2: Generate (2:00-10:00)

**Technique:** Random Entry
**Random word:** umbrella
**Target:** 10+ ideas

### Attributes of "umbrella"
1. Provides shelter
2. Foldable
3. Has a handle
4. Lightweight
5. Portable

### Forced Connections

| # | Attribute | Connection to problem |
|---|-----------|----------------------|
| 1 | Provides shelter | Create a "shelter" staging env that catches errors before prod |
| 2 | Foldable | Make the pipeline collapsible — skip steps when confidence is high |
| 3 | Has a handle | Add a single control point (dashboard) for all deploy actions |
| 4 | Lightweight | Strip the deploy script to bare essentials |
| 5 | Portable | Make deploys work from any machine, not just CI |

---

## Phase 3: Harvest (10:00-13:00)

**[NOW] Implement immediately:**
- Build the single deploy dashboard
- Strip deploy script to essentials

**[LATER] Worth exploring:**
- Collapsible pipeline steps

**[EXPLORE] Needs research:**
- Portable deploy from any machine

---

## Phase 4: Treat (13:00-15:00)

| Idea | Next Step | By When | Who |
|------|-----------|---------|-----|
| Deploy dashboard | Create wireframe | 2026-04-05 | Me |
| Strip deploy script | Audit current script | 2026-04-03 | Me |
"""

EMPTY_SCAFFOLD = """\
# Session 1: {problem_statement}
**Date:** 2026-04-01
**Format:** Random Entry (15 min)
**Status:** in-progress

---

## Phase 1: Focus (0:00-2:00)

**Problem statement:**


**Is this the real problem, or a symptom?**


**Dominant assumption:**


**Success looks like:**


---

## Phase 2: Generate (2:00-10:00)

**Technique:** Random Entry
**Random word:** umbrella
**Target:** 10+ ideas

### Attributes of "umbrella"
1.
2.
3.
4.
5.

### Forced Connections

| # | Attribute | Connection to problem |
|---|-----------|----------------------|
| 1 | | |
| 2 | | |
| 3 | | |

---

## Phase 3: Harvest (10:00-13:00)

**[NOW] Implement immediately:**
-

**[LATER] Worth exploring:**
-

---

## Phase 4: Treat (13:00-15:00)

| Idea | Next Step | By When | Who |
|------|-----------|---------|-----|
| | | | |
"""

COMPLETE_SIX_HATS = """\
# Session 2: Should we migrate to a monorepo?
**Date:** 2026-04-02
**Format:** Six Thinking Hats (20 min)
**Status:** complete

---

## Phase 1: Focus

**Decision to make:**
Whether to consolidate three repos into a monorepo.

**Options on the table:**
- Keep separate repos with better tooling
- Full monorepo migration
- Partial monorepo (shared libs only)

---

## Blue Hat (0:00-1:00) - Set the Goal

**What am I thinking about?**
Deciding if a monorepo is worth the migration cost.

---

## White Hat (1:00-4:00) - Facts

- Current setup: 3 repos, shared code copied between them
- Build times: 8 min average per repo
- Team size: 5 engineers
- Migration estimate: 2 weeks

---

## Yellow Hat (4:00-7:00) - Benefits

- Single CI pipeline reduces maintenance
- Atomic cross-repo changes become trivial
- Code sharing via imports instead of copy-paste
- Unified dependency management

---

## Black Hat (7:00-10:00) - Risks

- Migration downtime and broken builds
- Monorepo tooling learning curve (nx/turborepo)
- Larger clone sizes for contributors
- Risk of tighter coupling between services

---

## Green Hat (10:00-14:00) - Alternatives

- Keep repos but add a shared packages repo
- Use git submodules for shared code
- Monorepo with strict module boundaries enforced by CI
- Partial migration: merge only the two most coupled repos

---

## Blue Hat (14:00-17:00) - Decision and Next Steps

**Decision:** Partial monorepo — merge the two most coupled repos first as a trial.

1. Identify the two most coupled repos by measuring cross-repo PRs
2. Set up turborepo config for the merged repo
3. Run parallel CI for 1 week before cutting over
"""

PARTIAL_SESSION = """\
# Session 3: Improve onboarding
**Date:** 2026-04-03
**Format:** Random Entry (15 min)
**Status:** in-progress

---

## Phase 1: Focus (0:00-2:00)

**Problem statement:**
New hires take 3 weeks to ship their first PR.

**Is this the real problem, or a symptom?**
Symptom — the real issue is lack of documentation and pairing.

**Dominant assumption:**
We need a better onboarding doc.

**Success looks like:**
First PR within 5 business days.

---

## Phase 2: Generate (2:00-10:00)

**Technique:** Random Entry
**Random word:** bridge
**Target:** 10+ ideas

### Attributes of "bridge"
1. Connects two sides
2. Has load limits
3. Built incrementally
4. Requires foundations
5. Multiple designs for different needs

### Forced Connections

| # | Attribute | Connection to problem |
|---|-----------|----------------------|
| 1 | Connects two sides | Pair each new hire with a "bridge" buddy |
| 2 | Has load limits | Limit first PR scope to reduce overwhelm |
| 3 | Built incrementally | Progressive onboarding tasks, not a doc dump |
| 4 | Requires foundations | Ensure dev env setup is fully automated first |
| 5 | Multiple designs | Different onboarding tracks for frontend vs backend |

---

## Phase 3: Harvest (10:00-13:00)

**[NOW] Implement immediately:**
-

**[LATER] Worth exploring:**
- Progressive task tracks

---

## Phase 4: Treat (13:00-15:00)

| Idea | Next Step | By When | Who |
|------|-----------|---------|-----|
| | | | |
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

print("validate_session.py")

# Complete random entry session passes all checks
r = run(COMPLETE_RANDOM_ENTRY)
assert_eq("complete random entry is valid", True, r["valid"])
assert_eq("all checks pass", True, all(r["checks"].values()))
assert_eq("format detected", "Random Entry (15 min)", r["format"])
assert_eq("idea count >= 5", True, r["idea_count"] >= 5)

# Empty scaffold fails all content checks
r = run(EMPTY_SCAFFOLD)
assert_eq("empty scaffold is invalid", False, r["valid"])
assert_eq("focus not defined", False, r["checks"]["focus_defined"])
assert_eq("no ideas generated", False, r["checks"]["ideas_generated"])
assert_eq("no harvest tags", False, r["checks"]["harvest_tagged"])
assert_eq("no treat rows", False, r["checks"]["treat_actionable"])

# Complete six hats session passes
r = run(COMPLETE_SIX_HATS)
assert_eq("complete six hats is valid", True, r["valid"])
assert_eq("six hats format detected", "Six Thinking Hats (20 min)", r["format"])

# Partial session — has focus and ideas but missing harvest/treat
r = run(PARTIAL_SESSION)
assert_eq("partial session is invalid", False, r["valid"])
assert_eq("partial: focus defined", True, r["checks"]["focus_defined"])
assert_eq("partial: ideas generated", True, r["checks"]["ideas_generated"])
assert_eq("partial: harvest not tagged", False, r["checks"]["harvest_tagged"])
assert_eq("partial: treat not actionable", False, r["checks"]["treat_actionable"])
assert_eq("partial: missing list has 2 items", 2, len(r["missing"]))

# File not found
r = run.__wrapped__ if hasattr(run, "__wrapped__") else None
result = subprocess.run(
    [sys.executable, str(SCRIPT), "validate", "/nonexistent/file.md"],
    capture_output=True, text=True,
)
not_found = json.loads(result.stdout)
assert_eq("missing file returns invalid", False, not_found["valid"])
assert_eq("missing file has error", True, "error" in not_found)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print()
print("─────────────────────────")
print(f"Passed: {PASS}  Failed: {FAIL}")

if FAIL > 0:
    sys.exit(1)
