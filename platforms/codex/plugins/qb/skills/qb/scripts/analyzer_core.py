"""QB analyzer core -- reusable analysis primitives (Phase 1.3).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
Phase 1.3 extracts the repository-agnostic machinery the planning validator used
to own -- the length-bounded secret patterns and scan, the P0-P3 severity
counting, and a fail-closed analysis-state core -- into ONE place, so there is a
single implementation with two callers:

  * ``validate_planner_docs.py`` -- the planning path, which now imports these
    primitives and preserves byte-identical output; and
  * the Phase 1.2 analyzer interface -- via ``SecretHygieneAnalyzer`` below, which
    runs the same secret scan over an arbitrary repository and returns Phase 1.1
    Findings with redacted ``path:line`` evidence (never the secret value).

This retires the ASSESS-P2-02 coupling (the validator was the sole owner of the
secret/severity logic) without duplicating it.
"""

from __future__ import annotations

import bisect
import fnmatch
import importlib.util
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# --- Load co-located siblings (memoized; works as CLI and via importlib) -------
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
AnalyzerConfig = _ai.AnalyzerConfig
Finding = _ai.Finding
validate_finding = _ai.validate_finding
compute_finding_id = _ai.compute_finding_id

SEVERITIES: tuple[str, ...] = ("P0", "P1", "P2", "P3")

# Analyzer confidence policy. High is reserved for deterministic local evidence
# or configured advisory data; heuristic/tool/config hygiene findings stay
# medium unless a future rule has an explicit reason to use low.
CONFIDENCE_POLICY: dict[str, dict[str, str]] = {
    "secret-hygiene": {
        "secret-pattern": "high",
    },
    "command-injection": {
        "shell-string-subprocess": "high",
        "system-shell-call": "high",
        "system-pipe-call": "medium",
        "subprocess-getoutput": "medium",
        "node-shell-exec": "high",
        "dynamic-eval": "medium",
        "dynamic-exec": "medium",
        "path-traversal-sink": "medium",
    },
    "quality-correctness": {
        "tool-diagnostic": "medium",
    },
    "dependency-audit": {
        "manifest-hygiene": "medium",
        "network-advisory": "high",
    },
    "license-hygiene": {
        "missing-license": "high",
        "empty-license": "medium",
    },
    "config-hygiene": {
        "committed-config": "medium",
    },
    "workflow-actions": {
        "broad-action-ref": "medium",
        "broad-permissions": "medium",
    },
}


def confidence_for_rule(analyzer_id: str, rule_kind: str) -> str:
    """Return the reviewed confidence band for one analyzer rule kind."""
    try:
        return CONFIDENCE_POLICY[analyzer_id][rule_kind]
    except KeyError as exc:
        raise KeyError(f"unknown confidence policy: {analyzer_id}:{rule_kind}") from exc


_SUPPRESSION_RE = re.compile(r"\bqb-ignore:\s*(?P<rule>[A-Za-z0-9_.:-]+|\*)\s+(?P<reason>.+)")


def suppression_reason_for_line(text: str, line_number: int, rule_key: str) -> str | None:
    """Return the required reason for a matching same-line or prior-line suppression."""
    lines = text.splitlines()
    for candidate in (line_number, line_number - 1):
        if candidate < 1 or candidate > len(lines):
            continue
        match = _SUPPRESSION_RE.search(lines[candidate - 1])
        if not match:
            continue
        if match.group("rule") not in (rule_key, "*"):
            continue
        reason = match.group("reason").strip(" -:")
        return reason or None
    return None

# Directories QB must never audit as repository implementation source.
# ``.qb`` covers the audit run-store (``.qb/audit/``) as well as the planning
# artifacts, so the store is never scanned as if it were repository source.
_TOOL_OWNED_SCAN_DIRS = frozenset({
    ".git",
    ".hg",
    ".svn",
    ".qb",
    ".planwright",
})

# Non-git fallback pruning. In git worktrees, iter_repo_files instead follows
# git's own ignored/non-ignored view and applies only _TOOL_OWNED_SCAN_DIRS.
_FALLBACK_SKIP_SCAN_DIRS = _TOOL_OWNED_SCAN_DIRS | frozenset({
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "artifacts",
})


def _has_skipped_part(path: Path, skipped: frozenset[str]) -> bool:
    return any(part in skipped for part in path.parts)


def _command_safety():
    """Lazily resolve command_safety without a module-load import cycle.

    command_safety imports analyzer_core at load time, so analyzer_core cannot
    import it at the top level. Resolve it on first use (by which point the engine
    has loaded it) -- reusing the cached module instance when present.
    """
    module = sys.modules.get("qb_command_safety")
    if module is None:
        path = Path(__file__).resolve().parent / "command_safety.py"
        spec = importlib.util.spec_from_file_location("qb_command_safety", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["qb_command_safety"] = module
        spec.loader.exec_module(module)
    return module


def _git_list_files(root: Path) -> list[str] | None:
    """Return git-tracked/non-ignored files, or None outside usable git."""
    cs = _command_safety()
    argv = ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    try:
        # Flow through the central run_command convention (no shell, argv vector);
        # this trusted, read-only git call opts out of confinement explicitly.
        completed = cs.run_command(
            argv, confinement=cs.unconfined("trusted read-only git ls-files over the audited repo")
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return [rel for rel in completed.stdout.split("\0") if rel]


def _is_safe_file(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root)
    except (OSError, ValueError):
        return False
    return candidate.is_file()


def _path_selected(rel: str, include, exclude) -> bool:
    """True when the repo-relative posix path passes AnalyzerConfig include/exclude.

    fnmatch (case-sensitive) globs; a file is kept when it matches some include
    glob and no exclude glob. The defaults (``include=("**",)``, ``exclude=()``)
    select everything, so an analyzer that does not scope walks the whole tree --
    the filters change the walk only when a caller sets them.
    """
    if include and not any(fnmatch.fnmatchcase(rel, pat) for pat in include):
        return False
    if exclude and any(fnmatch.fnmatchcase(rel, pat) for pat in exclude):
        return False
    return True


def iter_repo_files(repo_root: str | Path, config=None):
    """Yield files QB may scan, excluding git-ignored/tool-owned paths.

    In git worktrees this follows git's own view of source files: tracked files
    plus untracked files that are not ignored by .gitignore or other standard
    ignore mechanisms. That keeps generated local planning state such as .qb/
    out of audits. Outside git, fall back to deterministic os.walk pruning.

    ``config`` is the optional AnalyzerConfig: its ``include``/``exclude`` globs
    (fnmatch over the repo-relative posix path) narrow the walk. The defaults --
    and ``config=None`` -- select everything, so unscoped callers are unaffected.
    """
    include = getattr(config, "include", ("**",))
    exclude = getattr(config, "exclude", ())
    root = Path(repo_root).resolve()
    if not root.is_dir():
        return

    git_files = _git_list_files(root)
    if git_files is not None:
        seen: set[str] = set()
        for rel in sorted(git_files):
            rel_path = Path(rel)
            if rel in seen or _has_skipped_part(rel_path, _TOOL_OWNED_SCAN_DIRS):
                continue
            seen.add(rel)
            if not _path_selected(rel, include, exclude):
                continue
            candidate = root / rel_path
            if _is_safe_file(root, candidate):
                yield candidate
        return

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        rel_dir = current.relative_to(root)
        if rel_dir != Path(".") and _has_skipped_part(rel_dir, _FALLBACK_SKIP_SCAN_DIRS):
            dirnames[:] = []
            continue
        dirnames[:] = sorted(name for name in dirnames if name not in _FALLBACK_SKIP_SCAN_DIRS)
        for filename in sorted(filenames):
            candidate = current / filename
            if not _path_selected(candidate.relative_to(root).as_posix(), include, exclude):
                continue
            if _is_safe_file(root, candidate):
                yield candidate

# --- Length-bounded secret patterns (the single source) -----------------------
# Relocated verbatim from validate_planner_docs.py; the planning validator now
# imports this list rather than defining its own copy.
SECRET_PATTERNS = [
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("github_legacy_pat", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    # AWS key IDs share the 16-char [0-9A-Z] body but vary in prefix: AKIA (long-term)
    # plus ASIA (STS temporary), AGPA/AIDA/ANPA/AROA/AIPA/ANVA (other identity types).
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|ANPA|AROA|AIPA|ANVA)[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("stripe_secret_key", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{20,}\b")),
    # Azure storage account key: 64 bytes base64 (86 chars + "==") preceded by the
    # AccountKey= context, so the anchor bounds false positives on bare base64 blobs.
    ("azure_storage_key", re.compile(r"AccountKey=[A-Za-z0-9+/]{86}==")),
    # GitHub OAuth / app / refresh tokens share ghp_'s structure but a different
    # prefix letter: gho_ (OAuth), ghu_ (user-to-server), ghs_ (server-to-server),
    # ghr_ (refresh). ghp_ (classic PAT) stays its own github_legacy_pat entry.
    ("github_app_token", re.compile(r"\bgh[orsu]_[A-Za-z0-9]{20,}\b")),
    # Google API key: the distinctive "AIza" prefix plus a fixed 35-char body
    # bounds false positives on bare base64-ish strings.
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
]


def scan_text_for_secrets(text: str) -> list[tuple[str, int]]:
    """Return ``[(pattern_name, line_number), ...]`` -- redacted, never the value.

    Enumeration order matches the validator's historical nested loop (outer over
    patterns, inner over matches) so callers produce byte-identical output.
    """
    results: list[tuple[str, int]] = []
    # Precompute newline offsets once; the line of a match is 1 + the count of
    # newlines before it, found by bisect (O(n + m log L) vs the old O(n*m) of a
    # per-match prefix count). Byte-identical results, same enumeration order.
    newline_offsets = [index for index, char in enumerate(text) if char == "\n"]
    for name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            line = bisect.bisect_left(newline_offsets, match.start()) + 1
            results.append((name, line))
    return results


def count_severities(severities) -> dict[str, int]:
    """Tally an iterable of P0-P3 tokens into a ``{P0,P1,P2,P3: int}`` dict."""
    counts = {sev: 0 for sev in SEVERITIES}
    for sev in severities:
        if sev in counts:
            counts[sev] += 1
    return counts


@dataclass
class AnalysisState:
    """Reusable fail-closed accumulation core: errors, warnings, metrics."""

    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


# --- Secret-hygiene analyzer (Phase 1.2 conformant; reuses the single source) --
class SecretHygieneAnalyzer:
    """Read-only analyzer: emits a Finding per secret match, value redacted."""

    descriptor = AnalyzerDescriptor(
        id="secret-hygiene",
        categories=("secret",),
        offline=True,
    )

    def analyze(self, repo_root: str, config) -> list:
        root = Path(repo_root).resolve()
        findings: list = []
        for path in iter_repo_files(root, config):
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            rel = path.relative_to(root).as_posix()
            for name, line in scan_text_for_secrets(text):
                evidence = f"{rel}:{line}"
                findings.append(
                    Finding(
                        id=compute_finding_id("secret", evidence, name),
                        category="secret",
                        severity="P1",
                        confidence=confidence_for_rule(self.descriptor.id, "secret-pattern"),
                        evidence=evidence,
                        rationale=(
                            f"A length-bounded secret pattern ({name}) matched at this "
                            "location; the matched value is redacted from this finding."
                        ),
                        suggested_fix=(
                            "Remove the secret from source and load it from an environment "
                            "variable or secret manager; rotate the exposed credential."
                        ),
                        fix_strategy="manual",
                    )
                )
        return findings
