# QB Workflow Quality Notes

Use these notes alongside the active planner prompt and skill. They do not replace
the planner prompt; they capture reliability practices proven in real use.

## Read Before Reporting Counts

- Read the full active planner prompt (bundled next to the running skill) before summarizing requirements.
- Do not report phase, sub-plan, or section counts from memory.
- Report counts only after reading the prompt or running the validator.
- Required section counts: `Main-Planning.md` has 10 numbered sections; the sub-plan index has 7 (after its H1); each Step 2 sub-plan has 13 top-level `##` sections after its H1; the audit has 15.

## Step 1 Repo-Aware Intake

- Run a bounded, read-only repository scan before asking the four Step 1 fields.
- Use `references/repo-aware-intake.md` to infer evidence-backed defaults, but never treat an inferred value as final until the user confirms or edits it.
- Keep intake conversational and sequential: one plain-text question at a time, in the user's language.
- If the repository is empty or evidence is weak, say so and fall back to concise generic questions.
- Do not let the pre-intake scan replace the full Step 1 inspection required by `first-planner.md`.

## Use The Bundled Validator

Prefer the bundled validator over ad hoc checks. Resolve the plugin root by walking up
from the active skill's own directory to the folder that contains the plugin manifest;
the script is at `<plugin-root>/scripts/validate_planner_docs.py`. Always pass `--root .`
so it validates the user's active workspace `Planner-docs/`, never the plugin directory.

```bash
python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step1 --strict
python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step2 --strict
python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step3 --strict
python3 <plugin-root>/scripts/validate_planner_docs.py --root . --mode step4
```

The validator is read-only. It checks required sections and order, phase folders,
filename conventions, full-path index references, duplicate numbering, numbering gaps,
missing or unindexed files, length-bounded secret patterns, audit status, and audit
severity counts.

Graceful fallback: if `python3` is unavailable or the script cannot be found, perform
the equivalent checks manually (heading presence and order; every main phase has a
`Phase-<n>-Plans/` folder with at least one conforming sub-plan; the index references every
sub-plan by full relative path; no secrets) and state plainly that the validator was
unavailable and checks were manual.

## Keep Output Concise

- Keep chat output concise during long goal-backed runs.
- Do not dump full generated files unless the user explicitly asks.
- Summarize counts, file paths, blockers, and validation status; keep detailed evidence inside the generated Markdown artifacts.

## Avoid Noisy Inline Generators; Build Large Docs Incrementally

- Prefer normal file-editing tools over large inline generation scripts.
- Build large documents incrementally (create the file, then add section by section) instead of one oversized write.
- Validate every generated file; do not rely on sampled reads. Step 2 requires all-file structure validation.

## Handle Untracked Planner Docs Correctly

`Planner-docs/` is usually untracked on first use, and `git diff -- Planner-docs` does
not show new untracked files. Use these together:

```bash
find Planner-docs -maxdepth 4 -type f | sort
git status --short -- Planner-docs
git diff -- Planner-docs
```

Use `git diff --no-index` only as a read-only comparison helper.

## Secret Scan Discipline

- Use length-bounded token patterns such as `sk-[A-Za-z0-9_-]{20,}`; never one-character `sk-` prefixes.
- Never print secret values if a secret-like pattern is detected.

## Step Handoffs (in-session, automatic)

- Every step runs in the current session. Step 1 is interactive; Steps 2 and 3 are launched automatically by the workflow under each step's goal contract (objective, success evidence, scope bounds, stop condition). There is no copy/paste handoff.
- Step 3 may create or update only `Planner-docs/Sub-Planning-Audit.md`.
- Step 4 (implementation) starts only after `--mode step4` validation passes: the audit is not `BLOCKED` and has no P0/P1 findings. Step 4 is a separate goal-backed implementation run, not a planning-file generation step.

## Step 4 Token Discipline

- Do not load all phase sub-plans at once.
- Read `Sub-Planning-Audit.md` and `Sub-Planning-Index.md` first.
- Select one READY or READY_WITH_WARNINGS sub-plan.
- Load only the selected sub-plan and the repo files needed for that one slice.
- Stop before implementation if the audit contains P0/P1 findings.
