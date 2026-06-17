"""QB aggregate telemetry series.

This module keeps multi-run telemetry as a small, versioned wrapper around the
per-run records produced by telemetry.py. It does not define new metric
vocabulary; each entry reuses the existing detection/action/cost/quality slices.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

AGGREGATE_TELEMETRY_SCHEMA_VERSION = 1
AGGREGATE_TELEMETRY_FILENAME = "telemetry-aggregate.json"
TELEMETRY_SLICES = ("detection", "action", "cost", "quality")


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_telemetry = _load_sibling("qb_telemetry", "telemetry.py")


def _copy_run(record: dict) -> dict:
    entry = {
        "schema_version": record.get("schema_version", _telemetry.TELEMETRY_SCHEMA_VERSION),
        "run_id": record.get("run_id", ""),
        "autonomy_level": record.get("autonomy_level", ""),
        "clamp_reason": record.get("clamp_reason"),
    }
    for key in TELEMETRY_SLICES:
        entry[key] = dict(record.get(key, {}))
    return _telemetry.redact(entry)


def build_aggregate(records) -> dict:
    """Build a versioned, ordered series from per-run telemetry records."""
    runs = [_copy_run(dict(record)) for record in records]
    return {
        "schema_version": AGGREGATE_TELEMETRY_SCHEMA_VERSION,
        "run_count": len(runs),
        "runs": runs,
    }
