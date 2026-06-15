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
from fnmatch import fnmatch
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
_release = _load_sibling("qb_release_gate", "release_gate.py")

ActionDescriptor = _policy.ActionDescriptor
evaluate = _policy.evaluate

_LEVEL_RANK = {A0: 0, A1: 1, A2: 2, A3: 3}


def _clamp_level(declared: str, earned: str) -> str:
    """The effective level: a declared level capped by what telemetry has EARNED.

    ``release_gate.permitted_autonomy`` returns A1 or A2 (A2 only with sufficient
    precision + fix safety; no/insufficient telemetry => A1). So a declared A2/A3 is
    clamped to A1 until promotion is earned. A3's *deliver* capability is gated
    separately by the explicit ``enable_a3`` flag, not by telemetry.
    """
    return declared if _LEVEL_RANK.get(declared, 0) <= _LEVEL_RANK.get(earned, 1) else earned


def _evidence_path(finding) -> str:
    evidence = getattr(finding, "evidence", "") or ""
    return evidence.split(":", 1)[0]


def _promote(isolation, repo_root):
    """The sole working-tree write path: apply isolation's verified changes to repo_root.

    Promotion is driven off ``git status --porcelain -z --no-renames``: ``--no-renames``
    decomposes a rename into a delete + add (so there is no fragile rename-pair parse),
    ``-z`` is NUL-delimited (no path quoting), and the two-char XY status distinguishes
    deletions from copies. The previous ``line[3:].strip()`` + ``is_file()`` approach
    silently dropped deletions, mangled renames into a single garbage path, and aborted
    mid-loop on a non-UTF-8 file -- each leaving a partially-applied working tree.

    Fail closed on scope: a change is promoted only when it is contained under
    ``repo_root`` AND (when the isolation carries a write allowlist) matches it. Anything
    else -- a fix write outside policy, or an incidental verification byproduct such as
    ``__pycache__`` left in the disposable worktree -- is skipped and never reaches the
    working tree. Content round-trips as bytes so binary files survive.
    """
    repo_root = Path(repo_root)
    wt = Path(isolation.worktree_path)
    status = _cs.run_command(
        ["git", "-C", str(wt), "status", "--porcelain", "-z", "--no-renames"])
    allowlist = getattr(isolation, "allowlist", None)
    promoted = []
    for entry in status.stdout.split("\0"):
        if len(entry) < 4:
            continue
        xy, rel = entry[:2], entry[3:]
        if not rel:
            continue
        # Confine to the allowlist (when set) and to repo_root before any write.
        if allowlist is not None and not any(fnmatch(rel, g) for g in allowlist):
            continue
        if not _cs.is_within(repo_root, rel):
            continue
        target = repo_root / rel
        if "D" in xy:                       # deletion (incl. a rename's old side)
            if target.is_file() or target.is_symlink():
                target.unlink()
                promoted.append(rel)
            continue
        source = wt / rel
        if not source.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())  # bytes: binary-safe round-trip
        promoted.append(rel)
    return promoted


def run_finding(policy, repo_root, fix_plan, apply_fn, *, run_id="run", enable_a3=False,
                review=None, telemetry=None) -> dict:
    """The single enforcement chokepoint for one finding's fix attempt.

    The declared ``policy.autonomy_level`` is clamped by the EARNED ceiling
    (``release_gate.permitted_autonomy`` over prior-run ``telemetry``): promotion to
    the working tree requires the level to be earned, not merely declared. With no
    telemetry the ceiling is A1, so a cold-start A2/A3 run isolates and verifies but
    promotes nothing.
    """
    declared = policy.autonomy_level
    earned = _release.permitted_autonomy(telemetry or {})
    level = _clamp_level(declared, earned)
    finding = fix_plan.finding
    action = ActionDescriptor(
        action_kind="fix",
        category=getattr(finding, "category", ""),
        severity=getattr(finding, "severity", ""),
        confidence=getattr(finding, "confidence", "low"),
        target_path=_evidence_path(finding),
    )
    result = {"level": level, "declared_level": declared, "earned_ceiling": earned,
              "outcome": None, "reason": None, "promoted": [], "changeset": None, "evidence": None}

    # A0 is report-only: never open isolation, never write. (Only a declared A0 lands
    # here; the earned ceiling is never below A1, so it never forces report-only.)
    if level == A0:
        result["outcome"] = "report-only"
        result["reason"] = "autonomy-report-only"
        return result

    verdict = evaluate(policy, action)
    if not verdict.allowed:
        result["outcome"] = "blocked"          # block, never warn; no side effect
        result["reason"] = verdict.reason
        return result

    # Promotion caps come from the EFFECTIVE (clamped) level; the A3 deliver/changeset
    # capability is an explicit declaration (declared A3 + enable_a3), not telemetry-earned.
    caps = SIDE_EFFECT_MATRIX.get(level, SIDE_EFFECT_MATRIX[A0])
    changeset_capable = SIDE_EFFECT_MATRIX.get(declared, SIDE_EFFECT_MATRIX[A0])["changeset"]
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
        if result["outcome"] == "kept" and caps["promote"] and changeset_capable and enable_a3:
            result["changeset"] = {"files": list(result["promoted"]),
                                   "commit_permitted": bool(policy.allow_commit)}
    finally:
        isolation.teardown()
    return result
