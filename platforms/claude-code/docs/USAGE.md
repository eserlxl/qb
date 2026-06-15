# Usage

QB runs a repo-aware, five-step planning workflow inside the Claude Code
chat session. Each long autonomous step is delegated to a matching subagent via
the Task tool, with that step's goal contract (objective, success evidence,
scope bounds, stop condition) passed as the subagent's task brief — there is no
copy/paste handoff. If subagents or the Task tool are unavailable in a session,
QB falls back to running the step's skill in-session under the same
in-context goal contract; the behavior is identical. The workflow pauses for
your explicit approval at each gate.

Open the chat in the project you want to plan and run:

```text
/qb-plan
```

## Step 1: Main Plan (interactive, repo-aware)

QB runs a bounded read-only scan of your workspace, then asks four intake
questions one at a time, in your language, each with a repo-derived draft to
confirm or edit:

- `PROJECT_NAME`
- `PROJECT_INTENT`
- `TARGET_END_STATE` (product, engineering, operations, security, user value)
- `KNOWN_CONSTRAINTS` (team, infra, budget, timeline, stack, compliance, must-use/must-not-use)

It writes `.qb/main-planning.md` and validates it (`--mode step1`).

## Step 1.5: Existing-Project Assessment (automatic for existing repos)

For an existing or partially built project, QB then delegates to the
`qb-assess` subagent (or runs the `qb-assess` skill in-session as
the fallback) and writes `.qb/assessment.md` - a 13-section technical
feedback report (modules, feature inventory, placeholders/stubs, technical debt,
broken integrations, test/CI gaps, security, and alignment with the main plan).
For empty or nearly empty repositories this step is skipped and `assessment.md` is
not created.

## Gate 1

You review the master plan (and the assessment, when present), give feedback, and
approve moving on. Main-plan feedback is applied to `main-planning.md` only;
assessment feedback to `assessment.md` only.

## Step 2: Phase Sub-Plans (subagent-delegated)

The `qb-subplanner` subagent decomposes every phase into detailed
sub-plans under `.qb/phase-<n>-plans/`, plus a full-path
`.qb/sub-planning-index.md`. When `assessment.md` exists, it is read as
supporting feedback (not a replacement for the main plan). It runs until every
phase is covered, then validates all files (`--mode step2 --strict`).

## Gate 2

QB asks for explicit approval before auditing.

## Step 3: Sub-Plan QA Audit (subagent-delegated)

The `qb-auditor` subagent runs the validator first, audits the sub-plans
against the master plan, and writes `.qb/sub-planning-audit.md` with a
status of `PASS`, `PASS_WITH_WARNINGS`, or `BLOCKED`. It never edits the plans
themselves. Findings are listed as `- AUDIT-FIX-NN | PX | <title>` single-line
headers.

## Step 4: Gated Implementation (subagent-delegated)

After the audit, QB runs the Step-4 gate (`--mode step4`). Step 4 is
offered only when the audit is not `BLOCKED` and has no P0/P1 findings. If
approved, the `qb-implementer` subagent implements one bounded, reversible
slice from a single `READY` sub-plan: it determines the validation command
first, makes a minimal change, runs focused tests plus the relevant `make`
target, and verifies before claiming done. It never commits, pushes, opens a PR,
or mutates external systems unless you explicitly ask. Re-run
`/qb-implement` for each subsequent slice.

## Step 5: Export to planwright (automatic)

After the audit, QB automatically projects the sub-plans into a flat,
execution-ready `.qb/plan.md` in [planwright](https://github.com/eserlxl/planwright)'s
8-field checkbox item format — one item per "Planned Work Breakdown" entry, across
all phases. It writes only `.qb/plan.md` (no source changes, no gate) and validates
it with `validate_planwright_plan.py`, which mirrors the machine-checkable subset of
planwright's plan linter so the file is accepted by planwright on hand-off. To run the
plan with planwright: `cp .qb/plan.md .planwright/plan.md`, then run planwright
`execute` (or `cycle <N>`). QB never writes to `.planwright/` or invokes planwright.

## Subagent delegation and the goal contract

For each long autonomous step (1.5, 2, 3, and 4), the orchestrator delegates to
the matching subagent via the Task tool — `qb-assess`,
`qb-subplanner`, `qb-auditor`, and `qb-implementer` — passing
that step's goal contract as the task brief:

- **Objective** — what the step must produce.
- **Success evidence** — what proves the step is done.
- **Scope bounds** — what the step may and may not touch.
- **Stop condition** — when to hand control back for the next gate.

The brief also includes the absolute path to that step's bundled spec file so
the subagent works from the exact prompt. If subagents or the Task tool are
unavailable this session, the orchestrator runs the same skill in-session under
the identical in-context goal contract; the product stays in-session,
zero-setup, and gated at every step.

## Direct step invocation

- `/qb-assess` - run only the assessment on an existing `main-planning.md`.
- `/qb-audit` - re-run only the audit (for example after repairs).
- `/qb-implement` - run only the gated implementation for one `READY` sub-plan.

The Step 5 planwright export has no dedicated command (it runs automatically at the end
of every `/qb-plan` run). To refresh `.qb/plan.md` on its own, re-run `/qb-plan`, or ask
QB to run only the Step 5 export against the existing `.qb/` sub-plans.

## Validator output

The validator prints deterministic summary lines, for example:

```text
planner_docs_validation=passed
mode=step2
phase_folder_count=9
subplan_count=35
assessment_exists=true
warning_count=0
error_count=0
```

It exits nonzero on structural failures. With `--strict`, repeated or generic
section warnings become failures. Secret scanning uses length-bounded token
patterns so normal filenames such as `task-spec.yaml` are not flagged. In
`--mode step4`, P0/P1 audit findings block implementation readiness while P2/P3
findings are warnings. When `.qb/assessment.md` exists, the validator
checks its required heading order during Step 2/3 validation.

## Output location

All planning artifacts land under `.qb/` in your active workspace -
never in the plugin directory:

```text
.qb/
├── main-planning.md         # the master plan                          (Step 1)
├── assessment.md              # repo health report for existing projects (Step 1.5)
├── sub-planning-index.md    # map of every sub-plan + coverage check   (Step 2)
├── sub-planning-audit.md    # quality/coverage audit + PASS/BLOCKED    (Step 3)
├── plan.md                  # flat planwright-format export            (Step 5)
└── phase-1-plans/            # detailed sub-plans, one folder per phase
    ├── phase-1.1-...md
    └── phase-1.2-...md
```
