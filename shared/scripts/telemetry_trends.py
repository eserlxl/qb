"""Trend extraction helpers for aggregate telemetry."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

DIMENSION_PATHS = {
    "precision": ("quality", "precision_estimate"),
    "fix_safety": ("quality", "fix_safety_ok"),
    "latency": ("cost", "wall_ms"),
    "cost": ("cost", "tokens"),
    "quality": ("quality", "false_positive_signals"),
}
LOWER_IS_BETTER = frozenset({"latency", "cost", "quality"})
VERDICT_IMPROVING = "improving"
VERDICT_STABLE = "stable"
VERDICT_REGRESSING = "regressing"
VERDICT_INSUFFICIENT = "insufficient-data"
VERDICT_UNMEASURED = "unmeasured"


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
_telemetry = _load_sibling("qb_telemetry", "telemetry.py")
UNMEASURED = _telemetry.UNMEASURED


def _as_aggregate(source) -> dict:
    if isinstance(source, dict):
        return source
    return _aggregate.read_aggregate(source)


def _value_at(run: dict, path: tuple[str, str]):
    current = run
    for key in path:
        if not isinstance(current, dict):
            return UNMEASURED
        current = current.get(key, UNMEASURED)
    return current


def dimension_series(source, dimension: str) -> list[dict]:
    """Return one run/value row per aggregate entry for a named dimension."""
    if dimension not in DIMENSION_PATHS:
        raise KeyError(f"unknown trend dimension: {dimension}")
    aggregate = _as_aggregate(source)
    rows = []
    for run in aggregate.get("runs", []):
        if not isinstance(run, dict):
            continue
        rows.append({
            "run_id": run.get("run_id", ""),
            "value": _value_at(run, DIMENSION_PATHS[dimension]),
        })
    return rows


def extract_series(source) -> dict[str, list[dict]]:
    """Return all supported trend dimensions as run/value series."""
    return {
        dimension: dimension_series(source, dimension)
        for dimension in sorted(DIMENSION_PATHS)
    }


def _measured_number(value):
    if value in (None, UNMEASURED):
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    return None


def direction_verdict(source, dimension: str, window: int = 3) -> str:
    """Classify the last N rows as improving, stable, regressing, or non-committal."""
    if window < 2:
        raise ValueError("trend verdict window must be at least 2")
    rows = dimension_series(source, dimension)[-window:]
    measured = [
        numeric
        for numeric in (_measured_number(row.get("value")) for row in rows)
        if numeric is not None
    ]
    if not measured:
        return VERDICT_UNMEASURED
    if len(measured) < 2:
        return VERDICT_INSUFFICIENT

    first = measured[0]
    last = measured[-1]
    if last == first:
        return VERDICT_STABLE
    increasing = last > first
    if dimension in LOWER_IS_BETTER:
        return VERDICT_REGRESSING if increasing else VERDICT_IMPROVING
    return VERDICT_IMPROVING if increasing else VERDICT_REGRESSING
