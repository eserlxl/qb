---
name: qb-implement
description: Run only the gated QB Step 4 implementation for one READY sub-plan slice.
---

# QB Implement

Invoke the `qb-implementer` skill directly, without re-running Steps 1-3.

Use this after the Step 3 audit to implement one bounded, reversible slice from the audited
plan. The skill first runs the Step-4 gate
(`python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step4`): if the audit is
`BLOCKED` or has any P0/P1 finding, it stops and recommends repair instead of implementing. When the
gate passes, delegate this step to the matching `qb-implementer` subagent via the Task tool
(fallback: run the `qb-implementer` skill in-session under the same goal contract), selects one
`READY` / `READY_WITH_WARNINGS` sub-plan, determines the validation command first, makes a minimal
reversible change, and verifies before claiming done. It changes source code only in this run and
never commits, pushes, opens a PR, or mutates external systems unless you explicitly ask.
