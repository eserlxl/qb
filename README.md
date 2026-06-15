<div align="center">

# QB

**A zero-setup, in-session, gated, repo-aware planning and audit/harden workflow — for Claude Code, Cursor, and Codex.**

Turn a fuzzy idea into a clear, reviewed, build-ready plan,
then ship it one safe slice at a time — or run a conservative audit report —
without leaving your AI coding host.

[![validate](https://github.com/eserlxl/qb/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/eserlxl/qb/actions/workflows/validate.yml)
[![version](https://img.shields.io/badge/version-0.9.0-2563EB)](VERSION)
[![license](https://img.shields.io/badge/license-MIT-16A34A)](LICENSE)
[![platforms](https://img.shields.io/badge/platforms-claude--code%20%C2%B7%20cursor%20%C2%B7%20codex-2563EB)](#platforms)

</div>

---

## What QB is

QB is a multi-platform AI coding workflow that runs **inside your chat session** and ships as native packages for Claude Code, Cursor, and Codex.

It has two related surfaces:

- **Planning workflow** — QB asks a few short repo-aware questions, writes a staged planning package under `.qb/`, audits that package, exports `.qb/plan.md` for [planwright](https://github.com/eserlxl/planwright), and only after explicit approval hands off one bounded implementation slice.
- **Audit/harden/report engine** — QB can run a dependency-free audit over a repository, emit findings and reports under `QB-Audit/`, and, when explicitly raised above A0, attempt fixes only through policy, git isolation, verification, and rollback gates.

Planning output is always **English**; questions follow whatever language you write in. QB never writes secrets and never auto-commits, pushes, opens PRs, or deploys. This monorepo builds all platform packages from a single shared source of truth.

---

## Planning Workflow

| Step | Name | What happens | Output |
|:--:|---|---|---|
| **1** | Master plan | Repo-aware intake, then a senior-architect plan. | `.qb/main-planning.md` |
| **1.5** | Assessment | For existing projects, a technical health report. | `.qb/assessment.md` |
| **Gate 1** | Review | Review the plan (and assessment) together, give feedback, approve. | — |
| **2** | Sub-plans | Every phase becomes detailed sub-plans plus a coverage index. | `.qb/phase-<n>-plans/` + `.qb/sub-planning-index.md` |
| **Gate 2** | Approve audit | Confirm you want the quality audit. | — |
| **3** | Audit | Coverage/quality audit with a `PASS` / `PASS_WITH_WARNINGS` / `BLOCKED` status. | `.qb/sub-planning-audit.md` |
| **3.5** | Export | Automatic step after the audit: project the sub-plans into a flat [planwright](https://github.com/eserlxl/planwright)-format plan. | `.qb/plan.md` |
| **4** | Implement | One bounded, reversible code slice from a `READY` sub-plan — gated and approved. | code changes (gated) |

A bundled, dependency-free, **read-only** Python validator checks each step's output — required sections and heading order, phase-folder coverage, filename conventions, index consistency, length-bounded secret patterns, the audit status, and Step-4 readiness. P0/P1 audit findings block the implementation handoff. A second validator (`validate_planwright_plan.py`) gates the Step-3.5 export against the machine-checkable subset of planwright's plan linter, so `.qb/plan.md` is accepted by planwright on hand-off (`cp .qb/plan.md .planwright/plan.md`, then run planwright `execute` / `cycle`).

---

## Planning Artifacts

Every artifact lands under `.qb/` in **your** workspace — never inside the plugin folder:

```text
.qb/
├── main-planning.md         # the master plan                          (Step 1)
├── assessment.md               # repo health report for existing projects (Step 1.5)
├── sub-planning-index.md    # map of every sub-plan + coverage check   (Step 2)
├── sub-planning-audit.md    # quality/coverage audit + PASS/BLOCKED    (Step 3)
├── plan.md                  # flat planwright-format export            (Step 3.5)
└── phase-1-plans/           # detailed sub-plans, one folder per phase
    ├── phase-1.1-...md
    └── phase-1.2-...md
```

> These names — `main-planning.md`, `assessment.md`, `sub-planning-index.md`, `sub-planning-audit.md`, `plan.md`, and the `phase-<n>-plans/` / `phase-<n>.<m>-*.md` patterns — are fixed identifiers that the bundled validators and the index cross-references match exactly, so don't rename them. The document *content* is always English.

---

## Audit/Harden Engine

QB also ships a host-neutral audit -> harden -> report engine under `shared/scripts/` and each platform package's `scripts/` directory. It is separate from the `.qb/` planning workflow.

Default mode is **A0 report-only**:

```bash
python3 shared/scripts/qb_headless.py --root /path/to/repo --out QB-Audit
```

From an installed platform package, use that package's copied script path instead. Claude Code and Cursor expose `/qb-harden`; Codex routes audit-and-harden requests through `$qb`.

| Autonomy | Behavior |
|---|---|
| **A0** | Report-only. No fix isolation and no working-tree writes. |
| **A1** | Propose fixes in a disposable git worktree; the user's working tree stays unchanged. |
| **A2** | Promote only fixes that pass policy, verification, and rollback gates. |
| **A3** | A2 plus a reviewable changeset path, still explicit opt-in; commit, push, and PR remain policy-gated and default-off. |

The built-in analyzers are dependency-free and offline by default:

- secret hygiene using length-bounded token patterns;
- command injection, dynamic eval, and path-traversal sink detection;
- local quality/correctness adapters such as `ruff` and `pyflakes` when those tools already exist;
- dependency hygiene for manifests and lockfiles, with advisory enrichment only when networked analysis is explicitly enabled.

The fixed run store is:

```text
QB-Audit/
├── findings.jsonl      # canonical graded findings
├── evidence/           # per-fix verification + rollback evidence
├── run-log.jsonl       # append-only orchestration events
├── summary.json
├── report.json
├── report.sarif
└── summary.txt
```

Telemetry records are built by `telemetry.py` from findings, evidence, cost, and autonomy data; release and production gates consume those current signals when autonomous operation is being considered. Headless exit codes are stable: `0` clean, `1` findings present, `2` policy/budget boundary, `3` internal error. See [RUNBOOK.md](RUNBOOK.md) for operating, pausing, killing, recovering, and production-gating autonomous runs.

---

## Monorepo Layout

One host-neutral source of truth lives in `shared/`; `scripts/sync.sh` materializes committed, byte-for-byte copies into each platform package.

```text
shared/                         # CANONICAL host-neutral IP — the single source of truth
  planners/                     #   first / second / third / fourth / assessment planner specs
  references/                   #   repo-aware-intake.md, workflow-quality.md
  scripts/                      #   validators, analyzers, policy, isolation, reports, headless runner
platforms/
  claude-code/                  # Claude Code package: commands, skills, agents, .claude-plugin/
  cursor/                       # Cursor package: commands, skills, .cursor-plugin/
  codex/                        # Codex package: .agents marketplace + plugins/qb/.codex-plugin/
scripts/sync.sh                 # materializes shared/ into every platform (committed copies)
tests/                          # top-level unified cross-platform invariant tests
Makefile  README.md  LICENSE  .gitignore  .github/workflows/validate.yml
```

The planner specs, reference docs, validators, analyzer contracts, engine modules, and report/runtime helpers are **host-neutral** — they refer to the product generically as "QB" and live only in `shared/`. Everything that carries a platform's brand or host mechanism — manifests, slash commands, skills/orchestration wrappers, agents, per-platform `validate.sh`, docs, README, CHANGELOG, and assets — is **hand-authored per platform**.

---

## Platforms

Each platform is correct *for its own host*: all three install under the plugin id `qb`, run the same planning workflow, write the same `.qb/` artifacts, share the same validators, and receive byte-equal copies of the shared engine. They differ only — intentionally — in how long autonomous work launches:

| Platform | Planning long steps | Audit/harden runner |
|---|---|
| **Claude Code** | Task-tool subagents: `qb-assess`, `qb-subplanner`, `qb-auditor`, `qb-implementer`. | `/qb-harden` delegates to `qb-runner`. |
| **Cursor** | Native `define-goal` goals for the matching skills. | `/qb-harden` launches the `qb-runner` goal. |
| **Codex** | Text-only Goal-mode copy/paste prompt blocks through `$qb`. | `$qb` audit-and-harden flow, backed by `qb_headless.py`. |

### User Entry Points

| Host | Main planning | Direct planning steps | Audit/harden |
|---|---|---|---|
| **Claude Code** | `/qb-plan` (`/qb-plan auto` for non-interactive planning export) | `/qb-assess`, `/qb-audit`, `/qb-implement` | `/qb-harden` |
| **Cursor** | `/qb-plan` (`/qb-plan auto` for non-interactive planning export) | `/qb-assess`, `/qb-audit`, `/qb-implement` | `/qb-harden` |
| **Codex** | `Use $qb ...` (`Use $qb auto ...` for non-interactive planning export) | Ask `$qb` for Step 1.5, Step 2, Step 3, Step 3.5 export, or Step 4 handoff | Ask `$qb` to audit and harden the repository |

### Installing each platform

**Claude Code** — add the `eserlxl` marketplace, then install it:

```text
/plugin marketplace add eserlxl/claude-marketplace
/plugin install qb@eserlxl
```

The Claude Code package is plugin-only; it is published through the dedicated
[`eserlxl/claude-marketplace`](https://github.com/eserlxl/claude-marketplace) aggregator (which
also offers `planwright`). For local development, register `platforms/claude-code`
directly as a plugin — see `platforms/claude-code/docs/INSTALLATION.md`. Then run
`/qb-plan` in your project.

**Cursor** — clone the repo, symlink the platform package into Cursor's local plugins, reload Cursor, then run `/qb-plan`:

```bash
git clone https://github.com/eserlxl/qb.git
ln -s "$(pwd)/qb/platforms/cursor" ~/.cursor/plugins/local/qb
```

(Cursor can also import `eserlxl/qb` as a marketplace from its Plugins settings.)

**Codex** — add the marketplace from GitHub, then invoke `$qb` in a new Codex thread:

```bash
codex plugin marketplace add eserlxl/qb --ref main
codex plugin add qb@eserlxl
```

(For a local checkout, run `codex plugin marketplace add .` from the `platforms/codex` directory instead.)

Each platform directory ships its own README and `docs/` with host-specific install and usage details.

---

## Development

The shared specs and engine modules are the single source of truth; platform copies are generated. After editing anything under `shared/`, re-sync and validate:

```bash
make sync    # copy shared/ files into every platform's expected location
make check   # verify sync is clean, run each platform's validate.sh, then the top-level tests
make test    # run the top-level cross-platform invariant tests only
make export-sanitized   # git archive the committed tree to QB-sanitized.zip
```

`scripts/sync.sh --check` (run by `make check`) exits non-zero and lists the drifting paths if any platform copy no longer byte-matches its `shared/` source — so a forgotten `make sync` is caught by the GitHub Actions workflow at `.github/workflows/validate.yml`, which runs `make check` on every pull request and on pushes to `main`.

Versioning is anchored by the root [VERSION](VERSION) file. Use `scripts/bump-version.sh` to bump or re-sync versions across platform manifests, `SKILL.md` frontmatter, and platform changelogs:

```bash
scripts/bump-version.sh patch -m "Describe the change"
scripts/bump-version.sh --sync
```

### Invariants enforced

- **Sync is clean** — every platform copy byte-matches its `shared/` source.
- **Every shared file is mapped** — `scripts/sync.sh --check` fails if a new `shared/` file is not wired to the platform fan-out map.
- **Every shared engine module ships everywhere** — analyzer, policy, isolation, report, telemetry, and headless modules are byte-equal in all packages.
- **Version is lockstep** — root `VERSION`, all platform manifests, and all platform `SKILL.md` metadata versions match.
- **Manifest name == platform id** — `qb` on every platform.
- **Frontmatter name == location** — skills match their directory; commands/agents match their filename stem.
- **No cross-host residue** — each platform's hand-authored host files mention only its own host (the synced neutral specs/references/validator, which say only "QB", are exempt); READMEs, CHANGELOGs, and docs may mention all three platforms.
- **Preserved artifact names** — the fixed `.qb/` identifiers above stay stable across the workflow and the validator.
- **No committed secrets** — tracked text is scanned for known credential-shaped values.
- **Dependency-free core** — shared engine modules import only Python standard-library modules and sibling files.
- **Autonomy is enforced** — A0/A1/A2/A3 side effects, budget stops, kill-switch behavior, rollback drills, cross-review, release gates, and the production gate are covered by tests.

---

## Attribution

QB is an independent, multi-platform project **inspired by** two projects by **[Alican Kiraz](https://github.com/alicankiraz1)**:

- **[CursorQB](https://github.com/alicankiraz1/CursorQB)** — the Cursor plugin
- **[CodexQB](https://github.com/alicankiraz1/CodexQB)** — the Codex plugin

QB **is not a direct port** of either. It builds on their ideas while standing on its own: a native Claude Code platform the originals never had, a unified `qb` identity across hosts, and reworked planner prompts, repo-aware intake, workflow-quality guidance, and a read-only validator — each platform's launch mechanism adapted to its native host. Released under the **MIT** license.

---

<div align="center">

**[MIT](LICENSE)** · inspired by Alican Kiraz's CursorQB & CodexQB · QB © Eser KUBALI

</div>
