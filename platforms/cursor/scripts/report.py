"""QB machine-readable reporting (Phase 5.2 + 5.3).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
Renders, from the Phase-5.1 run-state store (never recomputing analysis), three
deterministic outputs for a single run:
  * report.json  -- versioned typed report (graded findings + per-fix hardening),
                    optionally carrying a provenance block (Phase 5.3) and the
                    separable reviewer's cross-review verdicts.
  * report.sarif -- SARIF 2.1.0: each finding a result with a category-derived
                    rule id, a P0-P3-derived level, and an evidence location.
  * summary.txt  -- a concise human summary using QB's P0-P3 vocabulary.

Determinism (Phase 5.3): findings/results are sorted by id and JSON is emitted
with sorted keys, so re-rendering the same store is byte-identical. The only
non-deterministic fields are those the caller places under provenance.timing.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPORT_SCHEMA_VERSION = 1
SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

SEVERITY_TO_SARIF = {"P0": "error", "P1": "error", "P2": "warning", "P3": "note"}
_SEVERITIES = ("P0", "P1", "P2", "P3")

REPORT_FILENAME = "report.json"
SARIF_FILENAME = "report.sarif"
SUMMARY_TEXT_FILENAME = "summary.txt"

# Fields excluded from byte-for-byte reproducibility comparison (Phase 5.3).
NON_DETERMINISTIC_FIELDS = ("timing",)
TIMING_BOUNDARY_DECISION = (
    "raw wall-clock latency is excluded from the canonical report body; "
    "callers may place it under provenance.timing, covered by NON_DETERMINISTIC_FIELDS"
)
SIGNALS_SURFACING_DECISION = (
    "signals are surfaced in report.json and summary.txt; report.sarif remains "
    "standards-conformant SARIF without QB-specific operational signals"
)


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_aggregate = _load_sibling("qb_telemetry_aggregate", "telemetry_aggregate.py")
_trends = _load_sibling("qb_telemetry_trends", "telemetry_trends.py")


def _category_rule(category: str) -> str:
    return f"qb/{category}"


def _evidence_location(evidence: str):
    path, _, line = (evidence or "").partition(":")
    try:
        start = int(line.split("-", 1)[0]) if line else 1
    except ValueError:
        start = 1
    return path or evidence, start


def _precision_estimate(kept: int, reverted: int):
    denom = kept + reverted
    return round(kept / denom, 4) if denom else None


def _store_signals(store, findings: list, hardening: list) -> dict:
    """Operational signals derived only from persisted store artifacts.

    This function deliberately performs no wall-clock reads; render-time timing
    stays under provenance.timing so report-body re-renders stay byte-identical.
    """
    telemetry = store.read_telemetry() if hasattr(store, "read_telemetry") else {}
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    quality = telemetry.get("quality") if isinstance(telemetry.get("quality"), dict) else {}
    cost = telemetry.get("cost") if isinstance(telemetry.get("cost"), dict) else {}
    summary = store.read_summary()

    severity_counts = {s: 0 for s in _SEVERITIES}
    for finding in findings:
        severity = finding.get("severity")
        if severity in severity_counts:
            severity_counts[severity] += 1

    fixes = {
        "kept": sum(1 for e in hardening if e.get("outcome") == "kept"),
        "reverted": sum(1 for e in hardening if e.get("outcome") == "reverted"),
        "blocked": sum(1 for e in hardening if e.get("outcome") == "blocked"),
    }
    precision = quality.get("precision_estimate", _precision_estimate(fixes["kept"], fixes["reverted"]))
    fix_safety = quality.get(
        "fix_safety_ok",
        all(e.get("after_exit") in (0, None) for e in hardening if e.get("outcome") == "kept"),
    )
    signals = {
        "severity_counts": severity_counts,
        "fixes": fixes,
        "quality": {
            "precision_estimate": precision,
            "fix_safety_ok": fix_safety,
        },
        "iterations": cost.get("iterations", summary.get("iterations", 0)),
    }
    aggregate_path = getattr(store, "root", None)
    if aggregate_path is not None:
        aggregate_file = Path(aggregate_path) / _aggregate.AGGREGATE_TELEMETRY_FILENAME
        aggregate = _aggregate.read_aggregate(aggregate_file)
        if aggregate.get("runs"):
            signals["trend_direction"] = {
                dimension: _trends.direction_verdict(aggregate, dimension)
                for dimension in sorted(_trends.DIMENSION_PATHS)
            }
    return signals


def render_json(store, *, provenance=None) -> dict:
    """Typed JSON report rendered purely from the store (sorted, deterministic)."""
    findings = sorted(store.read_findings(), key=lambda f: f.get("id", ""))
    hardening = sorted(store.read_evidence(), key=lambda e: e.get("finding_id", ""))
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "summary": store.read_summary(),
        "signals": _store_signals(store, findings, hardening),
        "findings": findings,
        "hardening": hardening,
    }
    if provenance is not None:
        report["provenance"] = provenance
    return report


def render_sarif(store) -> dict:
    """SARIF 2.1.0 document: one result per finding, standard structure."""
    findings = sorted(store.read_findings(), key=lambda f: f.get("id", ""))
    rule_ids = sorted({_category_rule(f.get("category", "unknown")) for f in findings})
    results = []
    for finding in findings:
        path, line = _evidence_location(finding.get("evidence", ""))
        results.append({
            "ruleId": _category_rule(finding.get("category", "unknown")),
            # Fail closed: an unknown or missing severity (e.g. a store written by a
            # future/buggy producer, never re-validated on read) maps to the MOST
            # severe level, not silently down to 'warning' which would hide a P0.
            "level": SEVERITY_TO_SARIF.get(finding.get("severity"), "error"),
            "message": {"text": finding.get("rationale", "")},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": path},
                    "region": {"startLine": line},
                }
            }],
        })
    return {
        "version": SARIF_VERSION,
        "$schema": SARIF_SCHEMA,
        "runs": [{
            "tool": {"driver": {"name": "QB", "rules": [{"id": rid} for rid in rule_ids]}},
            "results": results,
        }],
    }


def render_summary_text(store) -> str:
    """Concise human summary: counts by severity, fixes kept/reverted, stop reason."""
    findings = store.read_findings()
    evidence = store.read_evidence()
    summary = store.read_summary()
    signals = _store_signals(store, findings, evidence)
    sev_counts = signals["severity_counts"]
    fixes = signals["fixes"]
    quality = signals["quality"]
    # Established process-confinement controls (names only, no command output), so a
    # reader can confirm fix verification "ran contained" from the summary alone.
    confinement = sorted({c for e in evidence for c in (e.get("confinement_controls") or [])})
    confinement_str = ",".join(confinement) if confinement else "none"
    lines = [
        "QB audit report",
        f"findings: {len(findings)} (" + ", ".join(f"{s}={sev_counts[s]}" for s in _SEVERITIES) + ")",
        f"hardening: kept={fixes['kept']} reverted={fixes['reverted']} blocked={fixes['blocked']}",
        f"confinement: {confinement_str}",
        "signals: "
        f"precision={quality['precision_estimate']} "
        f"fix_safety_ok={quality['fix_safety_ok']} "
        f"iterations={signals['iterations']}",
        f"stop: {summary.get('trigger', summary.get('stop', 'completed'))}",
    ]
    if "trend_direction" in signals:
        trend_text = json.dumps(signals["trend_direction"], sort_keys=True, separators=(",", ":"))
        lines.insert(-1, f"trend_direction: {trend_text}")
    return "\n".join(lines) + "\n"


def validate_report(report: dict) -> list:
    """Lightweight schema conformance check (no third-party validator)."""
    errors = []
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        errors.append(f"bad_schema_version={report.get('schema_version')}")
    for key in ("summary", "signals", "findings", "hardening"):
        if key not in report:
            errors.append(f"missing_key={key}")
    if not isinstance(report.get("findings"), list):
        errors.append("findings_not_a_list")
    if not isinstance(report.get("hardening"), list):
        errors.append("hardening_not_a_list")
    return errors


def emit(store, *, provenance=None) -> dict:
    """Render and write all three outputs into the store directory; return paths."""
    report = render_json(store, provenance=provenance)
    sarif = render_sarif(store)
    summary_text = render_summary_text(store)
    (store.root / REPORT_FILENAME).write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (store.root / SARIF_FILENAME).write_text(
        json.dumps(sarif, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (store.root / SUMMARY_TEXT_FILENAME).write_text(summary_text, encoding="utf-8")
    return {
        "report": str(store.root / REPORT_FILENAME),
        "sarif": str(store.root / SARIF_FILENAME),
        "summary_text": str(store.root / SUMMARY_TEXT_FILENAME),
    }


def build_provenance(policy, *, analyzer_versions=None, timing=None) -> dict:
    """Phase 5.3 provenance: analyzer versions, resolved policy, autonomy level, budgets.

    Per-analyzer versions are captured explicitly (manifests already drift, so there
    is no single global version); an absent optional/networked analyzer is recorded
    as 'absent' rather than omitted. ``timing`` is the sole non-deterministic field.
    """
    provenance = {
        "autonomy_level": getattr(policy, "autonomy_level", "A0"),
        "policy": {
            "auto_fixable_categories": sorted(getattr(policy, "auto_fixable_categories", []) or []),
            "default_min_confidence": getattr(policy, "default_min_confidence", "high"),
            "write_allowlist": list(getattr(policy, "write_allowlist", ()) or ()),
            "write_denylist": list(getattr(policy, "write_denylist", ()) or ()),
            "allow_commit": getattr(policy, "allow_commit", False),
            "allow_push": getattr(policy, "allow_push", False),
            "allow_pr": getattr(policy, "allow_pr", False),
        },
        "budgets": dict(getattr(policy, "budgets", {}) or {}),
        "analyzer_versions": dict(analyzer_versions or {}),
    }
    if timing is not None:
        provenance["timing"] = timing  # the only non-deterministic field
    return provenance
