# Installation

QB is a single Claude Code plugin: Claude Code auto-discovers its
`commands/`, `agents/`, `skills/`, and `hooks/` from the plugin manifest at
`.claude-plugin/plugin.json`. It draws on the
[CursorQB](https://github.com/alicankiraz1/CursorQB) Cursor plugin (with
[CodexQB](https://github.com/alicankiraz1/CodexQB) as a secondary reference),
but is not a direct port.

## Install from a marketplace (recommended)

QB's Claude Code package is **plugin-only** — it ships no marketplace manifest of
its own. It is published through the dedicated
[`eserlxl/claude-marketplace`](https://github.com/eserlxl/claude-marketplace) aggregator repo,
which references this package with a `git-subdir` source. That single marketplace
also offers `planwright`.

Run these in Claude Code:

```text
/plugin marketplace add eserlxl/claude-marketplace
/plugin install qb@eserlxl
```

- Add **only** `eserlxl/claude-marketplace`. Do not add `eserlxl/qb` as a marketplace —
  this repo no longer declares one. A Claude Code marketplace is keyed by the
  `name` inside its manifest, and `eserlxl/qb` previously claimed the same
  `eserlxl` name as the aggregator, which made the two collide.
- For **local development**, register this package's directory directly (see
  *Manual install* below) instead of adding it as a marketplace.
- After installation, start a fresh chat so the skills, commands, and subagents
  are loaded into context.

Once installed, these commands become available:

- `/qb-plan` - start the full five-step workflow.
- `/qb-assess` - run only the Step 1.5 existing-project assessment.
- `/qb-audit` - run only the Step 3 audit.
- `/qb-implement` - run only the gated Step 4 implementation.

## Manual install

If you prefer not to use the marketplace flow, register the plugin directory
directly. Clone or copy this repository to a stable location, then point Claude
Code at the plugin root via your Claude Code settings (the directory that
contains `.claude-plugin/plugin.json`). Claude Code reads
`.claude-plugin/plugin.json` and auto-discovers everything under `commands/`,
`agents/`, and `skills/` — there are no path-pointer keys to maintain. Reload
or restart Claude Code after registering the directory.

## Requirements

- **Claude Code** with plugin support.
- **`python3`** *(for the validator)* — powers the bundled validator
  (`scripts/validate_planner_docs.py`) and the test suite. `python3` ships on
  macOS and most Linux systems. If `python3` is unavailable, the skills fall
  back to equivalent manual checks and say so; the workflow still runs.

## Verify the install

```bash
make check
```

This validates the manifest, required files, and frontmatter, and runs the test
suite. Expect a final `qb_repo_validation=passed` line.

You can also verify interactively: open a chat in a project and run
`/qb-plan`. QB performs a bounded read-only scan of the repository, then
confirms the four intake fields (`PROJECT_NAME`, `PROJECT_INTENT`,
`TARGET_END_STATE`, `KNOWN_CONSTRAINTS`) — auto-derived with a single
consolidated confirmation on a well-structured repo, or asked in turn
otherwise — before writing `.qb/main-planning.md`.

## Verified install & launch path

- **Source:** published via the
  [`eserlxl/claude-marketplace`](https://github.com/eserlxl/claude-marketplace)
  aggregator (a `git-subdir` source pointing at this package's
  `.claude-plugin/plugin.json`); local development registers the plugin directory
  directly.
- **Launch entrypoint:** `skills/qb-planner/SKILL.md` (with `commands/qb-plan.md`)
  is what `/qb-plan` runs.
- **Proven by:** `scripts/validate.sh` (run by `make check`), which fails closed if
  the manifest, the launch entrypoint, or any required component is missing.
