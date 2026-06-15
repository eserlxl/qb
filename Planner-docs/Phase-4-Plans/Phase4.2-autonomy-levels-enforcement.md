# Phase 4.2 — Autonomy Level Enforcement

## 1. Context

Within Phase 4 of `Planner-docs/Main-Planning.md` (the orchestrator/policy phase, M3->M4), this sub-phase turns the autonomy-level field defined by the Phase 4.1 schema into enforced runtime behavior. Where 4.1 froze "what the policy says," 4.2 guarantees "what the running system is physically allowed to do" at each level: A0 report-only (no writes at all), A1 propose (writes confined to throwaway isolation, never the user's working tree), A2 apply-verified (only verified fixes promoted into the working tree, everything else reverted), and A3 deliver (a reviewable changeset, prepared only when explicitly enabled). It builds on the Phase 3 fixer's git branch/worktree isolation primitive (the net-new mechanism flagged in `AUTOPSY-P0-02`) and on the Phase 4.1 engine verdicts. The defining rule, drawn straight from Main-Planning section 5, is that an out-of-policy action is blocked, not warned — the same fail-closed posture the existing validator already exhibits in `finalize`.

## 2. Goal

Deliver a runtime enforcement layer that maps each autonomy level to a concrete, verifiable set of permitted side effects and physically prevents anything outside that set: at A0 zero filesystem writes to the target tree occur; at A1 every write lands only inside throwaway isolation and the user's working tree is byte-identical before and after; at A2 only fixes that passed verification are present in the working tree and all unverified or failed fixes are absent; and at A3 a reviewable changeset is assembled only when an explicit enable flag is set, with commit/push/PR still gated by policy. The goal is met when each level's invariant can be asserted by a test that inspects the tree state after a simulated run.

## 3. Description

This sub-phase is where autonomy stops being a number in a file and becomes an enforced boundary on real side effects. The problem it solves is the gap between a policy that *says* "report only" and a system that *cannot* write when it should not — today there is no such enforcement because QB has no write-capable runtime at all (`Planner-docs/Autopsy.md` section 10 confirms the only existing rollback is implicit git). The work defines, per level, the exact permitted side-effect surface and the promotion/demotion transitions between isolation and the working tree: A1 keeps all fixer output quarantined in a dedicated branch or worktree; A2 promotes a fix into the working tree only after the verifier confirms its validation command passes, and demotes (reverts) anything that fails; A3 packages the promoted set as a reviewable changeset behind an explicit opt-in. It belongs here because the policy engine (4.1) already decides per-action permission, but level enforcement is the structural guarantee that even a buggy or compromised fixer cannot exceed its level. It reduces risk by making the working tree a protected resource whose mutation requires both a passing policy verdict and a passing verification, and it prepares Phase 4.3 (budgets/kill-switch) and 4.4 (cross-review) to plug in as additional pre-promotion gates.

### 3.1 Working tree as a protected resource

The user's working tree is treated as the asset of record. A1 never touches it; A2 mutates it only through a verified-promotion path; A3 additionally snapshots the promoted set for review. Any code path that would write to the working tree without passing through promotion is a design defect, not a runtime warning.

### 3.2 Promotion and demotion semantics

Promotion moves a fix from isolation into the working tree after verification succeeds. Demotion removes a fix (revert to the pre-fix reversal handle) when verification fails or when a higher level gate denies it. Both transitions are explicit, logged, and reversible.

## 4. Scope

- A per-level permitted-side-effect specification (A0/A1/A2/A3) defining exactly which target-tree writes, isolation writes, and changeset operations each level allows.
- The enforcement seam: the single chokepoint through which any working-tree mutation must pass, so level checks cannot be bypassed.
- The A1 isolation confinement rule (all writes inside a throwaway branch/worktree built on the Phase 3 isolation primitive).
- The A2 verified-promotion and auto-demotion rules tying promotion to a passing verification result.
- The A3 reviewable-changeset assembly behind an explicit enable flag, with commit/push/PR still subject to Phase 4.1 policy permission.
- The block-not-warn behavior for any attempted action above the active level, with a stable reason code.
- A test plan asserting each level's tree-state invariant after a simulated run.

## 5. Out of Scope

- The policy schema and engine evaluation logic themselves (Phase 4.1; consumed here as a dependency).
- Budget accounting, wall-time/token ceilings, and the kill-switch (Phase 4.3).
- Cross-review verdicts and reviewer role assignment (Phase 4.4); A2 promotion here gates on verification, with cross-review layered on later.
- The fixer's internal patch-generation logic and the isolation primitive's construction (Phase 3); this sub-phase consumes the isolation primitive, it does not build it.
- Actual commit/push/PR execution mechanics and remote interaction (Phase 5 reporting/delivery and later phases govern any remote step).
- Changes to the planning workflow's behavior under `Planner-docs/`.

## 6. Current Repository Evidence

QB has no write-capable runtime today, so there is currently nothing that enforces a write boundary at runtime — `Planner-docs/Autopsy.md` section 10 states the only backup/rollback is implicit git, with no worktree/branch isolation and no kill-switch. The closest existing safety analog is the prose discipline in `shared/planners/fourth-planner.md` (lines 28-31, 57-63): "one sub-plan and one reversible slice per run," "no commit, push, PR, deploy ... unless the user explicitly asks," and "verify with fresh evidence before claiming done" — the conceptual ancestor of A2 verified-promotion, but unenforced prose. The fail-closed reflex this sub-phase generalizes is visible in `finalize` (lines 537-555 of `shared/scripts/validate_planner_docs.py`), where any error yields exit 1 and strict mode promotes warnings to errors. `AUTOPSY-P0-02` records that the git branch/worktree isolation primitive is net-new and must be delivered in Phase 3, which this sub-phase then enforces levels on top of. No existing test inspects post-run working-tree state, so the level-invariant tests proposed here are a new surface.

## 7. Planned Work Breakdown

- F4.2-01 — Specify the per-level side-effect matrix
  - Description: For A0, A1, A2, A3, define exactly which operations are permitted (target-tree write, isolation write, changeset assembly, commit/push/PR request) and which are denied, with the denial expressed as a block.
  - Output: a four-row capability matrix with explicit allow/deny per operation.
- F4.2-02 — Define the single enforcement chokepoint
  - Description: Specify the one seam every working-tree mutation must traverse, so the level check is unavoidable and centrally testable; describe how the fixer routes all writes through it.
  - Output: an enforcement-seam specification naming the entry contract and the inputs it inspects (active level, policy verdict, verification status).
- F4.2-03 — A1 isolation-confinement rule
  - Description: Define that at A1 every fixer write lands in a throwaway branch/worktree and the user's working tree is provably unchanged; specify the pre/post equality check.
  - Output: an A1 confinement specification plus the working-tree-unchanged assertion.
- F4.2-04 — A2 verified-promotion and auto-demotion rule
  - Description: Define that a fix is promoted to the working tree only after its verification command passes, and that any unverified or failed fix is demoted via its reversal handle; specify the ordering (verify -> promote, fail -> revert).
  - Output: a promotion/demotion state-transition specification with the keep/revert decision points.
- F4.2-05 — A3 reviewable-changeset gating
  - Description: Define that A3 assembles a reviewable changeset only when an explicit enable flag is set, and that commit/push/PR remain subject to the Phase 4.1 permission booleans even at A3.
  - Output: an A3 delivery-gating specification with the explicit-opt-in precondition.
- F4.2-06 — Level-invariant test plan
  - Description: Specify tests that simulate a run at each level and assert the corresponding tree-state invariant (A0: no writes; A1: working tree unchanged; A2: only verified fixes present; A3: changeset assembled only when enabled).
  - Output: a test plan section naming proposed modules and the post-run assertions for each level.

## 8. Acceptance Criteria

- A per-level side-effect matrix exists that, for each of A0/A1/A2/A3, lists every permitted and every blocked operation with no overlap or ambiguity.
- The plan defines exactly one enforcement seam through which all working-tree mutations pass, making bypass a detectable design error.
- The A0 specification guarantees zero writes to the target working tree, demonstrable by a no-diff assertion after a simulated A0 run.
- The A1 specification confines all writes to throwaway isolation and asserts the user's working tree is byte-identical before and after.
- The A2 specification ties working-tree promotion strictly to a passing verification and demotes everything else; the A3 specification requires an explicit enable flag and keeps commit/push/PR under policy control.
- Every attempted above-level action is described as blocked with a stable reason code, never as a warning.
- Local readiness (level invariants assertable via simulated-run tests) is distinguished from live readiness (an actual unattended A2 run on a fixture, validated in Phase 4.3's end-to-end work and Phase 5).
- No secrets, tokens, or credentials appear in any specification or example.

## 9. Validation and Test Approach

- Document validation: run `python3 shared/scripts/validate_planner_docs.py --root . --mode step2 --strict` to confirm structure and no placeholder tokens.
- Local smoke (proposed): a proposed `tests/test_autonomy_levels.py` that simulates a run at each level and asserts the tree-state invariant (A0 no-diff, A1 working-tree-unchanged, A2 only-verified-present, A3 changeset-only-when-enabled).
- Local smoke (proposed): a proposed block-not-warn test asserting that an above-level action returns a deny verdict with a reason code and produces no side effect.
- Local validation: use `git status --short` and `git diff --check` style assertions in tests to prove the working tree is unmodified at A0/A1.
- CI: fold the new level tests into `make check` so they run via `.github/workflows/validate.yml` on every PR and push.
- Live readiness: deferred — a genuine end-to-end unattended A2 run on a fixture repo is owned by Phase 4.3 (budgets) and Phase 5 (reporting), not this sub-phase.

## 10. Dependencies and Sequencing

- Depends on Phase 4.1 (policy schema and engine) for the autonomy-level field and the per-action verdicts that gate promotion.
- Depends on Phase 3 for the git branch/worktree isolation primitive and per-fix reversal handles that A1 confinement and A2 demotion rely on.
- Depends on the Phase 3 verifier producing a pass/fail verification result that A2 promotion keys on.
- Should precede Phase 4.4 cross-review, which adds a second pre-promotion gate on top of the verification gate defined here.
- Requires the human decision on whether A3 (commit/push/PR) is ever enabled by default (Main-Planning section 9 open question (a)); until decided, A3 stays opt-in and off by default.
- Requires no live credentials or network for A0-A2; only A3 delivery to a remote (deferred) would.

## 11. Risks and Mitigations

- Risk: a write path that bypasses the enforcement seam reaches the working tree directly. Impact: a fix lands without level or verification checks, corrupting the user's tree. Mitigation: a single mandatory chokepoint plus a test that fails if any simulated write skips it.
- Risk: an A2 promotion races ahead of verification and keeps an unverified fix. Impact: a confidently-wrong change in the working tree. Mitigation: strict verify-then-promote ordering with demotion-on-failure, asserted by the only-verified-present invariant test.
- Risk: A1 isolation leaks into the working tree (for example a shared index or stray absolute path write). Impact: the "never touch the user's tree" guarantee breaks. Mitigation: the working-tree-byte-identical pre/post assertion and reliance on the Phase 3 worktree isolation primitive rather than in-place branching.
- Risk: A3 is accidentally treated as default-on. Impact: unrequested changeset/commit preparation. Mitigation: an explicit enable precondition and a default-off test asserting no changeset is assembled without the flag.

## 12. Desired End State

The four autonomy levels are enforced, not merely declared: A0 produces a provably unchanged working tree, A1 confines all activity to throwaway isolation, A2 admits only verification-passing fixes into the working tree and auto-reverts the rest, and A3 prepares a reviewable changeset only behind an explicit opt-in with commit/push/PR still under policy control. All working-tree mutation flows through one testable enforcement seam, every above-level attempt is blocked with a reason code, and a suite of level-invariant tests (green under `make check` after implementation) makes each guarantee verifiable. The planning workflow is unaffected, and no remote mutation is yet performed.

## 13. Transition Criteria to the Next Sub-Phase

- The per-level side-effect matrix is complete, internally consistent, and reviewed.
- The single enforcement chokepoint is specified and the level-invariant test plan covers A0 no-diff, A1 unchanged-tree, A2 only-verified, and A3 explicit-opt-in.
- Verified-promotion and auto-demotion semantics are unambiguous and tied to the Phase 3 verification result and reversal handles.
- Above-level actions are specified as blocked-with-reason-code, never warned, consistent with the fail-closed posture.
- Budget metering and the kill-switch remain unimplemented and are handed to Phase 4.3, which will add stop-and-report and halt-safely behavior as further gates before promotion.
