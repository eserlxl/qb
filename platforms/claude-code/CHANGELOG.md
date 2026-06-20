# Changelog

All notable changes to QB are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.18.0] - 2026-06-20

### Added
- Planner enhancements: a v2 planning ledger, a project ontology, a probe-policy, and a task-delegation playbook, plus a confidence + evidence taxonomy and a seven-scenario planning corpus.
- Tracked-file secret-hygiene scan in all four platform validators — each `validate.sh` scans its package for committed credentials and fails with a uniform `tracked_secret_hygiene_failed` token, covered by per-host tests.

### Fixed
- The planner-doc validator now masks only balanced code fences, so a dangling fence can no longer hide fix-list findings; the Step 4 readiness gate no longer silently bypasses on legacy three-field audit rows, and accepted findings still gate Step 4.

### Changed
- Attribution now credits Alican Kiraz's ClaudeQB alongside CursorQB, CodexQB, and AntigravityQB.

## [0.17.0] - 2026-06-19

### Changed
- Broaden secret-hygiene coverage to GitHub OAuth/app/refresh tokens, Google API keys and OAuth client secrets, and GitLab/npm/SendGrid credentials, single-sourced into the repo-wide committed-secret guard; detect child_process.execSync as a shell-injection sink; skip non-registry npm dependencies (git/file/link/workspace/url) to remove false unpinned findings; harden the release-gate and recoverability evidence readers to degrade gracefully on malformed records; and make the audit engine clean under its own QualityAnalyzer.

## [0.16.0] - 2026-06-19

### Changed
- Telemetry trends CLI (make trends) over the multi-run aggregate series, headless telemetry.json emission, a fail-closed precision/recall threshold gate (make precision), and a governed Antigravity reference inventory

## [0.15.0] - 2026-06-17

### Changed
- Phase 7-8 hardening: production-gate signal assembly + headless entrypoint and per-conjunct operator procedure; redacted evidence records (release-gate authorization, self-audit, recoverability, production-gate); accepted-findings register + reconciliation; CI least-privilege + opt-in pre-push gate-of-record; governance docs (SECURITY/CONTRIBUTING/CODEOWNERS/templates); changelog+versioning guards; and a deterministic release-integrity manifest with an end-to-end release runbook

## [0.14.1] - 2026-06-16

### Changed
- Gate qb planwright export on verified implementation items; drop legacy phase-3 verification docs

## [0.14.0] - 2026-06-16

### Changed
- bump-version.sh now keeps the root README version badge in lockstep with VERSION; make check enforces it via test_doc_consistency.py.

## [0.13.0] - 2026-06-16

### Changed
- Parallelize per-phase planning (Steps 2/3 sub-planning and audit, plus Step 3.5 export) with map/reduce subagent fan-out; add read-only Step 1 evidence fan-out

## [0.12.0] - 2026-06-16

### Changed
- Add Antigravity (Gemini) as the fourth supported platform: a planning-only, manifest-less Agent Skill converted to QB house format.

## [0.11.0] - 2026-06-16

### Changed
- Auto-mode planning (`/qb-plan auto`) now mandates independent subagent (Task-tool) delegation of every step — above all the Step 3 audit: a caller that trusts `QB_PLAN_AUTO_OK` is trusting that the audit was independent, so an in-session self-audit by the plan's own author is no longer treated as equivalent. The in-session path is a degraded fallback used only when the Task tool is genuinely unavailable, and must then disclose `QB_PLAN_AUTO_WARN: in-session fallback — audit not independently delegated` before the result line so consumers can downgrade trust. Also formalizes the Step-0 guard that adds `.qb/` to the target repo's .gitignore at planning start.

## [0.10.0] - 2026-06-15

### Changed
- Complete analyzer coverage with license-hygiene and config-hygiene analyzers (every producible finding category now has a producer); enforce the earned-autonomy ceiling at the run chokepoint (cold start promotes nothing above A1); minimize the verification subprocess environment so repo code never inherits QB secrets; linear-time secret/command line scanning; plus fail-closed engine hardening (findings redaction, promotion correctness, gate coercion, broadened secret patterns) and per-platform CI-gate parity.

## [0.9.0] - 2026-06-15

### Changed
- Add `scripts/bump-version.sh`: lockstep version bumps across VERSION, all three platform manifests, every SKILL.md frontmatter, and all CHANGELOGs, with a `--sync` drift-repair mode.

## [0.8.0] - 2026-06-15

### Added

- **`/qb-plan auto` — non-interactive planning mode.** Passing the `auto` flag runs the whole
  planning workflow without prompting: it auto-derives the four Step-1 intake fields from the
  repository and **fails closed** if any is missing (prints
  `QB_PLAN_AUTO_ERROR: missing required field(s): …` and stops), auto-passes Gate 1 and Gate 2,
  skips the gated Step 4 implementation, produces and validates `.qb/plan.md`, and prints a
  single deterministic result line (`QB_PLAN_AUTO_OK:` / `QB_PLAN_AUTO_ERROR:`) so an external
  caller such as planwright can detect success. Auto mode writes only under `.qb/` and never
  modifies source code, commits, pushes, or opens PRs.
- **Repo-aware auto-intake fast path.** On a well-structured repository (at least three of five
  signals: a README, a manifest/build file, a source directory, a tests directory, a CI config),
  Step-1 intake auto-derives all four fields and asks a single consolidated confirmation instead
  of one question per field; weak-evidence fields fall back to per-field prompts. In `auto` mode
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

- **Step 5 — automatic planwright-format plan export.** Every planning run now closes by
  projecting the `.qb/` sub-plans into a flat, execution-ready `.qb/plan.md` in planwright's
  8-field checkbox item format (one item per Planned Work Breakdown entry, across all phases),
  so a QB plan can be handed to planwright's `execute` / `cycle` without re-planning. A new
  bundled read-only validator, `scripts/validate_planwright_plan.py`, gates the export against
  the machine-checkable subset of planwright's plan linter (a plan that passes it is accepted
  by planwright on hand-off). New spec `export-planner.md`. Hand-off:
  `cp .qb/plan.md .planwright/plan.md` then run planwright `execute` (or `cycle <N>`).

### Changed

- **BREAKING (Claude Code distribution) — the Claude Code package is now
  plugin-only.** It no longer ships a marketplace manifest; both the root
  `.claude-plugin/marketplace.json` and the package-local
  `platforms/claude-code/.claude-plugin/marketplace.json` were removed. QB is now
  published through the dedicated [`eserlxl/claude-marketplace`](https://github.com/eserlxl/claude-marketplace)
  aggregator repo, which references this package with a `git-subdir` source and
  also offers `planwright`.
  - **Install changed:** `/plugin marketplace add eserlxl/claude-marketplace` then
    `/plugin install qb@eserlxl` (previously `/plugin marketplace add eserlxl/qb`).
  - **Why:** a Claude Code marketplace is keyed by the `name` inside its manifest,
    not by the repo. `eserlxl/qb` and `eserlxl/planwright` both declared a
    marketplace named `eserlxl`, so adding both made the second overwrite the
    first. A single aggregator repo owns the `eserlxl` name; the plugin repos no
    longer compete for it.
  - Cursor and Codex are unaffected — they remain self-hosted marketplaces.

## [0.3.0] - 2026-06-15

### Changed

- **BREAKING — unified naming: per-host `*qb` identifiers collapsed to `qb`.** The
  Claude Code, Cursor, and Codex packages now share one product name (`QB`), one plugin
  `id` (`qb`), and one command/skill namespace. Upstream attribution to Alican Kiraz's
  original CursorQB and CodexQB projects is preserved verbatim.
  - Commands: `/claudeqb-{plan,assessment,audit,implement}` → `/qb-{plan,assessment,audit,implement}`
  - Skills: `claudeqb-{planner,subplanner,auditor,implementer,assessment}` → `qb-*`
  - Agents: `claudeqb-{subplanner,auditor,implementer,assessment}` → `qb-*`
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
  existing projects and Gate 1 feedback covers both `Main-Planing.md` and `Assessment.md`.
- `qb-assess` skill + `/qb-assess` command (Step 1.5): an existing-project assessment that
  writes a 13-section `Planner-docs/Assessment.md` technical feedback report, run automatically after Step 1
  for existing/non-empty repositories and skipped for empty ones.
- `qb-subplanner` skill (Step 2): phase decomposition into `Planner-docs/Faz-<n>-Plans/` sub-plans
  plus `Sub-Planing-Index.md`, requiring full relative-path index references and all-file validation. It
  reads `Planner-docs/Assessment.md` as an optional supporting source.
- `qb-auditor` skill + `/qb-audit` command (Step 3): a coverage/quality audit producing
  `Planner-docs/Sub-Planing-Audit.md` with a `PASS` / `PASS_WITH_WARNINGS` / `BLOCKED` status; safe to run
  standalone for re-audits.
- `qb-implementer` skill + `/qb-implement` command (Step 4): a gated implementation of one
  bounded, reversible slice from a `READY` sub-plan, only when the audit is not `BLOCKED` and has no P0/P1
  findings.
- `/qb-plan` command to run the full multi-step workflow from the start.
- Goal-backed steps adapted to Claude Code: the orchestrator delegates each long autonomous step
  (Step 1.5, 2, 3, 4) to a matching subagent — `qb-assess`, `qb-subplanner`,
  `qb-auditor`, `qb-implementer` under `agents/` — via the Task tool, passing the step's goal
  contract (objective / success evidence / scope bounds / stop condition) and the absolute path to the
  bundled spec. If subagents or the Task tool are unavailable, it falls back to running the step's skill
  in-session under the identical in-context goal contract.
- Bundled planner prompts co-located with their skills: `planners/first-planner.md`, `assessment-planner.md`,
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
  `Planner-docs/`, `Main-Planing.md`, `Assessment.md`, `Sub-Planing-Index.md`, `Sub-Planing-Audit.md`,
  `Faz-<n>-Plans/`, and `Faz<n>.<m>-*.md`, including the intentional `Planing` spelling.
- Documentation: `README.md`, `docs/INSTALLATION.md`, `docs/USAGE.md`, and `docs/MAINTAINING.md`.
