# Phase 1.3 — Refactor the Validator Behind the Analyzer Interface

## 1. Context

Phase 1's parent goal in `Planner-docs/Main-Planning.md` §6 ends with the phrase "reusing the existing validator machinery" and its acceptance signal is "validator reused, not duplicated." The autopsy is sharper: AUTOPSY-P2-02 records that `shared/scripts/validate_planner_docs.py` is tightly coupled to `Planner-docs/` paths and planning headings, and the Phase-1 feedback in §12 directs Step 2 to "refactor (not wrap-only) the validator's `ValidationState` / severity counter / `scan_secrets` behind an analyzer interface, then run read-only over QB itself, with a non-regression test for the planning path." This sub-phase executes exactly that. It comes third in Phase 1 because it needs both the frozen Finding schema (Phase 1.1) and the analyzer interface (Phase 1.2) to refactor toward. Its defining constraint is that the planning product, which Main-Planning §1 commits to preserving, must keep behaving byte-identically after the refactor.

## 2. Goal

Extract the reusable, repository-agnostic machinery currently embedded in `shared/scripts/validate_planner_docs.py` — the fail-closed state machine (`ValidationState`), the P0-P3 severity counting (`count_audit_severities`), and the length-bounded secret scanning (`SECRET_PATTERNS` plus `scan_secrets`) — into components that implement or back the Phase 1.2 analyzer interface, while leaving the planning-document validation path producing identical output. The outcome is shared analysis machinery usable over an arbitrary repository, a planning-doc validator that is now a consumer of that shared machinery rather than the sole owner of it, and a non-regression test proving `make check` still passes unchanged.

## 3. Description

This is a behavior-preserving refactor whose risk is regression, not invention. The validator today fuses two concerns that this sub-phase must separate: generic analysis primitives (state accumulation with errors/warnings/metrics, severity tallying, secret pattern scanning, evidence string formatting) and planning-specific policy (the `Planner-docs/` path binding, the fixed planning headings in `SUBPLAN_HEADINGS` and `AUDIT_HEADINGS`, the Step-1 through Step-4 mode logic). The generic primitives are lifted into reusable components that the analyzer interface from Phase 1.2 can drive over any repository; the planning policy stays as a thin analyzer (or caller) layered on top, still reading `Planner-docs/`. This directly retires the AUTOPSY-P2-02 coupling without the duplication trap the autopsy warns against — a thin wrapper would leave two copies of the severity and secret logic to drift, whereas a real extraction gives one implementation with two callers. The secret scanner is especially valuable to share because Main-Planning §7's secret-leakage risk applies to the whole-repo audit, and `scan_secrets` already produces redacted `path:line` evidence rather than secret values. Because the extraction is invisible to the planning user, the non-regression test is the load-bearing safeguard.

## 4. Scope

- Extraction of `ValidationState` (or its error/warning/metrics core) into a reusable analysis-state component.
- Extraction of `count_audit_severities` severity tallying into a reusable P0-P3 counting component.
- Extraction of `SECRET_PATTERNS` and `scan_secrets` into a reusable, repository-agnostic secret-scanning component.
- Adapting these extracted components to back the Phase 1.2 analyzer interface (for example a secret-hygiene analyzer that returns Findings).
- Keeping the planning-document validation as a caller of the shared machinery with byte-identical output.
- A non-regression test asserting the planning validation output is unchanged and `make check` still passes.
- Updating `scripts/sync.sh` MAP coverage if any new shared file is introduced, plus the sync-map completeness expectation.

## 5. Out of Scope

- The Finding schema definition (Phase 1.1) and the analyzer interface definition (Phase 1.2).
- Adding any new analyzer category beyond exposing the already-existing secret scan as an analyzer (new categories are Phase 2).
- The audit runner, output-directory convention, and finding aggregation/ordering (Phase 1.4).
- Changing the planning workflow's user-visible behavior, headings, modes, or exit semantics.
- Any write-capable, fixer, isolation, or rollback work (Phase 3).
- Policy/budget gating that consumes the extracted severity counts (Phase 4).
- JSON/SARIF emission of the extracted findings (Phase 5).
- Resolving the codex structural asymmetry noted in AUTOPSY-P2-01 (Phase 6 hygiene).

## 6. Current Repository Evidence

The coupling this sub-phase removes is concrete and locatable. `shared/scripts/validate_planner_docs.py` hard-binds to the planning product through `ValidationState.planner_docs` (lines 156-158, returning `root / "Planner-docs"`), the planning heading constants `SUBPLAN_HEADINGS` (lines 60-73) and `AUDIT_HEADINGS` (lines 76-93), and the four `--mode` choices `step1..step4` in `parse_args` (lines 558-568). The reusable seam is equally concrete: `ValidationState` is a clean dataclass with `errors`, `warnings`, and `metrics` plus an `error`/`warning` pair (lines 147-170); `count_audit_severities` (lines 483-488) returns a P0-P3 dict; and `scan_secrets` (lines 519-534) iterates files, applies `SECRET_PATTERNS` (lines 113-120), and emits `secret_pattern={name}::{path}:{line}` without printing the secret. The non-regression anchor already exists: `tests/test_spec_validator_contract.py` loads the validator via `importlib` and asserts its heading constants, and `make check` runs `python3 -m unittest discover -s tests` after the three platform `validate.sh` scripts. The validator is synced to all three hosts via the last three MAP entries in `scripts/sync.sh` (lines 95-98), so any file split must update that MAP.

## 7. Planned Work Breakdown

- F1.3-01 — Identify the extraction seam
  - Description: Catalog exactly which symbols are generic (state, severity counting, secret scan) versus planning-specific (path binding, planning headings, step modes), producing the precise boundary the refactor will cut along.
  - Output: a seam map listing each symbol and its target side (shared component versus planning caller).
- F1.3-02 — Extract the analysis-state component
  - Description: Move the error/warning/metrics accumulation core out of the planning-bound `ValidationState` into a reusable component, leaving the planning path to use it via composition.
  - Output: a refactor specification for the state component and how the planning path consumes it.
- F1.3-03 — Extract the severity-counting component
  - Description: Lift `count_audit_severities` into a reusable P0-P3 counter that operates on findings/inputs rather than only a planning audit section.
  - Output: a refactor specification for the severity counter usable by the analyzer interface.
- F1.3-04 — Extract the secret-scanning analyzer
  - Description: Lift `SECRET_PATTERNS` and `scan_secrets` into a reusable secret-hygiene component and expose it as a Phase 1.2 analyzer that returns Findings with redacted `path:line` evidence.
  - Output: a refactor specification plus the analyzer descriptor for secret-hygiene.
- F1.3-05 — Preserve the planning path
  - Description: Re-wire the planning validation to call the extracted components so its CLI, modes, headings, and output remain byte-identical.
  - Output: a mapping of every current planning output line to its post-refactor source.
- F1.3-06 — Non-regression test and sync update
  - Description: Add a test asserting the planning validation output is unchanged and `make check` passes, and update `scripts/sync.sh` MAP plus completeness coverage for any new shared file.
  - Output: a non-regression test design and a sync-MAP delta.

## 8. Acceptance Criteria

- The reusable state, severity-counting, and secret-scanning components exist as repository-agnostic units that the Phase 1.2 analyzer interface can drive over an arbitrary repository.
- Running `python3 shared/scripts/validate_planner_docs.py --root . --mode all` over the existing `Planner-docs/` produces output identical to the pre-refactor behavior, with no changed metric keys, error strings, or exit codes.
- A non-regression test asserts the planning validation path is byte-stable and that `make check` completes successfully after the refactor.
- The secret-scanning component is exposed as an analyzer that returns Findings conformant to the Phase 1.1 schema, carrying redacted `path:line` evidence and never the secret value itself.
- There is exactly one implementation of the severity counting and secret patterns after the refactor, with both the planning path and the analyzer interface as callers, proving reuse rather than duplication.
- If a new shared file is introduced, `scripts/sync.sh --check` still passes (the file is mapped to all three platforms and the completeness guard is satisfied).
- No secret value is written into any artifact, and `scan_secrets` reports zero secret findings for the new components.

## 9. Validation and Test Approach

This refactor sub-plan is itself document-validated by running `python3 shared/scripts/validate_planner_docs.py --root . --mode step2 --strict`, which must pass. Non-regression validation: run the validator in `all`, `step1`, `step2`, `step3`, and `step4` modes before and after the refactor and diff the output to confirm byte-stability; encode this as `tests/test_validator_nonregression.py` discovered by `python3 -m unittest discover -s tests`. Local smoke: `make check` must pass, which runs `scripts/sync.sh --check`, the three platform `validate.sh` scripts, and the unittest suite, so a sync-MAP omission or a behavior change is caught locally. CI: `.github/workflows/validate.yml` runs `make check` on every push to `main` and PR. Security validation: confirm the extracted secret scanner still emits `secret_pattern` evidence without the secret value and reports `secret_findings=0` over the repository's tracked source. This is an offline refactor with no live readiness dimension.

## 10. Dependencies and Sequencing

This sub-phase depends on Phase 1.1 (the secret-hygiene analyzer must return schema-conformant Findings) and Phase 1.2 (the extracted components must implement the analyzer interface). It should run before Phase 1.4, because the runner will enumerate the now-extracted secret-hygiene analyzer as its first real, reused analyzer over an arbitrary repository. A required decision is whether the extracted components live in a new `shared/` module (which then needs a `scripts/sync.sh` MAP entry and a completeness-guard update) or remain inside the existing validator file behind a cleaner internal seam; the autopsy's "refactor not wrap" directive favors a genuine module split. No live credentials, network, or infrastructure are required. The one approval-sensitive decision is accepting any new shared file into the sync MAP, since that is a single-source-of-truth change.

## 11. Risks and Mitigations

- Risk: the refactor silently changes a planning validation output line, breaking the planning product the project promised to preserve. Impact: regression in the shipping product and broken `make check`. Mitigation: capture the full pre-refactor validator output across all modes as a golden baseline and assert byte-equality in the non-regression test.
- Risk: extracting to a new shared module without updating `scripts/sync.sh` leaves a file out of the single-source-of-truth contract. Impact: the sync completeness guard fails or, worse, a host runs stale logic. Mitigation: add the MAP entry and run `scripts/sync.sh --check` as part of acceptance so an unmapped shared file fails loudly.
- Risk: over-aggressive extraction couples the planning path to a half-built generic interface and destabilizes both. Impact: two products broken at once. Mitigation: cut the seam conservatively along the already-clean `ValidationState` / `count_audit_severities` / `scan_secrets` boundaries identified in the evidence, leaving planning policy in place.
- Risk: the secret analyzer, now run over a whole repository, surfaces a secret value into a finding. Impact: secret leakage into audit output, violating Main-Planning §7. Mitigation: carry forward the validator's redact-by-evidence behavior so findings report `path:line` and the pattern name, never the matched secret text.

## 12. Desired End State

The fail-closed state machine, P0-P3 severity counting, and length-bounded secret scanning live as reusable, repository-agnostic components that back the Phase 1.2 analyzer interface and can run over any repository, while `shared/scripts/validate_planner_docs.py` continues to validate `Planner-docs/` with byte-identical output as a thin caller of that shared machinery. A non-regression test guarantees the planning path is unchanged and `make check` stays green, and `scripts/sync.sh --check` confirms any new shared file reaches all three hosts. The AUTOPSY-P2-02 coupling is retired without duplication, and the audit engine now has its first genuinely reused analyzer (secret-hygiene) ready for the Phase 1.4 runner.

## 13. Transition Criteria to the Next Sub-Phase

Before starting Phase 1.4 (the audit runner), the extracted state, severity, and secret components must exist behind the analyzer interface; the planning validation path must demonstrably produce byte-identical output across all validator modes via the golden-baseline non-regression test; `make check` and `scripts/sync.sh --check` must both pass with any new shared file mapped; and `python3 shared/scripts/validate_planner_docs.py --root . --mode step2 --strict` must pass for this sub-plan. The secret-hygiene analyzer must be confirmed schema-conformant so the runner can aggregate its findings in Phase 1.4 without further contract work.
