---
name: qb-auditor
description: Goal-backed Step 3 of the QB planning workflow - a quality, coverage, consistency, and readiness audit of the Step 2 sub-plans. Use to verify that .qb/phase-*-plans/*.md and sub-planning-index.md are faithful to main-planning.md, complete, ordered, well-structured, and ready for implementation. Launched automatically as a Cursor goal via the define-goal skill and runs until every phase and sub-plan is inspected; produces only .qb/sub-planning-audit.md and returns PASS / PASS_WITH_WARNINGS / BLOCKED. Safe to run standalone for re-audits.
metadata:
  version: "0.12.0"
---

# QB Auditor (Step 3, goal-backed)

Audit the Step 2 output and write a single report. This is an audit-only step: it never fixes
the sub-plans and never changes the master plan. It is run as a **goal** so the audit covers
every phase and every sub-plan before stopping.

## Execution model

- **In-session, zero-setup.** Read the full Step-3 specification from `third-planner.md`
  (next to this skill) and follow it end to end. Do not inline its full text into chat.
- **Sources of truth (read-only):** `.qb/main-planning.md`,
  `.qb/sub-planning-index.md`, and every `.qb/phase-*-plans/*.md` in the user's
  active workspace (cwd).
- **Only writable file:** `.qb/sub-planning-audit.md` in the user's workspace. Do not
  modify any plan file, the index, the master plan, source, config, tests, or scripts.
- **Language:** the audit report is written in English.
- **Reliability + validator.** Resolve the plugin root by walking up to the folder containing
  `.cursor-plugin/plugin.json`; read `references/workflow-quality.md` and follow it. The bundled
  validator is at `<plugin-root>/scripts/validate_planner_docs.py`.

## Goal contract (declare before starting)

- **Objective:** Produce `.qb/sub-planning-audit.md` using the exact 15-section structure
  from `third-planner.md`, with an overall status of `PASS`, `PASS_WITH_WARNINGS`, or `BLOCKED`.
- **Success evidence (all must hold):**
  - `main-planning.md` phase coverage was checked against generated folders/sub-plans.
  - `sub-planning-index.md` consistency was checked against the actual files.
  - Every detected phase folder was inspected and every sub-plan file inventoried.
  - Required section structure, naming, and ordering were checked.
  - Step 4 readiness was assessed and a prioritized fix list (`AUDIT-FIX-NN`, severity P0-P3) was produced.
  - `git status` was checked; only `sub-planning-audit.md` changed.
- **Scope bounds:** create/update only `.qb/sub-planning-audit.md`. Report problems; do
  not fix them. No secrets in the report. No commit, push, or PR.
- **Stop condition:** stop only when the full audit is complete, or on a Blocked condition below.

## Goal setup via Cursor define-goal (do this first)

Before auditing, register the goal contract above as a Cursor goal - automatically and in-session.
This is the primary mechanism, not an optional add-on, and it is hands-free: there is no "Follow
the Goal" button and no copy/paste handoff.

1. Follow the Cursor `define-goal` skill: call `get_goal`, and if there is no matching active goal,
   call `create_goal` with the Objective above, including its success evidence and scope bounds.
2. As phases are audited, update the goal's progress when `update_goal` is available.
3. Fallback: if `define-goal` / the goal tool (`create_goal`) is not available this session,
   proceed under the in-context goal contract above - behavior is identical.

## Pre-audit validation (run first)

Run the bundled validator and fold its output into the audit as concrete findings:
`python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step3 --strict`
(fallback: inventory with `find .qb -path "*/phase-*-plans/*.md" | sort` and check headings
manually). Treat validator errors (coverage gaps, naming/numbering issues, index mismatches,
structure problems, secrets) as audit findings and cite them in the relevant audit sections.

## Continuation loop (this is what prevents early exit)

1. Inventory all phase folders and sub-plan files (`find .qb -path "*/phase-*-plans/*.md" | sort`).
2. Audit each phase and each sub-plan against `main-planning.md` and the 13-section requirement -
   coverage, order, naming, index accuracy, section structure, content quality, scope drift,
   readiness realism, and security/governance.
3. After each phase, continue to the next. **Do not stop after auditing one phase.**
4. When all phases and sub-plans are inspected, assemble `sub-planning-audit.md` with all 15
   sections, the coverage table, the file inventory, the Step-4 readiness table, and the
   prioritized fix list.
5. In `## 13. Prioritized Fix List`, write each real finding as a **single-line header**
   `- AUDIT-FIX-NN | PX | <short title>` (the severity `PX` comes immediately after the id, separated
   by `|`, `:`, `—`, or `-`), followed by optional detail bullets (affected file, issue, fix, why).
   State zero-finding severities only on a plain count line (e.g. "P0: 0, P1: 0, P2: 5, P3: 3"); never
   write bare `P0`/`P1` tokens in prose. The validator counts exactly one severity per
   `AUDIT-FIX-NN | PX` finding header, so this format keeps the Step-4 gate accurate.
6. Re-run `python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step3 --strict`
   (post-write), then `--mode step4` to determine the Step-4 gate; record the gate result
   (PASS / blocked-by-P0/P1 / BLOCKED) in `## 12` and `## 14`. Confirm `git status` shows only
   `sub-planning-audit.md` changed.

## Blocked conditions (still write the report)

Following `third-planner.md`: if `main-planning.md` is missing, `sub-planning-index.md` is missing,
or no `phase-*-plans/*.md` files exist, still create `sub-planning-audit.md`, mark the status
`BLOCKED`, explain what is missing and the minimal next action, and stop.

## Output and handoff

Report: the audit status; number of main phases detected; number of sub-plan files inspected; the
P0/P1/P2/P3 finding counts; whether Step 4 can begin; the single most important fix; and
confirmation that only `sub-planning-audit.md` changed.

- **PASS** -> Step 4 (implementation) can begin; the orchestrator offers it, gated by `--mode step4`.
- **PASS_WITH_WARNINGS** -> if there are no P0/P1 findings, Step 4 may begin with the P2/P3 warnings
  kept visible; if any P0/P1 finding exists, hand the prioritized fix list back to `qb-planner`
  for targeted repairs, then re-invoke this skill to confirm.
- **BLOCKED** -> surface the blocker and minimal next action; do not proceed to Step 4.
