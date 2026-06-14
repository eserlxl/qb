"""Preserved artifact filenames in the shared source, plus a sync-clean gate."""

from __future__ import annotations

import subprocess
import unittest

from tests.qb_monorepo import PLATFORMS_DIR, REPO_ROOT, SHARED_DIR

VALIDATOR = SHARED_DIR / "scripts/validate_planner_docs.py"
SYNC_SCRIPT = REPO_ROOT / "scripts/sync.sh"

# Exact artifact identifiers the workflow + validator depend on (the "Planing"
# spelling is intentional and must be preserved verbatim).
PRESERVED_LITERALS = (
    "Main-Planing.md",
    "Autopsy.md",
    "Sub-Planing-Index.md",
    "Sub-Planing-Audit.md",
)

# Audit-status vocabulary the Step-4 gate depends on.
AUDIT_VOCABULARY = (
    "PASS",
    "PASS_WITH_WARNINGS",
    "BLOCKED",
)


class SharedValidatorArtifactTests(unittest.TestCase):
    """The shared validator references every preserved artifact name + Faz pattern."""

    def setUp(self) -> None:
        if not VALIDATOR.exists():
            self.skipTest(f"shared validator missing: {VALIDATOR}")
        self.text = VALIDATOR.read_text(encoding="utf-8")

    def test_preserved_artifact_filenames_appear_in_validator(self) -> None:
        missing = [name for name in PRESERVED_LITERALS if name not in self.text]
        self.assertEqual(missing, [], f"missing artifact names in validator: {missing}")

    def test_faz_folder_and_subplan_patterns_appear_in_validator(self) -> None:
        # The folder + sub-plan regex literals (intentional "Faz" spelling).
        self.assertIn("Faz-", self.text, "Faz-<n>-Plans folder pattern missing from validator")
        self.assertIn("Faz", self.text, "Faz sub-plan pattern missing from validator")
        # Sub-plan numbering uses Faz<n>.<m>; assert the dotted form is present.
        self.assertIn(r"Faz(\d+)\.(\d+)", self.text, "Faz<n>.<m> sub-plan regex missing")

    def test_audit_vocabulary_appears_in_validator(self) -> None:
        missing = [word for word in AUDIT_VOCABULARY if word not in self.text]
        self.assertEqual(missing, [], f"missing audit vocabulary in validator: {missing}")


class SharedSpecArtifactTests(unittest.TestCase):
    """The preserved artifact names also appear across the shared planner specs."""

    def test_artifact_names_present_somewhere_in_shared_specs(self) -> None:
        planners_dir = SHARED_DIR / "planners"
        if not planners_dir.exists():
            self.skipTest(f"shared planners missing: {planners_dir}")
        corpus = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(planners_dir.glob("*.md"))
        )
        self.assertIn("Planner-docs", corpus, "shared planner specs never mention Planner-docs/")
        self.assertIn("Main-Planing.md", corpus, "shared planner specs never mention Main-Planing.md")


class SyncCleanTests(unittest.TestCase):
    """`scripts/sync.sh --check` must exit 0: every platform copy matches shared/."""

    def test_sync_check_passes(self) -> None:
        if not SYNC_SCRIPT.exists():
            self.skipTest(f"sync.sh missing: {SYNC_SCRIPT}")
        # If a platform package has not been materialized yet (parallel build),
        # the byte-for-byte copies cannot exist, so skip rather than report a
        # false drift. Once all platforms are present this assertion is strict.
        platform_dirs = [
            PLATFORMS_DIR / "claude-code",
            PLATFORMS_DIR / "cursor",
            PLATFORMS_DIR / "codex",
        ]
        if not all(d.is_dir() and any(d.iterdir()) for d in platform_dirs):
            self.skipTest("not all platform packages are built yet")

        result = subprocess.run(
            ["bash", str(SYNC_SCRIPT), "--check"],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"sync.sh --check reported drift:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
