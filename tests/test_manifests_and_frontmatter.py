"""Manifest-id and frontmatter-name invariants across all three platforms."""

from __future__ import annotations

import json
import re
import unittest

from tests.qb_monorepo import (
    ALL_PLATFORMS,
    CLAUDE_CODE,
    CODEX,
    CURSOR,
    frontmatter_name,
    load_manifest,
)


class ManifestIdTests(unittest.TestCase):
    """Each platform manifest parses and its ``name`` equals the platform id."""

    def test_each_manifest_parses_and_name_matches_id(self) -> None:
        for platform in ALL_PLATFORMS:
            with self.subTest(platform=platform["id"]):
                if not platform["manifest"].exists():
                    self.skipTest(f"platform not built yet: {platform['manifest']}")
                # Parses as JSON (raises a clear failure otherwise).
                try:
                    data = load_manifest(platform)
                except json.JSONDecodeError as exc:  # pragma: no cover - explicit message
                    self.fail(f"manifest is not valid JSON: {platform['manifest']}: {exc}")
                self.assertEqual(
                    data.get("name"),
                    platform["id"],
                    f"manifest name {data.get('name')!r} != expected id {platform['id']!r} "
                    f"in {platform['manifest']}",
                )

    def test_each_manifest_declares_semver_version_and_mit_license(self) -> None:
        semver = re.compile(r"^\d+\.\d+\.\d+$")
        for platform in ALL_PLATFORMS:
            with self.subTest(platform=platform["id"]):
                if not platform["manifest"].exists():
                    self.skipTest(f"platform not built yet: {platform['manifest']}")
                data = load_manifest(platform)
                version = data.get("version")
                self.assertIsInstance(
                    version, str, f"missing version in {platform['manifest']}"
                )
                self.assertRegex(
                    version,
                    semver,
                    f"version {version!r} is not semver in {platform['manifest']}",
                )
                self.assertEqual(
                    data.get("license"),
                    "MIT",
                    f"license != MIT in {platform['manifest']}",
                )

    def test_codex_manifest_is_read_from_the_nested_codex_plugin_dir(self) -> None:
        # The Codex package nests its manifest under plugins/qb/.codex-plugin/.
        expected = CODEX["root"] / "plugins/qb/.codex-plugin/plugin.json"
        self.assertEqual(CODEX["manifest"], expected)


class FrontmatterNameTests(unittest.TestCase):
    """skill name == dir; command/agent name == filename stem, on every platform."""

    def _check_skill_dirs(self, skills_root) -> list[str]:
        problems: list[str] = []
        for skill in skills_root.rglob("SKILL.md"):
            name = frontmatter_name(skill.read_text(encoding="utf-8"))
            if name != skill.parent.name:
                problems.append(f"skill_name_mismatch={skill}::name={name}::dir={skill.parent.name}")
        return problems

    def _check_md_stems(self, directory) -> list[str]:
        problems: list[str] = []
        if not directory.exists():
            return problems
        for path in sorted(directory.glob("*.md")):
            name = frontmatter_name(path.read_text(encoding="utf-8"))
            if name != path.stem:
                problems.append(f"name_mismatch={path}::name={name}::stem={path.stem}")
        return problems

    def test_claude_code_frontmatter_names(self) -> None:
        root = CLAUDE_CODE["root"]
        if not CLAUDE_CODE["manifest"].exists():
            self.skipTest("claude-code not built yet")
        problems = self._check_skill_dirs(root / "skills")
        problems += self._check_md_stems(root / "commands")
        problems += self._check_md_stems(root / "agents")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_cursor_frontmatter_names(self) -> None:
        root = CURSOR["root"]
        if not CURSOR["manifest"].exists():
            self.skipTest("cursor not built yet")
        problems = self._check_skill_dirs(root / "skills")
        problems += self._check_md_stems(root / "commands")
        problems += self._check_md_stems(root / "agents")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_codex_frontmatter_names(self) -> None:
        # Codex nests its single skill under plugins/qb/skills/qb/.
        root = CODEX["root"] / "plugins/qb"
        if not CODEX["manifest"].exists():
            self.skipTest("codex not built yet")
        problems = self._check_skill_dirs(root / "skills")
        problems += self._check_md_stems(root / "commands")
        # Codex agents use agents/openai.yaml (no frontmatter `name:` stem
        # convention), so it is intentionally not stem-checked here.
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
