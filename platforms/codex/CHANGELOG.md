# Changelog

All notable changes to QB are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.20.0] - 2026-06-21

### Changed
- Add a container-config analyzer (Dockerfile / compose / k8s misconfiguration detection) and a manifest-undeclared-license rule to the license analyzer across all four platforms; isolate per-analyzer crashes so one failing analyzer no longer aborts a headless run; fix SARIF/report evidence-location parsing to split on the last colon and to accept paths containing spaces; fail the release-manifest --check closed on missing tracked files and traverse nested manifests; anchor the supply-chain signal in the production-gate engine inventory; raise ProcessGroupKillError on a failed process-group kill; document the tomllib (Python 3.11+) contract with TOML-fallback tests; and enforce an 80% line-coverage floor in the Makefile gate.

## [0.19.0] - 2026-06-20

### Added
- Dependency analyzer now audits Cargo `[workspace.dependencies]` and `[target.*.dependencies]` tables and PEP 735 `[dependency-groups]`, and flags a `pyproject.toml` that declares dependencies without a Python lockfile (`poetry.lock` / `pdm.lock` / `uv.lock` / `Pipfile.lock`) — extending the unpinned-dependency and missing-lockfile supply-chain checks across the Rust and Python ecosystems.
- Workflow-action analyzer now detects `uses:` in the named-step form (`- name:` then an indented `uses:`) and in reusable-workflow calls, not only the first-key `- uses:` form, so a named step's unpinned action is no longer missed.

### Fixed
- Dependency analyzer no longer raises on a TOML-valid `pyproject.toml` whose `project` or `tool` is a scalar (the offline tier fails closed to no findings), and no longer reports a false unpinned finding for a Poetry git/path dependency declared as an inline table without a version.
- The policy loader (`load_policy`) now fails closed to the default A0 policy on a malformed-field coercion error (for example a non-numeric `schema_version`), honoring its documented "fail closed on any problem" contract instead of raising.

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
