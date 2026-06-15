---
name: qb-autopsy
description: Goal-backed Step 1.5 of the QB planning workflow - an existing-project autopsy. Use after Step 1 (or directly) to inspect an existing/partially built repository and write .qb/autopsy.md, a 13-section technical feedback report that enriches Step 2 sub-plans. Runs automatically for existing/non-empty repositories and is skipped for empty or nearly empty ones. Launched automatically as a Cursor goal via the define-goal skill; only creates/updates .qb/autopsy.md.
---

# QB Autopsy (Step 1.5, goal-backed)

Inspect an existing or partially built repository in detail and write a single autopsy report
that Step 2 uses as supporting feedback. This step never changes source code, never changes
`main-planning.md`, and only creates/updates `.qb/autopsy.md`. Read the full Step-1.5
spec in `autopsy-planner.md` (next to this skill) and follow it end to end.

## Execution model

- **In-session, goal-backed.** Read the bundled `autopsy-planner.md` spec and follow it. Register the goal via the Cursor `define-goal` skill (`get_goal` then `create_goal`); if the goal tool is unavailable, proceed under the in-context goal contract - behavior is identical.
- **Reliability + validator.** Resolve the plugin root by walking up to the folder containing `.cursor-plugin/plugin.json`; read `references/workflow-quality.md` and follow it. The bundled validator is at `<plugin-root>/scripts/validate_planner_docs.py`.
- **Sources of truth (read-only):** `.qb/main-planning.md` (primary) plus repository evidence (README, manifests, CI, tests, docs, service/package folders, configs).
- **Only writable file:** `.qb/autopsy.md` in the user's active workspace (cwd). Never touch source, `main-planning.md`, or any Step 2/3 file.
- **Language:** the autopsy report is written in English.

## When to run vs skip

- **Run** for existing or partially built projects: the repository is not empty and contains meaningful evidence such as README, manifests, source/service/package directories, tests, docs, configs, or CI.
- **Skip** for new or nearly empty repositories: do not create `.qb/autopsy.md`; report that Step 1.5 was skipped because there is not enough repository evidence, then stop. Step 2 continues without it.

## Goal contract (declare before starting)

- **Objective:** For an existing project, produce `.qb/autopsy.md` using the exact 14-heading structure (`# Project Autopsy` + 13 numbered sections) from `autopsy-planner.md`, grounded in repository evidence.
- **Success evidence:** `autopsy.md` exists with all 14 headings in order, in English, no secrets; `git status` shows only `.qb/autopsy.md` changed; OR Step 1.5 was correctly skipped for an empty repo (no `autopsy.md` created).
- **Scope bounds:** only create/update `.qb/autopsy.md`. No source/config/test edits. No secrets, tokens, or credentials. No commit, push, or PR.
- **Stop condition:** stop on Success, on a correct skip, or on a blocking read error.

## Procedure

1. Read `main-planning.md` and inspect the repository with the read-only commands listed in `autopsy-planner.md`.
2. If evidence is too thin (empty/new repo), skip and report; do not write `autopsy.md`.
3. Otherwise build `autopsy.md` incrementally (create the file, then add sections) with all 14 headings, grounded in evidence; redact any secret-like value to `<redacted>`.
4. Validate: run `python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step2 --strict` and confirm `autopsy_exists=true` with no `autopsy.md` heading errors (fallback: manually confirm the 14 headings in order). Confirm only `.qb/autopsy.md` changed.

## Output and handoff

Report: whether Step 1.5 succeeded, was skipped, or was blocked; whether `autopsy.md` was created/updated; the highest-priority `AUTOPSY-P0/P1` signals; how Step 2 should use the report; and confirmation that only `.qb/autopsy.md` changed. Control returns to `qb-planner` (Gate 1 feedback covers both `main-planning.md` and `autopsy.md`); Step 2 (`qb-subplanner`) reads `autopsy.md` as supporting feedback.
