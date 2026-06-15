# Phase 6.4 — Manifest and Structure Consistency

## 1. Context

This sub-phase resolves the two parity hazards the autopsy demands be settled before a write-capable engine fans out to three hosts plus headless: the manifest version drift and the codex structural asymmetry. `Planner-docs/Autopsy.md` section 11 states it directly for this phase: "Phase 6 (multi-host + headless): needs the codex structural divergence and version drift resolved or explicitly accepted before fanning out a writer." The same report's prioritized signal AUTOPSY-P2-01 records the evidence: codex uses a nested `plugins/qb/skills/qb/` layout with capitalized `*-Planner.md` filenames and an `agents/openai.yaml`, plus a 262-line `validate.sh` versus roughly 131 lines for claude-code and cursor; and the `qb` plugin version differs across manifests (claude-code `0.3.0`, cursor `0.6.0`, codex `0.3.0`) "with no consistency test." The parent Phase 6 acceptance signals in `Planner-docs/Main-Planning.md` section 6 include "Sync-clean across hosts" and "invariant tests extended and green." This sub-phase converts those structural and metadata hazards from silent drift into CI-caught failures, so the parity established by Phases 6.1-6.3 cannot quietly regress.

## 2. Goal

Resolve or explicitly and consistently document the codex structural asymmetry, align the plugin version across all three manifests under a single version-truth policy, and add CI-enforced consistency tests — a manifest-version-alignment test and a structural-invariant test — so that any future version drift or unsanctioned structural divergence fails `make check`. The outcome is that multi-host parity is guaranteed by tests rather than by reviewer vigilance, removing the autopsy's pre-fan-out blocker.

## 3. Description

The problem here is metadata and shape drift that the byte-for-byte sync contract does not cover. `scripts/sync.sh --check` proves the synced shared files are identical, but it says nothing about plugin versions or about the directory shape and casing around those files — so the codex package can diverge structurally and the three manifests can carry three different versions without any check complaining. With a read-only planning product this asymmetry is tolerable debt; once an autonomous write-capable engine ships on all hosts plus a headless surface, the asymmetry multiplies the places where behavior can differ, which is precisely why the autopsy makes resolving or accepting it a Phase 6 precondition. This sub-phase makes a deliberate decision per hazard: for the version drift, designate one source of version truth and align the manifests, then pin that with a test; for the codex layout, either normalize it toward the other hosts or formally accept it and encode the accepted shape as a structural invariant the test enforces. It belongs at the end of Phase 6 because the new launch adapters (6.2) and headless surface (6.3) add files to each platform, so the structural-invariant test should be written against the final, post-fan-out shape. It reduces risk by closing the exact gap the autopsy names as undetected (no version-consistency test) and prepares Phase 7, where a self-audit and release gates assume a consistent, test-pinned package layout.

## 4. Scope

- A single source-of-version-truth policy for the `qb` plugin and alignment of the three manifest versions (`platforms/claude-code/.claude-plugin/plugin.json`, `platforms/cursor/.cursor-plugin/plugin.json`, `platforms/codex/plugins/qb/.codex-plugin/plugin.json`) to it.
- A manifest-version-consistency test that fails when the three plugin versions diverge.
- A decision record for the codex structural asymmetry: either normalize the layout/casing toward claude-code/cursor, or explicitly accept the divergence with a written rationale.
- A structural-invariant test that pins the accepted per-host shape (expected directories, the codex nested `plugins/qb/skills/qb/` layout and capitalized reference filenames if accepted, presence of `agents/openai.yaml`).
- Reconciliation of the `validate.sh` size/scope divergence so the three scripts assert an equivalent contract even where the codex layout differs.
- Updates to `tests/qb_monorepo.py` descriptors if the structural decision changes any platform's expected paths or forbidden-token sets.

## 5. Out of Scope

- Engine artifact authoring, sync `MAP` extension, host launch adapters, and the headless CLI — those are Phases 6.1, 6.2, and 6.3 respectively.
- Changing the plugin id `qb` or the marketplace registration model — the id invariant is preserved.
- Any auto-commit, auto-push, auto-PR, or release tagging; this sub-phase aligns version metadata but does not cut a release.
- Documentation rewrites for the audit/harden pivot beyond what version alignment and structural decisions require (broad doc updates are tracked separately per autopsy AUTOPSY-P3-01).
- Network access, dependency installation, or secret handling.

## 6. Current Repository Evidence

The version drift is directly observable in the three manifests: `platforms/claude-code/.claude-plugin/plugin.json` declares `"version": "0.3.0"`, `platforms/cursor/.cursor-plugin/plugin.json` declares `"version": "0.6.0"`, and `platforms/codex/plugins/qb/.codex-plugin/plugin.json` declares `"version": "0.3.0"`. `tests/test_manifests_and_frontmatter.py` already enforces that each version is valid semver (`^\d+\.\d+\.\d+$`) and that license is MIT, but it asserts nothing about the three versions being equal — confirming the autopsy's "no consistency test" finding. The codex structural divergence is visible in the file tree: `platforms/codex/plugins/qb/skills/qb/references/` holds `First-Planner.md`, `Second-Planner.md`, `Third-Planner.md`, `Fourth-Planner.md`, and `Autopsy-Planner.md` (capitalized), plus `agents/openai.yaml`, whereas claude-code and cursor use flat lowercase `skills/<name>/`, `references/`, `commands/`, and `agents/` paths; `wc -l` shows `platforms/codex/scripts/validate.sh` at 262 lines versus 131 (claude-code) and 132 (cursor). `tests/qb_monorepo.py` encodes per-platform descriptors with distinct `manifest` paths and `forbidden` token sets, giving a natural place to add a version-equality assertion and structural invariants.

## 7. Planned Work Breakdown

- F6.4-01 — Version source-of-truth policy and manifest alignment
  - Description: Choose one authoritative version value and policy for the `qb` plugin, then align all three plugin manifests to it so claude-code, cursor, and codex carry the same version.
  - Expected output: Three manifests with an identical, policy-defined version and a written rule for how the version is bumped going forward.
- F6.4-02 — Manifest-version-consistency test
  - Description: Add a test (extending `tests/test_manifests_and_frontmatter.py` or a sibling module using `tests/qb_monorepo.py` descriptors) that fails when the three plugin versions differ.
  - Expected output: A CI-gated test that catches version drift the existing semver check misses.
- F6.4-03 — Codex structural-asymmetry decision record
  - Description: Decide and document whether to normalize the codex layout/casing toward the other hosts or explicitly accept the divergence, with rationale grounded in Codex packaging requirements.
  - Expected output: A decision record stating the accepted per-host shape, including codex nesting/casing and `agents/openai.yaml` status.
- F6.4-04 — Structural-invariant test
  - Description: Add a test pinning the accepted per-host directory shape and key filenames so an unsanctioned structural change (for example a renamed codex reference) fails `make check`.
  - Expected output: A structural-invariant test asserting expected paths per platform and rejecting drift from the ratified shape.
- F6.4-05 — validate.sh contract reconciliation
  - Description: Reconcile the three `validate.sh` scripts so they assert an equivalent presence/parse contract despite layout differences, reducing the unexplained 262-vs-131 line gap to deliberate, documented differences.
  - Expected output: Three `validate.sh` scripts whose differences are intentional and explained, each still `set -euo pipefail` and standard-library-only.

## 8. Acceptance Criteria

- All three `qb` plugin manifests carry the same version value, governed by a written single-source-of-version-truth policy.
- A manifest-version-consistency test fails when any one of the three manifest versions is changed away from the others, and passes when they match; this gap was previously undetected by the semver-only check.
- The codex structural asymmetry is either normalized or explicitly accepted in a decision record, and a structural-invariant test pins the chosen shape so an unsanctioned layout or filename change fails `make check`.
- The three `validate.sh` scripts assert an equivalent contract, with any remaining size or scope difference documented as intentional rather than accidental.
- `make check` passes with the new consistency tests, and `tests/qb_monorepo.py` descriptors reflect any path or token changes the structural decision introduced.
- No plugin id changes (all remain `qb`), no release is cut, and no secret is written; these consistency changes are local readiness, not a live deploy.

## 9. Validation and Test Approach

Document validation: confirm the version-truth policy and the codex decision record are unambiguous and that the structural-invariant test encodes exactly the accepted shape. Local unit validation: run `python3 -m unittest tests.test_manifests_and_frontmatter` plus the new consistency/structural modules and confirm they fail on an intentionally mismatched version or a renamed codex reference (a transient mutation during review, reverted afterward) and pass on the aligned tree. Local smoke: run `make check`, which runs the three `validate.sh` scripts and the full unit suite, to confirm the reconciled validators and new tests are green. CI validation: `.github/workflows/validate.yml` runs `make check` on push to `main` and every pull request, so version drift and structural divergence are gated automatically once the tests land. Security validation: rely on the committed-secret test path to confirm manifest and test edits introduce no secret. Live readiness is not in scope here; this sub-phase pins consistency, it does not release. All listed commands already exist in the repository; the new tests are proposed additions.

## 10. Dependencies and Sequencing

This sub-phase is best sequenced last within Phase 6 because the structural-invariant test in F6.4-04 should pin the final post-fan-out shape, which includes the launch adapter files from Phase 6.2 and the headless script destinations from Phase 6.3. It depends on Phase 6.1 only insofar as the structural test should account for the new engine artifact destinations. It is the direct resolution of autopsy signal AUTOPSY-P2-01 and removes the autopsy's stated precondition for fanning out a write-capable engine. No live credentials, network access, or infrastructure are required. The blocking decision is the codex normalize-versus-accept choice (F6.4-03), which is a packaging judgement that must be made before F6.4-04 can pin the shape; it should be confirmed with the maintainer since it affects the codex package layout and any downstream Codex install instructions.

## 11. Risks and Mitigations

- Risk: normalizing the codex layout breaks Codex package discovery or its install path. Impact: the codex plugin stops loading. Mitigation: prefer explicit acceptance with a documented rationale where Codex requires the nested `plugins/qb/skills/qb/` shape, and validate any normalization against Codex packaging expectations before changing paths.
- Risk: the chosen single version value is wrong (for example regressing cursor's `0.6.0` history). Impact: a misleading version that confuses users tracking releases. Mitigation: the F6.4-01 policy explicitly selects the highest meaningful version or a deliberate reset and records the reasoning, rather than picking arbitrarily.
- Risk: the structural-invariant test is over-tight and fails on every legitimate future file addition. Impact: friction that pressures contributors to weaken the test. Mitigation: pin only load-bearing structural facts (key directories, codex casing/nesting, `agents/openai.yaml` presence) rather than an exhaustive file list, and update `tests/qb_monorepo.py` descriptors deliberately.
- Risk: reconciling `validate.sh` scripts accidentally drops a codex-specific check encoded in its larger script. Impact: a real codex validation gap. Mitigation: treat the 262-line codex `validate.sh` as the superset to preserve, documenting which checks are codex-specific rather than deleting them.

## 12. Desired End State

The `qb` plugin carries one consistent version across all three manifests under a written version-truth policy, and a manifest-version-consistency test fails the build if they ever diverge again. The codex structural asymmetry is settled — either normalized toward the other hosts or explicitly accepted with rationale — and a structural-invariant test pins the ratified per-host shape so an unsanctioned layout or filename change fails `make check`. The three `validate.sh` scripts assert an equivalent contract with only intentional, documented differences. The autopsy's pre-fan-out precondition is satisfied: parity across Claude Code, Cursor, Codex, and headless is guarded by CI-enforced tests, not by reviewer attention.

## 13. Transition Criteria to the Next Sub-Phase

Phase 6 is complete and ready to hand to Phase 7 when: all three manifests share one policy-defined version; the manifest-version-consistency test and the structural-invariant test are present, green, and demonstrably fail on an injected mismatch; the codex normalize-or-accept decision is recorded and the structural test pins the accepted shape; the three `validate.sh` scripts assert an equivalent contract with documented differences; `make check` and the full unit suite pass; and `git status --short` confirms only manifest, test, `validate.sh`, and `tests/qb_monorepo.py` files changed. With consistency CI-enforced and the four-host parity (Phases 6.1-6.3) in place, Phase 7 production hardening and self-audit may begin.
