# Telemetry trends

QB persists one schema-versioned telemetry record per audit run and appends it to a
store-local multi-run series, `.qb/audit/telemetry-aggregate.json` (written by the run
path via `run_store.append_telemetry_aggregate`). The trend surface turns that series
into a per-dimension verdict so a maintainer or CI can see whether the engine is getting
better, worse, or holding steady across runs — without writing a script. The run path
also **persists** the rendered trend read-out per run, so the verdicts are a durable,
diffable artifact on disk rather than only an on-demand `make trends` recomputation.

## Persisted run-store artifacts

The headless run finale writes these fixed-path, schema-versioned, deterministically
rendered artifacts into the run store (`.qb/audit/` by default):

| Artifact | Written by | Schema constant |
|---|---|---|
| `telemetry.json` | `run_store.write_telemetry` (one record per run) | `telemetry.TELEMETRY_SCHEMA_VERSION` |
| `telemetry-aggregate.json` | `run_store.append_telemetry_aggregate` (multi-run series) | `telemetry_aggregate.AGGREGATE_TELEMETRY_SCHEMA_VERSION` |
| `telemetry-trends.json` | `run_store.emit_trend_artifacts` (per-run trend report) | `telemetry_trends.TREND_REPORT_SCHEMA_VERSION` |
| `telemetry-trends.txt` | `run_store.emit_trend_artifacts` (text summary) | — |

`run_store.emit_trend_artifacts` runs right after the aggregate append, so every completed
run leaves a `telemetry-trends.json` report and a `telemetry-trends.txt` summary alongside
the series. A thin series renders `insufficient-data` verdicts rather than erroring — the
same fail-soft cold-start posture as `make trends`. Re-derive the read-out on demand with
`make trends`; the gate of record is `make check`.

## Usage

```
make trends                               # text summary over the default series
python3 shared/scripts/telemetry_trends.py --root .            # equivalent
python3 shared/scripts/telemetry_trends.py --json              # structured JSON report
python3 shared/scripts/telemetry_trends.py --window 5          # last 5 runs per dimension
python3 shared/scripts/telemetry_trends.py --aggregate path/to/telemetry-aggregate.json
```

- `--aggregate PATH` — read this series file directly. Default:
  `<root>/.qb/audit/telemetry-aggregate.json`.
- `--root DIR` — repository root used to locate the default series. Default: cwd.
- `--window N` — trailing runs per dimension to classify (must be `>= 2`). Default: 3.
- `--json` — emit the structured `build_trend_report` payload instead of the summary.

An absent or empty series is a **documented no-op**: the command writes
`no telemetry series yet (<path>)` to stderr and exits `0`. A cold start has nothing to
trend yet, which must never read as a failure (the same fail-soft posture as the rest of
the observability pipeline).

## Dimensions and verdicts

Each dimension is classified by comparing the first and last measured value in the window:

| Dimension | Telemetry path | Better when |
|---|---|---|
| `precision` | `quality.precision_estimate` | higher |
| `fix_safety` | `quality.fix_safety_ok` | higher |
| `latency` | `cost.wall_ms` | lower |
| `cost` | `cost.tokens` | lower |
| `quality` | `quality.false_positive_signals` | lower |

Verdicts: `improving`, `regressing`, `stable`, `insufficient-data` (fewer than two
measured points in the window), and `unmeasured` (no measured points). Unmeasured cost
fields (`UNMEASURED`) are skipped rather than coerced to zero, so "never measured" is never
mistaken for "measured zero".

The rendering is deterministic and byte-stable (`render_trend_json` / `render_trend_summary`),
so the JSON report can be diffed or gated in CI.
