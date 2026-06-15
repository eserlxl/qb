# Phase 2.2 — Command-Execution and Injection Analyzer

## 1. Context

This sub-phase confronts the single highest new attack surface the pivot introduces, recorded as AUTOPSY-P1-03 in `Planner-docs/Autopsy.md` section 13: "untrusted-repo command-execution surface is undesigned (no structured argv command schema, no path-traversal write guard, no sandboxing)." The master plan reinforces this in `Planner-docs/Main-Planning.md` section 5 ("Integration boundaries"), which states analyzers may wrap external tools "but only through structured command schemas with explicit argument lists — never shell-string interpolation," and in section 7's "Command-execution and untrusted-repo attack surface" risk. Two problems are bundled here. First, QB itself must define and adopt a structured argv convention before any analyzer or fixer shells out, because Phase 2.3 and Phase 3 will both invoke external processes. Second, QB must be able to *detect* the same dangerous patterns in the target repository it audits — shell-string execution, unsafe dynamic exec, and path-traversal sinks. This sub-phase therefore both establishes a tool-wide convention and ships an analyzer that flags violations of that convention in audited code.

## 2. Goal

Establish a documented, enforceable structured argv command-execution convention for the entire QB engine (every external process is launched from an explicit argument vector with no shell-string interpolation), and deliver an analyzer that emits `Finding` records for command-execution and injection risks in a target repository — shell-string execution sinks, dangerous dynamic evaluation, and path-traversal write/read patterns — each with `path:line` evidence, severity, and confidence.

## 3. Description

The convention work writes down a single rule the rest of the tool obeys: external commands are represented as a fixed program name plus an explicit list of arguments, passed without an intervening shell, with no interpolation of untrusted strings into a command line. This rule is the foundation Phase 2.3 (offline tool adapters) and Phase 3 (the fixer's verification commands) build on, so it must exist and be referenceable before those analyzers and runtimes are designed. The detection work scans the target repo for the inverse of that rule: invocations that pass a composed string to a shell, dynamic evaluation of attacker-influenced input, and file operations whose paths are built from external input without containment to the repository root. Findings are categorized (for example `command-injection`, `dangerous-exec`, `path-traversal`) so the fixer and reporting layers can route them. This belongs at this point in the roadmap because it is the security gate that must precede any analyzer that runs an external binary; placing it second in Phase 2, immediately after the trust-critical secret analyzer, ensures the riskiest integration boundary is designed before it is exercised. It reduces project risk by turning an undesigned attack surface into an explicit, testable contract, and it prepares later phases by giving them a safe invocation primitive to depend on.

## 4. Scope

- A written structured argv command-schema convention: explicit program plus argument list, no shell, no interpolation of untrusted input, adopted tool-wide.
- A path-containment helper concept that confines any analyzer or fixer file access to the target repository root, rejecting traversal outside it.
- Detection rules for shell-string execution sinks in audited code.
- Detection rules for dangerous dynamic evaluation and for path-traversal read/write sinks.
- Finding categories `command-injection`, `dangerous-exec`, and `path-traversal` mapped to severities and confidences.
- Seeded-defect fixtures containing each unsafe pattern plus safe counterparts that must not trigger findings.
- A statement that QB never auto-runs repo-provided scripts without explicit sandboxed authorization.

## 5. Out of Scope

- Full sandboxing or containerization of analyzer/fixer execution; this slice defines the argv convention and detection, not an isolation runtime.
- Taint analysis or interprocedural dataflow across modules; detection here is pattern- and sink-based, not a full dataflow engine.
- Fixing the detected command-injection or traversal defects; remediation is Phase 3.
- Networked or dynamic execution of the target repo's code to confirm exploitability.
- Language-specific deep parsing beyond what is needed to recognize the documented sink patterns.
- Policy enforcement of which commands QB may run; that governance lives in the Phase 4 policy engine.

## 6. Current Repository Evidence

The repository today contains no structured command schema and no path-traversal guard, exactly as AUTOPSY-P1-03 and section 7 of the autopsy state. The closest existing read-only walk is `scan_secrets` in `shared/scripts/validate_planner_docs.py` (lines 519-534), which demonstrates the safe file-iteration pattern this analyzer can mirror (skip `.git`, tolerate undecodable files), but it performs no command analysis. The planning workflow itself shells out only inside `scripts/sync.sh` and the per-platform `platforms/*/scripts/validate.sh`, which are maintainer-controlled and not invoked against untrusted repositories, so they are not the surface at risk; the risk arrives with the new engine. There is no test asserting an argv-only invocation discipline, and no fixture exercising injection or traversal sinks. Current repository evidence for the injection-detection rules themselves is limited, because no such analyzer has ever existed in QB; the convention must be authored here.

## 7. Planned Work Breakdown

- F2.2-01 — Structured argv command-schema convention
  - Description: Author the tool-wide rule that external commands are an explicit program plus argument vector with no shell and no untrusted-string interpolation.
  - Output: a convention document under `shared/` that Phase 2.3 and Phase 3 must cite.
- F2.2-02 — Path-containment helper concept
  - Description: Specify a containment check that confines analyzer/fixer file access to the target repo root and rejects traversal.
  - Output: a containment-rule specification with accept/reject examples.
- F2.2-03 — Shell-string and dangerous-exec detection rules
  - Description: Define the patterns flagged as `command-injection` and `dangerous-exec` in audited code.
  - Output: a categorized detection-rule table with severities and confidences.
- F2.2-04 — Path-traversal sink detection rules
  - Description: Define the read/write sink patterns flagged as `path-traversal`.
  - Output: detection-rule entries with evidence-format examples.
- F2.2-05 — Seeded-defect and safe-counterpart fixtures
  - Description: Build fixtures with each unsafe pattern and matching safe forms that must not trigger findings.
  - Output: fixture layout and expected per-category finding counts.

## 8. Acceptance Criteria

- The structured argv convention is documented and explicitly forbids shell-string interpolation, and it is referenced by later sub-phases as the mandatory invocation primitive.
- Running the analyzer over the seeded fixtures produces the expected `command-injection`, `dangerous-exec`, and `path-traversal` findings with correct `path:line` evidence.
- Safe-counterpart fixtures produce zero findings, demonstrating the rules do not over-report.
- The path-containment specification rejects any access resolving outside the target repository root, with documented accept and reject cases.
- A stated, testable rule confirms QB never auto-executes repo-provided scripts absent explicit sandboxed authorization.
- Every emitted finding carries a category, severity, and confidence.

## 9. Validation and Test Approach

- Document validation: confirm the argv convention and path-containment rules are written with concrete accept/reject examples.
- Local smoke (proposed): run the analyzer over seeded-defect and safe-counterpart fixtures, asserting expected and zero finding counts respectively.
- Security validation: a containment test asserting that path resolution outside the repo root is rejected; this is the gating check for this sub-phase.
- Convention conformance (proposed): a test asserting any engine code that launches a process uses the argv form, not a shell string.
- Regression: keep `make check` and `python3 -m unittest discover -s tests` green so the planning product and sync invariants are unaffected.
- Live readiness: not applicable; detection is static and read-only, and no external process is executed against the target during this sub-phase.

## 10. Dependencies and Sequencing

- Depends on the Phase 1 `Finding` schema and analyzer interface for the shape of emitted findings.
- Should follow Phase 2.1 so the redaction contract is available when this analyzer quotes matched source lines.
- The argv convention authored here is a hard prerequisite for Phase 2.3 (which adapts external tools) and for Phase 3 (whose verification commands must use it).
- The path-containment concept is a prerequisite for any write-capable behavior in Phase 3.
- No live endpoints, credentials, or human approvals are required to implement or validate this static analyzer.

## 11. Risks and Mitigations

- Risk: the argv convention is documented but later code silently reverts to shell strings. Impact: the very injection class QB warns about reappears inside QB. Mitigation: pair the convention with a conformance test that flags shell-string process launches in the engine itself.
- Risk: traversal detection is too narrow and misses an exploitable sink. Impact: a malicious repo path escapes containment undetected. Mitigation: complement detection with a runtime path-containment check so escape is blocked even when a sink is not pattern-matched.
- Risk: injection detection over-reports on benign dynamic code. Impact: noise that erodes trust and feeds bad fixes downstream. Mitigation: require safe-counterpart fixtures to yield zero findings as a gating acceptance criterion, and attach lower confidence to ambiguous sinks.
- Risk: pattern-based detection cannot prove exploitability. Impact: findings may be theoretical. Mitigation: clearly label severity by sink danger and reserve auto-fix eligibility for high-confidence categories only.

## 12. Desired End State

QB has a tool-wide structured argv command-execution convention forbidding shell-string interpolation, a path-containment rule confining all file access to the target repo root, and a static analyzer that emits categorized `command-injection`, `dangerous-exec`, and `path-traversal` findings with evidence, severity, and confidence. Seeded-defect fixtures trigger the expected findings while safe counterparts stay clean, the containment rule is enforced by a test, and a conformance test guards against the engine itself reintroducing shell-string execution. Later phases now have a safe invocation primitive and a containment guarantee to build on.

## 13. Transition Criteria to the Next Sub-Phase

- The argv convention and path-containment rules are ratified, documented, and cited as the mandatory primitives for external execution.
- The analyzer passes its seeded-defect and safe-counterpart fixture runs, and the containment test rejects out-of-root access.
- The conformance test for argv-only process launches is in place so Phase 2.3 can adopt external tools without reintroducing shell-string risk.
- `make check` and the existing test suite remain green, and any new shared file is wired into the `scripts/sync.sh` MAP.
