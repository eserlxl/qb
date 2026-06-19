"""QB config-hygiene analyzer (Phase 2 analyzer-suite completion, net-new).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).

This completes the last wired-but-unproduced finding category. The frozen schema
(``finding_schema.py``) lists ``config`` in ``CATEGORIES`` and the fixer
(``fixer.py``) binds ``config`` -> the ``config-review`` recipe, yet the only
analyzer declaring the category was the no-op ``ReferenceAnalyzer`` (deliberately
excluded from the default registry), so a real audit never produced a ``config``
finding. ``ConfigHygieneAnalyzer`` is the producer that makes the category live.

It is an ordinary instance of the existing read-only ``Analyzer`` contract (not a
new subsystem). It flags a deterministic, low-noise config-hygiene gap: a present
dotenv-style file (``.env`` / ``.env.<env>``) that is NOT a template
(``.env.example`` / ``.env.sample`` / ``.env.template`` / ``.env.dist``). Such
files commonly carry deployment config or secrets and should be gitignored, not
committed. Config remediation is a human decision, so findings are ``manual``.
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
_core = _load_sibling("qb_analyzer_core", "analyzer_core.py")
AnalyzerDescriptor = _ai.AnalyzerDescriptor
Finding = _ai.Finding
compute_finding_id = _ai.compute_finding_id
validate_finding = _ai.validate_finding
iter_repo_files = _core.iter_repo_files
confidence_for_rule = _core.confidence_for_rule

# A dotenv file: ".env" or ".env.<seg>[.<seg>...]" (e.g. .env.local, .env.production,
# .env.production.local -- Next.js/CRA layer their secrets across multiple segments).
_ENV_NAME_RE = re.compile(r"^\.env(?:\.[A-Za-z0-9_-]+)*$")
# Legitimate, commit-safe templates -- never flagged.
_TEMPLATE_SUFFIXES = frozenset({"example", "sample", "template", "dist", "defaults"})
_NPMRC_CREDENTIAL_KEYS = frozenset({"_authtoken", "_password", "username", "email"})


def _is_committed_env(path: Path) -> bool:
    name = path.name
    if not _ENV_NAME_RE.match(name):
        return False
    # ".env" -> "env"; ".env.local" -> "local"; ".env.example" -> "example".
    suffix = name.rsplit(".", 1)[-1].lower()
    return suffix not in _TEMPLATE_SUFFIXES


def _is_template_name(path: Path) -> bool:
    suffix = path.name.rsplit(".", 1)[-1].lower()
    return suffix in _TEMPLATE_SUFFIXES


def _npmrc_credential_lines(text: str) -> list[int]:
    lines: list[int] = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip().lower()
        key = key.rsplit(":", 1)[-1]
        if key in _NPMRC_CREDENTIAL_KEYS:
            lines.append(line_number)
    return lines


class ConfigHygieneAnalyzer:
    """Read-only analyzer: flags a present, non-template dotenv config file."""

    descriptor = AnalyzerDescriptor(
        id="config-hygiene",
        categories=("config",),
        offline=True,
    )

    _RULE_ENV = "committed-dotenv-file"
    _RULE_NPMRC = "committed-npmrc-credential-key"

    def analyze(self, repo_root: str, config) -> list:
        root = Path(repo_root).resolve()
        findings: list = []
        if not root.is_dir():
            return findings
        for path in iter_repo_files(root, config):
            rel_path = path.relative_to(root)
            if not _is_committed_env(path):
                continue
            rel = rel_path.as_posix()
            evidence = f"{rel}:1"
            finding = Finding(
                id=compute_finding_id("config", evidence, self._RULE_ENV),
                category="config",
                severity="P2",
                confidence=confidence_for_rule(self.descriptor.id, "committed-config"),
                evidence=evidence,
                rationale=(
                    f"A dotenv-style config file ({rel}) is present in the tree; "
                    "environment files commonly carry deployment config or secrets "
                    "and should be gitignored, not committed."
                ),
                suggested_fix=(
                    "Move real values into the deployment environment or a secret "
                    "manager and gitignore this file; keep only a .env.example template."
                ),
                fix_strategy="manual",
            )
            # A locator with whitespace (a spaced directory in the path) is not
            # schema-conformant; emit only conformant findings so the store never
            # carries a record that downstream validation would reject.
            if validate_finding(finding):
                continue
            findings.append(finding)

        for path in iter_repo_files(root, config):
            rel_path = path.relative_to(root)
            if path.name != ".npmrc" or _is_template_name(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            rel = rel_path.as_posix()
            for line in _npmrc_credential_lines(text):
                evidence = f"{rel}:{line}"
                finding = Finding(
                    id=compute_finding_id("config", evidence, self._RULE_NPMRC),
                    category="config",
                    severity="P2",
                    confidence=confidence_for_rule(self.descriptor.id, "committed-config"),
                    evidence=evidence,
                    rationale=(
                        f"An npm config file ({rel}) contains a credential-bearing key; "
                        "committed package-manager auth config can expose registry credentials."
                    ),
                    suggested_fix=(
                        "Move registry credentials to the user or CI environment and keep only "
                        "non-secret registry configuration in the repository."
                    ),
                    fix_strategy="manual",
                )
                if validate_finding(finding):
                    continue
                findings.append(finding)
        findings.sort(key=lambda item: (item.evidence, item.id))
        return findings
