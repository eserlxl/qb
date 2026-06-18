"""QB offline quality/correctness adapters (Phase 2.3).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
Wraps locally-available linters / static-analysis tools as Phase-1.2 analyzers,
normalizing their heterogeneous output into the unified Finding schema.

Design guarantees (per main-planning sections 5/7 and the assessment offline-core
rule):
  * Every tool is launched through the Phase-2.2 structured argv convention
    (``command_safety.run_command``), never a shell string.
  * Tool presence is detected first; an absent tool is a NON-FATAL skip recorded
    in the capability report, so a zero-setup base install still produces a valid
    (smaller) audit and adds no third-party dependency.
  * Native severities map to QB P0-P3 by a documented, deterministic table.
  * Each finding records the originating tool in its rationale (provenance).
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_ai = _load_sibling("qb_analyzer_interface", "analyzer_interface.py")
_cs = _load_sibling("qb_command_safety", "command_safety.py")
_core = _load_sibling("qb_analyzer_core", "analyzer_core.py")
Analyzer = _ai.Analyzer
AnalyzerDescriptor = _ai.AnalyzerDescriptor
Finding = _ai.Finding
compute_finding_id = _ai.compute_finding_id
run_command = _cs.run_command
confidence_for_rule = _core.confidence_for_rule


@dataclass
class ToolAdapter:
    """A thin, read-only bridge from one external offline tool to QB findings."""

    name: str               # provenance: the tool that produced the finding
    executable: str         # command detected via shutil.which()
    category: str           # "quality" or "correctness"
    build_argv: Callable[[str], list]      # (repo_root) -> argv list
    parse: Callable[[str, str], list]      # (stdout, stderr) -> list[dict diagnostics]
    severity_map: dict = field(default_factory=dict)  # native severity -> P0-P3
    default_severity: str = "P3"

    def available(self) -> bool:
        return shutil.which(self.executable) is not None


def _ruff_argv(repo_root: str) -> list:
    return ["ruff", "check", "--output-format=json", repo_root]


def _ruff_parse(stdout: str, stderr: str) -> list:
    try:
        items = json.loads(stdout or "[]")
    except json.JSONDecodeError:
        return []
    diagnostics = []
    for item in items:
        code = item.get("code") or "ruff"
        diagnostics.append({
            "path": item.get("filename", ""),
            "line": (item.get("location") or {}).get("row", 1),
            "severity": code[:1] if code else "E",
            "rule": code,
            "message": item.get("message", ""),
        })
    return diagnostics


_PYFLAKES_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+):(?:\d+:)?\s*(?P<message>.+)$")


def _pyflakes_argv(repo_root: str) -> list:
    return ["pyflakes", repo_root]


def _pyflakes_parse(stdout: str, stderr: str) -> list:
    diagnostics = []
    for raw in (stdout or "").splitlines():
        match = _PYFLAKES_RE.match(raw.strip())
        if not match:
            continue
        diagnostics.append({
            "path": match.group("path"),
            "line": int(match.group("line")),
            "severity": "error",
            "rule": "pyflakes",
            "message": match.group("message"),
        })
    return diagnostics


def default_quality_adapters() -> list:
    """QB's built-in offline adapters; each skips gracefully if its tool is absent."""
    return [
        ToolAdapter(
            name="ruff", executable="ruff", category="quality",
            build_argv=_ruff_argv, parse=_ruff_parse,
            severity_map={"F": "P2", "E": "P3", "W": "P3"}, default_severity="P3",
        ),
        ToolAdapter(
            name="pyflakes", executable="pyflakes", category="correctness",
            build_argv=_pyflakes_argv, parse=_pyflakes_parse,
            severity_map={"error": "P2"}, default_severity="P2",
        ),
    ]


class QualityAnalyzer:
    """Runs offline tool adapters, normalizes output, degrades gracefully."""

    descriptor = AnalyzerDescriptor(
        id="quality-correctness",
        categories=("quality", "correctness"),
        offline=True,
    )

    def __init__(self, adapters=None):
        self.adapters = list(adapters) if adapters is not None else default_quality_adapters()
        self.last_capability_report: dict = {"ran": [], "skipped": []}

    def _relpath(self, repo_root: Path, raw_path: str) -> str:
        try:
            return Path(raw_path).resolve().relative_to(repo_root.resolve()).as_posix()
        except (ValueError, OSError):
            return raw_path

    def analyze(self, repo_root: str, config) -> list:
        root = Path(repo_root)
        report = {"ran": [], "skipped": []}
        findings: list = []

        for adapter in self.adapters:
            if not adapter.available():
                report["skipped"].append({
                    "adapter": adapter.name,
                    "executable": adapter.executable,
                    "reason": "tool-unavailable",
                })
                continue
            try:
                completed = run_command(adapter.build_argv(str(root)), cwd=str(root))
                diagnostics = adapter.parse(completed.stdout, completed.stderr)
            except Exception as exc:  # fail soft to a recorded skip; never crash the audit
                report["skipped"].append({
                    "adapter": adapter.name,
                    "executable": adapter.executable,
                    "reason": f"{type(exc).__name__}: {exc}",
                })
                continue
            report["ran"].append(adapter.name)
            for diag in diagnostics:
                severity = adapter.severity_map.get(diag.get("severity"), adapter.default_severity)
                rel = self._relpath(root, diag.get("path", ""))
                evidence = f"{rel}:{diag.get('line', 1)}"
                rule = diag.get("rule", adapter.name)
                findings.append(
                    Finding(
                        id=compute_finding_id(adapter.category, evidence, f"{adapter.name}:{rule}"),
                        category=adapter.category,
                        severity=severity,
                        confidence=confidence_for_rule(self.descriptor.id, "tool-diagnostic"),
                        evidence=evidence,
                        rationale=f"Reported by {adapter.name} ({rule}): {diag.get('message', '').strip()}",
                        suggested_fix=f"Address the {adapter.name} diagnostic {rule} at this location.",
                        fix_strategy="manual",
                    )
                )

        self.last_capability_report = report
        findings.sort(key=lambda f: (f.category, f.evidence, f.id))
        return findings
