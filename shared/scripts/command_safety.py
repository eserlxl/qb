"""QB command-safety convention + injection analyzer (Phase 2.2).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
This module addresses ASSESS-P1-03 (the untrusted-repo command-execution surface)
with two halves:

1. A tool-wide STRUCTURED ARGV CONVENTION. Every external process QB launches is
   represented as an explicit program-plus-argument vector (a ``list[str]``) and
   run WITHOUT an intervening system shell and WITHOUT interpolating untrusted
   strings into a command line. ``assert_argv`` and ``run_command`` enforce this;
   Phase 2.3 (tool adapters) and Phase 3 (the fixer's verification commands) MUST
   use ``run_command`` rather than any shell-string form. A companion rule:
   ``AUTO_RUN_REPO_SCRIPTS`` is False -- QB never auto-executes scripts provided
   by the repository under audit absent explicit, sandboxed authorization.

2. A PATH-CONTAINMENT helper. ``resolve_within`` confines any analyzer/fixer file
   access to the target repository root and rejects traversal outside it; this is
   the runtime guarantee that backs the (necessarily best-effort) static
   traversal detection below.

3. A static ``CommandInjectionAnalyzer`` (Phase 1.2 conformant) that flags the
   inverse of the convention in audited code -- shell-string execution sinks,
   dynamic evaluation, and path-traversal file sinks -- as ``injection`` /
   ``path-traversal`` findings with redacted ``path:line`` evidence. Detection is
   pattern- and sink-based, not a dataflow engine; containment is the guarantee.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

# QB never auto-runs scripts from the audited repository without explicit,
# sandboxed authorization. This is a hard, testable rule.
AUTO_RUN_REPO_SCRIPTS = False


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
Analyzer = _ai.Analyzer
AnalyzerDescriptor = _ai.AnalyzerDescriptor
Finding = _ai.Finding
compute_finding_id = _ai.compute_finding_id


# --- Structured argv convention -----------------------------------------------
def assert_argv(argv):
    """Validate a command is an explicit argument vector, never a shell string."""
    if isinstance(argv, str):
        raise ValueError("command must be an argument vector (list[str]), not a shell string")
    if not isinstance(argv, (list, tuple)) or not argv:
        raise ValueError("command must be a non-empty list of arguments")
    if not all(isinstance(arg, str) for arg in argv):
        raise ValueError("every command argument must be a string")
    return list(argv)


def run_command(argv, cwd=None, timeout=None, env=None):
    """Run an external command from an argv vector with no system shell."""
    args = assert_argv(argv)
    return subprocess.run(  # noqa: S603 -- argv form, no shell; this is the safe primitive
        args,
        cwd=cwd,
        timeout=timeout,
        env=env,
        shell=False,
        capture_output=True,
        text=True,
    )


# --- Path containment ---------------------------------------------------------
def resolve_within(root, candidate) -> Path:
    """Resolve ``candidate`` under ``root``; raise ValueError if it escapes root."""
    root_path = Path(root).resolve()
    target = (root_path / candidate).resolve()
    try:
        target.relative_to(root_path)
    except ValueError:
        raise ValueError(f"path escapes repository root: {candidate}")
    return target


def is_within(root, candidate) -> bool:
    try:
        resolve_within(root, candidate)
        return True
    except ValueError:
        return False


# --- Static detection rules ---------------------------------------------------
# (rule_key, category, severity, confidence, compiled pattern)
# Patterns recognize the documented sinks; safe argv/exec-file forms are not matched.
_RULES = [
    ("shell-string-subprocess", "injection", "P1", "high",
     re.compile(r"subprocess\.(?:run|call|check_call|check_output|Popen)\s*\([^\n]*shell\s*=\s*True")),
    ("system-shell-call", "injection", "P1", "high", re.compile(r"\bos\.system\s*\(")),
    ("system-pipe-call", "injection", "P2", "medium", re.compile(r"\bos\.popen\s*\(")),
    ("subprocess-getoutput", "injection", "P2", "medium", re.compile(r"\bsubprocess\.getoutput\s*\(")),
    ("node-shell-exec", "injection", "P1", "high", re.compile(r"child_process\.exec\s*\(")),
    ("dynamic-eval", "injection", "P2", "medium", re.compile(r"\beval\s*\(")),
    ("dynamic-exec", "injection", "P2", "medium", re.compile(r"\bexec\s*\(")),
    ("path-traversal-sink", "path-traversal", "P2", "medium",
     re.compile(r"(?:open|os\.path\.join|Path)\s*\([^)]*\.\.[\\/]")),
]

_FIX_STRATEGY = {"high": "propose", "medium": "manual", "low": "manual"}


def scan_text_for_command_risks(text: str):
    """Return ``[(rule_key, category, severity, confidence, line), ...]`` -- redacted."""
    results = []
    for rule_key, category, severity, confidence, pattern in _RULES:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            results.append((rule_key, category, severity, confidence, line))
    return results


class CommandInjectionAnalyzer:
    """Read-only analyzer for command-execution, dynamic-eval, and traversal sinks."""

    descriptor = AnalyzerDescriptor(
        id="command-injection",
        categories=("injection", "path-traversal"),
        offline=True,
    )

    def analyze(self, repo_root: str, config) -> list:
        root = Path(repo_root)
        findings: list = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or ".git" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            rel = path.relative_to(root).as_posix()
            for rule_key, category, severity, confidence, line in scan_text_for_command_risks(text):
                evidence = f"{rel}:{line}"
                findings.append(
                    Finding(
                        id=compute_finding_id(category, evidence, rule_key),
                        category=category,
                        severity=severity,
                        confidence=confidence,
                        evidence=evidence,
                        rationale=(
                            f"Potential {rule_key} sink ({category}) detected at this location; "
                            "the matched source text is redacted from this finding."
                        ),
                        suggested_fix=(
                            "Replace shell-string execution with an explicit argument vector "
                            "(see the QB structured argv convention), avoid dynamic evaluation of "
                            "external input, and confine file paths to the repository root."
                        ),
                        fix_strategy=_FIX_STRATEGY.get(confidence, "manual"),
                    )
                )
        return findings
