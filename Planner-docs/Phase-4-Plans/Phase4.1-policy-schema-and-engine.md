# Phase 4.1 — Policy Schema and Engine

## 1. Context

Phase 4 of `Planner-docs/Main-Planning.md` (row 4 of the master roadmap, maturity M3->M4) replaces QB's per-gate human clicks with a policy-bounded, fail-closed orchestrator. This first sub-phase delivers the decision substrate every other Phase 4 sub-phase consumes: a frozen declarative policy schema plus the engine that reads it and answers a single question for each candidate action — "is this allowed, right now, under this policy?". It directly realizes the highest-leverage half of `AUTOPSY-P1-01` (no policy / autonomy / budget engine; today safety is prompt-only via `validate_step4_readiness`). It depends on the Phase 0 autonomy charter for the A0-A3 concept and naming, on the frozen `Finding` schema from Phase 1 (the engine reasons over `severity`, `confidence`, `category`, `evidence path`), and on the Phase 3 fixer contract whose write attempts the engine must now authorize. The policy schema becomes a new canonical artifact under `shared/`, materialized into every platform by `scripts/sync.sh`, mirroring how the planner specs and validator are already the single source of truth.

## 2. Goal

Produce a frozen, versioned, declarative policy schema and a host-neutral policy engine that deterministically decides, for any proposed audit or fix action, whether it is permitted — keyed on auto-fixable category and severity sets, a minimum confidence threshold per category, write-path allowlist globs, and explicit commit/push/PR permission flags — and that defaults to the most restrictive interpretation (report-only) whenever the policy is missing, unparseable, ambiguous, or references an unknown field. The goal is achieved when a single policy document plus a single engine entry point can be handed any candidate action and return an auditable allow/deny verdict with a machine-readable reason code.

## 3. Description

This sub-phase writes down the contract that turns "autonomous" from a vibe into a bounded function of declared rules. The core problem it solves is that QB currently encodes permission as English prose in planner specs (`shared/planners/fourth-planner.md` says "no commit, push, PR ... unless the user explicitly asks") and as one hard-coded readiness check in the validator — neither is a reusable, machine-evaluable policy. The work freezes a declarative schema with a small, closed set of keys (autonomy level, per-category auto-fix eligibility, per-category minimum confidence, write-path allowlist globs, deny globs, commit/push/PR permission booleans, and a policy schema version) and builds an engine whose only job is evaluation, not execution. It belongs at the start of Phase 4 because the autonomy-level enforcer (4.2), the budget/kill-switch layer (4.3), and the role separation gates (4.4) all need to call into one authoritative decision function rather than re-deriving permission logic independently. It reduces project risk by making every permission decision deterministic, testable, and explainable, and it prepares later phases by giving the orchestrator a stable engine API to compose budgets, levels, and cross-review verdicts on top of.

### 3.1 Closed-key schema principle

The schema deliberately enumerates a fixed key set; any unrecognized top-level key is a hard parse error rather than an ignored extra, so a typo'd permission can never silently widen authority. New capabilities require a deliberate schema-version bump, not an ad-hoc field.

### 3.2 Pure-evaluation engine principle

The engine never performs I/O against the target tree, never runs a fix, and never commits. It is a pure function from (policy, candidate action descriptor) to (verdict, reason code). This keeps it trivially testable and prevents the decision layer from acquiring side effects.

## 4. Scope

- The declarative policy schema definition as a new canonical artifact under `shared/` (field list, types, allowed value sets, fail-closed defaults, schema version field).
- A policy reference/example document showing a conservative default policy and an explicit annotated example.
- The host-neutral policy engine specification: load -> parse -> validate-shape -> evaluate(action) -> verdict, with reason codes.
- The closed-key validation rule (unknown key = parse error) and the missing-file behavior (synthesize the most restrictive policy).
- The per-category minimum-confidence threshold model and per-category/severity auto-fix eligibility sets.
- The write-path allowlist/denylist glob model and its intersection-with-deny precedence rule.
- A policy-shape conformance test plan and a fail-closed-default test plan aligned with the `tests/` conventions.
- Wiring the new `shared/` artifacts into the `scripts/sync.sh` `MAP` and the sync-map-completeness guard.

## 5. Out of Scope

- Runtime enforcement of autonomy levels A0-A3 against actual writes (that is Phase 4.2; this sub-phase only defines the level field and its allowed values).
- Budget accounting, wall-time/token metering, and the kill-switch mechanism (Phase 4.3).
- Role separation and cross-review verdict gating (Phase 4.4).
- Any change to the existing `Planner-docs/` planning workflow gate (`validate_step4_readiness`); that path must remain untouched and non-regressed.
- Building or modifying analyzers (Phase 2) or the fixer runtime (Phase 3).
- Networked policy distribution, remote policy servers, or signed-policy verification.
- JSON/SARIF report emission and telemetry (Phases 5 and 7).

## 6. Current Repository Evidence

The only permission logic that exists today is `validate_step4_readiness` in `shared/scripts/validate_planner_docs.py` (lines 491-516): it reads `Sub-Planning-Audit.md`, blocks on `BLOCKED` status, and blocks when any P0 or P1 finding is present — a single hard-coded gate bound to planning documents, not a configurable policy. `count_audit_severities` (lines 483-488) and `extract_audit_status` (lines 466-480) show the existing P0-P3 vocabulary and status parsing that the new schema's severity model should stay compatible with. `finalize` (lines 537-555) demonstrates the existing fail-closed habit: in `--strict` mode warnings are promoted to errors, and a non-empty error list yields exit code 1. There is no policy file format anywhere in the repo, no configurable threshold, and no write-path allowlist — confirmed by `Planner-docs/Autopsy.md` section 9 and finding `AUTOPSY-P1-01`. The sync contract that the new artifacts must join is in `scripts/sync.sh`: the `MAP` array (from line 59) and the unmapped-source completeness guard (from line 133) mean any new `shared/` file must be wired in or `--check` fails. The `tests/` directory already contains `test_spec_validator_contract.py` and `test_sync_map_completeness.py`, the conventions the new conformance tests should follow.

## 7. Planned Work Breakdown

- F4.1-01 — Freeze the declarative policy schema
  - Description: Enumerate the closed key set (schema version, autonomy level, auto-fixable category set, per-category severity eligibility, per-category minimum confidence, write allowlist globs, write deny globs, commit/push/PR permission booleans), their types, and allowed value ranges; specify that unknown keys are a parse error.
  - Output: a new canonical schema artifact under `shared/` plus its field-by-field documentation.
- F4.1-02 — Define fail-closed defaults
  - Description: Specify the synthesized policy used when the file is absent/unparseable (autonomy A0, empty auto-fix set, confidence threshold at maximum, empty write allowlist, all commit/push/PR booleans false) and the precedence rule that deny globs always override allow globs.
  - Output: a "default policy" section in the schema doc and a worked annotated example policy.
- F4.1-03 — Specify the policy engine evaluation contract
  - Description: Define the pure-function API load(path) -> policy, evaluate(policy, action_descriptor) -> (verdict, reason_code), and the action descriptor shape (category, severity, confidence, target path, action kind).
  - Output: an engine specification section with the verdict reason-code catalog.
- F4.1-04 — Define the reason-code catalog
  - Description: Enumerate stable machine-readable deny reasons (for example category-not-auto-fixable, confidence-below-threshold, path-outside-allowlist, path-in-denylist, commit-not-permitted, policy-parse-error, unknown-key) so the orchestrator and reports can act on codes, not prose.
  - Output: a reason-code table with one-line semantics for each code.
- F4.1-05 — Plan the conformance and fail-closed test surface
  - Description: Specify a policy-shape conformance test (valid policies accepted, malformed/unknown-key policies rejected) and a fail-closed test (missing policy yields A0/deny-all), following `tests/` style.
  - Output: a test plan section naming proposed test modules and the assertions each must make.
- F4.1-06 — Wire artifacts into the sync contract
  - Description: Identify the exact `MAP` entries to add to `scripts/sync.sh` for the new schema and reference artifacts so byte-for-byte materialization reaches all three platforms and the completeness guard passes.
  - Output: a sync-wiring note listing each new shared path and its three platform destinations.

## 8. Acceptance Criteria

- A frozen policy schema artifact exists under `shared/` enumerating exactly the closed key set, each key's type, allowed values, and its fail-closed default value.
- The schema document states explicitly that an unknown or misspelled top-level key is rejected as a parse error, never silently ignored.
- A worked example policy and a synthesized default policy are both present and visibly distinct, with the default being report-only (A0) and deny-all-writes.
- The engine specification defines a pure evaluation function with no side effects and a complete, enumerated reason-code catalog covering every deny path.
- The plan distinguishes local readiness (schema and engine spec frozen, conformance test green offline) from live readiness (the engine actually invoked inside an unattended run, which is owned by Phase 4.2 onward).
- The plan names the precise `scripts/sync.sh` `MAP` additions required so `bash scripts/sync.sh --check` would pass after implementation.
- No secret values, tokens, or credentials appear in any schema, example policy, or plan text.

## 9. Validation and Test Approach

- Document validation: run `python3 shared/scripts/validate_planner_docs.py --root . --mode step2` and `--strict` to confirm this sub-plan's structure and absence of placeholder tokens.
- Local smoke (proposed, post-implementation): a proposed `tests/test_policy_schema.py` asserting that the example policy parses, the default policy is deny-all/A0, and a policy with an unknown key is rejected.
- Local smoke (proposed): a proposed engine unit test feeding crafted action descriptors and asserting the expected verdict and reason code for each deny path.
- CI: extend `make check` (currently runs `scripts/sync.sh --check`, three `validate.sh`, then `python3 -m unittest discover -s tests`) so the new conformance test runs in CI via `.github/workflows/validate.yml`.
- Security validation: confirm no example policy embeds a real credential and that `scan_secrets` over the planner tree stays clean.
- Live readiness: explicitly deferred — the engine's behavior inside a real unattended run is validated in later Phase 4 sub-phases, not here.

## 10. Dependencies and Sequencing

- Requires the Phase 0 autonomy charter for the A0-A3 vocabulary and naming, and the Phase 1 frozen `Finding` schema for the severity/confidence/category fields the engine reasons over.
- Should land before Phase 4.2, 4.3, and 4.4, all of which call the engine's evaluation function.
- Requires a human decision (carried from Main-Planning section 9 open question (a)) on the default autonomy level and whether commit/push/PR is ever permitted by default; until decided, the plan assumes the most conservative defaults.
- Requires no live credentials, no network, and no external infrastructure — the schema and engine are offline and dependency-free, preserving QB's zero-setup property.

## 11. Risks and Mitigations

- Risk: an over-permissive default lets an unattended run write before the level enforcer (4.2) exists. Impact: premature writes outside policy. Mitigation: the synthesized default is A0 report-only with an empty auto-fix set and deny-all writes, so even a half-built engine grants no write authority.
- Risk: schema sprawl, where ad-hoc keys accrete and permission logic becomes unauditable. Impact: silent authority creep and untestable decisions. Mitigation: a closed key set with parse-error-on-unknown-key and a mandatory schema-version bump for any new capability.
- Risk: divergence between the engine's severity vocabulary and the validator's existing P0-P3 model. Impact: inconsistent gating between the planning path and the audit path. Mitigation: reuse the exact P0-P3 vocabulary already present in `count_audit_severities` and assert compatibility in the conformance test.
- Risk: the new shared artifacts are forgotten in `scripts/sync.sh`, breaking `make check`. Impact: CI failure and cross-host drift. Mitigation: F4.1-06 names the exact `MAP` entries and the sync-map-completeness test enforces it.

## 12. Desired End State

A single canonical policy schema lives under `shared/`, is synced byte-for-byte to all three platforms, and is accompanied by a conservative default policy and a worked example. A host-neutral, side-effect-free policy engine specification defines one evaluation function that any orchestrator component can call to obtain a deterministic allow/deny verdict plus a stable reason code, with the most restrictive interpretation applied to every ambiguity. Conformance and fail-closed tests are specified (and, post-implementation, green under `make check`), the planning-product gate remains untouched, and no live writes are yet authorized — that authority is composed on top of this engine in the following sub-phases.

## 13. Transition Criteria to the Next Sub-Phase

- The policy schema is frozen with a recorded schema version and a closed, documented key set, free of internal contradictions.
- The synthesized default policy is provably the most restrictive (A0, deny-all writes, empty auto-fix set) and the example policy parses cleanly.
- The engine evaluation contract and complete reason-code catalog are specified and reviewed.
- The conformance and fail-closed test plan is written and the sync `MAP` additions are identified, so `bash scripts/sync.sh --check` and `make check` would pass after implementation.
- Autonomy-level runtime enforcement remains explicitly unimplemented and is handed to Phase 4.2 with the engine API as its stable dependency.
