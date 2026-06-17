"""QB verification gate -- keep/revert decision + evidence (Phase 3.3).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
Turns QB's verify-before-done prose discipline into a non-bypassable gate:
"applied" never implies "kept". For each fix the gate captures a rollback handle
(Phase 3.2), applies the fix inside isolation, runs the pre-selected verification
command (Phase 3.1), and branches:

  * GREEN  (exit 0)            -> keep the fix, record success evidence.
  * NON-GREEN (non-zero exit,
    command error, or timeout)  -> auto-revert to the rollback handle, record
                                   failure evidence.

Fail-closed rules:
  * A finding with no runnable verification command is NEVER kept (the fix is not
    even applied; outcome is reverted with reason 'no-verification-command').
  * Captured command output is redacted of secrets BEFORE it is stored, so a
    verification command that prints a secret never persists the value.

Verification boundary:
  * Write isolation is delivered by ``isolation.py``: verification runs inside
    the disposable worktree, not the operator's checked-out tree.
  * The environment floor is always ``command_safety.minimal_env()``.
  * Execution process confinement is applied by default (``confinement=None``); a
    required control that cannot be established fails closed instead of running
    unconfined, and the orchestrator then caps autonomy below apply-verified.

The two guarantees Phase 3.4 asserts: every kept fix verified green; every
reverted fix leaves the isolation tree back at the captured handle.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from importlib import util as _import_util
from pathlib import Path

_OUTPUT_CAP = 2000
_TIMEOUT_EXIT = 124

# Floor-preservation checklist for the confine-by-default confinement extension:
# - environment minimization: run_verification always passes _cs.minimal_env().
# - worktree write isolation: gate_fix verifies inside isolation.worktree_path.
# - secret redaction: gate_fix redacts captured output before evidence storage.
# - timeout: run_verification keeps the same timeout path and _TIMEOUT_EXIT.
FLOOR_PRESERVATION_CHECKLIST = (
    "minimal_env",
    "worktree_write_isolation",
    "secret_redaction",
    "timeout",
)


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = _import_util.spec_from_file_location(module_name, path)
    module = _import_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_cs = _load_sibling("qb_command_safety", "command_safety.py")
_core = _load_sibling("qb_analyzer_core", "analyzer_core.py")
assert_argv = _cs.assert_argv


def redact(text: str) -> str:
    """Replace any secret-shaped substring with <redacted> before persistence."""
    out = text or ""
    for _name, pattern in _core.SECRET_PATTERNS:
        out = pattern.sub("<redacted>", out)
    return out


@dataclass
class EvidenceRecord:
    finding_id: str
    verify_command: list | None
    after_exit: int | None
    after_output: str
    rollback_handle: str | None
    outcome: str          # "kept" | "reverted"
    reason: str
    confinement_controls: tuple = ()   # process-confinement control names actually established

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "verify_command": list(self.verify_command) if self.verify_command else None,
            "after_exit": self.after_exit,
            "after_output": self.after_output,
            "rollback_handle": self.rollback_handle,
            "outcome": self.outcome,
            "reason": self.reason,
            # Control names only (never command output): lets a reviewer confirm
            # the verification "ran contained" from the evidence record alone.
            "confinement_controls": list(self.confinement_controls),
        }


def run_verification(command, cwd, timeout=120, confinement=None, established_controls=None):
    """Run the verification command (argv); return (exit_code, combined_output).

    The verification command runs the audited repo's own code; it gets a minimized
    environment so QB's secrets are never inherited, and confinement defaults to the
    command layer's confine-by-default (unavailable required controls fail closed).

    When ``established_controls`` (a list) is supplied, it is populated with the
    NAMES of the process-confinement controls actually established for this run --
    control names only, never command output -- so a caller can record in evidence
    that the verification "ran contained".
    """
    assert_argv(command)
    try:
        completed = _cs.run_command(command, cwd=str(cwd), timeout=timeout,
                                    env=_cs.minimal_env(), confinement=confinement)
    except subprocess.TimeoutExpired:
        return _TIMEOUT_EXIT, "verification timed out"
    except _cs.ConfinementUnavailable as exc:
        return 1, f"verification confinement unavailable: {exc}"
    except Exception as exc:  # command error counts as non-green
        return 1, f"verification error: {type(exc).__name__}: {exc}"
    if established_controls is not None:
        established_controls.extend(getattr(completed, "qb_confinement", {}).get("controls", ()))
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, output


def gate_fix(isolation, fix_plan, apply_fn, timeout=120, confinement=None) -> EvidenceRecord:
    """Apply one fix in isolation and keep it only if verification is green."""
    finding_id = getattr(fix_plan.finding, "id", "unknown")
    command = fix_plan.verify_command

    # Fail-closed: no runnable command means the fix can never be kept.
    if command is None:
        return EvidenceRecord(finding_id, None, None, "", isolation.capture_handle(),
                              "reverted", "no-verification-command")

    handle = isolation.capture_handle()
    apply_fn(isolation)
    established_controls: list = []
    exit_code, output = run_verification(
        command, cwd=isolation.worktree_path, timeout=timeout, confinement=confinement,
        established_controls=established_controls,
    )
    redacted = redact(output)[:_OUTPUT_CAP]
    controls = tuple(established_controls)

    if exit_code == 0:
        return EvidenceRecord(finding_id, list(command), exit_code, redacted, handle,
                              "kept", "verification green", confinement_controls=controls)

    isolation.restore(handle)
    return EvidenceRecord(finding_id, list(command), exit_code, redacted, handle,
                          "reverted", f"verification non-green (exit {exit_code})",
                          confinement_controls=controls)
