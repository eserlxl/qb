"""QB production-gate signal assembly (Phase 7.4, roadmap finale).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
``production_gate.py`` takes six literal booleans; this module DERIVES those six
conjuncts from their real evidence sources and calls ``production_gate`` to produce
the single authorization decision the finale is named for:

  * telemetry_emitted     -- a per-run telemetry record is present (7.1).
  * rollback_drill_passed -- the persisted recoverability evidence record passed (7.1).
  * killswitch_proven     -- the budget engine's kill-switch halts at a safe
                             checkpoint with the documented exit code, proven live (7.1).
  * least_privilege_ok    -- the write/network/script least-privilege invariants hold (7.3).
  * supply_chain_ok       -- manifest-anchored (Phase 6.1): the engine's dependency-free
                             core AND the QB release manifest verifying clean (a
                             well-formed semver VERSION over a non-empty tree -- the
                             same invariant scripts/release-manifest.py --check pins).
                             Fail-closed: any verification error denies the conjunct.
  * self_audit_clean      -- the QB-audits-QB reconciliation is clean (7.3).

Every derivation is fail-closed: a missing record, an unreadable signal, or any
error yields False for that conjunct, so the composite gate can only pass when
every signal is positively established. The release-gate earned autonomy (7.2) is
surfaced alongside the decision but is NOT one of the six conjuncts (it clamps
autonomy; it does not gate operation).
"""

from __future__ import annotations

import argparse
import re
import sys
from importlib import util as _import_util
from pathlib import Path

# A well-formed manifest pins a semver VERSION (mirrors release-manifest.py --check).
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")

# Entrypoint exit-code contract (fail-closed: a crash never reports passed):
#   0 GATE_PASSED  -- every conjunct holds; autonomous operation authorized.
#   1 GATE_DENIED  -- at least one conjunct failed; named in the printed failures.
#   2 GATE_ERROR   -- an internal error occurred assembling the decision.
GATE_PASSED = 0
GATE_DENIED = 1
GATE_ERROR = 2


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
_store = _load_sibling("qb_run_store", "run_store.py")
_recov = _load_sibling("qb_recoverability_drill", "recoverability_drill.py")
_reconcile = _load_sibling("qb_self_audit_reconcile", "self_audit_reconcile.py")
_release = _load_sibling("qb_release_gate", "release_gate.py")
_lp = _load_sibling("qb_least_privilege", "least_privilege.py")


def telemetry_emitted(audit_dir) -> bool:
    """A schema-valid per-run telemetry record is present in the run store."""
    return bool(_store.RunStore(Path(audit_dir)).read_telemetry())


def rollback_drill_passed(audit_dir) -> bool:
    """The persisted recoverability evidence record exists and recorded a pass."""
    return _recov.read_evidence(audit_dir).get("passed") is True


def prove_killswitch() -> bool:
    """Prove the kill-switch halts at a safe checkpoint (the Phase 7.1 drill).

    A triggered kill-switch stops ``budget.run_session`` BEFORE any fix unit is
    consumed, with the documented kill-stop exit code and nothing half-applied. The
    kill fires at the loop's safe checkpoint before the first unit, so the (unused)
    item is never dereferenced -- no git/isolation is needed to prove the halt.
    Fail-closed: any error means the kill-switch is NOT proven.
    """
    try:
        budget = _load_sibling("qb_budget", "budget.py")
        policy_mod = _load_sibling("qb_policy", "policy.py")
        policy = policy_mod.default_policy()
        ks = budget.KillSwitch()
        ks.trigger()
        results, report = budget.run_session(policy, ".", [(None, None)], killswitch=ks)
        return (report.trigger == "kill"
                and report.exit_code == budget.KILL_STOP_EXIT
                and results == [])
    except Exception:
        return False


def least_privilege_ok(repo_root) -> bool:
    """The least-privilege invariants hold: writes default-deny (empty allowlist
    denies all; a traversal path is refused), no implicit network egress, and QB
    never auto-runs a repo-supplied script."""
    no_autorun = _lp.AUTO_RUN_REPO_SCRIPTS is False
    empty_denies = _lp.write_allowed(repo_root, "any.txt", []) is False
    traversal_denied = _lp.write_allowed(repo_root, "../escape.txt", ["*"]) is False
    offline_runs = _lp.network_allowed(analyzer_is_offline=True, allow_networked=False) is True
    no_implicit_egress = _lp.network_allowed(analyzer_is_offline=False, allow_networked=False) is False
    return bool(no_autorun and empty_denies and traversal_denied
                and offline_runs and no_implicit_egress)


def _qb_root(scripts_dir: Path):
    """The QB package root anchoring the release manifest: the nearest ancestor of the
    engine scripts dir that holds a VERSION file. None if none is found (fail-closed)."""
    for parent in (scripts_dir, *scripts_dir.parents):
        if (parent / "VERSION").is_file():
            return parent
    return None


def _manifest_verifies(scripts_dir: Path) -> bool:
    """The release-manifest integrity invariant, reimplemented stdlib-only so the shared
    engine never imports the repo-root scripts/release-manifest.py: the QB package root
    pins a well-formed semver VERSION over a non-empty tree -- the same well-formed-manifest
    property scripts/release-manifest.py --check enforces (which remains the authoritative
    on-disk SHA-256 inventory). Fail-closed: returns False if the root or VERSION is
    missing/malformed."""
    root = _qb_root(scripts_dir)
    if root is None:
        return False
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not _SEMVER_RE.match(version):
        return False
    return any(p.is_file() for p in root.iterdir())


def supply_chain_ok(scripts_dir=None) -> bool:
    """Manifest-anchored supply-chain signal (Phase 6.1): the engine's dependency-free
    core (no non-stdlib import in any shared module) AND the QB release manifest verifying
    clean (a well-formed semver VERSION over a non-empty tree -- the invariant
    scripts/release-manifest.py --check pins). Fail-closed: any verification error returns
    False (never raises), and it never returns True on a placeholder."""
    scripts_dir = Path(scripts_dir) if scripts_dir is not None else Path(__file__).resolve().parent
    try:
        if _lp.assert_dependency_free_core(scripts_dir) != []:
            return False
        return _manifest_verifies(scripts_dir)
    except Exception:
        return False


def self_audit_clean(audit_dir, repo_root) -> bool:
    """The QB-audits-QB reconciliation is clean (every finding fixed or accepted)."""
    return bool(_reconcile.reconcile(audit_dir, repo_root)["self_audit_clean"])


def assemble_signals(audit_dir, repo_root, scripts_dir=None) -> dict:
    """Derive the six production-gate conjuncts from their real evidence sources."""
    return {
        "telemetry_emitted": telemetry_emitted(audit_dir),
        "rollback_drill_passed": rollback_drill_passed(audit_dir),
        "least_privilege_ok": least_privilege_ok(repo_root),
        "supply_chain_ok": supply_chain_ok(scripts_dir),
        "killswitch_proven": prove_killswitch(),
        "self_audit_clean": self_audit_clean(audit_dir, repo_root),
    }


def permitted_autonomy(audit_dir) -> str:
    """The earned autonomy ceiling (release gate, 7.2) over the recorded telemetry --
    surfaced alongside the decision; it clamps autonomy, it is not a gate conjunct."""
    telemetry = _store.RunStore(Path(audit_dir)).read_telemetry()
    return _release.permitted_autonomy(telemetry)


def gate_decision(audit_dir, repo_root, scripts_dir=None) -> dict:
    """Assemble the six signals and run the composite production gate, returning the
    gate result augmented with the raw signals and the earned autonomy ceiling."""
    signals = assemble_signals(audit_dir, repo_root, scripts_dir)
    result = _pg.production_gate(**signals)
    result["signals"] = signals
    result["permitted_autonomy"] = permitted_autonomy(audit_dir)
    return result


def main(argv=None) -> int:
    """CLI entrypoint: assemble the six signals and report the production-gate
    authorization decision with a documented exit code. Fail-closed: an internal
    error returns GATE_ERROR, never a passed decision."""
    parser = argparse.ArgumentParser(
        description="Assemble the six production-gate signals and report the authorization decision.")
    parser.add_argument("--root", default=".",
                        help="Repository root (for least-privilege + the self-audit register).")
    parser.add_argument("--out", default=None,
                        help=f".qb/audit store directory; default <root>/{_store.OUTPUT_DIR_NAME}.")
    parser.add_argument("--scripts-dir", default=None,
                        help="Engine scripts dir for the supply-chain check; default this module's dir.")
    args = parser.parse_args(argv)
    audit_dir = args.out if args.out is not None else str(Path(args.root) / _store.OUTPUT_DIR_NAME)
    try:
        decision = gate_decision(audit_dir, args.root, scripts_dir=args.scripts_dir)
    except Exception as exc:  # fail-closed: never report passed on a crashed assembly
        sys.stderr.write(
            f"production_gate_signals: internal error: {type(exc).__name__}: {exc}\n")
        return GATE_ERROR
    failures = ",".join(decision["failures"]) or "none"
    print(f"production_gate passed={decision['passed']} failures={failures} "
          f"permitted_autonomy={decision['permitted_autonomy']} "
          f"a3_enabled_by_default={decision['a3_enabled_by_default']}")
    return GATE_PASSED if decision["passed"] else GATE_DENIED


if __name__ == "__main__":
    raise SystemExit(main())
