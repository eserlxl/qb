# Phase 7.1 — Telemetry and Quality Metrics

## 1. Context

This sub-phase opens parent Phase 7 (Production Hardening, Observability and Self-Audit, maturity M5 to M7), whose goal in `Planner-docs/Main-Planning.md` section 6 is to make unattended operation safe, observable, and recoverable at scale. Observability is the precondition for everything else in this phase: backup drills (7.2), least-privilege enforcement (7.3), and the self-audit production gate (7.4) all need measured signals before they can assert anything. The autopsy (`Planner-docs/Autopsy.md` section 10) records the blunt current reality: "Observability / logging / metrics / tracing: none" and "Cost / latency / quality signals: none captured; no budget model." Main-Planning section 4 names the exact signal set required: findings by severity, fixes applied/reverted, false-positive signals, latency, and token/compute cost. This sub-phase exists because by the end of Phase 6 the engine runs end to end across hosts and headless CI, but every run is effectively blind — no run leaves a structured, queryable record of what it found, what it changed, and what it cost. The single seed already present is the in-memory `state.metrics` dict inside `shared/scripts/validate_planner_docs.py` (it already stores `audit_status` and `p0_findings`..`p3_findings` counts in `validate_step4_readiness`), but those counters live only for the duration of one process and are never persisted or emitted. This sub-phase turns that ephemeral counter habit into a durable, redacted, schema-versioned telemetry record.

## 2. Goal

Define a persistent, schema-versioned, redact-by-default telemetry record emitted once per QB run that captures findings-by-severity, fixes-applied versus fixes-reverted, false-positive signals, wall-clock latency, and token/compute cost — and define the precision and fix-safety thresholds ("what good looks like") that this telemetry must report before any later sub-phase is permitted to raise the operating autonomy level from A1 toward A2 or A3.

## 3. Description

The work here is to convert measurement from an afterthought into a first-class output of every audit and harden run. Concretely it specifies a telemetry record format (a versioned JSON object written under the fixed-name output directory established in Phase 0, alongside the findings file and run log) and a small accumulator that the orchestrator populates as a run proceeds. The record must distinguish detection-time metrics (count of findings per category and per P0-P3 severity, per-analyzer counts, confidence histogram) from action-time metrics (fixes attempted, fixes kept after verification, fixes auto-reverted, fixes blocked by policy) and from cost metrics (wall-clock duration per stage, iteration count, and token/compute consumption where the host exposes it). It also formalizes a false-positive feedback channel: when a fix is reverted because its verification failed, or when a human marks a finding as not-a-defect, that signal is recorded so precision can be estimated over time. This belongs at the start of Phase 7 because the release gates in 7.2 and the production gate in 7.4 are defined in terms of these numbers; without the record there is nothing to gate on. It reduces risk by replacing subjective trust with a reproducible measurement, and it prepares later phases by giving the autonomy-raising decision a quantitative basis (a documented precision floor) instead of a judgment call.

## 4. Scope

- Telemetry record schema: a versioned, host-neutral JSON shape defined as `shared/` IP, with field names, types, and a `schema_version`.
- Metric taxonomy: detection metrics (findings by category/severity/analyzer, confidence histogram), action metrics (fixes attempted/kept/reverted/blocked), and cost metrics (per-stage latency, iteration count, token/compute where available).
- False-positive signal capture: how a reverted fix or a human not-a-defect mark is recorded against the originating finding.
- The "good" definition: a documented precision target and a fix-safety target (every kept fix keeps its verification command green), expressed as numeric thresholds.
- The precision gate contract: the rule that links measured precision to the maximum permitted autonomy level, consumed by Phase 7.2 release gates and Phase 4 policy.
- Redaction rules for telemetry: never write secret values, finding evidence is stored as path:line references, not raw matched text where the match is a candidate secret.
- A telemetry-conformance test mirroring the existing `Finding`-schema test convention in `tests/`.

## 5. Out of Scope

- Live dashboards, web UIs, time-series databases, or any external metrics backend (the record is a local file, not a service).
- Network egress of telemetry to a remote collector or any opt-in analytics upload.
- The backup/rollback drills and release-gate enforcement themselves (Phase 7.2 owns those; this sub-phase only defines the numbers they consume).
- The kill-switch, runbook, and self-audit dogfood run (Phase 7.4).
- Changing how findings are detected or how fixes are applied — this measures the existing pipeline, it does not alter analyzer or fixer behavior.
- Cross-host launch wiring for telemetry (Phase 6 already established the shared output convention; this only adds one more artifact under it).

## 6. Current Repository Evidence

The only existing measurement primitive is the in-memory `state.metrics` dictionary in `shared/scripts/validate_planner_docs.py`; `validate_step4_readiness` writes `audit_status` and the per-severity finding counts into it, and `finalize` reads them, but nothing is ever persisted to disk. There is no JSON emitter, no run-record file, and no cost or latency capture anywhere in the tree. The `Makefile` exposes only `sync`, `check`, `test`, and `export-sanitized`; none emit metrics. CI (`.github/workflows/validate.yml`) runs a single `make check` step and surfaces only pass/fail. The autopsy (`Planner-docs/Autopsy.md` section 10) explicitly states observability, cost, and latency signals are all absent, and section 8 confirms there is no eval harness to measure precision. The severity vocabulary P0-P3 already exists (`count_audit_severities`, `SECRET_PATTERNS` in the validator) and should be reused verbatim so telemetry severities match audit severities exactly.

## 7. Planned Work Breakdown

- F7.1-01 — Telemetry record schema definition
  - Description: Specify the versioned JSON telemetry record (schema_version, run id, autonomy level, host, start/end timestamps, and three metric groups) as a host-neutral artifact under `shared/`, reusing the P0-P3 severity vocabulary already in the validator.
  - Output: a schema document and a frozen field list ready for a conformance test.
- F7.1-02 — Metric taxonomy and accumulator contract
  - Description: Define each metric (detection, action, cost), how the orchestrator accumulates it across stages, and the units (counts, milliseconds, iterations, tokens), generalizing the existing `state.metrics` counter habit into a persisted accumulator.
  - Output: a metric catalog with names, units, and accumulation rules.
- F7.1-03 — False-positive signal channel
  - Description: Specify how a verification-failed auto-revert and a human not-a-defect mark are attributed back to a finding id so precision can be estimated.
  - Output: a documented feedback-record format keyed by finding id.
- F7.1-04 — "What good looks like" thresholds
  - Description: Set the numeric precision floor and the fix-safety target (kept fixes keep verification green) and document the rationale for each value.
  - Output: a thresholds table with target values and justification.
- F7.1-05 — Precision gate contract
  - Description: Define the rule mapping measured precision and fix-safety to the maximum permitted autonomy level, to be enforced by Phase 7.2 and Phase 4 policy.
  - Output: a gate-contract specification referencing the thresholds from F7.1-04.
- F7.1-06 — Telemetry redaction rules and conformance test design
  - Description: Specify redaction (no secret values; candidate-secret findings stored as path:line only) and design a telemetry-conformance test in the style of the existing `tests/` modules.
  - Output: redaction rule list plus a test design note.

## 8. Acceptance Criteria

- `Planner-docs/Phase-7-Plans/Phase7.1-telemetry-and-metrics.md` defines a versioned telemetry record with explicit field names, types, and a `schema_version` field.
- The metric taxonomy enumerates detection, action, and cost metrics with units, and each metric is traceable to a Main-Planning section 4 requirement (findings, fixes applied/reverted, false-positive, latency, cost).
- A numeric precision floor and a fix-safety target are stated as concrete values with rationale, not as vague aspirations.
- The precision gate contract states, in verifiable terms, which measured outcome permits which maximum autonomy level.
- Redaction rules guarantee that no secret value can appear in a telemetry record, expressed precisely enough to test.
- A telemetry-conformance test is designed following the convention of existing modules under `tests/` (for example the spec/validator contract test), and local readiness (file written, schema frozen) is distinguished from live readiness (real runs emitting records on each host).
- No secret values, tokens, or credentials appear anywhere in the plan.

## 9. Validation and Test Approach

Document validation: confirm via the bundled checker `python3 shared/scripts/validate_planner_docs.py` that this sub-plan carries all 13 required headings and no placeholder tokens, and run a `--strict` pass to promote warnings to failures. Local smoke (proposed): once the telemetry emitter exists, a proposed `make telemetry-selfcheck` target would run a no-op audit over a fixture and assert a schema-valid record is produced and contains zero secret matches. Schema validation: the proposed telemetry-conformance test asserts that an emitted record matches the frozen schema and that `schema_version` is present, mirroring how `tests/test_spec_validator_contract.py` enforces a contract today. Security validation: a redaction assertion runs the existing `SECRET_PATTERNS` over a sample telemetry record and requires zero matches; `python3 -m unittest discover -s tests` and the repo-wide secret-scan test (`tests/test_no_committed_secrets.py`) remain the gate. CI: `make check` continues to gate merges and would be extended to run the telemetry-conformance test. Live readiness is explicitly deferred until real runs on each host emit records — this sub-phase only freezes the format and thresholds.

## 10. Dependencies and Sequencing

Depends on Phase 0 (the fixed-name output directory convention, since the telemetry record is written there), Phase 1 (the `Finding` schema and its P0-P3 severities, reused verbatim), Phase 3 (the fixer's kept/reverted outcomes are an action-metric source), Phase 4 (policy-blocked actions are an action metric), and Phase 6 (the multi-host plus headless surface that will actually run and emit). Required decisions: the precise numeric precision floor and the units used for compute/token cost on hosts that do not expose token counts. No live credentials, infrastructure, or human approvals block writing this plan; raising autonomy based on the precision gate is a human-on-the-loop decision documented here and enforced in 7.2. This sub-phase blocks 7.2 (release gates need the metric definitions) and 7.4 (the production gate reports these numbers).

## 11. Risks and Mitigations

- Risk: telemetry leaks secrets by recording raw matched text from candidate-secret findings. Impact: a metrics file becomes a credential exfiltration path, undermining the tool's core safety promise. Mitigation: store candidate-secret findings as path:line references only, run `SECRET_PATTERNS` over every emitted record as a conformance assertion, and fail closed if any match is found.
- Risk: metrics are defined but never wired in, so the precision gate has no data and autonomy is raised on a hunch. Impact: A2/A3 enabled without evidence, exactly the confidently-wrong-at-scale failure the master plan warns against. Mitigation: make the conformance test require a non-trivial populated record from a fixture run before the gate contract is considered satisfied.
- Risk: cost/token metrics are unavailable on some hosts, making cross-host comparison meaningless. Impact: the budget and precision gates behave inconsistently across Claude Code, Cursor, and Codex. Mitigation: define cost as best-effort with an explicit "unmeasured" sentinel and rely on wall-clock latency and iteration count as the host-independent fallback signals.
- Risk: schema churn breaks downstream consumers in 7.2 and 7.4. Impact: release gates parse stale fields and silently mis-gate. Mitigation: version the record with `schema_version` and require the conformance test to assert the version, so a format change is a visible, gated event.

## 12. Desired End State

QB emits exactly one persisted, schema-versioned, redacted telemetry record per run, written under the established fixed-name output directory, capturing findings by severity, fixes applied versus reverted, false-positive signals, per-stage latency, iteration count, and best-effort token/compute cost. A documented numeric precision floor and fix-safety target define "good," and a precision gate contract states which measured outcomes permit which maximum autonomy level. A telemetry-conformance test is specified in the existing `tests/` style and a redaction assertion guarantees no secret can appear in a record. Downstream sub-phases (7.2 release gates, 7.4 production gate) have a concrete, queryable signal source instead of guesswork.

## 13. Transition Criteria to the Next Sub-Phase

Before starting Phase 7.2, the telemetry record schema and `schema_version` must be frozen and free of contradictions, the metric taxonomy must map every required signal from Main-Planning section 4, the precision floor and fix-safety target must be stated as concrete numeric values, and the precision gate contract must be written in terms those numbers can satisfy. The redaction rules must be precise enough that the conformance test can assert zero secret matches. No autonomy level may be raised on the strength of this plan alone — that decision is gated in 7.2 — and the document checker (`python3 shared/scripts/validate_planner_docs.py`, including a `--strict` pass) must report this sub-plan as clean.
