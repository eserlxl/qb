---
name: cursorqb-implement
description: Run only the gated CursorQB Step 4 implementation for one READY sub-plan slice.
---

# CursorQB Implement

Invoke the `cursorqb-implementer` skill directly, without re-running Steps 1-3.

Use this after the Step 3 audit to implement one bounded, reversible slice from the audited
plan. The skill first runs the Step-4 gate
(`python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step4`): if the audit is
`BLOCKED` or has any P0/P1 finding, it stops and recommends repair instead of implementing. When the
gate passes, it launches automatically as a Cursor goal via the `define-goal` skill, selects one
`READY` / `READY_WITH_WARNINGS` sub-plan, determines the validation command first, makes a minimal
reversible change, and verifies before claiming done. It changes source code only in this run and
never commits, pushes, opens a PR, or mutates external systems unless you explicitly ask.
