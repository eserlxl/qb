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
import json
import re
import sys
from pathlib import Path
try:
    import tomllib
except ImportError:  # pragma: no cover - Python <3.11 fallback
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
Analyzer = _ai.Analyzer
AnalyzerDescriptor = _ai.AnalyzerDescriptor
Finding = _ai.Finding
compute_finding_id = _ai.compute_finding_id
confidence_for_rule = _core.confidence_for_rule

_LOCKFILES = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml")
# Recognized Python lockfiles: a pyproject.toml that declares dependencies but
# ships none of these has non-reproducible installs (mirrors the npm/cargo checks).
_PY_LOCKFILES = ("poetry.lock", "pdm.lock", "uv.lock", "Pipfile.lock")
_REQ_LINE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*(.*)$")
# pip VCS / direct-URL requirements (git+https://..., https://...#egg=name): the
# `_REQ_LINE` name regex would split the scheme into a bogus "git" dependency, so
# detect and skip these -- a VCS/URL requirement carries no PyPI registry version
# to pin and is not an unpinned-dependency finding.
_URL_REQUIREMENT_RE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9.+-]*\+)?(?:https?|git|ssh|file|hg|svn|bzr)://", re.IGNORECASE)
_EXACT_VERSION_RE = re.compile(r"^\s*\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?\s*$")
_ADVISORY_SEVERITY = {
    "critical": "P0",
    "high": "P1",
    "moderate": "P2",
    "medium": "P2",
    "low": "P3",
}


def _is_exact_pin(spec: str) -> bool:
    spec = (spec or "").strip()
    return "==" in spec or "===" in spec or bool(_EXACT_VERSION_RE.match(spec))


def _is_cargo_exact_pin(spec: str) -> bool:
    # Cargo semantics differ from pip/npm: a bare "1.2.3" is a caret range
    # (^1.2.3), so ONLY a leading "=" is an exact version requirement. "*",
    # "^", "~", ">=" etc. are ranges. (This is the inverse of _is_exact_pin,
    # which treats a bare exact version as pinned.)
    spec = (spec or "").strip()
    return bool(re.match(r"^=\s*\d+(?:\.\d+)*(?:[-+][0-9A-Za-z.-]+)?$", spec))


def _is_npm_nonregistry(spec: str) -> bool:
    # An npm spec pointing outside the registry -- git+/github:/gitlab:/file:/link:/
    # portal:/workspace:/http(s):// , an npm: alias, or a "user/repo" shorthand --
    # carries no registry version to pin. A registry version or range never contains
    # "/" or ":", so their presence marks a non-registry spec to skip (mirrors the
    # pip VCS/URL skip), rather than flag it "unpinned".
    spec = (spec or "").strip()
    return "/" in spec or ":" in spec


def _line_for_token(text: str, token: str, start: int = 1) -> int:
    for line_number, raw in enumerate(text.splitlines(), start=1):
        if line_number >= start and token in raw:
            return line_number
    return start


def parse_requirements(text: str) -> list:
    """Parse a requirements.txt body into dependency records (offline)."""
    deps = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        if _URL_REQUIREMENT_RE.match(line):
            continue  # VCS/URL requirement: no PyPI version to pin, not a "git" dep
        line = line.split(" #", 1)[0].strip()
        match = _REQ_LINE.match(line)
        if not match:
            continue
        name = match.group(1)
        spec = match.group(2).strip()
        deps.append({"name": name, "spec": spec, "line": line_number, "pinned": _is_exact_pin(spec)})
    return deps


def parse_pyproject(text: str) -> list:
    """Parse pyproject.toml dependency declarations into dependency records."""
    if tomllib is None:
        return []
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []

    deps: list = []
    project = data.get("project", {}) if isinstance(data, dict) else {}
    if not isinstance(project, dict):
        project = {}  # a TOML-valid scalar `project = "x"` must not crash the audit
    raw_entries = project.get("dependencies", []) or []
    entries = list(raw_entries) if isinstance(raw_entries, list) else []
    optional = project.get("optional-dependencies", {}) or {}
    if isinstance(optional, dict):
        for group_entries in optional.values():
            if isinstance(group_entries, list):
                entries.extend(group_entries)
    for entry in entries:
        if not isinstance(entry, str):
            continue
        parsed = _REQ_LINE.match(entry)
        if not parsed:
            continue
        name = parsed.group(1)
        spec = parsed.group(2).strip()
        deps.append({
            "name": name,
            "spec": spec,
            "line": _line_for_token(text, entry),
            "pinned": _is_exact_pin(spec),
        })

    tool = data.get("tool", {})
    tool = tool if isinstance(tool, dict) else {}  # `tool = "x"` scalar must not crash
    poetry_tool = tool.get("poetry", {})
    poetry_tool = poetry_tool if isinstance(poetry_tool, dict) else {}
    poetry = poetry_tool.get("dependencies", {})
    if isinstance(poetry, dict):
        for name, raw_spec in sorted(poetry.items()):
            if str(name).lower() == "python":
                continue
            if isinstance(raw_spec, str):
                spec = raw_spec
            elif isinstance(raw_spec, dict):
                # A poetry git/path dependency (inline table without a version)
                # carries no registry version to pin; skip it rather than emit a
                # bogus unpinned finding (mirrors parse_cargo's git/path skip).
                if "version" not in raw_spec:
                    continue
                spec = str(raw_spec.get("version", ""))
            else:
                spec = str(raw_spec)
            deps.append({
                "name": str(name),
                "spec": spec,
                "line": _line_for_token(text, str(name)),
                "pinned": _is_exact_pin(spec),
            })

    # PEP 735 dependency groups ([dependency-groups]). Each group is a list of
    # PEP 508 requirement strings (or {"include-group": ...} table references,
    # which carry no version and are skipped).
    groups = data.get("dependency-groups", {})
    if isinstance(groups, dict):
        for group_entries in groups.values():
            if not isinstance(group_entries, list):
                continue
            for entry in group_entries:
                if not isinstance(entry, str):
                    continue
                parsed = _REQ_LINE.match(entry)
                if not parsed:
                    continue
                name = parsed.group(1)
                spec = parsed.group(2).strip()
                deps.append({
                    "name": name,
                    "spec": spec,
                    "line": _line_for_token(text, entry),
                    "pinned": _is_exact_pin(spec),
                })
    return deps


def parse_package_json(text: str) -> list:
    """Parse bounded npm dependency sections into dependency records."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []

    deps: list = []
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        entries = data.get(section, {})
        if not isinstance(entries, dict):
            continue
        for name, raw_spec in sorted(entries.items()):
            if not isinstance(name, str):
                continue
            spec = raw_spec if isinstance(raw_spec, str) else str(raw_spec)
            if _is_npm_nonregistry(spec):
                continue  # git/file/link/workspace/url/alias dep: no registry version to pin
            deps.append({
                "name": name,
                "spec": spec,
                "section": section,
                "line": _line_for_token(text, f'"{name}"'),
                "pinned": _is_exact_pin(spec),
            })
    return deps


_CARGO_DEP_KINDS = ("dependencies", "dev-dependencies", "build-dependencies")


def _cargo_table_deps(text: str, entries, section: str) -> list:
    """Extract dependency records from one Cargo dependency table (offline)."""
    deps: list = []
    if not isinstance(entries, dict):
        return deps
    for name, raw_spec in sorted(entries.items()):
        if not isinstance(name, str):
            continue
        if isinstance(raw_spec, str):
            spec = raw_spec
        elif isinstance(raw_spec, dict):
            # A path/git dependency carries no registry version to pin; skip.
            if "version" not in raw_spec:
                continue
            spec = str(raw_spec.get("version", ""))
        else:
            continue
        deps.append({
            "name": name,
            "spec": spec,
            "section": section,
            "line": _line_for_token(text, name),
            "pinned": _is_cargo_exact_pin(spec),
        })
    return deps


def parse_cargo(text: str) -> list:
    """Parse Cargo.toml dependency tables into dependency records (offline)."""
    if tomllib is None:
        return []
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    if not isinstance(data, dict):
        return []

    deps: list = []
    for section in _CARGO_DEP_KINDS:
        deps.extend(_cargo_table_deps(text, data.get(section, {}), section))

    # Workspace-level declarations ([workspace.dependencies]) — inherited by members.
    workspace = data.get("workspace", {})
    if isinstance(workspace, dict):
        deps.extend(_cargo_table_deps(text, workspace.get("dependencies", {}), "workspace.dependencies"))

    # Platform/target-specific tables ([target.<cfg>.<kind>]).
    target = data.get("target", {})
    if isinstance(target, dict):
        for cfg, cfg_table in sorted(target.items()):
            if not isinstance(cfg, str) or not isinstance(cfg_table, dict):
                continue
            for kind in _CARGO_DEP_KINDS:
                deps.extend(_cargo_table_deps(text, cfg_table.get(kind, {}), f"target({cfg}).{kind}"))
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
                        "dependency", "P2", confidence_for_rule(self.descriptor.id, "manifest-hygiene"),
                        dep["evidence"], f"unpinned:{dep['name']}",
                        f"Offline manifest audit: dependency '{dep['name']}' is not pinned to an exact "
                        f"version ({dep['spec'] or 'no version specifier'}).",
                        "Pin the dependency to an exact version (name==X.Y.Z) and commit a lockfile.",
                    ))

        pyproject_path = root / "pyproject.toml"
        if pyproject_path.is_file():
            try:
                text = pyproject_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                text = ""
            pyproject_deps = parse_pyproject(text)
            for dep in pyproject_deps:
                dep["evidence"] = f"pyproject.toml:{dep['line']}"
                inventory.append(dep)
                if not dep["pinned"]:
                    findings.append(self._finding(
                        "dependency", "P2", confidence_for_rule(self.descriptor.id, "manifest-hygiene"),
                        dep["evidence"],
                        f"unpinned-pyproject:{dep['name']}",
                        f"Offline pyproject audit: dependency '{dep['name']}' is not pinned to an "
                        f"exact version ({dep['spec'] or 'no version specifier'}).",
                        "Pin the dependency to an exact version in pyproject.toml and regenerate the lockfile.",
                    ))
            if pyproject_deps and not any((root / lock).is_file() for lock in _PY_LOCKFILES):
                findings.append(self._finding(
                    "dependency", "P2", confidence_for_rule(self.descriptor.id, "manifest-hygiene"),
                    "pyproject.toml:1", "missing-python-lockfile",
                    "Offline manifest audit: pyproject.toml declares dependencies but no Python "
                    "lockfile (poetry.lock / pdm.lock / uv.lock / Pipfile.lock) was found, so the "
                    "resolved dependency versions are not reproducible.",
                    "Generate and commit a lockfile (e.g. `poetry lock`, `pdm lock`, or `uv lock`).",
                ))

        pkg_path = root / "package.json"
        if pkg_path.is_file():
            try:
                text = pkg_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                text = ""
            for dep in parse_package_json(text):
                dep["evidence"] = f"package.json:{dep['line']}"
                inventory.append(dep)
                if not dep["pinned"]:
                    findings.append(self._finding(
                        "dependency",
                        "P2",
                        confidence_for_rule(self.descriptor.id, "manifest-hygiene"),
                        dep["evidence"],
                        f"unpinned-package-json:{dep['section']}:{dep['name']}",
                        f"Offline package.json audit: {dep['section']} dependency '{dep['name']}' "
                        f"is not pinned to an exact version ({dep['spec'] or 'no version specifier'}).",
                        "Pin the package dependency to an exact version and regenerate the lockfile.",
                    ))
        if pkg_path.is_file() and not any((root / lock).is_file() for lock in _LOCKFILES):
            findings.append(self._finding(
                "dependency", "P2", confidence_for_rule(self.descriptor.id, "manifest-hygiene"),
                "package.json:1", "missing-lockfile",
                "Offline manifest audit: package.json is present but no lockfile "
                "(package-lock.json / yarn.lock / pnpm-lock.yaml) was found.",
                "Generate and commit a lockfile so dependency versions are reproducible.",
            ))

        cargo_path = root / "Cargo.toml"
        if cargo_path.is_file():
            try:
                text = cargo_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                text = ""
            for dep in parse_cargo(text):
                dep["evidence"] = f"Cargo.toml:{dep['line']}"
                inventory.append(dep)
                if not dep["pinned"]:
                    findings.append(self._finding(
                        "dependency", "P2", confidence_for_rule(self.descriptor.id, "manifest-hygiene"),
                        dep["evidence"],
                        f"unpinned-cargo:{dep['section']}:{dep['name']}",
                        f"Offline Cargo.toml audit: {dep['section']} dependency '{dep['name']}' is not "
                        f"pinned to an exact version ({dep['spec'] or 'no version specifier'}); a bare, "
                        f"caret, or wildcard spec can resolve to a different version over time.",
                        "Pin the dependency to an exact version (=X.Y.Z) and commit Cargo.lock.",
                    ))
        if cargo_path.is_file() and not (root / "Cargo.lock").is_file():
            findings.append(self._finding(
                "dependency", "P2", confidence_for_rule(self.descriptor.id, "manifest-hygiene"),
                "Cargo.toml:1", "missing-cargo-lockfile",
                "Offline manifest audit: Cargo.toml is present but no Cargo.lock was found, "
                "so the resolved dependency versions are not reproducible.",
                "Run `cargo generate-lockfile` (or `cargo build`) and commit Cargo.lock.",
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
                            "dependency", severity, confidence_for_rule(self.descriptor.id, "network-advisory"),
                            dep["evidence"],
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
