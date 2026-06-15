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

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "verify_command": list(self.verify_command) if self.verify_command else None,
            "after_exit": self.after_exit,
            "after_output": self.after_output,
            "rollback_handle": self.rollback_handle,
            "outcome": self.outcome,
            "reason": self.reason,
        }


def run_verification(command, cwd, timeout=120):
    """Run the verification command (argv); return (exit_code, combined_output)."""
    assert_argv(command)
    try:
        # The verification command runs the audited repo's own code; give it a
        # minimized environment so QB's secrets are never inherited by repo code.
        completed = _cs.run_command(command, cwd=str(cwd), timeout=timeout,
                                    env=_cs.minimal_env())
    except subprocess.TimeoutExpired:
        return _TIMEOUT_EXIT, "verification timed out"
    except Exception as exc:  # command error counts as non-green
        return 1, f"verification error: {type(exc).__name__}: {exc}"
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, output


def gate_fix(isolation, fix_plan, apply_fn, timeout=120) -> EvidenceRecord:
    """Apply one fix in isolation and keep it only if verification is green."""
    finding_id = getattr(fix_plan.finding, "id", "unknown")
    command = fix_plan.verify_command

    # Fail-closed: no runnable command means the fix can never be kept.
    if command is None:
        return EvidenceRecord(finding_id, None, None, "", isolation.capture_handle(),
                              "reverted", "no-verification-command")

    handle = isolation.capture_handle()
    apply_fn(isolation)
    exit_code, output = run_verification(command, cwd=isolation.worktree_path, timeout=timeout)
    redacted = redact(output)[:_OUTPUT_CAP]

    if exit_code == 0:
        return EvidenceRecord(finding_id, list(command), exit_code, redacted, handle,
                              "kept", "verification green")

    isolation.restore(handle)
    return EvidenceRecord(finding_id, list(command), exit_code, redacted, handle,
                          "reverted", f"verification non-green (exit {exit_code})")
