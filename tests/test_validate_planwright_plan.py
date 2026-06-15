"""Behavior tests for the QB-exported planwright-plan validator.

The shared validator (shared/scripts/validate_planwright_plan.py) is the read-only
structural gate for the Step 3.5 export, .qb/plan.md. It mirrors the machine-checkable
subset of planwright's own plan linter, so a plan that passes here is accepted by
planwright on hand-off. These tests pin that gate: a clean plan passes, and each
structural violation class fails.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

VALIDATOR_PATH = SHARED_DIR / "scripts/validate_planwright_plan.py"

# Canonical 8-field item order, used to render fixtures deterministically.
_ORDER = ["Mode", "Rationale", "Evidence", "Surfaces", "New Surfaces",
          "Development", "Acceptance", "Verification"]


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "qb_planwright_plan_validator_under_test", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_root(tmp: str) -> Path:
    """A minimal repo root with a real Surface file the clean fixture can name."""
    root = Path(tmp)
    (root / ".qb").mkdir()
    (root / "src").mkdir()
    (root / "src/app.py").write_text("line1\nline2\nline3\n", encoding="utf-8")
    (root / "Makefile").write_text("check:\n\techo ok\n", encoding="utf-8")
    return root


def render(title: str = "Phase 1.1 — Add health endpoint", **over: object) -> str:
    """Render one item; pass a field=None to drop it, field='x' to override it."""
    fields: dict[str, str] = {
        "Mode": "develop",
        "Rationale": "there is no liveness probe, so orchestration cannot tell if it is up.",
        "Evidence": "src/app.py:1 defines the app with no /health route.",
        "Surfaces": "src/app.py",
        "Development": "add a GET /health handler returning 200, wired in src/app.py.",
        "Acceptance": "GET /health returns 200 with a JSON body.",
        "Verification": "make check",
    }
    for key, value in over.items():
        if value is None:
            fields.pop(key, None)
        else:
            fields[key] = str(value)
    lines = [f"- [ ] {title}"]
    for key in _ORDER:
        if key in fields:
            lines.append(f"      {key}: {fields[key]}")
    return "\n".join(lines) + "\n"


class ValidatePlanwrightPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        if not VALIDATOR_PATH.exists():
            self.skipTest(f"shared validator not present: {VALIDATOR_PATH}")
        self.v = _load_validator()

    def _errors(self, plan_text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(tmp)
            errors, _adv, _n = self.v.validate_plan(plan_text, str(root))
            return errors

    def _run_main(self, plan_text: str | None, strict: bool = False) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(tmp)
            if plan_text is not None:
                (root / ".qb/plan.md").write_text(plan_text, encoding="utf-8")
            argv = ["--root", str(root)] + (["--strict"] if strict else [])
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = self.v.main(argv)
            return code, buf.getvalue()

    def _exit_code(self, plan_text: str | None, strict: bool = False) -> int:
        return self._run_main(plan_text, strict)[0]

    # --- passing cases -------------------------------------------------------
    def test_clean_plan_passes(self) -> None:
        self.assertEqual(self._errors(render()), [])

    def test_clean_plan_exit_zero(self) -> None:
        self.assertEqual(self._exit_code(render()), 0)

    def test_valid_repair_with_anchor_passes(self) -> None:
        plan = render(
            title="Phase 1.2 — Fix off-by-one in pager",
            Mode="repair",
            Evidence="src/app.py:2 loops while i < n-1 instead of i < n.",
            Verification="python3 -m pytest tests/test_pager.py",
        )
        self.assertEqual(self._errors(plan), [])

    def test_surfaces_plus_new_surfaces_passes(self) -> None:
        plan = render(**{"New Surfaces": "src/health.py"})
        self.assertEqual(self._errors(plan), [])

    def test_empty_plan_passes(self) -> None:
        self.assertEqual(self._exit_code("<!-- nothing to export -->\n"), 0)

    def test_completed_items_are_not_linted(self) -> None:
        # A checked item with garbage fields must not fail the gate (pending-only).
        plan = "- [x] done already\n      Mode: nonsense\n"
        self.assertEqual(self._errors(plan), [])

    # --- failing cases -------------------------------------------------------
    def test_missing_required_field_fails(self) -> None:
        errors = self._errors(render(Verification=None))
        self.assertTrue(any("missing required field 'Verification:'" in e for e in errors), errors)

    def test_empty_required_field_fails(self) -> None:
        errors = self._errors(render(Rationale=""))
        self.assertTrue(any("empty field 'Rationale:'" in e for e in errors), errors)

    def test_new_surfaces_only_fails(self) -> None:
        # Surfaces is required even when New Surfaces is present (planwright parity).
        errors = self._errors(render(Surfaces=None, **{"New Surfaces": "src/health.py"}))
        self.assertTrue(any("missing required field 'Surfaces:'" in e for e in errors), errors)

    def test_invalid_mode_fails(self) -> None:
        errors = self._errors(render(Mode="frobnicate"))
        self.assertTrue(any("invalid Mode" in e for e in errors), errors)

    def test_nonexistent_surface_fails(self) -> None:
        errors = self._errors(render(Surfaces="src/ghost.py"))
        self.assertTrue(any("does not exist under root" in e for e in errors), errors)

    def test_absolute_surface_fails(self) -> None:
        errors = self._errors(render(Surfaces="/etc/hosts"))
        self.assertTrue(any("not a safe repo-relative path" in e for e in errors), errors)

    def test_repair_without_anchor_fails(self) -> None:
        errors = self._errors(render(Mode="repair",
                                     Evidence="the loop is wrong somewhere"))
        self.assertTrue(any("repair Evidence lacks a file:line anchor" in e for e in errors), errors)

    def test_placeholder_verification_fails(self) -> None:
        errors = self._errors(render(Verification="TODO"))
        self.assertTrue(any("placeholder" in e for e in errors), errors)

    def test_prose_verification_fails(self) -> None:
        errors = self._errors(render(Verification="verify manually later"))
        self.assertTrue(any("reads as prose" in e for e in errors), errors)

    def test_new_surface_that_exists_fails(self) -> None:
        errors = self._errors(render(**{"New Surfaces": "src/app.py"}))
        self.assertTrue(any("already exists" in e for e in errors), errors)

    def test_tool_owned_surface_fails(self) -> None:
        errors = self._errors(render(Surfaces=".planwright/plan.md"))
        self.assertTrue(any("tool-owned planwright state" in e for e in errors), errors)

    def test_graph_memory_evidence_fails(self) -> None:
        errors = self._errors(render(Evidence="graph.json says the node is hot"))
        self.assertTrue(any("graph memory" in e for e in errors), errors)

    def test_duplicate_title_fails(self) -> None:
        plan = render() + render()  # same title twice
        errors = self._errors(plan)
        self.assertTrue(any("duplicate pending title" in e for e in errors), errors)

    def test_missing_plan_file_exit_nonzero(self) -> None:
        self.assertEqual(self._exit_code(None), 1)

    # --- secret scanning -----------------------------------------------------
    def test_clean_plan_reports_zero_secret_findings(self) -> None:
        code, out = self._run_main(render())
        self.assertEqual(code, 0)
        self.assertIn("secret_findings=0", out)

    def test_secret_in_plan_fails(self) -> None:
        # Build the token at runtime so no literal secret is committed to this file
        # (mirrors the planner-docs secret tests; see tests/test_no_committed_secrets.py).
        leak = render(Rationale="leaked credential " + "sk-" + "A" * 24)
        code, out = self._run_main(leak)
        self.assertEqual(code, 1)
        self.assertIn("secret_pattern=openai_api_key", out)
        self.assertIn("secret_findings=1", out)

    def test_strict_promotes_missing_anchor_advisory(self) -> None:
        # A non-repair Evidence anchor to a missing file is advisory by default,
        # promoted to a failure under --strict.
        plan = render(Evidence="src/ghost.py:5 is the bad call site.",
                      Surfaces="src/app.py")
        self.assertEqual(self._exit_code(plan), 0)
        self.assertEqual(self._exit_code(plan, strict=True), 1)


if __name__ == "__main__":
    unittest.main()
