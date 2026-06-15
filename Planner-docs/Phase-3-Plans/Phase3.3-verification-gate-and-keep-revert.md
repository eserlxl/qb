# Phase 3.3 — Verification Gate and Keep/Revert Decision

## 1. Context

Phase 3.3 turns QB's prose verification discipline into an enforced gate. `shared/planners/fourth-planner.md` already states the rule in steps 4-5 of its "Slice procedure" — "Run the focused tests" and "Before claiming done, verify with fresh evidence (run the command and confirm output)" — but the autopsy notes in section 6 that "there is no machine-checkable enforcement that an applied fix was actually verified or is reversible; the safety is currently a prompt, not a gate." This sub-phase makes that enforcement real.

Within Phase 3, this is the third sub-phase. It consumes the per-finding verification command chosen in Phase 3.1 and the rollback handle produced in Phase 3.2, and it produces the keep-or-revert decision plus the before/after evidence record. Main-Planning section 5 names this exact contract: "Every applied fix carries the patch, the verification command and its before/after result, and a reversal handle (git ref). No fix is 'done' without recorded verification evidence." Main-Planning's Phase 3 acceptance signals are also realized here: "Every applied fix keeps verification green; failed fixes auto-revert with evidence."

The gate is the join point of the two preceding sub-phases: without Phase 3.1's chosen command there is nothing to run, and without Phase 3.2's handle there is nothing to revert to. It feeds Phase 3.4, whose fix-safety harness asserts the gate's two invariants on fixture repos.

## 2. Goal

Define a mandatory per-fix verification gate that, for each applied fix, runs the pre-selected verification command, keeps the fix only if the command passes, and otherwise auto-reverts using the Phase 3.2 rollback handle — recording before-and-after evidence either way. The outcome is a written enforced-gate contract in which "fix applied" and "fix verified" are inseparable: a fix that has not been proven green cannot be kept, and a fix that fails verification is automatically undone with its failure evidence captured.

## 3. Description

The defect this sub-phase removes is that verification is currently advisory. An autonomous fixer that may skip or fake verification is precisely the "confidently-wrong change" the plan warns against, so Phase 3.3 makes verification a hard precondition for keeping any change. The gate captures a "before" baseline (the verification command's result on the unfixed state where meaningful, plus the rollback handle), applies the fix inside isolation, runs the same command to produce an "after" result, and branches: green means keep and record success evidence; non-green means immediately reset to the rollback handle and record failure evidence with the captured command output.

This belongs after isolation because the revert path requires a handle to revert to, and after fix binding because the command to run must already be chosen. The risk it reduces is silent regression and unverified writes: by making revert automatic on any non-green outcome, a failing fix can never persist, and by recording before/after evidence for every fix it produces the audit trail Main-Planning section 4 requires. It prepares Phase 4 because the policy engine will gate auto-keep behind severity and confidence thresholds, but it will rely on this gate to guarantee that whatever is kept is verified; and it prepares Phase 5, which consumes the recorded before/after evidence to build the reproducible report.

## 4. Scope

- A written enforced-gate contract generalizing the `fourth-planner.md` verify-before-done rule into a non-bypassable per-fix step.
- The before/after evidence record format: the verification command, its captured exit status and salient output (redacted of any secrets), the rollback handle, and the keep-or-revert outcome.
- The keep path: criteria for "green" and the rule that only green fixes are kept.
- The revert path: automatic reset to the rollback handle on any non-green outcome, including command error, non-zero exit, and timeout.
- A no-verification-command fail-closed rule: if no command can be run for a finding, the fix is not kept (it is reverted or never applied).
- Redaction-by-default of captured command output so secrets surfaced by a verification command are never persisted to evidence.

## 5. Out of Scope

- Creating isolation or capturing the rollback handle — owned by Phase 3.2 (this sub-phase only acts on the handle).
- Choosing the verification command per finding — owned by Phase 3.1 (this sub-phase only runs the chosen command).
- Severity/confidence thresholds, autonomy-level selection, and budgets that decide whether auto-keep is even permitted — owned by Phase 4.
- Cross-review of a kept fix by a separable role — owned by Phase 5.
- The fixture repos and the invariant harness that assert the gate's guarantees — owned by Phase 3.4.
- Emitting the final JSON/SARIF report from the recorded evidence — owned by Phase 5.

## 6. Current Repository Evidence

The verify-before-done discipline lives only as prose: `shared/planners/fourth-planner.md` lines 43-45 instruct running the focused tests and verifying with fresh evidence before claiming done, and line 64 forbids claiming success without running the validation command — but nothing enforces this mechanically. The autopsy's section 6 "Discipline-as-prose, not contract" entry and AUTOPSY-P0-02 both confirm the enforcement and the revert path are absent. The closest existing enforced gate in the codebase is the validator's Step-4 readiness check (`validate_step4_readiness` in `shared/scripts/validate_planner_docs.py:491`), which gates *whether implementation may start* based on audit severities — a useful structural precedent for a fail-closed gate, but it does not verify a fix after application. No before/after evidence record format exists anywhere in the repository. Current repository evidence for an enforced keep/revert gate is therefore limited to this prose discipline and the analogous readiness check.

## 7. Planned Work Breakdown

- F3.3-01 — Enforced verification-gate contract
  - Description: Author the contract that makes running the pre-selected verification command a non-bypassable step before any fix may be kept, generalizing the `fourth-planner.md` verify-before-done rule.
  - Expected output: a gate specification stating that "applied" never implies "kept" without a green verification.
- F3.3-02 — Before/after evidence record format
  - Description: Define the per-fix evidence record fields — verification command, before result, after result, exit status, redacted output, rollback handle, outcome — that Phase 5 will later render.
  - Expected output: an evidence-record schema description with every field named.
- F3.3-03 — Keep path and green criteria
  - Description: Specify what counts as "green" (exit status and any required output assertions) and the rule that only green fixes are kept.
  - Expected output: a keep-decision rule with explicit green criteria.
- F3.3-04 — Auto-revert path
  - Description: Define automatic reset to the Phase 3.2 rollback handle on any non-green outcome, enumerating the trigger conditions (non-zero exit, command error, timeout) and the post-revert verification that the tree matches the handle.
  - Expected output: a revert-decision rule covering all failure triggers.
- F3.3-05 — No-command and redaction fail-closed rules
  - Description: Specify that a finding with no runnable verification command is never kept, and that captured command output is redacted of secrets before persistence.
  - Expected output: two fail-closed rules (no-command-no-keep, redact-before-persist).

## 8. Acceptance Criteria

- The gate contract states that no fix is kept unless its pre-selected verification command was actually run and returned green, and that "applied" alone is insufficient.
- The before/after evidence record names every field, including the rollback handle and the redacted command output, so each kept or reverted fix is fully traceable.
- The keep path defines "green" precisely (exit status plus any output assertion), and the revert path triggers automatically on non-zero exit, command error, and timeout.
- A finding with no runnable verification command is explicitly never kept, and this is stated as a fail-closed rule.
- Captured verification output is redacted of secrets by default before it is written to any evidence record, so no secret value is persisted.
- The contract distinguishes the kept-fix evidence trail (success) from the reverted-fix evidence trail (failure), and both are recorded.

## 9. Validation and Test Approach

Document validation: any new shared artifact must pass `bash scripts/sync.sh --check` after `MAP` registration, and `python3 -m unittest discover -s tests` must stay green. Proposed local-smoke tests (not yet present): a keep-path test (working name `tests/test_verification_gate.py`) that applies a passing fix in a temporary git repo and asserts it is kept with a recorded green result, and a revert-path test that applies a failing fix and asserts the tree is reset to the rollback handle with failure evidence recorded. A redaction test asserts that a verification command which prints a secret-shaped string never persists that value to the evidence record, reusing the secret patterns established in `tests/test_no_committed_secrets.py`. These follow the `unittest` + `subprocess` + temporary-repo convention. Distinguish document validation (drift check) from local smoke (the proposed gate tests) from CI (the suite runs under `make check`) from live readiness (an end-to-end keep/revert over a real target repo, gated until Phase 4).

## 10. Dependencies and Sequencing

Hard upstream dependencies: Phase 3.1 (the chosen verification command) and Phase 3.2 (the rollback handle and isolation container) must both exist, because the gate runs the former and reverts via the latter. This sub-phase blocks Phase 3.4, whose invariant harness asserts the two gate guarantees (every kept fix is green, every reverted fix leaves a clean tree). It also blocks Phase 4's auto-keep policy, which assumes a working gate beneath it, and Phase 5's report, which consumes the evidence records defined here. No network access, no live credentials, and no human approvals are required to design or locally test the gate; a working git binary and the ability to run the verification command in isolation are the only runtime needs.

## 11. Risks and Mitigations

- Risk: a flaky verification command passes once and fails on rerun, so a kept fix is not truly green. Impact: an unstable "verified" fix that regresses later. Mitigation: define green strictly on the recorded run and allow the contract to require a confirmatory rerun for categories prone to flakiness, recording both results.
- Risk: a verification command hangs and the gate never decides. Impact: a stuck run that never reverts. Mitigation: treat a timeout as a non-green outcome that triggers auto-revert, with the timeout enumerated as an explicit failure trigger.
- Risk: a verification command emits a secret (for example printing an environment variable) that lands in the evidence record. Impact: secret leakage into persisted artifacts. Mitigation: redact-by-default of captured output before persistence, using the established secret patterns, so no secret value is stored.
- Risk: the revert path resets isolation but a previously promoted fix already touched the working tree. Impact: a partial revert that leaves a stale change. Mitigation: bind keep/revert to the per-finding atomic promotion boundary defined in Phase 3.2 so revert and promotion never overlap.

## 12. Desired End State

A mandatory, non-bypassable verification gate exists in plan-ready form. For each fix, the gate runs the pre-selected command, keeps the fix only when it is green, and otherwise auto-reverts to the captured rollback handle — recording redacted before/after evidence in every case. "Applied" and "verified" are inseparable, a finding with no runnable command can never be kept, and no secret reaches an evidence record. The two guarantees that Phase 3.4 will assert as invariants — every kept fix keeps verification green, and every reverted fix leaves a clean tree — are now defined concretely enough to test.

## 13. Transition Criteria to the Next Sub-Phase

Before Phase 3.4 begins, the keep-path green criteria and the auto-revert triggers (non-zero exit, command error, timeout) must be fully specified, the before/after evidence record must name every field, and the no-command-no-keep and redact-before-persist fail-closed rules must be written down. The two gate guarantees must be phrased as testable invariants so the fixture harness can assert them directly. No end-to-end keep/revert may have been run against a real target repository, since live execution depends on Phase 4 selecting an autonomy level.
