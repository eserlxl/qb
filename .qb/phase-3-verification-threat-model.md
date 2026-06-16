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
