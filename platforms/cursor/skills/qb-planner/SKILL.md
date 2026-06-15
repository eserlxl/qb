---
name: qb-planner
description: Guided five-step (1, 1.5, 2, 3, 4), goal-backed project planning orchestrator with a repo-aware intake. Use when the user runs /qb-plan or asks QB to plan a project end to end - master plan, existing-project assessment, phase decomposition, coverage audit, then optional implementation. Runs a repo-aware Step 1 intake, produces .qb/main-planning.md, runs a Step 1.5 assessment (qb-assess) for existing projects, then gates into phase decomposition (qb-subplanner), a coverage/quality audit (qb-auditor), and a gated implementation step (qb-implementer) - launched automatically as Cursor goals via define-goal. Validates each step with the bundled validator.
metadata:
  version: "0.10.0"
---

# QB Planner (orchestrator)

Drive the QB planning workflow inside the current chat session, with an explicit
user-approval gate between every step. This skill owns the conversation, the repo-aware
Step-1 intake, and the gates; it delegates the long autonomous steps to the goal-backed
`qb-assess`, `qb-subplanner`, `qb-auditor`, and `qb-implementer` skills.

```text
Step 1   repo-aware intake -> First-Planner -> main-planning.md       (interactive)   [validator step1]
Step 1.5 qb-assess  -> assessment.md (existing projects only)    (goal-backed)    [validator step2 assessment]
 Gate 1 feedback (main-planning + Assessment) + approve
Step 2   qb-subplanner -> phase-*-plans/ + sub-planning-index.md  (goal-backed)    [validator step2]
 Gate 2 audit approval
Step 3   qb-auditor     -> sub-planning-audit.md                (goal-backed)    [validator step3]
 Repair PASS_WITH_WARNINGS -> targeted fixes -> re-audit
Step 3.5 Export-Planner -> .qb/plan.md (planwright format)      (automatic)       [validator plan]
 Step 4 gate: validator step4 (audit not BLOCKED, no P0/P1)
Step 4   qb-implementer -> one reversible code slice           (goal-backed, gated)
```

## Execution model and non-negotiable rules

- **In-session, zero-setup.** No API key, no external process. You read the bundled planner
  prompt, fill it in your own context, and follow its instructions yourself.
- **Reliability references + validator.** Resolve the plugin root by walking up from this skill's
  directory to the folder containing `.cursor-plugin/plugin.json`. Read `references/workflow-quality.md`
  before starting and follow it (read-before-counting, concise output, untracked-.qb git
  handling, secret/token discipline). After each step, run the bundled validator
  `python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode stepN [--strict]`; if
  `python3` or the script is unavailable, fall back to the equivalent manual checks and say so.
- **Goal-backed steps use Cursor `define-goal`, automatically.** Steps 1.5, 2, 3, and 4 are launched as
  Cursor goals via the `define-goal` skill, in-session and hands-free. There is no "Follow the Goal"
  button and no copy/paste handoff. If the goal tool (`create_goal`) is unavailable, the step still
  runs under its own in-context goal contract.
- **Bundled prompt location.** The Step-1 prompt lives next to this skill at `planners/first-planner.md`.
  Read it from there. Never inline its full text into chat.
- **Output location is the user's workspace, not the plugin.** Write every planning artifact
  (`.qb/...`) into the user's **active workspace / current working directory**. Never write
  planning output into this plugin's directory.
- **Never mutate the templates.** Do placeholder substitution in memory only. The bundled prompts
  (`planners/first-planner.md` and the specs inside `qb-assess` / `qb-subplanner` /
  `qb-auditor` / `qb-implementer`) must stay byte-for-byte pristine for the next run.
- **Language.** Ask every question in the **language the user is writing in**. Produce all planning
  documents in **English** (the bundled prompts enforce English output).
- **Honor each prompt's guardrails.** Step 1 may only create/update `main-planning.md`; Step 1.5 may only
  create/update `assessment.md`; Step 2 may only change files under `.qb/`; Step 3 may only
  create/update `sub-planning-audit.md`; only Step 4 may change source code, and only after its gate
  passes and the user approves; the Step 3.5 export may only create/update `.qb/plan.md`. Never write
  secrets, tokens, or credentials. Never auto-commit, push, or open PRs during planning.
- **Always wait for explicit approval at each gate** before continuing (except in auto mode; see below).

## Auto mode (non-interactive)

When `qb-plan` is invoked with the `auto` flag (`/qb-plan auto`), run the entire workflow
**non-interactively** so an external caller (for example planwright) can invoke it and detect a
clean success or failure from the output. Auto mode **overrides** the interactive behavior of
Step 0, the Step-1 intake, Gate 1, Gate 2, and the repair loop, and it **disables Step 4**.

1. **Never prompt.** Do not ask the four intake questions, do not request Gate-1 feedback or
   Gate-2 approval, and do not offer interactive repairs. Emit only progress and the final
   result line. There is no user message to detect a language from, so produce everything in English.
2. **Intake is auto-derive only - fail closed.** Run the repo-aware Pre-Intake Scan from
   `references/repo-aware-intake.md` and derive all four fields (`PROJECT_NAME`, `PROJECT_INTENT`,
   `TARGET_END_STATE`, `KNOWN_CONSTRAINTS`) from repository evidence. If any field cannot be
   derived with sufficient evidence, do **not** fall back to a prompt - print a single error line
   and stop immediately, creating no `.qb/` artifacts:
   `QB_PLAN_AUTO_ERROR: missing required field(s): <comma-separated names> (insufficient repo evidence)`
3. **Auto-pass the gates.** Treat Gate 1 and Gate 2 as approved and run Step 1 -> 1.5 -> 2 -> 3
   straight through. If the audit is `PASS_WITH_WARNINGS` with only P2/P3 findings, continue; do
   not run the interactive repair loop. Record a `BLOCKED` or P0/P1 audit status in the summary
   but still produce the export (the export runs regardless of audit status).
4. **Planning-only - never touch source.** Auto mode writes only under `.qb/`. It runs the
   Step 3.5 export to produce and validate `.qb/plan.md`, then stops. It never runs Step 4, never
   modifies source code, and never commits, pushes, or opens PRs - regardless of audit status.
5. **Deterministic result line.** Print exactly one machine-detectable result line and nothing
   after it. Success (only after `.qb/plan.md` exists and passed `validate_planwright_plan.py`):
   `QB_PLAN_AUTO_OK: .qb/plan.md generated (<item-count> items); audit=<PASS|PASS_WITH_WARNINGS|BLOCKED>`
   Any blocking error (missing field, an unresolved validator failure, or no sub-plans to
   export): `QB_PLAN_AUTO_ERROR: <reason>`. Never print the success line unless the export validated.

Without the `auto` flag, ignore this section and follow the interactive Step 0 -> gates flow below.

## Step 0 - detect and brief

1. Detect the user's language from the conversation and use it for all questions and prose.
2. Read `references/workflow-quality.md` (resolve plugin root) and follow its reliability practices throughout.
3. In 2-3 sentences, explain the steps and that you will pause for approval at each gate.
4. Check the user's workspace for an existing `.qb/main-planning.md`. If it exists, say you will
   reconcile and update it rather than blindly duplicate (First-Planner handles reconciliation).

## Step 1 - repo-aware intake (interactive)

Follow `references/repo-aware-intake.md` (resolve plugin root). Before asking, run a bounded read-only
scan of the user's workspace. Then follow its **Well-Structured Fast Path**: on a well-structured repo,
auto-derive all four fields and present a single consolidated confirmation; otherwise (or for any
weak-evidence field) ask that field per turn, in the user's language, as a plain-text question (no
multiple-choice), offering your repo-derived draft to confirm or edit. Mark clearly when a value is
inferred.

1. `PROJECT_NAME`
2. `PROJECT_INTENT` - what the project is and what it should become.
3. `TARGET_END_STATE` - "done" across product, engineering, operations, security, and user value.
4. `KNOWN_CONSTRAINTS` - team, infrastructure, budget, timeline, stack, compliance, must-use/must-not-use.

User-confirmed values are the source of truth; repo-inferred notes are supporting context only. After
all four are confirmed, echo a compact summary, then continue (Gate 1 comes after the plan is generated).

## Step 1 - run First-Planner

1. Read `planners/first-planner.md` (relative to this skill).
2. In your working context, replace the placeholder block under each label with the collected value
   (do not edit the file on disk):
   - `<WRITE_PROJECT_NAME_HERE>` -> `PROJECT_NAME`
   - `<WRITE_THE_PROJECT_PURPOSE_HERE...>` -> `PROJECT_INTENT`
   - `<WRITE_THE_DESIRED_FINAL_STATE_HERE...>` -> `TARGET_END_STATE`
   - `<WRITE_CONSTRAINTS_HERE...>` -> `KNOWN_CONSTRAINTS`
3. Follow the filled-in prompt end to end, acting in the role it describes. Run only the read-only
   repository inspection it lists. Create or update `.qb/main-planning.md` in the user's
   workspace, in English, with exactly the required top-level sections.
4. Run the prompt's own post-write validation (read it back, confirm sections, English, no secrets).
5. Run the bundled validator: `python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step1 --strict`
   (fallback: manual checks). Fix any structural errors before Step 1.5 / Gate 1.

## Step 1.5 - existing-project assessment (auto for existing repos)

After Step 1, decide whether Step 1.5 applies:

- **Run** when the workspace is an existing or partially built project: it is not empty and has
  meaningful evidence (README, manifests, source/service/package dirs, tests, docs, configs, or CI).
- **Skip** for new or nearly empty repositories; do not create `.qb/assessment.md`.

When it applies, launch Step 1.5 via the define-goal procedure below (Canonical Step-1.5 goal text) and
follow the **`qb-assess`** skill. It writes only `.qb/assessment.md` (a 13-section technical
feedback report) which Step 2 uses as supporting feedback. No separate approval is needed before Step 1.5;
the user reviews both `main-planning.md` and `assessment.md` together at Gate 1.

## Goal-backed step launch via define-goal

Steps 1.5, 2, 3, and 4 are launched as Cursor goals - automatically and in-session. There is no "Follow
the Goal" button and no copy/paste handoff. When a step starts (Step 1.5) or a gate is approved, run this
procedure before handing off to the step skill:

1. Follow the Cursor `define-goal` skill: call `get_goal`, and if no matching active goal exists, call
   `create_goal` with the step's objective. Use the goal contract declared in the step's own skill
   (`qb-assess` for Step 1.5, `qb-subplanner` for Step 2, `qb-auditor` for Step 3,
   `qb-implementer` for Step 4) as the objective, including its success evidence and scope bounds.
   The user has explicitly opted into goal-backed execution for these steps, which satisfies define-goal's
   "only when the user asked" gate.
2. For transparency, show the user the one-line goal you just set, in the form `/define-goal <canonical text>`
   (in the user's language), using the canonical text below.
3. Immediately follow the step's skill in this session and run it to completion.
4. Fallback: if no goal tool (`create_goal`) is available this session, skip goal registration and run
   the step under its in-context goal contract - behavior is identical.

Canonical goal text, referencing the bundled spec by its real co-located path:

- Step 1.5 (`qb-assess`, spec `assessment-planner.md`):
  > Run Step 1.5 Assessment per the qb-assess skill's assessment-planner.md spec. Read .qb/main-planning.md and inspect the current repository read-only; create or update only .qb/assessment.md (a 14-heading technical feedback report). Skip for an empty or nearly empty repository and do not create assessment.md. Do not modify source code or main-planning.md.
- Step 2 (`qb-subplanner`, spec `second-planner.md`):
  > Run Step 2 per the qb-subplanner skill's second-planner.md spec. Read all main phases in .qb/main-planning.md; if .qb/assessment.md exists, read it fully as supporting feedback and account for it in the sub-plans. For each phase, create phase-<n>-plans folders under .qb and phase-<n>.<m>-*.md detailed sub-plan files. Do not stop until all phases are covered. Change only files under .qb.
- Step 3 (`qb-auditor`, spec `third-planner.md`):
  > Run Step 3 per the qb-auditor skill's third-planner.md spec. Audit .qb/main-planning.md, sub-planning-index.md, and all phase-*-plans/*.md files; analyze main-phase coverage, file naming, ordering, required section structure, index consistency, content quality, scope drift, readiness realism, security/governance, and Step 4 readiness. Do not fix any plan file; produce only .qb/sub-planning-audit.md. Do not stop until all phases and sub-plans are reviewed.

## Gate 1 - feedback, then approve Step 2

1. Present a concise summary of `main-planning.md` (current-state conclusion, number of high-level phases,
   most important next action) and, if Step 1.5 ran, the top `assessment.md` signals.
2. Ask the user (in their language) whether they have any feedback on the master plan and (if present) the
   assessment. Apply main-plan feedback to `main-planning.md` only, and assessment feedback to `assessment.md` only
   (via the `qb-assess` skill); re-validate (`--mode step1`, and `--mode step2` for the assessment
   heading check), then re-summarize. Repeat until the user is satisfied.
3. Use `AskQuestion` to confirm proceeding to Step 2. Describe Step 2 plainly: "Read every main phase in
   `.qb/main-planning.md` (and `assessment.md` when present) and, for each phase, create
   `.qb/phase-<n>-plans/` folders and `phase-<n>.<m>-*.md` detailed sub-plan files. Do not stop until
   all phases are covered. Only change files under `.qb/`."
   - Decline -> stop gracefully; the user can resume with `/qb-plan` or the `qb-subplanner` skill.
   - Approve -> launch Step 2 via the **define-goal procedure above** (Canonical Step-2 goal text), then
     follow the **`qb-subplanner`** skill to completion across all phases.

## Gate 2 - approve Step 3 (audit)

After `qb-subplanner` reports completion, present this confirmation, then ask with `AskQuestion`
(Yes / No):

> In the third step, we will now audit whether the sub-plans produced by Step 2 are faithful to the master plan, complete, ordered, actionable, and meet the quality bar. Do you approve?

- Decline -> stop gracefully; the user can run the audit later via the `qb-auditor` skill or `/qb-audit`.
- Approve -> launch Step 3 via the **define-goal procedure above** (Canonical Step-3 goal text), then
  follow the **`qb-auditor`** skill until it produces `.qb/sub-planning-audit.md` and returns a status.

## After the audit - status, repair loop, and Step 4 gate

Read the audit status from `sub-planning-audit.md` (`## 1. Audit Summary`, `## 15. Audit Result`), then
run the Step-4 gate validator:
`python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step4`
(fallback: read the audit `## 12. Step 4 Readiness Assessment` table and `## 13. Prioritized Fix List` manually).

- **Gate passes (PASS, or PASS_WITH_WARNINGS with no P0/P1)** -> summarize; surface any P2/P3 items from
  `## 13. Prioritized Fix List` to keep visible. Use `AskQuestion` to offer Step 4. If approved, launch
  Step 4 via the define-goal procedure and follow the **`qb-implementer`** skill for one READY sub-plan slice.
- **Gate fails on P0/P1** (`step4_blocked_by_high_severity_findings`) -> do not offer Step 4. Show the
  prioritized fix list from `## 13`; use `AskQuestion` to offer applying the targeted repairs to only the
  named sub-plan files (within `.qb/`), then re-run the `qb-auditor` skill. Repeat until the
  Step-4 gate passes or the user stops.
- **Gate fails on BLOCKED** -> report the blocker and the minimal next action from the audit; do not
  repair speculatively or start Step 4.

## Step 3.5 - export to planwright (automatic, after the audit)

After the audit and before the optional Step 4 slice, automatically produce a flat, execution-ready
planwright plan from the sub-plans so the QB plan can be handed to planwright's
`execute` / `cycle` without re-planning. This runs on **every** planning run that produced
sub-plans; it needs no gate or approval (it only writes `.qb/plan.md`).

1. Skip only when Step 2 produced no sub-plans (no `.qb/phase-*-plans/`): say there was nothing
   to export. Otherwise run regardless of audit status (note any unresolved blocker in the summary).
2. Read `planners/export-planner.md` (relative to this skill) and follow it end to end. Read every
   `.qb/phase-*-plans/phase-<n>.<m>-*.md` and emit one planwright item per `## 7. Planned Work
   Breakdown` entry, across all phases, into `.qb/plan.md` in the exact 8-field item format.
3. Run the bundled validator:
   `python3 <plugin-root>/scripts/validate_planwright_plan.py --root . --strict`
   (fallback: the manual checks the spec lists). Fix every flagged item and re-run until it passes.
4. Tell the user the hand-off in their language: to run the plan with planwright, copy it into place
   and execute, e.g. `cp .qb/plan.md .planwright/plan.md` then run planwright `execute` (or `cycle <N>`).
   QB does not write to `.planwright/` or invoke planwright itself.

## Stop rules

- During planning (Steps 1-3) and the Step 3.5 export, do not modify any file outside `.qb/`, and never
  modify the bundled template prompts. Only Step 4 may change source code, after its gate passes and the user approves.
- Never write secrets, tokens, credentials, or private endpoints into any file.
- Never auto-commit, push, merge, or open pull requests unless the user explicitly asks in a Step 4 run.
- Always pause for explicit user approval at each gate.
- Ask in the user's language; write planning documents in English.

## Output

On a successful planning run the user's workspace contains, under `.qb/`: `main-planning.md`,
`assessment.md` (for existing projects), one `phase-<n>-plans/` folder per phase with `phase-<n>.<m>-*.md`
sub-plans, `sub-planning-index.md`, `sub-planning-audit.md`, and `plan.md` (the Step 3.5 planwright-format
export). If Step 4 ran, also one reversible code slice with a passing validation command. Close with a
short summary, the planwright hand-off command for `.qb/plan.md`, and the single most important
recommended next action.
