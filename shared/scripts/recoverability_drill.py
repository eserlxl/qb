"""Whole-run recoverability drill (Phase 7.1).

Proves a run is fully reversible -- capture a baseline, mutate the tree, undo the
whole run, and confirm the tree is clean at the captured baseline -- and returns a
structured, redaction-safe evidence record. Reuses ``release_gate``'s
capture/rollback/baseline_clean primitives rather than reimplementing rollback, so
the drill and the live gate share one rollback path. Canonical host-neutral QB IP
under ``shared/`` (standard library only).

The structured result feeds the production gate's ``rollback_drill_passed`` signal
and is persisted (redacted) into the QB-Audit store as an audit-trail record.
"""

from __future__ import annotations

import json
import sys
from importlib import util as _import_util
from pathlib import Path


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = _import_util.spec_from_file_location(module_name, path)
    module = _import_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_rg = _load_sibling("qb_release_gate", "release_gate.py")
_store = _load_sibling("qb_run_store", "run_store.py")

RECOVERABILITY_EVIDENCE_SCHEMA_VERSION = 1
RECOVERABILITY_EVIDENCE_FILENAME = "recoverability.json"
_SCRATCH = ".qb-recoverability-drill.scratch"


def _default_mutate(repo_root) -> None:
    """A throwaway tree change so the drill exercises capture -> mutate -> rollback."""
    (Path(repo_root) / _SCRATCH).write_text("recoverability drill scratch\n", encoding="utf-8")


def run_drill(repo_root, run_id, mutate_fn=None) -> dict:
    """Capture -> mutate -> whole-run rollback -> assert clean-at-baseline, via
    ``release_gate``. Returns a structured, redaction-safe evidence record: the
    namespaced reversal ref and the clean/pass result, never the raw baseline sha
    value (only its length, as ref shape). ``passed`` is the drill verdict."""
    mutate = mutate_fn or _default_mutate
    handle = _rg.capture_baseline(repo_root, run_id)
    try:
        mutate(repo_root)
        _rg.rollback_run(repo_root, handle)
        clean = _rg.baseline_clean(repo_root, handle)
    finally:
        _rg.release_baseline(repo_root, handle)
    return {
        "schema_version": RECOVERABILITY_EVIDENCE_SCHEMA_VERSION,
        "run_id": run_id,
        "baseline_ref": handle["ref"],
        "baseline_sha_len": len(handle["sha"]),
        "baseline_clean": bool(clean),
        "passed": bool(clean),
    }


def persist_evidence(record, output_dir) -> Path:
    """Write a recoverability evidence record into the QB-Audit store, deterministically
    (sorted keys) and redacted via run_store.redact so no secret value is ever emitted.
    Returns the written path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    redacted = _store.redact(record)
    path = out / RECOVERABILITY_EVIDENCE_FILENAME
    path.write_text(json.dumps(redacted, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def read_evidence(output_dir) -> dict:
    """Read back the recoverability evidence record, or {} when absent."""
    path = Path(output_dir) / RECOVERABILITY_EVIDENCE_FILENAME
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def run_and_persist(repo_root, run_id, output_dir, mutate_fn=None) -> dict:
    """Run the drill and persist its (redacted) evidence record; return the record."""
    record = run_drill(repo_root, run_id, mutate_fn)
    persist_evidence(record, output_dir)
    return record
