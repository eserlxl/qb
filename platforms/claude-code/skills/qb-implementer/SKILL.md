---
name: qb-implementer
description: Gated Step 4 of the QB workflow - implement one bounded, reversible, testable slice from an audited plan. Use after the Step 3 audit when the user approves implementation, or via /qb-implement. Runs only when the audit is PASS or PASS_WITH_WARNINGS with no P0/P1 findings; otherwise it stops and recommends repair. Selects a single READY sub-plan, defines the validation command first, makes a minimal change, and verifies before claiming done.
metadata:
  version: "0.10.0"
---

# QB Implementer (Step 4, gated)

Implement one bounded, reversible slice from the audited QB plan. This is the only
QB step that changes source code, and it runs strictly behind the audit gate. Read
the full Step-4 spec in `fourth-planner.md` (next to this skill) and follow it end to end.

## Execution model

- **Delegated, in-session.** This step is run by the `qb-implementer` subagent via the Task tool. Read the bundled `fourth-planner.md` spec and follow it under the slice goal contract (objective / success evidence / scope bounds / stop condition) passed as the subagent task brief.
- **Fallback.** If subagents/Task are unavailable this session, run this skill in-session under the same in-context goal contract - behavior is identical.
- **Read the reliability notes.** Resolve the plugin root by walking up to the folder containing `.claude-plugin/plugin.json`, then read `references/workflow-quality.md` (especially Step 4 Token Discipline) before starting.
- **Scope is the user's workspace (cwd).** All reads/edits target the user's active workspace, never this plugin directory.

## Gate (mandatory, before any change)

Run the bundled validator in Step 4 mode (resolve `<plugin-root>` as above):

```bash
python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step4
```

- `BLOCKED` audit status -> do not implement; surface the blocker and minimal unblock action; stop.
- Any P0 or P1 finding -> do not implement; recommend the targeted repairs first (`qb-auditor` fix list + `qb-planner` repair loop); stop.
- PASS, or PASS_WITH_WARNINGS with only P2/P3 -> proceed and keep the warnings visible.
- `python3` unavailable -> read the audit's `## 1`, `## 12`, `## 13`, `## 15` sections and apply the same gate manually.

## Token discipline

- Read `.qb/sub-planning-audit.md` and `.qb/sub-planning-index.md` first.
- Select ONE `READY` or `READY_WITH_WARNINGS` sub-plan from the audit's `## 12. Step 4 Readiness Assessment` table (highest-priority first, unless the user names another).
- Load only that sub-plan and the repo files needed for the slice. Do not load all sub-plans.

## Slice procedure

1. Read `git status`, `README.md`, `AGENTS.md`, `Makefile`, the audit, and the selected sub-plan.
2. Determine the validation/test command FIRST; prefer existing repo commands over invented ones; write a failing test first when feasible.
3. Make the minimal, reversible change for the slice.
4. Run the focused tests plus the relevant `make` smoke/check target.
5. Verify with fresh evidence before claiming done.
6. Report an exact blocker or success; separate code-delivery status from external config/credential blockers.

## Leverage installed skills (optional, with fallback)

If installed/available, use these by scope; if not installed, do not stop - continue with the audit, the
selected sub-plan, repo instructions, and existing validation commands using the same principles:

- Superpowers `executing-plans` or `subagent-driven-development` for execution structure.
- Superpowers `test-driven-development` for code changes.
- Superpowers `verification-before-completion` before asserting the slice is done.
- The security review (`review-security` / security-review) for security-, policy-, secret-, or command-execution-sensitive changes.

## Stop rules

- One sub-plan and one reversible slice per run.
- Never write secrets, tokens, private keys, or local credentials.
- Do not commit, push, open a PR, deploy, or mutate external systems unless the user explicitly asks in this run.
- Do not claim success without running the validation command and confirming its output.

## Output

Report: which sub-plan slice was implemented, the validation command and its result,
files changed, remaining P2/P3 warnings to keep visible, and the recommended next slice
or the exact blocker. After a successful slice, the user can run `/qb-implement`
again for the next READY sub-plan.
