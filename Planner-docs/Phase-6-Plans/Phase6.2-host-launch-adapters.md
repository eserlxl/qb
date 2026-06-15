# Phase 6.2 — Per-Host Launch Adapters for Audit + Harden

## 1. Context

This sub-phase delivers the host-native launch surfaces for the audit->harden->report loop, sitting between Phase 6.1 (which makes the engine artifacts canonical and synced) and Phase 6.3 (which adds the non-interactive headless surface). The parent Phase 6 goal from `Planner-docs/Main-Planning.md` section 6 is to ship the engine "identically on all hosts." Main-Planning section 5 states the architectural principle directly: "The host adapters (Claude Code subagents/Task tool, Cursor goals, Codex goal-mode, and a headless CLI) are thin launch mechanisms — exactly the pattern QB already uses for its planning steps." QB already proves this pattern works for planning: `platforms/claude-code/commands/qb-plan.md` delegates Step 2 to the `qb-subplanner` subagent via the Task tool with an in-session fallback, `platforms/cursor/` mirrors the same flow through its skills, and `platforms/codex/plugins/qb/skills/qb/SKILL.md` hands off steps as Goal-mode prompts. This sub-phase reuses that exact launch grammar to drive the new engine loop, so behavior is identical across hosts while the launch glue stays host-native.

## 2. Goal

Provide one host-native launch adapter per host (Claude Code Task-tool subagent, Cursor goal/skill, Codex goal-mode) that drives the audit->harden->report loop at the user-selected autonomy level, reading the engine artifacts synced in Phase 6.1, so that the same logical run produces equivalent findings and fixes regardless of which host invoked it. The outcome is host-portable launch parity: a user on any of the three hosts can start an audit-and-harden run through their host's native mechanism and get the same engine behavior.

## 3. Description

The problem this sub-phase solves is that the engine, once canonical in `shared/`, still needs a host-appropriate trigger and orchestration shell on each platform. Each host launches long autonomous work differently: Claude Code uses slash commands that delegate to subagents through the Task tool with an in-session skill fallback; Cursor uses goal-backed skills; Codex uses a single goal-mode skill that reads bundled reference prompts and hands off step prompts. A naive approach would re-author the loop three times and let the hosts diverge in behavior — precisely the parity-drift risk the autopsy warns about. Instead this sub-phase keeps the loop logic in the synced engine and makes each host adapter a thin shell that supplies the run brief (target repo, autonomy level, policy, budgets) and invokes the engine, mirroring how `qb-plan.md` supplies a goal contract to `qb-subplanner`. This belongs here because the engine contract is now stable (Phase 6.1) but no host can yet start it; it reduces risk by reusing a launch pattern already validated by the planning product and its tests; and it prepares Phase 6.3, whose headless CLI becomes the fourth, non-interactive launch path over the same engine. The autonomy levels A0-A3 from Main-Planning section 5 are surfaced through each adapter as a run parameter, defaulting conservative, so the host launch never silently escalates write permission.

## 4. Scope

- A Claude Code launch path: a slash command plus a delegated subagent (mirroring `commands/qb-plan.md` -> `agents/qb-subplanner.md`) that starts the audit->harden->report loop with an in-session skill fallback.
- A Cursor launch path: a goal-backed skill under `platforms/cursor/skills/` that drives the same loop, consistent with Cursor's define-goal mechanism.
- A Codex launch path: goal-mode handoff prose in `platforms/codex/plugins/qb/skills/qb/SKILL.md` (and any `agents/openai.yaml` default-prompt addition) that launches the loop as a Goal-mode flow.
- A single run-brief contract shared by all three adapters: target repo path, autonomy level (A0-A3), policy reference, and budget references, declared before the loop starts.
- Conservative-by-default autonomy selection surfaced in each adapter, with explicit opt-in required to raise the level.
- Host-native help/description text for each new launch surface so the audit+harden capability is discoverable.

## 5. Out of Scope

- The engine loop logic itself (analyzers, fixer, verifier, orchestrator/policy) — authored in Phases 1-5 and merely launched here.
- The non-interactive headless CLI and pipeline exit codes — that is Phase 6.3.
- Manifest version alignment and codex structural normalization — that is Phase 6.4.
- Adding new shared engine artifacts or `MAP` entries — that was completed in Phase 6.1.
- Enabling A3 deliver/commit/push/PR behavior by default; A3 stays explicit opt-in per Main-Planning section 5.
- Any auto-commit, auto-push, auto-PR, or deploy action from the launch adapters.

## 6. Current Repository Evidence

The Claude Code launch grammar is concretely visible in `platforms/claude-code/commands/qb-plan.md`, which instructs the orchestrator to "run Step 2 by delegating to the `qb-subplanner` subagent via the Task tool (fallback: run the `qb-subplanner` skill in-session under the same goal contract)"; the matching subagent `platforms/claude-code/agents/qb-subplanner.md` declares `tools: Read, Grep, Glob, Write, Edit, Bash` and a full goal-contract block. Cursor exposes the same four commands (`platforms/cursor/commands/qb-audit.md`, `qb-autopsy.md`, `qb-implement.md`, `qb-plan.md`) and parallel skills (`platforms/cursor/skills/qb-{auditor,autopsy,implementer,planner,subplanner}/`). Codex differs structurally: it ships a single skill `platforms/codex/plugins/qb/skills/qb/SKILL.md` whose "Workflow Selection" routes step requests to bundled `references/*-Planner.md` prompts and hands off Steps 2-4 as Goal-mode text, plus `agents/openai.yaml` carrying the `default_prompt`. This three-way launch divergence is exactly the surface this sub-phase must mirror for the new loop without forking the engine logic.

## 7. Planned Work Breakdown

- F6.2-01 — Shared run-brief contract definition
  - Description: Specify the single run brief every adapter supplies to the engine: target repo path, autonomy level, policy reference, and budget references, with conservative defaults.
  - Expected output: A run-brief contract spec the three adapters reference identically, ensuring equivalent launches.
- F6.2-02 — Claude Code command + subagent adapter
  - Description: Author a slash command and a delegated subagent that start the loop via the Task tool with an in-session skill fallback, modeled on the `qb-plan.md`/`qb-subplanner.md` pair.
  - Expected output: A Claude Code launch surface that invokes the synced engine with the run brief and the chosen autonomy level.
- F6.2-03 — Cursor goal-backed skill adapter
  - Description: Author a Cursor goal/skill launch surface that drives the same loop, consistent with the define-goal mechanism used by the existing Cursor planning skills.
  - Expected output: A Cursor launch surface producing equivalent engine behavior to the Claude Code path.
- F6.2-04 — Codex goal-mode adapter
  - Description: Extend `platforms/codex/plugins/qb/skills/qb/SKILL.md` workflow selection (and any `openai.yaml` default prompt) to launch the loop as a Goal-mode flow over the bundled engine references.
  - Expected output: A Codex launch surface that hands off the audit->harden->report loop in goal mode.
- F6.2-05 — Cross-host launch parity check
  - Description: Define the equivalence assertion proving the three adapters launch the same loop with the same run brief and autonomy semantics, and extend the cross-host residue/manifest tests if new launch files introduce host tokens.
  - Expected output: A parity verification approach plus any test updates keeping `tests/test_no_cross_host_residue.py` green.

## 8. Acceptance Criteria

- Each host exposes a discoverable native launch surface for the audit+harden loop: a Claude Code command delegating to a subagent, a Cursor goal-backed skill, and a Codex goal-mode flow.
- All three adapters supply the same run-brief fields (target repo, autonomy level, policy, budgets) and default to the most conservative autonomy level, with raising the level requiring explicit user opt-in.
- The Claude Code adapter follows the existing delegate-via-Task-tool-with-in-session-fallback pattern, matching the structure of `commands/qb-plan.md`.
- No launch adapter performs any commit, push, PR, or deploy; A3 deliver behavior is reachable only through explicit opt-in and is not the default.
- `tests/test_no_cross_host_residue.py` and `tests/test_manifests_and_frontmatter.py` remain green, confirming new launch files carry no foreign-host tokens and valid frontmatter.
- Launch parity (same loop, same brief) is asserted as local readiness; live readiness of an end-to-end run is validated in Phase 6.3, not here.

## 9. Validation and Test Approach

Document validation: confirm each adapter's run brief lists identical fields and that the Claude Code path mirrors the `qb-plan.md` delegation grammar. Local smoke: run `make check`, which runs `bash scripts/sync.sh --check`, the three `validate.sh` scripts (each presence-checking host files), and the unit suite; new launch files must keep these green. Cross-host validation: run `python3 -m unittest tests.test_no_cross_host_residue` to confirm the new Claude Code adapter has no `$qb`/`.cursor-plugin`/`.codex-plugin` tokens, the Cursor adapter has no `$qb`/`.claude-plugin`/`.codex-plugin` tokens, and the codex adapter has none of the other hosts' markers. Frontmatter validation: `python3 -m unittest tests.test_manifests_and_frontmatter` confirms command/skill frontmatter names. Live readiness is explicitly deferred: an actual audit->harden run is exercised in Phase 6.3's headless path and Phase 7's self-audit, not in this launch-glue sub-phase. All listed commands already exist in the repository.

## 10. Dependencies and Sequencing

This sub-phase depends on Phase 6.1 having relocated and mapped the engine artifacts, so each adapter has a stable, synced target to launch. It also assumes the autonomy levels A0-A3 and the policy/budget references from Phases 0 and 4 exist, since the run brief surfaces them. It must precede Phase 6.3, because the headless CLI is the fourth launch path over the same loop and benefits from the run-brief contract defined in F6.2-01. It interacts with Phase 6.4: if Phase 6.4 normalizes the codex layout, the Codex adapter file locations are revised accordingly; authoring the Codex adapter against the current `plugins/qb/skills/qb/` shape is acceptable provided Phase 6.4's outcome is reconciled before release. No live credentials or network endpoints are required to author the adapters. The blocking decision is the default autonomy level surfaced by the adapters, which Main-Planning section 9 flags for human confirmation.

## 11. Risks and Mitigations

- Risk: the three adapters drift in behavior because each re-implements loop logic instead of launching the shared engine. Impact: a finding fixed on one host is missed on another. Mitigation: keep adapters thin and launch-only, sharing the F6.2-01 run-brief contract, exactly as `qb-plan.md` keeps logic in the subagent spec.
- Risk: a host adapter defaults to a permissive autonomy level. Impact: unintended writes during an interactive run. Mitigation: conservative default in F6.2-01, explicit opt-in to raise the level, and no commit/push/PR from any adapter.
- Risk: new launch files leak foreign-host tokens (for example `$qb` in a Claude Code file). Impact: cross-host residue test failure and confusing packaging. Mitigation: F6.2-05 keeps `tests/test_no_cross_host_residue.py` green and reviews each adapter against its platform's forbidden-token set.
- Risk: the Codex goal-mode handoff cannot express the full loop as a single prompt. Impact: a degraded or partial run on Codex. Mitigation: model the Codex flow on the existing multi-step `SKILL.md` workflow selection that already chains planning steps, decomposing the loop into goal-mode stages if needed.

## 12. Desired End State

Every host has a native, discoverable way to launch the audit->harden->report loop: a Claude Code slash command delegating to a subagent via the Task tool with an in-session fallback, a Cursor goal-backed skill, and a Codex goal-mode flow. All three supply an identical run brief, default to a conservative autonomy level, and never commit/push/PR by default. The launch glue is thin and host-native while the loop logic stays in the synced engine, so the same logical run behaves equivalently across hosts. The cross-host residue and frontmatter tests pass, confirming the new surfaces respect QB's packaging invariants.

## 13. Transition Criteria to the Next Sub-Phase

Before starting Phase 6.3, the following must hold: each of the three hosts exposes a native launch adapter for the loop using its own mechanism; all adapters share the F6.2-01 run brief and default to conservative autonomy; `make check` passes with the cross-host residue and frontmatter tests green; no adapter performs commit/push/PR/deploy by default; and `git status --short` confirms only platform launch files and any associated test updates changed. The headless, non-interactive launch path is intentionally still absent and is built next in Phase 6.3.
