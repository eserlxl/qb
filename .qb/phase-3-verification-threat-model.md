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
