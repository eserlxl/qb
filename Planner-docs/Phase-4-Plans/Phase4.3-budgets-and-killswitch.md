# Phase 4.3 — Budgets and Kill-Switch

## 1. Context

This sub-phase sits inside Phase 4 of `Planner-docs/Main-Planning.md` (orchestrator/policy, M3->M4) and supplies the two safety primitives that make an *unattended* run survivable: hard budgets and a kill-switch. Main-Planning section 7 names "Cost/runtime blowup in unattended mode" as a first-class risk whose mitigation is "hard budgets (max findings/fixes/iterations/wall-time/tokens) enforced by the orchestrator, with fail-closed stop-and-report," and `Planner-docs/Autopsy.md` section 10 confirms QB has "no kill-switch ... no cost/iteration budget." It depends on the Phase 4.1 policy schema (which carries the budget fields) and on the Phase 4.2 enforcement seam (the point at which a budget check or a kill signal can halt promotion). Its job is bounded resource control plus a clean emergency stop that leaves the working tree consistent, completing the orchestrator's ability to run without a human babysitting each step.

## 2. Goal

Deliver a budget-metering layer and a kill-switch such that any unattended run halts deterministically and leaves the tree in a consistent, fully-described state when it hits a ceiling or is signalled to stop: when any hard budget (maximum findings considered, maximum fixes applied, maximum orchestration iterations, maximum wall-time, maximum token spend) is reached the run stops and reports rather than continuing, and when the kill-switch is triggered mid-run the orchestrator finishes or reverts the in-flight fix to a known-good boundary and emits a stop report. The goal is met when a fixture run that would exceed a budget provably stops at the ceiling, and a kill-signalled run provably ends with either a completed-and-verified or fully-reverted in-flight fix — never a half-applied one.

## 3. Description

This sub-phase prevents the two failure modes unique to autonomy without a human at the keyboard: runaway resource consumption and an unstoppable run. The problem is that an autonomous loop over a large repository can iterate indefinitely, apply ever more fixes, or burn unbounded tokens, and that without a clean stop a halt could leave a fix half-applied. The work defines a budget model whose ceilings live in the Phase 4.1 policy, a metering mechanism that counts findings/fixes/iterations and tracks wall-time and token spend as the run proceeds, and a fail-closed stop-and-report behavior that triggers the moment a ceiling is crossed. It also defines a kill-switch contract: a signal the orchestrator polls at safe checkpoints (notably the boundary between fixes, never mid-patch) so that an interrupt either lets the current verified fix finish and be recorded, or reverts the in-flight fix via its reversal handle, then exits with a stop report. It belongs at this point because budgets and the kill-switch are cross-cutting gates that compose with autonomy-level enforcement (4.2) and must exist before any genuine end-to-end unattended A2 run — the very acceptance signal Main-Planning lists for Phase 4. It reduces risk by capping cost and guaranteeing tree consistency on stop, and it prepares Phase 5 reporting by defining the stop-report contents.

### 3.1 Budget categories and ceilings

The model covers five independent ceilings — findings considered, fixes applied, orchestration iterations, wall-time, and token spend — each evaluated independently so the run stops at whichever is hit first. Ceilings are read from policy and default to conservative values when unspecified.

### 3.2 Safe-checkpoint halting

The kill-switch is honored only at safe checkpoints between atomic fix units, never in the middle of a patch or verification. This guarantees that a stop never bisects a fix: the in-flight unit is either completed-and-verified or reverted to its reversal handle before exit.

## 4. Scope

- The budget model: the five ceiling fields (max findings, max fixes, max iterations, max wall-time, max token spend), their conservative defaults, and their home in the Phase 4.1 policy schema.
- The metering contract: how the orchestrator counts/accumulates each resource as the run proceeds and where the per-ceiling check fires.
- The fail-closed stop-and-report behavior when any ceiling is reached, including the exit-code contract for headless use.
- The kill-switch contract: the stop signal, the safe-checkpoint polling points, and the in-flight-fix resolution rule (finish-and-record or revert-to-known-good).
- The stop-report contents: which ceiling/signal triggered the stop, what was completed, what was reverted, and the resulting tree state.
- A test plan asserting stop-at-ceiling behavior and tree-consistency-after-kill behavior.

## 5. Out of Scope

- The policy schema definition itself (Phase 4.1); this sub-phase adds the budget fields' semantics but the schema freezing is owned there.
- Autonomy-level side-effect enforcement (Phase 4.2); budgets and the kill-switch compose with that layer but do not redefine it.
- Cross-review verdicts (Phase 4.4).
- Full telemetry/metrics emission and the JSON/SARIF report format (Phases 5 and 7); this sub-phase defines only the minimal stop-report fields needed for a safe halt.
- The fixer's patch generation and the isolation/reversal primitive (Phase 3), which the kill-switch's revert path consumes.
- Distributed/parallel-run coordination or multi-process budget sharing; the model targets a single unattended run.

## 6. Current Repository Evidence

There is no budget model, no metering, and no kill-switch anywhere in the repository — `Planner-docs/Autopsy.md` section 10 explicitly lists "no cost/iteration budget" and "no kill-switch," and section 13's `AUTOPSY-P1-01` ties this to the absent policy/autonomy/budget engine. The only existing notion of a bounded run is the prose stop condition in `shared/planners/fourth-planner.md` (line 30): "stop on success, on a blocker that needs the user, or if the audit gate forbids implementation" — a manual, single-slice stop, not a metered ceiling. The existing exit-code convention this sub-phase's stop-report should align with is in `finalize` of `shared/scripts/validate_planner_docs.py` (line 555): exit 1 on any error, exit 0 otherwise — and CI consumes that via `make check` in `.github/workflows/validate.yml`. The reversal-handle mechanism the kill-switch revert path depends on is the Phase 3 isolation primitive flagged net-new in `AUTOPSY-P0-02`. No current test exercises run-duration, iteration count, or interrupt handling, so the budget and kill tests proposed here are a new surface following the `tests/` conventions.

## 7. Planned Work Breakdown

- F4.3-01 — Define the five-ceiling budget model
  - Description: Specify max findings, max fixes, max iterations, max wall-time, and max token spend as independent ceilings with conservative defaults, and place them in the Phase 4.1 policy schema.
  - Output: a budget-field specification with default values and per-field semantics.
- F4.3-02 — Specify the metering contract
  - Description: Define how each resource is counted/accumulated during a run and the exact points where the per-ceiling check is evaluated (for example before considering the next finding, before applying the next fix, at each iteration boundary).
  - Output: a metering specification listing each counter, its increment point, and its check point.
- F4.3-03 — Fail-closed stop-and-report behavior
  - Description: Define that crossing any ceiling immediately stops the run (no further finds or fixes) and emits a stop report; specify the headless exit-code contract distinguishing clean-finish, budget-stop, and kill-stop.
  - Output: a stop behavior specification with the exit-code mapping.
- F4.3-04 — Kill-switch contract
  - Description: Define the stop signal, the safe checkpoints at which it is polled (between atomic fix units, never mid-patch/mid-verify), and the resolution rule for an in-flight fix (finish-and-record if already verified, else revert via reversal handle).
  - Output: a kill-switch specification with the checkpoint list and the in-flight resolution decision tree.
- F4.3-05 — Stop-report contents
  - Description: Enumerate the minimal fields the stop report must carry: trigger (which ceiling or the kill signal), fixes completed, fixes reverted, and final tree-consistency state.
  - Output: a stop-report field list usable by Phase 5 reporting.
- F4.3-06 — Budget and kill test plan
  - Description: Specify tests that drive a fixture run past a ceiling (assert stop-at-ceiling) and that signal a kill mid-run (assert the in-flight fix is either completed-and-verified or fully reverted, with no half-applied state).
  - Output: a test plan section naming proposed modules and their assertions.

## 8. Acceptance Criteria

- A budget model defines all five independent ceilings with conservative defaults, each sourced from the Phase 4.1 policy and each capable of stopping the run on its own.
- The metering contract names, for every resource, where it is counted and where its ceiling is checked, so no resource can overrun unchecked.
- Crossing any ceiling deterministically halts the run and produces a stop report; the headless exit-code contract distinguishes a clean finish from a budget-triggered stop and from a kill-triggered stop.
- The kill-switch is honored only at safe checkpoints between atomic fix units, and the in-flight-fix resolution rule guarantees no half-applied fix remains after a stop.
- A fixture-run test demonstrates a stop exactly at a ceiling, and a kill-signal test demonstrates a consistent tree (in-flight fix completed-and-verified or fully reverted) afterward.
- Local readiness (metering and kill behavior assertable via fixture tests) is separated from live readiness (a real long-running unattended run hitting a real wall-time or token ceiling).
- No secrets, tokens, or credentials are written into any budget field, stop report, or plan text.

## 9. Validation and Test Approach

- Document validation: run `python3 shared/scripts/validate_planner_docs.py --root . --mode step2 --strict` to confirm structure and absence of placeholder tokens.
- Local smoke (proposed): a proposed `tests/test_budgets.py` that configures a low max-fixes ceiling on a fixture and asserts the run stops exactly at the ceiling and reports it.
- Local smoke (proposed): a proposed `tests/test_killswitch.py` that signals a stop between fix units and asserts the working tree is consistent (no half-applied fix) and the stop report records what completed/reverted.
- Local validation: assert the headless exit code differs for clean-finish vs budget-stop vs kill-stop, consistent with the existing exit-1-on-error convention in `finalize`.
- CI: add the budget and kill tests to `make check` so they run via `.github/workflows/validate.yml`.
- Live readiness: deferred — a genuine wall-time or token-spend ceiling under a real model-backed run is validated when the headless surface lands (Phase 6) and during production hardening (Phase 7).

## 10. Dependencies and Sequencing

- Depends on Phase 4.1 for the policy schema that carries the five budget fields.
- Depends on Phase 4.2 for the enforcement seam at which budget and kill checks gate promotion, and on Phase 3 for the reversal handles the kill revert path uses.
- Should land before any advertised end-to-end unattended A2 run, since that run's safety claim depends on budgets and a working kill-switch.
- Token-spend metering requires a token-accounting source from the host runtime; until that is available, the token ceiling is specified but its live enforcement is confirmed during the headless work in Phase 6.
- Requires no live credentials or network for findings/fixes/iterations/wall-time ceilings; wall-time uses a local clock.

## 11. Risks and Mitigations

- Risk: a resource is metered but its ceiling check is placed after the resource is already consumed. Impact: the run overruns the budget by one unit or more. Mitigation: the metering contract requires the check *before* consuming the next unit (before the next find/fix/iteration), asserted by the stop-at-ceiling test.
- Risk: the kill-switch is polled mid-patch and bisects a fix. Impact: a half-applied, inconsistent working tree. Mitigation: polling is restricted to safe checkpoints between atomic fix units, with the in-flight fix resolved to a known-good boundary before exit.
- Risk: token-spend accounting is unavailable or inaccurate from the host. Impact: the token ceiling silently never fires. Mitigation: specify the ceiling now, treat absence of a token source as a fail-closed condition (lower the iteration ceiling), and confirm live token metering during Phase 6 headless work.
- Risk: ambiguous exit codes make headless callers misread a budget-stop as success. Impact: CI passes a run that did not finish its work. Mitigation: a distinct exit code per stop reason, documented in the stop-report contract and asserted by tests.

## 12. Desired End State

An unattended run is bounded on five independent axes and can be stopped safely at any time. Crossing a findings, fixes, iterations, wall-time, or token ceiling halts the run at the boundary and emits a stop report with a distinct headless exit code. A kill-switch, honored only between atomic fix units, ends the run with the in-flight fix either completed-and-verified or fully reverted to its reversal handle, never half-applied, and records the outcome. Budget and kill tests are specified (and green under `make check` after implementation), giving the orchestrator the resource control and emergency-stop guarantees required before any genuine autonomous run is advertised.

## 13. Transition Criteria to the Next Sub-Phase

- All five budget ceilings are defined with conservative defaults and wired conceptually to the Phase 4.1 policy schema.
- The metering contract checks each ceiling before consuming the next unit, proven by a stop-at-ceiling fixture test.
- The kill-switch resolves any in-flight fix to a consistent known-good state and emits a stop report, proven by a kill-signal fixture test.
- The headless exit-code contract distinguishes clean-finish, budget-stop, and kill-stop unambiguously.
- Role separation and cross-review remain unaddressed and are handed to Phase 4.4, which adds an authorship-versus-judgment gate on top of the verified, budgeted, level-enforced run.
