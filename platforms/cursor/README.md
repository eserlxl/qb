<div align="center">

<img src="assets/logo.svg" width="96" height="96" alt="QB logo">

# QB

**Plan any project end to end — without leaving Cursor.**

Turn a fuzzy idea into a clear, reviewed, build-ready plan,
then ship it one safe slice at a time.

<br>

[![version](https://img.shields.io/badge/version-0.4.0-2563EB)](CHANGELOG.md)
[![license](https://img.shields.io/badge/license-MIT-16A34A)](LICENSE)
[![Cursor](https://img.shields.io/badge/Cursor-plugin-0F172A)](https://cursor.com)
[![works with](https://img.shields.io/badge/works%20with-new%20%26%20existing%20repos-EA580C)](#what-youll-get)

[Quick start](#quick-start) ·
[How it works](#how-it-works) ·
[Commands](#commands) ·
[Safety](#you-stay-in-control) ·
[FAQ](#faq)

</div>

---

QB is a **Cursor plugin** that runs a guided, five-step planning workflow right in your chat. You answer a few short questions in your own language, and QB:

1. **Inspects** your repository,
2. writes a senior-architect **master plan**,
3. breaks it into detailed **phase sub-plans**,
4. **audits** them for quality and coverage,
5. and — only if you approve — **implements** one reviewed slice.

It pauses for your explicit approval at every step. No CLI, no API key, no setup. Just type `/qb-plan`.

QB is the Cursor edition of the QB planning workflow. Sibling editions exist for Claude Code (QB) and Codex (QB); the shared planning specs and read-only validator are common to all three.

---

## Why QB?

| | |
|---|---|
| **From idea to plan, fast** | No more blank page — get a structured, phase-by-phase plan grounded in your real repository. |
| **Repo-aware** | It reads your codebase first and proposes evidence-backed answers, so the plan fits what you already have. |
| **Quality-checked** | A built-in auditor plus a read-only validator catch missing sections, gaps, and scope drift before you build. |
| **You stay in control** | An explicit approval gate sits between every step, and planning never touches your source code. |
| **Speaks your language** | Questions are asked in whatever language you write in; the planning documents are written in English. |

---

## Quick start

**1. Install** — link the plugin into Cursor's local plugins folder:

```bash
ln -s "/absolute/path/to/QB" ~/.cursor/plugins/local/qb
```

**2. Reload Cursor** — `Cmd/Ctrl + Shift + P` → **Developer: Reload Window**.

**3. Plan** — open the chat in your project and run:

```text
/qb-plan
```

Then answer the four short questions and approve each step as you go. That's it.

> See [`docs/INSTALLATION.md`](docs/INSTALLATION.md) for a copy-based install and verification steps.

---

## How it works

```mermaid
flowchart TD
    Start(["/qb-plan"]):::start

    subgraph PLAN["Planning &nbsp;·&nbsp; writes only inside Planner-docs/"]
        direction TB
        S1["<b>Step 1 · Master plan</b><br/><i>you answer 4 questions</i>"]:::step
        S15["<b>Step 1.5 · Repo autopsy</b><br/><i>existing projects only</i>"]:::step
        G1{{"Gate 1 &nbsp;·&nbsp; review &amp; approve"}}:::gate
        S2["<b>Step 2 · Phase sub-plans</b><br/><i>+ coverage index</i>"]:::step
        G2{{"Gate 2 &nbsp;·&nbsp; approve the audit"}}:::gate
        S3["<b>Step 3 · Quality audit</b><br/><i>PASS / WARN / BLOCKED</i>"]:::step
    end

    subgraph BUILD["Implementation &nbsp;·&nbsp; the only code-touching step"]
        direction TB
        G3{{"Step-4 gate &nbsp;·&nbsp; clean audit, no blockers"}}:::gate
        S4["<b>Step 4 · Implement one slice</b><br/><i>optional · reversible · you approve</i>"]:::build
    end

    Start --> S1 --> S15 --> G1 --> S2 --> G2 --> S3 --> G3 --> S4

    classDef start fill:#2563EB,stroke:#1E40AF,color:#FFFFFF;
    classDef step fill:#1E293B,stroke:#38BDF8,color:#E2E8F0;
    classDef gate fill:#0F172A,stroke:#FACC15,color:#FACC15;
    classDef build fill:#064E3B,stroke:#34D399,color:#D1FAE5;
    style PLAN fill:#0B1220,stroke:#334155,color:#94A3B8;
    style BUILD fill:#0B1220,stroke:#334155,color:#94A3B8;
```

| Step | Name | What happens | Your part |
|:--:|---|---|---|
| **1** | Master plan | Repo-aware intake, then a senior-architect plan written to `Main-Planning.md`. | Answer 4 questions |
| **1.5** | Autopsy | For existing projects, a technical health report in `Autopsy.md`. | — (auto / skipped) |
| **Gate 1** | Review | Review the plan (and autopsy) together. | Feedback + approve |
| **2** | Sub-plans | Every phase becomes detailed sub-plans plus an index. | — |
| **Gate 2** | Approve audit | Confirm you want the quality audit. | Approve |
| **3** | Audit | Coverage/quality audit with a `PASS` / `PASS_WITH_WARNINGS` / `BLOCKED` status. | Approve repairs if needed |
| **4** | Implement | One bounded, reversible code slice from a `READY` sub-plan. | Approve (gated) |

---

## What you'll get

Every artifact lands under `Planner-docs/` in **your** workspace — never in the plugin folder:

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

---

## Commands

| Command | What it does |
|---|---|
| `/qb-plan` | Run the full five-step workflow from the start. |
| `/qb-autopsy` | Analyze an existing repository only (Step 1.5). |
| `/qb-audit` | Re-run the quality audit only (Step 3). |
| `/qb-implement` | Implement one reviewed slice (Step 4, gated). |

---

## You stay in control

- Steps 1–3 only write inside `Planner-docs/` — they **never** modify your source code, config, tests, or scripts.
- Step 4 is the **only** step that edits code, and only after the audit passes and you approve — one reversible slice at a time.
- It never commits, pushes, opens a PR, or calls external systems unless you explicitly ask.
- No secrets, tokens, or credentials are ever written into a file.
- QB pauses for your explicit approval at every gate.

---

## Requirements

- **Cursor** with plugin support.
- **`python3`** *(optional)* — powers the bundled validator and tests, with a manual fallback when it is missing.

---

## FAQ

<details>
<summary><strong>Will it change my code?</strong></summary>

Not during planning. Only Step 4 touches code, and only with your explicit approval — one bounded, reversible slice at a time.
</details>

<details>
<summary><strong>What if my repo is brand new or empty?</strong></summary>

The autopsy is skipped automatically — you still get a full master plan and sub-plans.
</details>

<details>
<summary><strong>What language is the output in?</strong></summary>

Questions follow your language; all planning documents are written in English.
</details>

<details>
<summary><strong>Can I rename the planning files?</strong></summary>

No. `Main-Planning.md`, `Sub-Planning-Index.md`, `Sub-Planning-Audit.md`, and the `Phase-<n>-Plans/` / `Phase<n>.<m>-*.md` patterns are fixed identifiers the validator and the index cross-references match exactly. The document *content* is English.
</details>

<details>
<summary><strong>Do I need an API key or a terminal tool?</strong></summary>

No. QB runs entirely in-session inside Cursor.
</details>

---

## Development

```bash
make check   # validate the manifest, required files, frontmatter, and cross-host residue
```

Further reading: [`docs/INSTALLATION.md`](docs/INSTALLATION.md) ·
[`docs/USAGE.md`](docs/USAGE.md) ·
[`docs/MAINTAINING.md`](docs/MAINTAINING.md) ·
[`CHANGELOG.md`](CHANGELOG.md)

---

<div align="center">

**[MIT](LICENSE)** © Alican Kiraz

Ported from the upstream CursorQB / CodexQB workflow by Alican Kiraz.

</div>
