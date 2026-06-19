"""QB headless entry point -- non-interactive audit->report loop for CI (Phase 6.3).

Canonical host-neutral QB IP under ``shared/`` (Python standard library + bash/git
only -- preserves the zero-setup property). Runs the engine against a target repo
with no interactive prompt and returns a deterministic, documented exit code a CI
pipeline can branch on.

Exit-code contract (fail-closed: every boundary/error is a distinct non-zero):
  0  EXIT_CLEAN            -- no findings.
  1  EXIT_FINDINGS         -- findings present (above threshold); CI should gate.
  2  EXIT_BUDGET_BOUNDARY  -- a policy/budget boundary halted the run.
  3  EXIT_INTERNAL_ERROR   -- an internal error occurred.

Autonomy defaults to A0 (report-only): the headless core performs the deterministic
audit and writes the report/evidence; applying fixes (A1+) requires a recipe/apply
provider, which is not part of the deterministic shared core and stays opt-in.
A3 deliver/commit/push/PR is never enabled by default.
"""

from __future__ import annotations

import argparse
import sys
from importlib import util as _import_util
from pathlib import Path

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_BUDGET_BOUNDARY = 2
EXIT_INTERNAL_ERROR = 3


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = _import_util.spec_from_file_location(module_name, path)
    module = _import_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_audit = _load_sibling("qb_audit_runner", "audit_runner.py")
_policy = _load_sibling("qb_policy", "policy.py")
_store = _load_sibling("qb_run_store", "run_store.py")
_report = _load_sibling("qb_report", "report.py")
_fs = _load_sibling("qb_finding_schema", "finding_schema.py")
_telemetry = _load_sibling("qb_telemetry", "telemetry.py")

AnalyzerConfig = _audit.AnalyzerConfig
SEVERITIES = _fs.SEVERITIES


def _severity_counts(findings):
    counts = {s: 0 for s in SEVERITIES}
    for finding in findings:
        sev = getattr(finding, "severity", None)
        if sev in counts:
            counts[sev] += 1
    return counts


def run_headless(repo_root, *, policy=None, output_dir=None, allow_networked=False,
                 run_id="run") -> int:
    """Run the audit->report loop unattended; return an exit code."""
    policy = policy or _policy.default_policy()
    output_dir = Path(output_dir) if output_dir is not None else Path(repo_root) / _store.OUTPUT_DIR_NAME
    try:
        store = _store.RunStore(output_dir).open(overwrite=True)
        store.append_log({"event": "run-start", "autonomy_level": policy.autonomy_level})

        config = AnalyzerConfig(allow_networked=allow_networked)
        registry = _audit.build_default_registry()
        findings = []
        for analyzer in registry.enabled(config.allow_networked):
            try:
                findings.extend(analyzer.analyze(str(repo_root), config))
            except Exception as exc:  # one analyzer failing must not abort the audit
                store.append_log({"event": "analyzer-error",
                                  "analyzer": analyzer.descriptor.id, "error": str(exc)})
        findings.sort(key=lambda f: f.id)
        store.write_findings(findings)
        store.append_log({"event": "audit-complete", "findings": len(findings)})

        # Hardening: A0 is report-only; A1+ requires an apply/recipe provider not part
        # of the deterministic core, so the headless core records the decision and skips.
        store.append_log({"event": "harden-skipped",
                          "reason": "report-only" if policy.autonomy_level == "A0"
                          else "no-recipe-provider-in-headless-core"})

        store.write_summary({
            "trigger": "completed",
            "total_findings": len(findings),
            "severity_counts": _severity_counts(findings),
            "autonomy_level": policy.autonomy_level,
        })
        # A completed run emits exactly one telemetry.json (a fixed path, so a
        # re-run overwrites rather than duplicates). Even report-only A0 records the
        # detection slice; the action/cost/quality slices stay unmeasured by default
        # (no fixes applied, no cost forwarded by the deterministic headless core).
        telemetry_record = _telemetry.build_telemetry(
            run_id=run_id,
            autonomy_level=policy.autonomy_level,
            findings=findings,
            evidence=store.read_evidence(),
        )
        store.write_telemetry(telemetry_record)
        # Persist the run into the store-local multi-run series too, so the store
        # satisfies its own REQUIRED_SUBPATHS layout and the report emitted just
        # below sees a non-empty aggregate to derive trend_direction from.
        store.append_telemetry_aggregate(telemetry_record)
        _report.emit(store, provenance=_report.build_provenance(policy))
        return EXIT_FINDINGS if findings else EXIT_CLEAN
    except Exception as exc:  # fail-closed: never report a crashed run as clean
        sys.stderr.write(f"qb_headless: internal error: {type(exc).__name__}: {exc}\n")
        return EXIT_INTERNAL_ERROR


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the QB engine headlessly over a repository.")
    parser.add_argument("--root", default=".", help="Target repository to audit; default: current directory.")
    parser.add_argument("--out", default=None, help=f"Output directory; default: <root>/{_store.OUTPUT_DIR_NAME}.")
    parser.add_argument("--policy", default=None, help="Path to a policy JSON file; default: conservative A0.")
    parser.add_argument("--allow-networked", action="store_true",
                        help="Permit opt-in networked analyzers (default: offline only).")
    args = parser.parse_args(argv)

    policy = _policy.load_policy(args.policy) if args.policy else _policy.default_policy()
    code = run_headless(args.root, policy=policy, output_dir=args.out, allow_networked=args.allow_networked)
    out = args.out or str(Path(args.root) / _store.OUTPUT_DIR_NAME)
    print(f"qb_headless=done exit_code={code} output_dir={out} autonomy={policy.autonomy_level}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
