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

## Gate of record

QB has **one authoritative quality gate**: a green **local** `make check` on a clean
working tree. Cloud CI (the GitHub Actions `validate.yml` workflow behind the README
badge) is **disabled on the account**, so the cloud badge is *not* the gate — the
local run is.

**Required before every merge or push:** run

```bash
make check          # for a shared/ change: make sync && make check
```

and proceed only when it exits `0`. `make check` composes
`bash scripts/sync.sh --check` (platform copies byte-equal to `shared/`, every
shared file mapped into the fan-out), the four per-host
`platforms/<host>/scripts/validate.sh` validators, and
`python3 -m unittest discover -s tests`. This gate performs **no networked mutation
and no auto-push** — it only verifies; delivery stays a separate, explicit opt-in
(see the A3 note above). The recorded verified floor (command, exit status, version,
date, and per-guard mapping) lives in [BASELINE.md](BASELINE.md). The contributor
conventions — the SemVer + Keep-a-Changelog discipline and the sanctioned
`scripts/bump-version.sh` bump path — live in [CONTRIBUTING.md](CONTRIBUTING.md).

### Optional: enforce the gate locally with a pre-push hook

To run the gate of record automatically before every `git push`, install the
**opt-in** pre-push hook (there is no enforcing hook by default):

```bash
scripts/install-hooks.sh             # install (explicit opt-in); or: make install-hooks
scripts/install-hooks.sh --dry-run   # preview; writes nothing
scripts/install-hooks.sh --uninstall # remove it
```

It copies `scripts/hooks/pre-push` — which runs the existing `make check` target —
into `.git/hooks/pre-push`, so a red gate blocks the push. Nothing installs it
automatically, it performs **no network access and no push**, and it writes only
inside this repo's `.git/hooks/`.

### Verify a sanitized export

`make export-sanitized` writes `QB-sanitized.zip` plus a `QB-sanitized.manifest` — a
deterministic SHA-256 file list of the tracked tree with the root VERSION. Verify a
built tree against its manifest with:

```bash
python3 scripts/release-manifest.py --check --output QB-sanitized.manifest
```

It exits `0` only when the tree still matches the manifest.

## Release integrity

The sanitized export ships with a deterministic integrity manifest
(`scripts/release-manifest.py`). Be precise about what it does and does not
guarantee.

**Guaranteed:**

- A **deterministic file list** of the git-tracked tree (sorted; same tree → same
  manifest), each entry a **SHA-256** of the file's bytes, plus the root **VERSION**.
- **Byte-equality to the synced `shared/` core** — every platform copy matches its
  `shared/` source and every shared file is mapped into the fan-out (the
  `scripts/sync.sh --check` invariant, also pinned by
  `tests/test_release_integrity.py`).
- **Exclusion of tool-state trees** — the export is the tracked tree, so `.qb/`,
  `QB-Audit/`, and `.planwright/` are never shipped.

**NOT guaranteed:**

- **No cryptographic signing.** The manifest proves *integrity* (the listed files are
  intact and hash as recorded), not *authenticity* — there is no GPG/sigstore
  signature, so it does not prove *who* produced the artifact, only that its listed
  files hash as recorded.

To check a built artifact, run the verify recipe in **Verify a sanitized export**
above; it exits `0` only when the tree still matches its manifest.

The full end-to-end release sequence — clean tree → `make check` →
`scripts/bump-version.sh` → review → `make check` → `make export-sanitized` +
integrity check → operator tag/publish — lives in [RELEASING.md](RELEASING.md), with
tagging and publishing marked operator-only.

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
- **Recoverability evidence record:** `recoverability_drill.run_drill` reuses that
  same `release_gate` capture/rollback/`baseline_clean` path and returns a
  redaction-safe record; `recoverability_drill.run_and_persist` writes it to
  `QB-Audit/recoverability.json`. The format (the single committed source the
  production-gate procedure points at) is `schema_version`, `run_id`,
  `baseline_ref` (`refs/qb-baseline/<run_id>`), `baseline_sha_len` (the baseline
  sha's **length**, never its value), `baseline_clean`, and `passed` — redacted via
  `run_store.redact` and written with sorted keys, so the audit trail proves
  recoverability without persisting any secret value.

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
  is capped at A1 for that context. The engine reports the gate reasons `precision-below-floor` and `fix-safety-breach` (the verbatim tokens `release_gate.py` returns), so improve precision (tune analyzers, accept false positives in the register) before requesting A2.

## From findings to a fix plan

Audit findings become reviewable, verifiable work through planwright. Project a
run's `QB-Audit/findings.jsonl` into planwright items with
`python3 shared/scripts/findings_to_plan.py --root .`; it validates the projection
with the plan linter and prints `planwright_plan_validation` / `secret_findings` /
`violation_count`. The QB → planwright hand-off is **one-directional** — QB writes
its plan under `.qb/` and never writes the tool-owned `.planwright/` tree — so to
execute a plan you copy it across (`cp .qb/plan.md .planwright/plan.md`) and run
`planwright execute`.

## Observability

Across runs, QB persists an aggregate telemetry series at
`QB-Audit/telemetry-aggregate.json` (the fixed run-store layout defined in
`run_store.py`), appending one entry per run keyed by `run_id`. The trend reader
(`telemetry_trends`) derives a per-dimension series over the five tracked
dimensions — `precision`, `fix_safety`, `latency`, `cost`, and `quality` — and a
direction verdict for each: `improving`, `stable`, or `regressing` over the
trailing window, or `insufficient-data` / `unmeasured` when the series is too short
or carries no measured value.

Read the verdicts as the multi-run health signal: `precision` and `fix_safety`
should hold `stable` or `improving`; a `regressing` verdict on either is the cue to
pause autonomy and investigate before raising any budget. A genuinely unmeasured
value stays `unmeasured` and is **never** coerced to a measured `0`, so a sparse
history never reads as a false improvement.

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
`production_gate` passes on **current** signals. With cloud CI disabled, operator
discipline is load-bearing, so walk **one step per conjunct** — each is assembled
from a real evidence source by `production_gate_signals.assemble_signals` and named
exactly as in `production_gate.PRODUCTION_GATE_CHECKS`:

1. **`telemetry_emitted`** — a schema-valid per-run quality record exists
   (`QB-Audit/telemetry.json`).
2. **`rollback_drill_passed`** — the recoverability drill record records a pass
   (`QB-Audit/recoverability.json`; see [Recover](#recover)).
3. **`least_privilege_ok`** — the write/network/script least-privilege invariants
   hold (`least_privilege.py`: default-deny writes, no implicit egress, no auto-run
   of repo scripts).
4. **`supply_chain_ok`** — the engine's dependency-free core holds (the `make check`
   posture). This is **interim**: the authoritative published-integrity source is the
   Phase 8 release manifest + SHA-256, not this signal.
5. **`killswitch_proven`** — the kill-switch halts at a safe checkpoint with the
   documented kill-stop exit code (`budget.KillSwitch`; see [Pause / Kill](#pause--kill)).
6. **`self_audit_clean`** — every QB-audits-QB finding is fixed or explicitly accepted
   (`QB-Audit/self-audit.json` reconciled against
   [docs/accepted-findings.md](docs/accepted-findings.md)).

The composite decision and the earned-autonomy authorization are persisted redacted
under `QB-Audit/production-gate.json` and `QB-Audit/release-authorization.json`. The
gate **fails closed**: any single conjunct false denies operation, naming that
conjunct in `failures`. It **re-evaluates current signals each time** and is never a
one-time checkbox.

A **passing gate authorizes operation, never delivery.** A3 (commit / push / PR)
stays **explicit opt-in** even when the gate passes: `a3_enabled_by_default` is
`False` regardless of the gate outcome, so authorizing autonomous operation never
authorizes auto-delivery — that remains a separate, deliberate opt-in.

**Numbering hazard.** The roadmap-Phase-7 vocabulary in this procedure is distinct
from the historical engine docstring phase markers (e.g. "Phase 3.2", "Phase 7.1")
that appear inside the engine source — do not conflate a roadmap phase with a
docstring's development marker when locating an evidence artifact.

Read this gate alongside [Recover](#recover), [Pause / Kill](#pause--kill), and
[Trip responses](#trip-responses): treat authorization, operation, and recovery as one flow —
the gate authorizes operation, the kill-switch and trip responses govern it while it
runs, and the recover procedure undoes the whole run.
