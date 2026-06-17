"""Phase 8.4 -- release-integrity invariant (standard library only).

Pins the supply-chain integrity contract of the sanitized export (the git-tracked
tree `git archive` ships): platform copies are byte-equal to the synced shared/ core
(sync.sh --check semantics), the tree carries the expected root VERSION, and the
gitignored working trees (.qb/, QB-Audit/, .planwright/) are excluded.
"""

from __future__ import annotations

import subprocess
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

    def test_export_excludes_tool_state_trees(self):
        # The sanitized export = git-tracked files; the gitignored working trees must
        # never appear, so a release never ships .qb/, QB-Audit/, or .planwright/.
        tracked = self._tracked()
        for excluded in (".qb/", "QB-Audit/", ".planwright/"):
            offenders = [p for p in tracked if p.startswith(excluded)]
            self.assertEqual(offenders, [],
                             f"sanitized export must exclude {excluded}: {offenders}")


if __name__ == "__main__":
    unittest.main()
