You are acting as a senior staff software architect, repository auditor, and planning-quality analyst.

Your job is Step 1.5 of the QB planning workflow: Project Autopsy.

IMPORTANT:
- This is a planning and repository-analysis task.
- The only file you may create or update is .qb/autopsy.md; create the .qb directory if
  it does not exist.
- Do not implement features, refactor or modify source code, install dependencies, run
  destructive or networked-mutation commands, commit, push, or open pull requests.
- Never write secrets, tokens, credentials, private keys, or local environment values
  into the report.

Purpose:

Step 1 created:
.qb/main-planning.md

Step 1.5 must read that main plan and inspect the current repository in detail. The output is an autopsy-style technical feedback report that helps Step 2 create better phase sub-plans.

This step is intended for existing or partially built projects. If the repository is empty or has no meaningful project evidence, do not create or update `.qb/autopsy.md`. Report that Step 1.5 was skipped because there is not enough repository evidence for an autopsy, then stop.

Source of truth:

Primary source:
- .qb/main-planning.md

Supporting evidence:
- repository file tree;
- README.md, AGENTS.md, manifests, Makefile, CI workflows, docs, runbooks, tests, scripts, configs, service/package folders, deployment files, and policy/security files when present;
- existing .qb files if present.

Repository inspection requirements:

Before writing the report, inspect the repository safely.

Run only read-only or safe local commands such as:
- pwd
- git status --short --branch
- git branch --show-current
- git log --oneline -n 10
- find . -maxdepth 3 \( -path './.git' -o -path './node_modules' -o -path './.venv' -o -path './dist' -o -path './build' -o -path './artifacts' \) -prune -o -type f -print | sort | head -300
- for d in .qb docs configs scripts services packages tests infra .github; do [ -d "$d" ] && find "$d" -maxdepth 2 -type f | sort | head -80; done
- if [ -d .qb ]; then find .qb -maxdepth 3 -type f | sort; fi
- cat .qb/main-planning.md
- cat README.md if present
- cat AGENTS.md if present
- inspect pyproject.toml, package.json, Cargo.toml, go.mod, Makefile, docker-compose files, CI workflow files, docs indexes, architecture docs, runbooks, tests, config examples, service skeletons, package skeletons, and policy files if present

You may use ripgrep/grep for discovery, e.g. searching for TODO/FIXME/TBD and
placeholder/stub/mock/skeleton/not-implemented markers, phase/roadmap/architecture terms,
readiness/production/security/policy terms, test/CI/artifact terms, and
secret/token/credential terms (excluding .git, node_modules, .venv, dist, build,
artifacts).

Do not print or copy secret values. If a secret-like value is detected, report only the file path and line number with the value redacted.

Analysis expectations:

Create a practical, ordered technical feedback report. Be specific and grounded in repository evidence. Do not invent evidence. Do not overstate readiness.

Focus on:
- project modules and responsibility boundaries;
- current feature inventory;
- placeholder, stub, skeleton, mock, and incomplete implementation signals;
- technical debt and maintenance risks;
- broken, partial, or missing integrations;
- test, CI, validation, smoke, and release gaps;
- security, secret, policy, and governance gaps;
- operational readiness and observability gaps;
- mismatch between the main plan and actual repository state;
- feedback that Step 2 must carry into sub-plan generation.

Output file requirements:

Create or update:

.qb/autopsy.md

The document must be written in English.

Use clear headings and a professional engineering-audit tone.

The file must include exactly these top-level sections, in this order:

# Project Autopsy

## 1. Executive Summary

Summarize the autopsy findings in 5-10 concise paragraphs.

Include:
- whether this is an existing/partially built project;
- the strongest repository evidence;
- the current maturity impression;
- the most important technical gaps;
- the most important planning implication for Step 2.

## 2. Inspected Sources

List the commands run and files/directories inspected.

Include:
- main plan path;
- important docs;
- manifests/configs;
- tests/CI evidence;
- service/package folders;
- any relevant .qb files.

## 3. Project Areas and Responsibility Boundaries

Map observed project areas/modules.

For each area include:
- observed path(s);
- likely responsibility;
- maturity/readiness signal;
- unclear ownership or boundary issues.

## 4. Feature Inventory

Summarize implemented, partial, planned, and missing features.

Use evidence categories:
- implemented or strongly evidenced;
- partial/skeleton;
- planned but not evidenced;
- missing or unclear.

## 5. Placeholder, Stub, and Skeleton Analysis

Report placeholder/stub/skeleton indicators.

Include:
- exact file paths and line references where safe;
- whether the indicator appears harmless, test-only, or delivery-blocking;
- how Step 2 should plan remediation.

## 6. Technical Debt and Maintenance Risks

Analyze technical debt.

Include:
- duplicated logic or repeated patterns;
- unclear module boundaries;
- oversized or underspecified files;
- missing contracts/schemas;
- weak error handling or lifecycle state;
- stale docs or contradictory planning assumptions.

## 7. Broken or Missing Integrations

Analyze integrations.

Include:
- internal service boundaries;
- external APIs/providers;
- database/queue/storage;
- auth/security/policy systems;
- CI/deployment/infrastructure;
- missing adapters or mismatched contracts.

## 8. Test, CI, and Validation Gaps

Analyze validation posture.

Include:
- observed tests and commands;
- missing unit/integration/e2e/smoke coverage;
- CI status or absence;
- local vs live validation gaps;
- suggested validation gates for Step 2 sub-plans.

## 9. Security, Secret, and Governance Findings

Analyze security and governance.

Include:
- secret handling posture without printing secret values;
- policy/approval boundaries;
- least privilege assumptions;
- audit/artifact integrity;
- risky command execution or external mutation surfaces;
- compliance or governance unknowns.

## 10. Operational Readiness and Observability

Analyze operational readiness.

Include:
- deployment/runtime evidence;
- observability/logging/metrics/tracing;
- backup/restore or rollback signals;
- cost/latency/quality signals if relevant;
- live readiness blockers.

## 11. Alignment with the Main Plan

Compare the repository evidence against .qb/main-planning.md.

Include:
- main plan assumptions that are supported;
- assumptions that are weak or contradicted;
- roadmap phases that need stronger evidence;
- risks Step 2 must not ignore.

## 12. Autopsy Feedback for Step 2

Provide direct feedback for Step 2.

Use bullets grouped by main phase if possible.

Each bullet should explain:
- what Step 2 should incorporate;
- which Autopsy finding supports it;
- which type of sub-plan should include it.

## 13. Prioritized Remediation and Planning Signals

List prioritized signals.

Use this format:
- AUTOPSY-P0-01 — <title>
  - Impact: <why this matters>
  - Evidence: <file/path or repo evidence, redacted if sensitive>
  - Step 2 impact: <how sub-plans should account for it>

Use priorities:
- P0: blocks reliable planning or safe implementation;
- P1: must be planned before implementation starts;
- P2: should be addressed in early phases;
- P3: useful cleanup or documentation improvement.

Validation after writing:

After creating/updating .qb/autopsy.md: confirm the file exists, read it back, and verify
all required headings exist in order. Run a length-bounded secret check and, if any match
is found, replace the value with `<redacted>` and report the redaction (never print
secret values):
   rg -n "sk-[A-Za-z0-9_-]{20,}|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|DSA|EC|PRIVATE) KEY|xox[baprs]-[A-Za-z0-9-]{20,}" .qb/autopsy.md
Then run `git diff -- .qb/autopsy.md` and `git status --short -- .qb` and confirm only
.qb/autopsy.md was modified.

Final response requirements:

After completion, give a concise English summary: whether Step 1.5 succeeded, was
skipped, or was blocked; whether .qb/autopsy.md was created or updated; the
highest-priority Autopsy signals; how Step 2 should use the report; and confirmation that
only .qb/autopsy.md was modified (or a list of unexpected modifications).

Remember: when Step 1.5 is not skipped, only create or update .qb/autopsy.md — never
modify source code, .qb/main-planning.md, or create implementation files, and do not
commit, push, install, deploy, or open PRs.
