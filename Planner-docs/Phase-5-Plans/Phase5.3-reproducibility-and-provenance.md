# Phase 5.3 — Reproducibility, Provenance, and Cross-Review Integration

## 1. Context

This sub-phase closes Phase 5 (maturity M4), completing the parent goal of "machine-readable, reproducible, cross-reviewed run output consumable by humans and CI" (`Planner-docs/Main-Planning.md` section 6). Two of the three adjectives in that goal — reproducible and cross-reviewed — are this sub-phase's responsibility; Phase 5.2 delivered the machine-readable part. The roadmap table for Phase 5 names the decisive acceptance signals as "report reproducible from run-state" and "cross-review catches a seeded bad fix in eval," and both land here. Main-Planning section 5 ("Artifact/evidence boundaries") requires every fix to carry verification evidence and a reversal handle, and section 4 ("Testing/review/release target") requires that the role proposing a fix be separable from the role verifying it, so the same model family is not the sole judge of its own change. The Phase-4 orchestrator already separates auditor/fixer/verifier/reviewer roles; this sub-phase ensures the reviewer's verdicts are captured into the report and that the report can be regenerated deterministically from the Phase-5.1 store, with provenance attached so a reader knows which analyzer versions, which policy, and which budgets produced it. It depends on 5.1 (the store) and 5.2 (the report) and is the final trust layer before the engine fans out to multiple hosts in Phase 6.

## 2. Goal

Make the Phase-5.2 report deterministically reproducible from the Phase-5.1 run-state store, attach a provenance block recording analyzer versions, the active policy, and the budget settings that governed the run, and integrate the Phase-4 cross-review verdicts so that each finding and each fix in the report carries the separable reviewer's keep/reject decision and rationale. A specific, measurable outcome is that a deliberately seeded bad fix in the evaluation harness is caught by cross-review, the catch is recorded in the report, and re-rendering the report from the same store reproduces the same content byte-for-byte except for fields explicitly designated as non-deterministic.

## 3. Description

The problem this sub-phase solves is trust in the report's stability and authorship: a report that cannot be regenerated from stored truth, or that hides which policy and tool versions produced it, or that lets the fixer's own role bless its own change, is not auditable. Reproducibility is solved by deriving the report purely from the store and isolating any non-deterministic field (such as wall-clock timing) so the substantive content re-renders identically. Provenance is solved by capturing, at run time into the store and then into the report, the analyzer version identifiers, the resolved policy, and the budget envelope, so a future reader can explain why a given finding was or was not auto-fixed. Cross-review integration is solved by reading the separable reviewer role's verdicts from the store and surfacing them per finding and per fix in both the JSON and the human summary. This work belongs last in Phase 5 because it consumes both the store and the report that the earlier sub-phases define. It reduces risk by making false-positive-driven and confidently-wrong fixes visible and contestable, directly answering the false-positive risk in Main-Planning section 7. It prepares Phase 6 by giving each host a report whose authorship and reproducibility are verifiable, and Phase 7 by tying telemetry to a provenance-stamped run.

## 4. Scope

- A reproducibility contract: the report is a pure function of the Phase-5.1 store, with an explicit, enumerated list of non-deterministic fields excluded from the byte-for-byte comparison.
- A provenance block embedded in the JSON report: analyzer version identifiers, the resolved policy, the autonomy level, and the budget settings (max findings/fixes/iterations/wall-time/tokens) in effect.
- Cross-review verdict integration: each finding and each fix carries the separable reviewer role's keep/reject decision and rationale, sourced from the Phase-4 role separation.
- A seeded-bad-fix evaluation case demonstrating that cross-review catches the bad fix and that the catch is recorded in the report.
- A re-render comparison procedure proving the report regenerates from the store.
- Documentation of how provenance handles networked, opt-in analyzers versus the offline core so version capture degrades gracefully.

## 5. Out of Scope

- Definition of the run-state and evidence store, owned by Phase 5.1.
- The base report schema, SARIF mapping, and human summary layout, owned by Phase 5.2.
- The design of the role separation and policy engine itself, owned by Phase 4; this sub-phase only consumes the reviewer verdicts and policy those phases produce.
- Building the analyzers whose versions are captured (Phase 2) or the fixer whose changes are reviewed (Phase 3).
- The headless CLI, pipeline exit codes, and multi-host fan-out (Phase 6).
- Telemetry sinks and dashboards (Phase 7).
- Auto-commit, push, or PR of reports, provenance, or eval artifacts.

## 6. Current Repository Evidence

No reproducibility mechanism, provenance capture, or cross-review integration exists in the repository today; `Planner-docs/Autopsy.md` section 8 records there is "no eval harness / precision-recall measurement," section 10 records no telemetry and no captured cost/quality signals, and Main-Planning section 4 names cross-review as a target rather than an existing capability. The seed for role separation is conceptual: Main-Planning section 5 states that the reviewer is "a distinct lens applied to fixes (ideally not the same role that authored them)," but the autopsy notes in section 11 that this separation does not yet exist as code. The reuse anchor for provenance versioning is the manifest-version drift problem the autopsy flags in AUTOPSY-P2-01 — claude-code `0.3.0`, cursor `0.6.0`, codex `0.3.0` with no consistency test — which shows QB has no single source of version truth, so the provenance block must capture analyzer versions explicitly rather than assume a global one. The determinism anchor is the validator's sorted output in `finalize` (around line 549 of `shared/scripts/validate_planner_docs.py`), where metrics, warnings, and errors are emitted in sorted order — a precedent for deterministic rendering that the reproducible report should follow. No seeded fixture repo and no eval harness are present.

## 7. Planned Work Breakdown

- F5.3-01 — Reproducibility contract
  - Description: Define the report as a pure function of the Phase-5.1 store, enumerate the fields that are legitimately non-deterministic (such as timing), and specify a re-render comparison that ignores only those fields.
  - Output: a reproducibility contract listing deterministic and non-deterministic fields and the comparison procedure.
- F5.3-02 — Provenance block specification
  - Description: Specify a provenance block carrying analyzer version identifiers, the resolved policy, the autonomy level, and the budget settings in effect, embedded in the JSON report.
  - Output: a provenance field map with a synthetic example, including how absent optional-analyzer versions are represented.
- F5.3-03 — Cross-review verdict integration
  - Description: Specify how the separable reviewer role's keep/reject decision and rationale, produced by Phase 4, are read from the store and surfaced per finding and per fix in the JSON report and the human summary.
  - Output: a verdict integration contract and an example finding/fix carrying a reviewer verdict.
- F5.3-04 — Seeded-bad-fix evaluation case
  - Description: Specify an evaluation case in which a deliberately bad fix is seeded, cross-review must reject it, and the rejection must appear in the report; tie this to the fixture/eval harness seeded in Phase 1.
  - Output: an eval case specification with the seeded defect, the expected reviewer rejection, and the expected report record.
- F5.3-05 — Provenance degradation for networked analyzers
  - Description: Document how version capture behaves when an opt-in networked analyzer is absent or unreachable, preserving the offline-core promise.
  - Output: a degradation rule set distinguishing offline-core provenance from opt-in-networked provenance.
- F5.3-06 — Re-render verification procedure
  - Description: Specify the procedure and test that regenerate the report from the store twice and confirm byte-for-byte equality outside the enumerated non-deterministic fields.
  - Output: a re-render verification plan naming the `tests/` addition required.

## 8. Acceptance Criteria

- The reproducibility contract enumerates every non-deterministic field, and a re-render of the report from the same Phase-5.1 store reproduces all other content byte-for-byte, following the sorted-deterministic-output precedent in `finalize` within `shared/scripts/validate_planner_docs.py`.
- The JSON report contains a provenance block with analyzer version identifiers, the resolved policy, the autonomy level, and the budget settings (max findings/fixes/iterations/wall-time/tokens) that governed the run.
- Each finding and each fix in the report carries the separable reviewer role's keep/reject decision and rationale, sourced from the Phase-4 role separation rather than from the fixer's own role.
- A seeded-bad-fix evaluation case demonstrates that cross-review rejects the bad fix and that the rejection is recorded in the report, satisfying the Phase-5 roadmap acceptance signal.
- Provenance degradation is documented so that an absent opt-in networked analyzer's version is represented explicitly without breaking the offline-core run.
- Local readiness (re-render determinism on a synthetic store) is distinguished from live readiness (a real run's report reproduced in CI), with the latter deferred to Phase 6.
- No secret values, tokens, or private endpoints appear in any provenance block, verdict record, or eval artifact.

## 9. Validation and Test Approach

Document validation: confirm the reproducibility contract, provenance field map, verdict integration contract, and eval case are present and consistent, gated by `python3 shared/scripts/validate_planner_docs.py --strict` once the new `shared/` artifacts are wired into the sync MAP. Local smoke (proposed): render a report from a synthetic store twice and assert byte-for-byte equality outside the enumerated non-deterministic fields. Security validation: scan provenance blocks and verdict records for secrets using the `scan_secrets` logic in `shared/scripts/validate_planner_docs.py` and the `tests/test_no_committed_secrets.py` convention, asserting zero matches; the resolved policy in provenance must reference policy by identifier, never by embedding credentials. Eval validation (proposed): run the seeded-bad-fix case and assert the reviewer rejection appears in the rendered report. CI: extend `make check` so the re-render determinism test and the seeded-bad-fix eval run on every PR and push, mirroring `.github/workflows/validate.yml`; live readiness (reproducing a real CI run's report) is deferred to Phase 6.

## 10. Dependencies and Sequencing

This sub-phase depends on Phase 5.1 for the store it re-renders from and on Phase 5.2 for the report schema it augments with provenance and verdicts. It depends on Phase 4 for the resolved policy, the autonomy level, the budget envelope, and the separable reviewer role's verdicts, since this sub-phase consumes rather than creates those. It depends on the Phase-1 fixture/eval harness to host the seeded-bad-fix case and on the Phase-2 analyzers and Phase-3 fixer for the version identifiers and fixes whose reviews are recorded. It blocks Phase 6, which fans the now-trustworthy report out to multiple hosts and headless CI. No live credentials or network endpoints are required for the offline core; an opt-in networked analyzer would introduce a network dependency, but provenance must degrade gracefully when it is absent. The human decision to confirm before implementation is whether networked analyzers are in scope for v1, open question (b) in Main-Planning section 9, because it determines which version identifiers provenance must capture.

## 11. Risks and Mitigations

- Risk: hidden non-determinism (ordering, timestamps, environment) defeats byte-for-byte re-render. Impact: the reproducibility acceptance signal cannot be met. Mitigation: enumerate non-deterministic fields explicitly and render everything else in sorted, deterministic order following the `finalize` precedent.
- Risk: the fixer's own role reviews its own change, defeating cross-review. Impact: confidently-wrong fixes pass unchallenged, the exact false-positive danger named in Main-Planning section 7. Mitigation: source verdicts only from the Phase-4 separable reviewer role and assert separability in the eval case.
- Risk: the seeded-bad-fix eval is too easy and gives false confidence. Impact: cross-review looks effective but misses realistic bad fixes. Mitigation: design the seeded defect to resemble a plausible analyzer-driven mistake, not an obvious one, and document why it is representative.
- Risk: provenance embeds a policy that contains secrets or sensitive endpoints. Impact: secret leakage into a machine-readable, potentially shared report. Mitigation: reference policy by identifier and scan provenance with `scan_secrets`.
- Risk: provenance assumes a single version when manifests already drift (AUTOPSY-P2-01). Impact: misleading provenance that overstates consistency. Mitigation: capture per-analyzer versions explicitly rather than one global version.

## 12. Desired End State

A completed run's report can be regenerated from the Phase-5.1 store and reproduces identically outside a small, enumerated set of non-deterministic fields. The report carries a provenance block naming the analyzer versions, the resolved policy, the autonomy level, and the budget settings that governed the run, so any reader can explain why each finding was or was not auto-fixed. Every finding and every fix carries the separable reviewer role's keep/reject verdict and rationale, ensuring no role is the sole judge of its own change. A seeded-bad-fix evaluation case demonstrably has its bad fix rejected by cross-review with the rejection recorded in the report. No secret appears in any provenance, verdict, or eval artifact, and the engine's output is now trustworthy enough to fan out across hosts in Phase 6.

## 13. Transition Criteria to the Next Sub-Phase

The reproducibility contract must enumerate non-deterministic fields and demonstrate deterministic re-render on a synthetic store, passing `python3 shared/scripts/validate_planner_docs.py --strict` after sync-MAP wiring. The provenance block must capture per-analyzer versions, policy, autonomy level, and budgets. Cross-review verdicts must be integrated per finding and per fix from the separable reviewer role. The seeded-bad-fix eval must reject the bad fix and record it in the report. Secret scans over provenance and verdict records must be clean. Only once reproducibility, provenance, and cross-review are demonstrated should Phase 6 begin, because multi-host fan-out and headless CI should distribute an already-trustworthy, reproducible report rather than retrofit trust afterward; fan-out must not begin before the seeded-bad-fix eval passes.
