# Phase 6.3 — Headless CLI and CI Exit Codes

## 1. Context

This sub-phase adds the fourth launch surface — a non-interactive headless mode — completing the parity story begun by Phase 6.1 (canonical shared engine) and Phase 6.2 (interactive host adapters). The parent Phase 6 goal in `Planner-docs/Main-Planning.md` section 6 is to ship the engine "plus a non-interactive CI mode," and the desired end state is "QB audits+hardens identically on Claude Code, Cursor, Codex, and headless CI." Main-Planning section 4 (Operational target) is explicit: "A headless mode runs the full audit->harden->report loop non-interactively for CI, with exit codes that gate a pipeline." The autopsy (`Planner-docs/Autopsy.md` section 10) records that headless/CI runnability is currently entirely absent — "there is no headless entry point ... no pipeline exit-code contract" — and section 13 lists "no headless surface" as a hard live-readiness blocker. This sub-phase turns that blocker into a working, dependency-light entry point whose exit codes a CI pipeline can act on, while honoring QB's zero-setup promise.

## 2. Goal

Deliver a non-interactive headless entry point that runs the full audit->harden->report loop end to end against a target repository and returns deterministic, documented exit codes that gate a CI pipeline, operating with only the Python standard library and bash so the zero-setup property is preserved. The outcome is that an unattended pipeline can invoke QB, receive a pass/findings/error signal through its process exit code, and consume the machine-readable report without any interactive prompt.

## 3. Description

The problem this sub-phase solves is that all existing launch paths are interactive and in-session: the planning commands and the Phase 6.2 adapters expect a human to drive gates, which a CI runner cannot do. A pipeline needs a single command that takes a target repo, an autonomy level, a policy, and budgets, runs the loop without prompting, writes the structured report and evidence to the fixed-name output directory, and exits with a code the pipeline can branch on. This belongs at this point because the engine is canonical (Phase 6.1) and launchable interactively (Phase 6.2), so the remaining gap is purely the unattended driver and its exit-code contract. It reduces project risk by giving the autonomy model a fail-closed terminal behavior: a policy or budget boundary, or an internal error, maps to a distinct non-zero exit so CI never mistakes an aborted run for a clean one. It prepares Phase 7's production hardening and self-audit, which depend on an unattended run that can be scheduled and observed. The dependency-light constraint is load-bearing: the headless mode must not betray the zero-setup property that the autopsy confirms is core to QB, so it reuses the same standard-library-only posture as `scripts/validate_planner_docs.py` and the bash `validate.sh` scripts.

## 4. Scope

- A headless entry point (a standard-library Python script and/or a thin bash wrapper) under `shared/` so it syncs to every platform and is callable outside any host session.
- A non-interactive argument surface: target repository path, autonomy level (A0-A3), policy reference, budget references, and output directory selection, with safe conservative defaults.
- A documented, stable exit-code contract distinguishing at least: clean (no actionable findings), findings-present-above-threshold, fixes-applied-and-verified, policy/budget boundary hit (fail-closed), and internal error.
- Writing the machine-readable report and per-run evidence to the fixed-name output directory convention established for the engine.
- CI usage documentation: an example pipeline step invoking the headless mode and branching on its exit code, added to the per-platform `docs/` set.
- A sample CI invocation wired into `.github/workflows/validate.yml` or a sibling workflow that runs the headless mode against a fixture and asserts the exit code.

## 5. Out of Scope

- The interactive host launch adapters — delivered in Phase 6.2.
- Authoring the analyzers, fixer, verifier, or policy engine — delivered in Phases 1-5.
- Mandatory network access or third-party package installation; networked analyzers stay opt-in per Main-Planning section 5 and are not required for the headless core.
- Full telemetry/metrics emission and rollback drills — that is Phase 7.
- Manifest version alignment and codex structural normalization — that is Phase 6.4.
- Enabling A3 commit/push/PR by default in headless mode; deliver behavior remains explicit opt-in.

## 6. Current Repository Evidence

Current repository evidence for this sub-phase is limited because no headless entry point exists today. The repository proves the dependency-light pattern the headless mode must follow: `scripts/sync.sh` declares itself "Dependency-free: bash + coreutils," `platforms/codex/scripts/validate.sh` states it "Uses only bash and the Python standard library. No PyYAML, no network," and `.github/workflows/validate.yml` runs a single `make check` step on `ubuntu-latest` with `python-version: "3.x"` and no extra installs. The exit-code discipline already exists in miniature: `scripts/sync.sh --check` exits 1 on drift and exits 2 on an unknown argument, and the per-platform `validate.sh` scripts `set -euo pipefail` and emit tokenized failure lines like `missing_required_file=`. The `Makefile` `check` target chains `sync.sh --check`, three `validate.sh` runs, and `python3 -m unittest discover -s tests`, demonstrating the standard-library-only CI posture the headless mode must extend. No `QB-Audit/`-style output directory or JSON/SARIF emitter is present yet, consistent with the autopsy's operational-readiness findings.

## 7. Planned Work Breakdown

- F6.3-01 — Headless entry point under shared/
  - Description: Author a standard-library headless driver (Python and/or a thin bash wrapper) under `shared/` that runs the loop non-interactively and is wired into the Phase 6.1 sync `MAP`.
  - Expected output: A synced, dependency-light headless executable callable outside any host session.
- F6.3-02 — Non-interactive argument and defaults surface
  - Description: Define the CLI arguments (target repo, autonomy level, policy, budgets, output dir) with conservative defaults and no interactive prompting.
  - Expected output: An argument contract that runs to completion unattended, defaulting to the safest autonomy level.
- F6.3-03 — Exit-code contract specification
  - Description: Specify a stable mapping from run outcomes to exit codes (clean, findings-above-threshold, fixes-applied-verified, policy/budget-boundary fail-closed, internal error) that a pipeline can branch on.
  - Expected output: A documented exit-code table that is deterministic and fail-closed on any boundary or error.
- F6.3-04 — Machine-readable output to the fixed-name directory
  - Description: Ensure the headless run writes the structured report and per-run evidence to the engine's fixed-name output directory without printing secret values.
  - Expected output: A populated output directory whose report a CI step can parse and archive.
- F6.3-05 — CI usage docs and a sample gating workflow
  - Description: Document a CI pipeline step that invokes the headless mode and branches on its exit code, and add a sample workflow run against a fixture asserting the expected code.
  - Expected output: Per-platform CI usage docs plus a workflow step that proves the exit-code contract gates a sample pipeline.

## 8. Acceptance Criteria

- A single headless command runs the audit->harden->report loop against a target repo with no interactive prompt and terminates on its own.
- The process exit code follows the documented contract: a clean repo, a findings-present repo, a fixes-applied repo, a policy/budget-boundary abort, and an internal error each yield a distinct, documented code, with every boundary or error mapping to a non-zero fail-closed code.
- The headless mode runs using only the Python standard library and bash, requiring no package install and no mandatory network, preserving QB's zero-setup property.
- The run writes a machine-readable report and per-run evidence to the fixed-name output directory, and no secret value is written to any report, log, or evidence artifact.
- A sample CI workflow invokes the headless mode against a fixture and asserts the expected exit code, demonstrating pipeline gating; this is documented as live readiness distinct from the local document/unit checks.
- A3 deliver/commit/push/PR is not enabled by default in headless mode and requires explicit opt-in.

## 9. Validation and Test Approach

Document validation: confirm the exit-code table is complete, deterministic, and fail-closed, and that CI usage docs show a real branch on the exit code. Local smoke: run the headless mode against the QB repository itself at the most conservative autonomy level and confirm it completes, writes the output directory, and returns the documented clean/findings code without network access. Local unit/CI validation: run `make check` to confirm the headless script syncs cleanly (`scripts/sync.sh --check`), passes the platform `validate.sh` presence checks, and does not break the existing unit suite. Live readiness: the sample gating workflow (proposed addition alongside `.github/workflows/validate.yml`) runs the headless mode against a fixture repo and asserts the exit code — this is the first live, end-to-end readiness signal in Phase 6 and is explicitly distinguished from the local checks. Security validation: confirm via the existing secret-scan path that the report and evidence contain no secret values. The headless command and its workflow step are proposed new additions; `make check`, `scripts/sync.sh --check`, and the unit discover command already exist.

## 10. Dependencies and Sequencing

This sub-phase depends on Phase 6.1 (the headless script must be a mapped `shared/` artifact) and on Phase 6.2 (it reuses the F6.2-01 run-brief contract for its argument surface). It depends on Phases 1-5 for the loop, the policy/budget model, and the fixed-name output directory and report format. It should precede Phase 7, whose production hardening, scheduled runs, and self-audit assume a working unattended entry point. It interacts with Phase 6.4: the sample gating workflow and the headless script's platform destinations must reconcile with whatever structure Phase 6.4 ratifies. No live external credentials are required for the offline core; if the opt-in networked analyzers are later exercised in headless mode, those credentials are a separate, explicitly-gated concern. The blocking decision is the supported headless/CI surface for v1, which Main-Planning section 9 flags for human confirmation.

## 11. Risks and Mitigations

- Risk: an aborted or errored headless run exits 0 and a pipeline treats it as clean. Impact: defects ship because CI never gated. Mitigation: the F6.3-03 exit-code contract maps every boundary and error to a distinct non-zero code, fail-closed, mirroring how `scripts/sync.sh` already exits 1 on drift and 2 on bad input.
- Risk: the headless mode pulls in a third-party dependency or requires network access. Impact: the zero-setup promise the autopsy calls core is broken. Mitigation: restrict the implementation to the Python standard library and bash, matching `validate.sh` and `sync.sh`, and keep networked analyzers opt-in and non-default.
- Risk: secrets surface in the machine-readable report or evidence written during an unattended run. Impact: secret leakage into archived CI artifacts. Mitigation: redact-by-default in all output and rely on the committed-secret scan test to keep the repository clean of any fixture-derived secrets.
- Risk: headless mode runs unbounded on a large repo and hangs CI. Impact: runaway cost and stuck pipelines. Mitigation: enforce the Phase 4 budgets (max findings/fixes/iterations/wall-time) and fail closed with the budget-boundary exit code when a budget is hit.

## 12. Desired End State

QB has a non-interactive headless entry point, synced from `shared/` to every platform, that runs the full audit->harden->report loop against a target repository using only the Python standard library and bash. It returns a stable, documented set of exit codes — clean, findings-above-threshold, fixes-applied-verified, policy/budget-boundary, internal error — so a CI pipeline can branch deterministically and never mistakes an aborted run for success. It writes a machine-readable report and evidence to the fixed-name output directory with no secret leakage, defaults to conservative autonomy, and is demonstrated gating a sample CI workflow. The headless surface completes the four-way parity of Claude Code, Cursor, Codex, and CI.

## 13. Transition Criteria to the Next Sub-Phase

Before starting Phase 6.4, the following must hold: the headless entry point runs the loop unattended end to end and returns the documented exit code for clean, findings, fixes-applied, boundary, and error cases; it operates with no required third-party dependency and no mandatory network; the structured report and evidence land in the fixed-name output directory with no secret values; a sample workflow demonstrates exit-code-based pipeline gating; `make check` remains green with the headless script synced and presence-checked; and `git status --short` confirms only intended files (the `shared/` headless script, sync/validate updates, docs, and workflow) changed. A3 deliver behavior remains opt-in and is not activated by default.
