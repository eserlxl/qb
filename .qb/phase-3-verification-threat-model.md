# Phase 3 Verification Threat Model

## Threat Boundary

QB's verification subprocess is allowed to run only the gate-selected argv inside
the isolated repository worktree. The trusted floor is:

| Asset | Trust Level | Current Surface |
| --- | --- | --- |
| Gate-selected argv vector | Trusted input selected by QB before execution | `shared/scripts/verification_gate.py` calls `run_verification(command, cwd=...)` and rejects non-argv forms through `command_safety.assert_argv`. |
| Minimal environment | Trusted reduced environment | `shared/scripts/verification_gate.py` passes `env=_cs.minimal_env()` through `command_safety.run_command`. |
| Isolated worktree | Trusted write boundary for fix attempts | `shared/scripts/isolation.py` creates a disposable git worktree and rollback handle. |
| Target repository code and files | Untrusted | The verification command executes code from the repository under audit. |
| Host environment and secrets | Protected host asset | Must not be inherited by the verification subprocess except for `minimal_env()` allowlisted keys. |
| Operator working tree | Protected host asset | Must not be written by fix attempts; writes belong in the disposable isolation worktree. |
| Broader filesystem and network | Protected host asset | Not covered by the current floor; future execution confinement must address this explicitly. |

The existing floor is deliberately narrow. `minimal_env()` reduces inherited
environment variables, and `isolation.py` provides write isolation plus rollback
for fix attempts. Those guarantees are already delivered and are not re-planned
here. The remaining Phase 3 question is execution confinement for the untrusted
verification subprocess itself: what it can read, spawn, contact, or consume
while it runs.

## Residual Risk Register

The following risks remain after the existing floor. Each entry is intentionally
phrased as a test target for Phase 3.3 rather than as a restatement of delivered
write isolation or environment minimization.

1. **Environment variable read of non-stripped variables**
   - Likelihood: medium; impact: high when the host environment carries tokens
     outside the current allowlist or future allowlist additions.
   - Not mitigated by the current floor: `minimal_env()` strips most variables,
     but the verification subprocess still receives allowlisted variables and
     has no execution boundary preventing process introspection beyond that
     reduced environment.
2. **Out-of-worktree file read or write**
   - Likelihood: medium; impact: high for host files readable by the operator.
   - Not mitigated by the current floor: `isolation.py` confines QB's own writes
     to a disposable worktree, but untrusted code executed by the verifier can
     still attempt ordinary filesystem access outside that worktree.
3. **Child-process spawn**
   - Likelihood: high for arbitrary test commands; impact: medium to high when
     spawned tools inherit filesystem or network reach.
   - Not mitigated by the current floor: `run_command()` uses argv form and no
     shell for QB's launch, but code inside the target repo can spawn additional
     children unless the execution boundary blocks or limits that behavior.
4. **Network egress**
   - Likelihood: medium; impact: high when verification code can exfiltrate
     host metadata or downloaded artifacts.
   - Not mitigated by the current floor: neither `minimal_env()` nor git
     worktree isolation disables network access for the verification process.
5. **Resource exhaustion**
   - Likelihood: medium; impact: medium to high through CPU, memory, process, or
     disk pressure against the operator host.
   - Not mitigated by the current floor: `verification_gate.py` applies a
     timeout, but the current path does not impose memory, process-count, file
     size, or network-resource limits.

## Mechanism Options Matrix

| Option | Stdlib-only | Deterministic | Fail-closed shape | Cross-platform | Default-off opt-in | Pros | Cons / invariant conflict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Process confinement with stdlib primitives (`resource`, process groups, cwd/env hardening, explicit refusal when unsupported) | Preserved on POSIX for available primitives; Windows support must be feature-gated | High when the selected primitive set is reported in the outcome | Straightforward: if a requested primitive is unavailable, refuse or record a distinct degraded outcome | Partial; some primitives are POSIX-only | Natural extension of `command_safety.run_command` | Keeps QB dependency-free, layers onto `minimal_env()`, and can preserve existing argv/timeout semantics | Does not fully solve filesystem or network isolation by itself; capability varies by OS |
| OS namespaces (`unshare` for user/mount/pid/net) | Broken if shelling out to host tools; no stdlib namespace API | Medium; host kernel and permissions vary | Must refuse when namespace creation is unavailable or denied | Linux-specific | Possible but host-dependent | Stronger network and filesystem boundary than process limits | Breaks cross-platform expectations and depends on host namespace availability outside Python stdlib |
| Container-based confinement | Broken; requires Docker/Podman or equivalent | Medium; daemon state and image availability vary | Must refuse when runtime/image is unavailable | Runtime-dependent, not universal | Possible but heavyweight | Strong boundary when correctly configured | Violates dependency-free core, introduces image/runtime management, and risks network or daemon policy drift |

Recommendation pressure: the only option that can preserve QB's current
dependency-free core is a stdlib process-confinement wrapper with explicit
capability reporting and fail-closed behavior. Namespace or container approaches
may be stronger security mechanisms, but they conflict with the stdlib-only
invariant enforced by `shared/scripts/least_privilege.py` and should not become
the default engine path without a deliberate product decision.

## Decision

Selected opt-in mechanism: implement a stdlib process-confinement wrapper as
an explicit extension of `command_safety.run_command`, defaulting off and
reporting which controls were actually established. The initial wrapper should
preserve argv form, `cwd`, timeout, `minimal_env()`, output capture, and redaction
semantics. On hosts where a requested control is unavailable, the wrapper should
not silently execute unconfined.

Rationale: this is the only candidate that keeps the dependency-free core
intact, composes with the current safe-exec primitive, and gives Phase 3.3 a
testable fail-closed branch. It is weaker than namespace or container isolation,
so the result must be described as opt-in process confinement, not a full sandbox.

Fail-closed policy: requested confinement that cannot be established returns a
distinct non-green result and skips unconfined execution. There is no interactive
human-confirmation gate in the automated path; the recorded decision above is the
implementation contract for Phase 3.2. In particular, `qb-plan auto` remains a
non-interactive planning command: after Step 2 has produced sub-plans, Step 3.5
must generate and validate `.qb/plan.md` automatically rather than waiting for a
human decision.
