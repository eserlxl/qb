# Phase 3.4 — Fix-Safety Eval and Fixture Repos

## 1. Context

Phase 3.4 closes Phase 3 by building the test surface that proves the fixer is safe. The autopsy is unambiguous about the gap: finding AUTOPSY-P1-02 records that "all 13 tests/ modules validate the planning product; no fixture repos; no eval harness," and section 8 prescribes the exact gate for this phase — "A fix-safety invariant (Phase 3): every applied fix must keep its verification command green; failed fixes must auto-revert — assert via a fixture." Main-Planning section 4 also calls for an eval harness where "every applied fix must keep the verification command green," and the Phase 3 row's acceptance signals demand demonstrable keep-green and auto-revert behavior.

This is the fourth and final sub-phase of Phase 3. It depends on all three preceding sub-phases at once: it exercises the fix binding (3.1), the isolation and rollback runtime (3.2), and the verification gate (3.3) together on seeded defects. It produces the fixture repositories and the invariant harness that become a release gate for any future change to the fixer, wired into `make check` alongside the existing suite.

Because the current suite covers only the planning product, this sub-phase is the first to create a test surface for autonomous-fix behavior, addressing the zero-test-surface signal directly.

## 2. Goal

Build fixture repositories with seeded defects and a fix-safety invariant harness that asserts the two non-negotiable guarantees of the fixer: every applied fix keeps its verification command green, and every rejected fix leaves the working tree clean (byte-identical to the pre-fix state). The outcome is a runnable, deterministic harness that fails closed if either invariant is ever violated, giving QB measurable evidence of fix safety before any autonomy level above report-only is permitted to run unattended.

## 3. Description

The problem this sub-phase solves is unmeasurability: until now, fix safety is asserted only by prose and design, with no executable proof. This sub-phase creates small, self-contained git fixture repositories — each seeded with a known defect of a category Phase 3.1 marked auto-fixable, and each carrying its own verification command — so the full fix loop can be exercised end to end under test. The harness drives the fixer over each fixture and checks two invariants: a kept fix must leave the fixture's verification command green, and a rejected fix (one whose verification fails) must leave the fixture's tree exactly as it was before the attempt, with the isolation torn down.

It belongs last in Phase 3 because it integrates the outputs of every prior sub-phase; there is nothing to assert until binding, isolation, and the gate all exist. The risk it reduces is shipping an unsafe fixer: by making keep-green and clean-revert release gates, a regression in any of the three upstream mechanisms is caught before it can corrupt a real repository. It prepares Phase 4 by giving the policy engine a precondition it can rely on — autonomy may be raised only when the fix-safety harness is green — and it begins the eval surface that later phases (precision/recall on findings) extend. The fixtures also double as negative tests: a deliberately unfixable seeded defect proves the fixer reverts rather than forcing a bad change.

## 4. Scope

- One or more small, self-contained git fixture repositories under a dedicated test-data location, each with a seeded defect and its own verification command.
- A fix-safety invariant harness (working name `tests/test_fix_safety.py`) following the `unittest` + `subprocess` conventions in `tests/`, asserting keep-green and clean-revert.
- A positive fixture per auto-fixable category from Phase 3.1: the fixer applies a fix, verification goes green, the fix is kept.
- A negative fixture: a seeded defect whose fix cannot be verified green, so the fixer must auto-revert and leave the tree clean.
- Integration of the harness into the local validation flow so it runs under `make check` and in CI via `.github/workflows/validate.yml`.
- Registration of any new shared artifact in `scripts/sync.sh`, and extension of the sync-map completeness check if a synced artifact is added.

## 5. Out of Scope

- Audit precision/recall measurement of analyzer findings — that eval surface belongs to Phase 1 and Phase 2 fixtures, not the fix-safety harness here.
- The policy/budget/autonomy engine and its out-of-policy-blocked test — owned by Phase 4.
- Cross-review of fixes by a separable role and the seeded-bad-fix detection eval — owned by Phase 5.
- Defining the fix recipes, isolation runtime, or verification gate themselves — those are owned by Phase 3.1, 3.2, and 3.3; this sub-phase only exercises them.
- Networked or CVE-dependent fixtures requiring external feeds — kept out to preserve the offline, dependency-light core.
- Real target-repository runs or any commit/push/PR; all fixtures are local, self-contained, and disposable.

## 6. Current Repository Evidence

The existing test suite is the template and the proof of the gap simultaneously. `make check` runs `scripts/sync.sh --check`, the three per-platform `validate.sh`, then `python3 -m unittest discover -s tests`, and every one of those modules validates the planning product — for example `tests/test_no_committed_secrets.py` enumerates tracked files for secret patterns and `tests/test_sync_mechanism.py` exercises sync drift and restore. The shared helper `tests/qb_monorepo.py` exposes `REPO_ROOT`, the convention new tests should reuse. There is no fixture repository and no fix-safety test anywhere in `tests/`, matching AUTOPSY-P1-02. The `unittest` + `subprocess` + temporary-directory pattern visible in `tests/test_no_committed_secrets.py` is the idiom this sub-phase's harness must follow. Current repository evidence for an autonomous-fix test surface is otherwise nonexistent; this sub-phase creates it.

## 7. Planned Work Breakdown

- F3.4-01 — Positive fixture repos with seeded defects
  - Description: Create small self-contained git fixtures, one per auto-fixable category from Phase 3.1, each seeding a known defect and shipping a verification command that goes green once the defect is fixed.
  - Expected output: a set of disposable fixture repositories under a test-data path, each with a documented seeded defect and verify command.
- F3.4-02 — Negative (unfixable) fixture
  - Description: Create a fixture whose seeded defect cannot be verified green after a fix attempt, forcing the auto-revert path.
  - Expected output: a fixture that reliably triggers rejection and clean revert.
- F3.4-03 — Keep-green invariant assertion
  - Description: Implement the harness check that, after the fixer keeps a fix on a positive fixture, the fixture's verification command returns green.
  - Expected output: a passing keep-green assertion over every positive fixture.
- F3.4-04 — Clean-revert invariant assertion
  - Description: Implement the harness check that, after the fixer rejects a fix on the negative fixture, the fixture tree is byte-identical to its pre-attempt state and isolation is torn down.
  - Expected output: a passing clean-revert assertion over the negative fixture.
- F3.4-05 — Wire the harness into make check and CI
  - Description: Ensure the fix-safety harness runs under `python3 -m unittest discover -s tests` and thus under `make check` and `.github/workflows/validate.yml`, and register any synced artifact in `scripts/sync.sh`.
  - Expected output: the harness gating local validation and CI, with the sync-map completeness check still passing.

## 8. Acceptance Criteria

- At least one positive fixture exists per auto-fixable category from Phase 3.1, and each ships a verification command that is red before the fix and green after it.
- The keep-green invariant holds: for every positive fixture, the harness confirms the kept fix leaves the verification command green.
- The clean-revert invariant holds: for the negative fixture, the harness confirms the tree is byte-identical to its pre-attempt state and the isolation container is removed after rejection.
- The harness is discovered by `python3 -m unittest discover -s tests`, runs under `make check`, and runs in CI, failing closed if either invariant is violated.
- Fixtures are self-contained, offline, and disposable; no fixture requires network access or external credentials, and no fixture or evidence record contains a real secret value (any secret-shaped fixture content is a deliberate test marker, not a live credential).
- The sync-map completeness check still passes after any new synced artifact is registered.

## 9. Validation and Test Approach

This sub-phase is itself the validation surface, so its approach is to run and prove. Local smoke: `python3 -m unittest discover -s tests` must execute the new `tests/test_fix_safety.py` and pass both invariants. Full local gate: `make check` must remain green end to end, demonstrating the harness coexists with the planning-product tests and the sync drift check. CI: `.github/workflows/validate.yml` runs `make check` on PRs and pushes to `main`, so the harness gates merges automatically. Security validation: confirm any secret-shaped content inside a fixture carries the deliberate test marker so `tests/test_no_committed_secrets.py` does not flag it, and confirm no fixture executes a repo-provided script outside the controlled verification command. Distinguish document validation (drift check) from local smoke (the new harness) from CI (merge gate) from live readiness (real-repo unattended runs, which remain gated until Phase 4).

## 10. Dependencies and Sequencing

Hard upstream dependencies: Phase 3.1, 3.2, and 3.3 must all be in place, because the harness exercises the binding, the isolation/rollback runtime, and the verification gate together. This sub-phase blocks raising any autonomy level above report-only: Phase 4 should treat a green fix-safety harness as a precondition for enabling A2 unattended runs. A working git binary is required to create and reset fixture repositories; no network access, no live credentials, and no human approvals are needed because every fixture is local and disposable. The choice of where fixture repositories live (a dedicated test-data path) and whether any harness artifact is synced into platforms is a detail to be confirmed during implementation, kept consistent with the existing `tests/` conventions.

## 11. Risks and Mitigations

- Risk: nested git fixture repositories interfere with the outer QB repository's git state or get accidentally tracked. Impact: polluted history or a confused working tree. Mitigation: build fixtures in temporary directories created at test time, or store them as inert templates initialized into a temp dir per run, never leaving a live nested repo tracked in QB.
- Risk: a fixture's verification command is environment-dependent and passes locally but fails in CI. Impact: a flaky release gate that erodes trust. Mitigation: keep fixture verify commands offline and dependency-light, asserting only on deterministic local behavior, and run them under the same `make check` path locally and in CI.
- Risk: seeded secret-shaped fixture content trips the repo-wide secret scan. Impact: `tests/test_no_committed_secrets.py` fails on intentional fixtures. Mitigation: mark deliberate fixture secrets with the established allowlist marker so the scan recognizes them as test fixtures rather than live credentials.
- Risk: the harness asserts keep-green but not true clean-revert, missing partial reverts. Impact: a false sense of safety. Mitigation: assert byte-identity against the captured pre-attempt state and confirm isolation teardown, not merely that verification fails.

## 12. Desired End State

A runnable fix-safety harness and a set of seeded fixture repositories exist and gate every change to the fixer. The harness proves the two invariants — every kept fix keeps verification green, every rejected fix leaves a clean tree with isolation removed — across one positive fixture per auto-fixable category plus a negative fixture. It runs under `make check` and in CI, fails closed on any violation, and contains no live secrets. QB now has its first measurable, automated evidence of autonomous-fix safety, satisfying the autopsy's zero-test-surface signal for the fixer and giving Phase 4 a concrete precondition before raising autonomy.

## 13. Transition Criteria to the Next Sub-Phase

Before Phase 4 (Autonomy Orchestrator and Policy Engine) begins, the fix-safety harness must be green under `make check` and in CI, with the keep-green and clean-revert invariants both asserted over real fixtures. At least one positive fixture per auto-fixable category and the negative fixture must exist and be deterministic across local and CI runs. The sync-map completeness check must still pass, and no fixture may require network access or contain a live credential. With these in place, Phase 4 may treat a passing fix-safety harness as the precondition for enabling autonomy levels above report-only.
