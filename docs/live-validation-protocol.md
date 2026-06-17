# Live-Validation Protocol (A1 → A2 → A3)

The protocol for turning QB's tested safety machinery into measured operational
confidence. It defines the autonomy progression, the telemetry captured per run,
the rollback drill, and the precision/fix-safety thresholds a campaign must clear.

> **Scope (honest).** Near-term this protocol runs over a **trusted / neutralized
> corpus** — labelled synthetic fixtures whose verification commands are
> stdlib-only no-ops or otherwise trusted. Running QB over **untrusted or
> network-fetched targets** that execute their own verification commands is gated
> on the execution sandbox: analyzed-code verification runs under process
> confinement and fails closed when unavailable (see
> [execution-sandbox.md](execution-sandbox.md)), but that is process confinement,
> not a filesystem/network namespace, so untrusted targets remain out of scope
> until full sandboxing ships.

## Trusted-code preconditions

Running QB over a target executes that target's verification command. Until full
execution sandboxing ships, that is safe **only against trusted code**, so every
corpus repo carries one of two sanctioned trusted-code preconditions
(`tests/qb_corpus.TRUST_TAGS`):

- **`neutralized-noop`** — the verification command is a stdlib-only no-op
  (`["python3", "-c", ""]`), so no repo-supplied code runs during the
  audit → report run. Every fixture in the current corpus is tagged this way.
- **`trusted-verification`** — the verification command is real but the target is
  trusted (author-controlled), reserved for future fixtures.

The corpus builder **fails closed**: a repo without a valid trust tag and a stated
precondition is rejected. **Untrusted or network-fetched, self-executing targets
are not permitted in the corpus** — they are gated on the Phase 1 execution
sandbox (process confinement, fail-closed-and-cap; see
[execution-sandbox.md](execution-sandbox.md)), and full containment of untrusted
code requires the not-yet-shipped filesystem/network namespace.

## Autonomy progression

| Rung | Claim under test | Pass condition |
|---|---|---|
| **A1** propose | Writes are confined to throwaway isolation; the target tree is byte-identical before/after. | `git status --porcelain` of the target unchanged after the run. |
| **A2** apply-verified | A verified fix is promoted to the working tree **only** when the loaded telemetry earns A2. | Promotion happens iff `release_gate.permitted_autonomy(telemetry)` is `A2` and the fix verified green. |
| **A3** deliver | A2 plus a reviewable changeset; commit/push/PR stay explicit opt-in. | Changeset assembled only with `enable_a3`; `commit_permitted` still gated by policy. |

The effective level is the **most restrictive** of the declared level, the
telemetry-earned ceiling (`release_gate.permitted_autonomy`), and the
sandbox-availability clamp (`policy.sandbox_autonomy_ceiling`). A cold start (no
prior telemetry) is fail-closed to A1.

## Telemetry captured per run

Each run persists `QB-Audit/telemetry.json` via `telemetry.build_telemetry`, with:

- `schema_version` (`== TELEMETRY_SCHEMA_VERSION`), `run_id`, `autonomy_level`,
  `clamp_reason` (set when the sandbox clamp lowered the level).
- `detection`: `findings_total`, `by_severity`, `by_category`,
  `confidence_histogram`.
- `action`: `fixes_attempted`, `fixes_kept`, `fixes_reverted`, `fixes_blocked`.
- `cost`: `wall_ms`, `iterations`, `tokens`.
- `quality`: `precision_estimate`, `false_positive_signals`, `fix_safety_ok`.

The record is redacted before persistence and is read back with
`run_store.load_prior_telemetry`.

## Rollback drill

Every campaign run is reversible. `release_gate.run_rollback_drill(repo_root,
run_id, mutate_fn)` captures a namespaced baseline (`refs/qb-baseline/<run_id>`),
applies `mutate_fn`, then resets to the baseline and confirms a clean tree —
returning `True` only when the target is byte-identical to its pre-run state. A
campaign that cannot pass the rollback drill does not earn A2.

## Precision / fix-safety judging

- **Precision** is `precision_estimate = kept / (kept + reverted)`
  (`telemetry.precision_estimate`). A2 is earned only when precision **≥
  `PRECISION_FLOOR = 0.80`**.
- **Fix-safety** (`quality.fix_safety_ok`) is false if any *kept* fix did not
  verify green (`after_exit not in (0, None)`); a fix-safety breach denies A2.
- Measured precision is compared to the corpus **ground-truth labels** within a
  documented tolerance; a divergence is recorded as a labelled known gap rather
  than passed silently.

`release_gate.permitted_autonomy` composes the precision gate and the fix-safety
gate, returning `A2` only when both pass and `A1` otherwise (never defaulting
open).
