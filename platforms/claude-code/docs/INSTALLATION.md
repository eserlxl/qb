# Installation

ClaudeQB is a single Claude Code plugin: Claude Code auto-discovers its
`commands/`, `agents/`, `skills/`, and `hooks/` from the plugin manifest at
`.claude-plugin/plugin.json`. It is ported from the
[CursorQB](https://github.com/alicankiraz1/CursorQB) Cursor plugin (with
[CodexQB](https://github.com/alicankiraz1/CodexQB) as a secondary reference).

## Install from a marketplace (recommended)

ClaudeQB ships its own repo-local marketplace manifest at
`.claude-plugin/marketplace.json`, so you can add this repository as a
marketplace and install the plugin from it.

Run these in Claude Code:

```text
/plugin marketplace add <path-or-repo>
/plugin install claudeqb
```

- `<path-or-repo>` is either a local checkout directory (for example
  `/absolute/path/to/ClaudeQB`) or a Git repository reference. The plugin lives
  at the repository root (`"source": "./"`), so point the marketplace at the
  repository, not a subfolder.
- After installation, start a fresh chat so the skills, commands, and subagents
  are loaded into context.

Once installed, these commands become available:

- `/claudeqb-plan` - start the full five-step workflow.
- `/claudeqb-autopsy` - run only the Step 1.5 existing-project autopsy.
- `/claudeqb-audit` - run only the Step 3 audit.
- `/claudeqb-implement` - run only the gated Step 4 implementation.

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
suite. Expect a final `claudeqb_repo_validation=passed` line.

You can also verify interactively: open a chat in a project and run
`/claudeqb-plan`. ClaudeQB performs a bounded read-only scan of the repository,
then asks the four intake questions (`PROJECT_NAME`, `PROJECT_INTENT`,
`TARGET_END_STATE`, `KNOWN_CONSTRAINTS`) before writing
`Planner-docs/Main-Planing.md`.
