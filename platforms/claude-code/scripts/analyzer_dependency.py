"""QB dependency & supply-chain analyzer (Phase 2.4, opt-in networked).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
This closes Phase 2 with the one analyzer that legitimately wants a network, while
honoring the offline-core / opt-in-networked split (main-planning sections 5/7).

Two tiers:
  * OFFLINE tier (always runs): parses dependency manifests/lockfiles in the
    target repo and flags hygiene issues it can determine with no network --
    unpinned dependencies, and a manifest present without a lockfile.
  * NETWORKED tier (opt-in, OFF by default): only when ``config.allow_networked``
    is True AND an explicit ``advisory_source`` is configured does it enrich the
    inventory with advisory/CVE evidence and severity. It is fail-closed: if the
    flag is unset, no source is configured, or the source errors/raises, the
    analyzer completes successfully at the offline tier and records that
    enrichment was skipped (``last_enrichment_status``). The default path is
    provably network-free.

If a networked run ever shells out to an external scanner, it MUST use the
Phase-2.2 structured argv convention and never interpolate manifest content into a
command line. Advisory ids are public; no secret/credential is written.
"""

from __future__ import annotations

import importlib.util
import re
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


_ai = _load_sibling("qb_analyzer_interface", "analyzer_interface.py")
Analyzer = _ai.Analyzer
AnalyzerDescriptor = _ai.AnalyzerDescriptor
Finding = _ai.Finding
compute_finding_id = _ai.compute_finding_id

_LOCKFILES = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml")
_REQ_LINE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*(.*)$")
_ADVISORY_SEVERITY = {
    "critical": "P0",
    "high": "P1",
    "moderate": "P2",
    "medium": "P2",
    "low": "P3",
}


def parse_requirements(text: str) -> list:
    """Parse a requirements.txt body into dependency records (offline)."""
    deps = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        line = line.split(" #", 1)[0].strip()
        match = _REQ_LINE.match(line)
        if not match:
            continue
        name = match.group(1)
        spec = match.group(2).strip()
        deps.append({"name": name, "spec": spec, "line": line_number, "pinned": "==" in spec})
    return deps


class DependencyAnalyzer:
    """Offline dependency-hygiene audit with an opt-in, fail-closed networked tier."""

    descriptor = AnalyzerDescriptor(
        id="dependency-audit",
        categories=("dependency",),
        offline=True,  # base tier is offline; networking is internal opt-in
    )

    def __init__(self, advisory_source=None):
        # advisory_source: callable(name, spec) -> list[{"id":..., "severity":...}] or None
        self._advisory_source = advisory_source
        self.last_enrichment_status = "skipped:disabled"

    def _finding(self, category, severity, confidence, evidence, rule, rationale, suggested_fix):
        return Finding(
            id=compute_finding_id(category, evidence, rule),
            category=category,
            severity=severity,
            confidence=confidence,
            evidence=evidence,
            rationale=rationale,
            suggested_fix=suggested_fix,
            fix_strategy="manual",
        )

    def analyze(self, repo_root: str, config) -> list:
        root = Path(repo_root)
        findings: list = []
        inventory: list = []

        # --- Offline tier ----------------------------------------------------
        req_path = root / "requirements.txt"
        if req_path.is_file():
            try:
                text = req_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                text = ""
            for dep in parse_requirements(text):
                dep["evidence"] = f"requirements.txt:{dep['line']}"
                inventory.append(dep)
                if not dep["pinned"]:
                    findings.append(self._finding(
                        "dependency", "P2", "medium", dep["evidence"], f"unpinned:{dep['name']}",
                        f"Offline manifest audit: dependency '{dep['name']}' is not pinned to an exact "
                        f"version ({dep['spec'] or 'no version specifier'}).",
                        "Pin the dependency to an exact version (name==X.Y.Z) and commit a lockfile.",
                    ))

        pkg_path = root / "package.json"
        if pkg_path.is_file() and not any((root / lock).is_file() for lock in _LOCKFILES):
            findings.append(self._finding(
                "dependency", "P2", "medium", "package.json:1", "missing-lockfile",
                "Offline manifest audit: package.json is present but no lockfile "
                "(package-lock.json / yarn.lock / pnpm-lock.yaml) was found.",
                "Generate and commit a lockfile so dependency versions are reproducible.",
            ))

        # --- Networked tier (opt-in, fail-closed) ----------------------------
        allow_networked = bool(getattr(config, "allow_networked", False))
        if not allow_networked:
            self.last_enrichment_status = "skipped:disabled"
        elif self._advisory_source is None:
            self.last_enrichment_status = "skipped:no-source"
        else:
            try:
                for dep in inventory:
                    advisories = self._advisory_source(dep["name"], dep["spec"]) or []
                    for advisory in advisories:
                        advisory_id = str(advisory.get("id", "UNKNOWN"))
                        native = str(advisory.get("severity", "moderate")).lower()
                        severity = _ADVISORY_SEVERITY.get(native, "P2")
                        findings.append(self._finding(
                            "dependency", severity, "high", dep["evidence"],
                            f"cve:{dep['name']}:{advisory_id}",
                            f"Network-enriched: dependency '{dep['name']}' ({dep['spec'] or 'unpinned'}) "
                            f"is affected by advisory {advisory_id} (severity {native}).",
                            f"Upgrade '{dep['name']}' to a fixed version per advisory {advisory_id}.",
                        ))
                self.last_enrichment_status = "ran"
            except Exception as exc:  # fail closed to the offline tier; never abort
                self.last_enrichment_status = f"skipped:error:{type(exc).__name__}"

        findings.sort(key=lambda f: (f.severity, f.evidence, f.id))
        return findings
