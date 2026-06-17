# QB Regression Baseline

This is the committed gate-of-record baseline for QB. Cloud CI is disabled on the
account, so a green **local** `make check` is the authoritative no-regression
signal (see the README "Continuous integration" section). This document records the
verified floor every forward phase builds on, so any deviation from it reads as a
regression rather than an unknown.

## Gate of record

The gate of record is `make check`, run on a clean working tree.

| Field | Value |
|---|---|
| Command | `make check` |
| Observed exit status | `0` |
| Version (`VERSION`) | `0.14.1` |
| Commit | `5f97f35` |
| Date | 2026-06-17 |

`make check` composes `bash scripts/sync.sh --check`, the four per-host
`platforms/<host>/scripts/validate.sh` validators, then
`python3 -m unittest discover -s tests`. The run recorded above completed with every
sub-step green. No source, engine, or test behavior was changed to capture this
baseline.

## Test-suite counts

The full unit-test discovery is the frozen regression reference. Reproduce with:

```bash
python3 -m unittest discover -s tests -v
```

| Metric | Baseline value |
|---|---|
| Test modules (`tests/test_*.py`) | 44 |
| Test functions | 324 |
| Failures | 0 |
| Errors | 0 |
| Exit status | 0 |

A run reporting fewer than 44 modules or fewer than 324 passing functions, or any
failure or error, is a regression against this reference.

## Baseline preconditions

The baseline reproduces on a stock toolchain so it stays machine-independent:

- **Python 3, standard library only.** The gate of record invokes
  `python3 -m unittest discover -s tests` plus the bash/coreutils host validators;
  no third-party Python package is required for a green run.
- **`pyflakes` and `ruff` are optional and dormant when absent.** They enrich the
  `correctness` and `quality` analyzers when already installed, but `make check`
  does not require them and is green without them. Their absence is a coverage
  caveat (recorded below), not a baseline failure.

Because the gate is stdlib-only, a green `make check` on one machine reproduces on
another without installing the optional analyzers.

## Invariant inventory

`make check` is not one opaque signal; it composes the sub-steps below, each
enforcing a named invariant and individually runnable so a regression can be
localized to one guard.

| Sub-step (command) | Invariant enforced |
|---|---|
| `bash scripts/sync.sh --check` | Every platform copy is byte-equal to its `shared/` source, and every shared file is wired into the fan-out MAP. |
| `bash platforms/claude-code/scripts/validate.sh` | The Claude Code package validates: manifest identity, frontmatter, and no cross-host launch-syntax residue. |
| `bash platforms/cursor/scripts/validate.sh` | The Cursor package validates the same per-host contract. |
| `bash platforms/antigravity/scripts/validate.sh` | The Antigravity (planning-only) package validates its own contract. |
| `cd platforms/codex && bash scripts/validate.sh` | The Codex package validates the same per-host contract. |
| `python3 -m unittest discover -s tests` | The full cross-platform invariant suite (44 modules / 324 functions) passes. |

A red `make check` is diagnosed by re-running the failing sub-step in isolation;
each command above is self-contained.

## Guard-to-test mapping

Each baseline guard maps to a named, individually runnable per-module command, so a
failure inside the test sub-step can be re-run in isolation:

| Guard | Per-module command |
|---|---|
| Sync byte-equality mechanism | `python3 -m unittest tests.test_sync_mechanism` |
| Version + structure lockstep | `python3 -m unittest tests.test_version_and_structure` |
| Manifests + skill frontmatter | `python3 -m unittest tests.test_manifests_and_frontmatter` |
| No cross-host launch-syntax residue | `python3 -m unittest tests.test_no_cross_host_residue` |
| Every shared file mapped into the fan-out | `python3 -m unittest tests.test_sync_map_completeness` |
| Docs/engine drift guard | `python3 -m unittest tests.test_doc_consistency` |
| Committed-secret hygiene | `python3 -m unittest tests.test_no_committed_secrets` |

Run all seven together as the baseline guard set:

```bash
python3 -m unittest tests.test_sync_mechanism tests.test_version_and_structure \
  tests.test_manifests_and_frontmatter tests.test_no_cross_host_residue \
  tests.test_sync_map_completeness tests.test_doc_consistency \
  tests.test_no_committed_secrets
```
