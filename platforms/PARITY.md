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
