# Phase 1.4 — Audit Engine Runner and Output Convention

## 1. Context

This sub-phase completes Phase 1 by assembling the pieces into a working audit engine. The parent goal in `Planner-docs/Main-Planning.md` §6 is satisfied only when QB "can run read-only analyzers over an arbitrary repository and emit graded, evidence-backed findings," and the phase's acceptance signals demand a "deterministic findings output." Main-Planning §5 also requires a fixed-name output directory "e.g. `QB-Audit/` alongside the established `Planner-docs/` convention," whose names "become validator-checked identifiers." The autopsy reinforces this in AUTOPSY-P3-02 (no machine-readable output or run-state store) and in §13's Step-2 guidance to design the output-directory convention so observability is built in from the first run. This sub-phase is fourth and last in Phase 1: it depends on the frozen schema (1.1), the analyzer interface and registry (1.2), and the refactored/reused secret-hygiene analyzer (1.3), and it produces the artifact every later phase consumes.

## 2. Goal

Define the audit runner that enumerates the registered read-only analyzers, executes them over an arbitrary repository root, aggregates their Findings into a single deterministically ordered result, and writes that result to a fixed-name output directory whose names are registered as validator-checked identifiers — mirroring how `Planner-docs/` names are enforced today. The outcome is a reproducible, offline-by-default audit pass: pointed at a repository, it produces the same graded, evidence-backed findings file every time, with a stable ordering and a fixed output location that the validator and CI can check by name.

## 3. Description

The runner is the control-plane assembly that turns three contracts into one observable behavior. It reads the analyzer registry from Phase 1.2 in deterministic order, invokes each analyzer with the repository root and configuration, collects each analyzer's list of Phase 1.1 Findings, merges them, applies a total ordering so two runs over an unchanged repository are byte-identical, and persists the merged findings under a fixed-name output directory. Determinism is the headline property because Main-Planning §6 names it as an acceptance signal and because every downstream consumer — the Phase 3 fixer selecting findings to repair, the Phase 4 policy engine gating on severity/confidence, the Phase 5 reporter — depends on a stable, diffable input. The output-directory convention is the second deliverable: choosing the fixed name (for example `QB-Audit/`) and registering it as a validator-checked identifier extends the exact pattern that already protects `Planner-docs/` through `ValidationState.planner_docs` and the `FOLDER_RE`/`SUBPLAN_RE` identifier checks, so the audit tree gains the same naming guarantees the planning tree has. The runner stays offline by default, refusing to invoke any analyzer that declared itself `networked` unless networking is explicitly enabled, preserving the zero-setup promise.

## 4. Scope

- A runner specification under `shared/` that enumerates registered analyzers and executes them over a repository root.
- Aggregation of per-analyzer Findings into one collection with a defined, total, deterministic ordering rule.
- The fixed-name output-directory convention (working name `QB-Audit/`) and the set of fixed file/sub-path names within it.
- Registration of those names as validator-checked identifiers, mirroring the `Planner-docs/` identifier checks.
- The offline-by-default execution rule: skip or refuse `networked` analyzers unless networking is explicitly enabled, recording the decision.
- A run-summary record (counts by severity/category, analyzers run/skipped) emitted alongside the findings file.
- A runner test asserting determinism (stable output across two runs) and correct identifier-name enforcement.

## 5. Out of Scope

- The Finding schema (Phase 1.1), the analyzer interface/registry (Phase 1.2), and the validator extraction (Phase 1.3).
- Authoring additional analyzers beyond the trivial reference analyzer and the reused secret-hygiene analyzer (Phase 2).
- Any write-capable behavior on the audited repository: the runner only reads the target and writes its own output directory (the fixer is Phase 3).
- Autonomy levels, policy gating, thresholds, and budgets that consume the findings (Phase 4).
- JSON/SARIF rendering, provenance, and cross-review of the output (Phase 5).
- The headless CLI entry point and pipeline exit-code contract for CI (Phase 6).
- Telemetry beyond the basic run-summary counts (Phase 7).

## 6. Current Repository Evidence

No runner, no audit output directory, and no run-state store exist; AUTOPSY-P3-02 confirms the absence of any `QB-Audit/`-style output dir or evidence store. The pattern to mirror is, however, fully built for the planning side: `ValidationState.planner_docs` (lines 156-158 of `shared/scripts/validate_planner_docs.py`) hard-names `Planner-docs/`, and `FOLDER_RE`/`SUBPLAN_RE` (lines 97-98) plus `collect_phase_folders` (lines 224 onward) enforce that tree's identifiers — the exact mechanism this sub-phase replicates for the audit tree. The runner's "enumerate units and aggregate results" shape is foreshadowed by `main` in the validator (lines 571-587), which dispatches by mode, runs `scan_secrets`, and calls `finalize` to print sorted, deterministic output; `finalize` (lines 537-555) already sorts metrics, warnings, and errors before printing, demonstrating the project's existing commitment to deterministic, ordered output. The `Makefile` `check` target and `.github/workflows/validate.yml` show where a runner-output identifier check would be wired so CI enforces the new names. Current repository evidence for an arbitrary-repo runner is otherwise limited to these planning-side precedents.

## 7. Planned Work Breakdown

- F1.4-01 — Runner execution model
  - Description: Specify how the runner enumerates the Phase 1.2 registry in deterministic order, invokes each analyzer with the repository root and config, and collects its Findings, including how an analyzer failure is recorded without aborting the whole run.
  - Output: a runner-execution specification under `shared/`.
- F1.4-02 — Deterministic aggregation and ordering
  - Description: Define the total ordering applied to merged Findings (for example by severity, then category, then evidence location, then id) so two runs over an unchanged repository produce byte-identical output.
  - Output: an ordering rule with a worked example showing two analyzers' findings merged.
- F1.4-03 — Output-directory convention
  - Description: Choose the fixed output-directory name (working name `QB-Audit/`) and the fixed file/sub-path names within it for the findings file and run summary; the precise filenames to be confirmed during implementation.
  - Output: an output-convention section naming the directory and its fixed contents.
- F1.4-04 — Validator-checked identifiers
  - Description: Register the chosen output names as validator-checked identifiers, mirroring the `Planner-docs/` `FOLDER_RE`/`SUBPLAN_RE` approach, so a misnamed audit tree fails validation by name.
  - Output: an identifier-registration specification referencing the planning-side precedent.
- F1.4-05 — Offline-by-default enforcement
  - Description: Specify that the runner refuses to invoke any analyzer declaring `networked` unless networking is explicitly enabled, and records each skip with a reason in the run summary.
  - Output: an offline-default rule and the recorded-skip format.
- F1.4-06 — Determinism and naming test
  - Description: Author a runner test that runs twice over a fixed input and asserts identical output, and that asserts the output-name identifier check rejects a misnamed tree.
  - Output: a test design covering reproducibility and identifier enforcement.

## 8. Acceptance Criteria

- A runner specification under `shared/` enumerates the registered analyzers, executes them over a given repository root, and aggregates their Findings into one collection.
- Two runs of the runner over the same unchanged repository produce byte-identical findings output, proven by a determinism test that diffs the two runs.
- The total ordering rule is documented and applied so finding order does not depend on analyzer discovery timing.
- The fixed-name output directory (working name `QB-Audit/`) and its fixed file names are defined, and those names are registered as validator-checked identifiers analogous to the `Planner-docs/` checks.
- The runner is offline by default: an analyzer declared `networked` is not invoked unless networking is explicitly enabled, and each such skip is recorded with a reason in the run summary.
- The runner only reads the audited repository and writes solely within its own fixed output directory; the audited working tree is unchanged after a run.
- No secret value is written into the findings file or run summary; secret-hygiene findings carry redacted `path:line` evidence only.

## 9. Validation and Test Approach

For document validation of this runner sub-plan, `python3 shared/scripts/validate_planner_docs.py --root . --mode step2 --strict` must report a pass. Determinism validation (proposed): a `tests/test_audit_runner.py` module under `python3 -m unittest discover -s tests` that runs the runner twice over a fixed input (the QB repository or a small fixture) and asserts byte-identical output, plus asserts the identifier check rejects a misnamed output tree. Local smoke: run the runner over the QB repository itself and confirm it produces a graded, deterministically ordered findings file in the fixed output directory containing at least the secret-hygiene analyzer's findings, then `make check` to confirm no regression. CI: `.github/workflows/validate.yml` runs `make check` on every push to `main` and PR, gating the runner and identifier checks. Security validation: assert the audited tree is byte-unchanged after a run and that the findings file contains no secret values. There is no live readiness because the default run is offline; a `networked`-enabled run is a future, explicitly opt-in path.

## 10. Dependencies and Sequencing

This sub-phase depends on all three preceding Phase 1 sub-phases: Phase 1.1 (it aggregates conformant Findings), Phase 1.2 (it enumerates the registry and honors the offline/networked capability flag), and Phase 1.3 (its first real analyzer over an arbitrary repo is the reused secret-hygiene component). It is the terminal sub-phase of Phase 1 and the prerequisite for Phase 2 (analyzers plug into this runner), Phase 3 (the fixer reads this findings file), and Phase 5 (the reporter renders this output). A required decision is the exact output-directory and file names, which should be cross-checked against Phase 0's output-convention guidance so the audit and planning trees coexist coherently. No live credentials, network, or infrastructure are needed for the default offline run; a `networked` run would require explicit enablement, which is deferred. The naming decision is approval-sensitive because the names become permanent validator-checked identifiers.

## 11. Risks and Mitigations

- Risk: finding order depends on analyzer execution timing or filesystem iteration order, making output non-reproducible. Impact: downstream diffs are noisy and the Phase 6 reproducibility target fails. Mitigation: apply a total ordering on the merged findings independent of discovery order, and assert byte-identical output across two runs in the determinism test.
- Risk: the runner writes outside its fixed output directory or, worse, mutates the audited repository. Impact: the read-only audit guarantee from Main-Planning §5 is broken before the fixer phase even begins. Mitigation: constrain all writes to the fixed output tree and assert the audited working tree is unchanged after a run.
- Risk: a `networked` analyzer is invoked in the default run, breaking the zero-setup, offline-core promise. Impact: a base audit silently requires network access. Mitigation: make offline the default and require explicit enablement before any `networked` analyzer runs, recording every skip with a reason.
- Risk: the output-directory name is chosen casually and later collides with or shadows the `Planner-docs/` convention. Impact: a confusing dual-tree layout and a painful rename once names are validator-checked identifiers. Mitigation: register the name as a validator-checked identifier from the start and confirm it against the Phase 0 output-convention decision before freezing.

## 12. Desired End State

A read-only audit runner enumerates QB's registered analyzers in deterministic order, executes them over an arbitrary repository root, aggregates their Findings under a documented total ordering, and writes a graded, evidence-backed findings file plus a run summary into a fixed-name output directory whose names are enforced as validator-checked identifiers. The run is offline by default, refuses `networked` analyzers unless explicitly enabled, never mutates the audited tree, and produces byte-identical output across repeated runs over an unchanged repository — proven by a determinism test wired into `make check` and CI. Phase 1's parent goal is met: `qb-audit` emits deterministic, graded, machine-consumable findings for a real repository, giving Phases 2 through 5 a stable artifact to build on.

## 13. Transition Criteria to the Next Sub-Phase

Phase 1.4 is the final sub-phase of Phase 1, so its transition criteria are the readiness gates for Phase 2 (the analyzer suite). The runner must execute the registry over an arbitrary repository and emit deterministically ordered, schema-conformant Findings; the fixed output-directory name and its files must be frozen and registered as validator-checked identifiers; the determinism test and the read-only (audited-tree-unchanged) assertion must pass; offline-by-default behavior must be demonstrated; `make check`, `scripts/sync.sh --check`, and `python3 shared/scripts/validate_planner_docs.py --root . --mode step2 --strict` must all pass. Once these hold, Phase 2 can add real analyzers as conformant plugins that this runner enumerates, with no further changes to the runner or output contract.
