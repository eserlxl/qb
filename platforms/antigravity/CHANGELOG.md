# Changelog

All notable changes to QB are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
