"""QB telemetry & quality metrics (Phase 7.1).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
Converts measurement from an afterthought into a first-class, persisted, redacted,
schema-versioned record emitted once per run. Captures detection metrics (findings
by severity/category, confidence histogram), action metrics (fixes attempted/kept/
reverted/blocked), and cost metrics (latency, iterations, best-effort tokens), plus
a derived precision estimate and a fix-safety flag.

"What good looks like": PRECISION_FLOOR is the precision below which auto-apply (A2)
is denied; fix-safety requires every kept fix to have passed verification. The
precision gate maps measured outcomes to the maximum permitted autonomy level,
fail-closed (no data => no auto-apply).
"""

from __future__ import annotations

import sys
from importlib import util as _import_util
from pathlib import Path

TELEMETRY_SCHEMA_VERSION = 1
TELEMETRY_FILENAME = "telemetry.json"

PRECISION_FLOOR = 0.80   # minimum estimated precision to permit auto-apply (A2)
_SEVERITIES = ("P0", "P1", "P2", "P3")
_CONFIDENCE_BANDS = ("low", "medium", "high")
UNMEASURED = "unmeasured"


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = _import_util.spec_from_file_location(module_name, path)
    module = _import_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_core = _load_sibling("qb_analyzer_core", "analyzer_core.py")


def _get(item, key):
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def redact(value):
    if isinstance(value, str):
        out = value
        for _name, pattern in _core.SECRET_PATTERNS:
            out = pattern.sub("<redacted>", out)
        return out
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def build_telemetry(*, run_id, autonomy_level, findings, evidence, cost=None, clamp_reason=None) -> dict:
    """Build the per-run telemetry record from findings + per-fix evidence."""
    by_severity = {s: 0 for s in _SEVERITIES}
    by_category: dict = {}
    confidence_hist = {b: 0 for b in _CONFIDENCE_BANDS}
    for f in findings:
        sev = _get(f, "severity")
        if sev in by_severity:
            by_severity[sev] += 1
        cat = _get(f, "category")
        if cat:
            by_category[cat] = by_category.get(cat, 0) + 1
        conf = _get(f, "confidence")
        if conf in confidence_hist:
            confidence_hist[conf] += 1

    kept = sum(1 for e in evidence if _get(e, "outcome") == "kept")
    reverted = sum(1 for e in evidence if _get(e, "outcome") == "reverted")
    blocked = sum(1 for e in evidence if _get(e, "outcome") == "blocked")
    attempted = kept + reverted + blocked
    # A kept fix that did not verify green is a fix-safety violation.
    kept_not_green = sum(1 for e in evidence
                         if _get(e, "outcome") == "kept" and (_get(e, "after_exit") not in (0, None)))

    cost = dict(cost or {})
    record = {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "run_id": run_id,
        "autonomy_level": autonomy_level,
        # Why effective autonomy was capped below the declared level (e.g.
        # "sandbox unavailable -> autonomy capped to A1"); None when not clamped.
        "clamp_reason": clamp_reason,
        "detection": {
            "findings_total": len(list(findings)),
            "by_severity": by_severity,
            "by_category": by_category,
            "confidence_histogram": confidence_hist,
        },
        "action": {
            "fixes_attempted": attempted,
            "fixes_kept": kept,
            "fixes_reverted": reverted,
            "fixes_blocked": blocked,
        },
        # An unsupplied cost field stays UNMEASURED rather than being coerced to a
        # measured 0 -- "never measured" must never read as "measured zero", even when
        # the other cost fields ARE real. (iterations defaults to 0 because the run
        # loop always counts iterations; wall_ms/tokens are present only when the run
        # forwarded a real measurement.)
        "cost": {
            "wall_ms": cost.get("wall_ms", UNMEASURED),
            "iterations": cost.get("iterations", 0),
            "tokens": cost.get("tokens", UNMEASURED),
        },
        "quality": {
            "precision_estimate": precision_estimate(kept, reverted),
            "false_positive_signals": reverted,
            "fix_safety_ok": kept_not_green == 0,
        },
    }
    return redact(record)


def precision_estimate(kept: int, reverted: int):
    """Estimated precision = kept / (kept + reverted); None when no fixes attempted."""
    denom = kept + reverted
    if denom == 0:
        return None
    return round(kept / denom, 4)


def max_permitted_autonomy(telemetry: dict, floor: float = PRECISION_FLOOR) -> str:
    """Precision gate: map measured quality to the max autonomy level (fail-closed)."""
    quality = telemetry.get("quality", {})
    precision = quality.get("precision_estimate")
    fix_safety_ok = quality.get("fix_safety_ok", False)
    if precision is None or not fix_safety_ok:
        return "A1"   # no/insufficient evidence or a fix-safety breach => no auto-apply
    if precision >= floor:
        return "A2"
    return "A1"
