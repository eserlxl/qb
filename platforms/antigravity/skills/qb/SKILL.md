---
name: qb
description: Vibecoding-first Antigravity planning with assessment, ontology, ledger memory, helper-agent-aware QA, and gated handoff.
metadata:
  version: "0.21.0"
---

# QB

## Overview

Run the bundled planning workflow for a project repository. Keep Step 1 conversational and repo-aware, run Step 1.5 Assessment for existing projects, and hand off Step 2 and Step 3 as text-only Antigravity task prompts unless the user explicitly asks for a different flow. After Step 3, provide a gated Step 4 implementation handoff prompt only when the audit says implementation can begin.

The bundled prompts are:

- `references/first-planner.md` for Step 1 main planning.
- `references/assessment-planner.md` for Step 1.5 existing-project assessment.
- `references/second-planner.md` for Step 2 phase sub-planning.
- `references/third-planner.md` for Step 3 sub-plan QA and coverage audit.
- `references/handoffs/run-step2.md`, `references/handoffs/run-step3.md`, and `references/handoffs/run-step4.md` for the single-source Step 2/3/4 Antigravity task handoff prompts (each carries `contract_version` frontmatter). `references/fourth-planner.md` points to `run-step4.md` for the Step 4 implementation contract.

Planning behavior references:

- `references/vibecoding-principles.md` for adaptive, small-slice, validation-first planning.
- `references/task-delegation-playbook.md` for safe helper-agent/task delegation and role boundaries.
- `references/planning-ledger.md` for durable plan/implementation history via `.qb/planning-ledger.md`.
- `references/project-ontology.md` for durable project vocabulary, entities, workflows, boundaries, and invariants.
- `references/project-comprehension-methods.md` for the optional evidence-backed comprehension model (CQ questions, hypothesis confidence, Evidence Register, Domain-to-Code Trace Map, Architecture Reflexion) recorded in `.qb/project-comprehension.md` for non-trivial existing projects.
- `references/assessment-and-budget.md` for autonomy, Antigravity task, token/context, and budget assessment.
- `references/engineering-principles.md` for domain-appropriate CS, architecture, validation, and secure engineering methods.

Bundled support files:

- `scripts/validate_planner_docs.py` for read-only structural validation of `.qb/`.
- `references/repo-aware-intake.md` for evidence-backed Step 1 intake questions.
- `references/workflow-quality.md` for Antigravity task reliability, validation, token discipline, and handoff practices.

## Workflow Selection

1. If the user asks for normal planner startup, run Step 1.
2. If the user directly asks for Step 1.5 or Assessment, read `references/assessment-planner.md` and execute it.
3. If the user directly asks for Step 2, read `references/second-planner.md` and execute it.
4. If the user directly asks for Step 3, read `references/third-planner.md` and execute it.
5. If the user asks only for the Antigravity task prompt text, print the matching Step 2, Step 3, or gated Step 4 copy block without modifying files.
6. **Auto mode:** If the user specifies 'auto' (e.g. via the `/qb-plan auto` command), run Steps 1, 1.5, 2, and 3 non-interactively: auto-derive intake fields, auto-pass all gates, skip Step 4, validate at each step, and automatically export implementation-ready items to `.qb/plan.md`. No confirmation prompts may block this mode. Print `QB_PLAN_AUTO_OK:` on success or `QB_PLAN_AUTO_ERROR:` on failure.

This is a native Antigravity Agent Skill workflow. Do not use legacy package-manager or migration commands for this skill.

## Step 1 Intake

Read `references/repo-aware-intake.md` before asking questions.

Before asking `PROJECT_NAME`, do a bounded, read-only repository scan so the intake can suggest evidence-backed defaults. If `.qb/planning-ledger.md` or `.qb/project-ontology.md` exists, read it before asking intake questions and use it as supporting history, not as unquestioned truth. Then ask these four fields one at a time in the user's language, using plain text questions only:

1. `PROJECT_NAME`: project name, with an inferred default when possible.
2. `PROJECT_INTENT`: what the project is for and what it should become, with a repo-derived draft when possible.
3. `TARGET_END_STATE`: what done looks like from product, engineering, operations, security, and user-value perspectives, with a five-part draft when possible.
4. `KNOWN_CONSTRAINTS`: team size, infrastructure, budget, timeline, preferred stack, compliance boundaries, must-use tools, must-not-use tools, desired autonomy level, human review cadence, and any token/usage budget with detected constraints and unknowns when possible.

QB asks intake questions in the user's language when practical. Generated .qb artifacts are English by default unless the user explicitly requests another body language. Required document headings remain English for validator stability.

## Vibecoding, Memory, Ontology, and Helper-Agent Behavior

QB uses a vibecoding-first planning style: understand the repo, preserve a clear target, plan the next useful verified moves, and keep implementation slices small, reversible, and evidence-backed. Vibecoding does not relax safety, validation, secret, approval, or file-boundary rules.

Before long planning runs, read `references/vibecoding-principles.md`, `references/assessment-and-budget.md`, and `references/engineering-principles.md`. For existing projects, also read `references/planning-ledger.md` and `references/project-ontology.md`; if `.qb/planning-ledger.md` or `.qb/project-ontology.md` exists in the target repo, read them as evidence before replanning.

Use helper agents only when they reduce context pollution or improve evidence quality: large repo exploration, Step 1.5 Assessment, ontology mapping, multi-phase Step 2 drafting, Step 3 readiness/security audit, or Step 4 implementation/review separation. Read `references/task-delegation-playbook.md` before requesting helper agents. Parent QB owns final artifact writes; helper agents should gather evidence, draft options, or review unless the user explicitly asks otherwise.

Antigravity task handoffs must include the outcome, unchanged boundaries, validation checkpoints, stop gates, token/context risk, and whether helper agents are recommended.

After all four values are available:

1. Read `references/first-planner.md`.
2. Substitute the four collected values into the matching placeholders.
3. Follow the substituted Step 1 prompt exactly.
4. Create or update only `.qb/main-planning.md`, as required by the Step 1 prompt.
5. After completing Step 1, decide whether Step 1.5 Assessment applies.
6. Run Step 1.5 automatically only when the repository is an existing or partially built project: it is not empty and contains meaningful evidence such as README, manifests, source/service/package directories, tests, docs, configs, or CI.
7. Skip Step 1.5 for new or nearly empty projects; do not create `.qb/assessment.md` in that case.
8. After Step 1 and any Step 1.5 Assessment work, ask the user in plain text whether they have feedback for the main plan and assessment.
9. If feedback is provided, apply it under the same file boundary: update only `.qb/main-planning.md` for main plan feedback and only `.qb/assessment.md` for assessment feedback.

## Step 1.5 Assessment

Step 1.5 is for existing or partially built projects. It should not run for genuinely new or nearly empty repositories.

When Step 1.5 applies:

1. Read `references/assessment-planner.md`.
2. Read `.qb/main-planning.md`.
3. Inspect the repository with read-only commands.
4. Create or update `.qb/assessment.md`; when enough evidence exists, also create or update `.qb/project-ontology.md`.
5. Do not modify source files, `.qb/main-planning.md`, or any Step 2/3 files.
6. Treat `assessment.md`, `project-ontology.md`, and any existing `planning-ledger.md` as Step 2 feedback, not as replacements for the main plan.

## Step 2 Handoff

After Step 1 feedback is handled, ask whether the user wants to continue to Step 2. If yes, print the Copy Block from the single-source handoff `references/handoffs/run-step2.md` and tell the user to copy that text, open a new Antigravity task, and send it.

When executing Step 2 directly:

1. Read `references/second-planner.md`.
2. Read `references/workflow-quality.md`.
3. Read `.qb/assessment.md`, `.qb/project-ontology.md`, and `.qb/planning-ledger.md` when they exist; do not block Step 2 when they are absent.
4. Follow repository inspection, file-boundary, naming, all-file validation, and stopping rules exactly.
5. Run the bundled validator after generation when available. When manually validating from a QB repository checkout, use:
   `python3 skills/qb/scripts/validate_planner_docs.py --root . --mode step2 --strict`
   If no script path is accessible, perform equivalent all-file validation and report that fallback clearly.
6. Do not modify files outside `.qb/`.
7. After the Step 2 summary, print the Copy Block from `references/handoffs/run-step3.md`.

## Step 3 Handoff

After Step 2 is complete, ask whether the user wants to continue to Step 3. If yes, print the Copy Block from the single-source handoff `references/handoffs/run-step3.md` and tell the user to copy that text, open a new Antigravity task, and send it.

When executing Step 3 directly:

1. Read `references/third-planner.md`.
2. Read `references/workflow-quality.md`.
3. Run the bundled validator first when available and incorporate its findings into the audit. When manually validating from a QB repository checkout, use:
   `python3 skills/qb/scripts/validate_planner_docs.py --root . --mode step3 --strict`
   If no script path is accessible, perform equivalent all-file validation and report that fallback clearly.
4. Follow audit, file-boundary, validation, and stopping rules exactly.
5. Modify only `.qb/sub-planning-audit.md`.
6. After the Step 3 summary, print the Step 4 handoff prompt from `references/handoffs/run-step4.md` only if the audit permits implementation.

## Step 4 Handoff

Step 4 is not a QB planning step and must not be executed automatically by this skill.

When Step 3 completes:

1. Read `references/handoffs/run-step4.md` (the single-source Step 4 contract).
2. Run the bundled validator when available. When manually validating from a QB repository checkout, use:
   `python3 skills/qb/scripts/validate_planner_docs.py --root . --mode step4`
   If no script path is accessible, perform equivalent all-file validation and report that fallback clearly.
3. If validation passes, print the Copy Block from `references/handoffs/run-step4.md` and remind the user to watch token use.
4. If validation fails because the audit is `BLOCKED` or contains P0/P1 findings, do not print the Step 4 prompt; print the minimal repair or unblock prompt instead.
5. If validation passes with non-blocking warnings, print the Step 4 prompt and state that the implementation run must keep P2/P3 warnings visible.
6. The Step 4 prompt should execute the READY/READY_WITH_WARNINGS queue continuously in small verified slices. It should not stop after the first successful slice unless a stop gate is hit.

## Quality and Validation

- Prefer `scripts/validate_planner_docs.py` over ad hoc validation scripts.
- Use `--mode step1`, `--mode assessment`, `--mode step2`, `--mode step3`, or `--mode step4` for the active workflow step.
- Use `--strict` in Antigravity task so generic or repeated section warnings become failures.
- Do not report section counts from memory; report counts only after reading the active prompt or running validation.
- For untracked `.qb/`, use `find .qb -maxdepth 4 -type f | sort`, `git status --short -- .qb`, and `git diff -- .qb` together.
- Keep long Antigravity task stdout concise. Put detailed evidence in the generated Markdown artifacts.
- Track planning and implementation continuity through `.qb/planning-ledger.md` when available; Step 4 should append concise implementation summaries there.

## Safety Rules

- Treat the current working directory as the project being planned.
- Inspect the repository before writing any planning file, using the safe read-only commands required by the active planner prompt.
- Do not implement product features, refactor source code, install dependencies, commit, push, deploy, or open pull requests.
- Do not write secrets, tokens, credentials, private keys, or local sensitive environment values into planning files.
- Preserve the required fixed filenames exactly: `main-planning.md`, `sub-planning-index.md`, and `sub-planning-audit.md`.
- Preserve `.qb/assessment.md` as the Step 1.5 assessment filename.
- If a required source file is missing, follow the blocker behavior in the active planner prompt instead of inventing speculative output.

## Completion Reporting

For each executed step, report concisely:

- which planner step ran;
- which files were created or updated;
- whether the step succeeded or was blocked;
- the highest-priority next action;
- any uncertainty or blocker discovered.
