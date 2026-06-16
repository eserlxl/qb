---
name: qb
description: Repo-aware Codex planning with assessment, phase sub-plans, QA audit, and gated handoff.
metadata:
  version: "0.14.0"
---

# QB

## Overview

Run the bundled planning workflow for a project repository. Keep Step 1 conversational and repo-aware, run Step 1.5 Assessment for existing projects, and hand off Step 2 and Step 3 as text-only Goal mode prompts unless the user explicitly asks for a different flow. After Step 3, automatically run the Step 3.5 export to produce `.qb/plan.md` in planwright's plan format, and provide a gated Step 4 implementation handoff prompt only when the audit says implementation can begin.

The bundled prompts are:

- `references/first-planner.md` for Step 1 main planning.
- `references/assessment-planner.md` for Step 1.5 existing-project assessment.
- `references/second-planner.md` for Step 2 phase sub-planning.
- `references/third-planner.md` for Step 3 sub-plan QA and coverage audit.
- `references/fourth-planner.md` for the Step 4 implementation Goal handoff prompt template.
- `references/export-planner.md` for the Step 3.5 planwright-format plan export.

Bundled support files:

- `scripts/validate_planner_docs.py` for read-only structural validation of `.qb/`.
- `scripts/validate_planwright_plan.py` for read-only structural validation of the exported `.qb/plan.md`.
- `references/repo-aware-intake.md` for evidence-backed Step 1 intake questions.
- `references/workflow-quality.md` for Goal mode reliability, validation, token discipline, and handoff practices.

## Workflow Selection

1. If the user asks for normal planner startup, run Step 1.
2. If the user directly asks for Step 1.5 or Assessment, read `references/assessment-planner.md` and execute it.
3. If the user directly asks for Step 2, read `references/second-planner.md` and execute it.
4. If the user directly asks for Step 3, read `references/third-planner.md` and execute it.
5. If the user asks only for the Goal mode prompt text, print the matching Step 2, Step 3, or gated Step 4 copy block without modifying files.
6. If the user asks to audit and harden the repository (rather than plan it), launch the QB engine loop described under "Audit and Harden" below instead of the planner.
7. If the invocation includes the `auto` flag (for example "Use $qb auto"), run the planning workflow non-interactively per **Auto Mode (non-interactive)** below instead of the conversational flow.

Do not run `migrate-to-codex` for this workflow. This is a native Codex skill workflow, not a Claude migration.

## Auto Mode (non-interactive)

When the user invokes `$qb` with the `auto` flag (for example "Use $qb auto"), run the planning
workflow **non-interactively** so an external caller (for example planwright) can detect a clean
success or failure from the output. Auto mode overrides the conversational intake and the gates,
and disables the Step 4 implementation handoff.

1. **Never prompt.** Do not ask the four intake questions and do not pause for approval between
   steps. Emit only progress and the final result line, in English.
2. **Intake is auto-derive only - fail closed.** Run the repo-aware Pre-Intake Scan from
   `references/repo-aware-intake.md` and derive all four fields (`PROJECT_NAME`, `PROJECT_INTENT`,
   `TARGET_END_STATE`, `KNOWN_CONSTRAINTS`) from repository evidence. If any field cannot be
   derived with sufficient evidence, do not fall back to a question - print and stop, creating no
   `.qb/` artifacts:
   `QB_PLAN_AUTO_ERROR: missing required field(s): <comma-separated names> (insufficient repo evidence)`
3. **Run straight through - planning-only, verify every planning step, and be honest about independence.** Execute
   Step 1 -> 1.5 -> 2 -> 3, then the Step 3.5 export, treating the gates as approved but not
   bypassing validation. Step 1 must pass `validate_planner_docs.py --mode step1 --strict`
   before Step 2 starts; Step 2 must pass `--mode step2 --strict` before Step 3 starts; Step
   3 must pass `--mode step4` before Step 3.5 exports planwright items. Auto mode is the
   external-consumer path (planwright and other callers). Codex runs the whole workflow as **one
   in-session skill** — the audit (Step 3) is **not** an independent, subagent-isolated actor, so it
   grades the same context that produced the plan and can rubber-stamp it. So **emit, before the
   result line, the disclosure `QB_PLAN_AUTO_WARN: in-session audit — not subagent-isolated on this
   host`** so the consumer can downgrade its trust. Record a `BLOCKED` or P0/P1 audit status in the
   summary but still produce the export. Auto mode writes only under `.qb/`: do not emit or run the
   Step 4 implementation handoff, and never modify source code, commit, push, or open PRs. No
   approval, confirmation, human-review marker, or implementation-gate question may block
   `.qb/plan.md` generation once Step 2 has produced sub-plans, but failed validation must
   fail closed with `QB_PLAN_AUTO_ERROR`.
4. **Deterministic result line.** Print exactly one final line. Success (only after `.qb/plan.md`
   passed `scripts/validate_planwright_plan.py`):
   `QB_PLAN_AUTO_OK: .qb/plan.md generated (<item-count> items); audit=<PASS|PASS_WITH_WARNINGS|BLOCKED>`
   Otherwise: `QB_PLAN_AUTO_ERROR: <reason>`.

## Audit and Harden (engine loop)

QB also ships an autonomous audit -> harden -> report engine, separate from the planning workflow above. When the user asks to audit or harden the repository, run the engine rather than the planner.

Run brief (state before starting):

- Target repository: the current working directory.
- Autonomy level: `A0` (report-only) by default; raise to `A1` (propose in throwaway isolation), `A2` (apply only verified fixes), or `A3` (prepare a reviewable changeset) only on explicit request. Never escalate silently.
- Policy: an optional policy JSON; absent or unparseable means the conservative default (A0, deny-all writes, no commit/push/PR).
- Budgets: max findings / fixes / iterations / wall-time / tokens, taken from the policy.

Launch it through the bundled engine entry point:

```text
Use $qb. Run the audit and harden engine over this repository.
python3 scripts/qb_headless.py --root . --out QB-Audit
```

The exit code is the contract: `0` clean, `1` findings present, `2` policy/budget boundary, `3` internal error. The engine writes graded findings, per-fix evidence, and an append-only log to the fixed-name `QB-Audit/` store, plus `report.json`, `report.sarif`, and a human summary. At A0 nothing is written to the working tree; at A1+ each fix runs in git isolation, is kept only when its verification command passes, and is otherwise auto-reverted. Never commit, push, open a PR, or deploy; A3 deliver is explicit opt-in only; never write secrets into any output.

## Step 1 Intake

Read `references/repo-aware-intake.md` before asking questions.

Before asking `PROJECT_NAME`, do a bounded, read-only repository scan so the intake can suggest evidence-backed defaults. Then follow the **Well-Structured Fast Path** in `references/repo-aware-intake.md`: on a well-structured repo, auto-derive these four fields and present a single consolidated confirmation; otherwise (or for any weak-evidence field) ask that field per turn in the user's language, using plain text questions only:

1. `PROJECT_NAME`: project name, with an inferred default when possible.
2. `PROJECT_INTENT`: what the project is for and what it should become, with a repo-derived draft when possible.
3. `TARGET_END_STATE`: what done looks like from product, engineering, operations, security, and user-value perspectives, with a five-part draft when possible.
4. `KNOWN_CONSTRAINTS`: team size, infrastructure, budget, timeline, preferred stack, compliance boundaries, must-use tools, and must-not-use tools, with detected constraints and unknowns when possible.

QB asks intake questions in the user's language when practical. Generated .qb artifacts are English by default unless the user explicitly requests another body language. Required document headings remain English for validator stability.

After all four values are available:

1. Read `references/first-planner.md`.
2. Substitute the four collected values into the matching placeholders.
3. Follow the substituted Step 1 prompt exactly.
4. Before creating any `.qb/` artifact, ensure `.qb/` is git-ignored: inside a git working tree, if `git check-ignore -q .qb/` fails, append a `.qb/` line to the workspace `.gitignore` (creating it if absent) without touching the user's other entries. Skip outside a git repo. See `references/workflow-quality.md` ("Ignore the `.qb/` Planning Directory") for the exact, idempotent commands, and note the one-line change in your completion report.
5. Create or update only `.qb/main-planning.md`, as required by the Step 1 prompt.
6. After completing Step 1, decide whether Step 1.5 Assessment applies.
7. Run Step 1.5 automatically only when the repository is an existing or partially built project: it is not empty and contains meaningful evidence such as README, manifests, source/service/package directories, tests, docs, configs, or CI.
8. Skip Step 1.5 for new or nearly empty projects; do not create `.qb/assessment.md` in that case.
9. After Step 1 and any Step 1.5 Assessment work, ask the user in plain text whether they have feedback for the main plan and assessment.
10. If feedback is provided, apply it under the same file boundary: update only `.qb/main-planning.md` for main plan feedback and only `.qb/assessment.md` for assessment feedback.

## Step 1.5 Assessment

Step 1.5 is for existing or partially built projects. It should not run for genuinely new or nearly empty repositories.

When Step 1.5 applies:

1. Read `references/assessment-planner.md`.
2. Read `.qb/main-planning.md`.
3. Inspect the repository with read-only commands.
4. Create or update only `.qb/assessment.md`.
5. Do not modify source files, `.qb/main-planning.md`, or any Step 2/3 files.
6. Treat `assessment.md` as Step 2 feedback, not as a replacement for the main plan.

## Step 2 Handoff

After Step 1 feedback is handled, ask whether the user wants to continue to Step 2. If yes, tell the user to copy the following text, open Goal mode, and send it:

```text
Use $qb. Run Step 2 according to references/second-planner.md.

Read all main phases in .qb/main-planning.md. If .qb/assessment.md exists, read it fully as a supporting feedback source and account for it in the sub-phase plans. For each phase, create phase-<n>-plans folders and detailed phase-<n>.<m>-*.md sub-plan files under .qb. Do not stop until all phases are covered. Modify only .qb.
```

When executing Step 2 directly:

1. Read `references/second-planner.md`.
2. Read `references/workflow-quality.md`.
3. Read `.qb/assessment.md` when it exists; do not block Step 2 when it is absent.
4. Follow repository inspection, file-boundary, naming, all-file validation, and stopping rules exactly.
5. Run the bundled validator after generation when available. When manually validating from a QB repository checkout, use:
   `python3 plugins/qb/skills/qb/scripts/validate_planner_docs.py --root . --mode step2 --strict`
   If no script path is accessible, perform equivalent all-file validation and report that fallback clearly.
6. Do not modify files outside `.qb/`.
7. After the Step 2 summary, print the Step 3 Goal mode handoff block from this skill.

## Step 3 Handoff

After Step 2 is complete, ask whether the user wants to continue to Step 3. If yes, tell the user to copy the following text, open Goal mode, and send it:

```text
Use $qb. Run Step 3 according to references/third-planner.md.

Audit .qb/main-planning.md, .qb/sub-planning-index.md, and .qb/phase-*-plans/*.md. Analyze main-phase coverage, file naming, sequencing, required section structure, index consistency, content quality, scope drift, readiness realism, security/governance, and Step 4 readiness. Do not fix any plan files; produce only .qb/sub-planning-audit.md. Do not stop until all phases and sub-plans have been reviewed.
```

When executing Step 3 directly:

1. Read `references/third-planner.md`.
2. Read `references/workflow-quality.md`.
3. Run the bundled validator first when available and incorporate its findings into the audit. When manually validating from a QB repository checkout, use:
   `python3 plugins/qb/skills/qb/scripts/validate_planner_docs.py --root . --mode step3 --strict`
   If no script path is accessible, perform equivalent all-file validation and report that fallback clearly.
4. Follow audit, file-boundary, validation, and stopping rules exactly.
5. Modify only `.qb/sub-planning-audit.md`.
6. After the Step 3 summary, print the Step 4 handoff prompt from `references/fourth-planner.md` only if the audit permits implementation.

## Step 4 Handoff

Step 4 is not a QB planning step and must not be executed automatically by this skill.

When Step 3 completes:

1. Read `references/fourth-planner.md`.
2. Run the bundled validator when available. When manually validating from a QB repository checkout, use:
   `python3 plugins/qb/skills/qb/scripts/validate_planner_docs.py --root . --mode step4`
   If no script path is accessible, perform equivalent all-file validation and report that fallback clearly.
3. If validation passes, print the Step 4 Goal mode copy block and remind the user to watch token use.
4. If validation fails because the audit is `BLOCKED` or contains P0/P1 findings, do not print the Step 4 prompt; print the minimal repair or unblock prompt instead.
5. If validation passes with non-blocking warnings, print the Step 4 prompt and state that the implementation run must keep P2/P3 warnings visible.
6. The Step 4 prompt should execute the READY/READY_WITH_WARNINGS queue continuously in small verified slices. It should not stop after the first successful slice unless a stop gate is hit.

## Step 3.5 Export to planwright

Step 3.5 is an automatic, read-only export that projects the verified `.qb/` sub-plans into a single flat checkbox plan, `.qb/plan.md`, in the exact item format an external planwright executor consumes. Unlike Step 4 it never changes source code, so it runs automatically once Step 3 completes and the Step 4-readiness validator passes (whenever Step 2 produced sub-plans), before the optional gated Step 4 implement — no gate, no copy/paste prompt.

When the export runs:

1. Read `references/export-planner.md`.
2. Run the validation barrier (`validate_planner_docs.py --mode step1 --strict`,
   `--mode step2 --strict`, and `--mode step4`) before item generation.
3. Read every `.qb/phase-*-plans/phase-<n>.<m>-*.md` and emit one planwright item per verified,
   implementation-ready `## 7. Planned Work Breakdown` entry, across all phases, into `.qb/plan.md`
   in the required 8-field item format. Skip planning-only entries and any entry whose editable
   surfaces would be `.qb/`. Modify only `.qb/plan.md`.
4. Skip only when there are no sub-plans (no `.qb/phase-*-plans/`) or when the validation barrier
   blocks export; then say there was nothing executable to export.
5. Run the bundled validator when available:
   `python3 plugins/qb/skills/qb/scripts/validate_planwright_plan.py --root . --strict`
   If no script path is accessible, perform the equivalent manual checks and report that fallback clearly. Fix every flagged item and re-run until it passes.
6. Tell the user the hand-off: to run the plan with planwright, copy it into place and execute, e.g. `cp .qb/plan.md .planwright/plan.md` then run planwright `execute` (or `cycle <N>`). QB does not write to `.planwright/` or invoke planwright itself.

## Quality and Validation

- Prefer `scripts/validate_planner_docs.py` over ad hoc validation scripts.
- Use `scripts/validate_planwright_plan.py --root . --strict` to validate the Step 3.5 export (`.qb/plan.md`).
- Use `--mode step1`, `--mode step2`, `--mode step3`, or `--mode step4` for the active workflow step.
- Use `--strict` in Goal mode so generic or repeated section warnings become failures.
- Do not report section counts from memory; report counts only after reading the active prompt or running validation.
- For untracked `.qb/`, use `find .qb -maxdepth 4 -type f | sort`, `git status --short -- .qb`, and `git diff -- .qb` together.
- Keep long Goal mode stdout concise. Put detailed evidence in the generated Markdown artifacts.

## Safety Rules

- Treat the current working directory as the project being planned.
- Inspect the repository before writing any planning file, using the safe read-only commands required by the active planner prompt.
- Do not implement product features, refactor source code, install dependencies, commit, push, deploy, or open pull requests. The only write permitted outside `.qb/` is the Step 1 `.gitignore` guard, which may append a single `.qb/` line so planning artifacts stay uncommitted.
- Do not write secrets, tokens, credentials, private keys, or local sensitive environment values into planning files.
- Preserve the exact required filenames: `main-planning.md`, `sub-planning-index.md`, and `sub-planning-audit.md`.
- Preserve `.qb/assessment.md` as the Step 1.5 assessment filename, and `.qb/plan.md` as the Step 3.5 planwright-format export filename.
- If a required source file is missing, follow the blocker behavior in the active planner prompt instead of inventing speculative output.

## Completion Reporting

For each executed step, report concisely:

- which planner step ran;
- which files were created or updated;
- whether the step succeeded or was blocked;
- the highest-priority next action;
- any uncertainty or blocker discovered.
