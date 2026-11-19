#!/usr/bin/env python3
"""Coherence tests for native manifests, shared resources and host adapters.

The skill resolves its own installation; each manifest registers the native
host's Python hook adapter and root-level specialist definitions remain intact.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
CODEX_MANIFEST = REPO_ROOT / ".codex-plugin" / "plugin.json"
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
HOOKS_CONFIG = REPO_ROOT / "hooks" / "claude-hooks.json"
SKILL_DIR = REPO_ROOT / "skills" / "sage"
AGENTS_DIR = REPO_ROOT / "agents"

CLERKS = [
    "artifact-clerk",
    "assessment-agent",
    "verification-gate",
    "reference-clerk",
    "demo-generator",
    "capstone-architect",
]


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class TestSkillPaths(unittest.TestCase):
    def test_claude_skill_paths_resolve_and_hold_a_skill(self):
        for rel in load(CLAUDE_MANIFEST)["skills"]:
            resolved = (REPO_ROOT / rel).resolve()
            self.assertTrue(resolved.is_dir(), f"{rel} is not a directory")
            self.assertTrue(
                (resolved / "SKILL.md").is_file(), f"{rel} has no SKILL.md"
            )

    def test_codex_skills_field_is_a_container_of_skill_dirs(self):
        # Codex takes a single path string pointing at a directory of skill
        # subdirectories — not at a skill itself.
        rel = load(CODEX_MANIFEST)["skills"]
        self.assertIsInstance(rel, str, "Codex 'skills' must be a single path string")
        container = (REPO_ROOT / rel).resolve()
        self.assertTrue(container.is_dir())

        found = [d for d in container.iterdir() if (d / "SKILL.md").is_file()]
        self.assertTrue(found, f"{rel} contains no skill directories")

    def test_resource_resolver_and_native_specialists_ship_together(self):
        self.assertTrue((REPO_ROOT / "tools/plugin_root.py").is_file())
        for name in CLERKS:
            self.assertTrue((AGENTS_DIR / (name + ".md")).is_file())
        self.assertIn("native host configuration", (SKILL_DIR / "references/ref-subagents.md").read_text())

    def test_both_manifests_ship_the_same_skills(self):
        claude = {
            (REPO_ROOT / rel).resolve() for rel in load(CLAUDE_MANIFEST)["skills"]
        }
        container = (REPO_ROOT / load(CODEX_MANIFEST)["skills"]).resolve()
        codex = {d.resolve() for d in container.iterdir() if (d / "SKILL.md").is_file()}
        self.assertEqual(claude, codex)


class TestHooks(unittest.TestCase):
    def test_each_manifest_selects_its_host_adapter(self):
        for manifest, stem in [(CLAUDE_MANIFEST, "claude"), (CODEX_MANIFEST, "codex")]:
            self.assertEqual(load(manifest)["hooks"], "./hooks/" + stem + "-hooks.json")
            hooks = load(REPO_ROOT / load(manifest)["hooks"])["hooks"]
            self.assertEqual(set(hooks), {"SessionStart", "SessionEnd", "SubagentStart", "SubagentStop", "Stop"})
            for groups in hooks.values():
                for group in groups:
                    for hook in group["hooks"]:
                        self.assertIn("tools/host_hooks.py", hook["command"])
                        self.assertIn("--host " + ("claude-code" if stem == "claude" else "codex"), hook["command"])
                        self.assertNotIn("/tmp/", hook["command"])
                        self.assertNotIn("bash ", hook["command"])
        self.assertTrue((REPO_ROOT / "tools/host_hooks.py").is_file())



class TestVersionMirror(unittest.TestCase):
    def test_all_three_manifests_agree_on_version(self):
        version = load(CLAUDE_MANIFEST)["version"]
        self.assertEqual(load(CODEX_MANIFEST)["version"], version)
        self.assertEqual(load(MARKETPLACE)["plugins"][0]["version"], version)
        self.assertEqual(load(REPO_ROOT / 'package.json')['version'], version)


class TestInvocationPolicy(unittest.TestCase):
    def test_user_invoked_is_declared_in_both_harnesses(self):
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("disable-model-invocation: true", skill)

        openai = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("allow_implicit_invocation: false", openai)


class TestHostNeutralProse(unittest.TestCase):
    """The prompt layer must not name any one Host's API."""

    def _prose_files(self):
        return list(SKILL_DIR.rglob("*.md")) + list(AGENTS_DIR.glob("*.md"))

    def test_no_task_tool_vocabulary(self):
        for path in self._prose_files():
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("subagent_type", text, f"{path.name} names subagent_type")
            self.assertNotIn("Task tool", text, f"{path.name} names the Task tool")

    def test_every_clerk_spec_exists(self):
        for clerk in CLERKS:
            self.assertTrue((AGENTS_DIR / f"{clerk}.md").is_file())

    def test_delegation_pointers_name_a_real_spec(self):
        pattern = re.compile(r"\$SAGE_ROOT/agents/([\w-]+)\.md")
        seen = set()
        for path in self._prose_files():
            for name in pattern.findall(path.read_text(encoding="utf-8")):
                seen.add(name)
                self.assertIn(name, CLERKS, f"{path.name} points at unknown Clerk {name}")
        self.assertTrue(seen, "no delegation spec pointers found in the prompt layer")

    def test_bootstrap_line_prefers_an_exported_root(self):
        # Installed protocols must not consume a shared temporary root slot.
        for path in self._prose_files():
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "SAGE_ROOT=$(cat /tmp/.sage-plugin-root)",
                text,
                f"{path.name} uses the bare bootstrap form",
            )


class TestRouterMessagesAreHostNeutral(unittest.TestCase):
    """unknown_verb is the primary way the grammar is taught on a Host with no
    slash commands, so its messages must not name one. See docs/adr/0008."""

    def _messages(self):
        import session_router  # noqa: E402 — path wired by conftest

        return [
            session_router._unknown_verb("react", "hooks", "/sage-root")["message"],
            session_router._unknown_verb("continue", "", "/sage-root")["message"],
            session_router.route("/sage-root", "")["message"],
        ]

    def test_grammar_messages_carry_no_slash_command(self):
        for message in self._messages():
            self.assertNotIn("/sage", message, f"host syntax leaked into: {message}")

    def test_grammar_messages_still_name_both_verbs(self):
        joined = " ".join(self._messages())
        self.assertIn("learn", joined)
        self.assertIn("archive", joined)


if __name__ == "__main__":
    unittest.main()
