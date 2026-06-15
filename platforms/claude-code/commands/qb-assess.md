---
name: qb-assess
description: Run only the QB Step 1.5 existing-project assessment (produces .qb/assessment.md).
---

# QB Assessment

Invoke the `qb-assess` skill directly, without re-running Step 1.

Use this when `.qb/main-planning.md` already exists and you want an existing-project
assessment (or a re-run). The skill inspects the repository read-only and writes a 13-section
`.qb/assessment.md` technical feedback report that Step 2 (`qb-subplanner`) reads as
supporting feedback. Delegate this step to the matching `qb-assess` subagent via the Task
tool (fallback: run the `qb-assess` skill in-session under the same goal contract). It runs
only for existing/non-empty repositories (and reports a skip for empty ones), and creates or
updates only `.qb/assessment.md` - it never changes source code or `main-planning.md`.
