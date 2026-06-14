---
name: cursorqb-autopsy
description: Run only the CursorQB Step 1.5 existing-project autopsy (produces Planner-docs/Autopsy.md).
---

# CursorQB Autopsy

Invoke the `cursorqb-autopsy` skill directly, without re-running Step 1.

Use this when `Planner-docs/Main-Planing.md` already exists and you want an existing-project
autopsy (or a re-run). The skill inspects the repository read-only and writes a 13-section
`Planner-docs/Autopsy.md` technical feedback report that Step 2 (`cursorqb-subplanner`) reads as
supporting feedback. It launches automatically as a Cursor goal via the `define-goal` skill, runs
only for existing/non-empty repositories (and reports a skip for empty ones), and creates or
updates only `Planner-docs/Autopsy.md` - it never changes source code or `Main-Planing.md`.
