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
AnalyzerDescriptor = _ai.AnalyzerDescriptor
Finding = _ai.Finding
compute_finding_id = _ai.compute_finding_id

# A dotenv file: ".env" or ".env.<suffix>" (e.g. .env.local, .env.production).
_ENV_NAME_RE = re.compile(r"^\.env(?:\.[A-Za-z0-9_-]+)?$")
# Legitimate, commit-safe templates -- never flagged.
_TEMPLATE_SUFFIXES = frozenset({"example", "sample", "template", "dist", "defaults"})
# Directories an audit should never descend into for this check.
_SKIP_DIRS = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"})


def _is_committed_env(path: Path) -> bool:
    name = path.name
    if not _ENV_NAME_RE.match(name):
        return False
    # ".env" -> "env"; ".env.local" -> "local"; ".env.example" -> "example".
    suffix = name.rsplit(".", 1)[-1].lower()
    return suffix not in _TEMPLATE_SUFFIXES


class ConfigHygieneAnalyzer:
    """Read-only analyzer: flags a present, non-template dotenv config file."""

    descriptor = AnalyzerDescriptor(
        id="config-hygiene",
        categories=("config",),
        offline=True,
    )

    _RULE = "committed-dotenv-file"

    def analyze(self, repo_root: str, config) -> list:
        root = Path(repo_root)
        findings: list = []
        if not root.is_dir():
            return findings
        for path in sorted(root.rglob("*")):
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            if not path.is_file() or not _is_committed_env(path):
                continue
            rel = path.relative_to(root).as_posix()
            evidence = f"{rel}:1"
            findings.append(
                Finding(
                    id=compute_finding_id("config", evidence, self._RULE),
                    category="config",
                    severity="P2",
                    confidence="medium",
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
            )
        return findings
