# Phase 2.3 — Quality and Correctness Adapters (Offline)

## 1. Context

This sub-phase widens Phase 2 coverage from security to quality and correctness by wrapping offline linters and static-analysis tools as analyzers, normalizing their heterogeneous output into the unified `Finding` schema from Phase 1. The master plan's Phase 2 row in `Planner-docs/Main-Planning.md` section 6 calls explicitly for "basic correctness/lint adapters," and section 5 ("Integration boundaries") requires that such wrapping happen "only through structured command schemas with explicit argument lists." The autopsy reinforces a hard constraint in `Planner-docs/Autopsy.md` section 1 and AUTOPSY (the offline-core / opt-in-networked split): the tool's "zero-setup, dependency-free" identity must survive contact with real external tools, which means an absent optional linter must degrade gracefully rather than crash the audit. This sub-phase depends directly on the structured argv convention authored in Phase 2.2, because every adapter here launches an external process and must do so via the explicit-argument form, never a shell string.

## 2. Goal

Deliver a set of offline quality-and-correctness adapters that invoke locally available linters and static-analysis tools through the structured argv convention, parse their native output, and emit normalized `Finding` records (categories such as `code-quality` and `correctness`) with `path:line` evidence, severity, and confidence — while gracefully skipping any tool that is not installed, so the zero-setup core continues to run with no optional tool present.

## 3. Description

Each adapter is a thin, read-only bridge between one external analyzer and QB's finding model. It detects whether its backing tool exists, and if so launches it with an explicit argument vector (per the Phase 2.2 convention), captures the tool's structured output, maps each native diagnostic to a `Finding` — translating the tool's own severity into QB's P0-P3 grade and assigning a confidence that reflects how authoritative that tool is for that rule — and attaches the originating tool name to the finding for provenance. When the tool is absent, the adapter emits no findings and records a non-fatal "skipped: tool unavailable" signal, so a base install with no extra software produces a smaller but still valid audit. This belongs at this point in the roadmap because it broadens audit coverage beyond the two security analyzers without compromising the offline promise, and it exercises the argv convention against real binaries, proving that convention works before the fixer relies on it. It reduces project risk by making external-tool integration explicit, optional, and normalized rather than ad-hoc, and it prepares Phase 3 by producing `correctness` and `code-quality` findings the fixer can later remediate, and the eval harness can measure precision against.

## 4. Scope

- Adapter pattern wrapping each offline tool behind the Phase 2.2 structured argv convention.
- Tool-presence detection with graceful, non-fatal skip when a backing tool is absent.
- Output normalization mapping native diagnostics into `Finding` records with QB severities and confidences.
- Provenance: each finding records which external tool produced it.
- Categories `code-quality` and `correctness` mapped from tool rule classes.
- A capability-report surface listing which adapters ran and which were skipped.
- Fixtures: a repo with planted lint/correctness defects, plus a run with all optional tools simulated absent to prove graceful degradation.

## 5. Out of Scope

- Bundling, vendoring, or auto-installing any external linter; the base install adds no dependency.
- Deep SAST or whole-program correctness proofs beyond what a wrapped offline tool natively provides.
- Networked or CVE-dependent tools; those are reserved for Phase 2.4's opt-in networked split.
- Fixing the detected quality or correctness defects; remediation is Phase 3.
- Reconciling or de-duplicating overlapping findings across multiple tools; normalization here is per-tool.
- Defining the policy that decides which categories are auto-fixable; that governance is Phase 4.

## 6. Current Repository Evidence

QB has no external-tool adapters today; AUTOPSY-P1-03 and section 7 of the autopsy record that "no adapters for linters/SAST/dependency-CVE scanners" exist and that the integration surface is undesigned. The repository's existing process invocations are confined to maintainer-controlled scripts: `scripts/sync.sh` and `platforms/*/scripts/validate.sh`, which run trusted local logic, not third-party analyzers over target repos. The validator's dependency-free, read-only posture in `shared/scripts/validate_planner_docs.py` is the model this sub-phase must preserve — adapters add optional reach without adding required dependencies. The `tests/` suite contains no adapter or normalization tests, and there is no capability-report concept. The structured argv convention this sub-phase depends on does not yet exist either; it is produced in Phase 2.2 and consumed here, so this sub-phase cannot begin until that convention is ratified.

## 7. Planned Work Breakdown

- F2.3-01 — Adapter interface over the argv convention
  - Description: Define the common adapter contract that detects, launches (via explicit argv), and normalizes one external offline tool.
  - Output: an adapter-interface specification under `shared/` citing the Phase 2.2 convention.
- F2.3-02 — Tool-presence detection and graceful skip
  - Description: Specify how an adapter checks for its backing tool and records a non-fatal skip when absent.
  - Output: a degradation-behavior specification with the skipped-signal format.
- F2.3-03 — Output normalization and severity mapping
  - Description: Map each tool's native diagnostics and severities into QB `Finding` records with confidence and provenance.
  - Output: a normalization mapping table per supported tool class.
- F2.3-04 — Capability report
  - Description: Produce a surface listing which adapters ran versus skipped, so a smaller audit is transparent rather than silent.
  - Output: a capability-report format specification.
- F2.3-05 — Lint/correctness and absent-tool fixtures
  - Description: Build a fixture with planted lint/correctness defects and a configuration that simulates all optional tools absent.
  - Output: fixture layout, expected normalized findings, and expected graceful-degradation behavior.

## 8. Acceptance Criteria

- With a backing tool present, the adapter emits normalized `Finding` records whose evidence, severity, confidence, and originating-tool provenance are correct against the planted-defect fixture.
- With all optional tools absent, the audit completes successfully, emits no adapter findings, and the capability report lists each adapter as skipped — proving the zero-setup core is intact.
- Every adapter launches its tool through the structured argv convention from Phase 2.2, never via a shell string.
- Native tool severities are mapped to QB P0-P3 grades by a documented, deterministic rule.
- The base install requires no new third-party dependency to run a valid audit.
- The capability report distinguishes ran-versus-skipped adapters so reduced coverage is explicit.

## 9. Validation and Test Approach

- Document validation: confirm the adapter interface, degradation behavior, and normalization mapping are specified with concrete examples.
- Local smoke (proposed): run adapters over the planted-defect fixture with a tool present, asserting normalized finding counts and provenance.
- Degradation smoke (proposed): run the same audit with optional tools simulated absent, asserting completion, zero adapter findings, and a correct capability report.
- Convention conformance: reuse the Phase 2.2 argv conformance test to confirm adapters do not shell out via strings.
- Regression: keep `make check` and `python3 -m unittest discover -s tests` green so the planning product and offline core are unaffected.
- Live readiness: not applicable; all adapters here are offline. Networked tool readiness is deferred to Phase 2.4.

## 10. Dependencies and Sequencing

- Hard dependency on Phase 2.2: every adapter invokes an external process and must use the ratified structured argv convention.
- Depends on the Phase 1 `Finding` schema for the normalized output shape.
- Optionally consumes the Phase 2.1 redaction contract when a tool's diagnostic might quote a sensitive line.
- Requires no network, no credentials, and no human approval to implement or validate, because all backing tools are local and optional.
- Any new shared adapter file must be added to the `scripts/sync.sh` MAP so Cursor and Codex receive it byte-for-byte.

## 11. Risks and Mitigations

- Risk: an absent optional tool aborts the whole audit. Impact: the zero-setup promise is broken and a base install fails. Mitigation: make tool-presence detection non-fatal, emit a skipped signal, and gate the sub-phase on an absent-tool fixture run that must still complete.
- Risk: inconsistent severity mapping across tools produces incomparable grades. Impact: triage and policy thresholds behave unpredictably. Mitigation: define one deterministic native-to-P0-P3 mapping table and test it per tool class.
- Risk: parsing fragile native output formats breaks when a tool version changes. Impact: dropped or corrupted findings. Mitigation: parse only the tool's stable structured output mode and fail soft to a skip with a recorded signal rather than crashing.
- Risk: an adapter quietly pulls in a transitive dependency. Impact: erosion of the dependency-light core. Mitigation: forbid bundling tools, treat all backing tools as external and optional, and assert no new runtime dependency in the base install.

## 12. Desired End State

QB has a family of offline quality-and-correctness adapters that wrap locally available linters and static-analysis tools through the structured argv convention, normalize their output into `code-quality` and `correctness` findings with provenance, and skip gracefully when a tool is absent — so the base install audits with zero added dependencies while a tool-rich environment gets deeper coverage. A capability report makes reduced coverage explicit, fixtures prove both the present-tool and absent-tool paths, and the offline core's zero-setup property is verifiably preserved.

## 13. Transition Criteria to the Next Sub-Phase

- Adapters emit correct normalized findings with a tool present and degrade gracefully with all optional tools absent, both proven by fixtures.
- The native-to-P0-P3 severity mapping is documented and tested for determinism.
- The capability report format is finalized so Phase 2.4's opt-in networked analyzer can plug into the same ran-versus-skipped reporting surface.
- `make check` and the existing suite remain green, and all new shared adapter files are wired into the `scripts/sync.sh` MAP.
