---
name: qb-audit
description: Run only the QB Step 3 audit (re-audit) of existing .qb sub-plans.
---

# QB Audit

Invoke the `qb-auditor` skill directly, without re-running Steps 1 and 2. It launches
automatically as a Cursor goal via the `define-goal` skill - no manual "Follow the Goal" button.

Use this to (re)audit the current `.qb/` sub-plans - for example after applying
repairs from a previous `PASS_WITH_WARNINGS` result. The skill reads
`.qb/main-planning.md`, `.qb/sub-planning-index.md`, and every
`.qb/phase-*-plans/*.md`, then produces only `.qb/sub-planning-audit.md`
(in English) and returns a `PASS` / `PASS_WITH_WARNINGS` / `BLOCKED` status. It never edits the
plans themselves.
