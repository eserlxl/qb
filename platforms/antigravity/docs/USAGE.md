# Usage

QB runs a vibecoding-first, repo-aware planning workflow with optional Step 1.5 Assessment, project ontology, and planning ledger continuity for existing projects.

The workflow is planning-first. QB creates and audits `.qb/` artifacts during Steps 1-3, then prints a separate gated implementation prompt for Step 4 only when the audit allows implementation.

Optional continuity artifacts:

```text
.qb/project-ontology.md
.qb/planning-ledger.md
```

`project-ontology.md` preserves vocabulary, entities, workflows, boundaries, integrations, and invariants. `planning-ledger.md` records planning runs, implementation summaries, current state snapshots, and replanning inputs so later QB runs can understand what was planned and what was applied.

## Step 1: Main Plan

Open the project repository you want Antigravity to analyze and ask:

```text
Use the qb skill to create a main plan for this project.
```

QB first performs a bounded read-only scan of the current repository. It may inspect files such as `README.md`, `AGENTS.md`, manifests, CI workflows, docs indexes, deployment files, tests, top-level service directories, and any existing `.qb/planning-ledger.md` or `.qb/project-ontology.md`.

Then it asks four intake questions, one at a time:

- `PROJECT_NAME`: the project name.
- `PROJECT_INTENT`: what the project is for and what it should become.
- `TARGET_END_STATE`: what done looks like across product, engineering, operations, security, and user value.
- `KNOWN_CONSTRAINTS`: team, infrastructure, budget, timeline, stack, compliance, must-use tools, must-not-use tools, desired autonomy level, human review cadence, and any token/usage budget.

QB asks intake questions in the user's language when practical. Generated .qb artifacts are English by default unless the user explicitly requests another body language. Required document headings remain English for validator stability.

After the answers are collected, QB loads `first-planner.md`, substitutes the values, inspects the repository, and creates or updates:

```text
.qb/main-planning.md
```

Step 1 is allowed to modify only that file.

## Step 1.5: Existing Project Assessment

When the target repository is an existing or partially built project, QB runs `assessment-planner.md` after Step 1.

Expected output:

```text
.qb/assessment.md
.qb/project-ontology.md   # optional when enough evidence exists
```

The Assessment report analyzes project sections, feature inventory, placeholders/stubs/skeletons, technical debt, missing or broken integrations, test and CI gaps, security/governance issues, operational readiness, and alignment with `.qb/main-planning.md`. The optional ontology captures domain vocabulary, entities, workflows, boundaries, integrations, invariants, and open concept questions.

Step 1.5 is skipped for empty or nearly empty repositories. In that case, `assessment.md` is not required and Step 2 should continue without it.

When manually validating Step 1.5 from a QB checkout, use:

```bash
python3 skills/qb/scripts/validate_planner_docs.py --root /path/to/project --mode assessment --strict
```

## Step 2: Phase Sub-Plans

After Step 1, QB prints a text block for a new Antigravity task or conversation:

```text
Use the qb skill. Run Step 2 according to references/second-planner.md.

Read all main phases in .qb/main-planning.md. If .qb/assessment.md, .qb/project-ontology.md, or .qb/planning-ledger.md exists, read it fully as supporting evidence and account for it in the sub-phase plans. Plan in a vibecoding-first style: small reversible slices, fast validation signals, explicit deferrals, secure engineering boundaries, and Antigravity task readiness. For each phase, create phase-<n>-plans folders and detailed phase-<n>.<m>-*.md sub-plan files under .qb. Do not stop until all phases are covered. Modify only .qb.
```

Expected outputs:

```text
.qb/sub-planning-index.md
.qb/phase-<n>-plans/phase-<n>.<m>-*.md
```

`.qb/main-planning.md` remains the primary source of truth. `.qb/assessment.md`, `.qb/project-ontology.md`, and `.qb/planning-ledger.md`, when present, are supporting evidence that should influence sub-plan evidence, work breakdowns, acceptance criteria, risks, ontology consistency, and replanning continuity.

When manually validating from a QB checkout, use:

```bash
python3 skills/qb/scripts/validate_planner_docs.py --root /path/to/project --mode step2 --strict
```

## Step 3: Sub-Plan QA Audit

After Step 2, QB prints another text block for a new Antigravity task or conversation:

```text
Use the qb skill. Run Step 3 according to references/third-planner.md.

Audit .qb/main-planning.md, .qb/sub-planning-index.md, .qb/phase-*-plans/*.md, and any supporting .qb/assessment.md, .qb/project-ontology.md, or .qb/planning-ledger.md. Analyze main-phase coverage, file naming, sequencing, required section structure, index consistency, content quality, scope drift, readiness realism, ontology consistency, planning-history continuity, security/governance, vibecoding slice quality, and Step 4 readiness. Do not fix any plan files; produce only .qb/sub-planning-audit.md. Do not stop until all phases and sub-plans have been reviewed.
```

Expected output:

```text
.qb/sub-planning-audit.md
```

When manually validating from a QB checkout, use:

```bash
python3 skills/qb/scripts/validate_planner_docs.py --root /path/to/project --mode step3 --strict
```

## Step 4: Gated Implementation Handoff

After Step 3, QB may print a Step 4 implementation prompt. This prompt is for a separate Antigravity implementation task; QB itself does not implement product changes during Steps 1-3.

QB should print the Step 4 prompt only when:

- `.qb/sub-planning-audit.md` exists;
- the audit status is `PASS`, or `PASS_WITH_WARNINGS` with no P0/P1 findings;
- the Step 4 validator passes.

When manually checking readiness from a QB checkout, use:

```bash
python3 skills/qb/scripts/validate_planner_docs.py --root /path/to/project --mode step4
```

If the audit is `BLOCKED` or contains P0/P1 findings, repair the planning package first. If only P2/P3 warnings remain, the implementation prompt may be used but the warnings should stay visible.

The implementation handoff tells Antigravity to use relevant skills, project rules, helper agents when available, and security review guidance by scope; execute the READY/READY_WITH_WARNINGS queue continuously in small reversible slices; test before or with code changes; report exact blockers; avoid secrets; update `.qb/planning-ledger.md` with concise verified-slice or stop-event summaries; and limit token use by reading the audit/index first and only the active sub-plan afterward.

The implementation task should continue to the next acceptance criterion or next queued sub-plan after each verified slice. It should stop only for explicit gates such as P0/P1 or safety/security findings, failing tests, missing required files, plan/audit/repo contradictions, approval or credential blockers, unsafe external mutations, unrelated dirty worktree state, unavailable validation with no fallback, token/context pressure, or a user stop request.

## Validation Notes

If `.qb/assessment.md`, `.qb/project-ontology.md`, or `.qb/planning-ledger.md` exists, the validator checks required heading order during Step 2/3/4 validation. If these optional continuity docs do not exist, Step 2/3 validation continues without treating them as required. Use `--mode assessment --strict` after Step 1.5 when `assessment.md` should be required.

## Release and Sync

This Antigravity package participates in version bumps but not in source sync. `scripts/bump-version.sh` updates `platforms/antigravity/CHANGELOG.md` and the `SKILL.md` version in lockstep with the three engine-bearing hosts, so the antigravity CHANGELOG carries the same `## [<version>]` header as Claude Code, Cursor, and Codex. Antigravity is intentionally **not** a `scripts/sync.sh` destination, however: its planner and docs are authored on their own path rather than materialized from `shared/`. In short, antigravity is **bump-yes / sync-no**.

## Safety Expectations

QB is not an implementation tool. It is designed to produce planning artifacts only during Steps 1-3.

If QB finds missing source files or missing planner outputs, it should follow the blocker behavior in the active planner prompt instead of inventing speculative output.
