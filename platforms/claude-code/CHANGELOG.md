# Changelog

All notable changes to QB are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-06-15

### Changed

- **BREAKING — unified naming: per-host `*qb` identifiers collapsed to `qb`.** The
  Claude Code, Cursor, and Codex packages now share one product name (`QB`), one plugin
  `id` (`qb`), and one command/skill namespace. Upstream attribution to Alican Kiraz's
  original CursorQB and CodexQB projects is preserved verbatim.
  - Commands: `/claudeqb-{plan,autopsy,audit,implement}` → `/qb-{plan,autopsy,audit,implement}`
  - Skills: `claudeqb-{planner,subplanner,auditor,implementer,autopsy}` → `qb-*`
  - Agents: `claudeqb-{subplanner,auditor,implementer,autopsy}` → `qb-*`
  - Plugin `name` / display name: `claudeqb` / `ClaudeQB` → `qb` / `QB`
  - Existing installs must reinstall and update any saved command invocations.

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

## [0.1.0] - 2026-06-15

### Added

- Initial Claude Code port of the QB repo-aware planning workflow, adapted from CursorQB (the Cursor
  plugin) and CodexQB (the Codex plugin) by Alican Kiraz. The planner prompts, specs, repo-aware intake,
  workflow-quality guidance, and read-only validator are ported faithfully; the product stays zero-setup,
  in-session, and gated at every step with explicit user approval.
- Claude Code plugin manifest at `.claude-plugin/plugin.json` (name `qb`) and a marketplace manifest
  at `.claude-plugin/marketplace.json` that publishes the plugin from the repository root. Claude Code
  auto-discovers `commands/`, `agents/`, and `skills/`.
- `qb-planner` orchestrator skill (`skills/qb-planner/`): language detection, repo-aware
  Step-1 Q&A for the four planning fields, in-context placeholder substitution, Gate 1 (feedback +
  approval), Gate 2 (audit confirmation), and the `PASS_WITH_WARNINGS` repair loop. It runs Step 1.5 for
  existing projects and Gate 1 feedback covers both `Main-Planing.md` and `Autopsy.md`.
- `qb-autopsy` skill + `/qb-autopsy` command (Step 1.5): an existing-project autopsy that
  writes a 13-section `Planner-docs/Autopsy.md` technical feedback report, run automatically after Step 1
  for existing/non-empty repositories and skipped for empty ones.
- `qb-subplanner` skill (Step 2): phase decomposition into `Planner-docs/Faz-<n>-Plans/` sub-plans
  plus `Sub-Planing-Index.md`, requiring full relative-path index references and all-file validation. It
  reads `Planner-docs/Autopsy.md` as an optional supporting source.
- `qb-auditor` skill + `/qb-audit` command (Step 3): a coverage/quality audit producing
  `Planner-docs/Sub-Planing-Audit.md` with a `PASS` / `PASS_WITH_WARNINGS` / `BLOCKED` status; safe to run
  standalone for re-audits.
- `qb-implementer` skill + `/qb-implement` command (Step 4): a gated implementation of one
  bounded, reversible slice from a `READY` sub-plan, only when the audit is not `BLOCKED` and has no P0/P1
  findings.
- `/qb-plan` command to run the full multi-step workflow from the start.
- Goal-backed steps adapted to Claude Code: the orchestrator delegates each long autonomous step
  (Step 1.5, 2, 3, 4) to a matching subagent — `qb-autopsy`, `qb-subplanner`,
  `qb-auditor`, `qb-implementer` under `agents/` — via the Task tool, passing the step's goal
  contract (objective / success evidence / scope bounds / stop condition) and the absolute path to the
  bundled spec. If subagents or the Task tool are unavailable, it falls back to running the step's skill
  in-session under the identical in-context goal contract.
- Bundled planner prompts co-located with their skills: `planners/first-planner.md`, `autopsy-planner.md`,
  `second-planner.md`, `third-planner.md`, and `fourth-planner.md`.
- Shared references: `references/repo-aware-intake.md` (a bounded read-only repository scan that proposes
  evidence-backed drafts for the four intake fields) and `references/workflow-quality.md` (reliability
  practices for read-before-counting, concise output, incremental large-doc writes, all-file validation,
  untracked-`Planner-docs/` git handling, and secret/token discipline).
- Bundled read-only validator `scripts/validate_planner_docs.py`
  (`--root <path> --mode step1|step2|step3|step4 --strict`): section/heading checks, phase-folder
  coverage, filename conventions, full relative-path index references, duplicate/gap numbering, unindexed
  files, length-bounded secret scan, audit status, and audit severity counts. Skills run it after each
  step, with an equivalent all-file fallback when `python3` is unavailable.
- Repo quality infrastructure: `scripts/validate.sh`, `Makefile` (`make check` / `make test`), a unit test
  suite under `tests/`, and `.github/workflows/validate.yml` for CI on pushes and pull requests.
- Output language is English. All generated planning documents and their section headings are produced in
  English; setup questions are asked in the user's language. Stable identifiers are preserved exactly:
  `Planner-docs/`, `Main-Planing.md`, `Autopsy.md`, `Sub-Planing-Index.md`, `Sub-Planing-Audit.md`,
  `Faz-<n>-Plans/`, and `Faz<n>.<m>-*.md`, including the intentional `Planing` spelling.
- Documentation: `README.md`, `docs/INSTALLATION.md`, `docs/USAGE.md`, and `docs/MAINTAINING.md`.
