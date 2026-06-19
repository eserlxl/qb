# QB Planning Ledger

QB uses `.qb/planning-ledger.md` as an optional durable memory artifact for planning and implementation history.

QB uses the corrected `Planning` spelling; the artifact filename is `.qb/planning-ledger.md`.

## Purpose

The ledger answers:

- What planning runs were completed?
- Which plans were implemented?
- What did each implementation run change?
- Which validation commands passed or failed?
- What is the latest known project state?
- What should future replanning read before creating new phases?

## Recommended File

```text
.qb/planning-ledger.md
```

## Recommended Headings

Ledger v2 is the default structure for new files:

```markdown
# Planning Ledger

## 1. Purpose
## 2. Planning Runs
## 3. Plan Snapshot Registry
## 4. Sub-Plan Status Matrix
## 5. Implementation Runs
## 6. Current State Snapshot
## 7. Replanning Inputs
## 8. Open Decisions and Follow-Ups
```

Legacy v1 ledgers (the older six-section structure) remain valid for compatibility;
treat one as a deprecation warning and migrate it to Ledger v2 before Step 4
implementation starts.

## Update Rules

- Step 1 and Step 1.5 should read the ledger when it exists.
- Step 2 should read the ledger when it exists and carry relevant implementation history into sub-plans.
- Step 4 should append a concise implementation summary after each verified slice or stop event.
- Do not store secrets, tokens, credentials, private paths, or large logs.
- Store concise links or file paths to evidence instead of dumping full output.

## Plan Snapshot Registry

Record each planning/replanning run as a snapshot so sub-plan rows can point at the
plan version they were judged against:

```markdown
| Snapshot ID | Created At | Main Plan | Audit Status | Notes |
|---|---|---|---|---|
```

A new snapshot is created whenever Step 1/2/3 regenerate the plan or audit. Sub-Plan
Status Matrix rows reference the snapshot they belong to, so drift between an old row
and the current plan is visible.

## Sub-Plan Status Matrix

Allowed status values: `planned`, `ready`, `ready_with_warnings`, `in_progress`,
`implemented`, `verified`, `blocked`, `superseded`.

```markdown
| Sub-plan Path | Status | Snapshot ID | Run ID | Validation Evidence | Blocker | Next Action | Superseded By | Updated At |
|---|---|---|---|---|---|---|---|---|
```

Status semantics and required evidence:

- `planned`: no execution run exists yet.
- `ready`: the audit says the slice is executable.
- `ready_with_warnings`: only open/accepted P2/P3 or accepted risks remain.
- `in_progress`: a Run ID is required (a Next Action alone is not enough evidence).
- `implemented`: targeted validation evidence is required; the final acceptance/repo gate may still be pending.
- `verified`: acceptance criteria and required repo gates passed; Validation Evidence is required.
- `blocked`: a Blocker and a Next Action are required.
- `superseded`: a Superseded By reference is required.

Path safety: `Sub-plan Path` must be repo-relative, must not be absolute, and must not
contain `..`. Use the shape:

```text
.qb/phase-<n>-plans/phase-<n>.<m>-<slug>.md
```

Do not keep two active rows for the same sub-plan with conflicting statuses.

## Step 4 Implementation Run Summary

Each Step 4 summary entry should include:

```markdown
### <date/time or run label> — <short run title>

- Source plan(s): <sub-plan paths>
- Slice(s) completed: <brief list>
- Files changed: <paths>
- Validation run: <commands and status>
- Evidence/artifacts: <paths or summaries>
- Remaining blockers: <none or concise blockers>
- Next recommended slice: <next queue item>
```

## Replanning Use

When a user reruns QB for follow-up development, the agent should read the ledger before asking intake questions when possible. The agent should use the ledger as evidence, not as an unquestioned source of truth. Repository state, tests, and current user intent still win when they conflict with old ledger entries.
