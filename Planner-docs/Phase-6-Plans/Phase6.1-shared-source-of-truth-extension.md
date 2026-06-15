# Phase 6.1 — Extend the Shared Source of Truth and Sync Map

## 1. Context

This sub-phase opens Phase 6 (Multi-Host Parity & Headless/CI Mode, maturity M4->M5) and is the foundation on which the other three Phase 6 sub-plans depend. The parent phase goal in `Planner-docs/Main-Planning.md` section 6 is to "Ship the engine identically on all hosts plus a non-interactive CI mode, preserving the monorepo invariants." Before any host adapter (Phase 6.2) or headless CLI (Phase 6.3) can launch the audit->harden->report loop, the engine intellectual property produced in Phases 1-5 — the `Finding` schema, the analyzer interface, the fixer interface, the policy schema, and the orchestrator/runner — must live under `shared/` and be wired into `scripts/sync.sh` so every platform copy stays byte-identical. Today `shared/` holds eight host-neutral files (five planner specs, two reference docs, and `shared/scripts/validate_planner_docs.py`), each fanned out to three platforms by a 24-entry `MAP` in `scripts/sync.sh`. The autopsy (`Planner-docs/Autopsy.md` sections 3 and 8) is explicit that the single-source-of-truth invariant "must be extended, not broken, by every new artifact," and that `sync.sh` plus the sync-map completeness guard must grow whenever a new `shared/` artifact appears. This sub-phase makes that growth deliberate and test-gated rather than ad hoc.

## 2. Goal

Land every new engine artifact produced by Phases 1-5 inside `shared/` as the sole canonical home, extend the `scripts/sync.sh` `MAP` so each new artifact fans out to all three platforms, and strengthen the sync-map completeness test so that any unmapped `shared/` file fails `make check`. The outcome is that `shared/` remains the only place engine behavior is authored, the platform copies are provably byte-identical, and adding a future engine file cannot silently bypass the sync contract.

## 3. Description

The problem this sub-phase solves is a scaling problem in the source-of-truth contract. The current `MAP` in `scripts/sync.sh` was hand-written for exactly eight planning files; the audit-and-harden engine adds schemas, interface specs, a policy file format, and a runner spec that have no `MAP` entries and no platform destinations. Without deliberate wiring, a new engine spec authored under `shared/` would either never reach a platform (breaking parity) or be hand-copied into platforms (breaking the byte-for-byte invariant and inviting drift). This belongs at the start of Phase 6 because the per-host adapters and the headless surface both consume these artifacts; sequencing the shared-tree extension first means the writer that fans out across hosts in Phase 6.2 reads from a stable, mapped tree rather than racing the sync contract. It reduces project risk by converting the autopsy-flagged parity-drift risk into a mechanical, CI-enforced check. It prepares later phases because Phase 6.4's structure-consistency tests can assume a complete, mapped shared tree, and Phase 7's self-audit can trust that what it audits on one host is what runs on all hosts. The grouping discipline already present in the `MAP` — one comment block per shared source listing its three destinations — becomes the template every new engine artifact follows.

## 4. Scope

- Inventory every engine artifact frozen in Phases 1-5 that must be host-neutral (Finding schema definition, analyzer interface spec, fixer interface spec, policy schema, runner/orchestrator spec, and any shared evidence-record format).
- Place each artifact under the appropriate `shared/` subtree (for example `shared/schemas/`, `shared/specs/`, or `shared/scripts/` as decided during Phase 1-5 implementation).
- Add one `MAP` entry per (source, destination) pair in `scripts/sync.sh`, preserving the existing per-source comment-block grouping and the claude-code/cursor/codex fan-out order.
- Honor the codex destination naming convention already encoded in the `MAP` (codex references use `plugins/qb/skills/qb/references/...` with capitalized planner filenames; new engine artifacts must follow whatever codex naming Phase 6.4 ratifies).
- Update each platform `validate.sh` `required_files` list so the new synced destinations are presence-checked.
- Extend the sync-map completeness test (`tests/test_sync_map_completeness.py`) and `tests/test_shared_artifacts_and_sync.py` to assert the new artifacts are mapped and byte-equal.

## 5. Out of Scope

- Authoring the engine behavior itself (the Finding schema content, analyzer logic, fixer logic, policy semantics) — that is delivered in Phases 1-5 and merely relocated/wired here.
- Any host-specific launch glue (commands, agents, skills, goal-mode prompts) — that is Phase 6.2.
- The headless CLI entry point and CI exit codes — that is Phase 6.3.
- Resolving the manifest version drift or the codex structural asymmetry — that is Phase 6.4.
- Network access, dependency installation, or external tool integration of any kind.
- Writing secrets, tokens, or live endpoint credentials into any `shared/` artifact.

## 6. Current Repository Evidence

`scripts/sync.sh` defines a `MAP` array of 24 entries (eight distinct shared sources, each fanned out to claude-code, cursor, and codex), with the codex destinations using the nested `plugins/qb/skills/qb/...` path and capitalized `First-Planner.md`/`Second-Planner.md`/`Third-Planner.md`/`Fourth-Planner.md`/`Autopsy-Planner.md` filenames. The `--check` mode compares every destination to its source via `cmp -s` and, crucially, walks `find "$SHARED_DIR" -type f -not -path '*/__pycache__/*'` to fail loudly with `unmapped_shared_source=<rel>` on any shared file missing from the `MAP`. `tests/test_sync_map_completeness.py` already pins this guard: `test_unmapped_shared_file_is_detected` drops `shared/planners/extra-planner.md` into a temp repo and asserts `--check` exits 1 with the `unmapped_shared_source=` token. The `shared/` tree currently contains only planning files, confirmed by the `find platforms/codex/plugins/qb/skills/qb` listing showing seven references plus one script destination. There is no `shared/schemas/`, `shared/specs/`, or engine-runner file present yet, so the engine artifacts are net-new additions to the mapped tree.

## 7. Planned Work Breakdown

- F6.1-01 — Engine artifact inventory and shared-tree placement plan
  - Description: Enumerate every host-neutral engine artifact from Phases 1-5 and assign each a canonical path under `shared/`, choosing subtrees that keep schemas, interface specs, and runnable scripts cleanly separated.
  - Expected output: A placement table mapping each engine artifact to its `shared/<subtree>/<file>` canonical path, ready to drive `MAP` additions.
- F6.1-02 — sync.sh MAP extension for engine artifacts
  - Description: Add one comment-grouped block per new shared source to the `MAP` in `scripts/sync.sh`, each listing the claude-code, cursor, and codex destinations in the established order and codex naming convention.
  - Expected output: An updated `MAP` whose `cut -d'|' -f1 | sort -u` count matches the new shared-file count and whose default-mode copy reaches all three platforms.
- F6.1-03 — Per-platform required_files updates
  - Description: Append the new synced destination paths to the `required_files` array in each of `platforms/{claude-code,cursor,codex}/scripts/validate.sh` so a missing synced engine file is caught locally.
  - Expected output: Three updated `validate.sh` files whose presence checks include every new engine destination.
- F6.1-04 — Completeness and byte-equality test extension
  - Description: Extend `tests/test_sync_map_completeness.py` and `tests/test_shared_artifacts_and_sync.py` to assert the engine artifacts are mapped, fan out to three platforms, and remain byte-equal after `scripts/sync.sh`.
  - Expected output: Test additions that fail when an engine artifact is added to `shared/` without a `MAP` entry or when a copy drifts.
- F6.1-05 — Sync dry-run and drift verification note
  - Description: Document the exact read-only verification sequence (run `scripts/sync.sh`, then `scripts/sync.sh --check`, then the unit suite) that proves the extended tree is in sync.
  - Expected output: A reproducible verification recipe recorded in this sub-plan's validation section for the implementer to follow.

## 8. Acceptance Criteria

- Running `scripts/sync.sh --check` reports "in sync" with a copy count equal to (new shared-file count) times three, and emits no `unmapped_shared_source=` lines.
- Every engine artifact added to `shared/` has exactly three `MAP` destinations (one per platform) and no engine file lives only inside a platform directory.
- `python3 -m unittest discover -s tests` passes, including the extended completeness and byte-equality assertions, with no skipped engine-artifact checks once all platforms are built.
- Each platform `validate.sh` lists the new synced destinations in its `required_files` and exits non-zero if one is absent (verifiable by a transient local removal during review, restored afterward).
- No secret value, token, or credential appears in any new `shared/` artifact, confirmed by the existing secret-scan test path remaining green.
- Local readiness (sync-clean tree, green unit suite) is asserted separately from live readiness, which this sub-phase does not claim because no engine is launched here.

## 9. Validation and Test Approach

Document validation: confirm each engine artifact resolves to a single canonical `shared/` path and that the `MAP` comment blocks read coherently. Local smoke: run `make sync` (which invokes `bash scripts/sync.sh`) then `make check`, whose first step is `bash scripts/sync.sh --check`; the check must report in-sync with the new copy count. Unit validation: run `python3 -m unittest discover -s tests` and confirm `test_sync_map_completeness.py` and `test_shared_artifacts_and_sync.py` cover the new artifacts. Security validation: rely on the existing `tests/test_no_committed_secrets.py` path to confirm no secret entered the new shared files. CI validation: the `.github/workflows/validate.yml` job runs `make check` on push to `main` and on every pull request, so the extended sync contract is gated automatically. Live readiness is not evaluated in this sub-phase; it is deferred to Phase 6.3's headless run. All commands listed already exist in the repository; no proposed-but-absent command is required.

## 10. Dependencies and Sequencing

This sub-phase depends on Phases 1-5 having frozen the engine artifacts (Finding schema, analyzer/fixer interfaces, policy schema, runner) — without those frozen, there is nothing canonical to relocate and map. It must complete before Phase 6.2 (host launch adapters) and Phase 6.3 (headless CLI), because both read the mapped shared tree. It is largely independent of Phase 6.4 in authoring order, but Phase 6.4's ratified codex naming convention should inform the codex destination names chosen in F6.1-02; if Phase 6.4 changes the codex layout, the `MAP` codex destinations are revised in lockstep. No live credentials, network endpoints, or human approvals beyond normal review are required. The blocking decision is the final `shared/` subtree layout for engine artifacts, to be confirmed during implementation against the Phase 1-5 outputs.

## 11. Risks and Mitigations

- Risk: a new engine artifact is added under `shared/` but forgotten in the `MAP`. Impact: the file silently never reaches any platform, breaking parity. Mitigation: the completeness guard in `scripts/sync.sh --check` already fails on `unmapped_shared_source=`, and F6.1-04 pins that behavior for the engine artifacts specifically.
- Risk: a platform copy drifts from its shared source through manual editing of a platform file. Impact: hosts behave differently for the same logical engine artifact. Mitigation: `--check` uses `cmp -s` byte comparison and `tests/test_shared_artifacts_and_sync.py` asserts sync-clean state in CI.
- Risk: codex destination naming for engine artifacts is chosen inconsistently with the existing capitalized-reference convention. Impact: confusing, hard-to-maintain codex paths and possible Phase 6.4 rework. Mitigation: F6.1-02 mirrors the established codex naming and sequences after Phase 6.4's structure ratification where they overlap.
- Risk: relocating an engine artifact changes its content and quietly regresses Phase 1-5 behavior. Impact: a logic change disguised as a move. Mitigation: treat relocation as a pure move with byte-equal verification and rely on the Phase 1-5 engine tests remaining green.

## 12. Desired End State

`shared/` is the complete, single, canonical home for every host-neutral engine artifact alongside the existing planner specs and validator. `scripts/sync.sh` carries one comment-grouped `MAP` block per engine artifact, fanning each out to claude-code, cursor, and codex in the established order, and `scripts/sync.sh --check` reports an in-sync tree with the expanded copy count and zero unmapped sources. Each platform `validate.sh` presence-checks the new destinations, and the unit suite asserts mapping completeness and byte-equality. An implementer can add a future engine file knowing that omitting it from the `MAP` will fail `make check` rather than silently degrade parity.

## 13. Transition Criteria to the Next Sub-Phase

Before starting Phase 6.2, the following must hold: every engine artifact lives only under `shared/` with no orphaned platform-only copy; `scripts/sync.sh --check` reports in-sync with the new copy count and no `unmapped_shared_source=` output; `python3 -m unittest discover -s tests` passes including the extended completeness tests; each platform `validate.sh` `required_files` list includes the new destinations; and `git status --short` confirms only intended files (under `shared/`, `scripts/sync.sh`, the three `validate.sh`, and `tests/`) changed. Work requiring a live audit run remains not activated until Phase 6.3.
