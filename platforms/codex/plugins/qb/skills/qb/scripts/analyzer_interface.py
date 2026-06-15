"""QB analyzer interface -- the read-only contract every analyzer implements.

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
This module fixes the second half of Phase 1: given the frozen Finding schema
(``finding_schema.py``, Phase 1.1), it defines what an *analyzer* is, so the
Phase 2 suite is a matter of writing conformant plugins rather than re-inventing
wiring, the Phase 1.3 validator refactor has a target to conform to, and the
Phase 1.4 runner has a registry to enumerate.

================================================================================
THE CONTRACT
================================================================================
Method   : ``analyze(repo_root: str, config: AnalyzerConfig) -> list[Finding]``
Input    : a repository root path plus a read-only configuration object.
Output   : a list of findings, each conformant to the Phase 1.1 schema.
Read-only: an analyzer MUST NOT mutate the repository it inspects. The interface
           hands an analyzer only what it needs to read and takes back findings;
           a write attempt is a contract breach, asserted by the conformance test
           (the inspected tree is byte-identical after a run).

CAPABILITY DESCRIPTOR -- every analyzer carries an ``AnalyzerDescriptor`` with a
stable ``id``, the ``categories`` it can produce (each drawn from the frozen
schema's ``CATEGORIES``), and an ``offline`` flag. ``offline=True`` means the
analyzer needs no network; ``offline=False`` (networked) analyzers must not run
in the offline core unless networking is explicitly enabled -- a property the
registry's ``enabled(allow_networked=...)`` filter and the Phase 1.4 runner treat
as authoritative, not advisory.

Example descriptor:
    AnalyzerDescriptor(id="secret-hygiene", categories=("secret",), offline=True)

REGISTRY -- ``AnalyzerRegistry`` registers QB-owned analyzers and enumerates them
in a deterministic order (sorted by id) so runs are reproducible and diffable.
Discovery is restricted to QB-owned analyzers under ``shared/``; the registry
NEVER imports code from the repository being audited (that would be an injection
vector against untrusted repos). ``register_optional`` implements the
graceful-absence rule: an optional (e.g. networked) analyzer that fails to load
is recorded in ``skipped`` with a reason and the run continues.

REFERENCE ANALYZER -- ``ReferenceAnalyzer`` is a trivial, offline analyzer that
emits exactly one deterministic informational finding proving registration,
invocation, and finding emission work end to end. It performs no real detection.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable


# --- Load the co-located frozen Finding schema (Phase 1.1) ---------------------
# analyzer_interface.py is always materialized next to finding_schema.py (in
# shared/scripts/ and in every platform's scripts dir), so resolve it by path
# rather than relying on sys.path.
def _load_finding_schema():
    path = Path(__file__).resolve().parent / "finding_schema.py"
    spec = importlib.util.spec_from_file_location("qb_finding_schema", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


_fs = _load_finding_schema()
Finding = _fs.Finding
validate_finding = _fs.validate_finding
compute_finding_id = _fs.compute_finding_id
CATEGORIES = _fs.CATEGORIES


# --- Capability descriptor ----------------------------------------------------
@dataclass(frozen=True)
class AnalyzerDescriptor:
    """Stable identity + capability declaration for an analyzer."""

    id: str
    categories: tuple[str, ...]
    offline: bool
    version: str = "1"

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.id.strip():
            errors.append("empty_descriptor_id")
        if not self.categories:
            errors.append("no_categories")
        unknown = [c for c in self.categories if c not in CATEGORIES]
        if unknown:
            errors.append(f"unknown_categories={unknown}")
        return errors


# --- Read-only analyzer configuration -----------------------------------------
@dataclass(frozen=True)
class AnalyzerConfig:
    """Read-only configuration an analyzer may consult."""

    include: tuple[str, ...] = ("**",)
    exclude: tuple[str, ...] = ()
    allow_networked: bool = False


# --- The interface ------------------------------------------------------------
@runtime_checkable
class Analyzer(Protocol):
    """Every analyzer exposes a ``descriptor`` and a read-only ``analyze``."""

    descriptor: AnalyzerDescriptor

    def analyze(self, repo_root: str, config: AnalyzerConfig) -> list:  # list[Finding]
        ...


# --- Registry -----------------------------------------------------------------
class AnalyzerRegistry:
    """Deterministic registry of QB-owned analyzers (never repo-supplied code)."""

    def __init__(self) -> None:
        self._analyzers: dict[str, Analyzer] = {}
        self._skipped: list[tuple[str, str]] = []

    def register(self, analyzer: Analyzer) -> Analyzer:
        descriptor = analyzer.descriptor
        errors = descriptor.validate()
        if errors:
            raise ValueError(f"invalid_descriptor={descriptor.id}::{errors}")
        if descriptor.id in self._analyzers:
            raise ValueError(f"duplicate_analyzer_id={descriptor.id}")
        self._analyzers[descriptor.id] = analyzer
        return analyzer

    def register_optional(self, loader: Callable[[], Analyzer], analyzer_id: str):
        """Register an optional analyzer; record + skip if it fails to load."""
        try:
            analyzer = loader()
        except Exception as exc:  # graceful absence -- never abort the run
            self._skipped.append((analyzer_id, f"{type(exc).__name__}: {exc}"))
            return None
        return self.register(analyzer)

    def analyzers(self) -> list[Analyzer]:
        """All registered analyzers in deterministic id order."""
        return [self._analyzers[key] for key in sorted(self._analyzers)]

    def enabled(self, allow_networked: bool) -> list[Analyzer]:
        """Analyzers permitted to run; networked ones only when explicitly allowed."""
        return [a for a in self.analyzers() if a.descriptor.offline or allow_networked]

    @property
    def skipped(self) -> list[tuple[str, str]]:
        return list(self._skipped)


# --- Trivial reference analyzer (proves the wiring; no real detection) ---------
class ReferenceAnalyzer:
    """Offline analyzer emitting one deterministic informational finding."""

    descriptor = AnalyzerDescriptor(
        id="reference-noop",
        categories=("config",),
        offline=True,
    )

    _EVIDENCE = ".:1"
    _RULE_KEY = "reference-analyzer-rootcheck"

    def analyze(self, repo_root: str, config: AnalyzerConfig) -> list:
        finding = Finding(
            id=compute_finding_id("config", self._EVIDENCE, self._RULE_KEY),
            category="config",
            severity="P3",
            confidence="high",
            evidence=self._EVIDENCE,
            rationale="Reference analyzer reached the repository root; the analyzer interface wiring is functional.",
            suggested_fix="No action required; this informational finding is an interface self-check.",
            fix_strategy="none",
        )
        return [finding]


def default_registry() -> AnalyzerRegistry:
    """A registry preloaded with QB's built-in analyzers (currently the reference)."""
    registry = AnalyzerRegistry()
    registry.register(ReferenceAnalyzer())
    return registry
