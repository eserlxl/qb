# QB Autonomy Operations Runbook

Operating QB's autonomous audit → harden → report engine safely. This runbook
covers start / observe / pause / kill / recover and the response to every trip
event. It is the human-on-the-loop companion to the engine's fail-closed defaults.

> **A3 is always explicit opt-in.** Passing the production gate authorizes
> autonomous *operation*, never auto-delivery. QB never commits, pushes, opens a
> PR, or deploys unless you explicitly enable it for that run.

The local gate of record and its recorded verified floor (the `make check` run,
expected exit status, and test counts) live in the committed
[BASELINE.md](BASELINE.md); compare against it to recognize a regression.

## Autonomy levels

| Level | Behavior |
|---|---|
| **A0** (default) | Report-only. No writes anywhere. |
| **A1** | Propose: all fixes confined to throwaway git isolation; working tree untouched. |
| **A2** | Apply-verified: only fixes whose verification command passes are promoted to the working tree; the rest auto-revert. |
| **A3** | Deliver: A2 plus a reviewable changeset. Commit/push/PR still gated by policy; off by default. |

The maximum level a context may use is earned, not chosen: the release gates
(`release_gate.permitted_autonomy`) read the run's telemetry and deny auto-apply
(cap at A1) unless precision ≥ floor **and** every kept fix verified green.

The effective level is also capped by **execution-sandbox availability**. A2/A3
fix verification runs **contained** under process confinement; when the required
control cannot be established, autonomy is clamped to A1 (no A2/A3 apply) rather
than running analyzed-code verification unconfined, and the run records a clamp
reason (`sandbox unavailable -> autonomy capped to A1`) in the result and
telemetry. The effective level is the **most restrictive** of the declared level,
the telemetry-earned ceiling, and this sandbox clamp.

## Start

- **Headless / CI:** `python3 scripts/qb_headless.py --root <repo> --out QB-Audit`
  (defaults to A0). Branch on the exit code: `0` clean · `1` findings · `2`
  policy/budget boundary · `3` internal error.
- **In a host:** run the `qb-harden` command (Claude Code / Cursor) or the
  `$qb` audit-and-harden Goal-mode flow (Codex). State the run brief: target repo,
  autonomy level (A0 unless explicitly raised), policy, budgets.

## Observe

- The run writes everything to the fixed-name `QB-Audit/` store: `findings.jsonl`,
  `evidence/<id>.json`, append-only `run-log.jsonl`, `summary.json`, plus
  `report.json` / `report.sarif` / `summary.txt` and a `telemetry.json` record.
- Read `summary.txt` for severity counts and kept/reverted fix counts; read
  `telemetry.json` for precision, fix-safety, latency, and cost.

## Pause / Kill

- Trigger the kill-switch (`budget.KillSwitch.trigger()`). It is honored only at
  safe checkpoints **between** atomic fix units, never mid-patch, so a stop never
  bisects a fix. The in-flight fix is either already verified-and-kept or reverted
  to its rollback handle before exit. The run ends with the kill-stop exit code.

## Recover

- Every run captures a namespaced pre-run reversal handle
  (`refs/qb-baseline/<run_id>`). To undo an entire run:
  `release_gate.rollback_run(repo, handle)` resets to the baseline and cleans
  untracked files; `release_gate.baseline_clean(repo, handle)` confirms a clean
  tree at the baseline. The rollback drill proves this end to end.

## Live-validation protocol

Turning the tested safety machinery into measured confidence follows the
committed [docs/live-validation-protocol.md](docs/live-validation-protocol.md):
the A1 → A2 → A3 progression and pass conditions, the per-run telemetry fields
(`telemetry.build_telemetry`), the rollback drill
(`release_gate.run_rollback_drill`), and the precision/fix-safety judging anchored
to `PRECISION_FLOOR = 0.80`. The protocol runs over a trusted/neutralized corpus;
untrusted, self-executing targets are gated on the execution sandbox. It also
records the **reviewable-changeset contract**: A3 assembles a changeset whose
`commit_permitted` only reflects `policy.allow_commit`, and QB executes no
commit/push/PR in that seam (`HEAD` is left unchanged) — delivery stays an
explicit, separate opt-in.

## Trip responses

- **Budget boundary** (max findings/fixes/iterations/wall-time/tokens): the run
  stops at the ceiling and emits a stop report with exit code `2`. Review the
  telemetry, raise the budget deliberately if appropriate, and re-run.
- **Policy denial** (out-of-allowlist write, category not auto-fixable,
  confidence below floor, path in denylist): the action is blocked, not warned;
  the finding is reported for manual handling.
- **Release-gate denial** (precision below floor or a fix-safety breach): autonomy
  is capped at A1 for that context. Improve precision (tune analyzers, accept
  false positives in the register) before requesting A2.

## Budget raise paths

Each budget ceiling that can halt a run maps to a deliberate raise-path — the
evidence that justifies a raise, a conservative step, and the guardrail that must
hold first. A raise is **never** auto-applied; it takes effect only when you edit
`policy.budgets`. The mapping mirrors `budget.RAISE_PATHS`:

- **`max_findings`** — findings reached the ceiling with findings unprocessed.
  Raise `max_findings` one increment; triage P0/P1 first, because a wider finding
  budget broadens scope, not fix depth.
- **`max_fixes`** — fixes applied reached the ceiling while verified fixes remained
  queued. Raise `max_fixes` one increment, but only when `precision_estimate` is at
  or above the precision floor and fix-safety holds.
- **`max_iterations`** — orchestration iterations hit the ceiling before the queue
  drained. Raise `max_iterations` one increment; confirm iterations are productive,
  not looping on the same finding.
- **`max_wall_seconds`** — the run halted at the wall-time ceiling with work still
  queued. Raise `max_wall_seconds` (e.g. +50%); confirm the run was making progress
  (fixes kept), not spinning.
- **`max_tokens`** — token spend hit the ceiling before completion. Raise
  `max_tokens`; confirm token use is proportional to fixes kept, not waste.

**Advisory recommender.** `budget.recommend_budget(stop_report, aggregate)` reads a
run's stop report plus the aggregate telemetry series and advises whether a hit
ceiling is `constraining` (legitimately limiting useful work — consider a raise),
`protecting` (correctly guarding against a regressing or wasteful run — hold), or
`insufficient-evidence` (too little trend history — do not raise, fail-closed). It
is **output-only**: it returns advice and never mutates a budget, so widening a
ceiling always remains a deliberate `policy.budgets` edit.

## Execution sandbox contract

QB confines every external command it runs on the analyzed repository's behalf —
in particular each fix's verification command — under **process confinement**
established before the child spawns. This is process confinement (a new
session/process group plus conservative POSIX resource limits), **not** a
filesystem/network namespace or container sandbox.

The rule is **fail-closed**: when a required control cannot be established
(`command_safety.ConfinementUnavailable`), the command is refused, never run
unconfined, and the verification seam records `verification confinement
unavailable` as non-green so an unconfined run is never kept. Repo-supplied
scripts never execute unless `least_privilege.may_run_repo_script` authorizes
them (`AUTO_RUN_REPO_SCRIPTS` is `False`). The full contract — guarantee,
non-guarantee, supported controls, and governing symbols — lives in
[docs/execution-sandbox.md](docs/execution-sandbox.md).

## Production gate

Before authorizing earnest autonomous operation, confirm the composite
`production_gate` passes on **current** signals: telemetry emitted, rollback drill
passed, least-privilege + supply-chain invariants holding, kill-switch proven, and
a clean (or fully-accepted) self-audit. The gate fails closed; it re-evaluates each
time and is never a one-time checkbox. A3 remains explicit opt-in regardless.
