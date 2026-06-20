# QB Regression Baseline

This is the committed gate-of-record baseline for QB. Cloud CI is disabled on the
account, so a green **local** `make check` is the authoritative no-regression
signal (see the README "Continuous integration" section). This document records the
verified baseline every forward phase builds on, so any deviation from it reads
as a regression rather than an unknown.

## Gate of record

The gate of record is `make check`, run on a clean working tree.

| Field | Value |
|---|---|
| Command | `make check` |
| Observed exit status | `0` |
| Version (`VERSION`) | `0.19.0` |
| Commit | `9ab9e4a` |
| Date | 2026-06-20 |

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
| Test modules (`tests/test_*.py`) | 81 |
| Test functions | 639 |
| Failures | 0 |
| Errors | 0 |
| Exit status | 0 |

A run reporting anything other than 81 modules or 639 passing test cases, or any
failure or error, is a regression against this reference.

**Same-change update rule:** adding or removing a test module or test case must
update the recorded counts above in the **same change**. `tests/test_baseline_consistency.py`
re-derives the live counts and fails if they drift, so a test add/remove that skips
the baseline update turns the next `make check` red; diagnose by the per-guard
**Guard-to-test mapping** below.

**Authoritative count source:** the test-function count is live
`unittest` discovery (`unittest.TestLoader().discover('tests').countTestCases()`),
the operator-visible number — never a `def test_` text grep, which miscounts
(a text grep counts `def test_*` strings inside fixtures that are not real
tests, so it undercounts the live total). Use
`python3 -m unittest discover -s tests -v` (or `make baseline`) to read the
count; do not "correct" the baseline from a source-text regex.

## Baseline preconditions

The baseline reproduces on a stock toolchain so it stays machine-independent:

- **Python 3, standard library only.** The gate of record invokes
  `python3 -m unittest discover -s tests` plus the bash/coreutils host validators;
  no third-party Python package is required for a green run.
- **`pyflakes` and `ruff` are optional and dormant when absent.** They enrich the
  `correctness` and `quality` analyzers when already installed, but `make check`
  does not require them and is green without them. Their absence is recorded in
  the quality analyzer capability report as `tool-unavailable` with the missing
  executable name. This is a coverage caveat (recorded below), not a baseline
  failure.

Because the gate is stdlib-only, a green `make check` on one machine reproduces on
another without installing the optional analyzers.

## Invariant inventory

`make check` is not one opaque signal; it composes the sub-steps below, each
enforcing a named invariant and individually runnable so a regression can be
localized to one guard.

| Sub-step (command) | Invariant enforced |
|---|---|
| `bash scripts/sync.sh --check` | Every platform copy is byte-equal to its `shared/` source, and every shared file is wired into the fan-out MAP. |
| `bash platforms/claude-code/scripts/validate.sh` | The Claude Code package validates: manifest identity, frontmatter, no cross-host launch-syntax residue, and tracked-file secret hygiene. |
| `bash platforms/cursor/scripts/validate.sh` | The Cursor package validates the same per-host contract. |
| `bash platforms/antigravity/scripts/validate.sh` | The Antigravity (planning-only) package validates its own contract. |
| `cd platforms/codex && bash scripts/validate.sh` | The Codex package validates the same per-host contract. |
| `python3 -m unittest discover -s tests` | The full cross-platform invariant suite (81 modules / 639 functions) passes. |

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

## Done-definition for `shared/` edits

`shared/` is the single source of truth; `scripts/sync.sh` fans each shared file
out to the three engine-bearing host packages, and `scripts/sync.sh --check`
verifies the copies are byte-equal. Editing a `shared/` file without re-running the
fan-out leaves the host copies stale — drift that only the gate catches.

**Done-definition:** any change under `shared/` is not done until both of these run
clean, in order:

```bash
make sync      # materialize shared/ into the host packages
make check     # verify byte-equality + the full invariant suite
```

This is a repeatable contributor step, not tribal knowledge: a `shared/` change
that skips `make sync` will fail `bash scripts/sync.sh --check` (and therefore
`make check`).

## Capability and gap baseline

This is the authoritative "before" state every forward phase closes against.

### Shipped today

- Repo-aware staged planning (`.qb/` artifacts) with read-only, dependency-free
  validators at every step and a planwright export path.
- A dependency-free audit engine, A0 report-only by default, with the seven producer
  analyzers and frozen finding categories named in the README.
- Disposable git **write isolation** for proposed fixes — a throwaway worktree; the
  target working tree is untouched until a fix verifies and is promoted.
- Policy, verification, rollback, release, and production gates with fail-closed
  defaults and a namespaced pre-run reversal handle (`refs/qb-baseline/<run_id>`).
- Four native host packages over one synced shared core (Antigravity planning-only).

### Known gaps (each tagged to its closing phase)

| Gap | Status today | Closing phase |
|---|---|---|
| Full execution sandboxing of analyzed code | QB ships disposable write isolation plus command-level process confinement, but not filesystem, network, syscall, or container isolation for arbitrary analyzed code | Phase 1 hardens confine-by-default / sandboxed authorization; full execution sandboxing of analyzed code remains a boundary item per the README |
| Live A2/A3 autonomy proofs | Gates exist; end-to-end campaign evidence over a labelled corpus is pending | Phase 3 (corpus campaigns / autonomy proofs) |
| Disabled cloud CI | Local `make check` is the gate of record | Phase 0 (this baseline + regression net compensate) |
| Analyzer breadth / environment-dependence | `pyflakes`/`ruff` optional and dormant when absent | Phase 2 (analyzer coverage) |
| Antigravity parity | Planning-only; not a `sync.sh` destination; ships no audit engine | Phase 5 (multi-host parity) |

These statements mirror the existing README and RUNBOOK claims (notably the full
execution sandboxing "not yet shipped" caveat and the planning-only Antigravity
model) and do not supersede them.

## M7 readiness checklist

M7 (the roadmap's Production-Gated M7 Consolidation phase) is reached when **every**
prior-phase acceptance signal jointly holds, each re-derivable from a committed gate
rather than a narrative claim. Each row below names its joint acceptance signal
(meaning-equivalent to the roadmap's Key Acceptance Signals), a committed evidence
source (a tracked file or engine module — **never** a `.qb/` planning note), and the
command that re-derives it. A row is **green** iff its re-deriving command exits 0; M7
holds only when the Phase 0 floor and every Phase 1–5 row are jointly green. Each row
cross-references its closing-phase row in **Known gaps** above.

| Phase | Joint acceptance signal | Evidence source (committed) | Re-derives via | Known-gaps row |
|---|---|---|---|---|
| 0 — Baseline & Regression Net (floor) | `make check` exits 0 on a clean tree; baseline module/case counts unchanged; gate-of-record caveats documented | `BASELINE.md`, `.github/workflows/validate.yml`, `tests/test_baseline_consistency.py` | `make check` | Disabled cloud CI |
| 1 — Execution-Isolation Hardening | Confine-by-default / sandboxed-authorization gate enforced and tested; SECURITY/README posture pinned; isolation regressions green | `shared/scripts/isolation.py`, `shared/scripts/command_safety.py`, `tests/test_isolation_runtime.py` | `make check` | Full execution sandboxing of analyzed code |
| 2 — Analyzer Coverage & Determinism | Precision/recall bars met; analyzer-coverage doc and engine in sync; no silent dormant-analyzer gap | `tests/fixtures/precision-thresholds.json`, `shared/scripts/precision_harness.py`, `docs/analyzer-coverage.md` | `make precision` | Analyzer breadth / environment-dependence |
| 3 — Live A2/A3 Autonomy Proofs | A2/A3 campaign tests pass over the trusted corpus; verification evidence persisted; no isolation/gate escape | `tests/test_a1_campaign.py`, `tests/test_a2_campaign.py`, `tests/test_a3_campaign.py` | `make check` | Live A2/A3 autonomy proofs |
| 4 — Operations, Telemetry & Recoverability | Recoverability drill passes; the production gate's six fail-closed conjuncts hold (`telemetry_emitted`, `rollback_drill_passed`, `least_privilege_ok`, `supply_chain_ok`, `killswitch_proven`, `self_audit_clean`); telemetry trends render from a real series | `shared/scripts/recoverability_drill.py`, `shared/scripts/production_gate.py`, `tests/test_telemetry_trends.py` | `make check` | (operations maturity — no open gap row) |
| 5 — Multi-Host Parity | `scripts/sync.sh --check` byte-equal across engine hosts; Antigravity planning-only contract pinned; host-parity tests green | `scripts/sync.sh`, `platforms/PARITY.md`, `tests/test_host_parity_contract.py` | `bash scripts/sync.sh --check` | Antigravity parity |

When the Phase 0 floor and every Phase 1–5 row are jointly green, the consolidated M7
readiness signal holds. This checklist makes "are we at M7?" a reproducible gate rather
than a judgment call; it never rests on a `.qb/` planning note.

**M7 consolidation statement.** For QB, *M7* is the production-gated, observable,
recoverable system — with proven trusted-code autonomy and host parity — that the
roadmap's consolidation phase defines. It is **satisfied only when the cross-phase M7
readiness aggregator (`shared/scripts/m7_readiness.py`) returns a `passed` verdict** —
every prior-phase operational + autonomy signal jointly green over captured `.qb/audit/`
evidence (the six production-gate conjuncts plus `autonomy_earned`) — **alongside** the
test-suite gate of record (`make check`, which pins the Phase 0/1/5 floor). M7 is thus a
script-checkable assertion (`python3 shared/scripts/m7_readiness.py --root .`, exit 0),
never a narrative claim.

## A2/A3 trusted-code precondition and gate of record

Two operator-facing preconditions are part of the baseline so safety is not
misread:

- **Trusted-code precondition.** Because full execution sandboxing of analyzed
  code is not yet shipped, QB provides disposable write isolation (throwaway
  worktree) plus command-level process confinement, but does **not** contain
  arbitrary code execution with filesystem, network, syscall, or container
  isolation. A2 (apply-verified) and A3 (deliver) are safe only against
  **trusted code** until full execution sandboxing ships; do not rely on QB to
  contain untrusted code. This mirrors the README caveat and does not remove it.
- **Gate of record.** Cloud CI (the GitHub Actions `validate.yml` workflow behind
  the README badge) is **disabled on the account**, so a green **local**
  `make check` / `scripts/validate.sh` — not the cloud badge — is the
  authoritative no-regression signal.

## Analyzer-coverage and parity caveats

Two intentional baseline states are recorded as known caveats, not silent gaps:

- **Environment-dependent analyzer coverage.** The `correctness` (`pyflakes`) and
  `quality` (`ruff`) analyzers are optional and **dormant when their tool is
  absent**: they enrich coverage where the tool already exists but are not required
  for a green `make check`. Coverage therefore depends on the local environment.
  *Addressed in Phase 2 (analyzer coverage).*
- **Antigravity planning-only parity asymmetry.** The Antigravity package is
  deliberately planning-only: it ships no audit/harden engine and is **not** a
  `sync.sh` destination, so it does not carry the engine analyzers the other three
  hosts do. This is an intended asymmetry, not a defect.
  *Addressed in Phase 5 (multi-host parity).*

## Regression reference (v0.19.0)

The frozen reference any future run is compared against. A single `make baseline`
re-runs the whole net (fan-out + byte-equality + per-host validation + full test
discovery).

| Field | Reference value |
|---|---|
| Version (`VERSION`) | `0.19.0` |
| Expected `make check` exit status | `0` |
| Expected test modules | 81 |
| Expected test functions | 639 |
| Expected failures / errors | 0 / 0 |

Baseline guard set (each individually runnable — see **Guard-to-test mapping**):
`test_sync_mechanism`, `test_version_and_structure`, `test_manifests_and_frontmatter`,
`test_no_cross_host_residue`, `test_sync_map_completeness`, `test_doc_consistency`,
`test_no_committed_secrets`.

Any deviation from the version, exit status, counts, or guard set above is a
regression.

## Running the regression net

There is no enforcing git hook, so the net is a discipline: run it at the points
below and read a failure by guard.

**When to run it**

- After **any** change under `shared/`: `make sync` then `make check` (the
  done-definition above) — or the single `make baseline`, which does both.
- Before declaring any forward-phase work done, and before a release.
- Any time `bash scripts/sync.sh --check` is uncertain (e.g. after a merge).

**How to interpret a failure**

1. Identify the failing `make check` sub-step (see **Invariant inventory**).
2. If it is `scripts/sync.sh --check`, a `shared/` edit skipped `make sync` — run
   `make sync` and re-check.
3. If it is the test sub-step, re-run the single failing guard from the
   **Guard-to-test mapping** table to localize the regression, then fix and re-run
   `make baseline`.
