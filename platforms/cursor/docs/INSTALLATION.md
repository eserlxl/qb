# Installation

CursorQB is a single-plugin Cursor repository: Cursor discovers it directly from
`.cursor-plugin/plugin.json` at the repository root.

## Local install (immediate use)

Symlink this plugin into your local Cursor plugins directory, then reload Cursor:

```bash
ln -s "/absolute/path/to/CursorQB" ~/.cursor/plugins/local/cursorqb
```

After reloading, the skills and these commands become available:

- `/cursorqb-plan` - start the full five-step workflow.
- `/cursorqb-autopsy` - run only the Step 1.5 existing-project autopsy.
- `/cursorqb-audit` - run only the Step 3 audit.
- `/cursorqb-implement` - run only the gated Step 4 implementation.

## Marketplace

To publish, host this directory as its own git repository and submit it to the Cursor
plugin marketplace. The manifest at `.cursor-plugin/plugin.json` is the source of truth.

## Optional dependency

The bundled spec validator (`scripts/validate_planner_docs.py`) uses `python3`, but the host
validator (`scripts/validate.sh`) is pure POSIX shell and needs no `python3`. `python3` ships on
macOS and most Linux systems. If `python3` is unavailable, the skills fall back to equivalent
manual checks and say so; the workflow still runs.

## Verify the install

```bash
make check
```

This validates the manifest, required files, frontmatter, and cross-host residue. Expect a
final `cursorqb_repo_validation=passed` line.
