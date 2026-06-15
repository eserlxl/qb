# Phase 5.2 — Machine-Readable Reporting (JSON/SARIF)

## 1. Context

This sub-phase sits in the middle of Phase 5 (maturity M4) and delivers the output surface that the parent phase promises: "machine-readable, reproducible, cross-reviewed run output consumable by humans and CI" (`Planner-docs/Main-Planning.md` section 6). The autopsy is blunt about the gap: AUTOPSY-P3-02 records "no JSON/SARIF emitter" and section 10 confirms there is no machine-readable output anywhere in the repository. Main-Planning section 4 ("Testing/review/release target" and "Operational target") requires SARIF/JSON that validates and that a pipeline can gate on. Phase 5.1 has just defined the run-state and evidence store as the authoritative source of execution truth; this sub-phase turns that store into three rendered outputs without recomputing analysis: a JSON findings-plus-hardening report, a SARIF findings report for tooling that speaks the standard, and a human-readable summary. The acceptance signal called out for Phase 5 in the roadmap table is literally "SARIF/JSON validates," so this sub-phase carries the schema-definition and schema-validation burden that lets CI trust the output. It depends on 5.1 for input and is depended on by 5.3, which adds provenance and reproducibility on top of these reports.

## 2. Goal

Define a versioned report schema and an emitter that reads the Phase-5.1 run-state and evidence store and produces, for a single run, three outputs: (a) a JSON report containing the graded findings and the per-fix hardening outcomes keyed by stable finding id; (b) a SARIF report carrying the findings as standard static-analysis results with rule, level, and physical location; and (c) a concise human-readable summary suitable for a terminal or a CI log. The schema must be explicit and self-validating so that continuous integration can parse the JSON, confirm it conforms, and gate a pipeline on its contents rather than on free-text.

## 3. Description

The problem here is that QB's only current output is the validator's flat `key=value` stdout stream, which no SARIF-aware tool can ingest and which no CI step can reliably parse into structured findings. This sub-phase solves that by defining a stable, versioned report contract and rendering it from the store. It belongs after 5.1 because a report must serialize persisted truth, not transient memory, so that the same store always yields the same report. It reduces risk by making findings consumable by existing code-scanning ecosystems (anything that reads SARIF) and by giving CI a typed artifact to assert against, which removes brittle text scraping. It prepares Phase 6 (headless/CI) by giving the pipeline a concrete file to parse and a summary to log, and it prepares Phase 7 (observability) by ensuring the structured counts that telemetry needs are already present in the report rather than derived ad hoc. The SARIF mapping in particular unlocks integration with code-review surfaces and security dashboards that QB itself does not need to build. Three deliberately distinct renderings — typed JSON for QB-native consumers, SARIF for standard tooling, and a short human summary — cover the human-and-CI audience the parent phase names without overloading one format.

## 4. Scope

- A versioned JSON report schema covering graded findings and per-fix hardening outcomes, keyed by stable finding id.
- A SARIF report mapping: each finding becomes a SARIF result with a rule id derived from the finding category, a level derived from the P0-P3 severity, and a physical location from the finding's evidence path and line.
- A human-readable summary rendering: counts by severity, fixes applied versus reverted, and stop reason.
- A self-describing schema artifact under `shared/` and a documented schema-validation step CI can run.
- A severity-to-SARIF-level mapping table and a category-to-rule mapping.
- A schema version field and a compatibility note for how consumers detect version changes.
- An emitter specification that reads only the Phase-5.1 store and writes the three outputs into the run output directory.

## 5. Out of Scope

- Definition and persistence of the run-state and evidence store itself, owned by Phase 5.1.
- Provenance fields (analyzer versions, policy, budgets), reproducibility replay, and cross-review verdict integration, owned by Phase 5.3.
- The headless CLI and the pipeline exit-code contract that consumes the report (Phase 6).
- Telemetry sinks and dashboards (Phase 7).
- Any change to finding detection, severity assignment, or fix application; the emitter only renders what the store already holds.
- Hosting, uploading, or publishing reports to external services.
- Auto-commit, push, or PR of report files.

## 6. Current Repository Evidence

The repository contains exactly one machine-oriented output today, and it is not a report: the `finalize` function in `shared/scripts/validate_planner_docs.py` (around line 537) prints a flat newline-delimited `key=value` stream — `planner_docs_validation=passed|failed`, `mode`, `root`, sorted `metrics`, then `warning=` and `error=` lines. There is no JSON serialization, no SARIF, and no schema file anywhere in the tree, which `Planner-docs/Autopsy.md` section 10 and AUTOPSY-P3-02 both confirm. The severity vocabulary the SARIF level mapping must respect already exists as the P0-P3 counts produced by `count_audit_severities` (around line 483 of the validator), and the overall-status vocabulary (`PASS`, `PASS_WITH_WARNINGS`, `BLOCKED`) is produced by `extract_audit_status` (around line 466); the human summary should reuse these so QB speaks one severity and status language across surfaces. The closest existing "schema is enforced by a test" precedent is `tests/test_spec_validator_contract.py`, which ties spec headings to validator behavior; the report schema-validation gate should follow that same test-as-contract pattern. No SARIF sample, no JSON sample, and no report renderer exist in the repository.

## 7. Planned Work Breakdown

- F5.2-01 — JSON report schema definition
  - Description: Define a versioned JSON schema for the run report covering graded findings and per-fix hardening outcomes, keyed by stable finding id, designed so the schema is consumable and assertable by CI.
  - Output: a JSON schema artifact under `shared/` plus an annotated example report populated with synthetic, non-secret data.
- F5.2-02 — SARIF mapping specification
  - Description: Specify how each finding maps to a SARIF result: rule id from category, level from P0-P3 severity, and physical location from evidence path and line, plus run and tool metadata blocks.
  - Output: a SARIF mapping table and a sample SARIF document validated against the SARIF standard's required structure.
- F5.2-03 — Severity and status mapping tables
  - Description: Define the severity-to-SARIF-level table and confirm the human summary uses the same P0-P3 and PASS/PASS_WITH_WARNINGS/BLOCKED vocabulary the validator already emits.
  - Output: two mapping tables with a note on how unknown or future categories degrade gracefully.
- F5.2-04 — Human-readable summary rendering
  - Description: Define a concise summary rendering for terminals and CI logs: counts by severity, fixes applied versus reverted, and the run stop reason.
  - Output: a summary layout specification and a rendered example.
- F5.2-05 — Emitter specification
  - Description: Specify an emitter that reads only the Phase-5.1 store and writes the JSON, SARIF, and summary outputs into the run output directory, with no recomputation of analysis.
  - Output: an emitter contract describing inputs (store paths), outputs (report file names), and failure behavior.
- F5.2-06 — Schema-validation gate and version field
  - Description: Define a schema-version field and a CI-runnable validation step that confirms an emitted JSON report conforms to the schema, following the test-as-contract style of `tests/test_spec_validator_contract.py`.
  - Output: a schema-validation gate plan and a `tests/` addition specification.

## 8. Acceptance Criteria

- A versioned JSON report schema exists under `shared/`, includes a schema-version field, and an example report validates against it.
- A sample SARIF document is produced in which each finding appears as a result with a rule id from its category, a level mapped from its P0-P3 severity, and a physical location from its evidence path and line.
- The severity-to-SARIF-level table and the category-to-rule table are documented, and the human summary uses the same P0-P3 and PASS/PASS_WITH_WARNINGS/BLOCKED vocabulary that `count_audit_severities` and `extract_audit_status` already produce in `shared/scripts/validate_planner_docs.py`.
- The emitter specification reads only the Phase-5.1 store and recomputes nothing, demonstrated by the fact that every report field traces to a stored field.
- A schema-validation gate is specified that CI can run to confirm conformance, following the contract-test pattern of `tests/test_spec_validator_contract.py`.
- Local readiness (schema validates against synthetic examples) is separated from live readiness (an emitter rendering a real run's store), with the latter marked as exercised once Phases 1-4 and 5.1 produce real data.
- No secret values appear in any sample report, SARIF document, or summary.

## 9. Validation and Test Approach

Document validation: confirm the schema artifact, the SARIF mapping, the mapping tables, and the summary layout are present and consistent, gated by `python3 shared/scripts/validate_planner_docs.py --strict` once the new `shared/` artifacts are wired into the sync MAP. Local smoke (proposed): render the three outputs from a synthetic store and confirm the JSON validates against the schema and the SARIF parses as well-formed SARIF. Security validation: scan the rendered outputs for secrets reusing the `scan_secrets` logic in `shared/scripts/validate_planner_docs.py` and the `tests/test_no_committed_secrets.py` convention, asserting zero matches. Artifact validation (proposed): a new test asserts that an emitted report conforms to the JSON schema and that the SARIF severity levels match the source P0-P3 severities. CI: extend `make check` so the schema-conformance test runs on every PR and push, mirroring `.github/workflows/validate.yml`; live readiness (rendering a real CI run's store) is deferred to Phase 6.

## 10. Dependencies and Sequencing

This sub-phase depends directly on Phase 5.1, because the emitter reads the run-state and evidence store and renders nothing that is not stored there. It depends on the Phase-1 frozen `Finding` schema for field names and on the validator's existing P0-P3 and status vocabularies for the SARIF level mapping and human summary. It depends on the Phase-3 fixer outcomes (kept/reverted) being present in the store for the hardening section of the report. It blocks Phase 5.3, which augments these reports with provenance and reproducibility metadata and folds in cross-review verdicts. No live credentials or network endpoints are required; rendering is offline. The decision that should be confirmed before implementation is whether SARIF is a required v1 output or an opt-in one, which interacts with open question (e) in Main-Planning section 9 about the supported headless/CI surface.

## 11. Risks and Mitigations

- Risk: the SARIF mapping is malformed and rejected by downstream code-scanning tools. Impact: the standard-format promise fails and the report is unusable in dashboards. Mitigation: validate sample SARIF against the standard's required structure in a test before claiming the mapping is done.
- Risk: an unversioned schema changes silently and breaks CI consumers. Impact: pipelines that parsed the old shape fail without explanation. Mitigation: a mandatory schema-version field plus a documented compatibility rule for detecting changes.
- Risk: the emitter recomputes analysis instead of reading the store, producing reports that disagree with persisted truth. Impact: report and store diverge, undermining reproducibility in 5.3. Mitigation: a tracing acceptance criterion requiring every report field to map to a stored field, enforced by review.
- Risk: severity or status vocabulary drifts from the validator's existing terms. Impact: QB speaks two languages and consumers misclassify findings. Mitigation: reuse `count_audit_severities` and `extract_audit_status` vocabulary directly rather than redefining it.
- Risk: secrets surface in rendered evidence snippets. Impact: secret exposure in a machine-readable, potentially uploaded artifact. Mitigation: rely on the Phase-5.1 redaction and re-scan rendered outputs with `scan_secrets`.

## 12. Desired End State

The run output directory contains three rendered outputs for any completed run: a versioned JSON report that validates against a schema artifact under `shared/`, a SARIF report whose results carry category-derived rule ids, severity-derived levels, and evidence-derived locations, and a concise human-readable summary using QB's existing P0-P3 and PASS/PASS_WITH_WARNINGS/BLOCKED vocabulary. A CI step parses the JSON, confirms conformance, and can gate a pipeline on the structured contents. Every report field traces back to the Phase-5.1 store, no analysis is recomputed during rendering, and no secret value appears in any output. The reports are ready for Phase 5.3 to enrich with provenance and cross-review verdicts.

## 13. Transition Criteria to the Next Sub-Phase

The JSON schema must be versioned, validate against synthetic examples, and pass `python3 shared/scripts/validate_planner_docs.py --strict` after sync-MAP wiring. A sample SARIF document must parse as well-formed and carry correct severity levels. The mapping tables and human summary must use the validator's existing severity and status vocabulary with no new synonyms. The schema-conformance test must be specified for `make check`. The emitter must be confirmed to read only the store. Only then should Phase 5.3 begin, because provenance and reproducibility are layered onto a report contract that must already be stable; provenance work must not start before the report schema is frozen.
