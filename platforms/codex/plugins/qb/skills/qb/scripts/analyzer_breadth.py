"""Additional offline analyzers for ecosystem breadth.

The first breadth analyzer covers CI workflow dependencies. It scans GitHub
Actions workflow files for remote `uses:` entries pinned only to a broad branch
or major tag, and reports them as dependency findings. It is deliberately
stdlib-only and read-only, matching the core analyzer contract.
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

_USES_RE = re.compile(r"^\s*-\s*uses\s*:\s*['\"]?(?P<spec>[^'\"\s#]+)")
_FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_FULL_SEMVER_RE = re.compile(r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def _is_workflow_file(root: Path, path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    parts = rel.parts
    return (
        len(parts) >= 3
        and parts[0] == ".github"
        and parts[1] == "workflows"
        and path.suffix.lower() in (".yml", ".yaml")
    )


def _split_action_ref(spec: str):
    if spec.startswith("./") or spec.startswith("docker://"):
        return None
    if "@" not in spec:
        return (spec, "")
    action, ref = spec.rsplit("@", 1)
    if not action or "/" not in action:
        return None
    return (action, ref)


def _is_broad_ref(ref: str) -> bool:
    if not ref:
        return True
    if _FULL_SHA_RE.match(ref):
        return False
    if _FULL_SEMVER_RE.match(ref):
        return False
    return True


class WorkflowActionAnalyzer:
    """Read-only analyzer for broadly pinned GitHub Actions dependencies."""

    descriptor = AnalyzerDescriptor(
        id="workflow-actions",
        categories=("dependency",),
        offline=True,
    )

    _RULE = "github-action-broad-ref"

    def analyze(self, repo_root: str, config) -> list:
        root = Path(repo_root).resolve()
        findings: list = []
        for path in iter_repo_files(root):
            if not _is_workflow_file(root, path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            rel = path.relative_to(root).as_posix()
            for line_number, raw in enumerate(text.splitlines(), start=1):
                match = _USES_RE.match(raw)
                if not match:
                    continue
                spec = match.group("spec")
                parsed = _split_action_ref(spec)
                if parsed is None:
                    continue
                action, ref = parsed
                if not _is_broad_ref(ref):
                    continue
                evidence = f"{rel}:{line_number}"
                ref_text = ref or "no ref"
                finding = Finding(
                    id=compute_finding_id("dependency", evidence, self._RULE),
                    category="dependency",
                    severity="P2",
                    confidence="medium",
                    evidence=evidence,
                    rationale=(
                        f"GitHub Actions dependency '{action}' uses a broad ref "
                        f"({ref_text}); broad tags and branches can drift between runs."
                    ),
                    suggested_fix=(
                        "Pin the action to an immutable commit SHA or an explicit full "
                        "version tag and review updates intentionally."
                    ),
                    fix_strategy="manual",
                )
                if validate_finding(finding):
                    continue
                findings.append(finding)
        findings.sort(key=lambda item: (item.evidence, item.id))
        return findings
