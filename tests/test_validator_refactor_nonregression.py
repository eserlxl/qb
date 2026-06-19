"""Phase 1.3 -- the validator refactor preserves behavior and shares one source.

The reusable secret/severity machinery moved into
``shared/scripts/analyzer_core.py``; ``validate_planner_docs.py`` is now a caller.
This test pins (a) that there is a single source for the secret patterns and the
severity counter, (b) that the planning validation path is unchanged (secret
detection still fires; ``--mode all`` over the repo's own .qb tree still
passes), and (c) that the extracted secret scan is exposed as a Phase-1.2
analyzer returning Phase-1.1-conformant, redacted findings.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

CORE_PATH = SHARED_DIR / "scripts/analyzer_core.py"
VALIDATOR_PATH = SHARED_DIR / "scripts/validate_planner_docs.py"


def _write_heading_document(
    path: Path,
    headings: list[str],
    bodies: dict[str, str] | None = None,
) -> None:
    bodies = bodies or {}
    lines: list[str] = []
    for index, heading in enumerate(headings, start=1):
        lines.extend(
            [
                heading,
                "",
                bodies.get(
                    heading,
                    f"Fixture content for section {index} is intentionally complete enough "
                    "for the planner document validator.",
                ),
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_valid_planner_tree(root: Path, validator) -> None:
    qb = root / ".qb"
    phase_dir = qb / "phase-1-plans"
    phase_dir.mkdir(parents=True)

    _write_heading_document(
        qb / "main-planning.md",
        validator.STEP1_HEADINGS,
        {
            validator.ROADMAP_HEADING: (
                "| Phase | Summary |\n"
                "| --- | --- |\n"
                "| 1 | Build the validator fixture coverage. |"
            )
        },
    )
    _write_heading_document(
        qb / "sub-planning-index.md",
        validator.INDEX_HEADINGS,
        {
            "## 3. Phase and Sub-Plan Map": (
                "- .qb/phase-1-plans/phase-1.1-validator-fixture.md"
            ),
            "## 4. Prioritized Elaboration Order": (
                "1. .qb/phase-1-plans/phase-1.1-validator-fixture.md"
            ),
        },
    )
    _write_heading_document(qb / "sub-planning-audit.md", validator.AUDIT_HEADINGS)

    subplan = phase_dir / "phase-1.1-validator-fixture.md"
    subplan.write_text(
        "\n".join(
            [
                "# Phase 1.1 - Validator Fixture",
                "",
                *(
                    line
                    for index, heading in enumerate(validator.SUBPLAN_HEADINGS, start=1)
                    for line in (
                        heading,
                        "",
                        f"Fixture body {index} contains enough concrete planning detail "
                        "to satisfy structure and minimum-length checks.",
                        "",
                    )
                ),
            ]
        ),
        encoding="utf-8",
    )


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ValidatorRefactorNonRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        if not CORE_PATH.exists() or not VALIDATOR_PATH.exists():
            self.skipTest("analyzer_core or validator missing")
        # Load core under the exact name the validator uses, so the validator
        # reuses this instance and the single-source identity check is meaningful.
        self.core = _load("qb_analyzer_core", CORE_PATH)
        self.validator = _load("qb_validator_refactor_test", VALIDATOR_PATH)

    # --- single source of truth -------------------------------------------
    def test_validator_reuses_core_secret_patterns(self) -> None:
        self.assertIs(self.validator.SECRET_PATTERNS, self.core.SECRET_PATTERNS)

    def test_secret_pattern_set_is_canonical(self) -> None:
        names = [name for name, _ in self.core.SECRET_PATTERNS]
        self.assertEqual(
            names,
            ["openai_api_key", "github_pat", "github_legacy_pat",
             "aws_access_key", "private_key", "slack_token", "stripe_secret_key",
             "azure_storage_key", "github_app_token", "google_api_key"],
        )

    def test_severity_counter_is_delegated_and_correct(self) -> None:
        audit = (
            "## 13. Prioritized Fix List\n\n"
            "- AUDIT-FIX-01 | P0 | blocker\n"
            "- AUDIT-FIX-02 | P2 | nonblocking\n"
            "- AUDIT-FIX-03 | P2 | nonblocking\n"
        )
        self.assertEqual(
            self.validator.count_audit_severities(audit),
            {"P0": 1, "P1": 0, "P2": 2, "P3": 0},
        )

    # --- planning path behavior preserved ---------------------------------
    def test_validator_still_detects_a_planted_secret(self) -> None:
        token = "ghp_" + "C" * 30  # github_legacy_pat; split so it is not a committed literal
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "leak.txt").write_text(f"api = {token}\n", encoding="utf-8")
            state = self.validator.ValidationState(root=Path(d), mode="step2", strict=False)
            self.validator.scan_secrets(state)
            self.assertTrue(
                any("secret_pattern=github_legacy_pat" in e for e in state.errors),
                state.errors,
            )
            self.assertGreaterEqual(state.metrics["secret_findings"], 1)

    def test_mode_all_still_passes_over_repo_planner_docs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _build_valid_planner_tree(root, self.validator)
            result = subprocess.run(
                ["python3", str(VALIDATOR_PATH), "--root", str(root), "--mode", "all"],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("secret_findings=0", result.stdout)

    def test_mode_all_rejects_incomplete_planner_docs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _build_valid_planner_tree(root, self.validator)
            (root / ".qb/sub-planning-index.md").unlink()
            result = subprocess.run(
                ["python3", str(VALIDATOR_PATH), "--root", str(root), "--mode", "all"],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("missing_file=.qb/sub-planning-index.md", result.stdout)

    def test_step1_rejects_duplicate_required_heading(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _build_valid_planner_tree(root, self.validator)
            main_plan = root / ".qb/main-planning.md"
            main_plan.write_text(
                main_plan.read_text(encoding="utf-8")
                + "\n## 1. Executive Summary\n\nDuplicate summaries must fail validation.\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["python3", str(VALIDATOR_PATH), "--root", str(root), "--mode", "step1"],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "duplicate_heading=.qb/main-planning.md::## 1. Executive Summary::2",
            result.stdout,
        )

    # --- secret scan exposed as a Phase-1.2 analyzer ----------------------
    def test_secret_hygiene_analyzer_conforms_and_redacts(self) -> None:
        analyzer = self.core.SecretHygieneAnalyzer()
        self.assertIsInstance(analyzer, self.core.Analyzer)
        self.assertTrue(analyzer.descriptor.offline)
        self.assertEqual(analyzer.descriptor.categories, ("secret",))

        token = "ghp_" + "D" * 30
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "leak.txt").write_text(f"key = {token}\n", encoding="utf-8")
            (Path(d) / "clean.txt").write_text("nothing to see here\n", encoding="utf-8")
            findings = analyzer.analyze(d, self.core.AnalyzerConfig())

        self.assertTrue(findings, "analyzer should report the planted secret")
        for f in findings:
            self.assertEqual(self.core.validate_finding(f), [], f"non-conformant: {f}")
            # redact-by-default: the secret value never appears in any field.
            for value in (f.evidence, f.rationale, f.suggested_fix, f.id):
                self.assertNotIn(token, value)
        self.assertTrue(
            any(f.category == "secret" and f.evidence.startswith("leak.txt:") for f in findings)
        )

    def test_secret_hygiene_analyzer_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "leak.txt").write_text("ghp_" + "E" * 30 + "\n", encoding="utf-8")
            before = {p.name: p.stat().st_mtime_ns for p in Path(d).iterdir()}
            self.core.SecretHygieneAnalyzer().analyze(d, self.core.AnalyzerConfig())
            after = {p.name: p.stat().st_mtime_ns for p in Path(d).iterdir()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
