"""QB autonomy enforcement seam (Phase 4.2).

Canonical host-neutral QB IP under ``shared/`` (Python standard library + git).
Turns the Phase-4.1 autonomy-level field into enforced runtime behavior. Every
working-tree mutation flows through ONE chokepoint (``run_finding``), so the level
check cannot be bypassed. Out-of-policy actions are BLOCKED, not warned.

Per-level side-effect matrix (the working tree is the protected resource):
  A0 report-only     -- no isolation, no writes anywhere.
  A1 propose         -- writes confined to throwaway isolation; working tree
                        byte-identical before and after.
  A2 apply-verified  -- a fix is promoted into the working tree ONLY after the
                        verification gate keeps it; everything else is reverted.
  A3 deliver         -- A2 plus a reviewable changeset, assembled ONLY when an
                        explicit enable flag is set; commit/push/PR remain gated
                        by the Phase-4.1 policy booleans (not executed here).

Promotion (the only path that writes the working tree) runs at A2+ only. Demotion
is the gate's auto-revert. Both are explicit and reversible.
"""

from __future__ import annotations

import sys
from importlib import util as _import_util
from pathlib import Path

A0, A1, A2, A3 = "A0", "A1", "A2", "A3"

SIDE_EFFECT_MATRIX = {
    A0: {"isolation": False, "promote": False, "changeset": False},
    A1: {"isolation": True, "promote": False, "changeset": False},
    A2: {"isolation": True, "promote": True, "changeset": False},
    A3: {"isolation": True, "promote": True, "changeset": True},
}


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = _import_util.spec_from_file_location(module_name, path)
    module = _import_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_policy = _load_sibling("qb_policy", "policy.py")
_isolation = _load_sibling("qb_isolation", "isolation.py")
_gate = _load_sibling("qb_verification_gate", "verification_gate.py")
_cs = _load_sibling("qb_command_safety", "command_safety.py")

ActionDescriptor = _policy.ActionDescriptor
evaluate = _policy.evaluate


def _evidence_path(finding) -> str:
    evidence = getattr(finding, "evidence", "") or ""
    return evidence.split(":", 1)[0]


def _promote(isolation, repo_root):
    """The sole working-tree write path: copy isolation's changes into repo_root."""
    repo_root = Path(repo_root)
    status = _cs.run_command(["git", "-C", str(isolation.worktree_path), "status", "--porcelain"])
    promoted = []
    for line in status.stdout.splitlines():
        rel = line[3:].strip()
        if not rel:
            continue
        source = isolation.worktree_path / rel
        if not source.is_file():
            continue
        target = repo_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        promoted.append(rel)
    return promoted


def run_finding(policy, repo_root, fix_plan, apply_fn, *, run_id="run", enable_a3=False, review=None) -> dict:
    """The single enforcement chokepoint for one finding's fix attempt."""
    level = policy.autonomy_level
    finding = fix_plan.finding
    action = ActionDescriptor(
        action_kind="fix",
        category=getattr(finding, "category", ""),
        severity=getattr(finding, "severity", ""),
        confidence=getattr(finding, "confidence", "low"),
        target_path=_evidence_path(finding),
    )
    result = {"level": level, "outcome": None, "reason": None,
              "promoted": [], "changeset": None, "evidence": None}

    # A0 is report-only: never open isolation, never write.
    if level == A0:
        result["outcome"] = "report-only"
        result["reason"] = "autonomy-report-only"
        return result

    verdict = evaluate(policy, action)
    if not verdict.allowed:
        result["outcome"] = "blocked"          # block, never warn; no side effect
        result["reason"] = verdict.reason
        return result

    caps = SIDE_EFFECT_MATRIX.get(level, SIDE_EFFECT_MATRIX[A0])
    isolation = _isolation.Isolation(
        repo_root, level=level, run_id=run_id,
        allowlist=list(policy.write_allowlist) or None,
    ).open()
    try:
        record = _gate.gate_fix(isolation, fix_plan, apply_fn)
        result["evidence"] = record.to_dict()
        result["outcome"] = record.outcome
        result["reason"] = record.reason
        if record.outcome == "kept" and caps["promote"]:
            # Phase 4.4 cross-review gate composes here, before any working-tree write.
            decision = review(finding) if review is not None else {"promote": True, "reason": "no-review"}
            if decision["promote"]:
                result["promoted"] = _promote(isolation, repo_root)
            else:
                result["outcome"] = "blocked"          # demoted by review; isolation discarded on teardown
                result["reason"] = decision["reason"]
        if result["outcome"] == "kept" and caps["changeset"] and enable_a3:
            result["changeset"] = {"files": list(result["promoted"]),
                                   "commit_permitted": bool(policy.allow_commit)}
    finally:
        isolation.teardown()
    return result
