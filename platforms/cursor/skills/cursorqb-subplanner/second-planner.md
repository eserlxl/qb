You are acting as a senior staff software architect, technical program planner, and delivery planner.

You are executing Step 2 of a multi-step project planning workflow.

Your job:
Read Planner-docs/Main-Planning.md in detail, extract the main phase roadmap from it, and create detailed sub-planning documents for each main phase.

This is a planning-only task.
Do not implement product features.
Do not refactor code.
Do not modify source code.
Do not install dependencies.
Do not run destructive commands.
Do not run networked mutation commands.
Do not commit changes.
Do not push branches.
Do not open pull requests.
Do not write secrets, credentials, tokens, private keys, local environment values, or sensitive machine-specific data into any planning file.

Allowed file changes:
You may only create or update files under:

Planner-docs/

You must not modify files outside Planner-docs/.

Important source of truth:
The primary source of truth for this step is:

Planner-docs/Main-Planning.md

Optional supporting source:
If it exists, read this file fully before generating sub-plans:

Planner-docs/Autopsy.md

Autopsy.md is not a replacement for Main-Planning.md. It is a supporting feedback source from Step 1.5. Use it to enrich sub-plans with concrete repo feedback, technical debt, placeholder/stub findings, broken integration risks, test gaps, security/governance gaps, and readiness blockers. Do not block Step 2 when Autopsy.md is absent.

You must not invent a new master plan.
You must not replace the main plan.
You must not change the phase order unless the main plan is internally inconsistent, and even then you must preserve the original order while documenting the inconsistency in the generated index.

Step 1 produced the high-level master plan.
Step 1.5 may have produced an existing-project autopsy report.
Step 2 must now decompose that master plan into detailed sub-plans, incorporating Autopsy.md feedback when that file exists.

Expected output structure:

Planner-docs/
  Main-Planning.md
  Sub-Planning-Index.md
  Phase-0-Plans/
    Phase0.1-<short-slug>.md
    Phase0.2-<short-slug>.md
    ...
  Phase-1-Plans/
    Phase1.1-<short-slug>.md
    Phase1.2-<short-slug>.md
    ...
  Phase-2-Plans/
    Phase2.1-<short-slug>.md
    Phase2.2-<short-slug>.md
    ...
  ...

If Main-Planning.md starts phases from Phase 1, start with Phase-1-Plans.
If Main-Planning.md includes Phase 0, create Phase-0-Plans.
If Main-Planning.md uses a different naming style such as “Phase 1” or “Phase 1”, normalize generated folder names as:
Phase-<number>-Plans

For sub-plan filenames, use:
Phase<phase-number>.<subphase-number>-<short-ascii-kebab-slug>.md

Examples:
Phase1.1-repo-foundation-hardening.md
Phase1.2-live-readiness-gates.md
Phase2.1-api-contracts.md
Phase2.2-persistent-db-schema.md

Filename rules:
- Use ASCII-only lowercase slugs.
- Do not use spaces.
- Do not use accented or non-ASCII characters in filenames.
- Keep slugs short but meaningful.
- Do not create duplicate filenames.
- If rerunning this prompt, update existing matching files instead of creating duplicates.

Language:
All generated planning documents must be written in English.

Planning depth:
This step should be more detailed than Main-Planning.md, but it is still a planning task.
Do not write production code.
Do not generate implementation patches.
Do not create actual config files, migrations, service code, or tests.
You may reference likely files/directories that future implementation steps will touch, but do not modify those files now.

Repository inspection requirements:

Before writing sub-plans, inspect the repository safely.

Run only safe read-only commands such as:
- pwd
- git status --short --branch
- git branch --show-current
- git log --oneline -n 10
- find Planner-docs -maxdepth 3 -type f | sort
- cat Planner-docs/Main-Planning.md
- ls
- find . -maxdepth 3 -type f | sort | head -300
- cat README.md if present
- cat AGENTS.md if present
- inspect pyproject.toml, package.json, Makefile, docker-compose files, CI workflow files, docs indexes, architecture docs, runbooks, test files, config examples, service skeletons, package skeletons, and policy files if present

You may use ripgrep/grep for discovery:
- rg "Phase|Phase|roadmap|plan|architecture|maturity|readiness|activation|production|security|policy|worker|scheduler|gateway|adapter|test|smoke|CI|API|database|Postgres|queue|artifact|approval|review|risk|acceptance|Linear|GitHub|Temporal|LangGraph|LiteLLM|Codex|OpenCode|Claude|Gemini" .

If Planner-docs/Main-Planning.md is missing:
- Do not attempt full Step 2 decomposition.
- Create Planner-docs/Step2-Blocked.md.
- Explain that Step 2 requires Planner-docs/Main-Planning.md.
- Include the exact missing file path.
- Include what should be done next.
- Stop after creating that blocker document.

If Main-Planning.md exists but does not contain clear phases:
- Do not invent a detailed phase tree blindly.
- Create Planner-docs/Step2-Blocked.md.
- Explain that the main plan lacks a clear phase roadmap.
- Include suggested corrections needed in Main-Planning.md.
- Stop after creating that blocker document.

Sub-planning strategy:

1. Read Main-Planning.md fully.
2. Identify:
   - project vision;
   - target end state;
   - current-state conclusion;
   - main architectural decisions;
   - all main phases;
   - phase order;
   - phase goals;
   - phase maturity levels if present;
   - major risks;
   - Step 2 notes if present.
3. Preserve the main phase order.
4. For each main phase, create a folder:
   Planner-docs/Phase-<number>-Plans/
5. For each main phase, create a reasonable number of sub-phase plan documents.

Sub-phase sizing rules:
- Prefer 3-7 sub-phases per major phase.
- Small phases may have 1-3 sub-phases.
- Large phases may have 6-9 sub-phases, but avoid excessive fragmentation.
- Do not create 20 tiny sub-phases for one phase.
- Each sub-phase should represent a coherent delivery slice.
- Each sub-phase should have a clear outcome and validation approach.
- If a phase is future/uncertain, plan it at a lower detail level and explicitly mark unresolved decisions.

Important:
The plan must drive real delivery.
Avoid creating endless documentation-only work.
Each sub-plan should define a path toward observable implementation, validation, or operational readiness.

For each sub-plan file, use exactly this top-level structure:

# Phase X.Y — <Sub-Phase Title>

## 1. Context

Explain how this sub-phase connects to:
- the main project vision;
- the parent phase from Main-Planning.md;
- current repository state;
- previous phases or dependencies.

Be specific and grounded in repository evidence where possible.

## 2. Goal

State the goal of this sub-phase.

The goal must be outcome-oriented, not activity-oriented.

Bad:
“Write some docs.”

Good:
“Define a persistent task/lease/attempt state model that allows worker execution to survive process restarts.”

## 3. Description

Describe what will be planned or built in this sub-phase.

Include:
- what problem this sub-phase solves;
- why it belongs at this point in the roadmap;
- how it reduces project risk;
- how it prepares later phases.

## 4. Scope

List what is included.

Use concise bullet points.

Include likely areas such as:
- documentation;
- schemas/contracts;
- API boundaries;
- services;
- packages;
- policies;
- tests/smokes;
- artifacts;
- configuration;
- CI;
- observability;
- security;
- integrations;
only where relevant.

## 5. Out of Scope

List what is explicitly not included.

This prevents scope creep.

Examples:
- production deployment;
- real external API mutation;
- auto-merge;
- cloud activation;
- UI implementation;
- model fine-tuning;
- infrastructure scaling;
- secret handling beyond preflight;
only where relevant.

## 6. Current Repository Evidence

Summarize repository evidence relevant to this sub-phase.

Include:
- files/directories already present;
- tests or smoke targets already present;
- docs/runbooks already present;
- skeletons or missing implementations;
- contradictions or stale assumptions.

If no evidence exists, say:
“Current repository evidence for this sub-phase is limited.”

Do not invent evidence.

## 7. Planned Work Breakdown

Create a detailed but not code-level work breakdown.

Each item should include:
- ID, using format FX.Y-NN
- title
- description
- expected output

Example:
- F2.3-01 — Task state schema clarification
  - Description: Defines ASF task lifecycle states as queued/running/review/completed/failed/cancelled.
  - Output: schema document, DB model draft, lifecycle state diagram note.

Do not create implementation code.

## 8. Acceptance Criteria

Define concrete acceptance criteria.

Acceptance criteria must be verifiable.

Examples:
- “Planner-docs/Phase-2-Plans/Phase2.1-api-contracts.md contains an endpoint list, request/response drafts, and auth assumptions.”
- “If there is no API implementation, this is explicitly stated.”
- “Local readiness and live readiness are evaluated separately.”
- “Secret values are not written into plan files.”

## 9. Validation and Test Approach

Describe how this sub-phase should be validated later.

Include likely commands only if they already exist or are obvious from the repo, such as:
- make check
- make smoke
- make ci-local
- python3 scripts/scan-secrets.py
- git diff --check

For future commands, mark them as proposed.

Distinguish:
- document validation;
- local smoke;
- live readiness;
- CI;
- security validation;
- artifact validation.

## 10. Dependencies and Sequencing

Describe dependencies.

Include:
- previous sub-phases;
- required decisions;
- required credentials or live endpoints if any;
- required infrastructure;
- required human approvals.

Be explicit about what blocks implementation.

## 11. Risks and Mitigations

List risks specific to this sub-phase.

For each:
- risk;
- impact;
- mitigation.

Be direct.

## 12. Desired End State

Describe the desired end state after this sub-phase is completed.

This should be concrete enough that an implementer can understand what “done” means.

## 13. Transition Criteria to the Next Sub-Phase

Define what must be true before moving to the next sub-phase.

Examples:
- “Core decisions must be written down and free of contradictions.”
- “Local validation commands must pass.”
- “Work requiring live credentials must not be activated yet.”
- “Worker activation must not begin before the artifact contract is complete.”

Index file requirements:

Create or update:

Planner-docs/Sub-Planning-Index.md

This file must include:

# Sub-Planning Index

## 1. Purpose

Explain that this index maps Main-Planning.md phases to detailed sub-plan files.

## 2. Source Master Plan

Reference:
Planner-docs/Main-Planning.md

Include:
- detected phase count;
- detected phase names;
- any ambiguity or inconsistency found.

## 3. Phase and Sub-Plan Map

For each phase:
- phase number;
- phase title;
- phase summary;
- generated folder;
- generated sub-plan files;
- recommended execution order.

Use a table or nested list.

## 4. Prioritized Elaboration Order

Explain which sub-plans should be executed first and why.

Prioritize:
- security hardening;
- real local validation;
- core state/control-plane;
- live gateway/API activation;
- worker/runtime execution;
- review/CI/artifact gates;
- observability and production readiness;
adapted to the project domain.

## 5. Out-of-Scope or Deferred Topics

List topics that should not be expanded yet because they depend on unresolved decisions or future evidence.

## 6. Coverage Check

Include a checklist proving:
- every main phase from Main-Planning.md has a folder;
- every main phase has at least one sub-plan;
- sub-plan filenames follow the naming convention;
- generated docs are in English;
- no source code files were modified;
- no secrets were written.

## 7. Repository Inspection Notes

Include:
- commands run;
- important files inspected;
- assumptions made;
- things not verified.

Quality requirements:

The generated sub-plans must be:
- grounded in Main-Planning.md;
- grounded in repository evidence where available;
- sequential and realistic;
- detailed enough for Step 3 implementation-task decomposition;
- not generic templates;
- not over-fragmented;
- not implementation code;
- explicit about uncertainty;
- explicit about local vs live readiness;
- explicit about security and operational boundaries;
- useful for a senior engineering team.

Important planning principles:

Use these principles while generating the sub-plans:

1. Main-Planning.md is the source of truth.
2. Do not silently rewrite the project vision.
3. Do not confuse docs/skeleton/smoke with production readiness.
4. Separate local readiness from live readiness.
5. Separate work-management visibility from execution truth.
6. Separate core control plane from adapters/runtimes/tools.
7. Prioritize security hardening before live automation.
8. Prefer measurable acceptance criteria.
9. Every live workflow must produce artifacts/evidence.
10. Risky operations require policy, review, and human approval boundaries.
11. Avoid making future implementation depend on secrets being written into repo files.
12. Do not plan auto-merge, destructive production operations, or broad credential access without explicit approval gates.
13. If the repository is already advanced in some phases, plan from the observed state instead of restarting from scratch.
14. If the repository has many planning files but little working runtime, say that clearly in the relevant sub-plans.
15. If there are severe blockers, call them out directly.

Goal-following behavior:

This is a long planning task. Continue until all required sub-plan files and the index are created or updated.

Do not stop after only one phase unless a blocking condition prevents continuation.

Use this stopping rule:

You may stop only when one of the following is true:

A. Success:
- Planner-docs/Sub-Planning-Index.md exists;
- every phase detected from Planner-docs/Main-Planning.md has a corresponding Planner-docs/Phase-<number>-Plans/ folder;
- every phase has at least one PhaseX.Y-*.md sub-plan;
- every sub-plan uses the required section structure;
- all generated content is English;
- no files outside Planner-docs/ were modified;
- git diff confirms only Planner-docs/ changes.

B. Blocked:
- Planner-docs/Main-Planning.md is missing; or
- Main-Planning.md has no clear phase roadmap; or
- repository access/read errors prevent safe planning.

If blocked:
- create Planner-docs/Step2-Blocked.md;
- explain the blocker;
- do not generate speculative sub-plans;
- stop.

Validation after writing:

After generating all files:

1. Run:
   find Planner-docs -maxdepth 3 -type f | sort

2. Verify all generated folders and files exist.

3. Read back:
   Planner-docs/Sub-Planning-Index.md

4. Sample-read at least one generated sub-plan per phase.

5. Check that all required section headings exist in each sampled sub-plan.

6. Run:
   git diff -- Planner-docs

7. Run:
   git status --short

8. Confirm no files outside Planner-docs were modified.

9. Check generated docs for obvious secret leakage:
   - do not print secret values;
   - do not include tokens;
   - do not include local private endpoint credentials;
   - do not include private keys.

Final response requirements:

After completion, provide a concise final summary in English.

Include:
- whether Step 2 succeeded or was blocked;
- how many main phases were detected;
- how many sub-plan files were created or updated;
- which folders were created;
- where the index file is;
- the recommended first sub-plan to execute next;
- any blockers, ambiguities, or assumptions;
- confirmation that only Planner-docs/ was modified, or explicitly list any unexpected modifications.

Remember:
Only create or modify files under Planner-docs/.
Do not modify source code.
Do not modify Main-Planning.md unless absolutely necessary, and by default do not change it.
Do not create implementation files.
Do not commit, push, install, deploy, or open PRs.
