"""QB backup/rollback drills + release gates (Phase 7.2).

Canonical host-neutral QB IP under ``shared/`` (Python standard library + git).
Makes recoverability a tested property and gates dangerous autonomy on measured
evidence.

Whole-run recoverability (distinct from the Phase-3 per-fix revert):
  * capture_baseline -- before the first write, record HEAD and a namespaced
    ref (refs/qb-baseline/<run_id>) that cannot collide with user branches.
  * rollback_run -- a single operation that resets the tree to the baseline and
    cleans untracked files, returning the repo to its exact pre-run state.
  * run_rollback_drill -- a deterministic fixture drill: capture, mutate, undo,
    assert a clean tree at the baseline ref.

Release gates (read Phase-7.1 telemetry; fail-closed):
  * precision_gate -- denies auto-apply below PRECISION_FLOOR.
  * fix_safety_gate -- denies auto-apply unless every kept fix verified green.
  * permitted_autonomy -- composes both into the max permitted level; with no
    recent data it denies auto-apply (A1 max), never defaults open.
"""

from __future__ import annotations

import json
import sys
from importlib import util as _import_util
from pathlib import Path

REVERSAL_REF_PREFIX = "refs/qb-baseline/"


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
_telemetry = _load_sibling("qb_telemetry", "telemetry.py")
PRECISION_FLOOR = _telemetry.PRECISION_FLOOR


# QB's own git is a trusted internal operation, not analyzed repo code; it runs
# under the sanctioned unconfined opt-out so baseline/rollback keep working even
# where execution confinement is unavailable (confine-by-default targets the
# analyzed code's verification command, not QB's git).
_TRUSTED_GIT = _cs.unconfined("QB internal git operation")


def _git(repo, *args):
    return _cs.run_command(["git", "-C", str(repo), *args], confinement=_TRUSTED_GIT)


class RollbackError(Exception):
    pass


# --- whole-run recoverability -------------------------------------------------
def capture_baseline(repo_root, run_id) -> dict:
    """Snapshot the pre-run state: HEAD sha + a namespaced reversal ref."""
    head = _git(repo_root, "rev-parse", "HEAD")
    if head.returncode != 0:
        raise RollbackError("cannot capture baseline: not a git repo or no commits")
    sha = head.stdout.strip()
    ref = f"{REVERSAL_REF_PREFIX}{run_id}"
    if _git(repo_root, "update-ref", ref, sha).returncode != 0:
        raise RollbackError(f"cannot create reversal ref: {ref}")
    return {"sha": sha, "ref": ref}


def rollback_run(repo_root, handle) -> None:
    """Whole-run undo: reset to the baseline and remove untracked files."""
    _git(repo_root, "reset", "--hard", handle["sha"])
    _git(repo_root, "clean", "-fd")


def baseline_clean(repo_root, handle) -> bool:
    """True iff the tree is clean and HEAD is exactly the captured baseline."""
    status = _git(repo_root, "status", "--porcelain").stdout.strip()
    head = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    return status == "" and head == handle["sha"]


def release_baseline(repo_root, handle) -> None:
    _git(repo_root, "update-ref", "-d", handle["ref"])


def run_rollback_drill(repo_root, run_id, mutate_fn) -> bool:
    """Capture -> mutate -> undo -> assert clean at baseline. Returns True on pass."""
    handle = capture_baseline(repo_root, run_id)
    try:
        try:
            mutate_fn(repo_root)
        except Exception:
            rollback_run(repo_root, handle)
            return False
        rollback_run(repo_root, handle)
        return baseline_clean(repo_root, handle)
    finally:
        release_baseline(repo_root, handle)


# --- release gates (consume Phase-7.1 telemetry; fail-closed) ------------------
def _quality(telemetry) -> dict:
    """The quality block, coerced to a dict. Malformed telemetry (a hand-edited or
    corrupt telemetry.json with quality=null, a non-dict, or a non-numeric estimate)
    must fail the gates closed, never crash or pass."""
    if not isinstance(telemetry, dict):
        return {}
    quality = telemetry.get("quality")
    return quality if isinstance(quality, dict) else {}


def precision_gate(telemetry: dict, floor: float = PRECISION_FLOOR):
    precision = _quality(telemetry).get("precision_estimate")
    # A non-numeric (or boolean) estimate is treated as missing -> deny, not a crash.
    if not isinstance(precision, (int, float)) or isinstance(precision, bool):
        return (False, "no-precision-data")
    if precision < floor:
        return (False, f"precision-below-floor={precision}<{floor}")
    return (True, "precision-ok")


def fix_safety_gate(telemetry: dict):
    if not _quality(telemetry).get("fix_safety_ok", False):
        return (False, "fix-safety-breach")
    return (True, "fix-safety-ok")


def permitted_autonomy(telemetry: dict, floor: float = PRECISION_FLOOR) -> str:
    """Max autonomy a context has earned (A0/A1/A2), composing both gates."""
    precision_ok, _ = precision_gate(telemetry, floor)
    safety_ok, _ = fix_safety_gate(telemetry)
    if precision_ok and safety_ok:
        return "A2"
    return "A1"


_AUTONOMY_RANK = {"A0": 0, "A1": 1, "A2": 2, "A3": 3}


def most_restrictive(*levels) -> str:
    """The most restrictive (lowest-rank) of the given autonomy levels.

    Composes the independent autonomy sources of truth -- the declared level, the
    telemetry-earned ceiling (``permitted_autonomy``), and the sandbox-availability
    clamp -- into one effective level so the lowest always wins and no single source
    can raise the effective autonomy above another's cap.
    """
    return min(levels, key=lambda level: _AUTONOMY_RANK.get(level, 0))


# --- release-gate authorization evidence record (Phase 7.2) -------------------
# The earned-autonomy decision is persisted as a redacted, reproducible audit
# record: the permitted level plus the gate reason tokens (precision-ok /
# precision-below-floor=... / no-precision-data, and fix-safety-ok / fix-safety-
# breach), never a raw telemetry value. Mirrors recoverability_drill's record
# pattern so the audit trail proves the autonomy decision without persisting any
# secret value (redaction is via run_store.redact before write).
AUTHORIZATION_EVIDENCE_SCHEMA_VERSION = 1
AUTHORIZATION_EVIDENCE_FILENAME = "release-authorization.json"

_store = _load_sibling("qb_run_store", "run_store.py")


def authorization_record(telemetry: dict, floor: float = PRECISION_FLOOR) -> dict:
    """Build the redaction-safe release-gate authorization record: the permitted
    autonomy level plus the precision/fix-safety gate reasons. Carries no raw
    telemetry value -- only the level and the engine's reason tokens."""
    precision_ok, precision_reason = precision_gate(telemetry, floor)
    fix_safety_ok, fix_safety_reason = fix_safety_gate(telemetry)
    return {
        "schema_version": AUTHORIZATION_EVIDENCE_SCHEMA_VERSION,
        "permitted_autonomy": permitted_autonomy(telemetry, floor),
        "precision_ok": bool(precision_ok),
        "precision_reason": precision_reason,
        "fix_safety_ok": bool(fix_safety_ok),
        "fix_safety_reason": fix_safety_reason,
    }


def persist_authorization(record, output_dir) -> Path:
    """Write the authorization record into the .qb/audit store deterministically
    (sorted keys) and redacted via run_store.redact, so no secret value is ever
    emitted. Returns the written path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    redacted = _store.redact(record)
    path = out / AUTHORIZATION_EVIDENCE_FILENAME
    path.write_text(json.dumps(redacted, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def read_authorization(output_dir) -> dict:
    """Read back the release-gate authorization record, or {} when absent."""
    path = Path(output_dir) / AUTHORIZATION_EVIDENCE_FILENAME
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
