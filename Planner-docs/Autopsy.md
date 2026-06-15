# Project Autopsy

## 1. Executive Summary

This is an existing, mature, well-tested project — but its maturity is for the
*current* product, not the *new* goal. QB today is a zero-setup, in-session,
gated **planning workflow** shipped as a native plugin for three AI coding hosts
(Claude Code, Cursor, Codex). The strongest repository evidence for that current
product is unambiguous: a 592-line dependency-free read-only validator
(`shared/scripts/validate_planner_docs.py`), a byte-for-byte sync mechanism
(`scripts/sync.sh` with a `--check` mode and a completeness guard), 13 Python
test modules under `tests/`, a single-target CI workflow
(`.github/workflows/validate.yml` running `make check`), and a complete
documentation set (root + per-platform READMEs and `docs/`). A repo-wide secret
scan over tracked source returned zero matches.

The Step-1 master plan (`Planner-docs/Main-Planning.md`) sets a deliberate
**product pivot**: convert QB from a human-gated planning assistant into a
**full autonomous auditing and hardening tool** — autonomously inspect an
arbitrary repository for security/quality/correctness defects, then apply safe,
verified, reversible hardening fixes under an autonomy policy (levels A0–A3),
fail-closed, multi-host plus headless/CI. This autopsy assesses how ready the
*current* repository is to become *that* tool.

The honest maturity verdict for the NEW goal is early/seed stage (roughly the
plan's own "M1"). The pivot is well-founded because the two hardest seeds exist
in primitive form. The validator is structurally a real audit engine: it already
has a fail-closed `error`/`warning` state machine (`ValidationState`), P0–P3
severity counting (`count_audit_severities`), length-bounded secret patterns
(`SECRET_PATTERNS` + `scan_secrets`), and evidence-producing messages. The
Step-4 implementer (`shared/planners/fourth-planner.md`) encodes the right fixer
discipline: one minimal reversible slice, determine the validation command first,
verify with fresh evidence before claiming done, no auto-commit/push/PR.

However, every *generalized* capability the new goal requires is absent. There is
no code-aware `Finding` schema, no analyzer interface over arbitrary repos, no
autonomous fixer driven by findings, no policy/autonomy engine, no run-state or
evidence store, no machine-readable (JSON/SARIF) output, no headless/CLI entry
point, and no fixture repos or eval harness. The validator is hard-bound to
`Planner-docs/` paths and planning-document headings; its severity counter only
reads severities out of a planning audit document, not out of code analysis. The
fixer discipline exists only as prose in a planner spec and notably does **not**
yet include the git-isolation (branch/worktree) mechanism that Main-Planning
§5/§7 declares mandatory for safe autonomous writes.

The most important technical gaps for the pivot are therefore: (1) no structured
finding contract — the single dependency every downstream phase needs; (2) no
isolation+rollback runtime for write-capable fixes; (3) no policy/budget engine
to make "autonomous" safe and bounded; and (4) no test/eval surface for audit
precision or fix safety, since 100% of the current test suite validates the
planning product.

A secondary class of findings concerns multi-host parity. The three platform
packages are not symmetric. `platforms/codex` uses a different directory shape
(`plugins/qb/skills/qb/...` with capitalized reference filenames and an
`agents/openai.yaml`) and a 262-line `validate.sh` versus ~131 lines for
claude-code/cursor. The `qb` plugin version differs across manifests
(claude-code `0.3.0`, cursor `0.6.0`, codex `0.3.0`). These are not byte-drift of
the synced shared files (the sync contract covers those), but structural and
metadata asymmetries that will multiply risk once a write-capable engine ships on
all hosts plus a fourth headless surface.

The most important planning implication for Step 2 is to **decompose the contract
phases first and reuse, not rebuild**. Phase 0 (autonomy charter) and Phase 1
(Finding schema + generalized audit engine) define the interfaces every later
phase consumes. Step 2 sub-plans should be written so the existing validator's
state machine, severity counter, and secret scanner are *factored out behind an
analyzer interface* rather than duplicated, and so the fourth-planner discipline
is promoted into an executable fixer contract that adds the missing isolation and
rollback. The planning product must be preserved (non-regression) and the
`shared/`→`platforms/` single-source-of-truth invariant must be extended, not
broken, by every new artifact.

## 2. Inspected Sources

**Primary source (read, not modified):**
- `Planner-docs/Main-Planning.md` — the Step-1 master plan (155 lines, 10
  numbered sections) defining the autonomous audit+harden pivot, A0–A3 autonomy
  levels, the 8-phase roadmap, risks, and Step-2 preparation notes.

**Read-only commands run:**
- `git status --short --branch` → branch `main`, in sync with `origin/main`;
  only untracked path is `Planner-docs/`.
- `git log --oneline -n 12` → recent history is documentation/rebranding and
  test-hardening commits (e.g. "rebrand: QB ownership", "Add repo-wide
  committed-secret scan", "Cover cursor and codex validate.sh rejection
  branches").
- `find . -maxdepth 3 -type f` (with VCS/build prunes) → full file tree.
- Per-directory walks of `Planner-docs/`, `shared/`, `platforms/`, `tests/`,
  `scripts/`, `.github/`.
- Length-bounded secret scan over `shared platforms scripts tests Makefile
  README.md` → 0 matches.

**Files / directories inspected:**
- Validator: `shared/scripts/validate_planner_docs.py` (592 lines) — analyzed
  for `ValidationState`, `SECRET_PATTERNS`, `count_audit_severities`,
  `scan_secrets`, `extract_audit_status`, `validate_step4_readiness`,
  heading-order checks, placeholder patterns.
- Fixer seed: `shared/planners/fourth-planner.md` — gate, goal contract, slice
  procedure, safety rules.
- Other planner specs: `shared/planners/{first,second,third,autopsy}-planner.md`.
- Reference docs: `shared/references/{repo-aware-intake,workflow-quality}.md`.
- Sync mechanism: `scripts/sync.sh` (the `MAP` sync contract, `--check` byte
  comparison via `cmp`, and the unmapped-source completeness guard).
- Build/CI: `Makefile` (`sync`/`check`/`test`/`export-sanitized`),
  `.github/workflows/validate.yml`.
- Per-host validators: `platforms/{claude-code,cursor,codex}/scripts/validate.sh`
  (131 / 132 / 262 lines respectively).
- Manifests: `platforms/claude-code/.claude-plugin/plugin.json` (v0.3.0),
  `platforms/cursor/.cursor-plugin/plugin.json` (v0.6.0),
  `platforms/codex/plugins/qb/.codex-plugin/plugin.json` (v0.3.0), and root
  marketplace manifests `.claude-plugin/marketplace.json`,
  `.cursor-plugin/marketplace.json`, `.agents/plugins/marketplace.json`.
- Subagent specs: `platforms/claude-code/agents/{qb-autopsy,qb-auditor,
  qb-implementer,qb-subplanner}.md`.
- Test suite: all 13 modules under `tests/` (purpose read from module
  docstrings).

**Planner-docs files present:** only `Planner-docs/Main-Planning.md`
(no prior `Autopsy.md` — this report is newly created).

## 3. Project Areas and Responsibility Boundaries

| Area | Observed path(s) | Likely responsibility | Maturity / readiness | Boundary issues |
|---|---|---|---|---|
| Canonical IP (control-plane source of truth) | `shared/planners/*.md`, `shared/references/*.md`, `shared/scripts/validate_planner_docs.py` | Host-neutral planner specs + validator; single source of truth | Mature for planning; **seed-only** for audit/harden | Today scoped to planning docs; the place where new Finding/analyzer/policy schemas must live |
| Audit engine seed | `shared/scripts/validate_planner_docs.py` | Fail-closed, graded, evidence-producing document checker | Mature but **doc-bound** | Hard-coded to `Planner-docs/` paths and planning headings; severity counter reads a planning audit doc, not code |
| Fixer discipline seed | `shared/planners/fourth-planner.md` | Verify-before-keep, one reversible slice, no auto-mutation | Prose contract only | No executable form; **no git isolation/rollback mechanism** present |
| Platform packages | `platforms/claude-code/`, `platforms/cursor/`, `platforms/codex/` | Per-host adapters (manifests, commands, agents/skills, synced copies) | Mature for planning | **Asymmetric**: codex differs in layout, filename casing, and validate.sh size; manifest versions differ |
| Sync / parity contract | `scripts/sync.sh`, `tests/test_sync_*`, `tests/test_shared_artifacts_and_sync.py` | Materialize shared→platforms byte-for-byte; enforce completeness | Mature | Covers byte-equality of mapped files only; does not normalize cross-host *structure* divergence |
| Validation / CI | `Makefile`, `platforms/*/scripts/validate.sh`, `.github/workflows/validate.yml`, `tests/` | Local + CI gating of the planning product | Mature for planning | **Zero** coverage of audit/fix behavior (it does not exist yet) |
| Documentation | root `README.md`, `platforms/*/README.md`, `platforms/*/docs/{INSTALLATION,USAGE,MAINTAINING}.md`, `CHANGELOG.md` | User + maintainer docs | Strong | Describes a *planning* product only; will diverge from the pivot |
| Planning output (runtime artifact) | `Planner-docs/` | Where the planning workflow writes its docs | N/A (data dir) | The new goal needs a parallel `QB-Audit/`-style output convention that does not yet exist |

Unclear ownership for the NEW goal: there is no home yet for the four
control-plane roles named in Main-Planning §5 (Analyzers, Fixer, Verifier,
Orchestrator/Policy). All four are currently implied by prose only.

## 4. Feature Inventory

**Implemented / strongly evidenced (current product):**
- Five-step gated planning workflow (master plan → autopsy → sub-plans → audit →
  gated implementation), with fixed-name `Planner-docs/` artifacts.
- Dependency-free read-only validator with heading-order checks, phase/sub-plan
  coverage, index consistency, audit-status extraction (`PASS` /
  `PASS_WITH_WARNINGS` / `BLOCKED`), P0–P3 severity counting that gates Step 4,
  placeholder/`TODO`/`TBD`/`FIXME` detection, and length-bounded secret scanning
  with a `--strict` mode (`shared/scripts/validate_planner_docs.py`).
- Byte-for-byte sync from `shared/` to all platforms plus a `--check` drift gate
  and an unmapped-source completeness guard (`scripts/sync.sh`).
- 13 invariant test modules (manifest ids, frontmatter, no committed secrets, no
  cross-host residue, sync mechanism + map completeness, spec/validator contract,
  per-platform validate.sh failure paths).
- CI on push-to-`main` and all PRs running `make check`
  (`.github/workflows/validate.yml`).
- Multi-host packaging for Claude Code, Cursor, Codex, plus root marketplace
  manifests.

**Partial / skeleton (for the new goal):**
- Audit-engine machinery exists inside the validator but is doc-bound (not yet a
  reusable analyzer over arbitrary repos).
- Fixer discipline exists as a planner spec (`fourth-planner.md`) but is not
  executable and lacks isolation/rollback.

**Planned but not evidenced (declared in Main-Planning, absent in repo):**
- `Finding` schema; pluggable analyzer suite; autonomous finding-driven fixer;
  autonomy/policy engine (A0–A3); run-state + evidence store; JSON/SARIF
  reporting; headless/CI entry point; fixture repos + eval harness; telemetry;
  kill-switch; budget model.

**Missing or unclear:**
- Any runtime beyond the host session and the validator script. There is no
  application code, no service, no CLI, no `configs/`, `services/`, `packages/`,
  or `infra/` directory (these were checked and are empty/absent).

## 5. Placeholder, Stub, and Skeleton Analysis

A repo-wide scan for `TODO|FIXME|TBD|placeholder|NotImplemented|stub|skeleton|
XXX|HACK` over `*.py`, `*.md`, `*.sh` (excluding the five planner spec files,
which legitimately *describe* such patterns as discovery targets) found **no
delivery-blocking code stubs**. The matches fall into two harmless classes:

- **Validator pattern definitions (test-only / by-design):**
  `shared/scripts/validate_planner_docs.py:123-128` define the
  `TODO`/`TBD`/`FIXME`/`angle_placeholder`/`brace_placeholder` regexes the
  validator uses to *detect* placeholders in planning docs; line 382 emits the
  `placeholder_text=...` warning. These are functional, not incomplete.
- **Documentation prose:** README/USAGE/MAINTAINING and the
  `repo-aware-intake.md` references mention "placeholder substitution, in memory
  only" as a workflow instruction — harmless documentation.

The notable "skeleton" signal is not a code stub but an **absence**: the entire
audit+harden surface declared in Main-Planning is unwritten. For the NEW goal the
relevant placeholders are conceptual (schemas/interfaces that exist only in the
plan), not literal `TODO` markers.

How Step 2 should plan remediation: treat the *missing contracts* as the real
"skeleton to fill." Phase 1 sub-plans should specify the concrete file(s) under
`shared/` that will hold the `Finding` schema and analyzer interface, with
acceptance criteria, so the conceptual skeleton becomes a validated artifact.
Keep the validator's existing placeholder-detection regexes intact when
refactoring (they are a load-bearing feature, not debt).

## 6. Technical Debt and Maintenance Risks

- **Cross-host structural asymmetry (the dominant debt).** `platforms/codex`
  uses a nested `plugins/qb/skills/qb/...` layout with **capitalized** reference
  filenames (`First-Planner.md`, `Autopsy-Planner.md`, etc.) and an
  `agents/openai.yaml`, whereas claude-code/cursor use flat `agents/`,
  `commands/`, `references/` with lowercase names. Its `validate.sh` is 262 lines
  vs ~131 for the other two. The byte-equal sync contract guarantees the *synced
  shared files* match, but the *shape* around them diverges per host — more
  surface to keep correct as the engine grows.
- **Manifest version drift.** The same `qb` plugin is `0.3.0` (claude-code),
  `0.6.0` (cursor), `0.3.0` (codex). There is no single source of version truth
  and no test asserting version consistency, so versions can silently diverge.
- **Validator scope coupling.** The audit machinery is tightly bound to
  `Planner-docs/` and planning headings (`extract_audit_status`,
  `count_audit_severities` parse a *planning* audit document). Generalizing
  without a clean interface risks either duplicating the logic (drift) or
  over-refactoring a file the planning product still depends on (regression).
- **Discipline-as-prose, not contract.** The fixer rules live only in
  `fourth-planner.md`. There is no machine-checkable enforcement that an applied
  fix was actually verified or is reversible; the safety is currently a prompt,
  not a gate.
- **Documentation will go stale at the pivot.** All user/maintainer docs
  describe a planning product. Once audit/harden lands, README/USAGE/CHANGELOG
  across three platforms (plus root) must be updated in lockstep or they become
  contradictory — a known multiplier given the three-host fan-out.
- **No missing-schema/contract artifacts.** There is no `Finding` schema, no
  policy schema, no command schema — so the most important contracts are
  undefined and will be invented under time pressure unless frozen early.

## 7. Broken or Missing Integrations

- **Internal role boundaries (missing).** The Analyzer / Fixer / Verifier /
  Orchestrator separation from Main-Planning §5 does not exist as code or
  interfaces; today there is a single validator script and prose specs.
- **External tool/provider integration (missing, security-sensitive).** No
  adapters for linters/SAST/dependency-CVE scanners. Main-Planning §5/§7
  mandates structured command schemas (explicit argv, no shell-string interp);
  no such schema exists yet, so the integration surface is undesigned.
- **Database / queue / storage (none, and not yet needed).** No run-state store,
  no evidence/artifact store. The new goal requires a fixed-name output dir
  (e.g. `QB-Audit/`) analogous to `Planner-docs/`; it is unimplemented.
- **Auth / security / policy systems (missing).** No policy file format, no
  autonomy/permission engine. Secret *detection* exists (`SECRET_PATTERNS`); a
  *policy* governing writes/commits/budgets does not.
- **CI / deployment / infra.** CI exists and is healthy for the planning product
  (`make check`), but there is no headless entry point for CI to invoke an
  audit/harden run, no pipeline exit-code contract, and no `infra/`.
- **Mismatched/absent contracts.** Because no `Finding` schema is frozen, any
  future analyzer and fixer would integrate against an undefined contract — the
  single highest-leverage integration gap.

## 8. Test, CI, and Validation Gaps

**Observed tests and commands.** `make check` runs, in order:
`scripts/sync.sh --check`, the three per-platform `validate.sh`, then
`python3 -m unittest discover -s tests`. The 13 test modules cover: manifest-id
and frontmatter invariants (`test_manifests_and_frontmatter`,
`test_frontmatter_helper`), no committed secrets (`test_no_committed_secrets`),
no cross-host residue (`test_no_cross_host_residue`), sync drift/restore/CLI
(`test_sync_mechanism`), sync-map completeness (`test_sync_map_completeness`),
preserved artifact names + sync-clean (`test_shared_artifacts_and_sync`),
spec↔validator heading contract (`test_spec_validator_contract`), root
marketplace registration (`test_root_marketplaces`), and per-platform
validate.sh failure paths (`test_platform_validate_sh`). CI mirrors `make check`
on push-to-`main` and all PRs.

**Gaps (all relative to the NEW goal):**
- **Zero audit/fix coverage.** Every test validates the *planning* product.
  There is no test for code-finding detection, fix application, verification,
  rollback, or policy enforcement — because none of that exists.
- **No fixture repos.** Main-Planning §8 calls for 1–2 reference repos with
  seeded defects to anchor an eval harness; none are present.
- **No eval harness / precision-recall measurement.** Audit precision and
  fix-safety cannot be measured today.
- **No version-consistency test.** Manifest version drift (§6) is undetected.
- **Local vs live gap.** All validation is local/offline; there is no test of
  unattended/headless behavior, budgets, or kill-switch.

**Suggested validation gates for Step 2 sub-plans:**
- A `Finding`-schema conformance test (Phase 1) — freeze the schema with a test.
- Per-analyzer fixture tests (Phase 2) with seeded defects.
- A fix-safety invariant (Phase 3): every applied fix must keep its verification
  command green; failed fixes must auto-revert — assert via a fixture.
- A policy fail-closed test (Phase 4): out-of-policy actions are blocked; budgets
  are enforced.
- Extend `sync.sh` + sync-map-completeness whenever a new `shared/` artifact is
  added, and add a manifest-version-consistency test.

## 9. Security, Secret, and Governance Findings

- **Secret handling (current posture: good).** A length-bounded
  `SECRET_PATTERNS` list + `scan_secrets` in the validator, a repo-wide
  committed-secret test (`test_no_committed_secrets`), and redact-by-path
  conventions. A scan over tracked source in this autopsy returned **0 matches**;
  no secret values are reproduced in this report.
- **Policy / approval boundaries (current: human-in-the-loop; target: missing
  engine).** Today safety is "pause for explicit human approval at every gate,"
  enforced by prompts and the Step-4 readiness check. The new goal replaces this
  with a policy-bounded autonomy model (A0–A3) that **does not exist yet** — no
  policy schema, no thresholds, no budgets.
- **Least privilege (undesigned for writes).** The current tool is read-only
  (validator) plus prompt-disciplined writes (planning docs). The pivot makes QB
  write code autonomously and read untrusted repos, introducing path-allowlist,
  command-execution-safety, and untrusted-repo concerns that have no
  implementation.
- **Audit / artifact integrity (missing).** No evidence store, no per-fix
  before/after artifacts, no reversal handles (git refs). Main-Planning §5
  requires every fix to carry verification evidence and a reversal handle; none
  exists yet.
- **Risky command-execution surface (the top new risk).** Running
  analyzers/fixers/verification commands against arbitrary repos invites
  injection and malicious build scripts. There is currently no structured
  command schema, no path-traversal guard for writes, and no sandboxing — these
  must be designed before any write-capable analyzer runs.
- **Governance unknowns.** No kill-switch, no documented runbook for unattended
  operation, no cost/iteration budget. The plan flags these; the repo has none.

## 10. Operational Readiness and Observability

- **Deployment / runtime evidence:** none. QB has no runtime beyond the host
  session and the validator script — confirmed by the absence of any
  service/CLI/daemon code, `infra/`, or container/compose files.
- **Headless / CI runnability:** the planning product has none (it is
  interactive/in-session); the audit+harden goal *requires* a headless entry
  point with pipeline exit codes — unimplemented.
- **Observability / logging / metrics / tracing:** none. Main-Planning §4 calls
  for structured telemetry (findings by severity, fixes applied/reverted,
  false-positive signals, latency, token/cost); the repo emits none.
- **Backup / restore / rollback:** only implicit git. There is no automatic
  rollback mechanism, no worktree/branch isolation, and no kill-switch — yet
  these are the core safety primitives the autonomous writer depends on.
- **Cost / latency / quality signals:** none captured; no budget model.
- **Live readiness blockers:** no `Finding` contract, no isolation+rollback
  runtime, no policy engine, no evidence store, no headless surface — each is a
  hard blocker to an unattended run.

## 11. Alignment with the Main Plan

**Main-plan assumptions that are supported by repository evidence:**
- "QB already contains the two hardest seeds." Confirmed. The validator is a
  genuine fail-closed, P0–P3, evidence-producing, secret-scanning analyzer
  (`ValidationState`, `count_audit_severities`, `scan_secrets`), and
  `fourth-planner.md` genuinely encodes verify-before-keep / one-reversible-slice
  / no-auto-mutation discipline.
- "The planning product is mature and well-tested." Confirmed: 13 test modules,
  clean `make check` structure, CI on every PR and push to `main`.
- "`shared/` is the single source of truth materialized byte-for-byte." Confirmed
  by `scripts/sync.sh` (the `MAP`, `--check` via `cmp`, and the completeness
  guard) and the sync tests.
- "Current maturity for the new goal is ~M1 / seed-stage." Confirmed: none of the
  generalized capabilities exist.

**Assumptions that are weak, contradicted, or need a caveat:**
- The plan treats the validator as cleanly reusable; in practice it is *tightly
  coupled* to `Planner-docs/` paths and planning headings (§6), so "reuse, don't
  duplicate" requires real refactoring discipline, not a thin wrapper. The plan's
  open question (d) "refactor vs wrap the validator" is therefore load-bearing.
- The plan describes git-isolation (branch/worktree) for fixes as a core safety
  mechanism (§5, §7), but the fixer seed (`fourth-planner.md`) contains **no**
  isolation mechanism — it only says "minimal, reversible." The isolation
  primitive is net-new, not a generalization of an existing one.
- The plan assumes multi-host parity is largely solved by `sync.sh`; this autopsy
  finds *structural* asymmetry (codex layout/casing, validate.sh size) and
  *version* drift across manifests that the byte-equal sync contract does not
  cover. Parity is healthier than zero but is not "solved" for a write-capable
  engine across 3 hosts + headless.

**Roadmap phases needing stronger evidence before detailing:**
- Phase 1 (Finding schema + audit engine): needs a decision on validator
  refactor-vs-wrap and a concrete target file under `shared/`.
- Phase 3 (fixer): needs the *new* isolation+rollback primitive specified, since
  it is absent today.
- Phase 6 (multi-host + headless): needs the codex structural divergence and
  version drift resolved or explicitly accepted before fanning out a writer.

**Risks Step 2 must not ignore:** autonomous-write regressions without isolation;
false-positive-driven bad fixes without an eval harness; identity/scope drift
producing two half-products; the zero-setup promise vs real analyzers; and the
untrusted-repo command-execution attack surface.

## 12. Autopsy Feedback for Step 2

**Phase 0 — Autonomy Charter & Foundation**
- Incorporate an explicit **non-regression contract** for the planning product
  and a written A0–A3 autonomy/fail-closed model. *Supported by:* §9, §11
  (identity-drift risk; safety is prompt-only today). *Sub-plan type:* a
  foundation/charter sub-plan with acceptance = ratified design doc.
- Decide the output-directory convention (e.g. `QB-Audit/`) and register names as
  validator-checked identifiers. *Supported by:* §3, §7 (no evidence store).
  *Sub-plan type:* contract/naming sub-plan.

**Phase 1 — Findings Model & Audit Engine**
- Freeze the `Finding` schema (`id, category, severity P0–P3, confidence,
  evidence path:line, rationale, suggested-fix, fix-strategy`) as a `shared/`
  artifact with a conformance test. *Supported by:* §4, §7, §8 (no schema, no
  test). *Sub-plan type:* schema + validation-gate sub-plan.
- Refactor (not wrap-only) the validator's `ValidationState` / severity counter /
  `scan_secrets` behind an analyzer interface, then run read-only over QB itself
  and one external fixture. *Supported by:* §6, §11 (scope coupling). *Sub-plan
  type:* refactor sub-plan with a non-regression test for the planning path.

**Phase 2 — Analyzer Suite**
- Build offline analyzers (secret-hygiene seeded, dangerous-command/shell-string,
  path traversal, lint/correctness adapters) behind **structured command
  schemas**; keep networked CVE analyzers opt-in. *Supported by:* §7, §9
  (command-execution surface, offline-core promise). *Sub-plan type:*
  per-analyzer sub-plans each with a seeded-defect fixture test.

**Phase 3 — Autonomous Hardening (Fixer)**
- Promote `fourth-planner.md` into an executable, finding-driven fixer **and add
  the missing git branch/worktree isolation + auto-rollback** primitive.
  *Supported by:* §6, §10, §11 (isolation is net-new; safety is prose today).
  *Sub-plan type:* fixer sub-plan with a fix-safety invariant test (verification
  stays green or auto-revert).

**Phase 4 — Autonomy Orchestrator & Policy Engine**
- Define the policy + budget schema and a fail-closed engine with role
  separation (auditor/fixer/verifier/reviewer). *Supported by:* §9, §10
  (no policy, no budgets, no kill-switch). *Sub-plan type:* policy-engine
  sub-plan with an out-of-policy-blocked test.

**Phases 5–7 — Reporting / Multi-host+Headless / Production**
- Keep rough only for now, but pre-empt: a manifest-version-consistency gate and
  resolution/acceptance of the **codex structural asymmetry** before fanning out
  a writer; JSON/SARIF reporting from run-state; telemetry from the first real
  run. *Supported by:* §6, §8, §10. *Sub-plan type:* parity + reporting +
  observability sub-plans (decompose later).

**Cross-cutting reuse evidence Step 2 should collect (per Main-Planning §9):**
the internal structure of `validate_planner_docs.py` (`ValidationState`, severity
counting, `scan_secrets`); the exact `sync.sh` `MAP` mechanics and completeness
guard; the per-host launch mechanisms (claude-code `agents/` + Task tool, cursor
skills, codex `plugins/qb/skills/qb/`); and the `tests/` conventions so new tests
match the existing style.

## 13. Prioritized Remediation and Planning Signals

- AUTOPSY-P0-01 — No frozen `Finding` schema / code-finding contract
  - Impact: every downstream phase (analyzers, fixer, orchestrator, reporting)
    depends on this contract; without it the whole pivot integrates against an
    undefined interface and will churn.
  - Evidence: absent across repo; declared only in `Planner-docs/Main-Planning.md`
    §5/§8; validator severities live in `shared/scripts/validate_planner_docs.py`
    (`count_audit_severities`) but are bound to planning audit docs.
  - Step 2 impact: Phase-1 sub-plan must freeze the schema as a `shared/`
    artifact with a conformance test before any analyzer/fixer sub-plan starts.

- AUTOPSY-P0-02 — No isolation + rollback runtime for write-capable fixes
  - Impact: the pivot's core danger is unattended writes; without
    branch/worktree isolation and automatic rollback, a bad fix can corrupt the
    user's working tree — the single highest safety risk.
  - Evidence: `shared/planners/fourth-planner.md` specifies "minimal, reversible"
    and "verify before done" but contains **no** isolation/worktree/branch
    mechanism; Main-Planning §5/§7 mandates it as net-new.
  - Step 2 impact: Phase-3 fixer sub-plan must add isolation+rollback as a
    first-class primitive with a fix-safety invariant test, not inherit it.

- AUTOPSY-P1-01 — No policy / autonomy / budget engine (autonomy is undefined)
  - Impact: "full autonomous" cannot be safe without a fail-closed policy,
    severity/confidence thresholds, write-path allowlists, and budgets; today
    safety is prompt-only.
  - Evidence: no policy schema or engine anywhere; current gating is
    human-in-the-loop prompts + `validate_step4_readiness` in the validator.
  - Step 2 impact: Phase-0 charter + Phase-4 engine sub-plans must define A0–A3,
    thresholds, budgets, and a kill-switch, with an out-of-policy-blocked test.

- AUTOPSY-P1-02 — Zero test/eval surface for audit + fix quality
  - Impact: audit precision and fix safety are unmeasurable; raising autonomy
    without evidence risks confidently-wrong changes at scale.
  - Evidence: all 13 `tests/` modules validate the *planning* product; no fixture
    repos; no eval harness (Main-Planning §7 "Gap").
  - Step 2 impact: build 1–2 seeded fixture repos and an eval harness in Phase 1
    and grow them every phase; treat precision + fix-safety as release gates.

- AUTOPSY-P1-03 — Untrusted-repo command-execution surface is undesigned
  - Impact: running analyzers/fixers/verification against arbitrary repos invites
    injection and malicious build scripts → arbitrary code execution on the
    operator's machine.
  - Evidence: no structured command schema, no path-traversal write guard, no
    sandboxing; Main-Planning §7 names this risk but nothing implements the
    mitigation.
  - Step 2 impact: Phase-2/Phase-3 sub-plans must mandate explicit-argv command
    schemas (no shell-string interp), path allowlists, and never auto-run
    repo-provided scripts without sandboxed authorization.

- AUTOPSY-P2-01 — Cross-host structural asymmetry + manifest version drift
  - Impact: a write-capable engine fanned out to 3 hosts + headless will multiply
    on an already-uneven base, risking inconsistent behavior and broken
    `make check`.
  - Evidence: `platforms/codex` nested `plugins/qb/skills/qb/` layout with
    capitalized `*-Planner.md` names + `agents/openai.yaml` + 262-line
    `validate.sh` vs ~131 for the others; manifest versions diverge
    (claude-code `0.3.0`, cursor `0.6.0`, codex `0.3.0`) with no
    consistency test.
  - Step 2 impact: Phase-6 (and a small early hygiene sub-plan) must resolve or
    explicitly accept the codex divergence and add a manifest-version-consistency
    gate before the writer fans out.

- AUTOPSY-P2-02 — Validator is tightly coupled to `Planner-docs/`
  - Impact: "reuse, don't duplicate" the audit machinery requires real
    refactoring; a thin wrapper risks duplication/drift, an over-aggressive
    refactor risks regressing the planning product.
  - Evidence: `shared/scripts/validate_planner_docs.py` hard-binds to
    `Planner-docs/` paths and planning headings
    (`extract_audit_status`, `count_audit_severities`).
  - Step 2 impact: Phase-1 refactor sub-plan must extract the state machine /
    severity counter / secret scanner behind an analyzer interface with a
    non-regression test for the existing planning path.

- AUTOPSY-P3-01 — Documentation will diverge at the pivot
  - Impact: README/USAGE/CHANGELOG across 3 platforms + root all describe a
    planning product; left unupdated they become contradictory once audit+harden
    ships.
  - Evidence: root + per-platform `README.md`, `docs/`, `CHANGELOG.md`, and all
    three plugin descriptions reference only the planning workflow.
  - Step 2 impact: add a documentation-update sub-plan per phase that lands
    audit/harden features, keeping docs and `shared/` in lockstep.

- AUTOPSY-P3-02 — No machine-readable output or evidence/run-state store
  - Impact: CI consumption, reproducibility, and audit trails are impossible
    without structured output and persisted evidence.
  - Evidence: no JSON/SARIF emitter, no `QB-Audit/`-style output dir, no
    evidence/artifact store anywhere in the repo.
  - Step 2 impact: design the output-directory convention in Phase 0 and the
    JSON/SARIF + evidence record format in Phase 1/5 so observability is built in
    from the first real run, not retrofitted.
