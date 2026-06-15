# Changelog

All notable changes to QB are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-06-15

### Added

- **Step 5 — automatic planwright-format plan export.** Every planning run now closes by
  projecting the `.qb/` sub-plans into a flat, execution-ready `.qb/plan.md` in planwright's
  8-field checkbox item format (one item per Planned Work Breakdown entry, across all phases),
  so a QB plan can be handed to planwright's `execute` / `cycle` without re-planning. A new
  bundled read-only validator, `scripts/validate_planwright_plan.py`, gates the export against
  the machine-checkable subset of planwright's plan linter (a plan that passes it is accepted
  by planwright on hand-off). New spec `export-planner.md`. Hand-off:
  `cp .qb/plan.md .planwright/plan.md` then run planwright `execute` (or `cycle <N>`).

## [0.6.0] - 2026-06-15

### Changed

- **BREAKING — unified naming: per-host `*qb` identifiers collapsed to `qb`.** The
  Claude Code, Cursor, and Codex packages now share one product name (`QB`), one plugin
  `id` (`qb`), and one command/skill namespace. Upstream attribution to Alican Kiraz's
  original CursorQB and CodexQB projects is preserved verbatim.
  - Commands: `cursorqb-{plan,assessment,audit,implement}` → `qb-{plan,assessment,audit,implement}`
  - Skills: `cursorqb-{planner,subplanner,auditor,implementer,assessment}` → `qb-*`
  - Plugin `name` / display name: `cursorqb` / `CursorQB` → `qb` / `QB`
  - Existing installs must reinstall and update any saved command invocations.

## [0.5.0] - 2026-06-15

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

## [0.4.0] - 2026-06-14

### Changed

- **Output language is now English.** All generated planning documents (`Main-Planing.md`, `Assessment.md`,
  sub-plans, `Sub-Planing-Index.md`, `Sub-Planing-Audit.md`) and their section headings are produced in
  English. The bundled planner prompts (`first-planner.md`, `assessment-planner.md`, `second-planner.md`,
  `third-planner.md`) now mandate English output with English section headings.
- Translated all remaining in-product Turkish to English: the orchestrator's canonical `define-goal`
  texts and the Gate 2 audit confirmation, the repo-aware intake question templates (`Question N / 4`),
  and every skill's section-name references and language notes.
- Retargeted the validator (`STEP1`/`ASSESSMENT`/`INDEX`/`SUBPLAN`/`AUDIT` heading constants,
  `ROADMAP_HEADING`, and the `## 13. Prioritized Fix List` severity scan) and both test suites to the
  English headings. Stable identifiers are unchanged: `Main-Planing.md`, `Sub-Planing-Index.md`,
  `Sub-Planing-Audit.md`, `Faz-<n>-Plans/`, `Faz<n>.<m>-*.md`, and the intentional `Planing` spelling.
- Rewrote `README.md` as a clear English overview. Setup questions are still asked in the user's language.

## [0.3.0] - 2026-06-14

### Added

- `qb-assess` skill (Step 1.5) + `/qb-assess` command + bundled `assessment-planner.md`:
  an existing-project assessment that writes a 13-section `Planner-docs/Assessment.md` technical feedback
  report, run automatically after Step 1 for existing/non-empty repositories and skipped for empty ones.
- Validator Assessment support: `ASSESSMENT_HEADINGS` and `validate_assessment_optional` (reports `assessment_exists`
  and checks `Assessment.md` heading order during Step 2/3 validation).
- Test suite under `tests/`: `test_validate_planner_docs.py` (validator behavior, including assessment and
  Step-4 severity gating) and `test_skill_content.py` (skill-content and Cursor-native invariants).
- Repo quality infrastructure: `scripts/validate.sh`, `Makefile` (`make check` / `make test`),
  `.github/workflows/validate.yml`, and `.gitignore`.
- `docs/INSTALLATION.md`, `docs/USAGE.md`, and `docs/MAINTAINING.md`.

### Changed

- Reframed the workflow as five steps (1, 1.5, 2, 3, 4); the orchestrator runs Step 1.5 for existing
  projects and Gate 1 feedback covers both `Main-Planing.md` and `Assessment.md`.
- `qb-subplanner` and the bundled `second-planner.md` now read `Planner-docs/Assessment.md` as an
  optional supporting source (not a replacement for the master plan).
- `qb-auditor` `## 13` findings now use single-line `- AUDIT-FIX-NN | PX | <title>` headers, and the
  validator counts severities via `AUDIT_FIX_RE` (precise; never miscounts negative prose).
- `qb-implementer` / `fourth-planner.md` now frame the Superpowers skills and the security review as
  optional, with a graceful fallback to the audit, the selected sub-plan, and existing validation commands.

## [0.2.0] - 2026-06-14

### Added

- Bundled read-only validator `scripts/validate_planner_docs.py` (`--mode step1|step2|step3|step4 --strict`):
  section/heading checks, phase-folder coverage, filename conventions, full relative-path index
  references, duplicate/gap numbering, length-bounded secret scan, audit status, and audit severity
  counts. Skills run it after each step, with a manual fallback when `python3` is unavailable.
- `qb-implementer` skill and `/qb-implement` command: a gated, goal-backed Step 4 that
  implements one bounded, reversible slice from an audited plan (only when the audit is not `BLOCKED`
  and has no P0/P1 findings), leveraging the Superpowers skills and the security review.
- Repo-aware Step 1 intake (`references/repo-aware-intake.md`): a bounded read-only repository scan
  proposes evidence-backed drafts for the four intake fields before asking.
- `references/workflow-quality.md`: reliability practices (read-before-counting, concise output,
  incremental large-doc writes, all-file validation, untracked-`Planner-docs/` git handling, and
  secret/token discipline).

### Changed

- Reframed the workflow as four steps; the orchestrator now offers a gated Step 4 after the audit.
- `qb-subplanner` now requires full relative-path index references and all-file (not sampled) validation.
- `qb-auditor` now runs the validator before and after writing and keeps severity tokens on real
  `AUDIT-FIX-NN` finding lines.

### Fixed

- The validator's audit severity counter no longer miscounts bare `P0`/`P1` tokens in negative prose;
  it counts severities only on lines carrying an `AUDIT-FIX-` id or a `severity:` label.

## [0.1.0] - 2026-06-14

### Added

- Initial release of the QB three-step, goal-backed planning workflow.
- `qb-planner` orchestrator skill: language detection, sequential Step-1 Q&A for the four
  planning fields, in-context placeholder substitution, Gate 1 (feedback + approval), Gate 2
  (verbatim Turkish audit confirmation), and the `PASS_WITH_WARNINGS` repair loop.
- `qb-subplanner` skill: Step 2 phase decomposition, launched automatically as a Cursor
  goal via the `define-goal` skill, that runs until every phase has a `Faz-<n>-Plans/` folder,
  sub-plans, and a `Sub-Planing-Index.md`.
- `qb-auditor` skill: Step 3 coverage/quality audit, launched automatically as a Cursor
  goal via the `define-goal` skill, producing `Sub-Planing-Audit.md`; safe to run standalone for
  re-audits.
- Goal-backed steps (2 and 3) use Cursor's `define-goal` skill automatically and in-session, with
  a graceful fallback to an in-context goal contract when the goal tool is unavailable.
- `/qb-plan` and `/qb-audit` commands.
- Bundled planner prompts co-located with their skills (`first-planner.md`, `second-planner.md`,
  `third-planner.md`).
