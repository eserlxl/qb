"""QB license-hygiene analyzer (Phase 2 analyzer-suite completion, net-new).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).

This completes a wired-but-unproduced finding category. The frozen schema
(``finding_schema.py``) lists ``license`` in ``CATEGORIES`` and the fixer
(``fixer.py``) already binds ``license`` -> the ``license-review`` recipe, yet no
analyzer ever emitted a ``license`` finding -- so the category, and its recipe,
were dead. ``LicenseAnalyzer`` is the producer that makes them live.

It is an ordinary instance of the existing Phase-1.2 ``Analyzer`` contract
(read-only, offline, schema-conformant findings), not a new subsystem. It detects
the license-hygiene gaps an audit can establish deterministically from the tree
alone:

  * MISSING -- no recognizable license file at the repository root, so the
    project's distribution terms are unstated;
  * EMPTY -- a recognizable license file exists but is effectively empty (a
    placeholder), so the terms are still unstated; and
  * MANIFEST-UNDECLARED -- the repository root IS licensed, but a package
    manifest (``package.json`` / ``pyproject.toml`` / ``Cargo.toml``) declares a
    package yet omits its own license, so the published package would ship
    without stated terms. This compares package-level license declarations to the
    root license *presence* state (never to LICENSE file body text, which is not
    deterministically machine-readable).

License *choice* is a human decision, so every finding is ``manual`` (never
auto-applied), matching the fixer's conservative ``license-review`` recipe.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover - Python <3.11 fallback (no stdlib TOML)
    tomllib = None


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
validate_finding = _ai.validate_finding
confidence_for_rule = _core.confidence_for_rule
iter_repo_files = _core.iter_repo_files

# Recognized license-file stems (case-insensitive), with or without an extension:
# LICENSE, LICENCE, LICENSE.md, COPYING, COPYRIGHT, UNLICENSE, ...
_LICENSE_STEMS = frozenset({"license", "licence", "copying", "copyright", "unlicense"})

# A genuine license body is hundreds of bytes; below this it is a stub/placeholder.
_MIN_LICENSE_CHARS = 40

# Package manifests whose declared license is compared to the root license state,
# matched by EXACT basename only (never a heuristic JSON/TOML match) so an unrelated
# config file is never misread -- mirrors ContainerConfigAnalyzer's positive-id rule.
_MANIFEST_NAMES = frozenset({"package.json", "pyproject.toml", "Cargo.toml"})

# Path components that mark a manifest as sample/test data, not a published package;
# a manifest under any of these is never flagged (intentionally divergent demos).
_NON_PACKAGE_PARTS = frozenset({
    "fixtures", "fixture", "__fixtures__", "examples", "example",
    "testdata", "samples", "sample", "demo", "demos",
})


def _is_license_file(path: Path) -> bool:
    # Strip any extension (LICENSE.md, COPYING.txt), then match an exact stem or a
    # conventional dual-license variant (LICENSE-MIT, LICENSE-APACHE, COPYING-LESSER).
    # The "-" separator is required so an unrelated file like license_manager.py or
    # licensed.py is not mistaken for a license declaration.
    base = path.name.split(".", 1)[0].lower()
    return base in _LICENSE_STEMS or any(base.startswith(stem + "-") for stem in _LICENSE_STEMS)


def _is_sample_manifest(rel: str) -> bool:
    return any(part in _NON_PACKAGE_PARTS for part in rel.split("/"))


def _nonempty_str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _json_loads(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _toml_loads(text: str):
    if tomllib is None:  # Python <3.11: cannot parse TOML deterministically -> no finding
        return None
    try:
        return tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError):
        return None


def _package_json_has_license(data: dict) -> bool:
    lic = data.get("license")
    # An SPDX string, a deprecated {type,url} object, the legacy `licenses` array,
    # and the "SEE LICENSE IN <file>" / "UNLICENSED" sentinels all count as a
    # present declaration (the package author stated *something*).
    if _nonempty_str(lic):
        return True
    if isinstance(lic, dict) and lic:
        return True
    licenses = data.get("licenses")
    return isinstance(licenses, list) and len(licenses) > 0


def _pyproject_has_license(project: dict, poetry: dict) -> bool:
    dynamic = project.get("dynamic")
    if isinstance(dynamic, list) and ("license" in dynamic or "license-files" in dynamic):
        # PEP 621 deferred declaration: the build backend supplies the license at
        # build time (e.g. [tool.setuptools.dynamic] license = {file = "LICENSE"}).
        # It is an explicit "license IS declared", so the manifest stays silent.
        return True
    lic = project.get("license")
    if _nonempty_str(lic):  # PEP 639 SPDX-expression string
        return True
    if isinstance(lic, dict) and (lic.get("text") or lic.get("file")):  # {text=}/{file=}
        return True
    if project.get("license-files"):
        return True
    classifiers = project.get("classifiers")
    if isinstance(classifiers, list) and any(
        isinstance(item, str) and item.startswith("License ::") for item in classifiers
    ):
        return True
    return _nonempty_str(poetry.get("license"))


def _cargo_has_license(package: dict) -> bool:
    lic = package.get("license")
    if _nonempty_str(lic):  # SPDX expression string
        return True
    if isinstance(lic, dict) and lic.get("workspace") is True:  # inherits [workspace.package]
        return True
    return _nonempty_str(package.get("license-file"))


def _manifest_undeclares_license(name: str, text: str) -> bool:
    """True iff ``text`` is a package manifest of type ``name`` that declares a
    real package but no license, and is not private/unpublished. Any parse error,
    missing package identity, or unrecognized form degrades to False (no finding):
    the rule stays silent unless the omission is deterministically certain."""
    if name == "package.json":
        data = _json_loads(text)
        if not isinstance(data, dict) or not _nonempty_str(data.get("name")):
            return False  # unparseable or no package identity (workspace root / app shell)
        if data.get("private") is True or data.get("workspaces"):
            # private, or an npm monorepo umbrella root (a `workspaces` array/object
            # is never itself published) -- not a distributable package.
            return False
        return not _package_json_has_license(data)
    if name == "pyproject.toml":
        data = _toml_loads(text)
        if not isinstance(data, dict):
            return False
        project = data.get("project") if isinstance(data.get("project"), dict) else {}
        tool = data.get("tool") if isinstance(data.get("tool"), dict) else {}
        poetry = tool.get("poetry") if isinstance(tool.get("poetry"), dict) else {}
        if not project and not poetry:
            return False  # build-backend-only config, not a distributable package
        if not (_nonempty_str(project.get("name")) or _nonempty_str(poetry.get("name"))):
            return False  # dynamic/inherited name: identity is ambiguous -> stay silent
        return not _pyproject_has_license(project, poetry)
    if name == "Cargo.toml":
        data = _toml_loads(text)
        if not isinstance(data, dict):
            return False
        package = data.get("package") if isinstance(data.get("package"), dict) else None
        if package is None or not _nonempty_str(package.get("name")):
            return False  # virtual/workspace-only or inherited-name crate -> stay silent
        publish = package.get("publish")
        if publish is False or publish == []:
            return False  # unpublished crate (publish=false or an empty registry allow-list)
        return not _cargo_has_license(package)
    return False


class LicenseAnalyzer:
    """Read-only analyzer: flags missing/empty root license and undeclared package
    manifests in an otherwise-licensed repository."""

    descriptor = AnalyzerDescriptor(
        id="license-hygiene",
        categories=("license",),
        offline=True,
    )

    _RULE_MISSING = "no-license-file"
    _RULE_EMPTY = "empty-license-file"
    _RULE_MANIFEST_UNDECLARED = "manifest-undeclared-license"

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
            # The root is unlicensed: this single finding states the gap, so we do
            # NOT also walk package manifests (the root rule already covers it).
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

        # The root is licensed: a package manifest that declares a package but omits
        # its own license would ship without stated terms -- flag each such manifest.
        findings.extend(self._manifest_findings(root, config))
        return findings

    def _manifest_findings(self, root: Path, config) -> list:
        base = root.resolve()
        out: list = []
        for path in iter_repo_files(base, config):
            if path.name not in _MANIFEST_NAMES:
                continue
            rel = path.relative_to(base).as_posix()
            if _is_sample_manifest(rel):
                continue
            try:
                # utf-8-sig strips a leading BOM (common in Windows-emitted
                # manifests, which npm/cargo/pip accept) so a BOM-prefixed but
                # otherwise valid manifest parses instead of being silently skipped.
                text = path.read_text(encoding="utf-8-sig")
            except (UnicodeDecodeError, OSError):
                continue
            if not _manifest_undeclares_license(path.name, text):
                continue
            evidence = f"{rel}:1"
            finding = Finding(
                id=compute_finding_id("license", evidence, self._RULE_MANIFEST_UNDECLARED),
                category="license",
                severity="P3",
                confidence=confidence_for_rule(self.descriptor.id, "manifest-undeclared-license"),
                evidence=evidence,
                rationale=(
                    f"The package manifest {rel} declares a package but no license, while "
                    "the repository root is licensed; the published package would ship "
                    "without its own stated distribution terms."
                ),
                suggested_fix=(
                    "Declare the package license in the manifest (an SPDX 'license' field) "
                    "matching the project's intended terms; license choice needs a human."
                ),
                fix_strategy="manual",
            )
            # A non-conformant locator (e.g. a spaced/odd directory in the path) must
            # never enter the store; emit only conformant findings.
            if validate_finding(finding):
                continue
            out.append(finding)
        out.sort(key=lambda item: (item.evidence, item.id))
        return out
