# QB Probe Policy

Use this graduated probe policy when gathering runtime or behavioral evidence during
Step 1.5 Assessment or Step 4 verification. Prefer the lowest tier that can answer the
question, and never silently promote a low-confidence claim to a fact — record the
contradiction and the next probe instead.

QB's planning steps stay read-only by default (see `assessment-planner.md`). Tiers 1+
are evidence-gathering escalations, each with explicit approval, timeout, cleanup, and
evidence-artifact discipline.

## Tier 0: Static Local Probe

Read-only file inspection, manifest parsing, git-history inspection, and local
documentation review.

- Approval: not required.
- Timeout: keep commands short and bounded.
- Cleanup: none expected.
- Evidence artifact: a concise path, line, or command summary.

## Tier 1: Bounded Local Probe

Non-mutating local commands that produce no durable state — for example building,
running existing tests, linting, type-checking, or a focused smoke command.

- Approval: not required for standard, well-known repo commands; note when a command is unusual.
- Timeout: define a bounded timeout before starting.
- Cleanup: none expected; do not leave background processes running.
- Evidence artifact: command, exit status, and a short result summary.

## Tier 2: Stateful Local Probe

Commands that create local databases, containers, generated artifacts, caches,
migrations, or other durable state.

- Approval: get explicit user approval when state creation is non-trivial or cleanup is uncertain.
- Timeout: define the timeout before starting.
- Cleanup: document cleanup commands and remove generated temporary state when practical.
- Evidence artifact: artifact path, command, exit status, cleanup status, and remaining local state.

## Tier 3: External / Live Probe

Network calls, live services, cloud resources, paid APIs, production-like
infrastructure, deployments, or external mutations.

- Approval: explicit user approval is required.
- Timeout: define a bounded timeout and a stop condition.
- Cleanup: document rollback or cleanup steps before any mutation.
- Evidence artifact: never include secrets; record endpoint class, command summary, status, and redacted evidence only.

## General Rules

- Prefer the lowest tier that can answer the question; escalate only when the lower tier cannot.
- Record the tier used alongside the evidence so reviewers know how a claim was obtained.
- When evidence contradicts an assumption, record the contradiction and the next probe; do not silently promote the claim.
- All probe evidence follows the same secret discipline as the rest of QB (see `workflow-quality.md`): never print secret values; redact and report only paths/line numbers.
