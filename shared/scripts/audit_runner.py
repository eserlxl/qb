"""QB audit runner -- the read-only audit engine assembly (Phase 1.4).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
This completes Phase 1: it enumerates the registered analyzers (Phase 1.2) in
deterministic order, runs each over an arbitrary repository root, aggregates
their Phase-1.1 Findings under a total ordering, and writes a graded,
evidence-backed findings file plus a run summary into a fixed-name output
directory whose names are validator-checked identifiers (mirroring how
``Planner-docs/`` names are enforced).

Properties:
  * Deterministic -- two runs over an unchanged repository produce byte-identical
    output (total ordering on findings + sorted file walks + sorted JSON keys).
  * Offline by default -- a ``networked`` analyzer is not invoked unless
    networking is explicitly enabled; each skip is recorded in the summary.
  * Read-only on the target -- the runner only reads the audited repository and
    writes solely within its own output directory.
  * Redacted -- secret-hygiene findings carry ``path:line`` evidence only.

Output convention (fixed, validator-checked identifiers):
  ``QB-Audit/findings.jsonl``  -- one canonical JSON finding per line, ordered.
  ``QB-Audit/summary.json``    -- counts by severity/category + analyzers run/skipped.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Load in dependency order so a single finding_schema instance is shared.
_fs = _load_sibling("qb_finding_schema", "finding_schema.py")
_ai = _load_sibling("qb_analyzer_interface", "analyzer_interface.py")
_core = _load_sibling("qb_analyzer_core", "analyzer_core.py")
_cs = _load_sibling("qb_command_safety", "command_safety.py")

serialize_finding = _fs.serialize_finding
validate_finding = _fs.validate_finding
SEVERITIES = _fs.SEVERITIES

AnalyzerRegistry = _ai.AnalyzerRegistry
AnalyzerConfig = _ai.AnalyzerConfig
AnalyzerDescriptor = _ai.AnalyzerDescriptor
ReferenceAnalyzer = _ai.ReferenceAnalyzer
SecretHygieneAnalyzer = _core.SecretHygieneAnalyzer
CommandInjectionAnalyzer = _cs.CommandInjectionAnalyzer

# --- Fixed output-directory convention (validator-checked identifiers) ---------
OUTPUT_DIR_NAME = "QB-Audit"
FINDINGS_FILENAME = "findings.jsonl"
SUMMARY_FILENAME = "summary.json"
OUTPUT_FILENAMES = (FINDINGS_FILENAME, SUMMARY_FILENAME)

_SEV_RANK = {sev: index for index, sev in enumerate(SEVERITIES)}


def _sort_key(finding):
    """Total ordering independent of analyzer discovery / filesystem timing."""
    return (
        _SEV_RANK.get(finding.severity, len(SEVERITIES)),
        finding.category,
        finding.evidence,
        finding.id,
    )


def build_default_registry():
    """QB's built-in analyzers: the reference no-op plus the secret-hygiene scan."""
    registry = AnalyzerRegistry()
    registry.register(ReferenceAnalyzer())
    registry.register(SecretHygieneAnalyzer())
    registry.register(CommandInjectionAnalyzer())
    return registry


def validate_output_layout(output_dir) -> list[str]:
    """Identifier check: reject a misnamed or incomplete audit output tree."""
    errors: list[str] = []
    directory = Path(output_dir)
    if directory.name != OUTPUT_DIR_NAME:
        errors.append(f"invalid_output_dir_name={directory.name}")
    for filename in OUTPUT_FILENAMES:
        if not (directory / filename).is_file():
            errors.append(f"missing_output_file={filename}")
    return errors


def run_audit(repo_root, config=None, registry=None, output_dir=None) -> dict:
    """Run the read-only audit and write the fixed output tree. Returns a result dict."""
    config = config or AnalyzerConfig()
    registry = registry or build_default_registry()
    output_dir = Path(output_dir) if output_dir is not None else Path(repo_root) / OUTPUT_DIR_NAME

    enabled = registry.enabled(config.allow_networked)
    enabled_ids = {analyzer.descriptor.id for analyzer in enabled}

    findings: list = []
    analyzers_run: list[str] = []
    analyzers_skipped: list[dict] = []

    # Offline-by-default: networked analyzers present but not enabled are skipped.
    for analyzer in registry.analyzers():
        if analyzer.descriptor.id not in enabled_ids:
            analyzers_skipped.append({"id": analyzer.descriptor.id, "reason": "networked-disabled"})
    # Registry load failures (graceful absence) carry their own reason.
    for skipped_id, reason in registry.skipped:
        analyzers_skipped.append({"id": skipped_id, "reason": reason})

    for analyzer in enabled:
        try:
            result = analyzer.analyze(str(repo_root), config)
        except Exception as exc:  # one analyzer failing must not abort the run
            analyzers_skipped.append(
                {"id": analyzer.descriptor.id, "reason": f"{type(exc).__name__}: {exc}"}
            )
            continue
        findings.extend(result)
        analyzers_run.append(analyzer.descriptor.id)

    findings.sort(key=_sort_key)

    severity_counts = {sev: 0 for sev in SEVERITIES}
    category_counts: dict[str, int] = {}
    for finding in findings:
        if finding.severity in severity_counts:
            severity_counts[finding.severity] += 1
        category_counts[finding.category] = category_counts.get(finding.category, 0) + 1

    output_dir.mkdir(parents=True, exist_ok=True)
    findings_text = "".join(serialize_finding(finding) + "\n" for finding in findings)
    (output_dir / FINDINGS_FILENAME).write_text(findings_text, encoding="utf-8")

    summary = {
        "total_findings": len(findings),
        "severity_counts": severity_counts,
        "category_counts": category_counts,
        "analyzers_run": sorted(analyzers_run),
        "analyzers_skipped": sorted(analyzers_skipped, key=lambda item: item["id"]),
        "allow_networked": config.allow_networked,
    }
    (output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    return {"output_dir": str(output_dir), "findings": findings, "summary": summary}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the QB read-only audit engine over a repository.")
    parser.add_argument("--root", default=".", help="Repository root to audit; default: current directory.")
    parser.add_argument("--out", default=None, help=f"Output directory; default: <root>/{OUTPUT_DIR_NAME}.")
    parser.add_argument(
        "--allow-networked",
        action="store_true",
        help="Permit analyzers that declared themselves networked (default: offline only).",
    )
    args = parser.parse_args(argv)

    config = AnalyzerConfig(allow_networked=args.allow_networked)
    result = run_audit(args.root, config=config, output_dir=args.out)
    summary = result["summary"]
    counts = summary["severity_counts"]
    print(
        "qb_audit=completed"
        f" output_dir={result['output_dir']}"
        f" total_findings={summary['total_findings']}"
        f" P0={counts['P0']} P1={counts['P1']} P2={counts['P2']} P3={counts['P3']}"
        f" analyzers_run={len(summary['analyzers_run'])}"
        f" analyzers_skipped={len(summary['analyzers_skipped'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
