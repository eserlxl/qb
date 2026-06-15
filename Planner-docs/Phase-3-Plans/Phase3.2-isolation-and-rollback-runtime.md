# Phase 3.2 — Isolation and Rollback Runtime (Net-New)

## 1. Context

This sub-phase implements the safety primitive that the autopsy flagged as the single highest unattended-write risk. `Planner-docs/Autopsy.md` finding AUTOPSY-P0-02 states plainly that "shared/planners/fourth-planner.md specifies 'minimal, reversible' and 'verify before done' but contains no isolation/worktree/branch mechanism; Main-Planning sections 5/7 mandate it as net-new." Main-Planning section 5 likewise declares fixers must "run in isolation (dedicated branch/worktree) with mandatory verification and automatic rollback on failure," and section 7's top risk mitigation is "git isolation (branch/worktree)" plus "automatic rollback."

Phase 3.2 therefore does not generalize an existing mechanism — it builds one that the repository does not contain. A repository-wide search confirms there is no `git worktree`, `git checkout`, `git reset`, or `git revert` runtime anywhere in `shared/`, `platforms/`, `scripts/`, or `tests/`; the only git references are diagnostic `git branch --show-current` lines inside planner specs. This sub-phase consumes the per-finding fix plan from Phase 3.1 and produces the isolation container and the reversal handle that Phase 3.3 uses to keep or revert each fix.

It is sequenced as the second sub-phase of Phase 3 because isolation must exist before any verification gate can keep or discard a change. The autonomy levels A0-A3 from Main-Planning section 5 give isolation its precise contract: A0 writes nothing, A1 writes only to throwaway isolation, and A2 promotes verified fixes to the working tree while auto-reverting the rest.

## 2. Goal

Specify a net-new isolation primitive and a rollback handle so that every applied fix is fully reversible without relying on a human or on the operator's working tree being clean. The isolation primitive is a dedicated git branch or worktree dedicated to the run; the rollback handle is a captured git ref (the pre-fix commit/ref) that deterministically restores the prior state. The outcome is a written runtime design defining how isolation is created, how the handle is captured and used, how A1 confines all writes to throwaway isolation, and how A2 promotes only verified fixes — never touching the user's working tree on the failure path.

## 3. Description

The gap this sub-phase fills is that QB is about to write code autonomously while owning no mechanism to undo it. Without isolation, a bad autofix mutates the operator's working tree in place, and "reversible" is only a promise in prose. This design introduces a dedicated git worktree (or branch, where worktrees are unavailable) created at run start, into which all fix attempts are written; the operator's checked-out tree is never the target of an unverified write. Before each fix, the runtime captures a rollback handle — the current git ref of the isolation container — so a failed verification can be undone by resetting to that exact ref.

This belongs immediately after fix binding because the unit being isolated (one finding's minimal patch) is only defined once Phase 3.1 is complete, and it belongs before the verification gate because Phase 3.3's keep/revert decision is implemented *against* this handle. The risk it reduces is corruption of the user's working tree and lost work — the autopsy's stated top safety risk. It also encodes the autonomy-level write boundaries: A0 never opens isolation at all (report-only), A1 creates isolation and leaves every change there for human inspection, A2 creates isolation, verifies, then fast-forwards or cherry-promotes only the green fixes into the working tree and discards the rest. This prepares Phase 4, whose policy engine selects the autonomy level and thus selects which of these isolation behaviors runs.

## 4. Scope

- A written isolation-runtime design covering creation of a dedicated git worktree (preferred) or branch (fallback) keyed to the run, with a deterministic naming convention that avoids collision with user branches.
- A rollback-handle design: capture the pre-fix git ref, store it with the finding, and define the exact reset/discard operation that restores prior state.
- The per-autonomy-level write contract: A0 opens no isolation, A1 confines all writes to throwaway isolation, A2 promotes only verified fixes to the working tree.
- A path-allowlist boundary so writes inside isolation cannot touch paths outside the repo or outside policy-allowed globs (consistent with AUTOPSY-P1-03).
- A cleanup/teardown design that removes throwaway isolation deterministically and leaves the user's tree unchanged when nothing is promoted.
- Registration of any new shared artifact in the `scripts/sync.sh` `MAP`.

## 5. Out of Scope

- The keep-or-revert decision logic and the before/after evidence record — owned by Phase 3.3 (this sub-phase only provides the handle it acts on).
- Selecting which autonomy level a run uses, and the policy/budget engine that selects it — owned by Phase 4.
- The finding-to-recipe binding and verification-command selection — owned by Phase 3.1.
- Preparing a reviewable changeset or opening a PR (autonomy level A3) — deferred; this sub-phase stops at A2 working-tree promotion.
- Commit/push/PR/deploy of any kind without explicit per-run authorization, consistent with Main-Planning section 4.
- The fixture-repo harness that exercises isolation under test — owned by Phase 3.4.

## 6. Current Repository Evidence

A repository-wide search for `git worktree`, `git checkout`, `git reset`, `git revert`, `rollback`, and `isolation` as a runtime mechanism returns only documentation references: `shared/planners/third-planner.md:229` lists "rollback notes" as a plan field, `shared/planners/autopsy-planner.md:198` lists "backup/restore or rollback signals" as an inspection target, and `shared/references/repo-aware-intake.md:26` uses `git branch --show-current` for diagnostics only. None of these is an executable isolation or rollback runtime. `shared/planners/fourth-planner.md` says one reversible slice but provides no branch, worktree, or reset step, confirming AUTOPSY-P0-02. The Makefile shows the only persisted git-archive use is `export-sanitized` (`git archive ... HEAD`), which is a read-only export, not a rollback. There is consequently no existing isolation primitive to reuse; this sub-phase is genuinely net-new and must be designed from the git primitives directly.

## 7. Planned Work Breakdown

- F3.2-01 — Dedicated worktree isolation design
  - Description: Specify creation of a run-scoped git worktree as the primary isolation container, including a collision-safe naming convention and the branch-fallback path for environments without worktree support.
  - Expected output: an isolation-creation design with primary (worktree) and fallback (branch) procedures.
- F3.2-02 — Rollback-handle capture and restore
  - Description: Define capturing the pre-fix git ref as the reversal handle, attaching it to the finding's fix record, and the exact reset/discard operation that restores prior state.
  - Expected output: a rollback-handle lifecycle specification (capture, store, restore).
- F3.2-03 — Per-autonomy-level write contract
  - Description: Map A0/A1/A2 to concrete isolation behaviors — A0 no isolation, A1 throwaway-only writes, A2 verified-fix promotion — with explicit statements of when the user's working tree is and is not touched.
  - Expected output: an autonomy-to-isolation behavior table.
- F3.2-04 — Path-allowlist write guard
  - Description: Specify the path-allowlist boundary enforced on every write inside isolation so out-of-repo or out-of-policy paths are rejected.
  - Expected output: a write-guard rule referencing the policy allowlist concept from Phase 4.
- F3.2-05 — Teardown and clean-tree guarantee
  - Description: Define deterministic teardown of throwaway isolation and assert the user's working tree is byte-identical to its pre-run state when no fix is promoted.
  - Expected output: a teardown procedure with a clean-tree invariant statement.

## 8. Acceptance Criteria

- The design names git worktree as the primary isolation container and git branch as the documented fallback, with a collision-safe naming convention that cannot overwrite an existing user branch.
- Every fix has an associated rollback handle (a captured git ref) and a defined restore operation that returns the isolation container to its pre-fix state.
- The autonomy-to-isolation table states, for A1, that no write reaches the operator's checked-out working tree, and for A2, that only verified fixes are promoted while the rest are discarded.
- A path-allowlist write guard is specified such that writes outside the repo or outside policy-allowed globs are rejected before they occur.
- The teardown procedure guarantees that when nothing is promoted, the user's working tree is unchanged, and this is stated as a verifiable invariant for Phase 3.4 to assert.
- No secret values or credentials are written into the design or into any isolation artifact.

## 9. Validation and Test Approach

Document validation: any new shared artifact must pass `bash scripts/sync.sh --check` after `MAP` registration and the existing `python3 -m unittest discover -s tests` suite must remain green. Proposed local-smoke tests (not yet present): an isolation-lifecycle test (working name `tests/test_isolation_runtime.py`) that creates isolation in a temporary git repository, writes a change, captures the handle, restores via the handle, and asserts the tree returns to the captured ref; and a clean-tree test asserting that an A1-style run leaves the original working tree untouched. These use Python `unittest` with `subprocess` and a temporary git repo, matching the conventions in `tests/test_no_committed_secrets.py` and `tests/qb_monorepo.py`. Security validation: confirm the write guard rejects out-of-allowlist paths and that isolation creation uses explicit argument lists. Distinguish document validation (drift check) from local smoke (the proposed isolation tests) from live readiness (an actual A2 run over a real target repo, which is gated until Phase 4 selects autonomy).

## 10. Dependencies and Sequencing

Hard upstream dependency: Phase 3.1 must define the unit of work (one finding's minimal patch) so the isolation container has something well-defined to hold. This sub-phase blocks Phase 3.3, whose keep/revert gate acts directly on the rollback handle produced here, and it blocks Phase 3.4, whose fix-safety harness exercises isolation and rollback. The path-allowlist guard references the policy allowlist that Phase 4 formalizes; for this sub-phase the allowlist is treated as an injected boundary to be confirmed during implementation, not as a fully specified policy schema. A working git binary is required for any future execution; no network access, no live credentials, and no human approvals are required to design or test the isolation runtime locally.

## 11. Risks and Mitigations

- Risk: a generated isolation branch or worktree name collides with an existing user branch and overwrites it. Impact: destruction of user work — the exact failure isolation is meant to prevent. Mitigation: a collision-safe naming convention checked against existing refs before creation, failing closed if a collision is detected.
- Risk: worktree support is unavailable or the target repo is in a detached/dirty state. Impact: isolation cannot be created and the fixer might fall back to writing the live tree. Mitigation: the branch fallback path plus a fail-closed rule that aborts the run rather than writing the working tree when no isolation can be established.
- Risk: the rollback handle is captured incorrectly (wrong ref) and a revert restores the wrong state. Impact: a "reverted" tree that still contains the bad change. Mitigation: capture the handle immediately before each fix and verify post-restore that the tree matches the captured ref, surfacing a mismatch as a hard error.
- Risk: a partially-applied promotion in A2 leaves the working tree half-changed. Impact: an inconsistent tree neither fully fixed nor fully clean. Mitigation: promote each verified fix atomically and define an all-or-nothing promotion boundary per finding.

## 12. Desired End State

A net-new isolation-and-rollback runtime design exists that makes every autonomous write reversible. A run can create a dedicated worktree (or fallback branch), capture a git-ref rollback handle before each fix, and restore exactly that state on demand. The autonomy levels are wired to concrete isolation behaviors so A1 never touches the user's tree and A2 promotes only verified fixes. A path-allowlist guard prevents out-of-bounds writes, and teardown guarantees a clean tree when nothing is promoted. The single most important safety mechanism of the whole pivot now has a concrete, testable design that Phase 3.3 can build its keep/revert gate upon.

## 13. Transition Criteria to the Next Sub-Phase

Before Phase 3.3 begins, the rollback-handle lifecycle (capture, store, restore) must be fully specified, the autonomy-to-isolation behavior table must define A0/A1/A2 write boundaries unambiguously, and the collision-safe naming plus fail-closed no-isolation rule must be written down. The clean-tree invariant must be stated in a form Phase 3.4 can assert. No fix may be promoted to a working tree until the verification gate of Phase 3.3 exists, so this sub-phase must leave the keep/revert decision deliberately unimplemented.
