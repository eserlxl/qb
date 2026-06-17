---
name: qb-harden
description: Launch the QB autonomous audit -> harden -> report loop over the current repository at a chosen autonomy level.
---

# QB Harden

Start the QB engine's audit -> harden -> report loop on the current workspace by
launching the `qb-runner` skill as a Cursor goal. Keep the loop logic in the synced
engine; this command only supplies the run brief and starts the goal.

## Run brief (supply before starting)

- **Target repository**: the current workspace / working directory.
- **Autonomy level**: `A0` (report-only) by default. Raise to `A1` (propose in
  throwaway isolation), `A2` (apply only verified fixes), or `A3` (prepare a
  reviewable changeset) ONLY when the user explicitly asks. Never escalate
  silently.
- **Policy**: an optional policy JSON; absent or unparseable means the conservative
  default (A0, deny-all writes, no commit/push/PR).
- **Budgets**: max findings / fixes / iterations / wall-time / tokens, taken from
  the policy.

## What the run does

The engine audits the repository read-only, writes graded findings, per-fix
evidence, and an append-only log to the fixed-name `.qb/audit/` store, and emits a
machine-readable report (`report.json`, `report.sarif`) plus a human summary. At A0
nothing is written to the working tree; at A1+ each fix runs in git isolation, is
kept only when its verification command passes, and is otherwise auto-reverted.

For a non-interactive run, the engine is callable directly:
`python3 scripts/qb_headless.py --root . --out .qb/audit`.

## Stop rules

- Default to A0; require explicit user opt-in to raise the autonomy level.
- Never commit, push, open a PR, or deploy. A3 deliver is explicit opt-in only.
- Honor the policy budgets; stop and report when a budget boundary is hit.
- Never write secrets into the store, the report, or any evidence record.
