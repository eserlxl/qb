# Phase 7.4 — Self-Audit, Kill-Switch Runbook, and Production Gate

## 1. Context

This is the closing sub-phase of parent Phase 7 and of the master roadmap in `Planner-docs/Main-Planning.md`. The phase goal is to make unattended operation safe, observable, and recoverable at scale, summarized in section 6 as "QB hardens QB," with key acceptance signals "QB's self-audit run is clean; documented kill-switch and runbook." This sub-phase is where the engine is finally turned on itself: QB runs its own autonomous audit-and-harden loop against the QB repository (the ultimate dogfood) until the result is clean, the kill-switch and operations runbook for unattended use are written, and a final production-gated acceptance is defined that ties together the telemetry from 7.1, the rollback drills and release gates from 7.2, and the least-privilege and supply-chain guarantees from 7.3. The autopsy (`Planner-docs/Autopsy.md` section 10) lists the gaps this closes: "No kill-switch, no documented runbook for unattended operation," and section 13 (AUTOPSY-P1-01) ties the missing kill-switch to the autonomy-engine work. This sub-phase consumes every prior Phase 7 output and produces the single, observable, recoverable production gate that authorizes QB to run autonomously in earnest.

## 2. Goal

Run QB's autonomous audit-and-harden loop against the QB repository itself until it produces a clean, evidence-backed result, write the kill-switch and operations runbook for unattended use, and define a final production gate whose pass condition is that telemetry is emitted, rollback drills pass, least-privilege and supply-chain invariants hold, the kill-switch demonstrably halts a run, and the self-audit on QB is clean — the acceptance that authorizes earnest autonomous operation.

## 3. Description

This sub-phase is the integration and proof point for the whole production-hardening effort. The dogfood loop points `qb-audit` and `qb-harden` at the QB monorepo, treating QB as just another target repository: analyzers run read-only over `shared/`, `platforms/`, `scripts/`, and `tests/`; findings are graded with the frozen severity vocabulary; safely-fixable findings are remediated under isolation with verification; and the loop repeats until the audit is clean or the only remaining findings are explicitly accepted with rationale. This is more than a demo — it is the truest validation that the engine works, because QB must not break its own load-bearing invariants (the byte-for-byte `shared/` to `platforms/` sync, the plugin id `qb`, no cross-host residue, the fixed `Planner-docs/` identifiers) while hardening itself. In parallel it specifies the kill-switch: a single, fail-closed mechanism that halts an in-flight run immediately, leaves the working tree recoverable via the Phase 7.2 reversal handle, and is itself drillable. It writes the operations runbook: how to start, observe, pause, kill, and recover an unattended run; how to read the Phase 7.1 telemetry; and how to respond when a budget, policy, or release gate trips. Finally it composes the production gate from all prior signals. This belongs last because it can only be asserted once observability, recoverability, and least privilege exist — it is the capstone that converts a capable engine into a trustworthy, operable one.

## 4. Scope

- Self-audit dogfood run: QB audits and hardens the QB repository under an autonomy level appropriate to the release gate outcome, iterating to a clean or explicitly-accepted result.
- Invariant preservation during self-harden: the dogfood must not break sync byte-equality, plugin id `qb`, cross-host-residue cleanliness, or fixed artifact names.
- Kill-switch specification: a fail-closed, immediate halt mechanism that leaves the tree recoverable and is itself testable via a drill.
- Operations runbook: start/observe/pause/kill/recover procedures, how to read telemetry, and trip-response procedures for budget/policy/gate events.
- Production gate definition: the composite pass condition aggregating telemetry emission, rollback-drill pass, least-privilege and supply-chain conformance, kill-switch proof, and a clean self-audit.
- Acceptance evidence record: what the production gate writes (gate inputs, outcomes, and the clean-self-audit attestation) into the output convention.
- Accepted-findings register: how any residual self-audit finding that is intentionally not fixed is documented with rationale.

## 5. Out of Scope

- Defining telemetry metrics (Phase 7.1), the rollback drills and release gates themselves (Phase 7.2), or the least-privilege and supply-chain specifications (Phase 7.3) — this sub-phase composes and exercises them, it does not author them.
- Adding new analyzers or new fixer categories (Phases 2 and 3); the dogfood uses the analyzer and fixer surface that already exists.
- Multi-host launch wiring and the headless CLI (Phase 6); the self-audit runs on the existing surfaces.
- Enabling A3 commit/push/PR by default — even after a clean self-audit, A3 remains explicit opt-in.
- Production deployment infrastructure, hosted services, or any cloud activation; "production gate" here means a gated authorization to operate autonomously, not a deployment.
- Continuous scheduled self-auditing as an ongoing operation; this defines the gate and the first clean run, not a recurring schedule.

## 6. Current Repository Evidence

QB has never been audited by an autonomous engine because that engine does not yet exist; the autopsy (`Planner-docs/Autopsy.md` section 10) confirms there is "no runtime beyond the host session and the validator script" and section 4 lists the absent kill-switch, runbook, and budget model. What does exist and must be preserved during a self-harden is the invariant suite the dogfood could threaten: `scripts/sync.sh --check` enforces byte-equality of every mapped file plus an unmapped-source completeness guard, `make check` chains the sync check, three per-platform `validate.sh`, and `python3 -m unittest discover -s tests` across the test modules, and CI mirrors `make check` on push to `main` and every PR. The repo-wide secret scan (`tests/test_no_committed_secrets.py`) and the no-cross-host-residue test are the load-bearing safety nets the self-harden must keep green. A baseline read-only self-audit is feasible today only in the trivial sense that the doc validator already runs over `Planner-docs/`; a true code-level self-audit awaits the engine. No kill-switch, runbook, or production-gate definition exists anywhere in the tree.

## 7. Planned Work Breakdown

- F7.4-01 — Self-audit dogfood run procedure
  - Description: Define how QB audits and hardens the QB repository itself, iterating to a clean or explicitly-accepted result while operating at the release-gate-permitted autonomy level.
  - Output: a dogfood run procedure with the iteration and stop conditions.
- F7.4-02 — Invariant-preservation guard for self-harden
  - Description: Specify that the self-harden must keep `sync.sh --check`, the plugin id `qb`, cross-host-residue cleanliness, and fixed artifact names green throughout, treating any breach as a failed run.
  - Output: an invariant-preservation checklist tied to `make check`.
- F7.4-03 — Kill-switch specification
  - Description: Define a fail-closed, immediate halt that stops an in-flight run, preserves recoverability via the Phase 7.2 reversal handle, and is exercisable by a drill.
  - Output: a kill-switch specification plus a kill-switch drill.
- F7.4-04 — Operations runbook
  - Description: Write the start/observe/pause/kill/recover procedures, how to read Phase 7.1 telemetry, and how to respond when a budget, policy, or release gate trips.
  - Output: an operations runbook covering normal and trip-event operation.
- F7.4-05 — Production gate definition
  - Description: Compose the production gate as the conjunction of telemetry emission, rollback-drill pass, least-privilege and supply-chain conformance, a proven kill-switch, and a clean self-audit.
  - Output: a production-gate pass-condition specification and its evidence record.
- F7.4-06 — Accepted-findings register and acceptance evidence
  - Description: Define how residual self-audit findings that are intentionally unfixed are recorded with rationale, and what the gate writes as its acceptance attestation.
  - Output: an accepted-findings register format and an acceptance-evidence record.

## 8. Acceptance Criteria

- The self-audit dogfood procedure runs QB against QB and reaches either a clean audit or a fully-justified accepted-findings register, with evidence.
- The self-harden preserves every load-bearing invariant — `scripts/sync.sh --check` byte-equality, plugin id `qb`, no cross-host residue, fixed `Planner-docs/` names — verified by `make check` staying green.
- The kill-switch halts an in-flight run immediately, leaves the tree recoverable via the Phase 7.2 reversal handle, and its drill demonstrably proves the halt.
- The operations runbook covers start, observe, pause, kill, and recover, plus the response to a budget, policy, or release-gate trip.
- The production gate is defined as an explicit conjunction of telemetry emission, rollback-drill pass, least-privilege and supply-chain conformance, kill-switch proof, and a clean self-audit, and it writes an acceptance evidence record.
- Local readiness (a clean self-audit on the developer machine) is separated from live readiness (authorizing earnest autonomous operation), and A3 remains explicit opt-in even after the gate passes.
- No secret values, tokens, or credentials appear in the plan.

## 9. Validation and Test Approach

Document validation: `python3 shared/scripts/validate_planner_docs.py --strict` confirms the 13 headings and absence of placeholder tokens. Self-audit validation: the dogfood's success is asserted by a clean audit result plus a green `make check` (which runs `scripts/sync.sh --check`, the three `validate.sh` scripts, and `python3 -m unittest discover -s tests`), proving no invariant was broken while hardening. Kill-switch validation: a proposed kill-switch drill starts a run, triggers the halt, and asserts the run stopped and the working tree is recoverable to the pre-run baseline (clean `git status --short`). Runbook validation: a tabletop walkthrough confirms each documented procedure (start/observe/pause/kill/recover and each trip response) is executable against the real surfaces. Production-gate validation: the gate is exercised by feeding it the prior sub-phases' real signals and confirming it passes only when all conjuncts hold and fails closed otherwise. CI: `make check` remains the merge gate and the self-audit and kill-switch tests join it. Live readiness — authorizing recurring earnest autonomous operation — is the human-on-the-loop decision the gate informs, not something this plan asserts on its own.

## 10. Dependencies and Sequencing

Depends on every prior Phase 7 sub-phase: 7.1 (telemetry the gate and runbook read), 7.2 (rollback drills and release gates, and the reversal handle the kill-switch relies on), and 7.3 (the least-privilege and supply-chain invariants the gate confirms). It also depends on Phases 1 through 4 (the audit engine, analyzer suite, fixer, and policy/autonomy engine that make a real self-audit possible) and Phase 6 (the surfaces the self-audit runs on). Required decisions: the autonomy level for the self-audit (driven by the 7.2 release-gate outcome), and the acceptance threshold for residual findings. Required human approvals: passing the production gate authorizes autonomous operation and is a deliberate human-on-the-loop decision; enabling A3 remains a separate explicit opt-in. No live external credentials are required to audit QB itself. This sub-phase has no successor inside Phase 7 — it is the terminal gate of the roadmap.

## 11. Risks and Mitigations

- Risk: the self-harden breaks QB's own byte-for-byte sync or introduces cross-host residue while fixing a finding. Impact: QB damages itself, the worst possible advertisement for an autonomous hardener. Mitigation: treat `make check` (including `scripts/sync.sh --check` and the residue test) as a hard invariant guard the self-harden must keep green, failing the run on any breach.
- Risk: the kill-switch leaves a half-applied run, with some fixes kept and the tree in an inconsistent state. Impact: an operator who hits the emergency stop cannot trust the resulting tree. Mitigation: bind the kill-switch to the Phase 7.2 reversal handle so a halt is followed by a recoverable rollback, and prove it in a dedicated kill-switch drill asserting a clean post-halt status.
- Risk: the self-audit declares "clean" only because it under-reports on its own code. Impact: a falsely clean dogfood gives unwarranted confidence to enable autonomy. Mitigation: require the self-audit to meet the same Phase 7.1 precision floor as any target and to record any residual finding in the accepted-findings register with explicit rationale rather than silently dropping it.
- Risk: the production gate is treated as a one-time checkbox and drifts out of date as the engine evolves. Impact: autonomy keeps running on a stale authorization. Mitigation: define the gate to read current signals (latest telemetry, latest drill result, latest invariant state) so it re-evaluates rather than relying on a historical pass.
- Risk: passing the gate is read as license to enable A3 by default. Impact: unattended commit/push/PR without explicit opt-in, violating the master plan's safety contract. Mitigation: state explicitly that A3 stays opt-in regardless of gate outcome, and keep that rule in the runbook.

## 12. Desired End State

QB has audited and hardened itself to a clean or explicitly-accepted result without breaking a single load-bearing invariant, proven by a green `make check`. A fail-closed kill-switch halts any in-flight run and leaves the tree recoverable, demonstrated by a drill. An operations runbook documents how to start, observe, pause, kill, and recover an unattended run and how to respond to every trip event. A composite production gate — telemetry emitted, rollback drills passing, least-privilege and supply-chain invariants holding, kill-switch proven, self-audit clean — defines the verifiable authorization to operate autonomously in earnest, with A3 still requiring explicit opt-in. Parent Phase 7's goal of safe, observable, recoverable unattended operation, and the master plan's M5-to-M7 maturity target, are met.

## 13. Transition Criteria to the Next Sub-Phase

This is the terminal sub-phase of Phase 7 and of the roadmap, so its transition criterion is roadmap completion rather than a handoff to a successor. Before the roadmap is declared production-gated, the self-audit on QB must be clean or carry a fully-justified accepted-findings register, `make check` must remain green throughout the self-harden, the kill-switch drill must prove an immediate, recoverable halt, the operations runbook must cover all start/observe/pause/kill/recover and trip-response paths, and the composite production gate must pass on current signals while still treating A3 as explicit opt-in. Local readiness (a clean self-audit on a developer machine) must be clearly separated from the human-on-the-loop authorization of earnest autonomous operation. The document checker (`python3 shared/scripts/validate_planner_docs.py --strict`) must report this sub-plan as clean.
