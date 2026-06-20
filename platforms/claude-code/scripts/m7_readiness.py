"""Cross-phase M7 readiness aggregator (roadmap Phase 6 consolidation).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
Phases 6.1 and 6.2 produce a human-readable readiness checklist and a documented
release-gating procedure; this module makes the joint verdict **programmatic** so
"are we at M7?" is reproducible rather than a manual five-phase cross-read.

It reuses ``production_gate_signals.gate_decision`` for the six operational conjuncts
(the Phase 4 production gate, which also exercises the operational facets of Phases
1/3/5 -- least privilege, kill-switch, recoverability, self-audit), and adds the
earned-autonomy signal (``autonomy_earned``: the release gate's permitted autonomy
ceiling over the recorded telemetry is A2, proving the Phase 3 autonomy signal). The
test-suite-pinned floor (Phase 0 baseline counts, Phase 1 isolation regressions,
Phase 5 byte-equal parity) remains the gate of record (``make check``); this
aggregator consolidates the evidence-backed operational + autonomy verdict the per-run
audit produces.

Fail-closed: a missing record, an unreadable signal, or any error yields ``False`` for
that signal, and any single false signal yields ``passed == False``, named in
``failures`` -- the aggregator can only pass when every signal is positively
established. The verdict mirrors ``production_gate``'s ``{passed, failures, checks}``
shape.
"""

from __future__ import annotations

import sys
from importlib import util as _import_util
from pathlib import Path

# The earned autonomy ceiling that proves the Phase 3 A2/A3 autonomy signal.
A2_AUTONOMY = "A2"
# The aggregator's distinct signal beyond the six production-gate conjuncts.
AUTONOMY_SIGNAL = "autonomy_earned"


def _load_sibling(module_name, filename):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = _import_util.spec_from_file_location(module_name, path)
    module = _import_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_signals = _load_sibling("qb_production_gate_signals", "production_gate_signals.py")
_store = _load_sibling("qb_run_store", "run_store.py")


def evaluate(audit_dir, repo_root, scripts_dir=None) -> dict:
    """Return the fail-closed M7 readiness verdict over the captured evidence.

    ``checks`` is the per-signal boolean map -- the six production-gate conjuncts plus
    ``autonomy_earned`` -- and ``failures`` names every false signal (sorted). The
    earned ``permitted_autonomy`` ceiling is surfaced alongside. A crashed signal
    assembly is not readiness: it fails closed to ``passed == False``.
    """
    try:
        decision = _signals.gate_decision(audit_dir, repo_root, scripts_dir)
    except Exception:  # fail-closed: a crashed assembly is never readiness
        decision = {"passed": False, "failures": ["production_gate_error"],
                    "signals": {}, "permitted_autonomy": "A0"}
    checks = dict(decision.get("signals", {}))
    permitted = decision.get("permitted_autonomy", "A0")
    checks[AUTONOMY_SIGNAL] = (permitted == A2_AUTONOMY)
    failures = sorted(name for name, ok in checks.items() if not ok)
    return {
        "passed": not failures,
        "failures": failures,
        "checks": checks,
        "permitted_autonomy": permitted,
    }


def main(argv=None) -> int:
    """CLI entrypoint: print the fail-closed M7 readiness verdict over the run store.
    Exit 0 when M7-ready, 1 when any signal is false. Fail-closed on any error."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Aggregate prior-phase signals into one fail-closed M7 readiness verdict.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default=None,
                        help=f".qb/audit store directory; default <root>/{_store.OUTPUT_DIR_NAME}.")
    parser.add_argument("--scripts-dir", default=None)
    args = parser.parse_args(argv)
    audit_dir = args.out if args.out is not None else str(Path(args.root) / _store.OUTPUT_DIR_NAME)
    try:
        verdict = evaluate(audit_dir, args.root, scripts_dir=args.scripts_dir)
    except Exception as exc:  # fail-closed: never report ready on a crash
        sys.stderr.write(f"m7-readiness ERROR: {type(exc).__name__}: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(
        {"m7_ready": verdict["passed"], "failures": verdict["failures"]},
        sort_keys=True) + "\n")
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
