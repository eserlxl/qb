---
name: qb-subplanner
description: Goal-backed Step 2 of the QB planning workflow. Use to decompose every main phase in .qb/main-planning.md into detailed sub-plans under .qb/phase-<n>-plans/ plus sub-planning-index.md. Launched automatically as a Cursor goal via the define-goal skill and runs until ALL phases are covered - it does not stop after one phase. Invoke from qb-planner Gate 1, or directly to (re)generate sub-plans. Only changes files under .qb/.
metadata:
  version: "0.16.0"
---

# QB Sub-Planner (Step 2, goal-backed)

Decompose the master plan into detailed, per-phase sub-plans. This is a long autonomous task,
so it is run as a **goal**: you commit to an explicit completion contract up front and keep
working until that contract is satisfied or a blocking condition is hit.

## Execution model

- **In-session, zero-setup.** Read the full Step-2 specification from `second-planner.md`
  (next to this skill) and follow it end to end. Do not inline its full text into chat.
- **Source of truth:** `.qb/main-planning.md` in the user's active workspace (cwd).
- **Optional supporting source:** if `.qb/assessment.md` exists (from Step 1.5), read it fully
  first and weave its findings (technical debt, placeholder/stub, broken integrations, test/security/
  readiness gaps) into sub-plan evidence, work breakdowns, acceptance criteria, and risk sections. It is
  **not** a replacement for `main-planning.md`; do not block Step 2 when it is absent.
- **Output location:** the user's workspace `.qb/`, never this plugin's directory.
- **Language:** all generated planning documents are written in English.
- **Reliability + validator.** Resolve the plugin root by walking up to the folder containing
  `.cursor-plugin/plugin.json`; read `references/workflow-quality.md` and follow it (build large
  docs incrementally, all-file validation, concise output, untracked-.qb git handling,
  secret discipline). The bundled validator is at `<plugin-root>/scripts/validate_planner_docs.py`.

## Goal contract (declare before starting)

State this contract to the user in one short block, then pursue it:

- **Objective:** For every main phase in `.qb/main-planning.md`, create
  `.qb/phase-<n>-plans/` with one or more `phase-<n>.<m>-<ascii-kebab-slug>.md` sub-plans
  that each use the 13 required sections from `second-planner.md`, and create/update
  `.qb/sub-planning-index.md`.
- **Success evidence (all must hold):**
  - `.qb/sub-planning-index.md` exists and references **every** sub-plan by its full
    relative path (`.qb/phase-<n>-plans/phase-<n>.<m>-*.md`), never slug-only - the validator
    rejects slug-only references.
  - Every phase detected in `main-planning.md` has a matching `phase-<n>-plans/` folder.
  - Every phase folder has at least one conforming `phase-<n>.<m>-*.md` sub-plan.
  - Every sub-plan contains the 13 required top-level sections, in order, in English.
  - `git status --short` / `git diff` show changes only under `.qb/` (or, when the
    workspace is not a git repo, a manual review confirms only `.qb/` was touched).
- **Scope bounds:** only create/update files under `.qb/`. No source, config, test, or
  script edits. No secrets, tokens, or credentials in any file. No commit, push, or PR.
- **Stop condition:** stop only on Success (all evidence holds) or on a Blocked condition below.

## Goal setup via Cursor define-goal (do this first)

Before generating any sub-plans, register the goal contract above as a Cursor goal - automatically
and in-session. This is the primary mechanism, not an optional add-on, and it is hands-free: there
is no "Follow the Goal" button and no copy/paste handoff.

1. Follow the Cursor `define-goal` skill: call `get_goal`, and if there is no matching active goal,
   call `create_goal` with the Objective above, including its success evidence and scope bounds.
2. As each phase folder is completed, update the goal's progress when `update_goal` is available.
3. Fallback: if `define-goal` / the goal tool (`create_goal`) is not available this session,
   proceed under the in-context goal contract above - behavior is identical.

## Continuation loop (this is what prevents early exit)

1. Read `main-planning.md` fully and extract the ordered list of main phases (preserve their order). If
   `.qb/assessment.md` exists, read it fully too and treat it as supporting feedback.
2. For each phase, in order, create its `phase-<n>-plans/` folder and its sub-plan files following
   the `second-planner.md` sizing rules (prefer 3-7 sub-phases; small phases 1-3; large 6-9; avoid
   over-fragmentation) and the exact 13-section structure.
3. After finishing a phase, re-check the success-evidence checklist and **continue to the next
   uncovered phase. Do not stop after one phase.**
4. Build large sub-plans incrementally (create the file, then add sections) rather than one
   oversized write. When every phase is covered, create/update `sub-planning-index.md` with
   **full relative-path** references to every sub-plan.
5. Validate ALL generated files (not a sample): run
   `python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step2 --strict`
   (fallback: `find .qb -maxdepth 3 -type f | sort`, read every sub-plan's headings,
   confirm the 13 sections in order, English, full-path index references, no duplicate/gap
   numbering, and that only `.qb/` changed). Fix every reported error before handing off.

## Blocked conditions (stop early, but leave a record)

Following `second-planner.md`: if `.qb/main-planning.md` is missing, or it has no clear
phase roadmap, or repository read errors prevent safe planning, do NOT invent speculative
sub-plans. Instead create `.qb/Step2-Blocked.md` explaining the blocker, the exact
missing input, and the minimal next action, then stop.

## Output and handoff

Report: whether Step 2 succeeded or was blocked, how many main phases were detected, how many
sub-plan files were created/updated, which folders were created, the index file path, the
recommended first sub-plan to detail next, and confirmation that only `.qb/` changed.
When invoked from the orchestrator, control returns to `qb-planner` Gate 2 (the audit
approval). The natural next step is the `qb-auditor` skill.
