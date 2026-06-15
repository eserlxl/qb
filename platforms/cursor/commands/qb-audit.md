---
name: qb-audit
description: Run only the QB Step 3 audit (re-audit) of existing Planner-docs sub-plans.
---

# QB Audit

Invoke the `qb-auditor` skill directly, without re-running Steps 1 and 2. It launches
automatically as a Cursor goal via the `define-goal` skill - no manual "Follow the Goal" button.

Use this to (re)audit the current `Planner-docs/` sub-plans - for example after applying
repairs from a previous `PASS_WITH_WARNINGS` result. The skill reads
`Planner-docs/Main-Planning.md`, `Planner-docs/Sub-Planning-Index.md`, and every
`Planner-docs/Phase-*-Plans/*.md`, then produces only `Planner-docs/Sub-Planning-Audit.md`
(in English) and returns a `PASS` / `PASS_WITH_WARNINGS` / `BLOCKED` status. It never edits the
plans themselves.
