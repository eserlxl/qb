"""Phase 4.1 -- policy schema + pure evaluation engine.

Pins: the fail-closed default (A0 / deny-all); strict closed-key parsing (unknown
key rejected); fail-closed load on missing/malformed files; and the deterministic
allow/deny verdicts + reason codes for every fix and remote-action path.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/policy.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PolicyEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.exists():
            self.skipTest(f"policy missing: {MODULE_PATH}")
        self.p = _load("qb_policy_under_test", MODULE_PATH)

    def _fix(self, **kw):
        kw.setdefault("action_kind", "fix")
        return self.p.ActionDescriptor(**kw)

    def _permissive(self):
        return self.p.parse_policy({
            "autonomy_level": "A2",
            "auto_fixable_categories": ["quality"],
            "default_min_confidence": "medium",
            "write_allowlist": ["*.txt"],
        })

    # --- defaults + parsing ----------------------------------------------
    def test_default_policy_is_a0_deny_all(self) -> None:
        d = self.p.default_policy()
        self.assertEqual(d.autonomy_level, "A0")
        self.assertEqual(d.auto_fixable_categories, frozenset())
        self.assertFalse(d.allow_commit or d.allow_push or d.allow_pr)
        self.assertEqual(d.write_allowlist, ())

    def test_unknown_key_is_rejected(self) -> None:
        with self.assertRaises(self.p.PolicyError):
            self.p.parse_policy({"autonmy_level": "A2"})  # typo'd key

    def test_invalid_values_rejected(self) -> None:
        with self.assertRaises(self.p.PolicyError):
            self.p.parse_policy({"autonomy_level": "A9"})
        with self.assertRaises(self.p.PolicyError):
            self.p.parse_policy({"auto_fixable_categories": ["not-a-category"]})

    def test_load_missing_or_malformed_fails_closed_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.p.load_policy(Path(d) / "nope.json").autonomy_level, "A0")
            bad = Path(d) / "bad.json"
            bad.write_text("{ not json", encoding="utf-8")
            self.assertEqual(self.p.load_policy(bad).autonomy_level, "A0")
            unknown = Path(d) / "unknown.json"
            unknown.write_text('{"surprise": true}', encoding="utf-8")
            self.assertEqual(self.p.load_policy(unknown).autonomy_level, "A0")  # fail-closed
            # A malformed-but-valid-JSON field whose coercion raises must also fail
            # closed (the "any problem" contract), not crash the loader.
            for body in ('{"schema_version": "abc"}', '{"schema_version": null}',
                         '{"write_allowlist": 5}'):
                coerce_bad = Path(d) / "coerce.json"
                coerce_bad.write_text(body, encoding="utf-8")
                self.assertEqual(
                    self.p.load_policy(coerce_bad).autonomy_level, "A0",
                    msg=f"load_policy must fail closed on {body}",
                )

    # --- evaluation ------------------------------------------------------
    def test_default_blocks_every_fix(self) -> None:
        v = self.p.evaluate(self.p.default_policy(),
                            self._fix(category="quality", confidence="high", target_path="a.txt"))
        self.assertFalse(v.allowed)
        self.assertEqual(v.reason, "autonomy-report-only")

    def test_permissive_allows_matching_fix(self) -> None:
        v = self.p.evaluate(self._permissive(),
                            self._fix(category="quality", confidence="high", target_path="style.txt"))
        self.assertTrue(v.allowed)
        self.assertEqual(v.reason, "allowed")

    def test_category_not_autofixable_denied(self) -> None:
        v = self.p.evaluate(self._permissive(),
                            self._fix(category="secret", confidence="high", target_path="style.txt"))
        self.assertEqual(v.reason, "category-not-auto-fixable")

    def test_confidence_below_threshold_denied(self) -> None:
        v = self.p.evaluate(self._permissive(),
                            self._fix(category="quality", confidence="low", target_path="style.txt"))
        self.assertEqual(v.reason, "confidence-below-threshold")

    def test_denylist_overrides_allowlist(self) -> None:
        policy = self.p.parse_policy({
            "autonomy_level": "A2", "auto_fixable_categories": ["quality"],
            "default_min_confidence": "low",
            "write_allowlist": ["*.txt"], "write_denylist": ["secrets.txt"],
        })
        v = self.p.evaluate(policy, self._fix(category="quality", confidence="low", target_path="secrets.txt"))
        self.assertEqual(v.reason, "path-in-denylist")

    def test_path_outside_allowlist_denied(self) -> None:
        v = self.p.evaluate(self._permissive(),
                            self._fix(category="quality", confidence="high", target_path="src/main.py"))
        self.assertEqual(v.reason, "path-outside-allowlist")

    def test_remote_actions_gated_by_flags(self) -> None:
        default = self.p.default_policy()
        for kind, reason in (("commit", "commit-not-permitted"),
                             ("push", "push-not-permitted"),
                             ("pr", "pr-not-permitted")):
            self.assertEqual(self.p.evaluate(default, self.p.ActionDescriptor(action_kind=kind)).reason, reason)
        permissive = self.p.parse_policy({"allow_commit": True})
        self.assertTrue(self.p.evaluate(permissive, self.p.ActionDescriptor(action_kind="commit")).allowed)


if __name__ == "__main__":
    unittest.main()
