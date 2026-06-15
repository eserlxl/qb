---
name: qb-plan
description: Start the QB three-step, goal-backed planning workflow (master plan, phase decomposition, audit). Pass `auto` to run non-interactively (for planwright).
---

# QB Plan

Invoke the `qb-planner` skill and run its workflow from the beginning.

**Auto mode.** If the invocation includes the `auto` flag (`/qb-plan auto`), run the
`qb-planner` skill in its **"Auto mode (non-interactive)"** path: do not prompt for anything;
auto-derive the four Step-1 fields from the repository and, if any field cannot be derived,
print `QB_PLAN_AUTO_ERROR: missing required field(s): …` and stop; auto-pass Gate 1 and Gate 2;
skip Step 4; produce and validate `.qb/plan.md`; then print the single final result line
(`QB_PLAN_AUTO_OK:` on success, `QB_PLAN_AUTO_ERROR:` on failure) so an external caller such as
planwright can detect the outcome. Without the flag, run the interactive flow below.

- Collect the four Step-1 fields (`PROJECT_NAME`, `PROJECT_INTENT`, `TARGET_END_STATE`,
  `KNOWN_CONSTRAINTS`) per `repo-aware-intake.md`: on a well-structured repo, auto-derive them
  and ask a single consolidated confirmation; otherwise ask per field, in the user's language.
- Produce `.qb/main-planning.md`, then pause at Gate 1 for feedback and approval.
- On approval, run Step 2 (`qb-subplanner`, goal-backed), pause at Gate 2, then run
  Step 3 (`qb-auditor`, goal-backed). Offer targeted repairs if the audit is
  `PASS_WITH_WARNINGS`.
- As the automatic closing step (Step 5), export the sub-plans to `.qb/plan.md` in planwright's
  plan format and validate it with `validate_planwright_plan.py`. Tell the user the hand-off:
  `cp .qb/plan.md .planwright/plan.md` then run planwright `execute` (or `cycle <N>`).

Write all planning output under `.qb/` in the user's active workspace, in English.
Follow every stop rule defined in the `qb-planner` skill.
