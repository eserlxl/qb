---
name: qb-plan
description: Start the QB three-step planning workflow (master plan, phase decomposition, audit).
---

# QB Plan

Invoke the `qb-planner` skill and run its workflow from the beginning.

- Ask the four Step-1 fields (`PROJECT_NAME`, `PROJECT_INTENT`, `TARGET_END_STATE`,
  `KNOWN_CONSTRAINTS`) one at a time, in the language the user is writing in.
- Produce `.qb/main-planning.md`, then pause at Gate 1 for feedback and approval.
- On approval, run Step 2 by delegating to the `qb-subplanner` subagent via the Task tool
  (fallback: run the `qb-subplanner` skill in-session under the same goal contract), pause at
  Gate 2, then run Step 3 by delegating to the `qb-auditor` subagent via the Task tool
  (fallback: run the `qb-auditor` skill in-session). Offer targeted repairs if the audit is
  `PASS_WITH_WARNINGS`.

Write all planning output under `.qb/` in the user's active workspace, in English.
Follow every stop rule defined in the `qb-planner` skill.
