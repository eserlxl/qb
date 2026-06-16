---
name: qb-planner
description: Guided five-step (1, 1.5, 2, 3, 4), delegated project planning orchestrator with a repo-aware intake. Use when the user runs /qb-plan or asks QB to plan a project end to end - master plan, existing-project assessment, phase decomposition, coverage audit, then optional implementation. Runs a repo-aware Step 1 intake, produces .qb/main-planning.md, runs a Step 1.5 assessment (qb-assess) for existing projects, then gates into phase decomposition (qb-subplanner), a coverage/quality audit (qb-auditor), and a gated implementation step (qb-implementer) - each long autonomous step delegated automatically to a matching subagent via the Task tool. Validates each step with the bundled validator.
metadata:
  version: "0.10.0"
---

# QB Planner (orchestrator)

Drive the QB planning workflow inside the current chat session, with an explicit
user-approval gate between every step. This skill owns the conversation, the repo-aware
Step-1 intake, and the gates; it delegates the long autonomous steps to the
`qb-assess`, `qb-subplanner`, `qb-auditor`, and `qb-implementer` subagents
via the Task tool.

```text
Step 1   repo-aware intake -> First-Planner -> main-planning.md       (interactive)   [validator step1]
Step 1.5 qb-assess  -> assessment.md (existing projects only)    (delegated)      [validator step2 assessment]
 Gate 1 feedback (main-planning + Assessment) + approve
Step 2   qb-subplanner -> phase-*-plans/ + sub-planning-index.md  (delegated)      [validator step2]
 Gate 2 audit approval
Step 3   qb-auditor     -> sub-planning-audit.md                (delegated)      [validator step3]
 Repair PASS_WITH_WARNINGS -> targeted fixes -> re-audit
Step 3.5 Export-Planner -> .qb/plan.md (planwright format)      (automatic)       [validator plan]
 Step 4 gate: validator step4 (audit not BLOCKED, no P0/P1)
Step 4   qb-implementer -> one reversible code slice           (delegated, gated)
```

## Execution model and non-negotiable rules

- **In-session, zero-setup.** No API key, no external process. You read the bundled planner
  prompt, fill it in your own context, and follow its instructions yourself.
- **Reliability references + validator.** Resolve the plugin root by walking up from this skill's
  directory to the folder containing `.claude-plugin/plugin.json`. Read `references/workflow-quality.md`
  before starting and follow it (read-before-counting, concise output, untracked-.qb git
  handling, secret/token discipline). After each step, run the bundled validator
  `python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode stepN [--strict]`; if
  `python3` or the script is unavailable, fall back to the equivalent manual checks and say so.
- **Delegated steps use the Task tool, automatically — and delegation is what makes them
  independent.** Steps 1.5, 2, 3, and 4 are delegated to the matching `qb-*` subagent via the Task
  tool, in-session and hands-free. There is no copy/paste handoff. **Delegation is mandatory whenever
  the Task tool is available**: it gives each step a *fresh, independent actor* that did **not** author
  the upstream artifact — which is the entire point of the audit (Step 3) and the assessment
  (Step 1.5). Only when the Task tool or the `qb-*` subagents are **genuinely unavailable** may a step
  run **in-session** as a *degraded* fallback, and that is **not** equivalent: a step the orchestrator
  runs in-session inspects the very context that produced the plan, so it loses independence and tends
  to rubber-stamp the orchestrator's own framing (a self-audit is not an audit). When the fallback is
  used, **disclose it** — emit one line `note: <step> ran in-session (no independent subagent
  available) — independence reduced` — so the result is never mistaken for an independently-verified
  one.
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
3. **Auto-pass the gates — but DELEGATE every step independently.** Treat Gate 1 and Gate 2 as
   approved and run Step 1 -> 1.5 -> 2 -> 3 straight through. **Auto mode is the external-consumer
   path (planwright and other callers), so the delegated steps — above all Step 3, the audit — MUST
   run via the independent `qb-*` subagents (the Task tool), never as an in-session self-check.** A
   caller that trusts `QB_PLAN_AUTO_OK` is trusting that the audit was *independent*; an in-session
   audit run by the same actor that produced the plan rubber-stamps its own framing, and is exactly
   the failure this mandate prevents (it is how a real coverage gap can be reported as "0 items").
   Use the in-session fallback **only** if the Task tool is genuinely unavailable — and then you
   **must** emit, before the result line, the disclosure
   `QB_PLAN_AUTO_WARN: in-session fallback — audit not independently delegated` so the consumer can
   downgrade its trust in the result. If the audit is `PASS_WITH_WARNINGS` with only P2/P3 findings,
   continue; do not run the interactive repair loop. Record a `BLOCKED` or P0/P1 audit status in the
   summary but still produce the export (the export runs regardless of audit status).
4. **Planning-only - never touch source.** Auto mode writes only under `.qb/` (plus the one-line
   Step 0 `.gitignore` guard that keeps `.qb/` uncommitted). It runs the
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
5. Ensure `.qb/` is git-ignored before creating any `.qb/` artifact: inside a git working tree,
   if `git check-ignore -q .qb/` fails, append a `.qb/` line to the workspace `.gitignore`
   (creating it if absent) without touching the user's other entries. Skip outside a git repo.
   See `references/workflow-quality.md` ("Ignore the `.qb/` Planning Directory") for the exact,
   idempotent commands. Note this one-line change in your Gate 1 summary.

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

When it applies, launch Step 1.5 via the delegation procedure below (Canonical Step-1.5 subagent brief) and
follow the **`qb-assess`** subagent/skill. It writes only `.qb/assessment.md` (a 13-section technical
feedback report) which Step 2 uses as supporting feedback. No separate approval is needed before Step 1.5;
the user reviews both `main-planning.md` and `assessment.md` together at Gate 1.

## Delegated step launch via the Task tool

Steps 1.5, 2, 3, and 4 are delegated to the matching subagent - automatically and in-session. There is no
copy/paste handoff. When a step starts (Step 1.5) or a gate is approved, run this procedure before handing
off to the step:

1. Use the Task tool to spawn the matching subagent (`qb-assess` for Step 1.5, `qb-subplanner`
   for Step 2, `qb-auditor` for Step 3, `qb-implementer` for Step 4). Pass that step's **goal
   contract** as the subagent task brief - its objective, success evidence, scope bounds, and stop
   condition - together with the **absolute path** to the bundled spec file the subagent must follow
   (`<plugin-root>/skills/qb-assess/assessment-planner.md`,
   `<plugin-root>/skills/qb-subplanner/second-planner.md`,
   `<plugin-root>/skills/qb-auditor/third-planner.md`, or
   `<plugin-root>/skills/qb-implementer/fourth-planner.md`). The user has explicitly opted into this
   workflow, which authorizes the delegated, autonomous execution of these steps.
2. For transparency, show the user the one-line objective you just delegated (in the user's language),
   using the canonical brief below.
3. Let the subagent run the step to completion and report back its result and validator status.
4. Fallback (degraded — only when delegation is impossible): if the Task tool or subagents are
   **genuinely unavailable** this session, run the step's skill in this session under the same
   in-context goal contract. This is **not** equivalent to delegation — it loses the independence that
   catches the author's blind spots (an in-session audit/assessment grades the very context that
   produced the plan). Prefer delegation whenever the Task tool exists; when you must fall back,
   disclose it per the Execution-model rule above, and in auto mode emit the `QB_PLAN_AUTO_WARN` line.

Canonical per-step goal contract (the subagent task brief), referencing the bundled spec by its
co-located path:

- Step 1.5 (`qb-assess`, spec `skills/qb-assess/assessment-planner.md`):
  > Run Step 1.5 Assessment per the qb-assess assessment-planner.md spec. Read .qb/main-planning.md and inspect the current repository read-only; create or update only .qb/assessment.md (a 14-heading technical feedback report). Skip for an empty or nearly empty repository and do not create assessment.md. Do not modify source code or main-planning.md.
- Step 2 (`qb-subplanner`, spec `skills/qb-subplanner/second-planner.md`):
  > Run Step 2 per the qb-subplanner second-planner.md spec. Read all main phases in .qb/main-planning.md; if .qb/assessment.md exists, read it fully as supporting feedback and account for it in the sub-plans. For each phase, create phase-<n>-plans folders under .qb and phase-<n>.<m>-*.md detailed sub-plan files. Do not stop until all phases are covered. Change only files under .qb.
- Step 3 (`qb-auditor`, spec `skills/qb-auditor/third-planner.md`):
  > Run Step 3 per the qb-auditor third-planner.md spec. Audit .qb/main-planning.md, sub-planning-index.md, and all phase-*-plans/*.md files; analyze main-phase coverage, file naming, ordering, required section structure, index consistency, content quality, scope drift, readiness realism, security/governance, and Step 4 readiness. Do not fix any plan file; produce only .qb/sub-planning-audit.md. Do not stop until all phases and sub-plans are reviewed.

## Gate 1 - feedback, then approve Step 2

1. Present a concise summary of `main-planning.md` (current-state conclusion, number of high-level phases,
   most important next action) and, if Step 1.5 ran, the top `assessment.md` signals.
2. Ask the user (in their language) whether they have any feedback on the master plan and (if present) the
   assessment. Apply main-plan feedback to `main-planning.md` only, and assessment feedback to `assessment.md` only
   (via the `qb-assess` subagent/skill); re-validate (`--mode step1`, and `--mode step2` for the assessment
   heading check), then re-summarize. Repeat until the user is satisfied.
3. Use `AskUserQuestion` to confirm proceeding to Step 2. Describe Step 2 plainly: "Read every main phase in
   `.qb/main-planning.md` (and `assessment.md` when present) and, for each phase, create
   `.qb/phase-<n>-plans/` folders and `phase-<n>.<m>-*.md` detailed sub-plan files. Do not stop until
   all phases are covered. Only change files under `.qb/`."
   - Decline -> stop gracefully; the user can resume with `/qb-plan` or the `qb-subplanner` skill.
   - Approve -> launch Step 2 via the **delegation procedure above** (Canonical Step-2 brief), then
     run the **`qb-subplanner`** subagent/skill to completion across all phases.

## Gate 2 - approve Step 3 (audit)

After `qb-subplanner` reports completion, present this confirmation, then ask with `AskUserQuestion`
(Yes / No):

> In the third step, we will now audit whether the sub-plans produced by Step 2 are faithful to the master plan, complete, ordered, actionable, and meet the quality bar. Do you approve?

- Decline -> stop gracefully; the user can run the audit later via the `qb-auditor` skill or `/qb-audit`.
- Approve -> launch Step 3 via the **delegation procedure above** (Canonical Step-3 brief), then
  run the **`qb-auditor`** subagent/skill until it produces `.qb/sub-planning-audit.md` and returns a status.

## After the audit - status, repair loop, and Step 4 gate

Read the audit status from `sub-planning-audit.md` (`## 1. Audit Summary`, `## 15. Audit Result`), then
run the Step-4 gate validator:
`python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step4`
(fallback: read the audit `## 12. Step 4 Readiness Assessment` table and `## 13. Prioritized Fix List` manually).

- **Gate passes (PASS, or PASS_WITH_WARNINGS with no P0/P1)** -> summarize; surface any P2/P3 items from
  `## 13. Prioritized Fix List` to keep visible. Use `AskUserQuestion` to offer Step 4. If approved, launch
  Step 4 via the delegation procedure and run the **`qb-implementer`** subagent/skill for one READY sub-plan slice.
- **Gate fails on P0/P1** (`step4_blocked_by_high_severity_findings`) -> do not offer Step 4. Show the
  prioritized fix list from `## 13`; use `AskUserQuestion` to offer applying the targeted repairs to only the
  named sub-plan files (within `.qb/`), then re-run the `qb-auditor` subagent/skill. Repeat until the
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
  modify the bundled template prompts. The sole exception is the Step 0 `.gitignore` guard, which may
  append a single `.qb/` line to the workspace `.gitignore` so planning artifacts stay uncommitted.
  Only Step 4 may change source code, after its gate passes and the user approves.
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
