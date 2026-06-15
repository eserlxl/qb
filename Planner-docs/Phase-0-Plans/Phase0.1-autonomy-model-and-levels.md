# Phase 0.1 — Autonomy Model and Levels (A0-A3)

## 1. Context

This sub-phase opens Phase 0 (Autonomy Charter & Foundation) and sits directly under the master-plan goal of defining what "full autonomous" safely means for QB before any engine code is written. Main-Planning.md §5 already names four autonomy levels (A0 report-only, A1 propose, A2 apply-verified, A3 deliver) and §1 frames the central tension: QB's current identity is "pause for explicit human approval at every gate," while the pivot target is "full autonomous." Autopsy AUTOPSY-P1-01 records that no policy/autonomy/budget engine exists today and that "safety is prompt-only," so the autonomy ladder must be ratified on paper here before Phase 4 turns it into a runtime engine. The current repository state is a mature gated planning workflow whose only enforcement primitive relevant to autonomy is `validate_step4_readiness` in `shared/scripts/validate_planner_docs.py`, which blocks a single human-gated implementation step on P0/P1 findings. This sub-phase converts that single implicit gate into an explicit, named, multi-level ladder.

## 2. Goal

Produce a ratified, unambiguous autonomy ladder that defines the exact write-capability, isolation target, verification obligation, and stop condition of each level A0 through A3, names the conservative default level, and states the fail-closed downgrade rule so that any future orchestrator can map a requested autonomy level to a deterministic behavioral contract with no interpretive gaps.

## 3. Description

The problem this sub-phase solves is that "full autonomous" is currently a slogan, not a specification: there is no written definition of what a given autonomy level may write, where it may write, what it must verify first, and when it must stop. Without that ladder, every downstream phase would invent its own notion of "autonomous," producing inconsistent and unsafe behavior. This work belongs at the very front of the roadmap because the Finding schema (Phase 1), the analyzer suite (Phase 2), the fixer (Phase 3), and especially the policy engine (Phase 4) all consume the autonomy contract as an input; freezing it first prevents churn. It reduces project risk by making the dangerous transition from read-only to write-capable explicit and graduated rather than a single binary switch, and by pinning the most aggressive behaviors (A3 deliver) behind an opt-in that defaults off. It prepares later phases by giving the policy engine a finite, enumerated set of behavioral targets to enforce and by giving the fixer a precise statement of which isolation target (working tree versus throwaway branch/worktree) applies at each level.

## 4. Scope

- A definition table for levels A0, A1, A2, A3 with columns for write capability, write target, verification obligation, rollback obligation, and commit/push/PR permission.
- The default autonomy level for an unconfigured run, stated explicitly with rationale.
- The fail-closed downgrade rule: how an unknown, ambiguous, or unparseable autonomy request maps to report-only.
- A precise behavioral contract paragraph per level, written so it can later be asserted by a test.
- The mapping from each level to its isolation target (no writes / throwaway branch / working tree with auto-revert / reviewable changeset).
- The relationship between autonomy level and the existing P0-P3 severity grading inherited from the validator.

## 5. Out of Scope

- The declarative policy schema and budget model (these are sketched in Phase 0.3 and frozen in Phase 4).
- Any executable policy engine, runtime enforcement, or kill-switch implementation.
- The Finding schema fields, analyzer interface, or fixer isolation mechanism (Phases 1 and 3).
- Machine-readable report formats, JSON/SARIF, telemetry, or evidence-store layout.
- Multi-host launch surfaces and the headless/CI entry point.
- Any modification to the existing planning workflow behavior (covered by the non-regression contract in Phase 0.2).

## 6. Current Repository Evidence

The only autonomy-adjacent enforcement present today is `validate_step4_readiness` in `shared/scripts/validate_planner_docs.py` (lines 491-516), which is effectively a single hard gate: it blocks the gated implementation step when audit status is `BLOCKED` or when P0/P1 findings are counted by `count_audit_severities`. The fixer seed `shared/planners/fourth-planner.md` documents a "no commit, push, PR, deploy, or external mutation unless the user explicitly asks" rule, which is the prose ancestor of the A3 opt-in but encodes no graduated levels. Main-Planning.md §5 lists the A0-A3 names and §3 confirms there is "no autonomy/policy layer." There is no levels table, no default-level statement, and no fail-closed downgrade rule anywhere in the tree. The validator's severity vocabulary (`P0`, `P1`, `P2`, `P3` in `count_audit_severities`, lines 483-488) is the existing grading the autonomy ladder must align with rather than reinvent.

## 7. Planned Work Breakdown

- F0.1-01 — Autonomy levels definition table
  - Description: Author the canonical A0/A1/A2/A3 table fixing write capability, write target, verification obligation, rollback obligation, and commit/push/PR permission per level.
  - Output: a levels table embedded in this sub-plan and earmarked for a future `shared/` charter artifact.
- F0.1-02 — Default level and conservatism rationale
  - Description: Select the default level for an unconfigured run and justify why the default is conservative, tying it to the master-plan statement that "the default is conservative."
  - Output: a written default-level decision with rationale and the note that A3 is never the default.
- F0.1-03 — Fail-closed downgrade rule
  - Description: Specify deterministically how unknown, malformed, or ambiguous autonomy requests collapse to A0 report-only, including ambiguity sources (missing policy, unparseable level token, conflicting flags).
  - Output: a downgrade rule statement suitable for later assertion by a policy test.
- F0.1-04 — Per-level behavioral contracts
  - Description: Write one precise behavioral-contract paragraph per level describing observable run behavior, the isolation target, and the stop conditions.
  - Output: four contract paragraphs phrased as testable assertions.
- F0.1-05 — Severity-to-autonomy alignment note
  - Description: Document how P0-P3 severities interact with autonomy levels (for example, which severities a given level may auto-act on) without freezing thresholds, which belong to Phase 4.
  - Output: an alignment note that references the validator's existing severity vocabulary.

## 8. Acceptance Criteria

- This sub-plan contains a levels table covering A0, A1, A2, A3 where each row states write capability, write target, verification obligation, and commit/push/PR permission.
- A single default autonomy level is named for an unconfigured run, with an explicit statement that A3 (deliver) is never enabled by default.
- The fail-closed downgrade rule is written so an implementer can later assert "ambiguous or unknown request resolves to A0 report-only" as a unit test.
- Each of A0-A3 has a distinct behavioral-contract paragraph that names its isolation target and never describes two levels with identical write behavior.
- Local readiness (the paper ladder is internally consistent and free of contradictions) is distinguished from live readiness (no engine enforces it yet, stated plainly).
- No autonomy decision in this file writes or implies writing secrets, tokens, or credentials into any output.

## 9. Validation and Test Approach

Document validation for this sub-phase is the primary gate now: run `python3 shared/scripts/validate_planner_docs.py --strict` from the repository root to confirm the file passes heading-order, placeholder, and anti-boilerplate checks, and run `python3 -m unittest discover -s tests` to confirm no monorepo invariant regressed. A focused human review must confirm the four level contracts are mutually exclusive in write behavior and that the downgrade rule is deterministic. Live readiness is explicitly not testable here because no orchestrator exists yet; the future proposed test is a policy-engine unit test (Phase 4) asserting that a request for an unknown level yields A0 and that the default level matches this charter. Security validation at this stage is limited to the secret-pattern scan already performed by the validator's `scan_secrets`. Artifact validation is the confirmation that this file is the single home of the levels table with no duplicate ladder elsewhere.

## 10. Dependencies and Sequencing

This sub-phase has no upstream sub-plan dependency and should run first within Phase 0 because Phase 0.2 (safety invariants) references the levels by name and Phase 0.3 (policy/budget concept) maps policy fields onto these levels. It requires one human decision to ratify the default level and to confirm that A3 remains opt-in only; per Main-Planning.md §9 decision (a), the default autonomy level and whether A3 is ever default need human confirmation. No credentials, live endpoints, or infrastructure are required. It blocks the Phase 4 policy engine, which cannot be specified until the level set is frozen.

## 11. Risks and Mitigations

- Risk: the level definitions are too vague to enforce later. Impact: Phase 4 reinvents semantics and drifts from this charter. Mitigation: phrase every level contract as a single testable assertion and require the per-level write target to be unambiguous.
- Risk: a permissive default level is chosen, eroding QB's conservative identity. Impact: unattended runs could write to the working tree by default, surprising users. Mitigation: pin the default to a read-only or propose-only level and force A2/A3 to be explicit opt-ins, mirroring the existing no-auto-mutation prose in `shared/planners/fourth-planner.md`.
- Risk: the fail-closed downgrade rule has gaps for partially-specified requests. Impact: an ambiguous request silently runs at an unintended level. Mitigation: enumerate the ambiguity sources (missing policy, unparseable token, conflicting flags) and map every one to A0 report-only.
- Risk: the ladder contradicts the severity grading already used by the validator. Impact: confusing dual vocabularies for risk. Mitigation: explicitly reuse the P0-P3 vocabulary from `count_audit_severities` and document the interaction rather than introducing a parallel scale.

## 12. Desired End State

After this sub-phase, QB has a single, ratified autonomy ladder: A0 report-only writes nothing; A1 propose writes only to a throwaway branch/worktree and never to the user's working tree; A2 apply-verified writes verified fixes to the working tree and auto-reverts the rest; A3 deliver adds a reviewable changeset or optional PR and is opt-in only. The default for an unconfigured run is fixed at the conservative end, A3 is never default, and any unknown or ambiguous autonomy request deterministically downgrades to A0. The contract is internally consistent, free of contradictions, and ready to be consumed verbatim by the Phase 4 policy engine. No runtime yet enforces it; that gap is stated rather than hidden.

## 13. Transition Criteria to the Next Sub-Phase

Before moving to Phase 0.2, the four level contracts must be written down, mutually exclusive in write behavior, and free of internal contradictions; the default level and the A3-opt-in stance must be ratified by the human operator; the fail-closed downgrade rule must cover every enumerated ambiguity source; and `python3 shared/scripts/validate_planner_docs.py --strict` plus `python3 -m unittest discover -s tests` must both pass with only Planner-docs/ changed. Live enforcement must not be attempted in this sub-phase; that work is deferred to Phase 4.
