---
name: qb-planner
description: Guided five-step (1, 1.5, 2, 3, 4), delegated project planning orchestrator with a repo-aware intake. Use when the user runs /qb-plan or asks QB to plan a project end to end - master plan, existing-project autopsy, phase decomposition, coverage audit, then optional implementation. Runs a repo-aware Step 1 intake, produces Planner-docs/Main-Planning.md, runs a Step 1.5 autopsy (qb-autopsy) for existing projects, then gates into phase decomposition (qb-subplanner), a coverage/quality audit (qb-auditor), and a gated implementation step (qb-implementer) - each long autonomous step delegated automatically to a matching subagent via the Task tool. Validates each step with the bundled validator.
---

# QB Planner (orchestrator)

Drive the QB planning workflow inside the current chat session, with an explicit
user-approval gate between every step. This skill owns the conversation, the repo-aware
Step-1 intake, and the gates; it delegates the long autonomous steps to the
`qb-autopsy`, `qb-subplanner`, `qb-auditor`, and `qb-implementer` subagents
via the Task tool.

```text
Step 1   repo-aware intake -> First-Planner -> Main-Planning.md       (interactive)   [validator step1]
Step 1.5 qb-autopsy  -> Autopsy.md (existing projects only)    (delegated)      [validator step2 autopsy]
 Gate 1 feedback (Main-Planning + Autopsy) + approve
Step 2   qb-subplanner -> Phase-*-Plans/ + Sub-Planning-Index.md  (delegated)      [validator step2]
 Gate 2 audit approval
Step 3   qb-auditor     -> Sub-Planning-Audit.md                (delegated)      [validator step3]
 Repair PASS_WITH_WARNINGS -> targeted fixes -> re-audit
 Step 4 gate: validator step4 (audit not BLOCKED, no P0/P1)
Step 4   qb-implementer -> one reversible code slice           (delegated, gated)
```

## Execution model and non-negotiable rules

- **In-session, zero-setup.** No API key, no external process. You read the bundled planner
  prompt, fill it in your own context, and follow its instructions yourself.
- **Reliability references + validator.** Resolve the plugin root by walking up from this skill's
  directory to the folder containing `.claude-plugin/plugin.json`. Read `references/workflow-quality.md`
  before starting and follow it (read-before-counting, concise output, untracked-Planner-docs git
  handling, secret/token discipline). After each step, run the bundled validator
  `python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode stepN [--strict]`; if
  `python3` or the script is unavailable, fall back to the equivalent manual checks and say so.
- **Delegated steps use the Task tool, automatically.** Steps 1.5, 2, 3, and 4 are delegated to the
  matching `qb-*` subagent via the Task tool, in-session and hands-free. There is no copy/paste
  handoff. If the Task tool or subagents are unavailable this session, the step still runs in-session
  under its own in-context goal contract - behavior is identical.
- **Bundled prompt location.** The Step-1 prompt lives next to this skill at `planners/first-planner.md`.
  Read it from there. Never inline its full text into chat.
- **Output location is the user's workspace, not the plugin.** Write every planning artifact
  (`Planner-docs/...`) into the user's **active workspace / current working directory**. Never write
  planning output into this plugin's directory.
- **Never mutate the templates.** Do placeholder substitution in memory only. The bundled prompts
  (`planners/first-planner.md` and the specs inside `qb-autopsy` / `qb-subplanner` /
  `qb-auditor` / `qb-implementer`) must stay byte-for-byte pristine for the next run.
- **Language.** Ask every question in the **language the user is writing in**. Produce all planning
  documents in **English** (the bundled prompts enforce English output).
- **Honor each prompt's guardrails.** Step 1 may only create/update `Main-Planning.md`; Step 1.5 may only
  create/update `Autopsy.md`; Step 2 may only change files under `Planner-docs/`; Step 3 may only
  create/update `Sub-Planning-Audit.md`; only Step 4 may change source code, and only after its gate
  passes and the user approves. Never write secrets, tokens, or credentials. Never auto-commit, push, or
  open PRs during planning.
- **Always wait for explicit approval at each gate** before continuing.

## Step 0 - detect and brief

1. Detect the user's language from the conversation and use it for all questions and prose.
2. Read `references/workflow-quality.md` (resolve plugin root) and follow its reliability practices throughout.
3. In 2-3 sentences, explain the steps and that you will pause for approval at each gate.
4. Check the user's workspace for an existing `Planner-docs/Main-Planning.md`. If it exists, say you will
   reconcile and update it rather than blindly duplicate (First-Planner handles reconciliation).

## Step 1 - repo-aware intake (interactive)

Follow `references/repo-aware-intake.md` (resolve plugin root). Before asking, run a bounded read-only
scan of the user's workspace so you can propose evidence-backed drafts. Then ask the four fields **one
per turn, in order, in the user's language, as plain-text questions** (no multiple-choice). For each,
offer your repo-derived draft and ask the user to confirm or edit; mark clearly when a value is
inferred. If repo evidence is weak, say so and ask the concise generic version.

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
   repository inspection it lists. Create or update `Planner-docs/Main-Planning.md` in the user's
   workspace, in English, with exactly the required top-level sections.
4. Run the prompt's own post-write validation (read it back, confirm sections, English, no secrets).
5. Run the bundled validator: `python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step1 --strict`
   (fallback: manual checks). Fix any structural errors before Step 1.5 / Gate 1.

## Step 1.5 - existing-project autopsy (auto for existing repos)

After Step 1, decide whether Step 1.5 applies:

- **Run** when the workspace is an existing or partially built project: it is not empty and has
  meaningful evidence (README, manifests, source/service/package dirs, tests, docs, configs, or CI).
- **Skip** for new or nearly empty repositories; do not create `Planner-docs/Autopsy.md`.

When it applies, launch Step 1.5 via the delegation procedure below (Canonical Step-1.5 subagent brief) and
follow the **`qb-autopsy`** subagent/skill. It writes only `Planner-docs/Autopsy.md` (a 13-section technical
feedback report) which Step 2 uses as supporting feedback. No separate approval is needed before Step 1.5;
the user reviews both `Main-Planning.md` and `Autopsy.md` together at Gate 1.

## Delegated step launch via the Task tool

Steps 1.5, 2, 3, and 4 are delegated to the matching subagent - automatically and in-session. There is no
copy/paste handoff. When a step starts (Step 1.5) or a gate is approved, run this procedure before handing
off to the step:

1. Use the Task tool to spawn the matching subagent (`qb-autopsy` for Step 1.5, `qb-subplanner`
   for Step 2, `qb-auditor` for Step 3, `qb-implementer` for Step 4). Pass that step's **goal
   contract** as the subagent task brief - its objective, success evidence, scope bounds, and stop
   condition - together with the **absolute path** to the bundled spec file the subagent must follow
   (`<plugin-root>/skills/qb-autopsy/autopsy-planner.md`,
   `<plugin-root>/skills/qb-subplanner/second-planner.md`,
   `<plugin-root>/skills/qb-auditor/third-planner.md`, or
   `<plugin-root>/skills/qb-implementer/fourth-planner.md`). The user has explicitly opted into this
   workflow, which authorizes the delegated, autonomous execution of these steps.
2. For transparency, show the user the one-line objective you just delegated (in the user's language),
   using the canonical brief below.
3. Let the subagent run the step to completion and report back its result and validator status.
4. Fallback: if the Task tool or subagents are unavailable this session, skip delegation and run the
   step's skill in this session under the same in-context goal contract - behavior is identical.

Canonical per-step goal contract (the subagent task brief), referencing the bundled spec by its
co-located path:

- Step 1.5 (`qb-autopsy`, spec `skills/qb-autopsy/autopsy-planner.md`):
  > Run Step 1.5 Autopsy per the qb-autopsy autopsy-planner.md spec. Read Planner-docs/Main-Planning.md and inspect the current repository read-only; create or update only Planner-docs/Autopsy.md (a 14-heading technical feedback report). Skip for an empty or nearly empty repository and do not create Autopsy.md. Do not modify source code or Main-Planning.md.
- Step 2 (`qb-subplanner`, spec `skills/qb-subplanner/second-planner.md`):
  > Run Step 2 per the qb-subplanner second-planner.md spec. Read all main phases in Planner-docs/Main-Planning.md; if Planner-docs/Autopsy.md exists, read it fully as supporting feedback and account for it in the sub-plans. For each phase, create Phase-<n>-Plans folders under Planner-docs and Phase<n>.<m>-*.md detailed sub-plan files. Do not stop until all phases are covered. Change only files under Planner-docs.
- Step 3 (`qb-auditor`, spec `skills/qb-auditor/third-planner.md`):
  > Run Step 3 per the qb-auditor third-planner.md spec. Audit Planner-docs/Main-Planning.md, Sub-Planning-Index.md, and all Phase-*-Plans/*.md files; analyze main-phase coverage, file naming, ordering, required section structure, index consistency, content quality, scope drift, readiness realism, security/governance, and Step 4 readiness. Do not fix any plan file; produce only Planner-docs/Sub-Planning-Audit.md. Do not stop until all phases and sub-plans are reviewed.

## Gate 1 - feedback, then approve Step 2

1. Present a concise summary of `Main-Planning.md` (current-state conclusion, number of high-level phases,
   most important next action) and, if Step 1.5 ran, the top `Autopsy.md` signals.
2. Ask the user (in their language) whether they have any feedback on the master plan and (if present) the
   autopsy. Apply main-plan feedback to `Main-Planning.md` only, and autopsy feedback to `Autopsy.md` only
   (via the `qb-autopsy` subagent/skill); re-validate (`--mode step1`, and `--mode step2` for the autopsy
   heading check), then re-summarize. Repeat until the user is satisfied.
3. Use `AskUserQuestion` to confirm proceeding to Step 2. Describe Step 2 plainly: "Read every main phase in
   `Planner-docs/Main-Planning.md` (and `Autopsy.md` when present) and, for each phase, create
   `Planner-docs/Phase-<n>-Plans/` folders and `Phase<n>.<m>-*.md` detailed sub-plan files. Do not stop until
   all phases are covered. Only change files under `Planner-docs/`."
   - Decline -> stop gracefully; the user can resume with `/qb-plan` or the `qb-subplanner` skill.
   - Approve -> launch Step 2 via the **delegation procedure above** (Canonical Step-2 brief), then
     run the **`qb-subplanner`** subagent/skill to completion across all phases.

## Gate 2 - approve Step 3 (audit)

After `qb-subplanner` reports completion, present this confirmation, then ask with `AskUserQuestion`
(Yes / No):

> In the third step, we will now audit whether the sub-plans produced by Step 2 are faithful to the master plan, complete, ordered, actionable, and meet the quality bar. Do you approve?

- Decline -> stop gracefully; the user can run the audit later via the `qb-auditor` skill or `/qb-audit`.
- Approve -> launch Step 3 via the **delegation procedure above** (Canonical Step-3 brief), then
  run the **`qb-auditor`** subagent/skill until it produces `Planner-docs/Sub-Planning-Audit.md` and returns a status.

## After the audit - status, repair loop, and Step 4 gate

Read the audit status from `Sub-Planning-Audit.md` (`## 1. Audit Summary`, `## 15. Audit Result`), then
run the Step-4 gate validator:
`python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step4`
(fallback: read the audit `## 12. Step 4 Readiness Assessment` table and `## 13. Prioritized Fix List` manually).

- **Gate passes (PASS, or PASS_WITH_WARNINGS with no P0/P1)** -> summarize; surface any P2/P3 items from
  `## 13. Prioritized Fix List` to keep visible. Use `AskUserQuestion` to offer Step 4. If approved, launch
  Step 4 via the delegation procedure and run the **`qb-implementer`** subagent/skill for one READY sub-plan slice.
- **Gate fails on P0/P1** (`step4_blocked_by_high_severity_findings`) -> do not offer Step 4. Show the
  prioritized fix list from `## 13`; use `AskUserQuestion` to offer applying the targeted repairs to only the
  named sub-plan files (within `Planner-docs/`), then re-run the `qb-auditor` subagent/skill. Repeat until the
  Step-4 gate passes or the user stops.
- **Gate fails on BLOCKED** -> report the blocker and the minimal next action from the audit; do not
  repair speculatively or start Step 4.

## Stop rules

- During planning (Steps 1-3) do not modify any file outside `Planner-docs/`, and never modify the
  bundled template prompts. Only Step 4 may change source code, after its gate passes and the user approves.
- Never write secrets, tokens, credentials, or private endpoints into any file.
- Never auto-commit, push, merge, or open pull requests unless the user explicitly asks in a Step 4 run.
- Always pause for explicit user approval at each gate.
- Ask in the user's language; write planning documents in English.

## Output

On a successful planning run the user's workspace contains, under `Planner-docs/`: `Main-Planning.md`,
`Autopsy.md` (for existing projects), one `Phase-<n>-Plans/` folder per phase with `Phase<n>.<m>-*.md`
sub-plans, `Sub-Planning-Index.md`, and `Sub-Planning-Audit.md`. If Step 4 ran, also one reversible code
slice with a passing validation command. Close with a short summary and the single most important
recommended next action.
