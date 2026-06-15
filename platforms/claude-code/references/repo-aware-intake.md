# Repo-Aware Step 1 Intake

Use this reference before `first-planner.md` when QB starts a normal Step 1
planning run. The goal is to ask the same four required fields, but make the questions
active, evidence-backed, and useful for an existing repository.

## Boundaries

- Ask in the user's language (interactive mode).
- In the per-field fallback, ask one field per turn; the well-structured fast path instead presents a single consolidated confirmation (see "Well-Structured Fast Path").
- Use plain text only. Do not use pop-ups, forms, or multiple-choice UI for these four descriptive fields.
- Do not write files during intake.
- Do not run networked, destructive, install, commit, push, deploy, or PR commands.
- Treat the current working directory (the user's active workspace) as the project repository.
- Make it clear when a statement is inferred from repo evidence.
- If evidence is weak, say that repo evidence is limited and ask the concise generic version of the question.

## Pre-Intake Scan

Before asking `PROJECT_NAME`, inspect the repository with a bounded read-only pass.
Prefer commands like:

```bash
pwd
git status --short --branch
git branch --show-current
find . -maxdepth 2 -type f | sort | head -120
find . -maxdepth 2 -type d | sort | head -80
ls
```

Read likely evidence files when they exist: `README.md`, `AGENTS.md`, `Makefile`,
`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `docker-compose.yml` or
`compose.yml`, `.github/workflows/*.yml`, and `docs/` index/architecture/roadmap/runbook/
deployment/security/testing files, plus top-level service, package, app, config, script,
test, and infra directories.

Use `rg` only for targeted discovery when useful:

```bash
rg -n "architecture|roadmap|runbook|production|security|policy|workflow|worker|scheduler|gateway|adapter|dashboard|test|smoke|deploy|Kubernetes|Docker|Postgres|queue|approval|audit|artifact|observability" .
```

Keep this pass brief. Its purpose is to make the intake questions smarter, not to replace
the full repository analysis in `first-planner.md`.

## What To Infer

Infer a draft answer only when there is evidence.

- `PROJECT_NAME`: prefer README title, package/app name, repository directory name, product docs, or manifest names.
- `PROJECT_INTENT`: infer what the project does, its target users, main components, integrations, and what it seems to be trying to become.
- `TARGET_END_STATE`: draft the "done" state across product, engineering, operations, security, and user value.
- `KNOWN_CONSTRAINTS`: infer stack, deployment model, test commands, CI, compliance/security boundaries, must-use tools, must-not-use tools, timeline hints, and unknowns that need user confirmation.

In interactive mode, do not treat inferred values as final until the user confirms or edits
them; in auto mode the fail-closed derivation (see "Well-Structured Fast Path") is authoritative.

## Well-Structured Fast Path

Use this fast path when the workspace is a **well-structured repository** and the Pre-Intake
Scan yields strong evidence for the fields. Treat the repository as well-structured when the
scan finds at least three of these five signals, including either a README or a manifest:

- a README (`README*`);
- a manifest or build file (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`,
  `Makefile`, `composer.json`, `Gemfile`, or similar);
- a source directory (`src/`, `lib/`, `app/`, or a package/service directory);
- a tests directory (`tests/`, `test/`, `spec/`, or co-located test files);
- a CI config (`.github/workflows/*`, `.gitlab-ci.yml`, or similar).

When the repo is well-structured, derive all four fields (`PROJECT_NAME`, `PROJECT_INTENT`,
`TARGET_END_STATE`, `KNOWN_CONSTRAINTS`) from the Pre-Intake Scan and the "What To Infer"
guidance, then:

- **Interactive mode:** present all four derived fields together in a **single consolidated
  confirmation** (plain text, no forms), each marked as repo-inferred, and ask the user to
  confirm them or edit any. User edits are the source of truth. If a particular field's evidence
  is weak, mark it and fall back to its per-field question (see "Question Style") for that field
  only, while batch-confirming the rest (when asking a single follow-up field, the per-field
  template's "Question N / 4" header may be dropped or relabeled).
- **Auto mode (`/qb-plan auto`):** do not ask for confirmation. If all four fields derive with
  sufficient evidence, record them and proceed. If any field cannot be derived with sufficient
  evidence, do **not** prompt - print this line and stop, creating no `.qb/` artifacts:
  `QB_PLAN_AUTO_ERROR: missing required field(s): <comma-separated names> (insufficient repo evidence)`

When the repository is **not** well-structured (few signals, empty, or scaffold-only), skip the
fast path and use the per-field "Question Style" flow below. All intake boundaries still apply:
ask in the user's language (interactive mode), never write files during intake, and run no
networked, destructive, install, commit, push, deploy, or PR commands.

## Question Style

Use this per-field flow when the repository is not well-structured, or for any single field
whose evidence is weak (the well-structured fast path above handles the strong-evidence case).

Start with a short setup sentence (translate to the user's language when it is not English):

```text
I will ask a few short questions, one field per turn. I will enrich them with the evidence I find in the repository; after your answers I will generate the master plan.
```

### Question 1 / 4 - PROJECT_NAME

```text
Question 1 / 4 - PROJECT_NAME (Project Name)

Let's clarify which project this plan is for.

From what I can see in the repository, this project looks like "<inferred name>". Evidence: <short evidence: README title, package name, or repo folder>.

Can I take the project name as "<inferred name>", or would you like me to use a different/official name?
```

If evidence is weak:

```text
Question 1 / 4 - PROJECT_NAME (Project Name)

Repository evidence is limited, so I need you to clarify the project name.

Which project name should this plan be prepared for?
```

After the answer, confirm: `PROJECT_NAME = "<final value>" recorded.`

### Question 2 / 4 - PROJECT_INTENT

```text
Question 2 / 4 - PROJECT_INTENT (Project Purpose)

This field explains why the project exists and what it wants to become.

Here is the draft I derived from the repository:

<1-2 short paragraphs: inferred purpose, components, target users, direction.>

Questions:
1. Is this description correct, or are there points you want to fix/add?
2. What is the ultimate goal the project wants to become?
```

After the answer, confirm: `PROJECT_INTENT recorded: <short normalized summary>.`

### Question 3 / 4 - TARGET_END_STATE

```text
Question 3 / 4 - TARGET_END_STATE (Target End State / Definition of "Done")

I want to clarify the definition of "done" across five dimensions. Draft based on repo evidence:

- Product: <product outcome>
- Engineering: <engineering outcome>
- Operations: <operations outcome>
- Security: <security outcome>
- User value: <user-value outcome>

Do these five dimensions reflect your definition of "done"? Anything you want to add or remove?
```

After the answer, confirm: `TARGET_END_STATE recorded: <short normalized summary>.`

### Question 4 / 4 - KNOWN_CONSTRAINTS

```text
Question 4 / 4 - KNOWN_CONSTRAINTS (Known Constraints)

Constraint draft from what I saw in the repo or what is not yet clear:

- Stack/tools: <detected stack or unknown>
- Operations/infra: <detected deployment/runtime or unknown>
- Test/validation: <detected commands or unknown>
- Security/compliance: <detected boundaries or unknown>
- Time/team/budget: <known if present, otherwise unknown>
- Must-use / must-not-use: <known if present, otherwise unknown>

Is there anything I should add, correct, or specifically avoid in this list?
```

After the answer, confirm: `KNOWN_CONSTRAINTS recorded: <short normalized summary>.`

## After Intake

When all four fields are confirmed:

1. Read `first-planner.md` (bundled next to the Step 1 planner skill under `planners/`).
2. Substitute the confirmed field values into the placeholders, in memory only.
3. Treat user-confirmed field values as source of truth.
4. Treat repo-inferred intake notes as supporting context only.
5. Continue with the full Step 1 repository analysis required by `first-planner.md`.
