# Phase 7.3 — Least Privilege and Supply-Chain Safety

## 1. Context

This sub-phase addresses the two production-hardening concerns in parent Phase 7 that point the auditor at itself and at its own footprint rather than at quality numbers. Main-Planning section 6 lists "least-privilege review" and "supply-chain safety of QB itself" as Phase 7 deliverables, and section 4's security target demands "least privilege by default," writes confined to "policy-allowed globs," and that the tool be "safe to run against untrusted repositories (no auto-execution of repo-provided scripts unless explicitly sandboxed and authorized)." The autopsy reinforces both halves: section 9 records that least privilege is "undesigned for writes" and that the untrusted-repo command-execution surface is "the top new risk," while section 6 documents the supply-chain-adjacent debt — cross-host structural asymmetry and manifest version drift with "no single source of version truth and no test asserting version consistency." This sub-phase therefore has two faces: bound what QB is permitted to touch and run (least privilege over file and network access, and never auto-running repo-provided scripts without sandboxed authorization), and audit what QB itself is built from and shipped through (its own dependencies, its CI action pins, its manifests, and its distribution channel). It depends on the policy schema from Phase 4 (which already declares path allowlists and command schemas) and feeds the self-audit run in 7.4, where QB validates these very properties against itself.

## 2. Goal

Produce a least-privilege specification that bounds QB's file access to policy-allowed write globs and its network access to an explicit opt-in set, forbids auto-execution of any repo-provided script without sandboxed authorization, and a supply-chain safety specification that pins and reviews QB's own dependency surface, CI action versions, and distribution manifests — including a manifest-version-consistency gate that the current monorepo lacks.

## 3. Description

This sub-phase turns QB's safety promises from prose into bounded, checkable invariants about its own behavior and provenance. On the least-privilege side it specifies a default-deny posture for writes (only paths matching the policy's allowlisted globs may be written, every other path is refused and the run fails closed), a default-offline posture for the core (no network call unless an analyzer is explicitly opted in, mirroring Main-Planning's offline-core/opt-in-networked split), and an absolute rule against executing repo-provided scripts — build files, hooks, test runners declared by the target — unless the operator has explicitly authorized a sandboxed execution. It builds directly on the structured-command-schema requirement (explicit argv, never shell-string interpolation) that Phases 2 and 3 establish, extending it from a per-analyzer rule into a tool-wide privilege boundary. On the supply-chain side it reviews QB's own footprint: the core is dependency-free Python plus bash/coreutils, and that property must be asserted and protected; the GitHub Actions in `.github/workflows/validate.yml` (`actions/checkout@v4`, `actions/setup-python@v5`) are version-tagged and their pinning policy must be reviewed; and the divergent plugin manifests (claude-code, cursor, codex) must gain a version-consistency gate so the silent drift the autopsy found cannot recur. This belongs in Phase 7 because least privilege and supply-chain integrity are production properties — they matter most once the tool runs unattended and writes code — and it directly precedes 7.4, which dogfoods these guarantees by auditing QB with QB.

## 4. Scope

- Write least-privilege specification: default-deny, only policy-allowlisted globs writable, path-traversal refusal, fail-closed on any out-of-allowlist write attempt.
- Network least-privilege specification: default-offline core, explicit opt-in per networked analyzer, no implicit egress (including no telemetry upload).
- Repo-provided-script execution policy: never auto-run target-supplied scripts/build/hooks without explicit sandboxed operator authorization.
- Dependency footprint review of QB itself: assert and protect the dependency-free core (Python stdlib plus bash/coreutils), and classify any optional analyzer dependency as opt-in.
- CI action and toolchain pinning review: review the pinning of `actions/checkout`, `actions/setup-python`, and the `python-version` in `.github/workflows/validate.yml`.
- Distribution and manifest integrity: a manifest-version-consistency gate across the three `plugin.json` manifests and the root marketplace manifests.
- A privilege-and-provenance test design extending the existing `tests/` invariants.

## 5. Out of Scope

- Telemetry metric definitions and precision thresholds (Phase 7.1).
- Backup, rollback drills, and release gates (Phase 7.2).
- The kill-switch wiring, operations runbook, and the QB-on-QB dogfood execution and its production-gated acceptance (Phase 7.4) — this sub-phase defines what that run must check, not the run itself.
- The structured command schema's per-analyzer details (Phase 2) and the per-fix isolation primitive (Phase 3); this consumes and bounds them rather than defining them.
- Building a sandbox runtime (containers, VMs, seccomp): this sub-phase specifies the authorization boundary and the never-auto-run rule, not a sandbox implementation.
- Resolving the codex structural-layout asymmetry beyond the version-consistency gate (the broader parity fix is Phase 6 / a separate hygiene track).

## 6. Current Repository Evidence

QB's core is genuinely dependency-light: `shared/scripts/validate_planner_docs.py` is pure standard-library Python and `scripts/sync.sh` declares itself "Dependency-free: bash + coreutils (cmp / cp / mkdir / dirname)," so the offline-core property is real and worth protecting. There is, however, no write-path allowlist or network-access control anywhere, because the current tool only reads documents and writes planning files under operator direction — the autopsy (section 9) confirms least privilege is undesigned for writes and the untrusted-repo execution surface is unmitigated. On the supply-chain side, CI (`.github/workflows/validate.yml`) pins actions to major tags (`actions/checkout@v4`, `actions/setup-python@v5`) and uses `python-version: "3.x"`, which is a loose floating pin. The plugin manifests carry inconsistent versions (autopsy section 6 and section 13: claude-code `0.3.0`, cursor `0.6.0`, codex `0.3.0`) with no test asserting consistency, and `tests/` today checks manifest ids and frontmatter (`test_manifests_and_frontmatter.py`) and cross-host residue (`test_no_cross_host_residue.py`) but not version parity. No auto-run of repo-provided scripts exists yet because no fixer runtime ships, which is precisely why the prohibition must be specified before one does.

## 7. Planned Work Breakdown

- F7.3-01 — Write least-privilege specification
  - Description: Specify default-deny writes confined to policy-allowlisted globs, path-traversal refusal, and fail-closed behavior on any out-of-allowlist write attempt, extending the command-schema discipline into a tool-wide write boundary.
  - Output: a write-privilege rule set with the allowlist-evaluation order.
- F7.3-02 — Network least-privilege specification
  - Description: Specify a default-offline core with explicit per-analyzer opt-in network access and an explicit no-implicit-egress rule (including no telemetry upload).
  - Output: a network-privilege rule set and the opt-in declaration shape.
- F7.3-03 — Repo-provided-script execution policy
  - Description: Specify that target-supplied scripts, build files, and hooks are never auto-run without explicit sandboxed operator authorization, with fail-closed default.
  - Output: an execution-authorization policy with the authorization handshake described.
- F7.3-04 — QB dependency footprint review
  - Description: Assert and protect the dependency-free core (stdlib Python plus bash/coreutils per `scripts/sync.sh`) and classify any optional analyzer dependency as opt-in only.
  - Output: a dependency inventory and a core-dependency-free assertion.
- F7.3-05 — CI action and toolchain pinning review
  - Description: Review and tighten the pinning of `actions/checkout`, `actions/setup-python`, and `python-version` in `.github/workflows/validate.yml`, recommending a pinning policy.
  - Output: a pinning-policy recommendation for QB's own CI supply chain.
- F7.3-06 — Manifest-version-consistency gate
  - Description: Define a gate asserting the three plugin manifests and root marketplace manifests carry consistent versions, closing the drift the autopsy found.
  - Output: a version-consistency gate design extending the `tests/` manifest checks.

## 8. Acceptance Criteria

- The write least-privilege rule set states a default-deny posture, an allowlist-evaluation order, and explicit fail-closed behavior on out-of-allowlist or path-traversing writes.
- The network rule set confirms the core is offline by default, network is per-analyzer opt-in, and no telemetry or other data is uploaded implicitly.
- The repo-provided-script execution policy forbids auto-running any target-supplied script absent explicit sandboxed authorization, with a fail-closed default.
- QB's own dependency footprint is inventoried and the dependency-free-core property (stdlib Python, bash/coreutils) is asserted with a protecting check.
- A CI pinning-policy recommendation addresses `actions/checkout`, `actions/setup-python`, and the floating `python-version: "3.x"`.
- A manifest-version-consistency gate is designed to detect the drift documented in the autopsy, extending the existing `tests/test_manifests_and_frontmatter.py` style; local readiness (gate written and tested) is distinguished from live readiness (gate green across all shipped manifests).
- No secret values, tokens, or credentials appear in the plan.

## 9. Validation and Test Approach

Document validation: `python3 shared/scripts/validate_planner_docs.py --strict` confirms headings and absence of placeholder tokens. Local smoke: a proposed least-privilege test would attempt an out-of-allowlist write and a path-traversal write against a fixture and assert both are refused and the run fails closed; a proposed network test asserts the core makes zero network calls when no analyzer opts in. Security validation: the existing `tests/test_no_committed_secrets.py` and `tests/test_no_cross_host_residue.py` remain in force, and the new manifest-version-consistency gate runs under `python3 -m unittest discover -s tests`. Supply-chain validation: a proposed dependency-free-core assertion checks the core imports only the standard library; the CI pinning review is validated by inspecting `.github/workflows/validate.yml` against the recommended policy. CI: `make check` continues to gate merges and gains the privilege and version-consistency tests. Live readiness: actually running QB against an untrusted repository with these boundaries enforced is an operational milestone tied to 7.4's self-audit, not asserted by this plan.

## 10. Dependencies and Sequencing

Depends on Phase 4 (the policy schema that declares write-path allowlists, network opt-ins, and command-execution permission — least privilege is the enforcement view of that policy), Phase 2 and Phase 3 (the structured command schemas this boundary extends), and the existing `tests/` conventions for the version-consistency gate. Required decisions: the canonical source of version truth across manifests (to be confirmed during implementation), and the exact CI pinning policy (major-tag versus commit-SHA pinning) for QB's own actions. Required human approvals: any sandboxed execution of repo-provided scripts is an explicit per-run operator authorization. No live credentials are needed to write or test these specifications. This sub-phase precedes and feeds 7.4, where QB's self-audit must confirm these privilege and supply-chain invariants hold against QB itself.

## 11. Risks and Mitigations

- Risk: a write allowlist is too permissive (for example a broad glob) and effectively grants unrestricted writes. Impact: least privilege becomes nominal and a fixer can clobber unintended files in an untrusted repo. Mitigation: require the allowlist to be explicit, deny by default, and verified by a test that an out-of-allowlist and a traversing path are both refused with a fail-closed stop.
- Risk: an opt-in networked analyzer becomes an implicit egress channel for evidence or secrets. Impact: the offline-core promise is broken and data leaves the machine unexpectedly. Mitigation: gate all network access behind explicit per-analyzer opt-in, forbid implicit telemetry upload, and assert zero network calls in the no-opt-in case.
- Risk: the floating `python-version: "3.x"` and major-tag action pins let an upstream change silently alter CI behavior. Impact: a supply-chain shift in QB's own toolchain goes unnoticed. Mitigation: adopt the recommended pinning policy and review action versions deliberately rather than tracking moving tags.
- Risk: manifest version drift recurs after a one-time cleanup. Impact: the three hosts ship divergent versions again, exactly the autopsy finding. Mitigation: encode the version-consistency check as a gate in `tests/` so drift fails CI rather than relying on manual vigilance.
- Risk: a repo-provided script runs implicitly through an analyzer that shells out to a target build tool. Impact: arbitrary code execution on the operator's machine. Mitigation: enforce explicit-argv command schemas, forbid shell-string interpolation, and require explicit sandboxed authorization before any target-supplied script executes.

## 12. Desired End State

QB operates under an enforced least-privilege posture: writes are default-deny and confined to policy-allowlisted globs with path-traversal refused and fail-closed stops, the core is offline unless an analyzer is explicitly opted in, and no target-provided script ever runs without explicit sandboxed authorization. QB's own supply chain is reviewed and bounded: the dependency-free core is asserted and protected, CI actions and the Python toolchain follow a deliberate pinning policy, and a manifest-version-consistency gate prevents the version drift the autopsy documented from recurring. These invariants are stated precisely enough for the Phase 7.4 self-audit to verify them against QB itself.

## 13. Transition Criteria to the Next Sub-Phase

Before Phase 7.4, the write and network least-privilege rule sets and the repo-provided-script execution policy must be written as fail-closed, testable invariants; the dependency-free-core assertion and the CI pinning-policy recommendation must be in place; and the manifest-version-consistency gate must be designed in the `tests/` style and shown to detect the documented drift. The boundary between local enforcement readiness (tests pass on fixtures) and live enforcement against an untrusted repository must be explicit, since 7.4 exercises the live case. The document checker (`python3 shared/scripts/validate_planner_docs.py --strict`) must report this sub-plan as clean before proceeding.
