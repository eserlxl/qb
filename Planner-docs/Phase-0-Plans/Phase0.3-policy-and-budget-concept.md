# Phase 0.3 — Policy and Budget Concept

## 1. Context

This sub-phase closes Phase 0 by sketching, at the concept level, the declarative policy that decides what an autonomous run may auto-fix and the budget model that bounds how much a run may do. Main-Planning.md §5 describes a "declarative policy" governing fixable categories/severities, confidence thresholds, write-path allowlists, and commit permission, and §4 lists budgets as "max findings, max fixes, max iterations, max wall-time/tokens." Autopsy AUTOPSY-P1-01 records that no policy or budget engine exists and that the pivot's identity tension "must be resolved on paper before any code." This sub-phase produces that paper resolution at concept fidelity only: it names the policy and budget dimensions, shows how they sit on top of the autonomy ladder from Phase 0.1 and respect the invariants from Phase 0.2, and flags the decisions that need human confirmation. The frozen schema itself is explicitly deferred to Phase 4.

## 2. Goal

Define the conceptual shape of a declarative policy and a budget model — the dimensions each must express, how they bind to autonomy levels and severity grading, and the fail-closed defaults — so that Phase 4 can later freeze a concrete schema without rediscovering the design space, while clearly marking which choices require human ratification before implementation.

## 3. Description

Without a policy concept, "autonomous" has no governable surface: there is nothing that says which finding categories may be touched, how confident a finding must be before a fix is applied, where writes are permitted, or whether a commit is allowed. Without a budget concept, an unattended loop over a large repository can spin without bound, burning tokens and wall-time, which Main-Planning.md §7 names as a runaway-cost risk. This sub-phase sketches both as declarative concepts so the orchestrator can be driven by data rather than hard-coded behavior. It belongs at the end of Phase 0 because the policy maps onto the autonomy levels (Phase 0.1) and must respect the safety invariants (Phase 0.2), so both must be settled first. It reduces risk by forcing the dangerous knobs — auto-fixable severities, confidence cutoff, write allowlist, commit permission, and the hard budget ceilings — to be enumerated and defaulted conservatively now, on paper, where they are cheap to debate. It prepares Phase 4 by handing the policy engine a ready conceptual map and a list of human-confirmation items, and it prepares Phase 1 indirectly by confirming that the Finding schema must carry a confidence field the policy can threshold against.

## 4. Scope

- The conceptual policy dimensions: which finding categories and severities are auto-fixable, the confidence threshold, write-path/glob allowlists, and whether commit/push/PR is permitted for a run.
- The conceptual budget dimensions: maximum findings, maximum fixes, maximum iterations, maximum wall-time, and maximum tokens/cost.
- How policy and budget bind to the A0-A3 levels (for example, A0 ignores fix-related policy because it never writes).
- The fail-closed default posture: unknown policy resolves to report-only; a hit budget stops-and-reports.
- The offline-core versus opt-in-networked split as it touches policy (for example, enabling networked CVE analyzers as a policy choice).
- A list of decisions that require human confirmation before the Phase 4 schema is frozen.

## 5. Out of Scope

- Freezing the concrete policy or budget schema, field names, types, or file format — these are deliberately deferred to Phase 4.
- Any policy-engine implementation, parser, validator extension, or runtime enforcement.
- The autonomy level definitions (Phase 0.1) and the safety invariant list (Phase 0.2), which this file consumes but does not author.
- The Finding schema field set (Phase 1), beyond noting that a confidence field is required for thresholding.
- Telemetry, kill-switch implementation, and observability formats (Phase 7).
- Per-analyzer category specifics and command schemas (Phase 2).

## 6. Current Repository Evidence

No policy file format, threshold mechanism, or budget model exists anywhere in the repository; the only data-driven gating present is the validator's `validate_step4_readiness`, which applies a fixed, non-configurable rule (P0/P1 block; `BLOCKED` status blocks) in `shared/scripts/validate_planner_docs.py` lines 491-516. That fixed rule is the conceptual ancestor of a configurable severity policy but is not declarative — it cannot be tuned by data. The severity vocabulary the policy must threshold against (`P0`-`P3`) is established by `count_audit_severities` (lines 483-488), and the secret-scan prohibition the policy must never override lives in `scan_secrets` (lines 519-534). There is no confidence field anywhere yet, because the Finding schema is unwritten (autopsy AUTOPSY-P0-01); the policy concept must therefore assume confidence will be introduced in Phase 1. There is no budget primitive, no iteration counter, and no wall-time or token accounting in the codebase.

## 7. Planned Work Breakdown

- F0.3-01 — Policy dimension sketch
  - Description: Enumerate the declarative policy dimensions (auto-fixable categories/severities, confidence threshold, write-path allowlist, commit/push/PR permission) at concept level without fixing field names.
  - Output: a policy-dimension list annotated with conservative default postures.
- F0.3-02 — Budget dimension sketch
  - Description: Enumerate the budget dimensions (max findings, max fixes, max iterations, max wall-time, max tokens/cost) and the stop-and-report behavior when any ceiling is reached.
  - Output: a budget-dimension list with the fail-closed stop semantics described.
- F0.3-03 — Policy/budget-to-autonomy binding
  - Description: Describe how each dimension applies (or does not apply) per autonomy level, anchored to the Phase 0.1 ladder.
  - Output: a binding note showing, for example, that fix-policy is inert at A0 and that commit permission only matters at A3.
- F0.3-04 — Fail-closed default posture
  - Description: State that an unknown/unparseable policy collapses to report-only and that any breached budget halts the run and reports, consistent with the Phase 0.2 invariants.
  - Output: a fail-closed default statement reusable by the Phase 4 engine.
- F0.3-05 — Human-confirmation decision register
  - Description: Capture the choices that need operator ratification before the schema is frozen, drawn from Main-Planning.md §9 (default autonomy, networked-analyzer scope, output-dir sharing, refactor-vs-wrap, headless surface).
  - Output: a decision register marking each item as requiring human confirmation during implementation.

## 8. Acceptance Criteria

- This sub-plan enumerates the policy dimensions (auto-fixable categories/severities, confidence threshold, write-path allowlist, commit/push/PR permission) with a conservative default stated for each, and explicitly marks them concept-level pending the Phase 4 freeze.
- The budget model lists all five ceilings (findings, fixes, iterations, wall-time, tokens/cost) and describes the stop-and-report behavior triggered when any one is reached.
- Each policy and budget dimension is bound to the autonomy ladder so it is clear which level activates it.
- A fail-closed default is stated: an unknown policy yields report-only and a breached budget halts the run.
- The decisions requiring human confirmation are listed and each is phrased to be confirmed during implementation rather than asserted as already decided.
- The concept stays at concept fidelity (no frozen schema, no field types) and contains no secret values, endpoints, or credentials.

## 9. Validation and Test Approach

Validation here is concept-completeness checking rather than runtime testing: run `python3 shared/scripts/validate_planner_docs.py --strict` to confirm the document is structurally sound and placeholder-free, and run `python3 -m unittest discover -s tests` to confirm no invariant regressed. A human review must confirm that every dimension named in Main-Planning.md §4 and §5 is present in the concept and that the human-confirmation register matches §9's open decisions. Live readiness is not applicable because no policy engine exists; the proposed future gate is a Phase 4 fail-closed policy test asserting that an unknown policy yields report-only and that a budget breach halts and reports. Security validation is limited to confirming the concept never permits a policy to override the secret-scan prohibition. Document artifact validation confirms this is the sole home of the policy/budget concept and that it forward-references Phase 4 for the schema freeze rather than freezing it here.

## 10. Dependencies and Sequencing

This sub-phase depends on Phase 0.1 (the autonomy ladder the policy binds to) and Phase 0.2 (the invariants the policy must respect), so it runs last within Phase 0. It also has a soft forward dependency on Phase 1: the policy's confidence threshold presumes the Finding schema will carry a confidence field, so Phase 1 must honor that. It requires several human decisions before the Phase 4 schema can be frozen — Main-Planning.md §9 lists the default autonomy level and A3 default-enable question, whether networked CVE analyzers are in scope for v1, whether planning and auditing share one output tree, how aggressively to refactor versus wrap the validator, and the supported headless/CI surface. No credentials or infrastructure are required for this concept-level work. It blocks Phase 4, which freezes the schema this concept describes.

## 11. Risks and Mitigations

- Risk: the concept hardens into a premature schema and constrains Phase 4. Impact: rework when the real schema is frozen against the stabilized Finding model. Mitigation: keep this strictly at concept fidelity, naming dimensions and defaults but never field names or types, and forward-reference Phase 4 for the freeze.
- Risk: a policy dimension is omitted and an unsafe action becomes ungoverned. Impact: an autonomous run takes an action no policy can forbid. Mitigation: cross-check the dimension list against Main-Planning.md §4 and §5 and against the Phase 0.2 invariants so every dangerous action has a governing dimension.
- Risk: budgets are advisory rather than enforced in the concept. Impact: a runaway loop is not actually bounded, matching the cost-blowup risk in Main-Planning.md §7. Mitigation: define budgets as hard ceilings with explicit stop-and-report semantics, not soft targets.
- Risk: a policy is allowed to relax a safety invariant such as the secret prohibition. Impact: policy data could be used to disable a non-negotiable safeguard. Mitigation: state that policy may only tighten, never loosen, the Phase 0.2 invariants, and that the secret-scan prohibition is not policy-overridable.

## 12. Desired End State

After this sub-phase, QB has a concept-level map of its governance surface: a declarative policy that names which categories and severities are auto-fixable, the confidence threshold, the write-path allowlist, and the commit/push/PR permission, each with a conservative default; and a budget model with five hard ceilings (findings, fixes, iterations, wall-time, tokens/cost) and stop-and-report semantics. Both are bound to the A0-A3 ladder and constrained to only ever tighten the safety invariants. A decision register marks the open choices needing human confirmation before Phase 4 freezes the schema. The schema itself is deliberately not frozen here; that boundary is stated, so Phase 4 inherits a clear concept rather than an accidental specification.

## 13. Transition Criteria to the Next Sub-Phase

Phase 0.3 completes Phase 0, so the transition criteria govern entry to Phase 1 (Findings Model & Audit Engine). Before that transition, the policy and budget dimensions must be fully enumerated with conservative defaults and bound to the autonomy ladder; the fail-closed default and budget stop-and-report semantics must be written; the policy-may-only-tighten-invariants rule must be stated; the human-confirmation decision register must be complete and aligned with Main-Planning.md §9; and `python3 shared/scripts/validate_planner_docs.py --strict` plus `make check` must pass with only Planner-docs/ changed. The confidence-field expectation must be carried forward so Phase 1 designs the Finding schema to support policy thresholding. No schema freeze and no engine work may begin in Phase 0.
