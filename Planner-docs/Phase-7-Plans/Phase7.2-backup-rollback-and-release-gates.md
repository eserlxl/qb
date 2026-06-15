# Phase 7.2 — Backup/Rollback Drills and Release Gates

## 1. Context

This sub-phase sits in the middle of parent Phase 7, between telemetry (7.1) and the production self-audit gate (7.4). Main-Planning section 6 lists "git-based backup/rollback" and "release gates" as explicit Phase 7 deliverables, and its key acceptance signal for the phase is "rollback drills pass." The autopsy (`Planner-docs/Autopsy.md` section 10) is unambiguous that this safety net does not yet exist: "Backup / restore / rollback: only implicit git. There is no automatic rollback mechanism, no worktree/branch isolation, and no kill-switch." Phase 3 introduces per-fix git isolation and auto-rollback for a single fix, but a single-fix rollback is not the same as proving that an entire unattended run — possibly dozens of applied fixes across many files — can be undone cleanly. This sub-phase exists to close that gap: it defines repeatable rollback drills that demonstrate a whole run is reversible, and it defines the release gates that read the Phase 7.1 telemetry and decide whether a given context is allowed to operate at A2 (apply-verified) or A3 (deliver) at all. It connects forward to 7.4, where these drills and gates become part of the final production-gated acceptance, and it depends on the metric definitions frozen in 7.1.

## 2. Goal

Define git-based backup and full-run rollback drills that prove, with reproducible evidence, that an entire autonomous harden run can be reverted to its exact pre-run state — and define the release gates (an audit-precision gate plus a fix-safety gate, both reading Phase 7.1 telemetry) that must pass before autonomy level A2 or A3 may be enabled for a given repository context.

## 3. Description

This work establishes recoverability as a tested property rather than a hopeful assumption. It specifies how QB captures a pre-run reversal handle (a git ref or equivalent snapshot, building on the `export-sanitized` habit of using `git archive` already present in the `Makefile`) before any write occurs, how it records the set of refs and patches produced during the run, and how a single documented operation returns the working tree to its exact pre-run state. It then defines a rollback drill: a deterministic procedure run against a fixture repository that applies a known set of fixes, invokes the full-run undo, and asserts byte-for-byte equivalence with the captured pre-run snapshot. On top of recoverability it defines two release gates. The audit-precision gate consumes the precision floor from Phase 7.1 and refuses to permit auto-apply autonomy for a context whose measured precision is below the floor. The fix-safety gate refuses to permit A2/A3 unless the most recent eval shows every kept fix kept its verification command green and every failed fix auto-reverted. This belongs here, after telemetry and before the production gate, because release gating is meaningless without measured numbers (7.1) and the production acceptance (7.4) is built on top of working drills and passing gates. It reduces the master plan's top risk — autonomous changes causing regressions or damage — by guaranteeing a tested escape hatch and by withholding dangerous autonomy from contexts that have not earned it.

## 4. Scope

- Pre-run reversal-handle capture: a documented mechanism to snapshot the target's exact state before the first write, building on git refs and the `git archive` pattern already in the `Makefile`.
- Full-run rollback procedure: a single documented operation that reverts every change a run made, distinct from Phase 3's per-fix revert.
- Rollback drill specification: a deterministic fixture-based procedure that applies fixes, undoes the whole run, and asserts equivalence to the pre-run snapshot.
- Audit-precision release gate: a gate that reads the Phase 7.1 precision metric and permits/denies auto-apply autonomy per context.
- Fix-safety release gate: a gate asserting every kept fix kept verification green and every failure auto-reverted.
- Gate-to-autonomy mapping: which gate outcomes unlock A2 versus A3, and the fail-closed default when a gate has no recent data.
- Drill evidence record: what the drill writes (pass/fail, diff-clean assertion, snapshot equivalence) into the telemetry/output convention.

## 5. Out of Scope

- Defining the telemetry metrics themselves (Phase 7.1 owns the precision and fix-safety signal definitions; this sub-phase consumes them).
- The per-fix isolation and per-fix auto-rollback primitive (Phase 3 owns that; this builds the whole-run drill on top of it).
- The kill-switch and the operations runbook narrative, and the QB-hardens-QB dogfood run (Phase 7.4).
- Least-privilege write-path enforcement and supply-chain review (Phase 7.3).
- Any non-git backup technology (filesystem snapshots, external object storage, databases) — recoverability here is deliberately git-based to preserve the zero-setup promise.
- Enabling A3 commit/push/PR by default — A3 remains explicit opt-in regardless of gate outcomes.

## 6. Current Repository Evidence

The only backup-adjacent primitive in the repository is the `Makefile` `export-sanitized` target, which runs `git archive --format=zip --output QB-sanitized.zip HEAD` — a snapshot of committed state, not a pre-run reversal handle and not a run-undo mechanism. No script captures a reversal ref before writes, and no procedure reverts a multi-fix run; the autopsy (`Planner-docs/Autopsy.md` section 10) confirms rollback is "only implicit git." There are no release gates: the closest existing gate is `validate_step4_readiness` in `shared/scripts/validate_planner_docs.py`, which blocks Step 4 when audit status is BLOCKED or P0/P1 findings exist, but it gates a planning step, not an autonomy level, and reads a planning audit document rather than run telemetry. The fixer discipline in `shared/planners/fourth-planner.md` requires "minimal and reversible" changes and verify-before-done but, as the autopsy notes (section 11), contains no isolation or whole-run undo mechanism. Fixture repos to drill against do not exist yet (autopsy section 8), so the drill specification must assume they are created in the Phase 1 eval-harness work.

## 7. Planned Work Breakdown

- F7.2-01 — Pre-run reversal-handle capture
  - Description: Specify capturing the target's exact pre-run state as a git ref plus an optional `git archive` snapshot before any write, extending the `export-sanitized` pattern into a per-run safety baseline.
  - Output: a reversal-handle capture specification with the ref/snapshot format.
- F7.2-02 — Full-run rollback procedure
  - Description: Define a single documented operation that reverts every change a run produced and returns the working tree to the captured baseline, layered above Phase 3 per-fix reverts.
  - Output: a step-by-step whole-run undo specification.
- F7.2-03 — Rollback drill specification
  - Description: Define a deterministic fixture-based drill that applies known fixes, runs the full-run undo, and asserts byte-equivalence with the pre-run snapshot.
  - Output: a drill procedure plus its pass/fail assertion.
- F7.2-04 — Audit-precision release gate
  - Description: Define the gate that reads the Phase 7.1 precision metric and permits or denies auto-apply autonomy for a given context, failing closed below the floor.
  - Output: a precision-gate rule referencing the 7.1 thresholds.
- F7.2-05 — Fix-safety release gate
  - Description: Define the gate asserting every kept fix kept verification green and every failed fix auto-reverted, blocking A2/A3 otherwise.
  - Output: a fix-safety-gate rule with its data source.
- F7.2-06 — Gate-to-autonomy mapping and drill evidence
  - Description: Map gate outcomes to A2 versus A3 eligibility with a fail-closed default, and define what the drill writes into the output convention as evidence.
  - Output: a gate-to-autonomy table and a drill-evidence record format.

## 8. Acceptance Criteria

- This sub-plan specifies a pre-run reversal-handle capture distinct from `git archive`-of-HEAD, and a full-run undo distinct from Phase 3's per-fix revert.
- The rollback drill is deterministic and its pass condition is byte-equivalence between post-undo tree and pre-run snapshot, expressed concretely enough to assert in a test.
- Both release gates are defined as verifiable rules reading named Phase 7.1 metrics, and each gate fails closed when recent data is absent.
- The gate-to-autonomy mapping states explicitly which outcomes unlock A2 versus A3, and confirms A3 remains explicit opt-in regardless of gate results.
- Local readiness (drill passes on a fixture) is separated from live readiness (drill behavior on a real target repository under operator control).
- Drill evidence is written into the established output/telemetry convention, not to ad-hoc locations.
- No secret values, tokens, or credentials appear in the plan.

## 9. Validation and Test Approach

Document validation: run `python3 shared/scripts/validate_planner_docs.py --strict` to confirm the 13 headings and absence of placeholder tokens. Local smoke: a proposed `make rollback-drill` target would execute the drill against a fixture, apply fixes, run the whole-run undo, and assert the post-undo tree matches the pre-run snapshot; `git diff --check` and a `git status --short` clean assertion are the concrete equivalence probes. Local readiness: the precision and fix-safety gates are exercised against recorded telemetry fixtures so their permit/deny logic is tested without a live run. CI: `make check` continues to gate merges and would gain the drill and gate tests so a regression in recoverability or gating fails the build. Security validation: the existing secret-scan test (`tests/test_no_committed_secrets.py`) ensures no snapshot or drill artifact ships a secret. Live readiness: the drill against a real operator repository, and the act of enabling A2/A3 for a real context, are deferred operational steps that 7.4 ties into the production gate — they are not asserted by this plan.

## 10. Dependencies and Sequencing

Depends on Phase 7.1 (the precision and fix-safety metrics the gates read), Phase 3 (the per-fix isolation and revert primitive the whole-run undo is layered on), Phase 1 (the fixture repos and eval harness the drill runs against), and Phase 0 (the output-directory convention drill evidence is written to). Required decisions: the exact precision floor value (set in 7.1), and whether the reversal handle is a dedicated branch ref, a tag, or a stash-equivalent. Required human approvals: enabling A2 or A3 for any real context is a human-on-the-loop decision gated by these release gates. No live credentials are needed to write or test the drills against fixtures. This sub-phase blocks 7.4, whose production gate requires passing drills and passing release gates as inputs.

## 11. Risks and Mitigations

- Risk: the rollback drill passes on a clean fixture but the whole-run undo silently leaves untracked or ignored files behind on a messy real repository. Impact: an operator believes a run was fully reverted when residue remains, eroding the recoverability guarantee. Mitigation: make the drill assert a clean `git status --short` including untracked files and explicitly enumerate how ignored/untracked artifacts are handled by the undo.
- Risk: a release gate is bypassed or defaults open when telemetry is missing. Impact: A2/A3 enabled for a context with no measured precision, the exact ungated-autonomy danger the master plan forbids. Mitigation: define both gates fail-closed — absent or stale data denies auto-apply autonomy and forces report-only.
- Risk: the reversal handle conflicts with the user's own branches or refs and corrupts their VCS state. Impact: the safety mechanism itself damages the working tree it is meant to protect. Mitigation: namespace the reversal ref distinctly, capture it before any write, and verify it is restorable in the drill before a run is allowed to proceed.
- Risk: gates tuned to a fixture do not generalize, so a context passes the gate yet performs poorly live. Impact: false confidence in autonomy eligibility. Mitigation: require the gate decision to be re-evaluated per context against that context's own recent telemetry, never inherited from a different repository.

## 12. Desired End State

QB captures a namespaced pre-run reversal handle before its first write, and a single documented operation reverts an entire run to that baseline with a clean `git status` proven by a deterministic, repeatable rollback drill on a fixture. Two fail-closed release gates — audit-precision and fix-safety — read Phase 7.1 telemetry and decide per context whether A2 or A3 may be enabled, with A3 still requiring explicit opt-in. Drill outcomes and gate decisions are recorded in the established output convention. The master plan's top risk (autonomous changes causing damage) now has both a tested escape hatch and an evidence-based admission gate.

## 13. Transition Criteria to the Next Sub-Phase

Before Phase 7.3, the rollback drill must pass deterministically on a fixture with a clean post-undo `git status --short`, the pre-run reversal-handle mechanism must be namespaced and restorable without disturbing user refs, and both release gates must be defined as fail-closed rules reading named Phase 7.1 metrics. The gate-to-autonomy mapping must be unambiguous and confirm A3 stays explicit opt-in. Local recoverability readiness must be clearly separated from live recoverability on a real target. The document checker (`python3 shared/scripts/validate_planner_docs.py --strict`) must report this sub-plan as clean before proceeding.
