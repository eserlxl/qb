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

This retires the AUTOPSY-P2-02 coupling (the validator was the sole owner of the
secret/severity logic) without duplicating it.
"""

from __future__ import annotations

import importlib.util
import re
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

# --- Length-bounded secret patterns (the single source) -----------------------
# Relocated verbatim from validate_planner_docs.py; the planning validator now
# imports this list rather than defining its own copy.
SECRET_PATTERNS = [
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("github_legacy_pat", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
]


def scan_text_for_secrets(text: str) -> list[tuple[str, int]]:
    """Return ``[(pattern_name, line_number), ...]`` -- redacted, never the value.

    Enumeration order matches the validator's historical nested loop (outer over
    patterns, inner over matches) so callers produce byte-identical output.
    """
    results: list[tuple[str, int]] = []
    for name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
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
            for name, line in scan_text_for_secrets(text):
                evidence = f"{rel}:{line}"
                findings.append(
                    Finding(
                        id=compute_finding_id("secret", evidence, name),
                        category="secret",
                        severity="P1",
                        confidence="high",
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
