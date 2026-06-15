# Usage

QB runs a repo-aware planning workflow with an optional Step 1.5 Assessment for existing projects.

## Step 1: Main Plan

Open the project repository you want Codex to analyze and ask:

```text
Use $qb to create a main plan for this project.
```

QB first performs a bounded read-only scan of the current repository. It may inspect files such as `README.md`, `AGENTS.md`, manifests, CI workflows, docs indexes, deployment files, tests, and top-level service directories.

Then, unless the repo is well-structured (in which case it auto-derives the four fields and asks a single consolidated confirmation), it asks for each intake field in turn:

- `PROJECT_NAME`: the project name.
- `PROJECT_INTENT`: what the project is for and what it should become.
- `TARGET_END_STATE`: what done looks like across product, engineering, operations, security, and user value.
- `KNOWN_CONSTRAINTS`: team, infrastructure, budget, timeline, stack, compliance, must-use tools, and must-not-use tools.

QB asks intake questions in the user's language when practical. Generated .qb artifacts are English by default unless the user explicitly requests another body language. Required document headings remain English for validator stability.

For existing repositories, the questions should include repo-derived defaults or draft summaries. For example, QB may say that the README and package manifests suggest a specific project name, then ask whether to use that name or a different official name. For empty or minimal repositories, QB should clearly say repository evidence is limited and ask the concise generic version of each question.

After the answers are collected, QB loads `First-Planner.md`, substitutes the values, inspects the repository, and creates or updates:

```text
.qb/main-planning.md
```

Step 1 is allowed to modify only that file.

## Step 1.5: Existing Project Assessment

When the target repository is an existing or partially built project, QB runs `Assessment-Planner.md` after Step 1.

Expected output:

```text
.qb/assessment.md
```

The Assessment report analyzes project sections, feature inventory, placeholders/stubs/skeletons, technical debt, missing or broken integrations, test and CI gaps, security/governance issues, operational readiness, and alignment with `.qb/main-planning.md`.

Step 1.5 is skipped for empty or nearly empty repositories. In that case, `assessment.md` is not required and Step 2 should continue without it.

## Step 2: Phase Sub-Plans

After Step 1, QB prints a text block for Goal mode. Copy it, open Goal mode, and send it.

The prompt is:

```text
Use $qb. Run Step 2 according to references/Second-Planner.md.

Read all main phases in .qb/main-planning.md. If .qb/assessment.md exists, read it fully as a supporting feedback source and account for it in the sub-phase plans. For each phase, create phase-<n>-plans folders and detailed phase-<n>.<m>-*.md sub-plan files under .qb. Do not stop until all phases are covered. Modify only .qb.
```

Expected outputs:

```text
.qb/sub-planning-index.md
.qb/phase-<n>-plans/phase-<n>.<m>-*.md
```

Step 2 is allowed to modify only files under `.qb/`.

`.qb/main-planning.md` remains the primary source of truth. `.qb/assessment.md`, when present, is supporting feedback that should influence sub-plan evidence, work breakdowns, acceptance criteria, and risk sections.

At the end of Step 2, QB should run the bundled validator or an equivalent all-file validation, summarize the result, and print the Step 3 Goal mode handoff block. Do not rely on sampled reads alone for Step 2 structure checks.

When manually validating from a QB repository checkout, use:

```bash
python3 plugins/qb/skills/qb/scripts/validate_planner_docs.py --root /path/to/project --mode step2 --strict
```

When running through an installed plugin, QB should use the bundled validator path exposed by the active skill. If that path is unavailable, it should perform equivalent all-file validation and state that validator execution was unavailable.

## Step 3: Sub-Plan QA Audit

After Step 2, QB prints another text block for Goal mode. Copy it, open Goal mode, and send it.

The prompt is:

```text
Use $qb. Run Step 3 according to references/Third-Planner.md.

Audit .qb/main-planning.md, .qb/sub-planning-index.md, and .qb/phase-*-plans/*.md. Analyze main-phase coverage, file naming, sequencing, required section structure, index consistency, content quality, scope drift, readiness realism, security/governance, and Step 4 readiness. Do not fix any plan files; produce only .qb/sub-planning-audit.md. Do not stop until all phases and sub-plans have been reviewed.
```

Expected output:

```text
.qb/sub-planning-audit.md
```

Step 3 is an audit step. It reports problems but does not fix the sub-plans.

Step 3 should run the bundled validator first and incorporate its findings into `.qb/sub-planning-audit.md`. When manually validating from a QB repository checkout, use:

```bash
python3 plugins/qb/skills/qb/scripts/validate_planner_docs.py --root /path/to/project --mode step3 --strict
```

When running through an installed plugin, QB should use the bundled validator path exposed by the active skill. If that path is unavailable, it should perform equivalent all-file validation and state that validator execution was unavailable.

If the validator exits nonzero because it found structural issues, Step 3 should still write the audit unless required source files are missing.

## Step 4: Gated Implementation Handoff

After Step 3, QB may print a Step 4 Goal mode prompt. This prompt is for a separate implementation run; QB itself does not implement product changes during Steps 1-3.

QB should print the Step 4 prompt only when:

- `.qb/sub-planning-audit.md` exists;
- the audit status is `PASS`, or `PASS_WITH_WARNINGS` with no P0/P1 findings;
- the Step 4 validator passes.

When manually checking readiness from a QB repository checkout, use:

```bash
python3 plugins/qb/skills/qb/scripts/validate_planner_docs.py --root /path/to/project --mode step4
```

When running through an installed plugin, QB should use the bundled validator path exposed by the active skill. If that path is unavailable, it should perform equivalent all-file validation and state that validator execution was unavailable.

If the audit is `BLOCKED` or contains P0/P1 findings, repair the planning package first. If only P2/P3 warnings remain, the implementation prompt may be used but the warnings should stay visible.

The implementation handoff tells Codex to use relevant skills/plugins by scope, execute the READY/READY_WITH_WARNINGS queue continuously in small reversible slices, test before or with code changes, report exact blockers, avoid secrets, and limit token use by reading the audit/index first and only the active sub-plan afterward.

Step 4 should not stop after the first successful slice. It should continue to the next acceptance criterion or next eligible sub-plan until the queue is complete or a stop gate is hit, such as a P0/P1 finding, failing test, missing source file, required credential/live approval, unsafe external mutation, unrelated dirty worktree, or token/context budget pressure.

## Step 5: Export to planwright (automatic)

After Step 3, QB automatically projects the `.qb/` sub-plans into a flat, execution-ready `.qb/plan.md` in [planwright](https://github.com/eserlxl/planwright)'s 8-field checkbox item format — one item per "Planned Work Breakdown" entry, across all phases. Unlike Step 4 it never changes source code, so it runs without a gate or handoff prompt; it writes only `.qb/plan.md`. Validate it with the bundled validator, which mirrors the machine-checkable subset of planwright's plan linter:

```bash
python3 plugins/qb/skills/qb/scripts/validate_planwright_plan.py --root /path/to/project --strict
```

To run the plan with planwright: `cp .qb/plan.md .planwright/plan.md`, then run planwright `execute` (or `cycle <N>`). QB never writes to `.planwright/` or invokes planwright.

## Direct Step Invocation

You can invoke Step 2 or Step 3 directly:

```text
Use $qb to run Step 2 on the existing .qb/main-planning.md.
```

```text
Use $qb to run Step 3 and audit the existing sub-plans.
```

QB skips the Step 1 repo-aware intake when the requested step is explicit.

You can also invoke Step 1.5 directly when a main plan already exists:

```text
Use $qb to run Step 1.5 Assessment for this existing project.
```

You can also ask for the Step 4 prompt text after a completed audit:

```text
Use $qb to print the Step 4 implementation handoff prompt if the audit allows it.
```

The Step 5 export runs automatically after Step 3, but you can re-run it directly against existing sub-plans:

```text
Use $qb to export the .qb/ sub-plans to .qb/plan.md in planwright format.
```

## Validator Output

The validator prints deterministic summary lines such as:

```text
planner_docs_validation=passed
mode=step2
phase_folder_count=9
subplan_count=35
warning_count=0
error_count=0
```

It exits nonzero on structural failures. With `--strict`, repeated or generic section warnings are treated as failures. Secret scanning uses length-bounded token patterns so normal filenames such as `task-spec.yaml` are not flagged. In `--mode step4`, P0/P1 audit findings block implementation readiness while P2/P3 findings are warnings.

If `.qb/assessment.md` exists, the validator checks its required heading order during Step 2/3 validation. If it does not exist, Step 2/3 validation continues without treating Assessment as required.

## Safety Expectations

QB is not an implementation tool. It is designed to produce planning artifacts only.

If QB finds missing source files or missing planner outputs, it should follow the blocker behavior in the active planner prompt instead of inventing speculative output.
