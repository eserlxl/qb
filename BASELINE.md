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
