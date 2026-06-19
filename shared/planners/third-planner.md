You are acting as a senior staff software architect, delivery quality auditor, planning consistency reviewer, and repository governance analyst.

You are executing Step 3 of a multi-step project planning workflow.

Step 1 produced:
.qb/main-planning.md

Step 2 produced:
.qb/sub-planning-index.md
.qb/phase-<number>-plans/phase-<number>.<subnumber>-<slug>.md

Your job in Step 3:
Audit and analyze the Step 2 sub-planning output.

This is a quality-control, coverage, consistency, and readiness audit task.

Do not implement features, refactor or modify source code, install dependencies, run
destructive or networked-mutation commands, commit, push, or open pull requests. Never
write secrets, credentials, tokens, private keys, local environment values, or sensitive
machine-specific data into any file.

Allowed file changes:
You may only create or update this file:

.qb/sub-planning-audit.md

Do not modify .qb/main-planning.md, .qb/sub-planning-index.md, any
.qb/phase-*-plans/*.md file, or any source code, config, tests, scripts, or docs outside
.qb/sub-planning-audit.md. If you find problems, do not fix them directly — report them
clearly in .qb/sub-planning-audit.md with recommended remediation actions.

Primary sources of truth:

1. .qb/main-planning.md
2. .qb/sub-planning-index.md
3. .qb/phase-*-plans/*.md

main-planning.md is the master plan.
sub-planning-index.md and all sub-plan files must be checked against it.

Language:
Write .qb/sub-planning-audit.md in English.

Repository inspection requirements:

Before writing the audit, inspect the repository safely.

Run only safe read-only commands such as:
- pwd
- git status --short --branch
- git branch --show-current
- git log --oneline -n 10
- find .qb -maxdepth 4 -type f | sort
- cat .qb/main-planning.md
- cat .qb/sub-planning-index.md
- find .qb -path "*/phase-*-plans/*.md" -type f | sort
- grep/ripgrep commands for headings and phase markers

Useful discovery: ripgrep .qb for section headings and phase markers, for
TODO/FIXME/TBD/unclear/missing/blocker/risk markers, and for secret/credential/readiness
terms.

If .qb/main-planning.md is missing:
- Create .qb/sub-planning-audit.md.
- Mark the audit status as BLOCKED.
- Explain that Step 3 cannot audit coverage without main-planning.md.
- Stop.

If .qb/sub-planning-index.md is missing:
- Create .qb/sub-planning-audit.md.
- Mark the audit status as BLOCKED.
- Explain that Step 3 cannot audit Step 2 index coverage without sub-planning-index.md.
- Still inspect any phase-*-plans folders if present.
- Stop after writing the blocker audit.

If no .qb/phase-*-plans/*.md files exist:
- Create .qb/sub-planning-audit.md.
- Mark the audit status as BLOCKED.
- Explain that Step 2 appears incomplete or missing.
- Stop.

Audit objectives:

You must evaluate:

1. Phase coverage
- Every main phase in main-planning.md must have a matching .qb/phase-<number>-plans/ folder.
- Every main phase must have at least one sub-plan file.
- No major phase should be silently missing.
- No generated phase folder should exist without a corresponding main phase unless clearly justified.

2. Phase order consistency
- Generated folders must preserve the phase order from main-planning.md.
- Sub-plan numbering must be sequential within each phase.
- Detect gaps such as phase-2.1, phase-2.3 with missing phase-2.2.
- Detect duplicates such as two phase-3.1 files.
- Detect inconsistent numbering such as phase-2-plans containing phase-3.1 files.

3. Naming convention compliance
Expected folder format:
.qb/phase-<number>-plans/

Expected sub-plan filename format:
phase-<phase-number>.<subphase-number>-<ascii-kebab-slug>.md

Check:
- ASCII-only filename slugs.
- No spaces in filenames.
- No accented or non-ASCII characters in filenames.
- No duplicate filenames.
- Folder number and file phase number match.
- Slugs are meaningful, not generic.

4. Index accuracy
Check .qb/sub-planning-index.md against actual files.

Verify:
- It references all phase folders.
- It references all generated sub-plan files.
- It does not reference missing files.
- It does not omit existing sub-plan files.
- Detected phase count matches main-planning.md.
- Recommended execution order is plausible.
- Coverage checklist is honest.

5. Required section structure in each sub-plan
Every sub-plan must contain exactly these required top-level sections, in this order:

# Phase X.Y — <Sub-Phase Title>

## 1. Context
## 2. Goal
## 3. Description
## 4. Scope
## 5. Out of Scope
## 6. Current Repository Evidence
## 7. Planned Work Breakdown
## 8. Acceptance Criteria
## 9. Validation and Test Approach
## 10. Dependencies and Sequencing
## 11. Risks and Mitigations
## 12. Desired End State
## 13. Transition Criteria to the Next Sub-Phase

Detect:
- missing sections;
- wrong order;
- duplicated sections;
- sections with empty or placeholder content;
- wrong phase number in title;
- mismatch between filename and H1 title.

6. Content quality
For each sub-plan, evaluate whether it is:
- grounded in main-planning.md;
- grounded in repository evidence where possible;
- specific enough for Step 4 implementation-task decomposition;
- not generic boilerplate;
- not over-fragmented;
- not too vague;
- not trying to implement code;
- not silently changing the master vision;
- clear about what is in scope and out of scope;
- clear about local readiness vs live readiness where relevant;
- clear about security and operational boundaries where relevant;
- clear about verification;
- clear about acceptance criteria;
- clear about dependencies and transition criteria.

7. Scope drift
Detect whether Step 2 introduced:
- new major phases not present in main-planning.md;
- missing major phases;
- renamed phases that change meaning;
- excessive documentation-only work;
- premature production/live activation;
- auto-merge or destructive operations without approval;
- tool-specific decisions that should remain adapter/runtime-level;
- source-of-truth confusion.

8. Readiness realism
Detect misleading readiness language.

Flag cases where:
- documentation or skeletons are described as production-ready;
- local smoke tests are treated as live readiness;
- config examples are treated as working credentials;
- issue tracker state is treated as execution truth;
- adapter/tool pilots are treated as core scheduler/control-plane;
- tests are mentioned without concrete validation commands or acceptance criteria.

9. Security and governance audit
Check sub-plans for:
- secret-safe language;
- no token/credential values;
- least privilege assumptions;
- approval gates for risky operations;
- command execution safety if relevant;
- path traversal or artifact integrity concerns if relevant;
- CI/review/merge/deploy boundaries;
- local vs cloud boundary;
- human approval boundaries.

10. Step 4 readiness
Evaluate whether the sub-plans are ready to be decomposed into implementation tasks.

Step 4 will likely create detailed implementation task files with:
- task IDs;
- files to modify;
- exact acceptance criteria;
- validation commands;
- execution order;
- dependencies;
- rollback notes;
- risk classification.

Your audit must say which phases/sub-plans are ready for Step 4 and which need repair first.

11. Planwright-item readiness
This audit is the verification barrier before QB exports items for planwright.
For every `## 7. Planned Work Breakdown` entry, check whether it can become a
normal executor item after this audit:
- it names a concrete implementation, hardening, test, committed-doc, config,
  script, CI, or runtime-artifact change;
- it can be grounded to existing repository evidence and likely source/test/doc
  surfaces outside `.qb/`;
- it has or can cite a real runnable verification command;
- its expected output is not another `.qb/` planning note, decision record,
  ledger row, audit finding, or spec-only artifact.

Flag sub-plans whose work breakdown mostly describes planning-file edits rather
than implementation work. These are not ready for planwright export even if their
section structure is valid. A documentation item is acceptable only when it edits
committed project documentation such as `README.md`, `RUNBOOK.md`, package docs,
or another tracked documentation surface outside `.qb/`.

Audit output file:

Create or update:

.qb/sub-planning-audit.md

Use exactly this top-level structure:

# Sub-Planning Audit

## 1. Audit Summary

Include:
- overall audit status: PASS, PASS_WITH_WARNINGS, or BLOCKED
- short explanation
- whether Step 2 output is usable for Step 4
- most important finding
- most important remediation action

Status definitions:
- PASS: Coverage and structure are complete; only minor wording issues exist.
- PASS_WITH_WARNINGS: Step 2 output is mostly usable, but some issues should be fixed before Step 4.
- BLOCKED: Missing main plan, missing index, missing sub-plan files, severe coverage gaps, or severe structure problems prevent reliable Step 4 decomposition.

## 2. Inspected Sources

List:
- files inspected;
- folders inspected;
- important commands run;
- things not verified.

Do not include secrets.

## 3. Main Phase Coverage Analysis

Create a table comparing main-planning.md phases to generated folders and sub-plans.

Columns:
- Main phase number
- Main phase title
- Expected folder
- Folder exists?
- Sub-plan count
- Coverage status
- Notes

Mark status:
- OK
- WARNING
- MISSING
- EXTRA
- BLOCKED

## 4. Sub-Plan File Inventory

List all detected sub-plan files grouped by phase folder.

For each file include:
- filename;
- detected H1 title;
- phase number match status;
- section structure status;
- content quality status;
- notes.

## 5. Naming and Ordering Check

Report:
- folder naming issues;
- filename naming issues;
- numbering gaps;
- duplicate numbers;
- folder/file phase mismatches;
- non-ASCII slug issues;
- order inconsistencies.

If no issues, explicitly say no naming/order issues were found.

## 6. Index Consistency Check

Compare sub-planning-index.md to actual files.

Report:
- missing references;
- broken references;
- unindexed files;
- phase count mismatch;
- inaccurate coverage claims;
- questionable execution order.

## 7. Required Section Structure Check

For each sampled or all sub-plans, report required section compliance.

Prefer checking all sub-plans if the number is manageable.
If there are many files, check all headings programmatically/readably and sample content quality manually.

Include:
- missing sections;
- duplicated sections;
- wrong order;
- empty sections;
- placeholder sections.

## 8. Content Quality and Actionability Analysis

Analyze:
- whether sub-plans are specific;
- whether they are actionable;
- whether they preserve the main plan;
- whether they are suitable for Step 4 task decomposition;
- whether acceptance criteria are verifiable;
- whether validation approach is realistic;
- whether dependencies are explicit.

Be direct. If the docs are generic, say so.

## 9. Scope Drift and Architectural Consistency Analysis

Report any drift from main-planning.md.

Include:
- added/removed/renamed phase meaning;
- wrong ownership of state;
- tool vs core boundary confusion;
- premature live/production activation;
- over-documentation;
- missing security hardening;
- missing operational controls.

Adapt this section to the project domain if it is not an agentic/software-factory project.

## 10. Readiness Realism

Evaluate whether the planning language correctly distinguishes:
- docs vs implementation;
- skeleton vs working runtime;
- local readiness vs live readiness;
- smoke tests vs production confidence;
- examples vs real configs;
- pilot adapters vs production core.

Flag overclaims.

## 11. Security and Governance Findings

Report security/governance concerns in the generated plans.

Include:
- secret safety;
- command execution safety;
- path/artifact integrity;
- least privilege;
- approval gates;
- review/CI/merge boundaries;
- cloud/local boundary;
- destructive or risky operations.

If the project domain differs, adapt but still check for security boundaries.

## 12. Step 4 Readiness Assessment

Create a table:

Columns:
- Phase / Sub-Plan
- Finding IDs (the AUDIT-FIX-NN ids from section 13 that affect this sub-plan, or none)
- Ready for Step 4?
- Dependency State
- Reason
- Required fix before Step 4 starts

Use Ready-for-Step-4 statuses:
- READY
- READY_WITH_WARNINGS
- NEEDS_REPAIR
- BLOCKED

For a re-audit of an in-progress repository, a sub-plan may instead be terminal:
- COMPLETE — already implemented and verified; not a Step 4 candidate.
- SUPERSEDED — replaced by a later plan or decision; carried for traceability only.
- DEFERRED — intentionally postponed and tracked; not in the active queue.

Dependency State (do this sub-plan's prerequisites hold?):
- satisfied — prerequisite sub-plans are COMPLETE/verified.
- independent — no prerequisites.
- blocked — a prerequisite is not yet satisfied.
- unknown — prerequisite state could not be determined.

Close the section with an execution-queue verdict: the ordered list of READY and
READY_WITH_WARNINGS sub-plans that form the Step 4 queue, or "queue empty" with the
reason (all terminal, or blocked by open/accepted P0/P1 findings).

## 13. Prioritized Fix List

List concrete fixes needed before Step 4.

Write each finding as a single-line header in this form:

- AUDIT-FIX-NN | PX | <short title>

The severity token (PX) comes immediately after the id. You may carry an optional
per-finding lifecycle status as the next pipe-delimited field, before the title:

- AUDIT-FIX-NN | PX | <status> | <short title>

where <status> is one of:
- open — not yet addressed (the default when the field is omitted).
- accepted — the risk is knowingly carried forward; it stays visible but does not block.
- resolved — already fixed; recorded for traceability only.
- not_applicable — does not apply after review; recorded only.

Only open and accepted findings gate Step 4: a resolved or not_applicable P0/P1 no
longer holds the gate shut, so re-auditing an in-progress repo is not blocked by
findings that are already remediated. Put the status only in this dedicated field; do
not rely on a status word appearing inside the title.

Follow each header with optional detail bullets covering:
- affected file(s)
- issue
- recommended fix
- why it matters

Severity guide:
- P0: blocks Step 4 or could cause dangerous planning/implementation.
- P1: serious issue that should be fixed before implementation.
- P2: quality issue that can be fixed soon.
- P3: minor wording or maintainability issue.

Do not modify affected files. Only report fixes.

## 14. Recommended Next Command / Prompt

Provide a concise recommendation for the next prompt.

If audit PASS:
- Recommend Step 4 implementation-task decomposition prompt.
- Name the first phase/sub-plan to decompose.

If PASS_WITH_WARNINGS:
- Recommend a Step 3.1 repair prompt targeting only the identified files.
- Include the highest-priority repair scope.

If BLOCKED:
- Recommend the minimal prompt needed to unblock Step 2/3.

Do not actually run the next prompt.

## 15. Audit Result

End with:
- final status;
- confidence level: high, medium, or low;
- whether only .qb/sub-planning-audit.md was modified;
- whether any unexpected modifications were detected;
- whether Step 4 can safely begin.

Validation after writing the audit:

After creating/updating .qb/sub-planning-audit.md: read it back; run
`find .qb -maxdepth 4 -type f | sort`, `git diff -- .qb/sub-planning-audit.md`, and
`git status --short`; and confirm only .qb/sub-planning-audit.md changed. If any other
file changed, report it as unexpected and do not fix it unless explicitly asked.

Goal-following behavior:

This is a long audit task — do not stop after only one phase. You may stop only when:

A. Success: .qb/sub-planning-audit.md exists and you have checked main-planning.md
coverage, sub-planning-index.md consistency, all phase folders, all sub-plan files,
required section structure, naming/ordering, Step 4 readiness, the prioritized fix list,
and git status.

B. Blocked: .qb/main-planning.md or .qb/sub-planning-index.md is missing, no sub-plan
files exist, or read errors prevent the audit. If blocked, still create
.qb/sub-planning-audit.md, mark status BLOCKED, explain the blocker and the minimal next
action, then stop.

Final response requirements:

After completion, give a concise English summary: audit status; main phases detected;
sub-plan files inspected; P0/P1/P2/P3 finding counts; whether Step 4 can begin; the most
important fix (if any); the recommended next prompt direction; and confirmation that only
.qb/sub-planning-audit.md was modified (or a list of unexpected modifications).

Remember: this is an audit-and-analysis step — do not fix the sub-plans, create new
phase plans, or change the master plan. Only create or update
.qb/sub-planning-audit.md.

Parallel shard mode (optional):

This audit is normally run once over all phases (the default behavior described above).
When the launching orchestrator can fan the work out across independent actors, it may
instead launch one run of this prompt per phase folder, in parallel, followed by exactly
one reduce run that assembles the final audit. A run is in shard mode only when its
launching brief sets an explicit phase scope, for example:

PHASE SCOPE: 2

In shard mode, for the single assigned phase <n>:
- Inspect ONLY .qb/phase-<n>-plans/ (plus read-only .qb/main-planning.md for grounding).
- Do NOT write any file under .qb/. In particular do NOT create or modify
  .qb/sub-planning-audit.md and do NOT write fragment files. Return your findings in-band
  as your final message, as structured partial findings.
- Report, for your phase: the phase number; whether the folder exists and its sub-plan
  count; for each sub-plan file its filename, detected H1 title, phase-number match,
  required-section-structure status, and a content-quality verdict with notes; intra-phase
  numbering gaps or duplicates; naming-convention issues; readiness-realism and
  security/governance flags; and a per-phase Step 4 readiness verdict.
- Tag each finding with a LOCAL id of the form PH<n>-<seq> (for example PH2-01) and a
  severity P0-P3. Do NOT mint AUDIT-FIX-NN ids and do NOT emit a bare overall status line
  (PASS / PASS_WITH_WARNINGS / BLOCKED); those belong to the reduce run only.
- Do NOT compute the global checks: main-phase coverage (section 3), index consistency
  (section 6), cross-phase ordering, or the overall audit status. A single-phase shard
  cannot see a phase that has no folder, so coverage must be computed at reduce time.

The reduce run (an unscoped run of this prompt, or the orchestrator acting as the sole
audit writer) is the only writer of .qb/sub-planning-audit.md. It consumes the per-phase
partial-findings blocks, recomputes the global checks from the full file set on disk
(main-phase coverage, cross-phase ordering, index consistency), flattens every local
PH<n>-<seq> finding into one globally renumbered AUDIT-FIX-NN | PX list in section 13
(sorted by severity then phase), rolls the worst per-phase verdict plus the global findings
into a single overall status, writes all 15 sections in the exact required order with one
canonical status line, then runs validate_planner_docs.py --mode step3 --strict and --mode
step4 once over the complete audit, and confirms git status shows only
.qb/sub-planning-audit.md changed.

When no phase scope is given, this section does not apply: behave exactly as the default
above - audit every phase and write the single sub-planning-audit.md in a single run.
