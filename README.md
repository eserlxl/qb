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

QB is a guided, multi-step planning workflow that runs **inside your chat session**. You answer a few short questions in your own language, and QB:

1. **Inspects** your repository (repo-aware intake),
2. writes a senior-architect **master plan**,
3. runs an **autopsy** of an existing project's real state,
4. breaks the plan into detailed **phase sub-plans**,
5. **audits** them for coverage and quality, and
6. — only if you approve — **implements** one bounded, reversible slice.

It pauses for your explicit approval at every gate. No CLI, no API key, no setup. All planning output is **English**; questions follow whatever language you write in. QB never writes secrets and never auto-commits, pushes, or opens PRs during planning.

This monorepo ships QB as three native packages — one per host — built from a single shared source of truth.

---

## The workflow

```text
Step 1   repo-aware intake     -> Planner-docs/Main-Planning.md           (interactive)
Step 1.5 autopsy               -> Planner-docs/Autopsy.md                (existing projects only)
 Gate 1  review the plan (+ autopsy) and approve
Step 2   phase decomposition   -> Planner-docs/Phase-<n>-Plans/ + Sub-Planning-Index.md
 Gate 2  approve the audit
Step 3   audit                 -> Planner-docs/Sub-Planning-Audit.md
Step 4   gated implementation of ONE slice  (code changes, only after the Step-4 gate passes)
```

| Step | Name | What happens | Output |
|:--:|---|---|---|
| **1** | Master plan | Repo-aware intake, then a senior-architect plan. | `Planner-docs/Main-Planning.md` |
| **1.5** | Autopsy | For existing projects, a technical health report. | `Planner-docs/Autopsy.md` |
| **Gate 1** | Review | Review the plan (and autopsy) together, give feedback, approve. | — |
| **2** | Sub-plans | Every phase becomes detailed sub-plans plus a coverage index. | `Planner-docs/Phase-<n>-Plans/` + `Planner-docs/Sub-Planning-Index.md` |
| **Gate 2** | Approve audit | Confirm you want the quality audit. | — |
| **3** | Audit | Coverage/quality audit with a `PASS` / `PASS_WITH_WARNINGS` / `BLOCKED` status. | `Planner-docs/Sub-Planning-Audit.md` |
| **4** | Implement | One bounded, reversible code slice from a `READY` sub-plan — gated and approved. | code changes (gated) |

A bundled, dependency-free, **read-only** Python validator checks each step's output (required sections and heading order, phase-folder coverage, filename conventions, index consistency, length-bounded secret patterns, the audit status, and Step-4 readiness). P0/P1 audit findings block the implementation handoff.

---

## Generated artifacts

Every artifact lands under `Planner-docs/` in **your** workspace — never inside the plugin folder:

```text
Planner-docs/
├── Main-Planning.md         # the master plan                          (Step 1)
├── Autopsy.md              # repo health report for existing projects (Step 1.5)
├── Sub-Planning-Index.md    # map of every sub-plan + coverage check   (Step 2)
├── Sub-Planning-Audit.md    # quality/coverage audit + PASS/BLOCKED    (Step 3)
└── Phase-1-Plans/            # detailed sub-plans, one folder per phase
    ├── Phase1.1-...md
    └── Phase1.2-...md
```

> The artifact names — `Main-Planning.md`, `Sub-Planning-Index.md`, `Sub-Planning-Audit.md`, and the `Phase-<n>-Plans/` / `Phase<n>.<m>-*.md` patterns — are fixed identifiers that the bundled validator and the index cross-references match exactly, so don't rename them. The document *content* is always English. (Earlier releases used the Turkish `Faz` and the misspelled `Planing`; both were standardized to `Phase` / `Planning` — see the platform CHANGELOGs for the migration note.)

---

## Monorepo layout

QB keeps one host-neutral source of truth in `shared/` and materializes committed copies into each platform package with `scripts/sync.sh`.

```text
shared/                         # CANONICAL host-neutral IP — the single source of truth
  planners/                     #   first / second / third / fourth / autopsy planner specs
  references/                   #   repo-aware-intake.md, workflow-quality.md
  scripts/validate_planner_docs.py
platforms/
  claude-code/                  # plugin id "claudeqb"  — subagents via the Task tool
  cursor/                       # plugin id "cursorqb"  — Cursor goals via define-goal
  codex/                        # plugin id "codexqb"   — Goal-mode copy/paste handoff
scripts/sync.sh                 # materializes shared/ into every platform (committed copies)
tests/                          # top-level unified cross-platform invariant tests
Makefile  README.md  LICENSE  .gitignore  .github/workflows/validate.yml
```

**Shared vs. platform-specific.** The five planner specs, the two reference docs, and the validator are **host-neutral** (they refer to the product generically as "QB") and live only in `shared/`; `sync.sh` copies them byte-for-byte into each platform. Everything that carries a platform's brand or host mechanism — the manifest, slash commands, each skill's orchestration, subagents/agents, per-platform `validate.sh`, docs, README, CHANGELOG, and assets — is **hand-authored per platform**.

---

## Platforms

Each platform is correct *for its own host*; they intentionally use different launch mechanisms for the long autonomous steps (1.5, 2, 3, 4):

| Platform | Plugin id | How long steps launch |
|---|---|---|
| **Claude Code** (`platforms/claude-code`) | `claudeqb` | The orchestrator **delegates** each long step to a matching subagent via the **Task tool** (`claudeqb-autopsy`, `claudeqb-subplanner`, `claudeqb-auditor`, `claudeqb-implementer`). |
| **Cursor** (`platforms/cursor`) | `cursorqb` | Each long step is launched automatically as a **Cursor goal** through the native `define-goal` skill. |
| **Codex** (`platforms/codex`) | `codexqb` | Each long step is handed off as a text-only **Goal-mode** copy/paste prompt block. |

All three run the identical workflow, write the identical `Planner-docs/` artifacts, and share the identical validator behavior.

### Installing each platform

**Claude Code** — add the plugin from its marketplace manifest, then install it:

```bash
claude plugin marketplace add /absolute/path/to/qb/platforms/claude-code
claude plugin install claudeqb@claudeqb
```

Then run `/claudeqb-plan` in your project. See `platforms/claude-code/docs/INSTALLATION.md`.

**Cursor** — install the package at `platforms/cursor` per its README, then run `/cursorqb-plan`. See `platforms/cursor/docs/`.

**Codex** — install the package at `platforms/codex/plugins/codexqb` per its README, then invoke `$codexqb`. See `platforms/codex/docs/`.

Each platform directory ships its own README and `docs/` with host-specific install and usage details.

---

## Development

The shared specs are the single source of truth; the platform copies are generated. After editing anything under `shared/`, re-sync and validate:

```bash
make sync    # copy shared/ files into every platform's expected location
make check   # verify sync is clean, run each platform's validate.sh, then the top-level tests
make test    # run the top-level cross-platform invariant tests only
```

`scripts/sync.sh --check` (run by `make check`) exits non-zero and prints the drifting paths if any platform copy no longer byte-matches its `shared/` source — so a forgotten `make sync` is caught in CI.

The repository ships GitHub Actions at `.github/workflows/validate.yml`, which runs `make check` on pushes and pull requests.

```bash
make export-sanitized   # git archive the committed tree to QB-sanitized.zip
```

### Invariants enforced

- **Sync is clean** — every platform copy byte-matches its `shared/` source.
- **Manifest name == platform id** — `claudeqb` / `cursorqb` / `codexqb`.
- **Frontmatter name == location** — skills match their directory; commands/agents match their filename stem.
- **No cross-host residue** — each platform's hand-authored host files mention only its own host (the synced neutral specs/references/validator, which say only "QB", are exempt). READMEs, CHANGELOGs, and docs may mention all three platforms and the upstream attribution.
- **Preserved artifact names** — `Main-Planning.md`, `Autopsy.md`, `Sub-Planning-Index.md`, `Sub-Planning-Audit.md`, and the `Phase-<n>-Plans/` / `Phase<n>.<m>-*.md` patterns are stable across the workflow and the validator.

---

## Attribution

QB is derived from two projects by **[Alican Kiraz](https://github.com/alicankiraz1)** — it is an attributed, multi-platform port of:

- **[CursorQB](https://github.com/alicankiraz1/CursorQB)** — the Cursor plugin
- **[CodexQB](https://github.com/alicankiraz1/CodexQB)** — the Codex plugin

The planner prompts, repo-aware intake, workflow-quality guidance, and read-only validator are ported faithfully into the shared source of truth; each platform's launch mechanism is adapted to its native host (Claude Code subagents via the Task tool, Cursor `define-goal` goals, Codex Goal-mode handoff). Released under the **MIT** license.

---

<div align="center">

**[MIT](LICENSE)** · original © Alican Kiraz · port © Eser KUBALI

</div>
