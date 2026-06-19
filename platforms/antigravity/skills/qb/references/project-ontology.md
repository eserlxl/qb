# QB Project Ontology

QB uses `.qb/project-ontology.md` as an optional durable project-understanding artifact.

## Purpose

The ontology helps Antigravity and coding agents understand the project's language, boundaries, workflows, and invariants before planning or implementation.

## Recommended File

```text
.qb/project-ontology.md
```

## Recommended Headings

```markdown
# Project Ontology

## 1. Purpose
## 2. Domain Vocabulary
## 3. Core Entities and Concepts
## 4. Module and Boundary Map
## 5. Workflows and Lifecycles
## 6. Integrations and External Systems
## 7. Invariants and Constraints
## 8. Open Ontology Questions
```

## What to Capture

- domain nouns and verbs;
- core entities and their lifecycle states;
- modules and ownership boundaries;
- workflows and state transitions;
- integration points and external systems;
- security, compliance, or business invariants;
- ambiguous terms that require human confirmation.

## Competency Questions (Section 8)

Record `## 8. Open Ontology Questions` as a competency-questions table so each unknown is
tracked to an evidence-backed answer instead of staying implicit:

```markdown
| Question ID | Question | Status | Evidence |
|---|---|---|---|
| CQ-01 | Which module owns user-session expiry? | answered | `auth/session.py:expire()` |
| CQ-02 | Is the billing webhook idempotent? | open | — |
```

- Status enum: `answered`, `partially_answered`, `open`, `contradicted`.
- A `contradicted` row means repo evidence conflicts with a documented or assumed answer; record both sides and the next probe.
- Promote a question out of `open` only when concrete evidence (source, test, runtime, history, configuration, documentation, or user confirmation) supports the answer; otherwise leave it `open` for Step 2 to turn into validation work.

## Evidence and Confidence

Back ontology claims with an Evidence Register so terms, entities, and invariants are
not asserted from assumption:

```markdown
| Evidence ID | Claim | Evidence source | Evidence type | Confidence | Next probe |
|---|---|---|---|---|---|
```

- Evidence types: `source`, `test`, `runtime`, `history`, `configuration`, `documentation`, `user-confirmed`.
- Confidence: `confirmed`, `probable`, `tentative`, `contradicted`. A `tentative` or `probable` claim is not a fact — it is work for Step 2 to validate.
- Independence rule: a behavioral claim needs `test`/`runtime` evidence, or two independent evidence types with **different locators**; two documentation rows alone are not independent proof.
- For unresolved why/how/what questions, record a hypothesis (`HYP-01: <claim>`, supporting/contradicting evidence, next probe) rather than asserting a conclusion.

## How to Use It

- Step 1.5 should create or update the ontology for existing projects when enough evidence exists.
- Step 2 should use it to keep sub-plans consistent with project concepts and boundaries.
- Step 3 should audit whether plans contradict important invariants.
- Step 4 should read only the ontology sections relevant to the active slice.

## Safety

Do not include secrets, local credentials, private customer data, or full production data examples. Use redacted examples or abstract concept names when needed.
