# Changelog

All notable changes to QB are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-06-15

### Added

- **Step 5 — automatic planwright-format plan export.** After Step 3 the planning workflow now
  projects the `.qb/` sub-plans into a flat, execution-ready `.qb/plan.md` in planwright's
  8-field checkbox item format (one item per Planned Work Breakdown entry, across all phases),
  so a QB plan can be handed to planwright's `execute` / `cycle` without re-planning. A new
  bundled read-only validator, `scripts/validate_planwright_plan.py`, gates the export against
  the machine-checkable subset of planwright's plan linter (a plan that passes it is accepted
  by planwright on hand-off). New reference `Export-Planner.md`. Hand-off:
  `cp .qb/plan.md .planwright/plan.md` then run planwright `execute` (or `cycle <N>`).

## [0.3.0] - 2026-06-15

### Changed

- **BREAKING — unified naming: per-host `*qb` identifiers collapsed to `qb`.** The
  Claude Code, Cursor, and Codex packages now share one product name (`QB`), one plugin
  `id` (`qb`), and one command/skill namespace. Upstream attribution to Alican Kiraz's
  original CursorQB and CodexQB projects is preserved verbatim.
  - Skill: the `codexqb` skill is now `qb` (`plugins/codexqb/` → `plugins/qb/`,
    `skills/codexqb/` → `skills/qb/`)
  - Slash invocation: `$codexqb` → `$qb`
  - Plugin `name` / display name: `codexqb` / `CodexQB` → `qb` / `QB`
  - Upstream repository URLs (`alicankiraz1/CodexQB`) are unchanged.
  - Existing installs must reinstall and update any saved `$codexqb` invocations.

## [0.2.0] - 2026-06-15

### Changed

- **BREAKING — planning-artifact identifiers renamed.** The phase identifiers are now
  `Phase` and `Planning` across the planner prompts, the read-only validator, and the
  docs:
  - `Main-Planing.md` → `Main-Planning.md`
  - `Sub-Planing-Index.md` → `Sub-Planning-Index.md`
  - `Sub-Planing-Audit.md` → `Sub-Planning-Audit.md`
  - `Faz-<n>-Plans/` → `Phase-<n>-Plans/`
  - `Faz<n>.<m>-*.md` → `Phase<n>.<m>-*.md`
  - headings: `# Main Planing` → `# Main Planning`, `# Sub-Planing Index` →
    `# Sub-Planning Index`, `# Sub-Planing Audit` → `# Sub-Planning Audit`,
    `# Faz <n>.<m> — …` → `# Phase <n>.<m> — …`

  **Migration:** existing `Planner-docs/` that use the previous filenames are not
  recognized by the updated validator. Either re-run the workflow to regenerate them, or rename the
  files/folders above and update the path references inside `Sub-Planning-Index.md` to
  match. There is no automatic migration.
