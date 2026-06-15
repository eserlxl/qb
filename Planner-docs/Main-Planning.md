# Main Planning

## 1. Executive Summary

QB is today a zero-setup, in-session, **gated planning workflow** shipped as a native plugin for three AI coding hosts (Claude Code, Cursor, Codex). It guides a user from a fuzzy idea to a reviewed, build-ready plan through five steps (master plan, autopsy, sub-plans, audit, one gated implementation slice), writing fixed-name artifacts under `Planner-docs/` and validating each step with a bundled, dependency-free, read-only Python checker.

The requested direction is a product pivot: **convert QB into a full autonomous auditing and hardening tool.** Instead of (or in addition to) helping a human plan a project, QB should autonomously inspect a target repository for security, quality, and correctness defects, then apply safe hardening fixes with verification and evidence — running end-to-end with minimal human intervention.

The most important planning conclusion is that QB is unusually well-positioned for this pivot because it already contains the two hardest seeds in primitive form. The bundled validator (`scripts/validate_planner_docs.py`) is a fail-closed, severity-graded (P0–P3), evidence-producing analyzer — today scoped to planning documents, but structurally a real audit engine. The Step-4 implementer is already a discipline for "make one minimal, reversible change, determine the validation command first, verify before claiming done." The pivot is therefore primarily a **generalization and orchestration** effort, not a from-scratch build: widen the analyzer's scope from `Planner-docs/` to the whole repository, generalize the implementer into an autonomous fixer, and add an autonomy/policy layer on top.

The central design tension that this plan must resolve is that QB's current identity is built on the rule "pause for explicit human approval at every gate," while the new goal is "full autonomous." These are reconciled not by deleting safety but by **moving from human-in-the-loop to policy-bounded human-on-the-loop**: an explicit autonomy model (levels A0–A3) where what may be auto-applied is governed by finding severity, confidence, a declared policy, and mandatory per-fix verification with automatic rollback — and where the system fails closed when a policy or budget boundary is hit.

Current maturity for the *new* goal is approximately M1: the planning product itself is mature and well-tested (12 cross-platform invariant test modules, a clean `make check`, CI on every PR and push to `main`), but the auditing-and-hardening product is at the contract/seed stage — the analyzer exists only for docs, there is no code-finding schema, no autonomous fixer, and no autonomy/policy engine.

The single most important next milestone is **Phase 1: a code-aware findings model and a generalized audit engine** — a structured `Finding` schema plus the ability to run read-only analyzers over an arbitrary repository and emit graded, evidence-backed findings. Everything downstream (the fixer, the orchestrator, reporting) depends on that contract existing first.

This plan keeps QB's proven invariants intact through the transition: `shared/` remains the single source of truth materialized byte-for-byte into each platform, the tooling stays dependency-light and fail-closed, and no destructive or external-mutation behavior (commit/push/PR/deploy) happens without explicit opt-in — now expressed as autonomy policy rather than per-step human clicks.

## 2. Project Vision

QB should become a **trustworthy autonomous code auditor and hardener**: point it at a repository, and it discovers security, quality, and correctness defects, prioritizes them with evidence, and — within a declared safety policy — fixes the ones it can fix safely, proving each fix with a verification command and leaving a complete audit trail.

The intended users and operators are individual developers who want an unattended "harden my repo" pass inside their AI coding host, and engineering teams who want QB to run headless in CI as an automated audit-and-remediation gate. The same workflow must serve both an interactive single-developer session and an unattended pipeline run.

The engineering value is a single, host-portable engine that turns the ad-hoc, manual loop of "scan → triage → fix → verify" into a repeatable, policy-governed, evidence-producing automation that can run as often as desired without a human babysitting each step.

When finished, QB should make it possible to: (a) produce a graded, machine-readable audit of a repository (security, quality, correctness, supply chain); (b) autonomously remediate the safely-fixable subset with verified, reversible patches; (c) operate at a chosen autonomy level from "report only" to "fix and open a reviewable changeset"; and (d) do all of this identically across Claude Code, Cursor, and Codex, plus a headless CI mode.

What must never be compromised: **safety and reversibility**. QB must never apply an unverified change, must never act outside its declared policy, must fail closed on ambiguity, must never exfiltrate or write secrets, and must never commit/push/PR/deploy unless explicitly authorized for that run. Autonomy is earned through guardrails, not by removing them.

## 3. Current State Analysis

**Observed repository structure.** QB is a monorepo. `shared/` holds the canonical host-neutral intellectual property: the five planner specs (`planners/first|second|third|fourth|autopsy-planner.md`), two reference docs (`references/repo-aware-intake.md`, `references/workflow-quality.md`), and the validator (`scripts/validate_planner_docs.py`). `platforms/{claude-code,cursor,codex}` are hand-authored per-host packages containing byte-for-byte synced copies of the shared IP plus host-specific manifests, slash commands, skills, agents, and per-platform `validate.sh`. `scripts/sync.sh` materializes shared → platforms and `--check` enforces byte-equality. Top-level `tests/` holds 12 cross-platform invariant test modules; `.github/workflows/validate.yml` runs `make check` on PRs and pushes to `main`.

**Implemented / strongly evidenced.** The *planning* product is real and mature: the orchestrator skill, four delegated subagents (autopsy, subplanner, auditor, implementer), the four slash commands, and the validator are all present and consistent across three platforms. The validator is the standout asset — it already implements heading/structure validation, phase-folder and sub-plan coverage, index consistency, duplicate/gap numbering detection, audit-status extraction (`PASS` / `PASS_WITH_WARNINGS` / `BLOCKED`), P0–P3 severity counting that gates Step 4, length-bounded secret patterns (`sk-…{20,}`, `github_pat_…`, `ghp_…`, `AKIA…`, private-key headers), and a `--strict` mode that promotes warnings to failures. It is dependency-free and read-only.

**Partial / seed-stage for the new goal.** The Step-4 implementer (`fourth-planner.md`) encodes the right hardening discipline (one reversible slice, determine validation first, verify before done, no auto-commit) but is scoped to implementing *plan slices*, not remediating *audit findings*. There is no general code-finding schema, no analyzer abstraction, and no autonomy/policy layer.

**Documentation state.** Strong. Root README plus per-platform README/`docs/` (INSTALLATION, USAGE, MAINTAINING), CHANGELOGs, and clear attribution. Documentation describes a planning product, not an auditing tool — it will need a parallel track once the pivot lands.

**Test / CI state.** Good for the current product: `make check` runs sync-drift check, three per-platform `validate.sh`, and `python3 -m unittest discover -s tests` (12 modules, including secret-scan, cross-host-residue, sync-completeness, and a spec/validator contract test). CI mirrors this. However, **all current tests validate the planning product**; there is no test surface for code-auditing or autonomous-fix behavior because those do not exist yet.

**Configuration state.** Minimal and intentional: Makefile targets (`sync`, `check`, `test`, `export-sanitized`), `.gitignore`, plugin/marketplace manifests. No runtime configuration, because QB currently has no runtime beyond the host session and the validator script.

**Operational readiness (for the new goal).** Low. There is no headless entry point, no policy file format, no run-state/evidence store, no machine-readable report output (e.g. JSON/SARIF), and no telemetry. These are all required for "autonomous" and "CI-runnable."

**Security posture.** For its current scope, good: read-only validator, length-bounded secret scanning, a repo-wide committed-secret scan test, and a strict no-auto-commit/push/PR rule during planning. For the new goal the posture must expand substantially, because the tool will now *write code* autonomously and *analyze untrusted repositories* — introducing fix-safety, least-privilege, command-execution-safety, and supply-chain concerns that do not exist for a doc validator.

**Production readiness (for the new goal).** Not started. No autonomy levels, no rollback/backup mechanism beyond git, no kill-switch, no cost/iteration budgeting, no observability.

**Missing critical components for the pivot.** A structured `Finding` schema; a pluggable read-only analyzer suite over arbitrary repos; an autonomous fixer generalized from the Step-4 implementer; an autonomy/policy engine with fail-closed gates; a run-state and evidence/artifact store; machine-readable reporting; a headless/CI mode; and a test/eval harness for audit precision and fix safety.

## 4. Target End State

**Functional target.** `qb-audit` produces a graded, evidence-backed, machine-readable inventory of findings across an arbitrary repository (security, quality, correctness, supply chain). `qb-harden` autonomously remediates the safely-fixable subset, each fix minimal, reversible, and proven by a verification command. A single autonomy setting selects behavior from "report only" → "fix in working tree" → "fix and prepare a reviewable changeset."

**Technical target.** A host-neutral core in `shared/` defines the `Finding` schema, the analyzer interface, the fixer interface, and the policy schema. Analyzers are read-only and pluggable; fixers are write-capable but run in isolation (dedicated branch/worktree) with mandatory verification and automatic rollback on failure. Structured command schemas replace any shell-string execution. The existing planning workflow continues to work and shares the same validator/finding infrastructure.

**Operational target.** A headless mode runs the full audit→harden→report loop non-interactively for CI, with exit codes that gate a pipeline. Run state, per-finding evidence, and before/after artifacts are persisted under a fixed-name output directory (mirroring the `Planner-docs/` convention). Budgets (max findings, max fixes, max iterations, max wall-time/tokens) bound every run.

**Security target.** Least privilege by default; fail-closed on any policy/budget boundary; never write or print secrets; no commit/push/PR/deploy unless explicitly enabled for the run; fixers cannot touch paths outside the repo or outside policy-allowed globs; the tool is safe to run against untrusted repositories (no auto-execution of repo-provided scripts unless explicitly sandboxed and authorized).

**Testing/review/release target.** An eval harness measures audit precision/recall on fixture repos and fix-safety (every applied fix must keep the verification command green). Cross-review: the role that proposes a fix is separable from the role that verifies/reviews it, so the same model family is not the sole judge of its own change when cross-review matters. `make check` is extended to cover the new engine; CI gates merges on it.

**Observability/governance target.** Every run emits structured telemetry (findings by severity, fixes applied/reverted, false-positive signals, latency, token/cost) and a complete, reproducible audit trail. A documented autonomy policy and a kill-switch govern unattended operation. The multi-host invariants (sync-clean, plugin id `qb`, no cross-host residue, preserved artifact names) remain enforced.

## 5. Architectural Direction and Key Decisions

**Core system boundaries.** Introduce a clean separation of four roles, mirroring the architectural principles in QB's own first-planner guidance: (1) **Analyzers** — read-only, produce findings; (2) **Fixer** — write-capable, produces reversible patches under isolation; (3) **Verifier** — runs the per-fix validation command and decides keep/rollback; (4) **Orchestrator/Policy** — the control plane that decides what runs, at what autonomy level, within what budget, and when to stop. Reviewer is a distinct lens applied to fixes (ideally not the same role that authored them).

**Control plane vs adapter/runtime/tools.** The control plane is the host-neutral orchestrator + policy engine + run-state/evidence store, all defined in `shared/`. The host adapters (Claude Code subagents/Task tool, Cursor goals, Codex goal-mode, and a headless CLI) are thin launch mechanisms — exactly the pattern QB already uses for its planning steps.

**Source-of-truth decisions.** QB's *own* run-state and evidence artifacts are the source of execution truth for a run — not external issue trackers and not chat scrollback. This follows QB's existing principle of keeping task/attempt/artifact/review state in its own control plane. The `shared/` specs remain the single source of truth for behavior, materialized into platforms by `sync.sh`.

**Data/state ownership.** A fixed-name output directory (e.g. `QB-Audit/` alongside the established `Planner-docs/` convention) owns: the machine-readable findings file, the per-fix evidence/artifacts, the run log, and the final report. Names become validator-checked identifiers, like the current `Planner-docs/` names.

**Integration boundaries.** Analyzers may wrap external tools (linters, SAST, dependency/CVE scanners) but only through structured command schemas with explicit argument lists — never shell-string interpolation. External/network-dependent analyzers (e.g. CVE feeds) are opt-in and clearly separated from the offline, dependency-free core so the base tool keeps its zero-setup property.

**Security and policy boundaries.** A declarative policy governs: which finding categories/severities may be auto-fixed; required confidence thresholds; path/glob allowlists for writes; whether commit/push/PR is permitted; and budgets. The engine fails closed: unknown policy → report-only; verification fails → rollback; budget hit → stop and report.

**Artifact/evidence boundaries.** Every finding carries `id, category, severity (P0–P3), confidence, evidence (path:line), rationale, suggested-fix, fix-strategy`. Every applied fix carries the patch, the verification command and its before/after result, and a reversal handle (git ref). No fix is "done" without recorded verification evidence — a direct generalization of the current Step-4 rule.

**Human approval boundaries.** Autonomy levels: **A0 report-only** (no writes), **A1 propose** (writes to a throwaway branch/worktree, never to the working tree the user is on), **A2 apply-verified** (apply to working tree only fixes that pass verification, auto-revert the rest), **A3 deliver** (A2 plus prepare a reviewable changeset / optional PR — only when explicitly enabled). The default is conservative; "full autonomous" means A2/A3 under an explicit policy, not the absence of gates.

## 6. Phased Master Roadmap

| Phase | Name | Goal | Description | Desired end state | Maturity | Key acceptance signals |
|---|---|---|---|---|---|---|
| 0 | Autonomy Charter & Foundation | Define what "full autonomous" safely means for QB | Write the autonomy model (A0–A3), the safety invariants, the policy concept, and the new identity; decide naming/scope; keep planning product intact | A ratified design doc + invariants the rest of the plan is derived from | M0→M1 | Autonomy levels, fail-closed rules, and policy schema agreed; non-regression contract for the planning product stated |
| 1 | Findings Model & Audit Engine | A code-aware `Finding` schema + read-only audit over arbitrary repos | Generalize the validator's graded/evidence/secret machinery into a repository audit engine with a pluggable analyzer interface emitting structured findings | `qb-audit` emits graded, machine-readable, evidence-backed findings for a real repo | M1→M2 | Finding schema frozen; audit runs on fixture repos; deterministic findings output; validator reused, not duplicated |
| 2 | Analyzer Suite | Real security/quality/correctness coverage | Build offline analyzers (secret scan — already seeded, dangerous-command/shell-string patterns, path traversal, basic correctness/lint adapters) and opt-in networked analyzers (dependency/CVE) behind structured command schemas | A meaningful, extensible set of analyzers with categorized findings | M2 | ≥N analyzer categories live; opt-in/offline split honored; no shell-string execution; per-analyzer fixtures pass |
| 3 | Autonomous Hardening (Fixer) | Generalize Step-4 implementer into a finding-driven fixer | Per-finding fix planning; minimal reversible patches under git isolation; mandatory verification; auto-rollback on failure; per-fix evidence | `qb-harden` safely fixes the safely-fixable subset with verified, reversible patches | M2→M3 | Every applied fix keeps verification green; failed fixes auto-revert with evidence; zero out-of-policy writes |
| 4 | Autonomy Orchestrator & Policy Engine | Replace per-gate human clicks with policy-bounded autonomy | Policy schema + engine; autonomy levels A0–A3; severity/confidence thresholds; budgets; role separation (auditor/fixer/verifier/reviewer); human-on-the-loop notifications | End-to-end unattended run governed by an explicit, fail-closed policy | M3→M4 | A full A2 run completes unattended on a fixture; out-of-policy actions blocked; budgets enforced; kill-switch works |
| 5 | Verification, Evidence & Reporting | Machine-readable, reproducible, cross-reviewed output | Final audit + hardening report; JSON/SARIF output; provenance and reproducibility; cross-review of fixes by a separable role | A trustworthy, reproducible report consumable by humans and CI | M4 | SARIF/JSON validates; report reproducible from run-state; cross-review catches a seeded bad fix in eval |
| 6 | Multi-Host Parity & Headless/CI Mode | Ship the engine on all hosts + non-interactive CI | Keep `shared/` single-source-of-truth; adapt launch per host; add a headless CLI with pipeline exit codes; extend tests/CI and sync map | QB audits+hardens identically on Claude Code, Cursor, Codex, and headless CI | M4→M5 | Sync-clean across hosts; headless run gates a sample CI; invariant tests extended and green |
| 7 | Production Hardening, Observability & Self-Audit | Make unattended operation safe and observable at scale | Telemetry (findings/fixes/false-positives/latency/cost); git-based backup/rollback; release gates; least-privilege review; supply-chain safety of QB itself; QB hardens QB | A production-gated, observable, recoverable autonomous tool | M5→M7 | Telemetry emitted; rollback drills pass; QB's self-audit run is clean; documented kill-switch and runbook |

The phases are sequential and build on the current observed state — they do not restart QB from scratch. Phases 0–1 establish the contract; Phases 2–3 deliver the core capability; Phase 4 makes it autonomous; Phases 5–7 make it trustworthy, portable, and production-grade. A stabilization/hardening posture is built into Phases 4–7 before any "deliver / open PR" (A3) behavior is enabled.

## 7. Critical Risks and Gaps

- **Risk: Autonomous code changes cause regressions or damage.** Why it matters: the pivot's whole point is unattended writes, which is inherently dangerous. Likely impact: broken builds, silent behavioral changes, lost work. Mitigation: mandatory per-fix verification before keep, automatic rollback, git isolation (branch/worktree), conservative default autonomy (A0/A1), and a kill-switch — fail closed everywhere.

- **Risk: False positives drive bad fixes.** Why it matters: an analyzer that over-reports plus an autofixer equals confidently-wrong changes. Likely impact: noise, eroded trust, harmful patches. Mitigation: confidence scoring on findings, severity/confidence thresholds gating auto-fix, cross-review by a separable role, and an eval harness measuring precision before raising autonomy.

- **Risk: Identity/scope drift away from a coherent product.** Why it matters: QB is currently a *planning* tool; bolting on an auditor can produce two half-products. Likely impact: confused users, unmaintainable codebase, broken docs. Mitigation: Phase 0 charter, an explicit non-regression contract for the planning product, and shared infrastructure (one validator/finding model) rather than two parallel stacks.

- **Risk: The "zero-setup, dependency-free" property conflicts with real analyzers.** Why it matters: serious SAST/CVE scanning often needs external tools or network. Likely impact: either a weak auditor or a heavy install that betrays QB's promise. Mitigation: a strict offline-core / opt-in-networked split, structured command-schema adapters, and graceful degradation when an optional analyzer is absent.

- **Risk: Command-execution and untrusted-repo attack surface.** Why it matters: running analyzers/fixers and verification commands against arbitrary repos invites injection and malicious build scripts. Likely impact: arbitrary code execution on the operator's machine. Mitigation: structured command schemas (no shell-string exec), path-traversal protection, never auto-running repo-provided scripts without explicit sandboxed authorization, and least privilege.

- **Risk: Multi-host parity drift.** Why it matters: three hosts plus a headless mode multiply the surface where `shared/` and platform copies can diverge. Likely impact: inconsistent behavior, broken `make check`. Mitigation: keep `shared/` the only source of truth, extend `sync.sh` coverage and the sync-map completeness test, and gate every change on CI.

- **Risk: Secret/credential handling during deep code analysis.** Why it matters: the auditor now reads entire repos and may surface secrets. Likely impact: secret leakage into reports/logs. Mitigation: extend the existing length-bounded secret scanning, redact-by-default in all outputs, and never persist secret values to evidence artifacts.

- **Risk: Cost/runtime blowup in unattended mode.** Why it matters: an autonomous loop over a large repo can spin indefinitely or burn excessive tokens/compute. Likely impact: runaway cost, hung CI. Mitigation: hard budgets (max findings/fixes/iterations/wall-time/tokens) enforced by the orchestrator, with fail-closed stop-and-report.

- **Gap: No test/eval surface for the new behavior.** Why it matters: current tests only cover the planning product. Likely impact: unverifiable audit/fix quality. Mitigation: build fixture repos and an eval harness in Phase 1 and grow it every phase; treat audit precision and fix safety as release gates.

## 8. Prioritized Next Steps

1. **Ratify the Phase 0 autonomy charter**: write down autonomy levels A0–A3, the fail-closed invariants, the policy concept, and an explicit non-regression contract for the existing planning product. This is the highest-leverage decision because every later phase derives from it.
2. **Freeze the `Finding` schema** (id, category, severity P0–P3, confidence, evidence path:line, rationale, suggested-fix, fix-strategy) as host-neutral IP in `shared/`.
3. **Decide the output-directory convention and names** (e.g. `QB-Audit/…`) and register them as validator-checked identifiers, mirroring the `Planner-docs/` approach.
4. **Spike the audit engine** by refactoring the validator's graded/secret/evidence machinery behind an analyzer interface, then run it read-only over QB itself and one external fixture repo.
5. **Define the policy schema and budget model** (severity/confidence thresholds, write-path allowlists, commit/push permission, max findings/fixes/iterations/cost).
6. **Build 1–2 reference fixture repos** with known seeded defects to anchor the eval harness from the start.
7. **Prototype the fixer contract** by generalizing `fourth-planner.md` into a finding-driven, verify-before-keep, auto-rollback fix loop on a single safe category (e.g. a trivial lint/secret-hygiene fix).
8. **Plan the multi-host + headless launch surface** so parity and the sync map are designed in, not retrofitted.
9. **Draft the telemetry/evidence record format** so observability is captured from the first real run rather than added late.

## 9. Preparation Notes for Step 2

**Decompose first:** Phase 0 (charter) and Phase 1 (findings model + audit engine) — these define the contracts every other phase consumes and should be broken into concrete sub-plans with acceptance criteria, files to add under `shared/`, and validator/test changes.

**Decompose next:** Phase 2 (analyzer suite) and Phase 3 (fixer), since they deliver the core capability and have the most security-sensitive details (command schemas, isolation, rollback).

**Do not expand yet:** Phases 5–7 (reporting/SARIF, multi-host/headless, production observability) beyond rough shape — they depend on decisions locked in Phases 0–4 and would churn if detailed now. Phase 4 (orchestrator/policy) should be decomposed only after the Finding schema and fixer contract are stable.

**Evidence Step 2 should collect:** the exact internal structure of `validate_planner_docs.py` (its `ValidationState`, severity counting, and secret-scan functions) to maximize reuse; the precise sync-map mechanics in `scripts/sync.sh` and the sync-completeness test; the per-host launch mechanisms already used for delegated planning steps; and the current test contract in `tests/` so new tests follow existing conventions.

**Decisions needing human confirmation before detailed implementation:** (a) the default autonomy level and whether A3 (PR/commit) is ever enabled by default; (b) whether networked analyzers (CVE feeds) are in scope for v1 or deferred; (c) the output-directory name and whether the planning and auditing products share one tree or two; (d) how aggressively to refactor the existing validator vs. wrap it; (e) the supported headless/CI surface for v1.

## 10. Repository Inspection Notes

**Important files inspected:** `README.md` (product description, workflow table, monorepo layout, attribution); `platforms/claude-code/.claude-plugin/plugin.json` (id `qb`, v0.3.0, planning description); the four commands (`qb-plan|audit|autopsy|implement`); the orchestrator skill `skills/qb-planner/SKILL.md` and bundled `planners/first-planner.md`; `skills/qb-autopsy/autopsy-planner.md`; the reference docs `references/repo-aware-intake.md` and `references/workflow-quality.md`; `Makefile`; and `scripts/validate_planner_docs.py` (CLI surface and check categories).

**Important commands run (read-only):** `git status --short --branch`, `git log --oneline -n 12`, directory tree walks of `platforms/`, `shared/`, and `tests/`, and targeted `grep` over the validator for its argparse modes, function definitions, severity/status logic, and secret patterns.

**Important existing docs found:** root and per-platform READMEs, per-platform `docs/` (INSTALLATION, USAGE, MAINTAINING), CHANGELOGs, and `.github/workflows/validate.yml`.

**Important assumptions made:** that "full autonomous auditing and hardening tool" means generalizing scope from planning documents to whole repositories while preserving QB's safety, zero-setup, and multi-host invariants; that the existing validator and Step-4 implementer are the intended reuse seeds; and that the planning product should continue to function (non-regression) rather than be removed.

**Things not verified:** the full internal implementation of `validate_planner_docs.py` beyond its CLI/structure grep; the complete contents of `sync.sh` and each platform `validate.sh`; the Cursor and Codex launch mechanisms in depth; and the exact behavior of all 12 test modules. These are flagged for Step 2 evidence collection. No secrets or environment values were read into this plan.
