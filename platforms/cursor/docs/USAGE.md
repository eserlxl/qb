# Usage

CursorQB runs a repo-aware, five-step planning workflow inside the Cursor chat session. Every
long step is launched automatically as a Cursor goal via the `define-goal` skill - there is no
"Follow the Goal" button and no copy/paste handoff. The workflow pauses for your explicit
approval at each gate.

Open the chat in the project you want to plan and run:

```text
/cursorqb-plan
```

## Step 1: Main Plan (interactive, repo-aware)

CursorQB runs a bounded read-only scan of your workspace, then asks four intake questions one
at a time, in your language, each with a repo-derived draft to confirm or edit:

- `PROJECT_NAME`
- `PROJECT_INTENT`
- `TARGET_END_STATE` (product, engineering, operations, security, user value)
- `KNOWN_CONSTRAINTS` (team, infra, budget, timeline, stack, compliance, must-use/must-not-use)

It writes `Planner-docs/Main-Planing.md` and validates it (`--mode step1`).

## Step 1.5: Existing-Project Autopsy (automatic for existing repos)

For an existing or partially built project, CursorQB then runs the `cursorqb-autopsy` skill and
writes `Planner-docs/Autopsy.md` - a 13-section technical feedback report (modules, feature
inventory, placeholders/stubs, technical debt, broken integrations, test/CI gaps, security, and
alignment with the main plan). For empty or nearly empty repositories this step is skipped and
`Autopsy.md` is not created.

## Gate 1

You review the master plan (and the autopsy, when present), give feedback, and approve moving on.
Main-plan feedback is applied to `Main-Planing.md` only; autopsy feedback to `Autopsy.md` only.

## Step 2: Phase Sub-Plans (goal-backed)

The `cursorqb-subplanner` skill decomposes every phase into detailed sub-plans under
`Planner-docs/Faz-<n>-Plans/`, plus a full-path `Planner-docs/Sub-Planing-Index.md`. When
`Autopsy.md` exists, it is read as supporting feedback (not a replacement for the main plan). It
runs until every phase is covered, then validates all files (`--mode step2 --strict`).

## Gate 2

CursorQB asks for explicit approval before auditing.

## Step 3: Sub-Plan QA Audit (goal-backed)

The `cursorqb-auditor` skill runs the validator first, audits the sub-plans against the master
plan, and writes `Planner-docs/Sub-Planing-Audit.md` with a status of `PASS`,
`PASS_WITH_WARNINGS`, or `BLOCKED`. It never edits the plans themselves. Findings are listed as
`- AUDIT-FIX-NN | PX | <title>` single-line headers.

## Step 4: Gated Implementation (goal-backed)

After the audit, CursorQB runs the Step-4 gate (`--mode step4`). Step 4 is offered only when the
audit is not `BLOCKED` and has no P0/P1 findings. If approved, the `cursorqb-implementer` skill
implements one bounded, reversible slice from a single `READY` sub-plan: it determines the
validation command first, makes a minimal change, runs focused tests plus the relevant `make`
target, and verifies before claiming done. It never commits, pushes, opens a PR, or mutates
external systems unless you explicitly ask. Re-run `/cursorqb-implement` for each subsequent slice.

## Direct step invocation

- `/cursorqb-autopsy` - run only the autopsy on an existing `Main-Planing.md`.
- `/cursorqb-audit` - re-run only the audit (for example after repairs).
- `/cursorqb-implement` - run only the gated implementation for one `READY` sub-plan.

## Validator output

The validator prints deterministic summary lines, for example:

```text
planner_docs_validation=passed
mode=step2
phase_folder_count=9
subplan_count=35
autopsy_exists=true
warning_count=0
error_count=0
```

It exits nonzero on structural failures. With `--strict`, repeated or generic section warnings
become failures. Secret scanning uses length-bounded token patterns so normal filenames such as
`task-spec.yaml` are not flagged. In `--mode step4`, P0/P1 audit findings block implementation
readiness while P2/P3 findings are warnings. When `Planner-docs/Autopsy.md` exists, the validator
checks its required heading order during Step 2/3 validation.

## Output location

All planning artifacts land under `Planner-docs/` in your active workspace - never in the plugin
directory.
