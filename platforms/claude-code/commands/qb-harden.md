---
name: qb-harden
description: Launch the QB autonomous audit -> harden -> report loop over the current repository at a chosen autonomy level.
---

# QB Harden

Start the QB engine's audit -> harden -> report loop on the user's active workspace.
Delegate the long autonomous run to the `qb-runner` subagent via the Task tool
(fallback: run the engine in-session under the same goal contract).

## Run brief (supply before starting)

- **Target repository**: the active workspace / current working directory.
- **Autonomy level**: `A0` (report-only) by default. Raise to `A1` (propose in
  throwaway isolation), `A2` (apply only verified fixes), or `A3` (prepare a
  reviewable changeset) ONLY when the user explicitly asks. Never escalate
  silently.
- **Policy**: an optional policy JSON; absent or unparseable means the conservative
  default (A0, deny-all writes, no commit/push/PR).
- **Budgets**: max findings / fixes / iterations / wall-time / tokens, taken from
  the policy.

## What the run does

The engine (synced under `scripts/`) audits the repository read-only with the
analyzer suite, writes graded findings plus per-fix evidence and an append-only log
to the fixed-name `QB-Audit/` store, and emits a machine-readable report
(`report.json`, `report.sarif`) and a human summary. At A0 nothing is written to
the working tree; at A1+ every fix is attempted in git isolation, kept only when
its verification command passes, and otherwise auto-reverted.

For a non-interactive run, the engine is also callable directly:
`python3 <plugin-root>/scripts/qb_headless.py --root . --out QB-Audit`.

## Stop rules

- Default to A0; require explicit user opt-in to raise the autonomy level.
- Never commit, push, open a PR, or deploy. A3 deliver is explicit opt-in only.
- Honor the policy budgets; stop and report when a budget boundary is hit.
- Never write secrets into the store, the report, or any evidence record.
