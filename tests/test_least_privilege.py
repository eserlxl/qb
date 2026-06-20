"""Phase 7.3 -- least-privilege + supply-chain safety.

Pins: default-deny writes (only allowlisted globs, traversal refused, empty
allowlist denies all), offline-default network with explicit opt-in, the
never-auto-run-repo-scripts rule, and a real dependency-free-core assertion that
every shared engine module imports only the standard library.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import types
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


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _init_repo(repo: Path) -> None:
    subprocess.run(
        ["git", "init", "-q", str(repo)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "QB Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "file.txt").write_text("old\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")


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

    def test_repo_script_authorized_requires_establishable_confinement(self) -> None:
        # A repo-supplied command is authorized only when the required confinement
        # control is establishable on this host; dropping it denies (fail-closed),
        # and AUTO_RUN_REPO_SCRIPTS stays False so nothing auto-runs unsandboxed.
        self.assertFalse(self.lp.AUTO_RUN_REPO_SCRIPTS)
        cs = self.lp._cs
        original = cs.available_confinement_controls
        try:
            cs.available_confinement_controls = lambda: ()
            self.assertFalse(self.lp.repo_script_authorized())       # no control -> denied
            cs.available_confinement_controls = lambda: ("process_group",)
            self.assertTrue(self.lp.repo_script_authorized())        # control present -> authorized
        finally:
            cs.available_confinement_controls = original

        if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
            self.skipTest("git unavailable")
        orch = _load(
            "qb_orchestrator_for_least_privilege_test",
            SHARED_SCRIPTS / "orchestrator.py",
        )
        original_auth = orch._lp.repo_script_authorized
        original_controls = orch._cs.available_confinement_controls
        original_permitted = orch._release.permitted_autonomy
        orch._lp.repo_script_authorized = lambda: False
        orch._cs.available_confinement_controls = lambda: ("process_group",)
        orch._release.permitted_autonomy = lambda _telemetry: orch.A2
        try:
            policy = orch._policy.Policy(
                autonomy_level=orch.A2,
                auto_fixable_categories=frozenset({"quality"}),
                default_min_confidence="low",
                write_allowlist=("**",),
            )
            finding = types.SimpleNamespace(
                id="QBF-REPO-SCRIPT",
                category="quality",
                severity="P2",
                confidence="high",
                evidence="file.txt:1",
            )
            plan = types.SimpleNamespace(
                finding=finding,
                verify_command=[sys.executable, "-c", ""],
            )
            applied = {"called": False}
            with tempfile.TemporaryDirectory() as d:
                repo = Path(d)
                _init_repo(repo)
                result = orch.run_finding(
                    policy,
                    repo,
                    plan,
                    lambda _iso: applied.__setitem__("called", True),
                )
            self.assertEqual(result["outcome"], "blocked")
            self.assertEqual(
                result["reason"],
                "repo-script-unauthorized: sandbox unavailable",
            )
            self.assertFalse(
                applied["called"],
                "unauthorized repo script must block before apply",
            )
        finally:
            orch._lp.repo_script_authorized = original_auth
            orch._cs.available_confinement_controls = original_controls
            orch._release.permitted_autonomy = original_permitted

    def test_write_allowed_honors_policy_declared_allowlist(self) -> None:
        # The enforced write_allowed and the declared policy.write_allowlist must
        # not diverge: feed the policy's own allowlist into write_allowed so a
        # glob-format mismatch between declaration (policy.py) and enforcement
        # (least_privilege.py) is caught. The default (A0) policy declares an empty
        # allowlist -> deny-all; a parsed policy's globs are honored verbatim.
        # (Missing/malformed -> deny-all is covered by test_policy_engine's
        # test_load_missing_or_malformed_fails_closed_to_default.)
        policy = _load("qb_policy_for_least_privilege_test", SHARED_SCRIPTS / "policy.py")
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            default_allowlist = policy.default_policy().write_allowlist
            self.assertEqual(default_allowlist, (), "A0 default declares deny-all")
            self.assertFalse(
                self.lp.write_allowed(repo, "src/x.py", default_allowlist),
                "the declared deny-all allowlist must deny every write through write_allowed",
            )
            declared = policy.parse_policy({
                "autonomy_level": "A2",
                "auto_fixable_categories": ["quality"],
                "default_min_confidence": "low",
                "write_allowlist": ["src/*"],
            }).write_allowlist
            self.assertTrue(
                self.lp.write_allowed(repo, "src/x.py", declared),
                "a path matching the declared policy allowlist must be permitted",
            )
            self.assertFalse(
                self.lp.write_allowed(repo, "etc/x.py", declared),
                "a path outside the declared policy allowlist must be denied",
            )

    def test_engine_core_is_dependency_free(self) -> None:
        violations = self.lp.assert_dependency_free_core(SHARED_SCRIPTS)
        self.assertEqual(violations, [], f"non-stdlib imports in engine core: {violations}")

    def test_unparseable_module_is_reported_as_violation(self) -> None:
        # Fail-closed: a module that cannot be parsed cannot be proven
        # dependency-free, so it must be reported as a violation (not skipped).
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "broken.py").write_text("def f(:\n", encoding="utf-8")
            violations = self.lp.assert_dependency_free_core(Path(d))
            self.assertEqual(
                violations, [("broken.py", "<unanalyzable>")],
                "an unparseable engine module must be a supply-chain violation",
            )


if __name__ == "__main__":
    unittest.main()
