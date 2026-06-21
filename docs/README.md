# QB Engine Contract Docs

This directory holds the authoritative contract documents for QB's audit/harden
engine — one document per guarantee, each the single source of truth for the
engine module(s) named beside it. The root [README](../README.md),
[RUNBOOK](../RUNBOOK.md), and [SECURITY](../SECURITY.md) link here for the
detailed contracts.

| Document | Contract | Authoritative engine module(s) |
|---|---|---|
| [accepted-findings.md](accepted-findings.md) | The committed register of explicitly accepted self-audit findings; fail-closed when absent or empty. | `shared/scripts/accepted_findings.py`, `shared/scripts/production_gate.py` |
| [analyzer-coverage.md](analyzer-coverage.md) | The default offline analyzer registry, the frozen finding categories, and the run-level capability report. | `shared/scripts/audit_runner.py`, `shared/scripts/finding_schema.py` |
| [execution-sandbox.md](execution-sandbox.md) | The external-command process-confinement guarantee, supported controls, and the fail-closed rule. | `shared/scripts/command_safety.py`, `shared/scripts/verification_gate.py` |
| [false-positive-controls.md](false-positive-controls.md) | Deterministic suppression markers and the high/medium/low confidence-band policy. | `shared/scripts/analyzer_core.py`, `shared/scripts/command_safety.py` |
| [live-validation-protocol.md](live-validation-protocol.md) | The A1→A2→A3 autonomy progression, per-run telemetry, the rollback drill, and the precision/fix-safety thresholds. | `shared/scripts/release_gate.py`, `shared/scripts/telemetry.py` |
| [networked-enrichment.md](networked-enrichment.md) | The optional networked-analyzer contract: opt-in registration, the runtime gate, and fail-closed absence. | `shared/scripts/analyzer_interface.py` |
| [precision-harness.md](precision-harness.md) | The labelled precision/recall corpus, the join key, and the `make precision` gate. | `shared/scripts/precision_harness.py`, `tests/fixtures/precision-corpus/` |
| [telemetry-trends.md](telemetry-trends.md) | The per-run telemetry series, the per-dimension improving/regressing/stable trend verdict over a window, and the persisted run-store trend artifacts. | `shared/scripts/telemetry_trends.py`, `shared/scripts/telemetry_aggregate.py`, `shared/scripts/run_store.py` |

Every contract above is enforced by the local gate of record (`make check`); see
[RUNBOOK.md → Gate of record](../RUNBOOK.md#gate-of-record).
