"""QB self-audit reconciliation (Phase 7.3).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
Closes the self-audit loop: it loads the QB-audits-QB findings inventory
(``.qb/audit/findings.jsonl``, written by ``run_store``) and the committed
accepted-findings register (``docs/accepted-findings.md``, via
``accepted_findings``), reconciles them through ``production_gate.self_audit_clean``
/ ``unaccepted_findings``, and emits the ``self_audit_clean`` conjunct boolean plus
the list of unaccepted finding ids the gate must still account for.

This is the bridge between the headless self-audit run (Phase 7.3) and the
production gate's ``self_audit_clean`` signal (Phase 7.4): the conjunct is True
only when every finding QB raised about itself is either fixed (absent from the
inventory) or explicitly accepted in the register -- fail-closed by construction,
since an absent register accepts nothing.
"""

from __future__ import annotations

import json
import sys
from importlib import util as _import_util
from pathlib import Path

FINDINGS_FILENAME = "findings.jsonl"


def _load_sibling(module_name, filename):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = _import_util.spec_from_file_location(module_name, path)
    module = _import_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_pg = _load_sibling("qb_production_gate", "production_gate.py")
_accepted = _load_sibling("qb_accepted_findings", "accepted_findings.py")


def load_findings(audit_dir) -> list:
    """Load the self-audit findings inventory (one JSON object per line). A missing
    inventory yields an empty list; a malformed line is skipped rather than crashing
    the reconciliation."""
    path = Path(audit_dir) / FINDINGS_FILENAME
    if not path.is_file():
        return []
    findings = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            findings.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return findings


def reconcile(audit_dir, repo_root) -> dict:
    """Reconcile the self-audit inventory against the accepted-findings register.

    Returns the ``self_audit_clean`` conjunct boolean and the sorted list of
    unaccepted finding ids (those neither fixed nor accepted). Fail-closed: an
    absent register accepts nothing, so any finding QB raised about itself that is
    not explicitly accepted keeps the conjunct False.
    """
    findings = load_findings(audit_dir)
    accepted = _accepted.load_accepted_ids(repo_root)
    clean = _pg.self_audit_clean(findings, accepted_ids=accepted)
    unaccepted = _pg.unaccepted_findings(findings, accepted_ids=accepted)
    unaccepted_ids = sorted(
        f.get("id") for f in unaccepted if isinstance(f, dict) and f.get("id"))
    return {
        "self_audit_clean": clean,
        "findings_total": len(findings),
        "accepted_total": len(accepted),
        "unaccepted_ids": unaccepted_ids,
    }
