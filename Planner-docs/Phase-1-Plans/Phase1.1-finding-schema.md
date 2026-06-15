# Phase 1.1 — Freeze the Finding Schema

## 1. Context

This sub-phase opens Phase 1 of the QB self-run pivot, whose parent goal in `Planner-docs/Main-Planning.md` §6 is "a code-aware Finding schema plus a read-only audit over an arbitrary repository, reusing the existing validator machinery." The autopsy raised AUTOPSY-P0-01 as the single highest-leverage gap: there is no frozen Finding contract anywhere in the repository, so every later phase (analyzers in Phase 2, the fixer in Phase 3, the orchestrator in Phase 4, reporting in Phase 5) would otherwise bind to an undefined interface and churn. The Phase 0 charter ratified the autonomy model A0-A3; this sub-phase converts the charter's per-finding artifact boundary (`id, category, severity, confidence, evidence, rationale, suggested-fix, fix-strategy`, named in Main-Planning §5) into a concrete, validator-checkable schema living in `shared/`. It is the first sub-phase in Phase 1 and is a hard prerequisite for the other three sub-phases here.

## 2. Goal

Define and freeze a single host-neutral Finding schema, stored as canonical IP under `shared/`, that every QB analyzer and fixer must emit and consume, such that a malformed finding is mechanically rejected by a conformance test before any analyzer logic is written. The outcome is a stable contract object: a structured Finding record with the eight named fields, an explicit value vocabulary for the constrained fields (category, severity P0-P3, confidence, fix-strategy), and a deterministic identity rule, frozen firmly enough that Phases 2 through 5 can be planned and built against it without renegotiation.

## 3. Description

The work here is contract design, not feature delivery: it produces one schema definition plus the test that locks it. QB already proves, in `shared/scripts/validate_planner_docs.py`, that it can emit graded, evidence-bearing records — its `count_audit_severities` reads P0-P3 out of a planning audit document and its error strings carry `path:line` evidence such as `secret_pattern={name}::{path}:{line}` from `scan_secrets`. The Finding schema generalizes that latent record into a first-class, code-aware object so the audit engine can describe a defect found anywhere in an arbitrary repository, not only a severity tallied inside one planning file. Freezing it now removes the largest source of downstream rework: the fixer's fix-strategy enum, the orchestrator's severity/confidence gating thresholds, and the reporter's JSON/SARIF mapping all dereference these exact field names. Confidence is introduced here (absent from the validator today) precisely because Main-Planning §7 makes confidence-gated auto-fix a core false-positive mitigation, so it must exist in the contract from the very first finding.

## 4. Scope

- A schema document under `shared/` defining the Finding record and its field semantics.
- The eight required fields: `id`, `category`, `severity`, `confidence`, `evidence`, `rationale`, `suggested-fix`, `fix-strategy`.
- A closed value vocabulary for constrained fields: severity drawn from P0-P3 (reusing the validator's existing grading), an enumerated category set, an enumerated confidence band, and an enumerated fix-strategy set.
- The deterministic identity rule for `id` (how a finding is uniquely and reproducibly named so reruns are stable).
- The `evidence` shape as `path:line` (or a path with a line range) so every finding is traceable to a location.
- A conformance test under `tests/` that accepts well-formed findings and rejects ill-formed ones.
- A serialization decision (the on-disk representation a finding takes when persisted) recorded in the schema document.

## 5. Out of Scope

- Any analyzer that produces findings (deferred to Phase 2).
- The analyzer interface and registration mechanism (Phase 1.2).
- Refactoring the validator internals behind that interface (Phase 1.3).
- The audit runner and the output-directory convention (Phase 1.4).
- The fixer, fix application, isolation, or rollback (Phase 3).
- Policy thresholds, budgets, and autonomy gating that consume severity/confidence (Phase 4).
- JSON/SARIF report rendering and provenance (Phase 5).
- Networked enrichment of findings such as CVE metadata (Phase 2 opt-in track).

## 6. Current Repository Evidence

The repository contains no Finding type, no schema file, and no test that asserts a finding shape — confirmed by the absence of any such artifact under `shared/` and `tests/`. What does exist is reusable raw material: `shared/scripts/validate_planner_docs.py` defines `SECRET_PATTERNS` (lines 113-120) and a `scan_secrets` function (lines 519-534) that already emits `path:line` evidence, plus `count_audit_severities` (lines 483-488) that recognizes the P0-P3 vocabulary this schema will adopt. The validator's `ValidationState` dataclass (lines 147-170) shows the project's established pattern of a typed record with `errors`, `warnings`, and a `metrics` dict, which is a precedent for how a Finding dataclass should look. The test suite convention is set by `tests/test_spec_validator_contract.py`, which loads a module via `importlib` and asserts a contract; a finding-conformance test should mirror that style and register itself for `python3 -m unittest discover -s tests` as the `Makefile` `check` target runs. No prior finding evidence exists beyond these seeds.

## 7. Planned Work Breakdown

- F1.1-01 — Field roster and semantics
  - Description: Pin the eight Finding fields with one-line semantics each, marking which are required versus optional and which are free-text versus enumerated, so downstream phases reference one authoritative list.
  - Output: a field table in the `shared/` schema document.
- F1.1-02 — Constrained value vocabularies
  - Description: Enumerate the allowed values for `category`, `severity` (P0-P3, aligned to the validator's existing grading), `confidence` band, and `fix-strategy`, with a short definition for each value.
  - Output: four enumeration lists with definitions in the schema document.
- F1.1-03 — Deterministic finding identity
  - Description: Specify how `id` is derived so the same defect in the same place yields the same id across reruns (a stable, reproducible naming rule), enabling deduplication and diffing between runs.
  - Output: an identity rule with two worked examples.
- F1.1-04 — Evidence locator format
  - Description: Define the `evidence` field as a repository-relative `path:line` (or path plus line range) and state how a multi-location finding is represented.
  - Output: an evidence-format specification with examples.
- F1.1-05 — Serialization decision
  - Description: Decide the persisted on-disk representation of a finding (the structured text form written to the output directory) and confirm it is line-stable for deterministic diffing; the exact format to be confirmed during implementation against the dependency-light constraint.
  - Output: a serialization section naming the chosen representation and its ordering rule.
- F1.1-06 — Conformance test
  - Description: Author a `tests/` module that constructs valid and invalid findings and asserts acceptance/rejection, runnable under the existing unittest discovery.
  - Output: a test design note enumerating the positive and negative cases to encode.

## 8. Acceptance Criteria

- A schema artifact exists under `shared/` enumerating exactly the eight Finding fields with per-field semantics and required/optional status.
- The `severity` vocabulary is exactly P0, P1, P2, P3, matching what `count_audit_severities` in `shared/scripts/validate_planner_docs.py` already recognizes, so no second grading scale is introduced.
- `category`, `confidence`, and `fix-strategy` each have a closed, documented enumeration; any value outside the enumeration is defined as non-conformant.
- The `id` rule is deterministic: the document shows two examples proving the same defect at the same location reproduces the same id.
- A conformance test under `tests/` is specified that passes for a well-formed finding and fails for each of: a missing required field, an out-of-vocabulary severity, an out-of-vocabulary category, and an evidence value lacking a location.
- The schema document states the serialization format and asserts it is deterministically ordered.
- No secret value, token, or credential appears anywhere in the schema or test specification.

## 9. Validation and Test Approach

Document validation: run `python3 shared/scripts/validate_planner_docs.py --root . --mode step2 --strict` so this sub-plan itself passes the structural and anti-placeholder gates. Conformance validation (proposed, to be added by implementation): a new `tests/test_finding_schema_conformance.py` module discovered by `python3 -m unittest discover -s tests`, which the `Makefile` `check` target already invokes; it should construct findings and assert acceptance/rejection. Local smoke: confirm the new test runs green via `make test`. CI: `.github/workflows/validate.yml` runs `make check` on every push to `main` and every PR, so the conformance test gates merges automatically once added. Security validation: the validator's `scan_secrets` runs on every invocation and must report `secret_findings=0` for the schema artifact. There is no live readiness dimension for a schema definition; this is a purely local/offline contract.

## 10. Dependencies and Sequencing

This sub-phase depends on the Phase 0 charter having ratified the autonomy model and the per-finding artifact field list, since the schema realizes that field list. It has no dependency on any other Phase 1 sub-phase and must precede all of them: Phase 1.2's analyzer interface returns a list of these findings, Phase 1.3's refactored validator must emit them, and Phase 1.4's runner aggregates and orders them. A required decision is the closed enumeration for `category` and `fix-strategy`; these can be drafted here but should be reviewed against Phase 2's planned analyzer categories so the vocabularies do not need widening mid-build. No live credentials, network access, or infrastructure are required. No human approval beyond accepting the frozen vocabularies is needed to proceed.

## 11. Risks and Mitigations

- Risk: the enumerations are frozen too narrowly and Phase 2 analyzers need a category the schema forbids. Impact: a schema reopening that ripples into every consumer. Mitigation: include an explicit extension rule stating how a new enumerated value is added (additive only, with a test update) so widening is a controlled, test-gated change rather than a breaking one.
- Risk: confidence is defined as free-form rather than a small band, making Phase 4 thresholding ambiguous. Impact: the orchestrator cannot reliably gate auto-fix on confidence. Mitigation: define confidence as a small closed band with documented meanings, decided here, not deferred.
- Risk: the identity rule is non-deterministic (for example incorporating a timestamp), breaking rerun stability and deduplication. Impact: noisy diffs and duplicate findings across runs. Mitigation: require the id to be a pure function of stable inputs (category, normalized location, defect kind) and prove it with the two reproducibility examples in acceptance.
- Risk: a serialization choice pulls in a dependency, violating the zero-setup promise from Main-Planning §1. Impact: the base tool loses its dependency-light property. Mitigation: constrain the serialization decision to formats expressible with the Python standard library only.

## 12. Desired End State

A frozen, host-neutral Finding schema lives under `shared/` as canonical IP, defining eight fields, four closed vocabularies, a deterministic identity rule, an evidence locator format, and a standard-library-only serialization. A conformance test under `tests/` mechanically enforces the schema and is wired into `make check` and CI. Any contributor or future phase can read one document and know exactly what a QB finding is, what values each field may take, and how two runs over the same repository produce byte-stable findings. The contract is stable enough that Phases 2 through 5 can be designed against it without renegotiation, and a malformed finding fails the build rather than reaching a fixer.

## 13. Transition Criteria to the Next Sub-Phase

Before starting Phase 1.2 (the analyzer interface), the eight fields, four vocabularies, identity rule, and serialization must be written down in `shared/` and free of contradictions; the conformance test design must enumerate concrete positive and negative cases; `python3 shared/scripts/validate_planner_docs.py --root . --mode step2 --strict` must pass for this sub-plan; and the category/fix-strategy enumerations must be cross-checked against Phase 2's intended analyzer set so the interface in Phase 1.2 can be typed to return a list of conformant findings without anticipating an imminent vocabulary change. No analyzer or runner work begins until the schema is frozen.
