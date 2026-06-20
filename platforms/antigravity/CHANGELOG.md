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

### Added
- Antigravity platform build of QB: a native Antigravity Agent Skill (`skills/qb/`)
  that runs the repo-aware planning workflow — main plan, Step 1.5 assessment with
  optional project-ontology and planning-ledger memory, vibecoding-first phase
  sub-planning, a coverage/quality audit, and a gated implementation handoff. Ported
  from the standalone AntigravityQB project onto QB's naming conventions: `qb`
  identity, `.qb/` artifacts (`main-planning.md`, `assessment.md`,
  `sub-planning-index.md`, `sub-planning-audit.md`, `phase-N-plans/phase-N.M-*.md`),
  and the bundled read-only `validate_planner_docs.py`. Installs into the supported
  Antigravity/Gemini skill locations via `scripts/install.sh`.
