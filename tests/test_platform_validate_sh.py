"""Failure-path coverage for every platform's validate.sh CI gate.

The per-platform validate.sh scripts are otherwise only run against the healthy
repo, so their rejection branches are unverified. For each platform this copies
the package into a temp dir and confirms validate.sh actually fails on a missing
required file and on a mis-named manifest, not just that it passes when clean.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.qb_monorepo import ANTIGRAVITY, CLAUDE_CODE, CODEX, CURSOR


def _run(tmp_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(tmp_root / "scripts/validate.sh")],
        text=True,
        capture_output=True,
        check=False,
    )


class _ValidateShFailureBase:
    """Rejection-branch checks parameterized by a tests.qb_monorepo descriptor.

    Concrete subclasses set ``PLATFORM`` and also inherit ``unittest.TestCase``
    so the shared ``test_*`` methods run once per platform. This mixin is not a
    TestCase itself, so it is never collected on its own.
    """

    PLATFORM: dict

    def setUp(self) -> None:
        src_root = self.PLATFORM["root"]
        if not (src_root / "scripts/validate.sh").exists():
            self.skipTest(f"{self.PLATFORM['id']} platform not built yet")
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name) / src_root.name
        shutil.copytree(src_root, self.root)
        # Manifest path inside the copy; host layouts differ, so derive it from
        # the descriptor rather than hard-coding a per-platform path here.
        self.manifest = self.root / self.PLATFORM["manifest"].relative_to(src_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_clean_copy_passes(self) -> None:
        result = _run(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_required_file_fails(self) -> None:
        (self.root / "README.md").unlink()
        result = _run(self.root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("missing_required_file", result.stdout + result.stderr)

    def test_wrong_manifest_name_fails(self) -> None:
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        data["name"] = f"not-{self.PLATFORM['id']}"
        self.manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")
        result = _run(self.root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("unexpected_plugin_name", result.stdout + result.stderr)


class ClaudeCodeValidateShFailureTests(_ValidateShFailureBase, unittest.TestCase):
    PLATFORM = CLAUDE_CODE


class CursorValidateShFailureTests(_ValidateShFailureBase, unittest.TestCase):
    PLATFORM = CURSOR


class CodexValidateShFailureTests(_ValidateShFailureBase, unittest.TestCase):
    PLATFORM = CODEX

    def test_planted_secret_fails(self) -> None:
        # Codex-only: its validate.sh is the repo's CI-time tracked-file secret
        # scanner. Build the token by concatenation so this source carries no
        # literal credential (and never trips a secret scan itself).
        fake_secret = "ghp_" + "A" * 32  # matches the github_legacy_pat pattern
        leak = self.root / "docs/USAGE.md"  # exists, passes checks 1-7
        leak.write_text(
            leak.read_text(encoding="utf-8") + f"\n{fake_secret}\n",
            encoding="utf-8",
        )
        result = _run(self.root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("tracked_secret_hygiene_failed", result.stdout + result.stderr)


class AntigravityValidateShFailureTests(unittest.TestCase):
    """Antigravity is manifest-less, so it gets a dedicated rejection-branch suite:
    a clean copy passes, a missing required file fails, and a wrong SKILL.md
    frontmatter identity (its name check, in place of a JSON manifest-name check)
    fails.
    """

    def setUp(self) -> None:
        src_root = ANTIGRAVITY["root"]
        if not (src_root / "scripts/validate.sh").exists():
            self.skipTest("antigravity platform not built yet")
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name) / src_root.name
        shutil.copytree(src_root, self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_clean_copy_passes(self) -> None:
        result = _run(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_required_file_fails(self) -> None:
        (self.root / "README.md").unlink()
        result = _run(self.root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("missing_required_file", result.stdout + result.stderr)

    def test_wrong_skill_name_fails(self) -> None:
        skill = self.root / "skills/qb/SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace("name: qb", "name: not-qb", 1),
            encoding="utf-8",
        )
        result = _run(self.root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        # validate.sh's required-frontmatter check enforces the verbatim `name: qb`
        # line, so a wrong identity is rejected with this specific token (assert it
        # precisely rather than a vacuous substring that any frontmatter edit trips).
        self.assertIn("skill_frontmatter_missing_keys", result.stdout + result.stderr)


class AntigravityInstallVersionTests(unittest.TestCase):
    """install.sh derives the generated plugin.json version from SKILL.md frontmatter
    (single source of version truth). Pin that the app-global install -- the only
    path that emits a manifest -- produces name==qb, license==MIT, and
    version==VERSION, so a sed/frontmatter regression cannot silently ship a
    0.0.0 / wrong-version manifest while make check stays green.
    """

    def setUp(self) -> None:
        self.install = ANTIGRAVITY["root"] / "scripts/install.sh"
        if not self.install.exists():
            self.skipTest("antigravity platform not built yet")

    def test_app_global_plugin_json_version_matches_version_file(self) -> None:
        from tests.qb_monorepo import REPO_ROOT

        declared = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        with TemporaryDirectory() as home:
            result = subprocess.run(
                ["bash", str(self.install), "--scope", "app-global", "--force"],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "HOME": home},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plugin_root = Path(home) / ".gemini/config/plugins/qb"
            manifest = plugin_root / "plugin.json"
            self.assertTrue(manifest.exists(), f"plugin.json not generated: {result.stdout}")
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data.get("name"), "qb")
            self.assertEqual(data.get("license"), "MIT")
            self.assertEqual(
                data.get("version"),
                declared,
                f"generated plugin.json version {data.get('version')!r} != VERSION {declared!r}",
            )
            installed = json.loads(
                (plugin_root / "installed_version.json").read_text(encoding="utf-8")
            )
            self.assertEqual(installed.get("version"), declared)


def _required_files(validate_text: str) -> set:
    """Extract the required_files entries from a validate.sh (bash array or heredoc)."""
    array = re.search(r"required_files=\((.*?)\)", validate_text, re.DOTALL)
    if array:
        return set(re.findall(r'"([^"]+)"', array.group(1)))
    heredoc = re.search(r'required_files="\n(.*?)\n"', validate_text, re.DOTALL)
    if heredoc:
        return {ln.strip() for ln in heredoc.group(1).splitlines() if ln.strip()}
    return set()


def _shipped_components(root: Path) -> set:
    """Every shipped SKILL.md, command, and agent file, relative to the platform root."""
    comps = {p.relative_to(root).as_posix() for p in root.rglob("SKILL.md")
             if "__pycache__" not in p.parts}
    for sub in ("commands", "agents"):
        directory = root / sub
        if directory.is_dir():
            comps.update(p.relative_to(root).as_posix() for p in directory.glob("*.md"))
    return comps


class RequiredFilesCompletenessTests(unittest.TestCase):
    """Pin each validate.sh required_files list COMPLETE versus the shipped component
    set. Without this, a newly added skill/command/agent ships un-gated by the
    package CI -- the exact drift that left qb-runner, qb-harden, and qb_headless.py
    out of the required_files lists until they were caught by audit."""

    def _check(self, platform: dict) -> None:
        validate = platform["root"] / "scripts/validate.sh"
        if not validate.exists():
            self.skipTest(f"{platform['id']} platform not built yet")
        required = _required_files(validate.read_text(encoding="utf-8"))
        missing = sorted(c for c in _shipped_components(platform["root"]) if c not in required)
        self.assertEqual(
            missing, [],
            f"{platform['root'].name}: shipped components missing from validate.sh "
            f"required_files (deletion would pass CI undetected): {missing}",
        )

    def test_claude_code_required_files_are_complete(self) -> None:
        self._check(CLAUDE_CODE)

    def test_cursor_required_files_are_complete(self) -> None:
        self._check(CURSOR)

    def test_codex_required_files_are_complete(self) -> None:
        self._check(CODEX)

    def test_antigravity_required_files_are_complete(self) -> None:
        self._check(ANTIGRAVITY)


if __name__ == "__main__":
    unittest.main()
