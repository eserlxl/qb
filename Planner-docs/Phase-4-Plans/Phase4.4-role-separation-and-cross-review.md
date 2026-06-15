# Phase 4.4 — Role Separation and Cross-Review

## 1. Context

This final Phase 4 sub-phase of `Planner-docs/Main-Planning.md` (orchestrator/policy, M3->M4) implements the architectural separation of roles that the master plan's section 5 names — Analyzers, Fixer, Verifier, and a Reviewer applied as "a distinct lens ... ideally not the same role that authored them." It directly answers the autopsy directive that "the model that authored a fix is not the sole judge of it (cross-review)," and the Phase 4 acceptance signal in Main-Planning's roadmap that "cross-review catches a seeded bad fix in eval" (echoed in section 5's row for Phase 5 and the cross-review target in section 4). It builds on the policy engine (4.1), the level-enforced verified-promotion path (4.2), and the budget/kill safety net (4.3): cross-review becomes an additional pre-promotion gate so that, when it matters, a fix's keep/revert decision is not made solely by the role or model that produced it.

## 2. Goal

Deliver a role-separation model and a cross-review gate such that a fix authored by one role/model is judged for keep-or-revert by a distinct reviewing role/model whenever the fix meets the "it matters" criteria (for example security-category fixes, high-severity fixes, or fixes touching sensitive paths), and the cross-review verdict — together with the verification result — gates promotion into the working tree. The goal is met when a seeded bad fix in a fixture is caught and reverted by a reviewer distinct from its author, and an out-of-policy attempt to let the author self-approve a "matters" fix is blocked.

## 3. Description

This sub-phase closes the trust loop on autonomy by ensuring authorship and judgment are separable. The problem it addresses is the failure mode Main-Planning section 7 frames as "false positives drive bad fixes" combined with the conflict of interest in a single model both writing and approving its own change — confidently-wrong patches that pass a naive self-check. The work defines four roles with explicit responsibilities and write-capabilities (Analyzer read-only, Fixer write-under-isolation, Verifier runs the validation command and decides verification pass/fail, Reviewer renders an independent keep/revert verdict), specifies when cross-review is mandatory versus optional via "it matters" criteria, defines how the reviewer is made distinct from the author (a different role, and where feasible a different model/family), and wires the cross-review verdict into the promotion gate so that for a "matters" fix both verification *and* cross-review must pass before the fix reaches the working tree. It belongs last in Phase 4 because cross-review composes on top of the policy, level, and budget machinery rather than replacing it. It reduces risk by removing the single-judge conflict of interest and preparing Phase 5, where the cross-review verdict becomes part of the reproducible report and the eval harness measures its catch rate.

### 3.1 Author-distinct-from-reviewer rule

For any fix classified as mattering, the role (and, where the host supports it, the model/family) that authored the patch must not be the role that renders the keep/revert verdict. A self-approval of a mattering fix is an out-of-policy action and is blocked, not warned.

### 3.2 Verdict composition with verification

Cross-review does not replace verification; it adds to it. A mattering fix is promoted only when the verifier reports the validation command green *and* the reviewer returns a keep verdict. Either a failed verification or a revert verdict demotes the fix via its reversal handle.

## 4. Scope

- The four-role responsibility model (Analyzer, Fixer, Verifier, Reviewer) with each role's allowed capabilities and write-access.
- The "it matters" criteria that make cross-review mandatory (security category, high severity, sensitive-path writes) versus optional for low-risk fixes.
- The author-distinct-from-reviewer rule, including model/family distinctness where the host supports assigning it.
- The cross-review verdict contract (keep/revert plus a reason) and its composition with the Phase 3 verification result at the Phase 4.2 promotion gate.
- The self-approval block: a mattering fix whose reviewer equals its author is an out-of-policy, blocked action.
- A test plan covering the seeded-bad-fix catch and the self-approval-blocked path.

## 5. Out of Scope

- The policy schema and engine (Phase 4.1), consumed here to read the "it matters" thresholds and reviewer-required flag.
- Autonomy-level side-effect enforcement and the promotion seam mechanics (Phase 4.2), into which the cross-review verdict plugs.
- Budget metering and the kill-switch (Phase 4.3).
- The fixer's patch generation and the verifier's command-execution mechanics (Phase 3); this sub-phase consumes their outputs, it does not build them.
- The full eval harness that measures cross-review precision/recall across many fixtures (Phase 5); only a minimal seeded-bad-fix fixture is in scope here.
- Multi-host model-assignment specifics for every provider (Phase 6 parity work) beyond stating the distinctness requirement.

## 6. Current Repository Evidence

No role separation exists in the repository today: `Planner-docs/Autopsy.md` section 7 states "the Analyzer / Fixer / Verifier / Orchestrator separation from Main-Planning section 5 does not exist as code or interfaces; today there is a single validator script and prose specs." The closest analog is `shared/planners/fourth-planner.md`, where a single executing role both makes the change and verifies it (lines 42-45: "make the minimal, reversible change," then "verify with fresh evidence before claiming done") — exactly the self-judging arrangement cross-review is designed to break. The optional review hook in that spec (lines 54-55, "use the security review ... for security-, policy-, secret-, or command-execution-sensitive changes") is a manual, advisory step, not an enforced author-distinct gate. The severity vocabulary that the "it matters" criteria reuse is the P0-P3 model in `count_audit_severities` of `shared/scripts/validate_planner_docs.py` (lines 483-488). No current test asserts that one actor's output is judged by another, so the cross-review tests proposed here are a new surface aligned with the existing `tests/` style.

## 7. Planned Work Breakdown

- F4.4-01 — Define the four-role responsibility model
  - Description: Specify Analyzer (read-only findings), Fixer (write-under-isolation), Verifier (runs validation, reports pass/fail), and Reviewer (independent keep/revert verdict), with each role's capabilities and write-access boundaries.
  - Output: a role-capability table with allowed actions and write-access per role.
- F4.4-02 — Specify the "it matters" criteria
  - Description: Define when cross-review is mandatory (for example security-category findings, P0/P1 severity, writes to sensitive/allowlisted-but-critical paths) versus optional, sourcing thresholds from the Phase 4.1 policy.
  - Output: a criteria specification mapping finding attributes to mandatory-versus-optional cross-review.
- F4.4-03 — Author-distinct-from-reviewer rule
  - Description: Define that for a mattering fix the reviewing role must differ from the authoring role, and the model/family should differ where the host can assign it; specify the fallback when only one model is available.
  - Output: a distinctness specification including the single-model fallback (a distinct role still reviews, and the limitation is recorded).
- F4.4-04 — Cross-review verdict composition with verification
  - Description: Define the keep/revert verdict contract and how it combines with the Phase 3 verification result at the Phase 4.2 promotion gate: promote only on verification-pass and keep-verdict; demote otherwise.
  - Output: a verdict-composition truth table (verification x cross-review -> promote/demote).
- F4.4-05 — Self-approval block
  - Description: Define that a mattering fix whose reviewer equals its author is an out-of-policy, blocked action with a stable reason code, not a warning.
  - Output: a self-approval-block specification with the reason code.
- F4.4-06 — Cross-review test plan
  - Description: Specify a seeded-bad-fix fixture test (reviewer distinct from author catches and reverts the bad fix) and a self-approval-blocked test (author-as-reviewer on a mattering fix is denied).
  - Output: a test plan section naming proposed modules and their assertions.

## 8. Acceptance Criteria

- A four-role model is specified with each of Analyzer, Fixer, Verifier, and Reviewer having explicit, non-overlapping capabilities and write-access boundaries.
- The "it matters" criteria deterministically classify each fix as requiring mandatory cross-review or eligible for optional review, sourced from the Phase 4.1 policy thresholds.
- For any mattering fix, the reviewing role differs from the authoring role, with model/family distinctness applied where the host supports it and the single-model fallback recorded as a limitation.
- The verdict-composition rule promotes a mattering fix only when verification passes and the reviewer returns keep, and demotes it via the reversal handle otherwise.
- A self-approval of a mattering fix is blocked with a stable reason code, demonstrated by a test.
- A seeded-bad-fix fixture is caught and reverted by a distinct reviewer, demonstrating the cross-review catch.
- Local readiness (cross-review gating assertable on a seeded fixture) is separated from live readiness (cross-review across genuinely distinct models in an unattended run), which is confirmed in Phase 5 eval and Phase 6 parity.
- No secrets, tokens, or credentials appear in any role specification, fixture description, or plan text.

## 9. Validation and Test Approach

- Document validation: run `python3 shared/scripts/validate_planner_docs.py --root . --mode step2 --strict` to confirm structure and absence of placeholder tokens.
- Local smoke (proposed): a proposed `tests/test_cross_review.py` using a seeded-bad-fix fixture, asserting a reviewer distinct from the author returns a revert verdict and the fix is demoted.
- Local smoke (proposed): a proposed self-approval-blocked test asserting that assigning the author as the reviewer of a mattering fix yields a deny verdict with a reason code and no promotion.
- Local validation: assert the verdict-composition truth table — every (verification, cross-review) combination maps to the expected promote/demote outcome.
- CI: add the cross-review tests to `make check` so they run via `.github/workflows/validate.yml`.
- Live readiness: deferred — cross-review across genuinely different model families and its measured catch rate are validated by the Phase 5 eval harness and the Phase 6 multi-host work, not here.

## 10. Dependencies and Sequencing

- Depends on Phase 4.1 for the policy thresholds that drive the "it matters" criteria and the reviewer-required flag.
- Depends on Phase 4.2 for the promotion gate into which the cross-review verdict plugs, and on Phase 3 for the verification result and reversal handles the verdict composition relies on.
- Depends on Phase 4.3 only in that cross-review adds latency/iterations that must stay within the budget ceilings defined there.
- Requires a human decision (Main-Planning section 9 open question (e)) on the supported model-assignment surface per host, since true model/family distinctness depends on what each host exposes; the single-model fallback covers hosts that cannot assign a distinct reviewer model.
- Requires no live credentials for the seeded-fixture tests; genuine multi-model cross-review may require host model access, confirmed later.

## 11. Risks and Mitigations

- Risk: only one model is available, so "distinct reviewer" collapses back to self-review. Impact: the conflict-of-interest the gate exists to remove returns. Mitigation: enforce a distinct *role* even on one model, record the single-model limitation explicitly, and keep verification as an independent second check.
- Risk: the "it matters" criteria are drawn too narrowly and a genuinely risky fix skips cross-review. Impact: a confidently-wrong high-impact patch is promoted unreviewed. Mitigation: default the criteria to include all security-category and P0/P1 fixes and all sensitive-path writes, and make widening (not narrowing) the safe direction.
- Risk: cross-review and verification verdicts are combined inconsistently, allowing promotion on a partial pass. Impact: a fix lands without both gates clearing. Mitigation: an explicit truth table requiring both verification-pass and keep-verdict for promotion, asserted by tests.
- Risk: cross-review inflates iteration/token cost on every fix. Impact: budget exhaustion or slow runs. Mitigation: make cross-review mandatory only for "matters" fixes and optional otherwise, keeping low-risk fixes single-gated within the Phase 4.3 budgets.

## 12. Desired End State

QB's autonomy includes a separation-of-powers guarantee: Analyzer, Fixer, Verifier, and Reviewer are distinct roles with bounded capabilities, and a fix that matters is promoted only when an independent reviewer (a different role, and a different model/family where the host allows) returns keep *and* verification passes. A fix's author can never be the sole judge of a mattering fix — self-approval is blocked with a reason code. A seeded-bad-fix fixture is caught and reverted, and the verdict-composition truth table is enforced by tests green under `make check`. This completes Phase 4: an end-to-end run is now policy-bounded (4.1), level-enforced (4.2), resource-bounded and stoppable (4.3), and cross-reviewed (4.4), ready for the reproducible reporting and eval-measured catch rate of Phase 5.

## 13. Transition Criteria to the Next Sub-Phase

- The four-role model, "it matters" criteria, and author-distinct-from-reviewer rule are specified and internally consistent.
- The verdict-composition truth table requires both verification-pass and keep-verdict for promotion of a mattering fix, with demotion otherwise.
- A seeded-bad-fix fixture catch and a self-approval-blocked path are both specified as tests aligned with `tests/` conventions.
- The single-model fallback is documented so hosts without distinct model assignment still get a distinct reviewing role plus independent verification.
- Phase 4 is complete: the policy engine, level enforcement, budgets/kill-switch, and cross-review compose into one fail-closed unattended run, and the remaining work (reproducible JSON/SARIF reporting and the eval harness that measures cross-review catch rate) is explicitly carried into Phase 5.
