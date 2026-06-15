"""Phase 6.4 -- manifest version consistency + structural invariants.

Resolves ASSESS-P2-01. The root VERSION file is the single source of version
truth; all three plugin manifests must equal it, so version drift fails make check
(the prior semver-only check missed this). The structural-invariant test pins the
deliberately-accepted per-host shapes -- including the codex nested
plugins/qb/skills/qb/ layout with capitalized reference filenames and an
agents/openai.yaml -- so an unsanctioned layout/filename change fails CI.

Codex structural-asymmetry decision (F6.4-03): ACCEPTED, not normalized. Codex's
plugin packaging requires the nested plugins/qb/ layout and capitalized
reference filenames; normalizing would risk breaking Codex discovery. The shape is
therefore pinned as an invariant rather than flattened.
"""

from __future__ import annotations

import unittest

from tests.qb_monorepo import ALL_PLATFORMS, CLAUDE_CODE, CODEX, CURSOR, REPO_ROOT, load_manifest

VERSION_FILE = REPO_ROOT / "VERSION"


class VersionConsistencyTests(unittest.TestCase):
    def test_version_file_exists_and_is_semver(self) -> None:
        self.assertTrue(VERSION_FILE.is_file(), "root VERSION file (single source of truth) missing")
        import re
        self.assertRegex(VERSION_FILE.read_text(encoding="utf-8").strip(), r"^\d+\.\d+\.\d+$")

    def test_all_manifests_match_the_version_file(self) -> None:
        declared = VERSION_FILE.read_text(encoding="utf-8").strip()
        for platform in ALL_PLATFORMS:
            if not platform["manifest"].exists():
                self.skipTest(f"platform not built: {platform['id']}")
            with self.subTest(platform=platform["manifest"]):
                self.assertEqual(load_manifest(platform)["version"], declared,
                                 f"{platform['manifest']} version != VERSION ({declared})")

    def test_manifest_versions_do_not_diverge(self) -> None:
        versions = {load_manifest(p)["version"] for p in ALL_PLATFORMS if p["manifest"].exists()}
        self.assertEqual(len(versions), 1, f"plugin manifest versions diverge: {sorted(versions)}")


class StructuralInvariantTests(unittest.TestCase):
    """Pin the load-bearing per-host shape (accepted, not exhaustive)."""

    def _require(self, root, relpaths):
        for rel in relpaths:
            self.assertTrue((root / rel).exists(), f"missing structural path: {root / rel}")

    def test_claude_code_flat_shape(self) -> None:
        if not CLAUDE_CODE["manifest"].exists():
            self.skipTest("claude-code not built")
        self._require(CLAUDE_CODE["root"], [
            ".claude-plugin/plugin.json", "skills/qb-planner/SKILL.md",
            "commands", "agents", "scripts/validate_planner_docs.py",
        ])

    def test_cursor_flat_shape(self) -> None:
        if not CURSOR["manifest"].exists():
            self.skipTest("cursor not built")
        self._require(CURSOR["root"], [
            ".cursor-plugin/plugin.json", "skills/qb-planner/SKILL.md", "commands",
        ])

    def test_codex_accepted_nested_shape(self) -> None:
        if not CODEX["manifest"].exists():
            self.skipTest("codex not built")
        # Accepted asymmetry: nested plugins/qb/ + capitalized references + openai.yaml.
        self._require(CODEX["root"], [
            "plugins/qb/.codex-plugin/plugin.json",
            "plugins/qb/skills/qb/references/First-Planner.md",
            "plugins/qb/skills/qb/scripts/validate_planner_docs.py",
        ])
        self.assertTrue(any(CODEX["root"].rglob("openai.yaml")),
                        "codex agents/openai.yaml expected (accepted shape)")


if __name__ == "__main__":
    unittest.main()
