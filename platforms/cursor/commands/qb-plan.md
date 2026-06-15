---
name: qb-plan
description: Start the QB three-step, goal-backed planning workflow (master plan, phase decomposition, audit).
---

# QB Plan

Invoke the `qb-planner` skill and run its workflow from the beginning.

- Ask the four Step-1 fields (`PROJECT_NAME`, `PROJECT_INTENT`, `TARGET_END_STATE`,
  `KNOWN_CONSTRAINTS`) one at a time, in the language the user is writing in.
- Produce `.qb/main-planning.md`, then pause at Gate 1 for feedback and approval.
- On approval, run Step 2 (`qb-subplanner`, goal-backed), pause at Gate 2, then run
  Step 3 (`qb-auditor`, goal-backed). Offer targeted repairs if the audit is
  `PASS_WITH_WARNINGS`.

Write all planning output under `.qb/` in the user's active workspace, in English.
Follow every stop rule defined in the `qb-planner` skill.
