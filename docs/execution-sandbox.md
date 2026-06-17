# Execution Sandbox Contract

The single authoritative contract for how QB confines the external commands it
executes. The engine's confinement primitives live in
`shared/scripts/command_safety.py` (and the verification seam in
`shared/scripts/verification_gate.py`); this document is the one place that states
the guarantee, the non-guarantee, the supported controls, and the fail-closed rule
that Phase 1.2–1.6 implement and test against.

## Guarantee

Every external command QB executes on the analyzed repository's behalf — in
particular each fix's verification command run through
`verification_gate.run_verification` — runs under the **requested process
confinement**. The confinement boundary is established **before** the child is
spawned, never after.

## Non-guarantee

This is **process confinement, not a filesystem or network namespace and not a
container sandbox**. QB establishes a new session/process group and conservative
POSIX resource limits; it does **not** isolate the filesystem, the network, or
syscalls. Until that boundary is complete, A2/A3 remain safe only against trusted
code (see `BASELINE.md` and `RUNBOOK.md`).

## Supported controls

The supported, deliberately stdlib-only controls are named by
`SUPPORTED_CONFINEMENT_CONTROLS = {"process_group", "resource_limits"}`:

- **`process_group`** — start the child in a new session/process group
  (`start_new_session`).
- **`resource_limits`** — apply conservative POSIX resource hardening
  (`RLIMIT_CORE = 0`) via a `preexec_fn`.

`available_confinement_controls()` reports which of those the current host can
actually establish (both on POSIX with the `resource` module; none off POSIX).

## Governing symbols

| Symbol | Role |
|---|---|
| `ConfinementSpec` | The requested-confinement value (`enabled`, `require`, `resource_limits`). |
| `SUPPORTED_CONFINEMENT_CONTROLS` | The frozen set of controls QB knows how to establish. |
| `available_confinement_controls()` | The controls establishable on this host. |
| `ConfinementUnavailable` | Raised before spawn when a required control cannot be established. |
| `may_run_repo_script()` | Gate for executing a repo-supplied script (`sandboxed_authorization`). |

## Fail-closed rule

If a **required** control cannot be established — unsupported, or supported but
unavailable on this host — `command_safety.run_command` raises
`ConfinementUnavailable` **before any child process runs**. It never silently
falls back to running unconfined. The verification seam surfaces this as
`verification confinement unavailable` and treats it as non-green, so an
unconfined run can never be recorded as a kept fix.

A companion rule governs repo-supplied scripts: `AUTO_RUN_REPO_SCRIPTS` is
`False`, and `may_run_repo_script(sandboxed_authorization=...)` must permit a
repo-provided script before it is ever executed.

## Required-vs-optional control matrix

Grounded in `available_confinement_controls()` and the frozen
`SUPPORTED_CONFINEMENT_CONTROLS` set, the controls divide into one **required**
floor and one **best-effort** hardening:

| Control | POSIX host | Non-POSIX host | Role |
|---|---|---|---|
| `process_group` | **Required** — `available_confinement_controls()` reports it, and it is the default `ConfinementSpec.require` floor | Not establishable (`available_confinement_controls()` returns `()`) | The hard confinement floor: its absence is fail-closed. |
| `resource_limits` | Best-effort — applied when the `resource` module is present | Not establishable | Conservative hardening (`RLIMIT_CORE = 0`); never the sole requirement. |

Per-host behavior:

- **POSIX** with `process_group` available: confinement is established and the
  command runs contained.
- **POSIX** missing a required control, or **non-POSIX** (no controls): the
  required `process_group` floor cannot be met, so `run_command` raises
  `ConfinementUnavailable` before spawn. QB then clamps effective autonomy below
  apply-verified (Phase 1.4) rather than running analyzed code unconfined.

Only controls in `SUPPORTED_CONFINEMENT_CONTROLS` may be required; requesting any
other control is itself a fail-closed `ConfinementUnavailable`.

## Status

Confine-by-default at the command layer is enforced through Phase 1.2–1.6: an
explicit, auditable unconfined opt-out (1.2), the flipped default (1.2), the
orchestrator wiring and evidence (1.3), the autonomy clamp when confinement is
unavailable (1.4), the tests (1.5), and the doc realignment (1.6).
