# Phase 3 Verification Acceptance Contract

## Acceptance Contract for Phase 3.2/3.3

Phase 3.2 may add only an explicit, default-off execution-confinement path. The
existing default verification behavior remains the floor: argv execution through
`command_safety.run_command`, `minimal_env()`, output redaction, timeout handling,
and disposable-worktree write isolation.

Phase 3.3 must prove the opt-in path with these negative tests:

1. **Secret-read denial**
   - Home: `tests/test_verification_gate.py`.
   - Required assertion: with confinement opted in, code running inside the
     verification boundary cannot read a synthetic secret-named host environment
     variable, and captured output remains redacted.
   - Focused target: `python3 -m unittest tests.test_verification_gate`.
2. **Boundary-escape denial**
   - Home: `tests/test_verification_gate.py` and, where filesystem setup belongs
     closer to the primitive, `tests/test_isolation_runtime.py`.
   - Required assertion: with confinement opted in, verification code cannot read
     or write outside the declared filesystem boundary.
   - Focused target: `python3 -m unittest tests.test_verification_gate`.
3. **Default-path positive control**
   - Home: `tests/test_verification_gate.py`.
   - Required assertion: with confinement off, a benign green verification still
     keeps the fix exactly as today's gate does.
   - Focused target: `python3 -m unittest tests.test_verification_gate`.
4. **Requested-but-unavailable fail-closed behavior**
   - Home: `tests/test_verification_gate.py` with any low-level establishment
     checks in `tests/test_command_safety.py`.
   - Required assertion: when confinement is requested but cannot be established,
     QB refuses or records a distinct non-silent degraded outcome and does not run
     unconfined as though the request succeeded.
   - Focused target: `python3 -m unittest tests.test_verification_gate`.

The acceptance signal for the implementation phase is not a prose claim. It is a
green focused unittest target, plus the existing `tests.test_isolation_runtime`
suite remaining green for rollback and worktree isolation.
