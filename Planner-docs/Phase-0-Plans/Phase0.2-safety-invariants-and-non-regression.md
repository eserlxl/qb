# Phase 0.2 — Safety Invariants and Planning-Product Non-Regression Contract

## 1. Context

This sub-phase continues Phase 0 by pinning down the non-negotiable safety rules that bound every later phase, and by writing the explicit promise that QB's existing five-step planning workflow keeps working unchanged through the pivot. Main-Planning.md §2 states what "must never be compromised" — safety and reversibility — and §7 lists the identity/scope-drift risk that "bolting on an auditor can produce two half-products." The autopsy reinforces this: §11 confirms the planning product is mature with 13 test modules and a clean `make check`, while AUTOPSY-P3-01 warns documentation and behavior could diverge at the pivot. This sub-phase therefore has two halves: enumerate the invariants the autonomous engine may never violate, and bind the pivot to a regression contract so the planning product survives intact. It depends on Phase 0.1 because several invariants reference the autonomy levels by name.

## 2. Goal

Establish a closed list of safety invariants that hold at every autonomy level and an enforceable non-regression contract stating exactly which existing planning-workflow behaviors, artifact names, and validation gates must remain unchanged, so that any future engine change can be checked against a fixed safety boundary and the planning product cannot silently regress.

## 3. Description

Two distinct gaps motivate this work. First, today's safety is prompt-only: the rules live as prose in `shared/planners/fourth-planner.md` and as a single readiness gate in the validator, with no consolidated, authoritative invariant list. Second, the pivot introduces write-capable behavior alongside a planning product that 100% of the current tests validate, so without an explicit contract the planning workflow could regress unnoticed while attention is on the new engine. This sub-phase consolidates the scattered prose into a numbered invariant set and turns "the planning product keeps working" from an assumption into a contract with named preserved artifacts and named preserved tests. It belongs here because invariants are the safety floor that Phases 1-7 build on; defining them after code exists would mean retrofitting safety. It reduces risk by making "never apply an unverified change" and "fail closed on ambiguity" auditable statements rather than aspirations, and it prepares later phases by giving the policy engine and fixer a fixed set of prohibitions to enforce and a fixed set of legacy behaviors to leave alone.

## 4. Scope

- A numbered list of safety invariants that hold at every autonomy level (no unverified change applied, no secret written or printed, no action outside policy, no commit/push/PR without opt-in, fail closed on ambiguity).
- A mapping of each invariant to the master-plan or autopsy evidence that motivates it.
- The non-regression contract enumerating the preserved planning artifacts (fixed `Planner-docs/` names) and preserved planning behaviors.
- The list of existing tests and gates (`make check`, `scripts/sync.sh --check`, the `tests/` modules) that must continue to pass unchanged.
- A statement of how the planning and auditing products coexist (shared infrastructure, one validator/finding model rather than two stacks).
- The redact-by-default principle for all current and future outputs.

## 5. Out of Scope

- The autonomy level definitions themselves (owned by Phase 0.1) — this file references them but does not redefine them.
- The policy schema and budget thresholds (Phase 0.3 concept, Phase 4 freeze).
- Any new test implementation; this sub-phase names which tests must keep passing but does not write code.
- The Finding schema, analyzer interface, fixer isolation mechanism, or reporting format.
- The output-directory naming convention for the auditing product (a Phase 0/Phase 1 contract decision, not a safety invariant).
- Refactoring of the validator (Phase 1 handles the refactor with its own non-regression test).

## 6. Current Repository Evidence

Safety prose is fragmented across the repo: `shared/planners/fourth-planner.md` carries "no commit, push, PR, deploy, or external mutation unless the user explicitly asks" and "verify with fresh evidence before claiming done," while the validator enforces only the single `validate_step4_readiness` gate. The planning product's preserved surface is concrete and inspectable: `Planner-docs/Main-Planning.md`, `Planner-docs/Autopsy.md`, the `Phase-<n>-Plans/` folders, `Sub-Planning-Index.md`, and `Sub-Planning-Audit.md` are the fixed names the validator hard-binds to (paths throughout `shared/scripts/validate_planner_docs.py`). The protective test surface is real: `tests/` holds 12 modules including `test_no_committed_secrets.py`, `test_no_cross_host_residue.py`, `test_sync_mechanism.py`, `test_sync_map_completeness.py`, and `test_spec_validator_contract.py`, gated by `make check` and CI at `.github/workflows/validate.yml`. The secret-prohibition invariant has direct backing in `SECRET_PATTERNS` and `scan_secrets` (validator lines 113-120, 519-534). No consolidated invariant list and no written non-regression contract exist yet.

## 7. Planned Work Breakdown

- F0.2-01 — Safety invariant enumeration
  - Description: Write the closed, numbered list of invariants holding at every autonomy level, each phrased as a prohibition or a fail-closed obligation.
  - Output: a numbered invariant set ready to be promoted into a future `shared/` charter artifact.
- F0.2-02 — Invariant-to-evidence mapping
  - Description: Tie each invariant to its motivating master-plan section or autopsy finding so the list is grounded rather than asserted.
  - Output: a mapping note linking invariants to §2/§7 of Main-Planning.md and to autopsy §9/§13.
- F0.2-03 — Preserved-artifact register
  - Description: List the fixed planning artifact names that must remain stable through the pivot, drawn from the validator's hard-bound paths.
  - Output: an artifact register naming `Planner-docs/` files the validator depends on.
- F0.2-04 — Preserved-test register and gate contract
  - Description: Name the existing tests and gates (`make check`, sync drift check, the 12 `tests/` modules) that must keep passing unchanged as the engine is added.
  - Output: a test/gate register stating the non-regression pass condition.
- F0.2-05 — Coexistence and redaction principles
  - Description: State how the two products share one validator/finding model and that all outputs redact secrets by default.
  - Output: a coexistence-and-redaction principle note.

## 8. Acceptance Criteria

- This sub-plan contains a numbered, closed list of safety invariants, each holding at every autonomy level and each phrased so a reviewer can check compliance of a future change against it.
- Every invariant is mapped to at least one concrete source (a Main-Planning.md section or an autopsy finding identifier).
- The non-regression contract names the specific preserved `Planner-docs/` artifacts and the specific preserved `tests/` modules and gates that must continue to pass unchanged.
- The contract states plainly that `make check` and CI must stay green throughout the pivot and that no planning-workflow behavior is removed.
- Local readiness (the invariant list is complete and self-consistent on paper) is separated from live readiness (no engine enforces the invariants yet).
- The redact-by-default rule is stated, and the file itself contains no secret values, tokens, or credentials.

## 9. Validation and Test Approach

The validation distinction here is sharper than elsewhere because this sub-phase is itself about preserving validation: document validation runs `python3 shared/scripts/validate_planner_docs.py --strict` to confirm structure and absence of placeholders; the non-regression baseline is `make check`, which chains `scripts/sync.sh --check`, the three per-platform `validate.sh`, and `python3 -m unittest discover -s tests`, and must remain green. Local smoke is the unchanged behavior of the planning workflow against fixture `Planner-docs/` inputs. Live readiness is explicitly out of reach because the invariant-enforcing engine does not exist; the proposed future gate is a safety-invariant conformance test (Phase 4) asserting each prohibition is enforced by the engine. Security validation reuses the existing `test_no_committed_secrets.py` plus the validator's `scan_secrets`. CI validation is the existing `.github/workflows/validate.yml` run, which must not be weakened by the pivot.

## 10. Dependencies and Sequencing

This sub-phase depends on Phase 0.1 because invariants such as "never commit/push/PR without opt-in" reference the A3 level by name and "fail closed on ambiguity" references the A0 downgrade target. It should run second within Phase 0, before Phase 0.3, because the policy concept must respect these invariants as hard constraints. It requires one human ratification that the invariant list is complete and that no planning behavior is being intentionally dropped. No credentials, infrastructure, or live endpoints are needed. It blocks every later write-capable phase, since the fixer (Phase 3) and policy engine (Phase 4) must enforce this exact invariant set and preserve the named planning gates.

## 11. Risks and Mitigations

- Risk: the invariant list is incomplete and a dangerous behavior slips through unbounded. Impact: an autonomous run could violate an unstated rule with no gate to catch it. Mitigation: derive invariants directly from Main-Planning.md §2 and §7 and from the autopsy P0-P3 findings, then require human sign-off that the list is closed.
- Risk: the planning product silently regresses while engineering focus is on the new engine. Impact: existing users of the planning workflow break and the regression is noticed late. Mitigation: bind the non-regression contract to named `tests/` modules and to `make check`, so any regression surfaces in CI rather than in production.
- Risk: the two products fork into separate, drifting stacks. Impact: duplicated validator logic, contradictory docs, doubled maintenance. Mitigation: codify the coexistence principle that there is one validator/finding model shared by both products.
- Risk: secrets leak into auditing outputs once the engine reads whole repositories. Impact: credential exposure in reports or evidence. Mitigation: state redact-by-default as an invariant now and extend the existing `scan_secrets` coverage in later phases rather than weakening it.

## 12. Desired End State

After this sub-phase, QB has an authoritative, numbered safety-invariant set — never apply an unverified change, never write or print secrets, never act outside policy, never commit/push/PR without explicit opt-in, and fail closed on ambiguity — each traceable to its motivating evidence and each holding at every autonomy level. It also has a written non-regression contract that names the preserved `Planner-docs/` artifacts and the preserved `tests/` modules and gates, and that commits the pivot to keeping `make check` and CI green throughout. The planning and auditing products are declared to share one validator/finding model. The invariants are not yet machine-enforced; that enforcement is assigned to Phase 4, and the gap is stated openly.

## 13. Transition Criteria to the Next Sub-Phase

Before moving to Phase 0.3, the safety-invariant list must be closed, numbered, and each item mapped to motivating evidence; the non-regression contract must name its preserved artifacts and tests and assert the `make check`/CI green condition; the human operator must confirm no planning behavior is being intentionally dropped; and `python3 shared/scripts/validate_planner_docs.py --strict` together with `make check` must pass with only Planner-docs/ changed. The policy concept in Phase 0.3 must treat this invariant set as a fixed constraint, not negotiate it.
