<div align="center">

# QB

**A zero-setup, in-session, gated, repo-aware project-planning workflow — for Claude Code, Cursor, and Codex.**

Turn a fuzzy idea into a clear, reviewed, build-ready plan,
then ship it one safe slice at a time — without leaving your AI coding host.

[![license](https://img.shields.io/badge/license-MIT-16A34A)](LICENSE)
[![platforms](https://img.shields.io/badge/platforms-claude--code%20%C2%B7%20cursor%20%C2%B7%20codex-2563EB)](#platforms)

</div>

---

## What QB is

QB is a guided, multi-step planning workflow that runs **inside your chat session**. You answer a few short questions in your own language; QB inspects your repository, plans it in gated stages, and — only after you approve — implements one bounded, reversible slice. The stages and their outputs are listed in [The workflow](#the-workflow) below.

It pauses for your explicit approval at every gate. No CLI, no API key, no setup. Planning output is always **English**; questions follow whatever language you write in. QB never writes secrets and never auto-commits, pushes, or opens PRs during planning. This monorepo ships QB as three native packages — one per host — built from a single shared source of truth.

---

## The workflow

| Step | Name | What happens | Output |
|:--:|---|---|---|
| **1** | Master plan | Repo-aware intake, then a senior-architect plan. | `Planner-docs/Main-Planning.md` |
| **1.5** | Autopsy | For existing projects, a technical health report. | `Planner-docs/Autopsy.md` |
| **Gate 1** | Review | Review the plan (and autopsy) together, give feedback, approve. | — |
| **2** | Sub-plans | Every phase becomes detailed sub-plans plus a coverage index. | `Planner-docs/Phase-<n>-Plans/` + `Planner-docs/Sub-Planning-Index.md` |
| **Gate 2** | Approve audit | Confirm you want the quality audit. | — |
| **3** | Audit | Coverage/quality audit with a `PASS` / `PASS_WITH_WARNINGS` / `BLOCKED` status. | `Planner-docs/Sub-Planning-Audit.md` |
| **4** | Implement | One bounded, reversible code slice from a `READY` sub-plan — gated and approved. | code changes (gated) |

A bundled, dependency-free, **read-only** Python validator checks each step's output — required sections and heading order, phase-folder coverage, filename conventions, index consistency, length-bounded secret patterns, the audit status, and Step-4 readiness. P0/P1 audit findings block the implementation handoff.

---

## Generated artifacts

Every artifact lands under `Planner-docs/` in **your** workspace — never inside the plugin folder:

```text
Planner-docs/
├── Main-Planning.md         # the master plan                          (Step 1)
├── Autopsy.md               # repo health report for existing projects (Step 1.5)
├── Sub-Planning-Index.md    # map of every sub-plan + coverage check   (Step 2)
├── Sub-Planning-Audit.md    # quality/coverage audit + PASS/BLOCKED    (Step 3)
└── Phase-1-Plans/           # detailed sub-plans, one folder per phase
    ├── Phase1.1-...md
    └── Phase1.2-...md
```

> These names — `Main-Planning.md`, `Autopsy.md`, `Sub-Planning-Index.md`, `Sub-Planning-Audit.md`, and the `Phase-<n>-Plans/` / `Phase<n>.<m>-*.md` patterns — are fixed identifiers that the bundled validator and the index cross-references match exactly, so don't rename them. The document *content* is always English.

---

## Monorepo layout

One host-neutral source of truth lives in `shared/`; `scripts/sync.sh` materializes committed, byte-for-byte copies into each platform package.

```text
shared/                         # CANONICAL host-neutral IP — the single source of truth
  planners/                     #   first / second / third / fourth / autopsy planner specs
  references/                   #   repo-aware-intake.md, workflow-quality.md
  scripts/validate_planner_docs.py
platforms/
  claude-code/                  # Claude Code package: commands, skills, agents, .claude-plugin/
  cursor/                       # Cursor package: commands, skills, .cursor-plugin/
  codex/                        # Codex package: .agents marketplace + plugins/qb/.codex-plugin/
scripts/sync.sh                 # materializes shared/ into every platform (committed copies)
tests/                          # top-level unified cross-platform invariant tests
Makefile  README.md  LICENSE  .gitignore  .github/workflows/validate.yml
```

The planner specs, reference docs, and validator are **host-neutral** — they refer to the product generically as "QB" and live only in `shared/`. Everything that carries a platform's brand or host mechanism — the manifest, slash commands, each skill's orchestration, agents, per-platform `validate.sh`, docs, README, CHANGELOG, and assets — is **hand-authored per platform**.

---

## Platforms

Each platform is correct *for its own host*: all three install under the plugin id `qb`, run the same workflow, write the same `Planner-docs/` artifacts, and share the same validator behavior. They differ only — intentionally — in how the long autonomous steps (1.5, 2, 3, 4) launch:

| Platform | How long steps launch |
|---|---|
| **Claude Code** | The orchestrator **delegates** each long step to a matching subagent via the **Task tool** (`qb-autopsy`, `qb-subplanner`, `qb-auditor`, `qb-implementer`). |
| **Cursor** | Each long step is launched automatically as a **Cursor goal** through the native `define-goal` skill. |
| **Codex** | Each long step is handed off as a text-only **Goal-mode** copy/paste prompt block. |

### Installing each platform

**Claude Code** — add the `eserlxl` marketplace, then install it:

```text
/plugin marketplace add eserlxl/marketplace
/plugin install qb@eserlxl
```

The Claude Code package is plugin-only; it is published through the dedicated
[`eserlxl/marketplace`](https://github.com/eserlxl/marketplace) aggregator (which
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

The shared specs are the single source of truth; the platform copies are generated. After editing anything under `shared/`, re-sync and validate:

```bash
make sync    # copy shared/ files into every platform's expected location
make check   # verify sync is clean, run each platform's validate.sh, then the top-level tests
make test    # run the top-level cross-platform invariant tests only
make export-sanitized   # git archive the committed tree to QB-sanitized.zip
```

`scripts/sync.sh --check` (run by `make check`) exits non-zero and lists the drifting paths if any platform copy no longer byte-matches its `shared/` source — so a forgotten `make sync` is caught by the GitHub Actions workflow at `.github/workflows/validate.yml`, which runs `make check` on every pull request and on pushes to `main`.

### Invariants enforced

- **Sync is clean** — every platform copy byte-matches its `shared/` source.
- **Manifest name == platform id** — `qb` on every platform.
- **Frontmatter name == location** — skills match their directory; commands/agents match their filename stem.
- **No cross-host residue** — each platform's hand-authored host files mention only its own host (the synced neutral specs/references/validator, which say only "QB", are exempt); READMEs, CHANGELOGs, and docs may mention all three platforms.
- **Preserved artifact names** — the fixed `Planner-docs/` identifiers above stay stable across the workflow and the validator.

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
