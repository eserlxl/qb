# Changelog

All notable changes to QB are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2026-06-15

### Added

- **`$qb auto` — non-interactive planning mode.** Invoking `$qb` with the `auto` flag runs the
  whole planning workflow without prompting: it auto-derives the four Step-1 intake fields from
  the repository and **fails closed** if any is missing (prints
  `QB_PLAN_AUTO_ERROR: missing required field(s): …` and stops), treats the gates as approved,
  skips the gated Step 4 implementation handoff, produces and validates `.qb/plan.md`, and
  prints a single deterministic result line (`QB_PLAN_AUTO_OK:` / `QB_PLAN_AUTO_ERROR:`) so an
  external caller such as planwright can detect success. Auto mode writes only under `.qb/` and
  never modifies source code, commits, pushes, or opens PRs.
- **Repo-aware auto-intake fast path.** On a well-structured repository (at least three of five
  signals: a README, a manifest/build file, a source directory, a tests directory, a CI config),
  Step-1 intake auto-derives all four fields and asks a single consolidated confirmation instead
  of one question per field; weak-evidence fields fall back to per-field prompts. With `$qb auto`
  it derives without confirmation and fails closed (`QB_PLAN_AUTO_ERROR`) when a field cannot be
  derived.

### Changed

- **Export renumbered Step 5 → Step 3.5.** The automatic planwright-format export now carries the
  number that matches where it already runs — between the Step 3 audit and the optional, gated Step 4
  implementation — instead of the trailing "Step 5" label. Behaviour is unchanged (it still runs
  automatically after the audit and writes only `.qb/plan.md`); the orchestrator flow, commands, and
  usage docs were updated so the numbering reflects execution order. The Step 4 implementation gate
  (`--mode step4`) and the `## 12. Step 4 Readiness Assessment` audit heading are unchanged.

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

## [0.6.0] - 2026-06-15

### Changed

- **Manifest version alignment (Phase 6.4).** The Codex plugin manifest version was bumped
  to match the new shared root `VERSION` file, which became the single source of truth across
  all three platform packages (enforced by `test_version_and_structure.py`). No Codex behavior
  change; this entry records the manifest jump (`0.3.0` → `0.6.0`) that the per-package
  CHANGELOG had not previously tracked. Intermediate `0.4.0`/`0.5.0` were never separate Codex
  releases.

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
