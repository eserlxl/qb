"""sync.sh --check must reject a shared/ file that is not wired into the MAP.

shared/ is the single source of truth materialized into every platform. The MAP
is hand-maintained, so a newly added shared file can be forgotten and would then
silently never sync. These tests pin the completeness guard that makes --check
fail loudly on such an unmapped file (while still passing on a complete tree).
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.qb_monorepo import REPO_ROOT, SHARED_DIR

SYNC_SCRIPT = REPO_ROOT / "scripts/sync.sh"
ENGINE_DEST_PREFIXES = (
    "platforms/claude-code/",
    "platforms/cursor/",
    "platforms/codex/",
)


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(repo / "scripts/sync.sh"), *args],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )


class SyncMapCompletenessTests(unittest.TestCase):
    def setUp(self) -> None:
        if not SYNC_SCRIPT.exists() or not SHARED_DIR.exists():
            self.skipTest("sync.sh or shared/ not present")
        self._tmp = TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy2(SYNC_SCRIPT, self.repo / "scripts/sync.sh")
        shutil.copytree(SHARED_DIR, self.repo / "shared")
        # Materialize every mapped destination so the drift loop passes and the
        # completeness guard (which runs after it) is what the assertions reach.
        primed = _run(self.repo)
        self.assertEqual(primed.returncode, 0, primed.stdout + primed.stderr)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_fully_mapped_shared_tree_passes_check(self) -> None:
        check = _run(self.repo, "--check")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("in sync", check.stdout)

    def test_each_shared_source_fans_out_to_every_engine_host(self) -> None:
        by_source: dict[str, list[str]] = {}
        for raw in (self.repo / "scripts/sync.sh").read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not (line.startswith('"') and line.endswith('"') and "|" in line):
                continue
            source, destination = line.strip('"').split("|", 1)
            by_source.setdefault(source, []).append(destination)

        self.assertTrue(by_source, "sync MAP parser found no entries")
        shared_root = self.repo / "shared"
        shared_sources = {
            str(path.relative_to(shared_root))
            for path in shared_root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        self.assertEqual(set(by_source), shared_sources)
        categories = {
            "planner": {s for s in shared_sources if s.startswith("planners/")},
            "reference": {s for s in shared_sources if s.startswith("references/")},
            "validator": {
                "scripts/validate_planner_docs.py",
                "scripts/validate_planwright_plan.py",
            },
            "engine": {
                s for s in shared_sources
                if s.startswith("scripts/")
                and s not in {
                    "scripts/validate_planner_docs.py",
                    "scripts/validate_planwright_plan.py",
                }
            },
        }
        for label, sources in categories.items():
            self.assertTrue(sources, f"no {label} shared sources detected")
            self.assertTrue(sources <= set(by_source), f"{label} sources missing from MAP")

        all_destinations = [dst for destinations in by_source.values() for dst in destinations]
        self.assertFalse(
            any(dst.startswith("platforms/antigravity/") for dst in all_destinations),
            "Antigravity is planning-only and must not be a sync destination",
        )
        for source, destinations in sorted(by_source.items()):
            with self.subTest(source=source):
                self.assertEqual(len(destinations), len(ENGINE_DEST_PREFIXES))
                for prefix in ENGINE_DEST_PREFIXES:
                    matches = [dst for dst in destinations if dst.startswith(prefix)]
                    self.assertEqual(
                        len(matches), 1,
                        f"{source} does not have exactly one {prefix} destination",
                    )

    def test_unmapped_shared_file_is_detected(self) -> None:
        (self.repo / "shared/planners/extra-planner.md").write_text(
            "# Extra planner not wired into the sync MAP\n", encoding="utf-8"
        )
        check = _run(self.repo, "--check")
        self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
        self.assertIn("unmapped_shared_source=planners/extra-planner.md", check.stderr)
        # The fail-loud contract also includes an actionable remediation line so a
        # contributor who adds an unmapped shared/ file knows how to fix it.
        self.assertIn("Add a MAP entry in scripts/sync.sh", check.stderr)

    def test_pycache_under_shared_is_ignored(self) -> None:
        cache = self.repo / "shared/scripts/__pycache__"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "validate_planner_docs.cpython-312.pyc").write_text("x", encoding="utf-8")
        check = _run(self.repo, "--check")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)


if __name__ == "__main__":
    unittest.main()
