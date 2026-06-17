"""QB license-hygiene analyzer (Phase 2 analyzer-suite completion, net-new).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).

This completes a wired-but-unproduced finding category. The frozen schema
(``finding_schema.py``) lists ``license`` in ``CATEGORIES`` and the fixer
(``fixer.py``) already binds ``license`` -> the ``license-review`` recipe, yet no
analyzer ever emitted a ``license`` finding -- so the category, and its recipe,
were dead. ``LicenseAnalyzer`` is the producer that makes them live.

It is an ordinary instance of the existing Phase-1.2 ``Analyzer`` contract
(read-only, offline, schema-conformant findings), not a new subsystem. It detects
the two license-hygiene gaps an audit can establish deterministically from the
tree alone:

  * MISSING -- no recognizable license file at the repository root, so the
    project's distribution terms are unstated; and
  * EMPTY -- a recognizable license file exists but is effectively empty (a
    placeholder), so the terms are still unstated.

License *choice* is a human decision, so every finding is ``manual`` (never
auto-applied), matching the fixer's conservative ``license-review`` recipe.
"""

from __future__ import annotations

import importlib.util
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
_core = _load_sibling("qb_analyzer_core", "analyzer_core.py")
AnalyzerDescriptor = _ai.AnalyzerDescriptor
Finding = _ai.Finding
compute_finding_id = _ai.compute_finding_id
confidence_for_rule = _core.confidence_for_rule

# Recognized license-file stems (case-insensitive), with or without an extension:
# LICENSE, LICENCE, LICENSE.md, COPYING, COPYRIGHT, UNLICENSE, ...
_LICENSE_STEMS = frozenset({"license", "licence", "copying", "copyright", "unlicense"})

# A genuine license body is hundreds of bytes; below this it is a stub/placeholder.
_MIN_LICENSE_CHARS = 40


def _is_license_file(path: Path) -> bool:
    # Strip any extension (LICENSE.md, COPYING.txt), then match an exact stem or a
    # conventional dual-license variant (LICENSE-MIT, LICENSE-APACHE, COPYING-LESSER).
    # The "-" separator is required so an unrelated file like license_manager.py or
    # licensed.py is not mistaken for a license declaration.
    base = path.name.split(".", 1)[0].lower()
    return base in _LICENSE_STEMS or any(base.startswith(stem + "-") for stem in _LICENSE_STEMS)


class LicenseAnalyzer:
    """Read-only analyzer: flags a missing or empty repository-root license file."""

    descriptor = AnalyzerDescriptor(
        id="license-hygiene",
        categories=("license",),
        offline=True,
    )

    _RULE_MISSING = "no-license-file"
    _RULE_EMPTY = "empty-license-file"

    def analyze(self, repo_root: str, config) -> list:
        root = Path(repo_root)
        license_files = (
            [p for p in sorted(root.iterdir()) if p.is_file() and _is_license_file(p)]
            if root.is_dir()
            else []
        )
        findings: list = []

        if not license_files:
            # Point at the canonical expected location, NOT the repo-root sentinel
            # ".:1" (which is reserved for the interface ReferenceAnalyzer no-op).
            evidence = "LICENSE:1"
            findings.append(
                Finding(
                    id=compute_finding_id("license", evidence, self._RULE_MISSING),
                    category="license",
                    severity="P2",
                    confidence=confidence_for_rule(self.descriptor.id, "missing-license"),
                    evidence=evidence,
                    rationale=(
                        "No license file (LICENSE / LICENCE / COPYING / UNLICENSE) was found "
                        "at the repository root; the project's distribution terms are unstated."
                    ),
                    suggested_fix=(
                        "Add a license file at the repository root declaring the intended "
                        "terms (e.g. MIT, Apache-2.0, GPL-3.0); license choice needs a human."
                    ),
                    fix_strategy="manual",
                )
            )
            return findings

        for path in license_files:
            try:
                body = path.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
            if len(body) < _MIN_LICENSE_CHARS:
                rel = path.relative_to(root).as_posix()
                evidence = f"{rel}:1"
                findings.append(
                    Finding(
                        id=compute_finding_id("license", evidence, self._RULE_EMPTY),
                        category="license",
                        severity="P2",
                        confidence=confidence_for_rule(self.descriptor.id, "empty-license"),
                        evidence=evidence,
                        rationale=(
                            f"The license file {rel} is effectively empty "
                            f"({len(body)} non-whitespace characters); the terms are not stated."
                        ),
                        suggested_fix=(
                            "Populate the license file with the full text of the chosen license."
                        ),
                        fix_strategy="manual",
                    )
                )
        return findings
