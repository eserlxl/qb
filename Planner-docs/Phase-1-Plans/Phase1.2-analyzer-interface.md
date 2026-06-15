# Phase 1.2 — Pluggable Read-Only Analyzer Interface

## 1. Context

Phase 1's parent goal in `Planner-docs/Main-Planning.md` §6 pairs the Finding schema with "the ability to run read-only analyzers over an arbitrary repository." Phase 1.1 froze the Finding contract; this sub-phase defines the second half of that pair — the interface that any analyzer implements to produce those findings. Main-Planning §5 names "Analyzers — read-only, produce findings" as the first of four control-plane roles, and the autopsy §3 records that this role "does not exist as code or interfaces" today. Establishing the interface now is what makes Phase 2's analyzer suite a matter of writing conformant plugins rather than re-inventing wiring per analyzer. It sits second in Phase 1: it consumes the frozen Finding type from Phase 1.1, it is the target the refactored validator must conform to in Phase 1.3, and it is the unit the runner enumerates in Phase 1.4.

## 2. Goal

Define a single, host-neutral analyzer interface that fixes the read-only contract, the input shape (a repository root plus a configuration object), the output shape (a list of conformant Findings), the discovery and registration mechanism by which the runner finds analyzers, and an explicit per-analyzer declaration of whether it is offline or network-dependent — accompanied by exactly one trivial reference analyzer that proves the interface end to end without embedding any real analysis logic. The outcome is an interface stable enough that Phase 2 analyzers and the Phase 1.3 validator refactor can both implement it without changes to the contract.

## 3. Description

This sub-phase delivers the analyzer abstraction and a single reference implementation, deliberately containing no security or quality detection logic of its own. Its purpose is to decouple "what an analyzer is" from "what any particular analyzer detects," so Phase 2 can grow the suite additively. The interface must encode read-only as a hard property, because Main-Planning §5 and the autopsy §9 both insist analyzers never write, and because a write-capable analyzer would collapse the safety separation between auditing and the Phase 3 fixer. The offline-versus-networked declaration is first-class here rather than an afterthought because Main-Planning §5 and Risk four in §7 require a strict offline-core / opt-in-networked split to protect QB's zero-setup promise; encoding that flag in the interface lets the runner and policy engine reason about it uniformly. The trivial reference analyzer (for example one that reports a single deterministic informational finding about the repository root) exists only to exercise registration, invocation, and finding emission, giving Phase 1.4's runner a concrete plugin to enumerate before any real analyzer exists.

## 4. Scope

- An analyzer interface definition under `shared/` describing the method(s) every analyzer implements.
- The read-only contract expressed as an interface obligation, not merely documentation.
- The input contract: a repository root path plus a configuration object the analyzer may read.
- The output contract: a list of Findings conformant to the Phase 1.1 schema.
- A discovery and registration mechanism by which the runner enumerates available analyzers.
- A per-analyzer capability declaration: `offline` versus `networked`, plus a stable analyzer identifier and category coverage.
- One trivial reference analyzer that implements the interface and emits a single deterministic finding.
- A graceful-absence rule: how the registry behaves when an optional (for example networked) analyzer is unavailable.

## 5. Out of Scope

- The Finding schema fields and vocabularies themselves (frozen in Phase 1.1).
- Any real security, quality, or correctness analyzer (entire Phase 2 suite).
- Structured command schemas for wrapping external tools (designed in Phase 2 when real external analyzers arrive).
- The validator refactor that makes the existing checker an analyzer (Phase 1.3).
- The runner that executes the registry and the output-directory convention (Phase 1.4).
- Any write-capable behavior, isolation, or rollback (Phase 3).
- Policy-driven enabling/disabling of analyzers by autonomy level (Phase 4).
- Networked CVE or dependency feeds beyond the abstract `networked` capability flag.

## 6. Current Repository Evidence

No analyzer abstraction, registry, or plugin mechanism exists in the repository; the autopsy §3 and §7 explicitly record the Analyzer role as prose-only and the role boundaries as missing. The closest structural precedent is the validator's set of self-contained `validate_*` functions in `shared/scripts/validate_planner_docs.py` (for example `validate_step1`, `validate_step2`, `validate_step3_preflight`), each taking shared state and contributing findings — a manual, hard-wired version of what a registry will generalize. The validator is also a working example of the read-only property this interface must formalize: it only reads and never mutates the tree it inspects. For the offline split, `scan_secrets` (lines 519-534) is a purely local routine that needs no network, illustrating the `offline` capability the interface will let analyzers declare. The plugin-discovery patterns in `platforms/*` (manifest-driven component discovery) are a conceptual reference for registration but are host-specific; the interface here must stay host-neutral in `shared/`. Current repository evidence for a pluggable analyzer contract is otherwise limited.

## 7. Planned Work Breakdown

- F1.2-01 — Interface method contract
  - Description: Specify the analyzer method signature in host-neutral terms — what it receives, what it returns, and that it must not mutate the repository — so any implementer has one unambiguous shape to satisfy.
  - Output: an interface specification section under `shared/` with the method contract.
- F1.2-02 — Input and configuration object
  - Description: Define the repository-root input and the configuration object an analyzer may consult (for example include/exclude globs), keeping configuration read-only from the analyzer's perspective.
  - Output: an input-contract section with the configuration fields enumerated.
- F1.2-03 — Output binding to the Finding schema
  - Description: Bind the return value to the Phase 1.1 schema as a list of conformant Findings and state that emitting a non-conformant finding is a contract violation caught by the conformance test.
  - Output: an output-contract section referencing the frozen schema.
- F1.2-04 — Capability declaration and identity
  - Description: Require each analyzer to declare a stable identifier, its covered categories, and an `offline` versus `networked` flag, so the runner and future policy engine can filter and sequence analyzers.
  - Output: a capability-declaration section with the required descriptor fields.
- F1.2-05 — Discovery and registration mechanism
  - Description: Define how analyzers are registered and enumerated by the runner, including the graceful-absence behavior when an optional analyzer cannot load.
  - Output: a registry specification with the registration and absence-handling rules.
- F1.2-06 — Trivial reference analyzer
  - Description: Specify one minimal analyzer that emits a single deterministic informational finding, used solely to prove registration and invocation; it performs no real defect detection.
  - Output: a reference-analyzer specification and the deterministic finding it emits.

## 8. Acceptance Criteria

- An interface specification under `shared/` states the analyzer method contract, the read-only obligation, the input shape, and the output shape as a list of Phase 1.1-conformant Findings.
- The read-only property is expressed as an enforceable interface obligation, and the document states how a write attempt by an analyzer is considered a contract breach.
- Every analyzer is required to carry a descriptor with a stable id, covered categories, and an explicit `offline` or `networked` flag; the document gives one example descriptor.
- A discovery/registration mechanism is specified, including deterministic enumeration order so the runner sees analyzers in a stable sequence.
- The graceful-absence rule is defined: an unavailable optional analyzer is skipped with a recorded reason rather than aborting the run.
- The trivial reference analyzer is specified and emits exactly one deterministic finding that conforms to the Phase 1.1 schema.
- The interface introduces no network dependency in the offline core, and the reference analyzer is declared `offline`.

## 9. Validation and Test Approach

Document validation for this interface sub-plan runs `python3 shared/scripts/validate_planner_docs.py --root . --mode step2 --strict` and must pass. Conformance validation (proposed): a `tests/test_analyzer_interface.py` module under `python3 -m unittest discover -s tests` should assert that the reference analyzer implements the interface, returns Phase 1.1-conformant findings (reusing the Phase 1.1 conformance check), declares its capability flag, and is discoverable by the registry in deterministic order. Local smoke: `make test` runs the new module; a focused run can invoke the reference analyzer against the QB repository itself and confirm a single stable finding. CI: `make check` via `.github/workflows/validate.yml` gates the interface tests on every push to `main` and PR. Security validation: assert the reference analyzer performs no writes (the working tree is unchanged after a run) and that `scan_secrets` reports no secrets in the new artifacts. There is no live readiness here because the offline reference analyzer needs no network.

## 10. Dependencies and Sequencing

This sub-phase strictly depends on Phase 1.1: the output contract is "a list of Findings," so the schema must be frozen first. It must precede Phase 1.3, because the validator refactor's success criterion is that the refactored components implement this analyzer interface, and Phase 1.4, because the runner enumerates analyzers through this registry. A required decision is the registration mechanism's mechanics — whether analyzers self-register or are enumerated from a known location — which should be chosen to stay dependency-light per Main-Planning §1. No live credentials, network endpoints, or infrastructure are needed; the only network concern is the abstract `networked` flag, which is declared, not exercised. No human approval is required beyond accepting the interface shape.

## 11. Risks and Mitigations

- Risk: the interface leaks a write capability, blurring the analyzer/fixer separation that Main-Planning §5 depends on. Impact: an analyzer could mutate a repository, undermining the read-only audit guarantee. Mitigation: model the contract so the analyzer is handed only what it needs to read and returns findings, with a test asserting the working tree is unchanged after a reference run.
- Risk: registration uses dynamic import of arbitrary modules and becomes an injection vector against untrusted repositories. Impact: loading attacker-controlled code from a target repo during discovery. Mitigation: restrict discovery to QB-owned analyzers under `shared/`, never to code inside the repository being audited, and document that boundary explicitly.
- Risk: non-deterministic enumeration order yields unstable, hard-to-diff runs. Impact: Phase 1.4 cannot guarantee reproducible output. Mitigation: require the registry to enumerate analyzers in a stable, documented order (for example by analyzer id).
- Risk: the offline/networked flag is advisory only and a networked analyzer runs in the offline core anyway. Impact: the zero-setup promise breaks silently. Mitigation: make the runner (Phase 1.4) and policy (Phase 4) treat the flag as authoritative, and state here that the offline core must refuse to invoke a `networked` analyzer unless networking is explicitly enabled.

## 12. Desired End State

A host-neutral analyzer interface lives under `shared/` defining a read-only method contract, a repository-root-plus-config input, a list-of-Findings output, a capability descriptor with an offline/networked flag, and a deterministic registry. A single trivial reference analyzer implements the interface and emits one stable finding, proving the wiring works before any real analysis exists. A test module enforces the contract and the read-only property and is wired into `make check`. From this point, adding an analyzer in Phase 2 means writing a conformant plugin and declaring its capability, with no changes to the interface, and the Phase 1.3 validator refactor and the Phase 1.4 runner both have a fixed contract to build against.

## 13. Transition Criteria to the Next Sub-Phase

Before starting Phase 1.3 (the validator refactor), the analyzer interface, capability descriptor, and registry must be specified under `shared/` without contradictions; the trivial reference analyzer must be defined and shown to emit a Phase 1.1-conformant finding; the interface test design must cover conformance, the read-only obligation, capability declaration, and deterministic discovery; and `python3 shared/scripts/validate_planner_docs.py --root . --mode step2 --strict` must pass for this sub-plan. The interface must be agreed as the target the existing validator's extracted components will implement in Phase 1.3, so that refactor is a conformance exercise rather than an interface negotiation.
