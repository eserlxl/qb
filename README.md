# QB

Repo planning, plan export, and guarded repository hardening for AI coding hosts.

<div align="center">

[![version](https://img.shields.io/badge/version-0.14.1-2563EB)](VERSION)
[![license](https://img.shields.io/badge/license-MIT-16A34A)](LICENSE)
[![platforms](https://img.shields.io/badge/platforms-claude--code%20%C2%B7%20cursor%20%C2%B7%20codex%20%C2%B7%20antigravity-2563EB)](#platform-packages)

</div>

QB is a shared workflow layer for Claude Code, Cursor, Codex, and Antigravity: one host-neutral core, four native packages and a separate audit/harden engine that can inspect a repository without taking write privileges by default. (The Antigravity package is planning-only.)

The project has two jobs:

- Turn unclear repository work into reviewed, staged planning files that can be
  handed to [planwright](https://github.com/eserlxl/planwright).
- Run a dependency-free repository audit, optionally test isolated fixes, and
  promote only changes that pass policy, verification, and rollback gates.

Questions can follow the user's language. Generated planning documents are
English for validator stability. QB does not write secrets, and it does not
commit, push, open pull requests, deploy, or auto-apply hardening changes unless
the caller explicitly raises the autonomy level and the local safety gates allow
it.

## Operating Model

QB is built around fixed artifacts and explicit gates rather than chat-only
memory. Long-running AI work can be reviewed as normal files, checked by scripts,
and resumed by another host without changing the project contract.

| Area | What QB Owns | Files |
|---|---|---|
| Planning | Repo-aware intake, master plan, assessment, sub-plans, audit, and planwright export. | `.qb/` |
| Hardening | Findings, reports, verification evidence, telemetry, and autonomy decisions. | `QB-Audit/` |
| Packaging | Native host commands, skills, agents, manifests, and docs. | `platforms/` |
| Shared core | Planner specs, validators, analyzers, reports, policy, isolation, and gates. | `shared/` |

The root repository is the product source of truth. Platform packages are not
forks; `scripts/sync.sh` copies the shared core into the three engine-bearing
host packages (Claude Code, Cursor, Codex) and `make check` verifies those
copies remain byte-equal. The Antigravity package is planning-only and is **not**
a `sync.sh` destination; it is authored on its own path.

## Planning Path

The planning workflow is intentionally staged. Each stage leaves durable output
behind, and implementation is only reached after the plan and audit are in a
usable state.

| Stage | Purpose | Output |
|---|---|---|
| 1. Master plan | Establish repo context, project direction, constraints, and phases. | `.qb/main-planning.md` |
| 1.5 Assessment | Summarize the current project's health, gaps, and readiness risks. | `.qb/assessment.md` |
| Review gate | Let the user revise or approve the planning direction. | User approval |
| 2. Sub-plans | Expand each phase into bounded implementation plans and an index. | `.qb/phase-<n>-plans/`, `.qb/sub-planning-index.md` |
| Audit gate | Confirm the user wants the generated plan package audited. | User approval |
| 3. Planning audit | Check coverage, ordering, structure, readiness, and blocking issues. | `.qb/sub-planning-audit.md` |
| 3.5 Export | Convert READY sub-plans into planwright's flat checkbox plan format. | `.qb/plan.md` |
| 4. Handoff | Implement one bounded, reversible slice from a READY item. | Code changes, gated |

The validators are read-only and dependency-free. `validate_planner_docs.py`
checks section order, required files, phase coverage, filenames, index
references, audit status, secret-shaped values, and Step 4 readiness.
`validate_planwright_plan.py` checks the Step 3.5 export against the
machine-checkable subset of planwright's plan format.

Validation is a barrier at every planning step, not only at the final export:
Step 1 must pass `validate_planner_docs.py --mode step1 --strict`, Step 2 must
pass `--mode step2 --strict`, and Step 3 must pass `--mode step4` before Step
3.5 writes executable items. The Step 3.5 export contains only post-audit,
implementation-ready work against normal repository surfaces; `.qb/` planning
files may provide context but are never editable planwright item surfaces.

The planning filenames are part of the public contract. Keep these names stable:
`main-planning.md`, `assessment.md`, `sub-planning-index.md`,
`sub-planning-audit.md`, `plan.md`, `phase-<n>-plans/`, and
`phase-<n>.<m>-*.md`.

### Parallel Per-Phase Planning

On hosts with real subagents (Claude Code, via the Task tool), Steps 2, 3, and
3.5 run as a per-phase **map → barrier → reduce**: one worker drafts (Step 2),
audits (Step 3), or exports (Step 3.5) each main phase concurrently, then a
single reduce writes the shared artifact — `sub-planning-index.md`,
`sub-planning-audit.md`, or `plan.md` — and runs its validator once over the
complete tree. Step 1's read-only repository scan is likewise gathered in
parallel lanes and merged into one shared evidence bundle. This collapses a
planning run's wall-clock cost from the sum of all phases to the slowest single
phase plus the reduce, with byte-identical outputs.

The fan-out preserves the workflow's guarantees: distinct phases write distinct
files (no write conflicts), the reduce is the sole writer of each shared
artifact, and audit independence is kept because every worker is a fresh actor
(the Step 2 author of a phase is never its Step 3 auditor). Workers are scoped by
a `PHASE SCOPE: <n>` directive in their task brief; with no scope the specs run
their original single-pass behavior, which is preserved unchanged as the default
and as the fallback for hosts without subagents (Cursor, Codex, Antigravity).

## Hardening Path

The audit/harden engine is separate from the `.qb/` planning workflow. It can be
used directly from the shared script tree or through the installed host package.

```bash
python3 shared/scripts/qb_headless.py --root /path/to/repo --out QB-Audit
```

Default operation is A0 report-only: no fix isolation, no writes to the target
working tree, and no dependency downloads. Higher levels must be requested
explicitly and are still capped by the earned safety ceiling for the current
repository context.

| Level | Behavior |
|---|---|
| A0 | Report findings only. |
| A1 | Try proposed fixes in disposable git isolation; leave the working tree unchanged. |
| A2 | Promote only verified fixes that satisfy policy and rollback requirements. |
| A3 | A2 plus a reviewable delivery path; commit, push, and PR actions remain opt-in. |

Proposed fixes are tried in disposable git **write isolation** (a throwaway
worktree; the target working tree is never touched until a fix verifies and is
promoted), which is delivered today. Execution sandboxing of analyzed code is a
**Phase 3** boundary item and is **not yet shipped**, so QB confines *writes*,
not arbitrary code execution — do not rely on it to contain untrusted code.

The built-in producer analyzers are `SecretHygieneAnalyzer`,
`CommandInjectionAnalyzer`, `QualityAnalyzer`, `DependencyAnalyzer`,
`LicenseAnalyzer`, and `ConfigHygieneAnalyzer`. Together they cover the frozen
finding categories `secret`, `injection`, `path-traversal`, `dependency`,
`quality`, `correctness`, `license`, and `config`: secret-shaped values, command
injection, dynamic eval, path traversal, dependency manifests, lockfiles,
repository license state, committed dotenv/config hygiene, and local quality
tools such as `ruff`. The `correctness` category is produced conditionally by
the `pyflakes` adapter when `pyflakes` already exists. Advisory enrichment is
networked only when explicitly enabled.

Each run writes a fixed store:

```text
QB-Audit/
├── findings.jsonl
├── evidence/
├── run-log.jsonl
├── summary.json
├── report.json
├── report.sarif
└── summary.txt
```

Exit codes are stable: `0` clean, `1` findings present, `2` policy or budget
boundary, and `3` internal error. Operational details for pausing, killing,
recovering, rollback drills, release gates, and production gates live in
[RUNBOOK.md](RUNBOOK.md).

## Platform Packages

All hosts use the same `qb` identity and write the same planning artifacts. The
host packages differ only where the host requires a different launch mechanism.

| Host | Planning Entry | Direct Steps | Hardening Entry |
|---|---|---|---|
| Claude Code | `/qb-plan` or `/qb-plan auto` | `/qb-assess`, `/qb-audit`, `/qb-implement` | `/qb-harden` |
| Cursor | `/qb-plan` or `/qb-plan auto` | `/qb-assess`, `/qb-audit`, `/qb-implement` | `/qb-harden` |
| Codex | `Use $qb ...` or `Use $qb auto ...` | Ask `$qb` for Step 1.5, Step 2, Step 3, Step 3.5, or Step 4 | Ask `$qb` to audit and harden |
| Antigravity | `Use the qb skill ...` | Ask the skill for Step 1.5, Step 2, Step 3, or Step 4 | — (planning-only) |

Long-running work is launched through each host's native pattern:

| Host | Long-Running Planning | Audit/Harden Runner |
|---|---|---|
| Claude Code | Task-tool subagents: `qb-assess`, `qb-subplanner`, `qb-auditor`, `qb-implementer`; Steps 2/3/3.5 fan out one subagent per phase, then reduce. | `/qb-harden` delegates to `qb-runner`. |
| Cursor | Native `define-goal` goals for the matching skills. | `/qb-harden` launches the `qb-runner` goal. |
| Codex | Text-only Goal-mode prompt blocks through `$qb`. | `$qb` flow backed by `qb_headless.py`. |
| Antigravity | Text-only Antigravity-task prompt blocks via the `qb` skill. | — (planning-only) |

### Install

Claude Code:

```text
/plugin marketplace add eserlxl/claude-marketplace
/plugin install qb@eserlxl
```

For local Claude Code development, register `platforms/claude-code` directly as
a plugin. The package docs are in
`platforms/claude-code/docs/INSTALLATION.md`.

Cursor:

```bash
git clone https://github.com/eserlxl/qb.git
ln -s "$(pwd)/qb/platforms/cursor" ~/.cursor/plugins/local/qb
```

Cursor can also import `eserlxl/qb` as a marketplace from its Plugins settings.

Codex:

```bash
codex plugin marketplace add eserlxl/qb --ref main
codex plugin add qb@eserlxl
```

For a local checkout, run `codex plugin marketplace add .` from
`platforms/codex`.

Antigravity:

```bash
git clone https://github.com/eserlxl/qb.git
cd qb/platforms/antigravity
scripts/install.sh --scope app-global --force
```

See `platforms/antigravity/docs/INSTALLATION.md` for all scopes (IDE/CLI,
project/global).

## Repository Map

```text
shared/
  planners/                 # host-neutral planning specs
  references/               # repo intake and workflow quality guidance
  scripts/                  # validators, analyzers, policy, reports, runner
platforms/
  claude-code/              # Claude Code plugin package
  cursor/                   # Cursor plugin package
  codex/                    # Codex plugin package
  antigravity/              # Antigravity (Gemini) skill package -- planning-only
scripts/
  sync.sh                   # shared-core fan-out
  bump-version.sh           # version metadata maintenance
tests/                      # cross-platform invariant tests
Makefile
RUNBOOK.md
VERSION
```

Anything in `shared/` must stay host-neutral and refer to the product as QB.
Anything that depends on a host's command syntax, agent model, manifest format,
docs, changelog, or assets belongs under that host's `platforms/<host>/`
directory.

## Development

After editing shared planner specs, references, validators, or engine modules,
sync the generated platform copies and run the invariant suite:

```bash
make sync
make check
```

Useful targets:

```bash
make test               # top-level cross-platform tests
make export-sanitized   # archive the committed tree as QB-sanitized.zip
```

Version metadata is anchored by [VERSION](VERSION):

```bash
scripts/bump-version.sh patch -m "Describe the change"
scripts/bump-version.sh --sync
```

`make check` enforces the main repository contracts:

- platform copies match their `shared/` sources;
- every shared file is mapped into the fan-out;
- version fields and skill frontmatter are lockstep;
- each package uses the `qb` manifest identity;
- host-authored files do not leak another host's launch syntax;
- fixed `.qb/` artifact names stay stable;
- tracked text passes secret hygiene checks;
- shared Python modules remain standard-library-only plus sibling imports;
- autonomy, policy, isolation, rollback, verification, release, and production
  gates stay covered by tests.

### Continuous integration

Green **local** validation is the gate of record. Each host package runs
`bash scripts/validate.sh` (driven by `make check`), and the monorepo
`make check` aggregates all four. Cloud CI — the GitHub Actions `validate.yml`
workflow behind the badge above — is **disabled on the account**, so a passing
local `make check` / `scripts/validate.sh`, not the cloud badge, is the
authoritative signal.

### Documentation consistency

A stdlib drift guard (`tests/test_doc_consistency.py`, discovered and run by
`make check`) keeps these docs aligned with the engine. Each invariant derives
its expected value from a source of truth rather than a hardcoded duplicate:

| Invariant | Source of truth | Asserted in |
|---|---|---|
| Every registered producer analyzer is named | `shared/scripts/audit_runner.py` registry (`build_default_registry`) | root `README.md` |
| Every finding category is named | `shared/scripts/finding_schema.py` `CATEGORIES` | root `README.md` |
| Four-platform model + Antigravity planning-only stated | filesystem (host packages, `sync.sh` exclusion) | root `README.md`, `platforms/antigravity/README.md` |
| Per-host READMEs not claimed byte-identical copies | filesystem | root + host READMEs |
| All four CHANGELOGs share the latest version header | filesystem (`platforms/*/CHANGELOG.md`) | the four CHANGELOGs |
| Root README version badge equals `VERSION` | root `VERSION` file | root `README.md` |

The guard is dependency-free (Python standard library only) and is a root
monorepo invariant test, not a synced per-package file, so it runs once under the
local gate of record. Antigravity is checked for the platform-model and CHANGELOG
invariants but is excluded from the analyzer-naming assertion, since it is
planning-only and ships no audit engine.

## Attribution

QB is an independent project inspired by Alican Kiraz's
[CursorQB](https://github.com/alicankiraz1/CursorQB),
[CodexQB](https://github.com/alicankiraz1/CodexQB), and
[AntigravityQB](https://github.com/alicankiraz1/AntigravityQB). It now diverges
substantially in scope and architecture: native Claude Code support, a unified
`qb` identity across four hosts, `.qb/` artifacts, planwright export, parallel
per-phase planning fan-out, a shared host-neutral core, and a policy-gated
audit/harden engine. At this point it shares little beyond the original
inspiration — the planning model, multi-host core, validators, and hardening
engine are all QB's own.

Released under the [MIT](LICENSE) license.
