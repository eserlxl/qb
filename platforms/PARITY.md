# Per-Host Capability Parity

QB ships as four host packages under `platforms/`. They are **not** uniform: three
carry the full audit/harden engine; one is planning-only. This document is the
single authoritative statement of which capability set each host ships.

## Capability matrix

| Host | Planning workflow | Audit/harden engine |
|------|:-----------------:|:-------------------:|
| Claude Code | yes | yes |
| Cursor | yes | yes |
| Codex | yes | yes |
| Antigravity | yes | no (planning-only) |

- **Planning workflow** — the five-step `/qb-plan` workflow (Steps 1, 1.5, 2, 3, 4)
  that produces the `.qb/` planning artifacts. All four hosts ship it.
- **Audit/harden engine** — the host-neutral IP under `shared/scripts/`
  (`audit_runner.py`, `orchestrator.py`, `budget.py`, `release_gate.py`, and their
  siblings) that powers the read-only audit and the gated harden loop.
  `scripts/sync.sh` fans the engine into `platforms/claude-code`,
  `platforms/cursor`, and `platforms/codex/plugins/qb/skills/qb`. **Antigravity ships
  no engine module and is not a `scripts/sync.sh` destination** — it is deliberately
  planning-only.

## Decision: Antigravity scope

**Antigravity = planning-only is the chosen stance**, not an accident of incomplete
porting. The rationale:

- **Maintenance tax.** Each engine-bearing host is a `scripts/sync.sh` destination;
  adding Antigravity would make it a fourth synced surface (every engine module and
  its validator multiplied again), widening the sync map and the cross-host residue
  surface the validators must guard.
- **No evidenced demand.** Antigravity's role in QB is the planning workflow; there
  is no evidenced demand for running the audit/harden engine under Antigravity that
  would justify that ongoing tax.

**Deferred alternative — full parity.** Antigravity could be promoted to an
engine-bearing host by adding it to the `scripts/sync.sh` MAP and shipping the
`shared/scripts/` engine under its skill, exactly as the other three hosts do. The
cost is the maintenance tax above (a fourth sync destination plus a broadened
validator and residue surface) and a per-host harden entry. This is recorded as an
available future option, not a current commitment.

This is a recorded maintainer decision, not a tested property; its
**machine-checkable** consequences (engine absent under Antigravity; Antigravity
absent from the sync map) are enumerated below and enforced separately.

## Decision: Antigravity reference-doc ownership

`platforms/antigravity/skills/qb/references/` carries a richer planning-reference
set than the engine hosts. Two refs — `repo-aware-intake.md` and
`workflow-quality.md` — are **shared** (they live in `shared/references/` and fan
out to all engine hosts). The host-specific planner-step prompts
(`first-planner.md`, `second-planner.md`, `third-planner.md`, `fourth-planner.md`,
`assessment-planner.md`) are inherently Antigravity-only (they open with "You are
Antigravity, running as…"). The remaining concept docs are classified below so the
divergence is owned, not silent drift (closes ASSESS-P1-02); the first six were
previously ungoverned and `probe-policy.md` is a newer addition:

| Reference doc | Classification | Rationale |
|---|---|---|
| `engineering-principles.md` | Antigravity-only | Deep planning methodology for the dedicated planning-only host; the engine hosts ship a leaner planning surface and add value through the audit/harden engine. |
| `vibecoding-principles.md` | Antigravity-only | Same — planning-style guidance scoped to Antigravity's richer planning workflow. |
| `task-delegation-playbook.md` | Antigravity-only | Helper-agent delegation guidance specific to Antigravity's multi-step planner run. |
| `project-ontology.md` | Antigravity-only | Describes an optional `.qb/` planning artifact used by Antigravity's planner steps. |
| `planning-ledger.md` | Antigravity-only | Describes an optional `.qb/` planning-memory artifact used by Antigravity's planner steps. |
| `assessment-and-budget.md` | Antigravity-only | Supports the Antigravity Step-1.5 `assessment-planner.md` prompt. |
| `probe-policy.md` | Antigravity-only | Tiered evidence-probe discipline for the dedicated planning host's Step-1.5 assessment; the engine hosts keep a leaner read-only assessment surface. |

**Conservative default.** All seven are classified **intended Antigravity-only** (so
no reconcile/move is required — Phase 5.4's reconcile step is a no-op). This is a
deliberate, reversible governance decision: a maintainer may later reclassify any
of these to *reconcile-into-shared* (moving it to `shared/references/` with a
`scripts/sync.sh` MAP entry) if the engine hosts' planning surface should adopt it.

## Enforced invariants

These are machine-checkable and pinned by `tests/test_host_parity_contract.py`:

1. **Engine present in engine-bearing hosts.** Each of `platforms/claude-code/scripts/`,
   `platforms/cursor/scripts/`, and `platforms/codex/plugins/qb/skills/qb/scripts/`
   contains the engine modules (`audit_runner.py`, `orchestrator.py`, `budget.py`,
   `release_gate.py`).
2. **Engine absent under Antigravity.** No engine module appears anywhere under
   `platforms/antigravity/` — it is planning-only.
3. **Antigravity is not a sync destination.** No `scripts/sync.sh` MAP entry targets a
   path under `platforms/antigravity/`.
4. **The contract matches reality.** This document's matrix (engine-bearing for the
   three hosts, planning-only for Antigravity) matches the on-disk facts above.
