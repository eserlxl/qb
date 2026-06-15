# Phase 2.4 — Dependency and Supply-Chain Analyzer (Opt-In Networked)

## 1. Context

This sub-phase closes Phase 2 by adding dependency and supply-chain auditing — the one analyzer category that legitimately wants a network — while honoring the offline-core / opt-in-networked split the autopsy demands. `Planner-docs/Autopsy.md` section 1 frames the central tension: QB's "zero-setup, dependency-free" identity must not be betrayed by "heavy SAST/CVE" work, and `Planner-docs/Main-Planning.md` section 7 names the risk directly ("The 'zero-setup, dependency-free' property conflicts with real analyzers") with the mitigation being "a strict offline-core / opt-in-networked split ... and graceful degradation when an optional analyzer is absent." Section 5 ("Integration boundaries") of the master plan adds that "external/network-dependent analyzers (e.g. CVE feeds) are opt-in and clearly separated from the offline, dependency-free core." This analyzer is therefore deliberately last in Phase 2: it is the only one allowed to reach the network, it must be off by default, and it must fall back to a purely offline manifest audit when networking is disabled or unreachable.

## 2. Goal

Deliver an opt-in dependency-and-supply-chain analyzer that, when networked access is explicitly enabled by configuration, enriches dependency findings with vulnerability data and emits graded `Finding` records (category such as `dependency` and `supply-chain`) with package, version, and advisory evidence — and that, when networking is disabled, unavailable, or unconfigured, falls back to a fully offline manifest-and-lockfile audit without failing, keeping the default behavior network-free.

## 3. Description

The analyzer has two clearly separated tiers. The offline tier parses dependency manifests and lockfiles present in the target repository to inventory declared and pinned dependencies, flagging hygiene issues it can determine without a network — for example unpinned versions or absent lockfiles — as findings. The opt-in networked tier, activated only by an explicit configuration flag, augments that inventory by consulting a vulnerability/advisory source to attach known-CVE evidence and adjust severity. The split is fail-closed toward offline: if the network flag is unset, the network is unreachable, or the configured source errors, the analyzer silently and successfully completes at the offline tier and records that the networked enrichment was skipped. All external access uses the structured argv convention from Phase 2.2 if it shells out to a scanner, and never interpolates untrusted manifest content into a command. This belongs last in Phase 2 because it is the only category that crosses the offline boundary, so isolating it preserves the zero-setup default for every other analyzer; it reduces project risk by making network use a deliberate, bounded opt-in rather than an implicit dependency, and it prepares Phase 4 by giving the policy engine a concrete networked capability to gate.

## 4. Scope

- An offline tier that inventories dependencies from manifests and lockfiles and flags pinning/lockfile hygiene as findings.
- An opt-in networked tier, off by default, that enriches the inventory with vulnerability/advisory data when explicitly enabled.
- A configuration flag that gates all network access, with fail-closed fallback to the offline tier.
- Categories `dependency` and `supply-chain` mapped to severities, with CVE-derived severity when networked.
- Provenance distinguishing offline-derived findings from network-enriched findings.
- Structured argv invocation if an external scanner is used, with no interpolation of manifest content.
- Fixtures: a repo with planted dependency hygiene issues for the offline tier, and a network-disabled run proving offline fallback.

## 5. Out of Scope

- Making networked CVE enrichment the default behavior; the default must remain fully offline.
- Auto-upgrading, pinning, or otherwise remediating vulnerable dependencies; remediation is Phase 3 under policy control.
- Bundling a vulnerability database or vendoring a CVE feed into the base install.
- Continuous or scheduled re-scanning; this slice audits the repository on demand only.
- Authenticating to private package registries or paid advisory services; only an explicitly configured source is consulted.
- Defining the policy thresholds that decide which dependency findings may be auto-fixed; that governance is Phase 4.

## 6. Current Repository Evidence

The repository has no dependency or supply-chain analyzer and, fittingly, almost no runtime dependencies of its own: the autopsy section 4 notes "no application code, no service, no CLI" and the validator `shared/scripts/validate_planner_docs.py` is dependency-free, which is exactly the offline-core property this analyzer must not erode. There is no networked code path anywhere in QB today — `scripts/sync.sh`, the per-platform `validate.sh`, and the test suite are all offline — so this analyzer introduces the first deliberate network boundary in the codebase, which is precisely why it must be opt-in and fail-closed. AUTOPSY-P1-03's command-execution concern applies if the networked tier shells out to a scanner, mandating the Phase 2.2 argv convention. Current repository evidence for vulnerability-enrichment behavior is limited, because no manifest parser, no advisory client, and no dependency fixtures exist yet; this sub-phase authors the offline inventory tier and the gated networked tier from the contracts established earlier in Phase 2.

## 7. Planned Work Breakdown

- F2.4-01 — Offline dependency inventory tier
  - Description: Parse manifests and lockfiles in the target repo to inventory dependencies and flag pinning/lockfile hygiene as findings.
  - Output: an offline-tier specification with the manifest formats covered and the hygiene findings it emits.
- F2.4-02 — Network-gating configuration flag
  - Description: Define the explicit, default-off flag that authorizes any network access for vulnerability enrichment.
  - Output: a configuration-contract specification stating the default-offline behavior.
- F2.4-03 — Opt-in vulnerability enrichment tier
  - Description: Specify how an enabled networked run augments inventory findings with advisory/CVE evidence and adjusted severity.
  - Output: an enrichment-tier specification including the structured argv form if a scanner is invoked.
- F2.4-04 — Fail-closed offline fallback
  - Description: Define behavior when the flag is unset, the network is unreachable, or the source errors: complete successfully at the offline tier and record the skip.
  - Output: a fallback-behavior specification with the skipped-enrichment signal format.
- F2.4-05 — Offline-hygiene and network-disabled fixtures
  - Description: Build a fixture with planted dependency hygiene issues and a network-disabled run proving offline completion.
  - Output: fixture layout, expected offline findings, and expected fallback behavior.

## 8. Acceptance Criteria

- With networking disabled or unconfigured, the analyzer completes successfully, emits only offline-tier `dependency` findings, and records that network enrichment was skipped — the default path is provably network-free.
- With networking explicitly enabled, enriched findings carry advisory/CVE evidence and network-derived severity, and provenance distinguishes them from offline-derived findings.
- When the network is enabled but unreachable or the source errors, the analyzer falls back to the offline tier without failing the audit.
- Any external scanner invocation uses the structured argv convention from Phase 2.2 and never interpolates manifest content into a command line.
- The base install consults no network unless the gating flag is set, preserving the zero-setup default.
- Offline-tier hygiene findings (for example unpinned dependencies or a missing lockfile) are emitted with correct evidence and severity against the fixture.

## 9. Validation and Test Approach

- Document validation: confirm the two-tier design, the default-off network flag, and the fail-closed fallback are specified unambiguously.
- Offline smoke (proposed): run the analyzer network-disabled over the dependency-hygiene fixture, asserting offline findings and a recorded enrichment skip.
- Fallback smoke (proposed): enable networking but simulate an unreachable source, asserting the audit still completes at the offline tier.
- Networked readiness (live, gated): a separately marked check that enrichment attaches advisory evidence only runs when networking is explicitly authorized; it is never part of the default offline test path.
- Convention conformance: reuse the Phase 2.2 argv test if a scanner is shelled out.
- Regression and CI: keep `make check` and `python3 -m unittest discover -s tests` green, and ensure the default CI run requires no network.

## 10. Dependencies and Sequencing

- Depends on the Phase 1 `Finding` schema for the shape of dependency and supply-chain findings.
- Depends on the Phase 2.2 structured argv convention if the networked tier invokes an external scanner.
- Reuses the Phase 2.3 capability-report surface to mark whether networked enrichment ran or was skipped.
- Requires an explicit human-authorized configuration flag before any network access; this is the one analyzer with a live-readiness gate.
- No private credentials are written to repo files; any configured source is referenced by configuration, not by embedding secrets.
- Any new shared file must be added to the `scripts/sync.sh` MAP so all three hosts receive it.

## 11. Risks and Mitigations

- Risk: networked enrichment becomes a de-facto default and breaks the zero-setup promise. Impact: a base install unexpectedly requires the network. Mitigation: make the network flag default-off and gate the sub-phase on a network-disabled fixture run that must produce a complete offline audit.
- Risk: an unreachable or failing advisory source aborts the audit. Impact: a transient network issue fails an otherwise valid run. Mitigation: fail closed to the offline tier on any network error and record an enrichment-skipped signal rather than erroring.
- Risk: untrusted manifest content is interpolated into a scanner command. Impact: command injection from a malicious dependency file. Mitigation: invoke any scanner only through the Phase 2.2 argv convention with manifest content passed as data, never as command text.
- Risk: a configured advisory source requires a credential that leaks into repo files. Impact: secret exposure. Mitigation: reference sources by configuration only, never embed credentials, and rely on the Phase 2.1 redaction contract for any quoted output.

## 12. Desired End State

QB has a two-tier dependency-and-supply-chain analyzer whose default behavior is a fully offline manifest-and-lockfile audit emitting `dependency` and `supply-chain` findings, with an explicit, default-off configuration flag that authorizes networked vulnerability enrichment when desired. The analyzer fails closed to the offline tier whenever networking is disabled, unreachable, or erroring, distinguishes offline-derived from network-enriched findings by provenance, and invokes any external scanner only through the structured argv convention. The offline-core / opt-in-networked split the autopsy demanded is now concretely realized, and the zero-setup default is preserved and tested.

## 13. Transition Criteria to the Next Sub-Phase

- The network-disabled fixture run produces a complete offline dependency audit, and the network-enabled-but-unreachable run falls back without failing.
- The default-off network flag and fail-closed fallback are documented and tested, with the default CI path requiring no network.
- Provenance cleanly separates offline-derived from network-enriched findings, ready for the Phase 4 policy engine to gate networked capability.
- `make check` and the existing test suite remain green, and any new shared file is wired into the `scripts/sync.sh` MAP, completing the Phase 2 analyzer suite for the Phase 3 fixer to consume.
