# Sub-Planning Index

## 1. Purpose

This index maps the eight high-level phases defined in `Planner-docs/Main-Planning.md` to the detailed Step-2 sub-plan files generated under `Planner-docs/Phase-<n>-Plans/`. It exists so that Step 3 (audit) and Step 4 (implementation) can navigate the decomposition, verify coverage of every master-plan phase, and pick a delivery order. Each sub-plan is a coherent delivery slice with its own goal, scope, acceptance criteria, validation approach, and transition criteria; this document is the table of contents and coverage proof over that set. It does not restate the master plan or the autopsy — it points to them.

## 2. Source Master Plan

Primary source of truth: `Planner-docs/Main-Planning.md` (supporting feedback: `Planner-docs/Autopsy.md`).

- **Detected phase count:** 8 (Phases 0–7), exactly as enumerated in Main-Planning §6 "Phased Master Roadmap".
- **Detected phase names:** 0 Autonomy Charter & Foundation; 1 Findings Model & Audit Engine; 2 Analyzer Suite; 3 Autonomous Hardening (Fixer); 4 Autonomy Orchestrator & Policy Engine; 5 Verification, Evidence & Reporting; 6 Multi-Host Parity & Headless/CI Mode; 7 Production Hardening, Observability & Self-Audit.
- **Ambiguity / inconsistency found:** None in phase ordering. One deliberate divergence from Main-Planning §9 is recorded transparently: §9 recommended decomposing only the foundational phases first, but the operator explicitly approved decomposing all eight phases now. Phases 5–7 are therefore present but planned at the lower detail level §9 prescribed, with their unresolved decisions marked as deferred (see §5 below). The product-identity pivot (gated planning workflow → autonomous audit/hardening tool) is consistent across all sub-plans.

## 3. Phase and Sub-Plan Map

**Phase 0 — Autonomy Charter & Foundation** (maturity M0→M1). Defines what "full autonomous" safely means before any code. Recommended order: 0.1 → 0.2 → 0.3 (hard dependency chain).
- `Planner-docs/Phase-0-Plans/Phase0.1-autonomy-model-and-levels.md` — Autonomy Model and Levels (A0–A3)
- `Planner-docs/Phase-0-Plans/Phase0.2-safety-invariants-and-non-regression.md` — Safety Invariants and Planning-Product Non-Regression Contract
- `Planner-docs/Phase-0-Plans/Phase0.3-policy-and-budget-concept.md` — Policy and Budget Concept

**Phase 1 — Findings Model & Audit Engine** (M1→M2). The contract every later phase binds to. Recommended order: 1.1 → 1.2 → 1.3 → 1.4.
- `Planner-docs/Phase-1-Plans/Phase1.1-finding-schema.md` — Freeze the Finding Schema
- `Planner-docs/Phase-1-Plans/Phase1.2-analyzer-interface.md` — Pluggable Read-Only Analyzer Interface
- `Planner-docs/Phase-1-Plans/Phase1.3-validator-refactor-reuse.md` — Refactor the Validator Behind the Analyzer Interface
- `Planner-docs/Phase-1-Plans/Phase1.4-audit-engine-runner-and-output.md` — Audit Engine Runner and Output Convention

**Phase 2 — Analyzer Suite** (M2). Real security/quality/correctness coverage behind structured command schemas. Recommended order: 2.1 → 2.2 → 2.3 → 2.4 (2.2 establishes the structured argv command-schema convention that 2.3 and 2.4 reuse).
- `Planner-docs/Phase-2-Plans/Phase2.1-secret-and-credential-analyzer.md` — Secret and Credential Analyzer
- `Planner-docs/Phase-2-Plans/Phase2.2-command-exec-and-injection-analyzer.md` — Command-Execution and Injection Analyzer
- `Planner-docs/Phase-2-Plans/Phase2.3-quality-and-correctness-adapters.md` — Quality and Correctness Adapters (Offline)
- `Planner-docs/Phase-2-Plans/Phase2.4-dependency-and-supply-chain-analyzer.md` — Dependency and Supply-Chain Analyzer (Opt-In Networked)

**Phase 3 — Autonomous Hardening (Fixer)** (M2→M3). Finding-driven fixes with isolation, verification, and rollback. Recommended order: 3.1 → 3.2 → 3.3 → 3.4 (3.1 defines the unit of work that 3.2's isolation/rollback runtime operates on, per each sub-plan's §10 dependencies).
- `Planner-docs/Phase-3-Plans/Phase3.1-fix-strategy-and-finding-binding.md` — Fix Strategy and Finding Binding
- `Planner-docs/Phase-3-Plans/Phase3.2-isolation-and-rollback-runtime.md` — Isolation and Rollback Runtime (Net-New)
- `Planner-docs/Phase-3-Plans/Phase3.3-verification-gate-and-keep-revert.md` — Verification Gate and Keep/Revert Decision
- `Planner-docs/Phase-3-Plans/Phase3.4-fix-safety-eval-and-fixtures.md` — Fix-Safety Eval and Fixture Repos

**Phase 4 — Autonomy Orchestrator & Policy Engine** (M3→M4). Policy-bounded, fail-closed autonomy replacing per-gate clicks. Recommended order: 4.1 → 4.2 → 4.3 → 4.4.
- `Planner-docs/Phase-4-Plans/Phase4.1-policy-schema-and-engine.md` — Policy Schema and Engine
- `Planner-docs/Phase-4-Plans/Phase4.2-autonomy-levels-enforcement.md` — Autonomy Level Enforcement
- `Planner-docs/Phase-4-Plans/Phase4.3-budgets-and-killswitch.md` — Budgets and Kill-Switch
- `Planner-docs/Phase-4-Plans/Phase4.4-role-separation-and-cross-review.md` — Role Separation and Cross-Review

**Phase 5 — Verification, Evidence & Reporting** (M4). Machine-readable, reproducible, cross-reviewed output. Recommended order: 5.1 → 5.2 → 5.3.
- `Planner-docs/Phase-5-Plans/Phase5.1-run-state-and-evidence-store.md` — Run-State and Evidence Store
- `Planner-docs/Phase-5-Plans/Phase5.2-machine-readable-reporting.md` — Machine-Readable Reporting (JSON/SARIF)
- `Planner-docs/Phase-5-Plans/Phase5.3-reproducibility-and-provenance.md` — Reproducibility, Provenance, and Cross-Review Integration

**Phase 6 — Multi-Host Parity & Headless/CI Mode** (M4→M5). One engine on all hosts plus headless CI, preserving monorepo invariants. Recommended order: 6.1 → 6.4 → 6.2 → 6.3.
- `Planner-docs/Phase-6-Plans/Phase6.1-shared-source-of-truth-extension.md` — Extend the Shared Source of Truth and Sync Map
- `Planner-docs/Phase-6-Plans/Phase6.2-host-launch-adapters.md` — Per-Host Launch Adapters for Audit + Harden
- `Planner-docs/Phase-6-Plans/Phase6.3-headless-cli-and-ci-exit-codes.md` — Headless CLI and CI Exit Codes
- `Planner-docs/Phase-6-Plans/Phase6.4-manifest-and-structure-consistency.md` — Manifest and Structure Consistency

**Phase 7 — Production Hardening, Observability & Self-Audit** (M5→M7). Safe, observable, recoverable unattended operation; QB hardens QB. Recommended order: 7.1 → 7.2 → 7.3 → 7.4.
- `Planner-docs/Phase-7-Plans/Phase7.1-telemetry-and-metrics.md` — Telemetry and Quality Metrics
- `Planner-docs/Phase-7-Plans/Phase7.2-backup-rollback-and-release-gates.md` — Backup/Rollback Drills and Release Gates
- `Planner-docs/Phase-7-Plans/Phase7.3-least-privilege-and-supply-chain.md` — Least Privilege and Supply-Chain Safety
- `Planner-docs/Phase-7-Plans/Phase7.4-self-audit-and-runbook.md` — Self-Audit, Kill-Switch Runbook, and Production Gate

## 4. Prioritized Elaboration Order

Implementation should follow the master roadmap's sequence, with security and contract work front-loaded:

1. **Contracts first (Phase 0 → Phase 1).** Ratify the autonomy charter and safety invariants, then freeze the `Finding` schema and analyzer interface. Nothing downstream is safe to build against an undefined contract (AUTOPSY-P0-01).
2. **Security-sensitive core (Phase 2 → Phase 3).** Build the analyzer suite, treating the structured argv command-schema convention and path-containment (Phase 2.2) as the security backbone every later process invocation depends on; then the fixer, ensuring the net-new isolation+rollback runtime (Phase 3.2) is in place before any write-capable autonomy is enabled in Phase 4 (AUTOPSY-P0-02).
3. **Autonomy under policy (Phase 4).** Only after fixes are provably reversible and verified should the policy engine, autonomy-level enforcement, budgets/kill-switch, and cross-review be wired in.
4. **Evidence and reporting (Phase 5).** Run-state, machine-readable reports, and reproducibility make the autonomous behavior trustworthy and CI-consumable.
5. **Portability (Phase 6).** Extend `shared/` and the sync map, resolve manifest/structure drift, add per-host launch adapters and headless CI.
6. **Production readiness (Phase 7).** Telemetry, rollback drills, least-privilege/supply-chain review, and a clean self-audit gate live activation.

This mirrors the master plan's principle of prioritizing security and operational safety before live automation.

## 5. Out-of-Scope or Deferred Topics

These depend on unresolved decisions and are intentionally planned at lower detail until earlier phases land:

- **Default autonomy level and whether A3 (commit/PR/deliver) is ever a default** — requires human ratification (Main-Planning §9a); Phases 0.1/0.3 flag it as to be confirmed during implementation rather than deciding it now.
- **Networked CVE analyzer scope for v1** (Phase 2.4) — the offline tier is in scope; the opt-in networked tier is default-off and its v1 inclusion is deferred to a human decision (Main-Planning §9b).
- **Output-directory naming and whether planning and auditing share one tree or two** (`QB-Audit/` is a working name; Main-Planning §9c) — frozen as a validator-checked identifier only after the Phase-0 output-convention decision.
- **Phases 5–7 deep detail** — present for completeness but deliberately shallower per Main-Planning §9; they will be re-elaborated once Phases 0–4 contracts are stable.
- **Production deployment, real external mutation, auto-merge, and broad credential access** — excluded from planning until explicit approval gates exist (Phase 4) and release gates pass (Phase 7).

## 6. Coverage Check

- [x] Every main phase from `Main-Planning.md` (0–7) has a `Planner-docs/Phase-<n>-Plans/` folder — 8/8 folders present.
- [x] Every main phase has at least one sub-plan — 30 sub-plans total (Phase 0: 3; Phases 1–4: 4 each; Phase 5: 3; Phases 6–7: 4 each), with contiguous numbering 1..N per phase and no gaps.
- [x] Every sub-plan filename follows the `Phase<n>.<m>-<ascii-kebab-slug>.md` convention (verified — all conform).
- [x] Every sub-plan referenced in §3 above maps to a real file, and every generated file is referenced in §3 (no orphans, no dangling references).
- [x] All generated documents are written in English.
- [x] No source-code files were modified — only files under `Planner-docs/` were created.
- [x] No secrets, tokens, credentials, or private keys were written into any plan file.

## 7. Repository Inspection Notes

- **Commands run (read-only):** directory walks of `Planner-docs/Phase-*-Plans/`; per-phase file counts and filename-convention regex checks; a placeholder/secret grep across all sub-plans; and `git status --short` to confirm only `Planner-docs/` changed. Each phase subagent independently ran `find`, read `Main-Planning.md` and `Autopsy.md`, and self-checked its files' headings before returning.
- **Important files inspected:** `Planner-docs/Main-Planning.md` and `Planner-docs/Autopsy.md` (source and supporting feedback); the reuse seeds referenced throughout the sub-plans — `shared/scripts/validate_planner_docs.py`, `platforms/*/skills/qb-implementer/fourth-planner.md`, `scripts/sync.sh`, the `tests/` suite, and `.github/workflows/validate.yml`.
- **Assumptions made:** that `QB-Audit/` is a working name pending the Phase-0 output-convention decision; that the planning product must keep functioning unchanged (non-regression); and that decomposing all eight phases now (operator-approved) supersedes the foundational-first recommendation in Main-Planning §9, with Phases 5–7 kept intentionally shallower.
- **Things not verified:** the full internal behavior of `sync.sh` and each platform `validate.sh`; the Cursor and Codex launch mechanisms in depth; and the exact behavior of all invariant test modules — these are flagged for Step-3 scrutiny and Step-4 implementation evidence. No secrets or environment values were read into any plan.
