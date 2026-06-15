---
name: qb-autopsy
description: Run only the QB Step 1.5 existing-project autopsy (produces Planner-docs/Autopsy.md).
---

# QB Autopsy

Invoke the `qb-autopsy` skill directly, without re-running Step 1.

Use this when `Planner-docs/Main-Planning.md` already exists and you want an existing-project
autopsy (or a re-run). The skill inspects the repository read-only and writes a 13-section
`Planner-docs/Autopsy.md` technical feedback report that Step 2 (`qb-subplanner`) reads as
supporting feedback. Delegate this step to the matching `qb-autopsy` subagent via the Task
tool (fallback: run the `qb-autopsy` skill in-session under the same goal contract). It runs
only for existing/non-empty repositories (and reports a skip for empty ones), and creates or
updates only `Planner-docs/Autopsy.md` - it never changes source code or `Main-Planning.md`.
