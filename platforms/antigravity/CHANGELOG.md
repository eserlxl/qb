# Changelog

All notable changes to QB are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.21.1] - 2026-06-23

### Changed
- Harden the public_privacy release guard with focused tests for its CLI surface (scan_paths file I/O and main exit codes).

## [0.21.0] - 2026-06-21

### Changed
- Add a planner coverage-awareness gate so QB stops minting work items that a passing test already covers: threaded through every planner stage (assessment, first, second, export, third, fourth) across all four platforms, it keys on a read-confirmed assertion plus the verification command's pass/fail rather than a name match, cites the covering test on every drop, and treats skipped/failing/non-asserting tests as not coverage. Persist a per-run telemetry trend artifact (telemetry-trends.json report + telemetry-trends.txt summary) in the headless run finale via RunStore.emit_trend_artifacts(), rendered fail-soft on a thin series and fanned byte-equal to the three engine hosts. Ratchet the optional make coverage line-coverage floor 80 -> 84 with a recorded margin-below-measured policy. Harden the suite: guard the whole shared command-execution surface against multi-line shell-string spawns, pin the sync MAP remediation guidance, and self-document the BASELINE same-change count rule.

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
