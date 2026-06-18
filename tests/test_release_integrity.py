"""Phase 8.4 -- release-integrity invariant (standard library only).

Pins the supply-chain integrity contract of the sanitized export (the git-tracked
tree `git archive` ships): platform copies are byte-equal to the synced shared/ core
(sync.sh --check semantics), the tree carries the expected root VERSION, and the
gitignored working trees (.qb/, .planwright/) are excluded.
"""

from __future__ import annotations

import subprocess
import re
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests.qb_monorepo import REPO_ROOT

SYNC = REPO_ROOT / "scripts/sync.sh"
VERSION_FILE = REPO_ROOT / "VERSION"
MANIFEST = REPO_ROOT / "scripts/release-manifest.py"


def _git(*args):
    return subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True)


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
                 "git unavailable")
class ReleaseIntegrityTest(unittest.TestCase):
    def _tracked(self):
        return [p for p in _git("ls-files", "-z").stdout.split("\0") if p]

    def test_export_is_byte_equal_to_synced_shared_core(self):
        # sync.sh --check semantics: every platform copy byte-matches its shared/
        # source AND every shared file is mapped into the fan-out.
        if not SYNC.is_file():
            self.skipTest("sync.sh missing")
        result = subprocess.run(["bash", str(SYNC), "--check"],
                                cwd=str(REPO_ROOT), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         "sync.sh --check failed (export not byte-equal to shared/):\n"
                         f"{result.stdout}\n{result.stderr}")

    def test_export_carries_expected_version(self):
        self.assertIn("VERSION", self._tracked(),
                      "the export tree must ship the root VERSION file")
        declared = VERSION_FILE.read_text(encoding="utf-8").strip()
        self.assertRegex(declared, r"^\d+\.\d+\.\d+$")
        if MANIFEST.is_file():
            out = subprocess.run(["python3", str(MANIFEST), "--root", str(REPO_ROOT)],
                                 capture_output=True, text=True, check=True).stdout
            self.assertIn(f"version: {declared}", out,
                          "release manifest version must equal root VERSION")

    def test_release_manifest_is_deterministic_inventory_only(self):
        self.assertTrue(MANIFEST.is_file(), "release manifest script missing")
        first = subprocess.run(["python3", str(MANIFEST), "--root", str(REPO_ROOT)],
                               capture_output=True, text=True, check=True).stdout
        second = subprocess.run(["python3", str(MANIFEST), "--root", str(REPO_ROOT)],
                                capture_output=True, text=True, check=True).stdout
        self.assertEqual(first, second, "release manifest must be deterministic")

        lines = first.splitlines()
        self.assertEqual(lines[0], "# QB release manifest v1")
        self.assertRegex(lines[1], r"^version: \d+\.\d+\.\d+$")
        self.assertRegex(lines[2], r"^files: \d+$")
        self.assertTrue(lines[3:], "manifest must contain file hash entries")
        paths = [line.split("  ", 1)[1] for line in lines[3:]]
        self.assertEqual(paths, sorted(paths), "manifest entries must be sorted by path")
        self.assertTrue(
            all(re.match(r"^[0-9a-f]{64}  .+", line) for line in lines[3:]),
            "manifest entries must be SHA-256 inventory rows",
        )
        self.assertNotIn("signature", first.lower(),
                         "manifest is integrity inventory, not a signing artifact")

    def test_release_manifest_check_detects_stored_manifest_drift(self):
        self.assertTrue(MANIFEST.is_file(), "release manifest script missing")
        with TemporaryDirectory() as d:
            stored = Path(d) / "QB-sanitized.manifest"
            write = subprocess.run(
                ["python3", str(MANIFEST), "--root", str(REPO_ROOT), "--output", str(stored)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(write.returncode, 0, write.stderr)

            ok = subprocess.run(
                ["python3", str(MANIFEST), "--root", str(REPO_ROOT), "--check", "--output", str(stored)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(ok.returncode, 0, ok.stderr)

            stored.write_text(stored.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
            bad = subprocess.run(
                ["python3", str(MANIFEST), "--root", str(REPO_ROOT), "--check", "--output", str(stored)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(bad.returncode, 1, "drifted stored manifest must fail --check")
            self.assertIn("tree drifted", bad.stderr)

    def test_export_excludes_tool_state_trees(self):
        # The sanitized export = git-tracked files; the gitignored working trees must
        # never appear, so a release never ships .qb/ (which now holds the audit
        # run-store) or .planwright/.
        tracked = self._tracked()
        for excluded in (".qb/", ".planwright/"):
            offenders = [p for p in tracked if p.startswith(excluded)]
            self.assertEqual(offenders, [],
                             f"sanitized export must exclude {excluded}: {offenders}")


if __name__ == "__main__":
    unittest.main()
