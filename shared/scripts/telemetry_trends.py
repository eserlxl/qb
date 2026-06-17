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
