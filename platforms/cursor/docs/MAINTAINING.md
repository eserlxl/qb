# Maintaining CursorQB

## Validate locally

```bash
make check   # manifest + required files + frontmatter + cross-host residue scan
```

`make check` runs `scripts/validate.sh`, which:

1. parses `.cursor-plugin/plugin.json` and checks `name == "cursorqb"`;
2. confirms every required file exists (skills, bundled planner specs, references, scripts, commands, docs);
3. checks that each skill's frontmatter `name` equals its directory and each command's `name` equals its filename stem;
4. fails on cross-host residue in the hand-authored host files (skills `SKILL.md` and commands): the forbidden set is `claudeqb`, `codexqb`, the other-host plugin invocation token, `.claude-plugin`, and `.codex-plugin`. The synced neutral planner specs, references, and validator are intentionally **not** brand-scanned (they say only "QB").

`scripts/validate.sh` is dependency-free (pure POSIX shell) and ends with the line
`cursorqb_repo_validation=passed`.

## Shared vs. platform-specific files

CursorQB lives in a multi-platform monorepo whose **single source of truth** is the top-level
`shared/` directory. The host-neutral planner specs, the two reference docs, and the read-only
validator are authored once in `shared/` and copied into this platform by `scripts/sync.sh`. The
copies land at their normal co-located paths:

- `skills/cursorqb-planner/planners/first-planner.md` (Step 1)
- `skills/cursorqb-autopsy/autopsy-planner.md` (Step 1.5)
- `skills/cursorqb-subplanner/second-planner.md` (Step 2)
- `skills/cursorqb-auditor/third-planner.md` (Step 3)
- `skills/cursorqb-implementer/fourth-planner.md` (Step 4)
- `references/repo-aware-intake.md`, `references/workflow-quality.md`
- `scripts/validate_planner_docs.py`

These synced files are **host-neutral** ("QB", never CursorQB/Cursor): do not hand-edit them here.
Edit the canonical source under the monorepo's `shared/` and re-run the sync. Everything else in
this directory is **platform-specific** and hand-authored for Cursor: the manifest, the four slash
commands, the five `SKILL.md` orchestrations, `docs/`, `README.md`, `CHANGELOG.md`, `LICENSE`, and
`assets/`. These carry the `cursorqb` brand and Cursor's native `define-goal` goal mechanism.

## How the validator works

`scripts/validate_planner_docs.py` is read-only. Run it against a target project's `Planner-docs/`:

```bash
python3 scripts/validate_planner_docs.py --root /path/to/project --mode step2 --strict
```

Modes: `step1` (Main-Planning.md sections + phase roadmap), `step2` (phase folders, sub-plan
structure, full-path index references, optional `Autopsy.md` heading order, duplicate/gap
numbering), `step3` (audit heading order), `step4` (audit status + `AUDIT-FIX-NN | PX` severity
gating). It also runs a length-bounded secret scan in every mode. `--strict` turns quality
warnings (repeated/generic sections) into failures.

Key invariants the tests guard (`tests/`):

- Step-4 severity counting is driven by `AUDIT-FIX-NN | PX` finding headers, so negative prose like "P0/P1 none" is never miscounted.
- The roadmap phase count comes from the `## 6` table, ignoring historical phase mentions.
- Optional `Autopsy.md` is validated only when present.
- Index references must be full relative paths.

## Editing the bundled prompts

The bundled planner specs are the host-neutral source of truth for each step and live in the
monorepo's `shared/planners/`. Edit them there, then re-sync into this platform.

When editing them: preserve the exact required output filenames (`Main-Planning.md`,
`Sub-Planning-Index.md`, `Sub-Planning-Audit.md`), keep all required section headings and order (the
validator and `tests/test_validate_planner_docs.py` enforce them), keep the four Step-1
placeholders, and keep the specs host-neutral (they refer to the product generically as "QB").

## Conventions

- One skill per directory under `skills/`; frontmatter `name` must equal the directory name.
- One command per file under `commands/`; frontmatter `name` must equal the filename stem.
- Shared, read-only assets live in `references/` and `scripts/`; skills resolve them relative to
  the plugin root (walk up to `.cursor-plugin/`), never with `..` in component docs.
- Bump `version` in `.cursor-plugin/plugin.json` and add a `CHANGELOG.md` entry for every change.
