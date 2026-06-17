"""QB aggregate telemetry series.

This module keeps multi-run telemetry as a small, versioned wrapper around the
per-run records produced by telemetry.py. It does not define new metric
vocabulary; each entry reuses the existing detection/action/cost/quality slices.
"""

from __future__ import annotations

import importlib.util
import json
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


def read_aggregate(path) -> dict:
    """Read an aggregate series, returning an empty series when absent or invalid."""
    target = Path(path)
    if not target.is_file():
        return build_aggregate([])
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return build_aggregate([])
    if data.get("schema_version") != AGGREGATE_TELEMETRY_SCHEMA_VERSION:
        return build_aggregate([])
    runs = data.get("runs")
    if not isinstance(runs, list):
        return build_aggregate([])
    return build_aggregate([run for run in runs if isinstance(run, dict)])


def append_or_update(path, record: dict) -> dict:
    """Append one run, or replace the existing entry with the same run_id in place."""
    target = Path(path)
    aggregate = read_aggregate(target)
    entry = _copy_run(dict(record))
    run_id = entry.get("run_id", "")
    runs = list(aggregate["runs"])
    for index, existing in enumerate(runs):
        if existing.get("run_id") == run_id:
            runs[index] = entry
            break
    else:
        runs.append(entry)
    updated = build_aggregate(runs)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(updated, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return updated
