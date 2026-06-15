# Phase 3.1 — Fix Strategy and Finding Binding

## 1. Context

This sub-phase opens Phase 3 (Autonomous Hardening / Fixer), whose parent goal in `Planner-docs/Main-Planning.md` row 3 is to "Generalize the Step-4 implementer into a finding-driven fixer with isolation, mandatory verification, and auto-rollback." Phase 3.1 owns the front half of that sentence: the binding between an audit `Finding` (frozen in Phase 1) and a concrete, minimal patch plan, plus the rule that the verification command is chosen before any edit.

The reuse seed is `shared/planners/fourth-planner.md`. Its "Slice procedure" already says "Determine the validation/test command FIRST", "Make the minimal, reversible change", and "verify with fresh evidence" — but it is scoped to *plan slices selected from `Planner-docs/Sub-Planning-Audit.md`*, not to *audit findings*. The selection logic in that file (read `## 12. Step 4 Readiness Assessment`, pick one `READY` row) must be re-pointed at the Finding inventory produced by `qb-audit`. This sub-phase is therefore a generalization-and-binding task on top of an existing prose discipline.

It depends on the Phase 1 `Finding` schema (`id, category, severity P0-P3, confidence, evidence path:line, rationale, suggested-fix, fix-strategy`) per Main-Planning section 5 "Artifact/evidence boundaries", and it produces the per-finding fix plan that Phase 3.2 (isolation) and Phase 3.3 (verification gate) consume. It does not write any code or run any fix yet.

## 2. Goal

Define a deterministic, host-neutral fix-planning contract that turns a single `Finding` into a bounded patch plan: the `Finding.fix-strategy` field is bound to a named fix recipe, the verification command for that finding is selected first, and each finding category is classified as auto-fixable or propose-only with an explicit, evidence-backed reason. The outcome is a written contract (a new `shared/` planner artifact) that an implementer can execute one finding at a time without ambiguity about what changes, how it is proven, and whether it may be auto-applied.

## 3. Description

The problem this sub-phase solves is that QB currently has a fixer *discipline* but no mapping from a machine-readable defect to a specific repair. `fourth-planner.md` assumes a human-audited plan slice with a known acceptance criterion; an autonomous fixer instead receives a `Finding` with only a `suggested-fix` string and a `fix-strategy` hint. Phase 3.1 closes that gap by specifying how each finding category resolves to a named, parameterized fix recipe (for example: remove-committed-secret-reference, replace-shell-string-with-argv-list, add-path-traversal-guard, apply-lint-autofix) and how the verification command is derived deterministically from the finding's evidence path and the repository's existing commands.

It belongs at the start of Phase 3 because both isolation (3.2) and the keep/revert gate (3.3) are meaningless without a defined unit of work to isolate and verify; you cannot roll back a change you never specified. The risk it reduces is "confidently-wrong autofix": by classifying categories as auto-fixable versus propose-only up front, and by requiring a verification command to exist before a patch is planned, low-confidence or unverifiable findings are routed to proposal rather than auto-application. This prepares Phase 4 (orchestrator/policy), which will read this auto-fixable-versus-propose-only classification when applying severity and confidence thresholds.

## 4. Scope

- A new host-neutral fixer-contract artifact under `shared/planners/` (working name `shared/planners/fixer-contract.md`) generalized from `shared/planners/fourth-planner.md`, registered in the `MAP` of `scripts/sync.sh`.
- A finding-to-recipe binding table: each `Finding.category` maps to one or more named fix recipes with required inputs (the finding's `evidence path:line`, `suggested-fix`, `fix-strategy`).
- A verification-command-selection rule that derives the per-finding verify command deterministically, preferring existing repo commands (`make test`, `make check`, a focused unit test) over invented ones.
- An auto-fixable versus propose-only classification per category, with the rationale and the confidence floor each category requires.
- Documentation of the inputs this contract consumes from the Phase 1 `Finding` schema and the outputs it hands to Phase 3.2 and Phase 3.3.

## 5. Out of Scope

- The isolation primitive (git branch/worktree) and the rollback handle — these are owned entirely by Phase 3.2.
- The keep/revert decision and before/after evidence recording — owned by Phase 3.3.
- Actually executing any fix, running any verification command for real, or writing to a working tree.
- The policy/budget engine, severity/confidence threshold enforcement, and autonomy levels A0-A3 selection — owned by Phase 4.
- The analyzers that produce findings (Phase 2) and the `Finding` schema definition itself (Phase 1); this sub-phase consumes them, it does not define them.
- Machine-readable report or SARIF emission (Phase 5).

## 6. Current Repository Evidence

`shared/planners/fourth-planner.md` is the only fixer-shaped artifact in the repository; lines 39-46 contain the "Slice procedure" with the determine-validation-command-first and verify-before-claiming-done steps, and lines 34-37 contain the selection logic bound to `Planner-docs/Sub-Planning-Audit.md` rather than to findings. No file maps a defect category to a repair recipe today. The `Finding` schema this sub-phase binds to is declared only in `Planner-docs/Main-Planning.md` section 5 and is not yet a `shared/` artifact, so Phase 3.1 must treat the schema as an upstream dependency, not as present evidence. The sync contract that any new artifact must join lives in `scripts/sync.sh` (its `MAP` and `--check` byte comparison), and the spec-to-validator heading contract is exercised by `tests/test_spec_validator_contract.py`. Current repository evidence for an executable finding-to-fix binding is otherwise limited; it exists only as the prose discipline in `fourth-planner.md`.

## 7. Planned Work Breakdown

- F3.1-01 — Generalize the fixer spec from slice-driven to finding-driven
  - Description: Author `shared/planners/fixer-contract.md` by re-pointing the `fourth-planner.md` selection logic from `Sub-Planning-Audit.md` plan slices to the Phase 1 `Finding` inventory, preserving the determine-validation-first and one-reversible-change rules.
  - Expected output: a new shared planner artifact whose unit of work is a single `Finding`, ready to be registered in `scripts/sync.sh`.
- F3.1-02 — Finding-to-recipe binding table
  - Description: Define the table mapping each `Finding.category` to named fix recipes (for example remove-committed-secret-reference, shell-string-to-argv, path-traversal-guard, lint-autofix), listing the required finding inputs for each recipe.
  - Expected output: a binding table embedded in the fixer-contract artifact with one row per category-to-recipe pairing.
- F3.1-03 — Deterministic verification-command selection rule
  - Description: Specify how the per-finding verify command is derived from the finding's `evidence path:line` and the repo's existing commands, with a documented fallback order when no focused test exists.
  - Expected output: a written selection algorithm that yields exactly one verify command per finding.
- F3.1-04 — Auto-fixable versus propose-only category classification
  - Description: Classify every finding category as auto-fixable or propose-only, each with a stated confidence floor and rationale grounded in fix-safety risk.
  - Expected output: a classification table the Phase 4 policy engine can later read as input.
- F3.1-05 — Upstream/downstream interface note
  - Description: Document precisely which `Finding` fields are consumed and which fix-plan fields are emitted for Phase 3.2 (isolation) and Phase 3.3 (verification gate).
  - Expected output: an interface section naming inputs and outputs with no undefined fields.

## 8. Acceptance Criteria

- `Planner-docs/Phase-3-Plans/Phase3.1-fix-strategy-and-finding-binding.md` names a concrete target artifact (`shared/planners/fixer-contract.md`) and states it must be added to the `scripts/sync.sh` `MAP`.
- The binding table covers every finding category named in Phase 2 planning, and any category left unbound is explicitly listed as propose-only with a reason.
- For every auto-fixable category, a deterministic verification-command-selection rule yields exactly one command, and the rule prefers existing repo commands over invented ones.
- The auto-fixable-versus-propose-only classification states a confidence floor for each category and never marks a category auto-fixable without a verification command being derivable.
- The document distinguishes what is decided now (the binding contract) from what depends on the not-yet-frozen Phase 1 schema, phrased as to be confirmed during implementation in plain words.
- No secret values, tokens, or credentials appear anywhere in the file.

## 9. Validation and Test Approach

Document validation: the new fixer-contract artifact, once authored in implementation, must pass the byte-equality drift gate `bash scripts/sync.sh --check` after registration in the `MAP`, and the existing `python3 -m unittest discover -s tests` suite must stay green (non-regression for the planning product). Proposed new test: a finding-binding conformance test (working name `tests/test_fixer_binding.py`) asserting that every Phase 1 `Finding.category` resolves to at least one recipe and that no auto-fixable category lacks a derivable verify command; this is proposed, not yet present. Security validation: confirm the contract never instructs writing secrets and that verify-command selection uses explicit argument lists (no shell-string interpolation), consistent with Main-Planning section 5. Distinguish document validation (drift check, heading contract) from local smoke (the proposed binding test) from live readiness (none here — this sub-phase performs no writes).

## 10. Dependencies and Sequencing

Hard upstream dependency: the Phase 1 `Finding` schema must be frozen as a `shared/` artifact (AUTOPSY-P0-01) before the binding table can name real fields; until then, field names are bound provisionally and confirmed during implementation. Soft dependency: the Phase 2 analyzer category list informs which categories the table must cover. This sub-phase blocks Phase 3.2 and Phase 3.3, because both need a defined unit of work and a chosen verification command. No live credentials, network access, or human approvals are required for this planning artifact. The decision on which categories are auto-fixable by default is an input the Phase 4 policy engine consumes but does not need resolved before Phase 3.2 begins.

## 11. Risks and Mitigations

- Risk: a category is marked auto-fixable but its findings have no reliable verification command. Impact: the fixer would apply changes it cannot prove, defeating the keep/revert gate. Mitigation: make a derivable verify command a hard precondition for the auto-fixable label, and default any category lacking one to propose-only.
- Risk: the binding over-fits to QB's own repository and fails on arbitrary target repos. Impact: recipes that assume `make`-based commands break on repos without a Makefile. Mitigation: specify a fallback order in the verification-command rule and require recipes to declare a no-command outcome that routes the finding to proposal.
- Risk: drift between the new fixer-contract artifact and the original `fourth-planner.md` confuses maintainers about which governs implementation. Impact: two competing fixer specs. Mitigation: state explicitly that the new artifact is the finding-driven successor and cross-reference the planning-slice path it generalizes.
- Risk: the not-yet-frozen `Finding` schema changes after this binding is written. Impact: stale field references. Mitigation: isolate field names in a single interface section so a schema change updates one place.

## 12. Desired End State

A single host-neutral fixer-contract artifact exists in plan-ready form that, for any incoming `Finding`, names the fix recipe, the deterministic verification command, and whether the category is auto-fixable or propose-only. The binding is complete (every category resolved), conservative (no auto-fix without a verify command), and clearly interfaced to the isolation and verification sub-phases. An implementer reading this contract can pick up one finding and know exactly what minimal change to plan, how it will be proven, and whether it may be applied automatically — with the actual application, isolation, and rollback still deferred to 3.2 and 3.3.

## 13. Transition Criteria to the Next Sub-Phase

Before starting Phase 3.2, the finding-to-recipe binding table must be complete with no category left unclassified, every auto-fixable category must have a derivable verification command, and the interface section must name the exact fix-plan fields handed downstream. The provisional-versus-frozen status of each consumed `Finding` field must be written down so Phase 3.2 isolates a well-defined unit of work. No working-tree writes or real verification runs may have occurred, since execution mechanics belong to the later sub-phases.
