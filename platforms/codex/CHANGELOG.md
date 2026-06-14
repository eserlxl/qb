# Changelog

All notable changes to CodexQB are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
