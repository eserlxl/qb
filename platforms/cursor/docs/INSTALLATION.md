# Installation

QB's Cursor package lives at `platforms/cursor` in the QB monorepo. Its plugin
manifest is `platforms/cursor/.cursor-plugin/plugin.json`, and the repo-root
`.cursor-plugin/marketplace.json` registers it for marketplace import.

## Local install (immediate use)

Clone the repo and symlink the Cursor package into your local Cursor plugins directory, then reload Cursor:

```bash
git clone https://github.com/eserlxl/qb.git
ln -s "$(pwd)/qb/platforms/cursor" ~/.cursor/plugins/local/qb
```

After reloading, the skills and these commands become available:

- `/qb-plan` - start the full five-step workflow.
- `/qb-assess` - run only the Step 1.5 existing-project assessment.
- `/qb-audit` - run only the Step 3 audit.
- `/qb-implement` - run only the gated Step 4 implementation.

## Marketplace

The repo-root `.cursor-plugin/marketplace.json` registers the `qb` plugin
(`source: ./platforms/cursor`), so you can import `eserlxl/qb` as a marketplace
from Cursor's Plugins settings. The per-plugin manifest at
`platforms/cursor/.cursor-plugin/plugin.json` is the plugin's own source of truth.

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
final `qb_repo_validation=passed` line.

## Verified install & launch path

- **Source:** the repo-root `.cursor-plugin/marketplace.json` registers `qb` with
  source `./platforms/cursor`; `platforms/cursor/.cursor-plugin/plugin.json` is the
  per-plugin manifest.
- **Launch entrypoint:** `skills/qb-planner/SKILL.md` (with `commands/qb-plan.md`).
- **Proven by:** `scripts/validate.sh` (run by `make check`), which fails closed if
  the manifest, the launch entrypoint, or any required component is missing.
