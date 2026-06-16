"""QB command-safety convention + injection analyzer (Phase 2.2).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
This module addresses ASSESS-P1-03 (the untrusted-repo command-execution surface)
with two halves:

1. A tool-wide STRUCTURED ARGV CONVENTION. Every external process QB launches is
   represented as an explicit program-plus-argument vector (a ``list[str]``) and
   run WITHOUT an intervening system shell and WITHOUT interpolating untrusted
   strings into a command line. ``assert_argv`` and ``run_command`` enforce this;
   Phase 2.3 (tool adapters) and Phase 3 (the fixer's verification commands) MUST
   use ``run_command`` rather than any shell-string form. ``run_command`` also
   owns the default-off stdlib process-confinement seam: requested confinement
   is established before spawn, and unavailable required controls raise
   ``ConfinementUnavailable`` before any child process runs. A companion rule:
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

import bisect
import importlib.util
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Environment keys safe to forward to an untrusted / repo-provided command: enough
# for a typical test runner (PATH, HOME, locale, tmpdir, terminal) and nothing else,
# so a secret in QB's own environment never reaches the code being verified.
_SAFE_ENV_KEYS = (
    "PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LANGUAGE",
    "TERM", "SHELL", "USER", "LOGNAME", "TZ", "PWD",
)
_SAFE_ENV_PREFIXES = ("LC_",)

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
_core = _load_sibling("qb_analyzer_core", "analyzer_core.py")
Analyzer = _ai.Analyzer
AnalyzerDescriptor = _ai.AnalyzerDescriptor
Finding = _ai.Finding
compute_finding_id = _ai.compute_finding_id
iter_repo_files = _core.iter_repo_files


# --- Structured argv convention -----------------------------------------------
class ConfinementError(RuntimeError):
    """Base class for requested command-confinement failures."""


class ConfinementUnavailable(ConfinementError):
    """Raised when a requested confinement control cannot be established."""


@dataclass(frozen=True)
class ConfinementSpec:
    """Opt-in process-confinement controls for run_command.

    Supported controls are deliberately stdlib-only:
    - process_group: start the child in a new session/process group.
    - resource_limits: apply conservative POSIX resource hardening when present.
    """

    enabled: bool = False
    require: tuple[str, ...] = ("process_group",)
    resource_limits: bool = True


def available_confinement_controls() -> tuple[str, ...]:
    """Return stdlib confinement controls available on this host."""
    controls: list[str] = []
    if os.name == "posix":
        controls.append("process_group")
        try:
            import resource  # noqa: F401
        except ImportError:
            pass
        else:
            controls.append("resource_limits")
    return tuple(controls)


def _normalize_confinement(confinement) -> ConfinementSpec:
    if confinement in (None, False):
        return ConfinementSpec(enabled=False, require=(), resource_limits=False)
    if confinement is True:
        return ConfinementSpec()
    if isinstance(confinement, ConfinementSpec):
        return confinement
    if isinstance(confinement, dict):
        raw_require = confinement.get("require", ("process_group",))
        if isinstance(raw_require, str):
            require = (raw_require,)
        else:
            require = tuple(str(item) for item in raw_require)
        return ConfinementSpec(
            enabled=bool(confinement.get("enabled", True)),
            require=require,
            resource_limits=bool(confinement.get("resource_limits", True)),
        )
    raise TypeError("confinement must be None, bool, ConfinementSpec, or dict")


def _establish_confinement(spec: ConfinementSpec) -> tuple[tuple[str, ...], object | None, bool]:
    if not spec.enabled:
        return (), None, False

    available = set(available_confinement_controls())
    requested = set(spec.require)
    unsupported = requested - {"process_group", "resource_limits"}
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise ConfinementUnavailable(f"unsupported confinement control(s): {names}; command not run")

    missing = requested - available
    if missing:
        names = ", ".join(sorted(missing))
        raise ConfinementUnavailable(f"confinement unavailable: {names}; command not run")

    established: list[str] = []
    start_new_session = False
    preexec_fn = None

    if "process_group" in available:
        start_new_session = True
        established.append("process_group")

    if spec.resource_limits and "resource_limits" in available:
        import resource

        def _limit_child() -> None:
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

        preexec_fn = _limit_child
        established.append("resource_limits")

    if not established:
        raise ConfinementUnavailable("confinement unavailable: no stdlib controls; command not run")
    return tuple(established), preexec_fn, start_new_session


def assert_argv(argv):
    """Validate a command is an explicit argument vector, never a shell string."""
    if isinstance(argv, str):
        raise ValueError("command must be an argument vector (list[str]), not a shell string")
    if not isinstance(argv, (list, tuple)) or not argv:
        raise ValueError("command must be a non-empty list of arguments")
    if not all(isinstance(arg, str) for arg in argv):
        raise ValueError("every command argument must be a string")
    return list(argv)


def run_command(argv, cwd=None, timeout=None, env=None, confinement=None):
    """Run an external command from an argv vector with no system shell.

    Confinement is opt-in and default-off. When requested, the wrapper
    establishes the available stdlib process boundary before spawning the child;
    if a required control cannot be established, it raises
    ConfinementUnavailable instead of silently running unconfined.
    """
    args = assert_argv(argv)
    spec = _normalize_confinement(confinement)
    controls, preexec_fn, start_new_session = _establish_confinement(spec)
    completed = subprocess.run(  # noqa: S603 -- argv form, no shell; this is the safe primitive
        args,
        cwd=cwd,
        timeout=timeout,
        env=env,
        shell=False,
        capture_output=True,
        text=True,
        preexec_fn=preexec_fn,
        start_new_session=start_new_session,
    )
    completed.qb_confinement = {
        "enabled": spec.enabled,
        "controls": controls,
    }
    return completed


def minimal_env(base=None) -> dict:
    """A least-privilege environment for running an untrusted / repo-provided command.

    Forwards only the allowlisted keys a test runner needs (PATH, HOME, locale,
    tmpdir, terminal) and drops everything else -- so any credential present in QB's
    own environment cannot leak into the verified repository's code. PATH is always
    present (falling back to ``os.defpath``) so the command can still be located.
    """
    source = os.environ if base is None else base
    env = {
        key: value
        for key, value in source.items()
        if key in _SAFE_ENV_KEYS or any(key.startswith(prefix) for prefix in _SAFE_ENV_PREFIXES)
    }
    env.setdefault("PATH", os.defpath)
    return env


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
    # Precompute newline offsets once and bisect per match (O(n + m log L) vs the
    # old O(n*m) per-match prefix count); byte-identical results, same order.
    newline_offsets = [index for index, char in enumerate(text) if char == "\n"]
    for rule_key, category, severity, confidence, pattern in _RULES:
        for match in pattern.finditer(text):
            line = bisect.bisect_left(newline_offsets, match.start()) + 1
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
        root = Path(repo_root).resolve()
        findings: list = []
        for path in iter_repo_files(root):
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
