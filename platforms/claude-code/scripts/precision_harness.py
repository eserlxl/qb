"""QB precision/recall harness for labelled audit fixtures.

This module is standard-library only and offline by construction. It runs the
read-only audit engine over each fixture in a labelled corpus, joins emitted
findings to `labels.json` entries, and renders a deterministic JSON report with
per-analyzer and per-category precision/recall.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_runner = _load_sibling("qb_audit_runner", "audit_runner.py")
_schema = _load_sibling("qb_finding_schema", "finding_schema.py")

AnalyzerConfig = _runner.AnalyzerConfig
AnalyzerRegistry = _runner.AnalyzerRegistry
build_default_registry = _runner.build_default_registry
run_audit = _runner.run_audit
compute_finding_id = _schema.compute_finding_id
CATEGORIES = _schema.CATEGORIES

SCHEMA_VERSION = 1
LABELS_FILENAME = "labels.json"


def _ratio(numerator: int, denominator: int):
    if denominator == 0:
        return None
    return numerator / denominator


def _new_counts() -> dict:
    return {
        "true_positive": 0,
        "false_positive": 0,
        "false_negative": 0,
    }


def _finalize_counts(counts: dict) -> dict:
    result = dict(counts)
    tp = result["true_positive"]
    fp = result["false_positive"]
    fn = result["false_negative"]
    result["precision"] = _ratio(tp, tp + fp)
    result["recall"] = _ratio(tp, tp + fn)
    return result


def _add_counts(target: dict, counts: dict) -> None:
    target["true_positive"] += counts["true_positive"]
    target["false_positive"] += counts["false_positive"]
    target["false_negative"] += counts["false_negative"]


def _validate_label(raw: dict, fixture: str, index: int) -> dict:
    category = raw.get("category")
    evidence = raw.get("evidence")
    rule_key = raw.get("rule_key")
    analyzer_id = raw.get("analyzer_id")
    if not isinstance(category, str) or category not in CATEGORIES:
        raise ValueError(f"{fixture}: expected_findings[{index}].category is invalid")
    if not isinstance(evidence, str) or ":" not in evidence:
        raise ValueError(f"{fixture}: expected_findings[{index}].evidence is invalid")
    if not isinstance(rule_key, str) or not rule_key.strip():
        raise ValueError(f"{fixture}: expected_findings[{index}].rule_key is invalid")
    if analyzer_id is not None and (not isinstance(analyzer_id, str) or not analyzer_id.strip()):
        raise ValueError(f"{fixture}: expected_findings[{index}].analyzer_id is invalid")
    finding_id = compute_finding_id(category, evidence, rule_key)
    label = {
        "category": category,
        "evidence": evidence,
        "rule_key": rule_key,
        "id": finding_id,
    }
    if analyzer_id is not None:
        label["analyzer_id"] = analyzer_id
    return label


def load_labels(fixture_dir) -> dict:
    """Load and validate one fixture's ground-truth labels."""
    fixture_path = Path(fixture_dir)
    manifest_path = fixture_path / LABELS_FILENAME
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixture = data.get("fixture", fixture_path.name)
    if not isinstance(fixture, str) or not fixture.strip():
        raise ValueError(f"{manifest_path}: fixture must be a non-empty string")
    expected = data.get("expected_findings")
    if not isinstance(expected, list):
        raise ValueError(f"{manifest_path}: expected_findings must be a list")
    labels = [_validate_label(raw, fixture, index) for index, raw in enumerate(expected)]
    labels.sort(key=lambda item: (item["category"], item["evidence"], item["id"]))
    return {"fixture": fixture, "expected_findings": labels}


def discover_fixtures(corpus_root) -> list[Path]:
    """Return fixture directories with labels.json in deterministic order."""
    root = Path(corpus_root)
    fixtures = [
        path for path in root.iterdir()
        if path.is_dir() and (path / LABELS_FILENAME).is_file()
    ]
    return sorted(fixtures, key=lambda path: path.name)


def _finding_key(finding) -> tuple[str, str, str]:
    return (finding.category, finding.evidence, finding.id)


def _label_key(label: dict) -> tuple[str, str, str]:
    return (label["category"], label["evidence"], label["id"])


def _compare(labels: list[dict], findings: list) -> dict:
    expected = {_label_key(label) for label in labels}
    emitted = {_finding_key(finding) for finding in findings}
    matched = expected & emitted
    return {
        "true_positive": len(matched),
        "false_positive": len(emitted - expected),
        "false_negative": len(expected - emitted),
    }


def _single_analyzer_registry(analyzer_id: str):
    registry = AnalyzerRegistry()
    for analyzer in build_default_registry().analyzers():
        if analyzer.descriptor.id == analyzer_id:
            registry.register(analyzer)
            return registry
    raise KeyError(f"unknown analyzer id: {analyzer_id}")


def _audit_output_dir(root: Path, fixture: str, analyzer_id: str) -> Path:
    safe_fixture = fixture.replace("/", "_")
    safe_analyzer = analyzer_id.replace("/", "_")
    return root / safe_fixture / safe_analyzer / _runner.OUTPUT_DIR_NAME


def _offline_run(fixture_dir: Path, registry, output_dir: Path) -> dict:
    return run_audit(
        fixture_dir,
        config=AnalyzerConfig(allow_networked=False),
        registry=registry,
        output_dir=output_dir,
    )


def _labels_for_categories(labels: list[dict], categories: set[str]) -> list[dict]:
    return [label for label in labels if label["category"] in categories]


def _labels_for_analyzer(labels: list[dict], descriptor) -> list[dict]:
    scoped: list[dict] = []
    categories = set(descriptor.categories)
    for label in labels:
        owner = label.get("analyzer_id")
        if owner is not None:
            if owner == descriptor.id:
                scoped.append(label)
            continue
        if label["category"] in categories:
            scoped.append(label)
    return scoped


def _findings_for_category(findings: list, category: str) -> list:
    return [finding for finding in findings if finding.category == category]


def build_report(corpus_root, audit_output_root=None) -> dict:
    """Run the offline audit over a corpus and return deterministic metrics."""
    fixtures = discover_fixtures(corpus_root)
    analyzer_descriptors = [
        analyzer.descriptor for analyzer in build_default_registry().analyzers()
        if analyzer.descriptor.offline
    ]
    analyzer_descriptors.sort(key=lambda descriptor: descriptor.id)

    per_analyzer = {descriptor.id: _new_counts() for descriptor in analyzer_descriptors}
    per_category = {category: _new_counts() for category in sorted(CATEGORIES)}
    totals = _new_counts()
    fixture_reports: list[dict] = []
    # Analyzers that could not effectively run because their only adapters were
    # optional tools that were absent (e.g. ruff/pyflakes): the gate must not score
    # these as a precision/recall failure -- not-run is distinct from below-threshold.
    capability_skipped: set[str] = set()

    if audit_output_root is None:
        scratch_ctx = tempfile.TemporaryDirectory()
        audit_root = Path(scratch_ctx.name)
    else:
        scratch_ctx = None
        audit_root = Path(audit_output_root)
        audit_root.mkdir(parents=True, exist_ok=True)

    try:
        for fixture_dir in fixtures:
            manifest = load_labels(fixture_dir)
            fixture_name = manifest["fixture"]
            labels = manifest["expected_findings"]
            full_registry = build_default_registry()
            full_result = _offline_run(
                fixture_dir,
                full_registry,
                _audit_output_dir(audit_root, fixture_name, "all"),
            )
            full_findings = full_result["findings"]
            fixture_counts = _compare(labels, full_findings)
            _add_counts(totals, fixture_counts)

            for category in sorted(CATEGORIES):
                category_counts = _compare(
                    _labels_for_categories(labels, {category}),
                    _findings_for_category(full_findings, category),
                )
                _add_counts(per_category[category], category_counts)

            analyzer_rows = {}
            for descriptor in analyzer_descriptors:
                registry = _single_analyzer_registry(descriptor.id)
                analyzer_result = _offline_run(
                    fixture_dir,
                    registry,
                    _audit_output_dir(audit_root, fixture_name, descriptor.id),
                )
                analyzer_labels = _labels_for_analyzer(labels, descriptor)
                analyzer_counts = _compare(analyzer_labels, analyzer_result["findings"])
                _add_counts(per_analyzer[descriptor.id], analyzer_counts)
                analyzer_rows[descriptor.id] = _finalize_counts(analyzer_counts)
                # Capability: if this analyzer's adapters were all absent optional
                # tools (ran nothing, every adapter tool-unavailable), record it so
                # the gate treats it as not-run rather than below-threshold.
                cap = analyzer_result["summary"].get("capability_report", {}).get(descriptor.id)
                if cap is not None and not cap.get("ran") and cap.get("skipped") and all(
                    entry.get("reason") == "tool-unavailable" for entry in cap["skipped"]
                ):
                    capability_skipped.add(descriptor.id)

            fixture_reports.append({
                "fixture": fixture_name,
                "expected_findings": len(labels),
                "emitted_findings": len(full_findings),
                "metrics": _finalize_counts(fixture_counts),
                "per_analyzer": analyzer_rows,
            })
    finally:
        if scratch_ctx is not None:
            scratch_ctx.cleanup()

    return {
        "schema_version": SCHEMA_VERSION,
        "fixtures": fixture_reports,
        "per_analyzer": {
            key: _finalize_counts(per_analyzer[key])
            for key in sorted(per_analyzer)
        },
        "per_category": {
            key: _finalize_counts(per_category[key])
            for key in sorted(per_category)
        },
        "totals": _finalize_counts(totals),
        "capability_skipped": sorted(capability_skipped),
    }


def render_report(report: dict) -> str:
    """Render a byte-stable JSON report."""
    return json.dumps(report, sort_keys=True, indent=2) + "\n"


def write_report(report: dict, path) -> None:
    Path(path).write_text(render_report(report), encoding="utf-8")


def evaluate_thresholds(report: dict, *, min_precision=None, min_recall=None,
                        per_analyzer=None, per_category=None) -> dict:
    """Evaluate a built report against minimum precision/recall bars.

    ``min_precision`` / ``min_recall`` are the overall (``totals``) bars;
    ``per_analyzer`` / ``per_category`` map an id to ``{"min_precision": x,
    "min_recall": y}`` for scoped bars. A metric of ``None`` means **not
    measured** -- there were no labelled-and-emitted cases for that scope (for
    example an analyzer whose optional tool was absent, so it produced nothing) --
    and is **never** scored as a failure, so the gate distinguishes below-threshold
    from not-run (capability-aware).

    Returns ``{"passed": bool, "failures": [{"scope", "metric", "threshold",
    "actual"}, ...]}`` with a deterministic, sorted failures list.
    """
    failures: list[dict] = []

    def _check(scope: str, metrics: dict, bar_precision, bar_recall) -> None:
        for metric, bar in (("precision", bar_precision), ("recall", bar_recall)):
            if bar is None:
                continue
            actual = metrics.get(metric)
            if actual is not None and actual < bar:
                failures.append({
                    "scope": scope,
                    "metric": metric,
                    "threshold": bar,
                    "actual": actual,
                })

    _check("totals", report.get("totals", {}), min_precision, min_recall)
    capability_skipped = set(report.get("capability_skipped", []))
    for analyzer_id, bars in sorted((per_analyzer or {}).items()):
        if analyzer_id in capability_skipped:
            continue  # not-run (its optional tool was absent): never a failure
        metrics = report.get("per_analyzer", {}).get(analyzer_id)
        if metrics is not None:
            _check(f"per_analyzer:{analyzer_id}", metrics,
                   bars.get("min_precision"), bars.get("min_recall"))
    for category, bars in sorted((per_category or {}).items()):
        metrics = report.get("per_category", {}).get(category)
        if metrics is not None:
            _check(f"per_category:{category}", metrics,
                   bars.get("min_precision"), bars.get("min_recall"))

    failures.sort(key=lambda item: (item["scope"], item["metric"]))
    return {"passed": not failures, "failures": failures}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the QB precision/recall harness.")
    parser.add_argument(
        "--corpus",
        default="tests/fixtures/precision-corpus",
        help="Labelled fixture corpus root.",
    )
    parser.add_argument("--out", default=None, help="Write the JSON report to this path.")
    parser.add_argument(
        "--audit-out",
        default=None,
        help="Optional directory for per-fixture .qb/audit outputs; defaults to a temporary directory.",
    )
    parser.add_argument("--min-precision", type=float, default=None,
                        help="Minimum overall (totals) precision; the gate fails below it.")
    parser.add_argument("--min-recall", type=float, default=None,
                        help="Minimum overall (totals) recall; the gate fails below it.")
    parser.add_argument("--thresholds", default=None,
                        help="JSON file of bars: {min_precision, min_recall, "
                             "per_analyzer:{id:{min_precision,min_recall}}, per_category:{...}}.")
    args = parser.parse_args(argv)

    report = build_report(args.corpus, audit_output_root=args.audit_out)
    text = render_report(report)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)

    # Fail-closed threshold gate (opt-in): only gate when a bar was requested.
    thresholds = {}
    if args.thresholds:
        thresholds = json.loads(Path(args.thresholds).read_text(encoding="utf-8"))
    overall_precision = args.min_precision if args.min_precision is not None else thresholds.get("min_precision")
    overall_recall = args.min_recall if args.min_recall is not None else thresholds.get("min_recall")
    per_analyzer = thresholds.get("per_analyzer")
    per_category = thresholds.get("per_category")
    if (overall_precision is None and overall_recall is None
            and not per_analyzer and not per_category):
        return 0

    gate = evaluate_thresholds(
        report,
        min_precision=overall_precision,
        min_recall=overall_recall,
        per_analyzer=per_analyzer,
        per_category=per_category,
    )
    sys.stderr.write(json.dumps(
        {"gate": "PASS" if gate["passed"] else "FAIL", "failures": gate["failures"]},
        sort_keys=True,
    ) + "\n")
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
