---
name: qb-assess
description: Subagent-backed Step 1.5 of the QB planning workflow - an existing-project assessment. Use after Step 1 (or directly) to inspect an existing/partially built repository and write .qb/assessment.md, a 13-section technical feedback report that enriches Step 2 sub-plans. Runs automatically for existing/non-empty repositories and is skipped for empty or nearly empty ones. This skill is the spec that the qb-assess subagent follows; only creates/updates .qb/assessment.md.
metadata:
  version: "0.18.0"
---

# QB Assessment (Step 1.5, subagent-backed)

Inspect an existing or partially built repository in detail and write a single assessment report
that Step 2 uses as supporting feedback. This step never changes source code, never changes
`main-planning.md`, and only creates/updates `.qb/assessment.md`. Read the full Step-1.5
spec in `assessment-planner.md` (next to this skill) and follow it end to end.

## Execution model

- **In-session, subagent-backed.** Read the bundled `assessment-planner.md` spec and follow it under the goal contract below. The `qb-planner` orchestrator delegates this step to the `qb-assess` subagent via the Task tool, passing the goal contract as the task brief plus the absolute path to `assessment-planner.md`. Fallback: if subagents/Task are unavailable this session, run this skill in-session under the same in-context goal contract - behavior is identical.
- **Reliability + validator.** Resolve the plugin root by walking up to the folder containing `.claude-plugin/plugin.json`; read `references/workflow-quality.md` and follow it. The bundled validator is at `<plugin-root>/scripts/validate_planner_docs.py`.
- **Sources of truth (read-only):** `.qb/main-planning.md` (primary) plus repository evidence (README, manifests, CI, tests, docs, service/package folders, configs).
- **Only writable file:** `.qb/assessment.md` in the user's active workspace (cwd). Never touch source, `main-planning.md`, or any Step 2/3 file.
- **Language:** the assessment report is written in English.

## When to run vs skip

- **Run** for existing or partially built projects: the repository is not empty and contains meaningful evidence such as README, manifests, source/service/package directories, tests, docs, configs, or CI.
- **Skip** for new or nearly empty repositories: do not create `.qb/assessment.md`; report that Step 1.5 was skipped because there is not enough repository evidence, then stop. Step 2 continues without it.

## Goal contract (declare before starting)

- **Objective:** For an existing project, produce `.qb/assessment.md` using the exact 14-heading structure (`# Project Assessment` + 13 numbered sections) from `assessment-planner.md`, grounded in repository evidence.
- **Success evidence:** `assessment.md` exists with all 14 headings in order, in English, no secrets; `git status` shows only `.qb/assessment.md` changed; OR Step 1.5 was correctly skipped for an empty repo (no `assessment.md` created).
- **Scope bounds:** only create/update `.qb/assessment.md`. No source/config/test edits. No secrets, tokens, or credentials. No commit, push, or PR.
- **Stop condition:** stop on Success, on a correct skip, or on a blocking read error.

## Procedure

1. Read `main-planning.md` and inspect the repository with the read-only commands listed in `assessment-planner.md`.
2. If evidence is too thin (empty/new repo), skip and report; do not write `assessment.md`.
3. Otherwise build `assessment.md` incrementally (create the file, then add sections) with all 14 headings, grounded in evidence; redact any secret-like value to `<redacted>`.
4. Validate: run `python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step2 --strict` and confirm `assessment_exists=true` with no `assessment.md` heading errors (fallback: manually confirm the 14 headings in order). Confirm only `.qb/assessment.md` changed.

## Output and handoff

Report: whether Step 1.5 succeeded, was skipped, or was blocked; whether `assessment.md` was created/updated; the highest-priority `ASSESS-P0/P1` signals; how Step 2 should use the report; and confirmation that only `.qb/assessment.md` changed. Control returns to `qb-planner` (Gate 1 feedback covers both `main-planning.md` and `assessment.md`); Step 2 (`qb-subplanner`) reads `assessment.md` as supporting feedback.
