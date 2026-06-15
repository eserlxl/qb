"""Phase 7.3 -- least-privilege + supply-chain safety.

Pins: default-deny writes (only allowlisted globs, traversal refused, empty
allowlist denies all), offline-default network with explicit opt-in, the
never-auto-run-repo-scripts rule, and a real dependency-free-core assertion that
every shared engine module imports only the standard library.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/least_privilege.py"
SHARED_SCRIPTS = SHARED_DIR / "scripts"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class LeastPrivilegeTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.exists():
            self.skipTest("least_privilege missing")
        self.lp = _load("qb_least_privilege_under_test", MODULE_PATH)

    def test_writes_default_deny(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            self.assertFalse(self.lp.write_allowed(repo, "src/x.py", []))            # empty => deny
            self.assertTrue(self.lp.write_allowed(repo, "src/x.py", ["src/*"]))       # allowlisted
            self.assertFalse(self.lp.write_allowed(repo, "etc/x.py", ["src/*"]))      # outside glob
            self.assertFalse(self.lp.write_allowed(repo, "../escape.py", ["**"]))     # traversal refused

    def test_assert_write_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(self.lp.PrivilegeError):
                self.lp.assert_write(Path(d), "secret.txt", ["src/*"])

    def test_network_offline_default_with_opt_in(self) -> None:
        self.assertTrue(self.lp.network_allowed(analyzer_is_offline=True, allow_networked=False))
        self.assertFalse(self.lp.network_allowed(analyzer_is_offline=False, allow_networked=False))
        self.assertTrue(self.lp.network_allowed(analyzer_is_offline=False, allow_networked=True))

    def test_no_auto_run_repo_scripts(self) -> None:
        self.assertFalse(self.lp.AUTO_RUN_REPO_SCRIPTS)
        self.assertFalse(self.lp.may_run_repo_script())
        self.assertTrue(self.lp.may_run_repo_script(sandboxed_authorization=True))

    def test_engine_core_is_dependency_free(self) -> None:
        violations = self.lp.assert_dependency_free_core(SHARED_SCRIPTS)
        self.assertEqual(violations, [], f"non-stdlib imports in engine core: {violations}")


if __name__ == "__main__":
    unittest.main()
