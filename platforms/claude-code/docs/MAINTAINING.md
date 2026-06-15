# Maintaining QB

QB is an independent project inspired by [CursorQB](https://github.com/alicankiraz1/CursorQB)
(its closest analog) with [CodexQB](https://github.com/alicankiraz1/CodexQB) as
a secondary reference; it is not a direct port. The planner prompts, specs, intake,
workflow-quality rules, and validator are tool-agnostic product IP, reworked from
those upstream prompts into a host-neutral form.

## Validate locally

```bash
make check   # manifest + required files + frontmatter + traversal/residue scan + tests
make test    # unit tests only (verbose)
```

`make check` runs `scripts/validate.sh`, which:

1. parses `.claude-plugin/plugin.json` and checks `name == "qb"`;
2. confirms every required file exists (skills, bundled planner specs, agents, references, scripts, commands, docs);
3. checks that each skill's frontmatter `name` equals its directory and each command's and agent's `name` equals its filename stem;
4. fails on `../` parent traversal or any source-tooling residue (the upstream Cursor/Codex plugin ids and manifest directory names, the upstream goal-skill API names, and the old Codex handoff phrase) in component docs;
5. runs the test suite under `tests/`.

Expect a final `qb_repo_validation=passed` line on success.

## How the validator works

`scripts/validate_planner_docs.py` is read-only. Run it against a target
project's `.qb/`:

```bash
python3 scripts/validate_planner_docs.py --root /path/to/project --mode step2 --strict
```

Modes: `step1` (main-planning.md sections + phase roadmap), `step2` (phase
folders, sub-plan structure, full-path index references, optional `assessment.md`
heading order, duplicate/gap numbering), `step3` (audit heading order), `step4`
(audit status + `AUDIT-FIX-NN | PX` severity gating). It also runs a
length-bounded secret scan in every mode. `--strict` turns quality warnings
(repeated/generic sections) into failures.

Key invariants the tests guard (`tests/`):

- Step-4 severity counting is driven by `AUDIT-FIX-NN | PX` finding headers, so negative prose like "P0/P1 yok" is never miscounted.
- The roadmap phase count comes from the `## 6` table, ignoring historical phase mentions.
- Optional `assessment.md` is validated only when present.
- Index references must be full relative paths.

## Sanitized export

Do not create release archives with generic directory compression, because
ignored files such as `.git/`, `__pycache__/`, `.env`, `artifacts/`, `logs/`, or
`tmp/` can be included.

Use the tracked-file export target:

```bash
make export-sanitized
```

This writes `QB-sanitized.zip` with `git archive`, so only tracked files
are included.

## GitHub Actions CI

CI lives at `.github/workflows/validate.yml` and runs on pushes to `main` and on
pull requests. It checks out the repository and runs `make check`, the same gate
you run locally:

```yaml
name: validate

on:
  push:
    branches: [main]
  pull_request:

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run repository validation
        run: make check
```

Because `make check` runs the Python test suite, CI needs `python3` available on
the runner (`ubuntu-latest` provides it). If you pin a specific interpreter, add
an `actions/setup-python` step before `make check`.

## Editing the bundled prompts

The bundled planner specs are the source of truth for each step:

- `skills/qb-planner/planners/first-planner.md` (Step 1)
- `skills/qb-assess/assessment-planner.md` (Step 1.5)
- `skills/qb-subplanner/second-planner.md` (Step 2)
- `skills/qb-auditor/third-planner.md` (Step 3)
- `skills/qb-implementer/fourth-planner.md` (Step 4)

When editing them: preserve the exact required output filenames (`main-planning.md`,
`sub-planning-index.md`, `sub-planning-audit.md`), keep all required section
headings and order (the validator and
`tests/test_validate_planner_docs.py` enforce them), keep the four Step-1
placeholders, and keep the workflow Claude Code-native — delegate long
autonomous steps to the matching subagent via the Task tool (with the in-context
goal-contract fallback), and never reintroduce source-tooling residue (the
upstream plugin ids, the upstream goal-skill API names, or the old Codex handoff
phrase).

## Conventions

- One skill per directory under `skills/`; frontmatter `name` must equal the directory name.
- One command per file under `commands/`; frontmatter `name` must equal the filename stem.
- One subagent per file under `agents/`; frontmatter `name` must equal the filename stem.
- Shared, read-only assets live in `references/` and `scripts/`; skills and agents resolve them relative to the plugin root (the directory containing `.claude-plugin/`), never with `..` in component docs.
- Bump `version` in `.claude-plugin/plugin.json` and add a `CHANGELOG.md` entry for every change.
