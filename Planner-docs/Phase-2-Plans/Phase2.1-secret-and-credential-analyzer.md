# Phase 2.1 — Secret and Credential Analyzer

## 1. Context

This sub-phase opens Phase 2 (Analyzer Suite, maturity M2) by promoting the most battle-tested asset in the repository into the first first-class analyzer. The master plan (`Planner-docs/Main-Planning.md` section 5, "Artifact/evidence boundaries" and section 7, "Secret/credential handling during deep code analysis") demands that QB read entire repositories while never leaking or persisting secret values. The autopsy (`Planner-docs/Autopsy.md` section 9) records the current secret posture as "good" precisely because of `shared/scripts/validate_planner_docs.py`, whose `SECRET_PATTERNS` list (lines 113-120) and `scan_secrets` function (lines 519-534) already detect length-bounded OpenAI keys, GitHub PATs, AWS access keys, private-key headers, and Slack tokens, reporting only `name::path:line` and never the matched value. That scanner is, however, scoped to `Planner-docs/` (or the project root when that directory is absent), and it emits ad-hoc `error=` strings rather than the structured `Finding` records frozen in Phase 1. This sub-phase rebases the proven detection logic onto the Phase 1 `Finding` schema and analyzer interface so a secret-hygiene scan becomes a repeatable, graded, evidence-backed audit category over an arbitrary target repository.

## 2. Goal

Deliver a repository-wide secret-and-credential analyzer that, given any target repo, emits structured `Finding` records for each detected credential pattern with category `secret-hygiene`, a severity grade, a confidence value, and `path:line` evidence — while guaranteeing by construction that no matched secret substring is ever written to a finding, an evidence artifact, a log, or stdout. The analyzer must reuse the existing `SECRET_PATTERNS` regexes rather than reimplement them, and must run read-only with zero new runtime dependencies so the offline-core promise is preserved.

## 3. Description

The work converts a single-purpose, path-bound secret scan into a general analyzer plug-in. Concretely, the analyzer walks the target repository's tracked text files, applies the proven length-bounded regexes, and for every match constructs a `Finding` whose evidence captures the file path and one-based line number computed exactly as the existing scanner does (`text.count("\n", 0, match.start()) + 1`). The decisive new behavior is redaction-by-default: where the validator today appends `secret_pattern={name}::{path}:{line}` to its error list, the analyzer must emit a finding carrying the pattern name, a redacted excerpt (for example a fixed mask plus the trailing four characters only when policy permits, otherwise a full mask), and never the raw capture group. This belongs early in Phase 2 because secret hygiene is the lowest-risk, highest-trust analyzer to validate the whole `Finding`-emission contract end to end, and because a leaking auditor is unacceptable before any other analyzer reads untrusted code. It reduces project risk by proving the redaction discipline once, so every later analyzer inherits a known-safe evidence path, and it prepares Phase 3 by giving the fixer a clean, high-confidence finding category (credential removal or rotation prompts) to target first.

## 4. Scope

- Adapt `SECRET_PATTERNS` and the `scan_secrets` walk into an analyzer that conforms to the Phase 1 analyzer interface.
- Map each pattern to a `secret-hygiene` finding category with per-pattern default severity (for example private-key headers at the highest grade, generic tokens lower).
- Implement redaction-by-default for all outputs: findings, evidence artifacts, logs, and console summaries.
- Confidence scoring per pattern, reflecting how length-bounded and specific each regex is.
- A binary-file and large-file skip policy mirroring the existing `UnicodeDecodeError`/`OSError` guard.
- Fixture seeding: a synthetic test repo with planted non-real credential strings that match the regexes.
- Documentation note describing the redaction contract for downstream analyzers.

## 5. Out of Scope

- Entropy-based or machine-learning secret detection beyond the existing length-bounded regexes.
- Networked secret-validation (for example calling a provider API to check whether a token is live).
- Automatic secret rotation, revocation, or removal — those are fixer concerns deferred to Phase 3.
- Expanding the pattern catalogue with many new vendor formats; pattern growth is a follow-on, not this slice.
- Git-history scanning of past commits; this slice audits the working-tree snapshot only.
- Any write to the target repository; this analyzer is strictly read-only.

## 6. Current Repository Evidence

Direct evidence anchors this sub-phase. `shared/scripts/validate_planner_docs.py` defines `SECRET_PATTERNS` at lines 113-120 with six named regexes (`openai_api_key`, `github_pat`, `github_legacy_pat`, `aws_access_key`, `private_key`, `slack_token`) and the `scan_secrets` function at lines 519-534 that walks files, skips `.git`, tolerates undecodable files, and records only `name::path:line`. The committed-secret invariant is exercised by `tests/test_no_committed_secrets.py`, and the autopsy's own length-bounded scan over tracked source returned zero matches, so the repository itself is a clean negative fixture. The scanner is wired into every host through `scripts/sync.sh` (the MAP entries copying `scripts/validate_planner_docs.py` into all three platforms), meaning any extracted analyzer module must likewise be added to that MAP to reach Cursor and Codex. What is absent is any `secret-hygiene` finding category, any redaction layer beyond "do not print the value," and any positive fixture containing planted credentials.

## 7. Planned Work Breakdown

- F2.1-01 — Secret analyzer adapter
  - Description: Wrap the existing `SECRET_PATTERNS` and the `scan_secrets` walk behind the Phase 1 analyzer interface so the scan emits `Finding` records instead of raw error strings.
  - Output: an analyzer module specification under `shared/` plus a MAP entry note for `scripts/sync.sh`.
- F2.1-02 — Severity and confidence mapping
  - Description: Assign each pattern a default severity (private-key highest) and a confidence reflecting regex specificity.
  - Output: a documented pattern-to-grade table embedded in the analyzer spec.
- F2.1-03 — Redaction-by-default layer
  - Description: Define the masking rule applied to every output channel so no raw capture ever leaves the process.
  - Output: a redaction contract section that later analyzers cite.
- F2.1-04 — Positive and negative fixtures
  - Description: Create a fixture repo with planted, non-real strings matching each regex, and reuse the clean repo as the negative case.
  - Output: fixture layout description and expected finding counts per pattern.
- F2.1-05 — Conformance and no-leak test design
  - Description: Specify a test asserting emitted finding counts and asserting no raw secret substring appears in any output.
  - Output: test plan referencing `tests/` conventions.

## 8. Acceptance Criteria

- Running the analyzer over the planted-credential fixture yields one `secret-hygiene` finding per planted match, each with correct `path:line` evidence and a pattern name.
- No output channel (finding body, evidence file, log line, console summary) contains any raw matched secret substring; an automated assertion proves this.
- Running the analyzer over the current QB repository produces zero `secret-hygiene` findings, matching the autopsy's zero-match baseline.
- The analyzer reuses `SECRET_PATTERNS` rather than redefining the regexes, demonstrated by a single shared definition.
- The analyzer performs no writes to the target repository and adds no third-party runtime dependency.
- Per-pattern severity and confidence values are present on every emitted finding.

## 9. Validation and Test Approach

- Document validation: confirm this sub-plan and the analyzer spec describe the redaction contract and the pattern-to-grade table.
- Local smoke (proposed): run the new analyzer over the planted-credential fixture and over the QB repo, asserting expected finding counts.
- Security validation: an automated no-leak assertion scanning every output stream for raw matches; this is the gating check for this sub-phase.
- Regression: continue running `python3 -m unittest discover -s tests` so `tests/test_no_committed_secrets.py` and the existing planning-product checks stay green.
- CI: extend the existing `make check` flow only after the no-leak test passes locally; mark the analyzer test as a new gate.
- Live readiness: not applicable here — the analyzer is offline and read-only, so there is no live-credential surface to activate.

## 10. Dependencies and Sequencing

- Hard dependency on Phase 1: the `Finding` schema and analyzer interface must be frozen before this adapter is written, because every finding shape is consumed here.
- Requires the Phase 1 fixture-repo scaffolding so a planted-credential fixture can be added alongside it.
- No live credentials, network access, or human approval are required to implement or validate this analyzer.
- Must update `scripts/sync.sh` MAP whenever a new `shared/` analyzer file is introduced, so Cursor and Codex receive it byte-for-byte.
- Blocks no other Phase 2 analyzer directly, but its redaction contract is a prerequisite reference for any analyzer that quotes source lines.

## 11. Risks and Mitigations

- Risk: a redaction gap leaks a real credential into evidence or logs. Impact: catastrophic trust loss and possible credential exposure. Mitigation: mask at the point of finding construction, never store the raw match, and gate the sub-phase on an automated assertion that no output stream contains a raw match.
- Risk: rebasing onto the `Finding` schema accidentally regresses the planning-product secret scan that the validator still relies on. Impact: a previously caught committed secret slips through. Mitigation: keep one shared `SECRET_PATTERNS` definition, leave the validator's planning path intact, and keep `tests/test_no_committed_secrets.py` green.
- Risk: length-bounded regexes miss novel credential formats. Impact: false negatives in audits. Mitigation: document the known coverage boundary explicitly and treat pattern expansion as a tracked follow-on rather than silently claiming completeness.
- Risk: scanning large or binary files is slow or noisy. Impact: degraded audit performance. Mitigation: reuse the existing decode-failure skip and add a file-size threshold for the working-tree walk.

## 12. Desired End State

QB has a read-only, dependency-free secret-and-credential analyzer that emits graded, confidence-scored `secret-hygiene` findings for an arbitrary repository, with redaction guaranteed at construction time so no raw secret value can reach any output. The analyzer reuses the proven `SECRET_PATTERNS` and walk logic, is wired through `scripts/sync.sh` to all three hosts, ships with a planted-credential positive fixture and the clean QB repo as a negative fixture, and is covered by a no-leak assertion. The planning product's existing secret behavior is unchanged.

## 13. Transition Criteria to the Next Sub-Phase

- The `Finding`-emitting secret analyzer passes its conformance test and the no-leak assertion on both fixtures.
- A zero-finding run over the QB repo confirms parity with the autopsy baseline.
- The redaction contract is written down in a form the command-execution analyzer (Phase 2.2) can cite when it quotes matched source.
- `tests/test_no_committed_secrets.py` and the wider `make check` flow remain green, and the sync MAP includes any new shared analyzer file.
