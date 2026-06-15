# Phase 5.1 — Run-State and Evidence Store

## 1. Context

This sub-phase opens Phase 5 (maturity M4), whose parent goal in `Planner-docs/Main-Planning.md` section 6 is "machine-readable, reproducible, cross-reviewed run output consumable by humans and CI." The autopsy (`Planner-docs/Autopsy.md`, finding AUTOPSY-P3-02 and section 10) records that QB today has no run-state store, no evidence/artifact store, and no reversal-handle persistence — only implicit git. Main-Planning section 5 ("Source-of-truth decisions") declares that QB's own run-state and evidence artifacts are the source of execution truth for a run, not external issue trackers and not chat scrollback, mirroring how the planning product already keeps its truth in `Planner-docs/`. By the time Phase 5 starts, Phases 0-4 have produced the autonomy charter, the frozen `Finding` schema, the analyzer suite, the finding-driven fixer with git isolation, and the policy/orchestrator engine. All of those phases produce data that currently evaporates at process exit. This sub-phase plans the persistent home for that data so the reporting and reproducibility work in Phase 5.2 and Phase 5.3 has a stable substrate to read from. It is the storage foundation that turns four ephemeral roles into one auditable run.

## 2. Goal

Define and specify a fixed-name, validator-checked run output directory that persists, for a single audit-and-harden run, three durable record sets: (a) the graded findings inventory keyed by stable finding identifiers; (b) per-fix evidence including the patch, the verification command and its before/after result, and a git reversal handle; and (c) an append-only run log capturing orchestration decisions, policy and budget boundary events, and role transitions. The store must be the authoritative execution truth for the run such that, given only the store, a reader can reconstruct what was found, what was changed, why it was changed, and how to undo it — without consulting chat history or external trackers.

## 3. Description

The problem this sub-phase solves is the absence of a durable execution-truth substrate: every prior phase computes findings, patches, verification outcomes, and policy decisions in memory and then discards them. Without a defined on-disk layout, reporting (5.2) would have to re-run analysis to produce output, and reproducibility (5.3) would be impossible. This work belongs at the head of Phase 5 because both downstream sub-phases read the store rather than recompute; defining the store first prevents the report emitter and the provenance attacher from inventing incompatible private layouts. The store reduces project risk in three concrete ways: it makes every autonomous write recoverable by persisting a reversal handle next to each fix, it makes false-positive triage possible by retaining the evidence that justified each finding, and it makes unattended CI runs auditable after the process has exited. It prepares later phases by giving Phase 6 (headless/CI) a directory whose exit-relevant summary file a pipeline can inspect, and by giving Phase 7 (telemetry) a canonical place from which structured metrics are derived rather than separately instrumented. The directory name follows the established convention from `Planner-docs/` and becomes a validator-checked identifier exactly as the planning artifact names already are.

## 4. Scope

- Specification of the fixed-name run output directory and its required subpaths for findings, per-fix evidence, and the run log.
- A documented record format for the findings file that references the frozen Phase-1 `Finding` schema fields (`id, category, severity, confidence, evidence path:line, rationale, suggested-fix, fix-strategy`).
- A per-fix evidence record contract: patch reference, verification command, before-result, after-result, keep-or-revert decision, and git reversal handle (ref/sha).
- An append-only run-log record contract for orchestration events: role transitions, policy decisions, budget consumption, and stop reasons.
- A retention and overwrite policy describing how a new run relates to a prior run's directory.
- Redaction rules so the store never persists secret values, extending the existing length-bounded secret conventions.
- Registration of the directory name and required files as validator-checked identifiers, mirroring the `Planner-docs/` treatment.

## 5. Out of Scope

- The machine-readable report emitter and SARIF/JSON serialization, which are owned by Phase 5.2.
- Provenance capture, reproducibility replay, and cross-review integration, which are owned by Phase 5.3.
- Telemetry sinks, metric aggregation, and dashboards (Phase 7).
- The headless CLI entry point and pipeline exit-code contract (Phase 6).
- Any change to how analyzers detect findings or how the fixer applies patches; this sub-phase only persists their outputs.
- Database engines, queues, or networked storage; the store is a plain on-disk directory consistent with QB's zero-setup, dependency-light core.
- Auto-commit, push, or PR of the store contents.

## 6. Current Repository Evidence

QB has no persistence layer for a run today; `Planner-docs/Autopsy.md` section 7 states plainly that there is no run-state store and no evidence/artifact store, and section 10 confirms backup/rollback is "only implicit git." The one structurally similar precedent is the validator's terminal output in `shared/scripts/validate_planner_docs.py`: the `finalize` function (around line 537) prints a flat `key=value` stream (`planner_docs_validation=...`, `mode=...`, `root=...`, then sorted metrics, warnings, and errors) to stdout, but this is transient process output, not a persisted store. The graded severity machinery that the findings record will mirror lives in `count_audit_severities` (around line 483) and `extract_audit_status` (around line 466), both currently bound to a planning audit document. The per-fix evidence contract has a prose ancestor in `shared/planners/fourth-planner.md`, whose success-evidence line ("the chosen validation/test command passes; the change is minimal and reversible") describes exactly the fields the evidence record must persist, but that file records nothing to disk. The closest existing fixed-name-directory convention is `Planner-docs/` itself, whose names are enforced across `tests/` and the validator. No `QB-Audit/`-style directory exists anywhere in the repository.

## 7. Planned Work Breakdown

- F5.1-01 — Output directory naming and layout specification
  - Description: Specify the fixed-name run output directory and its required subpaths (a findings record, a per-fix evidence area, a run log, and a run-summary file consumed later by reporting). Confirm the exact top-level name during implementation in coordination with the Phase-0 naming decision; document the rationale for the chosen name.
  - Output: a layout specification section in this sub-plan's downstream design artifact under `shared/` describing every required path and its purpose.
- F5.1-02 — Findings record format
  - Description: Define the on-disk findings record that serializes the frozen `Finding` schema for a whole run, keyed by stable finding id, so reporting can render and CI can consume it without recomputation.
  - Output: a documented findings-record field map referencing the Phase-1 schema, plus example records with synthetic, non-secret data.
- F5.1-03 — Per-fix evidence record contract
  - Description: Define what each applied or attempted fix persists: patch reference, verification command, before-result, after-result, keep/revert decision, and a git reversal handle, so any fix is recoverable and explainable from the store alone.
  - Output: an evidence-record contract with field definitions and a worked keep-case and revert-case example.
- F5.1-04 — Run-log event contract
  - Description: Define an append-only run-log record for orchestration events: role transitions (auditor/fixer/verifier/reviewer), policy decisions, budget consumption, and stop reasons, so a run's control-flow is reconstructable.
  - Output: a run-log event schema with enumerated event types and ordering guarantees.
- F5.1-05 — Retention, overwrite, and redaction rules
  - Description: Define how a new run relates to a prior run directory, and mandate redaction so no secret value is ever persisted into any record.
  - Output: a retention/overwrite policy and a redaction rule set extending the existing secret conventions.
- F5.1-06 — Validator-checked identifier registration plan
  - Description: Specify how the new directory name and required files become validator-checked identifiers, mirroring the `Planner-docs/` treatment, including the sync MAP and test implications.
  - Output: a registration plan naming the validator checks and `tests/` additions required.

## 8. Acceptance Criteria

- The downstream design artifact states the exact fixed-name run output directory and every required subpath, and explains how the name was reconciled with the Phase-0 naming decision.
- The findings record format enumerates each field of the frozen Phase-1 `Finding` schema and shows a synthetic example whose severities use the P0-P3 vocabulary already counted by `count_audit_severities` in `shared/scripts/validate_planner_docs.py`.
- Each per-fix evidence record is shown to carry a patch reference, a verification command, a before/after result pair, a keep/revert decision, and a git reversal handle; a worked revert example demonstrates recoverability from the store alone.
- The run-log contract enumerates orchestration event types and guarantees append-only ordering.
- A redaction rule explicitly forbids persisting secret values and references the length-bounded secret patterns already used by `scan_secrets`.
- Local readiness (the spec validates and the identifiers are registrable) is documented separately from live readiness (an actual run writing the store), and the latter is marked as exercised only once Phases 1-4 emit real data.
- No secret values, tokens, or private endpoints appear in any example record.

## 9. Validation and Test Approach

Document validation: confirm this sub-plan and its downstream `shared/` design artifact carry every required field map and example, verifiable by `python3 shared/scripts/validate_planner_docs.py --strict` once the new identifiers are wired in. Local smoke (proposed): a future fixture run produces a populated store directory whose findings, evidence, and log files are present and parse cleanly; this is exercised after Phase 1-4 deliverables exist. Security validation: re-run the repository secret scan over the populated store to confirm zero secret matches, reusing the `scan_secrets` machinery in `shared/scripts/validate_planner_docs.py` and the `tests/test_no_committed_secrets.py` convention. Artifact validation (proposed): a new test asserts the required store subpaths exist and that each per-fix evidence record contains a reversal handle. CI: once the store identifiers are registered, `make check` exercises the validator and the sync-map completeness guard; live readiness (an unattended run actually writing the store in CI) is deferred to Phase 6.

## 10. Dependencies and Sequencing

This sub-phase depends on the Phase-0 output-directory naming decision and on the Phase-1 frozen `Finding` schema, because the findings record serializes that schema. It depends on the Phase-3 fixer's git-isolation and reversal-handle primitive, since the evidence record persists that handle. It depends on the Phase-4 orchestrator/policy engine for the event vocabulary the run log captures. It blocks Phase 5.2, which reads the store to emit reports, and Phase 5.3, which replays the store for reproducibility. No live credentials, network endpoints, or infrastructure are required; the store is a plain directory. The human decision that must be confirmed before implementation is the final directory name and whether the planning and auditing products share one output tree or two, listed as open question (c) in Main-Planning section 9.

## 11. Risks and Mitigations

- Risk: the store schema diverges from the frozen `Finding` schema, forcing reporting to translate between two shapes. Impact: drift and duplicated definitions. Mitigation: the findings record references Phase-1 fields by name rather than redefining them, and a conformance check fails if a field is renamed.
- Risk: secret values leak into evidence records because before/after results capture raw file content. Impact: secret exposure in a persisted, possibly committed artifact. Mitigation: mandatory redaction before write, plus a post-run secret scan over the store reusing `scan_secrets`.
- Risk: a missing or stale reversal handle leaves an applied fix unrecoverable from the store. Impact: an autonomous write cannot be undone after the process exits. Mitigation: treat the reversal handle as a required field; a fix with no recorded handle is recorded as not-kept.
- Risk: directory-name churn if the Phase-0 decision shifts late. Impact: rework across reporting and reproducibility. Mitigation: centralize the name as a single validator-checked identifier so a rename is one edit plus a sync.
- Risk: store overwrite destroys a prior run's audit trail. Impact: lost history needed for comparison or dispute. Mitigation: an explicit retention/overwrite policy that a new run never silently clobbers a prior run without an opt-in.

## 12. Desired End State

A reader of the repository finds a documented, fixed-name run output directory whose name and required files are validator-checked identifiers, just as `Planner-docs/` names are today. The directory holds a findings record that serializes the frozen `Finding` schema, a per-fix evidence area where each fix carries its patch, verification command, before/after result, keep/revert decision, and a git reversal handle, and an append-only run log of orchestration events. Redaction guarantees no secret value is ever persisted, and a post-run secret scan over the store is clean. Given only this directory, an implementer or auditor can reconstruct what was found, what changed, why, and how to revert it, with no reliance on chat scrollback or external trackers.

## 13. Transition Criteria to the Next Sub-Phase

The findings-record, per-fix evidence, and run-log contracts must be written down, internally consistent, and free of contradictions with the frozen `Finding` schema. The directory name and required files must be registered as validator-checked identifiers and pass `python3 shared/scripts/validate_planner_docs.py --strict`. The redaction rule and a clean store secret scan must be demonstrated on synthetic data. The reversal-handle field must be confirmed mandatory. Only once the store contract is stable should Phase 5.2 begin, because the report emitter must read this store rather than recompute analysis; report serialization must not start before the store layout is final.
