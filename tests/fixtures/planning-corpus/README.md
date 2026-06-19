# Planning-skill eval corpus

Ground-truth fixtures for QB's **planning / comprehension** skills (Step 1 – Step 3),
distinct from `tests/fixtures/precision-corpus/`, which exercises the security
*analyzer* engine. Each fixture is a tiny self-contained repository plus an
`expected.json` describing the comprehension signals, concept→code traces,
architecture-reflexion statuses, and quality checks a correct assessment should
surface.

Adapted from the upstream ClaudeQB fixture corpus, renamed to QB conventions
(`Planing`→`planning`, `Faz`→`phase`, `Planner-docs/`→`.qb/`).

## Fixtures

| Fixture | Scenario |
|---|---|
| `clean-layered-service` | Intended and implemented architecture agree (convergent). |
| `drifted-architecture` | Source contradicts the documented boundary (divergent). |
| `distributed-domain-feature` | One concept spans several runtime modules/state surfaces. |
| `hidden-coupling-signal` | Co-change history hints at unmodeled coupling. |
| `stale-ledger` | A planning ledger that has drifted from the code. |
| `runtime-only-behavior` | Correct understanding needs runtime/smoke evidence, not static reads. |
| `security-boundary-risk` | A command-execution boundary that must be captured as a security finding. |

## `expected.json` schema

Required keys (all non-empty string lists except `id`/`description`):
`id`, `description`, `expected_comprehension_signals`, `expected_trace_ids`,
`expected_architecture_statuses`, `expected_quality_checks`.

`expected_architecture_statuses` values come from the architecture-reflexion
vocabulary: `convergent`, `divergent`, `unmodeled`, `uncertain`.

## Scope caveat (important)

`tests/test_planning_corpus.py` is a **schema/shape validator only** — it keeps the
fixtures and their expected signals well-formed so future live skill evals have stable
inputs. It does **not** run a planning skill or grade real model output. A live grading
harness that compares actual assessment output against these expectations is a separate,
future piece of work; this corpus is the foundational input for it.
