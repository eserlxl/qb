"""Precision/recall harness baseline tests."""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import REPO_ROOT, SHARED_DIR

HARNESS_PATH = SHARED_DIR / "scripts/precision_harness.py"
CORPUS = REPO_ROOT / "tests/fixtures/precision-corpus"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PrecisionHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        if not HARNESS_PATH.exists() or not CORPUS.exists():
            self.skipTest("precision harness or corpus missing")
        self.harness = _load("qb_precision_harness_under_test", HARNESS_PATH)

    def _deterministic_registry(self):
        registry = self.harness.AnalyzerRegistry()
        registry.register(self.harness._runner.CommandInjectionAnalyzer())
        registry.register(self.harness._runner.DependencyAnalyzer())
        registry.register(self.harness._runner.SecretHygieneAnalyzer())
        registry.register(self.harness._runner.WorkflowActionAnalyzer())
        return registry

    def _build_report(self, corpus: Path):
        original = self.harness.build_default_registry
        self.harness.build_default_registry = self._deterministic_registry
        try:
            return self.harness.build_report(corpus)
        finally:
            self.harness.build_default_registry = original

    def test_baseline_metrics_are_deterministic(self) -> None:
        first = self._build_report(CORPUS)
        second = self._build_report(CORPUS)

        self.assertEqual(self.harness.render_report(first), self.harness.render_report(second))
        self.assertEqual(
            first["totals"],
            {
                "true_positive": 5,
                "false_positive": 0,
                "false_negative": 0,
                "precision": 1.0,
                "recall": 1.0,
            },
        )
        self.assertEqual(first["per_category"]["injection"]["precision"], 1.0)
        self.assertEqual(first["per_category"]["secret"]["recall"], 1.0)
        self.assertEqual(first["per_category"]["dependency"]["precision"], 1.0)
        self.assertEqual(first["per_analyzer"]["command-injection"]["precision"], 1.0)
        self.assertEqual(first["per_analyzer"]["dependency-audit"]["recall"], 1.0)
        self.assertEqual(first["per_analyzer"]["secret-hygiene"]["recall"], 1.0)
        self.assertEqual(first["per_analyzer"]["workflow-actions"]["recall"], 1.0)

    def test_unlabelled_positive_changes_precision(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            corpus = Path(d) / "corpus"
            shutil.copytree(CORPUS, corpus)
            injected = corpus / "clean-baseline/fp.py"
            injected.write_text("import os\nos.system(cmd)\n", encoding="utf-8")

            report = self._build_report(corpus)

        self.assertEqual(report["totals"]["true_positive"], 5)
        self.assertEqual(report["totals"]["false_positive"], 1)
        self.assertEqual(report["totals"]["false_negative"], 0)
        self.assertEqual(report["totals"]["precision"], 5 / 6)
        self.assertEqual(report["per_analyzer"]["command-injection"]["precision"], 0.5)

    def test_threshold_gate_pass_fail_and_capability_aware(self) -> None:
        report = self._build_report(CORPUS)  # deterministic: totals precision/recall 1.0
        # Met bars -> pass, no failures.
        ok = self.harness.evaluate_thresholds(report, min_precision=1.0, min_recall=1.0)
        self.assertTrue(ok["passed"])
        self.assertEqual(ok["failures"], [])
        # Unmet bars -> fail with a deterministic, sorted failure summary.
        bad = {"totals": {"precision": 0.5, "recall": 0.5},
               "per_analyzer": {}, "per_category": {}, "capability_skipped": []}
        res = self.harness.evaluate_thresholds(bad, min_precision=0.9, min_recall=0.9)
        self.assertFalse(res["passed"])
        self.assertEqual(
            [(f["scope"], f["metric"]) for f in res["failures"]],
            [("totals", "precision"), ("totals", "recall")],
        )
        # Capability-aware: an analyzer marked capability_skipped (absent optional
        # tool) must not be scored as a failure even with a failing metric.
        skipped = {"totals": {"precision": 1.0, "recall": 1.0},
                   "per_analyzer": {"quality-correctness": {"precision": 0.0, "recall": 0.0}},
                   "per_category": {}, "capability_skipped": ["quality-correctness"]}
        cap = self.harness.evaluate_thresholds(
            skipped, per_analyzer={"quality-correctness": {"min_precision": 1.0, "min_recall": 1.0}})
        self.assertTrue(cap["passed"], "an absent-tool analyzer must not fail the gate")

    def test_main_gate_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = str(Path(d) / "report.json")
            # A passing corpus with no bars requested exits 0.
            self.assertEqual(self.harness.main(["--corpus", str(CORPUS), "--out", out]), 0)
            # An unmet bar fails closed with a non-zero exit code (totals precision
            # over the full registry is well below 0.999).
            self.assertEqual(
                self.harness.main(["--corpus", str(CORPUS), "--out", out, "--min-precision", "0.999"]),
                1,
            )


if __name__ == "__main__":
    unittest.main()
