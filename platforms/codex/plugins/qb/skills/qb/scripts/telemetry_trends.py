"""Trend extraction helpers for aggregate telemetry."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

TREND_REPORT_SCHEMA_VERSION = 1
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


def build_trend_report(source, window: int = 3) -> dict:
    """Build the deterministic trend artifact payload."""
    series = extract_series(source)
    return {
        "schema_version": TREND_REPORT_SCHEMA_VERSION,
        "window": window,
        "series": series,
        "verdicts": {
            dimension: direction_verdict(source, dimension, window)
            for dimension in sorted(DIMENSION_PATHS)
        },
    }


def render_trend_json(source, window: int = 3) -> str:
    """Render a byte-stable JSON trend artifact."""
    return json.dumps(build_trend_report(source, window), sort_keys=True, indent=2) + "\n"


def render_trend_summary(source, window: int = 3) -> str:
    """Render a concise, deterministic text summary."""
    report = build_trend_report(source, window)
    lines = [f"trend_window={window}"]
    for dimension in sorted(DIMENSION_PATHS):
        rows = report["series"][dimension]
        latest = rows[-1]["value"] if rows else UNMEASURED
        lines.append(
            f"{dimension}: verdict={report['verdicts'][dimension]} latest={latest}"
        )
    return "\n".join(lines) + "\n"


def emit_trend_artifacts(source, json_path, summary_path, window: int = 3) -> dict:
    """Write JSON and text trend artifacts and return their rendered bytes."""
    json_text = render_trend_json(source, window)
    summary_text = render_trend_summary(source, window)
    Path(json_path).write_text(json_text, encoding="utf-8")
    Path(summary_path).write_text(summary_text, encoding="utf-8")
    return {"json": json_text, "summary": summary_text}


# The aggregate's default home, mirroring run_store.OUTPUT_DIR_NAME (".qb/audit");
# the run path persists telemetry-aggregate.json there once per run.
_DEFAULT_AGGREGATE_SUBPATH = Path(".qb") / "audit" / _aggregate.AGGREGATE_TELEMETRY_FILENAME
NO_SERIES_MESSAGE = "no telemetry series yet"


def main(argv=None) -> int:
    """CLI: render the multi-run telemetry trend report from an aggregate series.

    Reads the store-local ``telemetry-aggregate.json`` (populated once per run by
    the audit path) and prints a per-dimension improving/regressing/flat summary,
    or the structured JSON report under ``--json``. An absent or empty series is a
    documented, non-error outcome (exit 0 with a clear message on stderr): a cold
    start has nothing to trend yet, which must never read as a failure.
    """
    parser = argparse.ArgumentParser(
        description="Render the multi-run telemetry trend report from an aggregate series.")
    parser.add_argument("--aggregate", default=None,
                        help="Path to telemetry-aggregate.json. "
                             "Default: <root>/.qb/audit/telemetry-aggregate.json.")
    parser.add_argument("--root", default=".",
                        help="Repository root used to locate the default aggregate. Default: cwd.")
    parser.add_argument("--window", type=int, default=3,
                        help="Trailing runs per dimension to classify (>= 2). Default: 3.")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="Emit the structured JSON trend report instead of the text summary.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.window < 2:
        parser.error("--window must be at least 2")

    path = (Path(args.aggregate) if args.aggregate is not None
            else Path(args.root) / _DEFAULT_AGGREGATE_SUBPATH)
    aggregate = _aggregate.read_aggregate(path)
    if not aggregate.get("runs"):
        sys.stderr.write(f"{NO_SERIES_MESSAGE} ({path})\n")
        return 0
    sys.stdout.write(render_trend_json(aggregate, args.window) if args.as_json
                     else render_trend_summary(aggregate, args.window))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
