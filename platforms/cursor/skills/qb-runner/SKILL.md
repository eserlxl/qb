---
name: qb-runner
description: Run the QB audit -> harden -> report loop over a repository at a given autonomy level, launched as a Cursor goal by the qb-harden command. Audits read-only, applies only verified fixes in git isolation at A2+, and writes the QB-Audit/ store and reports. Never commits, pushes, or opens PRs.
metadata:
  version: "0.14.0"
---

# QB Runner (Cursor goal)

Run the QB engine's audit -> harden -> report loop as a goal-backed run. The
`qb-harden` command launches you with a run brief: the target repository, the
autonomy level, the policy, and the budgets. Keep the loop logic in the synced
engine; you are a thin launcher.

## Goal contract

- **Objective**: produce a graded, evidence-backed audit and, at the selected
  autonomy level, apply only verified, reversible fixes.
- **Success evidence**: the `QB-Audit/` store and the `report.json` /
  `report.sarif` / `summary.txt` outputs exist; every kept fix has a passing
  verification result and a recorded rollback handle; the working tree is unchanged
  at A0/A1.
- **Scope bounds**: one repository, the declared autonomy level, no commit / push /
  PR / deploy, no secrets written.
- **Stop condition**: stop on completion, on a policy or budget boundary (report
  it), or on a blocker that needs the user.

## How to run

Prefer the engine's own entry point for a deterministic run:

```bash
python3 scripts/qb_headless.py --root . --out QB-Audit
```

The exit code is the contract: `0` clean, `1` findings present, `2` policy/budget
boundary, `3` internal error. The autonomy level defaults to `A0` (report-only);
raising it is explicit per the run brief. At A2+, fixes are attempted in a
dedicated git worktree, verified before being kept, and auto-reverted on failure.

Report back the finding counts by severity, the kept/reverted fix counts, the run
stop reason, and the path to the written report. Do not claim success without the
report present.
