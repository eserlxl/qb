"""Project conformant QB-Audit findings into planwright plan items.

The audit engine emits graded ``Finding`` records into ``QB-Audit/findings.jsonl``;
this module turns each into a planwright plan item in the exact ``export-planner.md``
OUTPUT FORMAT, so the highest-value hardening work flows through the same reviewed
planwright ``execute`` / ``cycle`` surface as planned work -- no second item format.
Standard library only (canonical host-neutral QB IP under ``shared/``).

Mapping (see README "Findings -> planwright items"):
- ``Mode`` -- a defect fix-strategy (autofix/propose/manual) whose evidence anchor
  resolves to an existing in-repo file maps to ``repair`` (carrying the ``path:line``
  anchor); otherwise ``improve``. ``fix-strategy: none`` is never repair.
- ``Surfaces`` -- the evidence locator's path. It must be a safe, existing repo file
  and must not be planning state.
- A finding anchored under ``.qb/`` or ``.planwright/`` is planning state, not an
  executable surface, and is NOT projected (returns ``None``).
"""

from __future__ import annotations

import sys
from importlib import util as _import_util
from pathlib import Path


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = _import_util.spec_from_file_location(module_name, path)
    module = _import_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_fs = _load_sibling("qb_finding_schema", "finding_schema.py")
_vpp = _load_sibling("qb_validate_planwright_plan", "validate_planwright_plan.py")
_store = _load_sibling("qb_run_store", "run_store.py")

Finding = _fs.Finding

# A defect fix-strategy may map to repair (when its anchor resolves); "none" never does.
DEFECT_STRATEGIES = frozenset({"autofix", "propose", "manual"})


def evidence_path(evidence: str) -> str:
    """The repo-relative path of a ``path:line`` / ``path:start-end`` locator."""
    text = (evidence or "").strip()
    return text.rsplit(":", 1)[0] if ":" in text else text


# Single source shared with the validator (validate_planwright_plan) so the projector
# and the lint gate can never drift on what counts as non-editable planning state.
is_planning_state_surface = _vpp.is_planning_state_surface


def infer_mode(finding, root: str) -> str:
    """``repair`` only when a defect fix-strategy has an evidence anchor resolving to an
    existing in-repo file; otherwise ``improve`` (mirrors planwright's repair grounding)."""
    path = evidence_path(finding.evidence)
    if (finding.fix_strategy in DEFECT_STRATEGIES
            and _vpp._EVIDENCE_ANCHOR_RE.search(finding.evidence or "")
            and path
            and not _vpp.unsafe_surface(path, root)
            and (Path(root) / path).is_file()):
        return "repair"
    return "improve"


def skip_reason(finding, root: str):
    """Why a finding is not projectable into a plan item, or ``None`` when it is. Lets a
    caller *report* a drop instead of silently losing it (the export-planner
    'list skipped' discipline)."""
    if isinstance(finding, dict):
        finding = Finding.from_dict(finding)
    path = evidence_path(finding.evidence)
    if not path:
        return "no evidence locator path to name as a Surface"
    if is_planning_state_surface(path):
        return (f"evidence is anchored in planning state ({path}); .qb/ and .planwright/ "
                "are context/evidence only, never editable item Surfaces")
    if _vpp.unsafe_surface(path, root):
        return f"evidence path is not a safe repo-relative Surface ({path})"
    if not (Path(root) / path).is_file():
        return f"evidence Surface does not exist under root ({path})"
    return None


def project_finding(finding, root: str):
    """Render one finding as a planwright item block, or ``None`` when it is not
    projectable (see :func:`skip_reason`)."""
    if isinstance(finding, dict):
        finding = Finding.from_dict(finding)
    if skip_reason(finding, root) is not None:
        return None
    path = evidence_path(finding.evidence)
    mode = infer_mode(finding, root)
    title = f"Resolve {finding.severity} {finding.category} finding {finding.id}"
    return "\n".join([
        f"- [ ] {title}",
        f"      Mode: {mode}",
        f"      Rationale: {finding.rationale}",
        f"      Evidence: {finding.evidence} — {finding.rationale}",
        f"      Surfaces: {path}",
        f"      Development: {finding.suggested_fix}",
        f"      Acceptance: the {finding.category} finding at {finding.evidence} "
        f"is resolved and no longer reported by a re-run audit.",
        "      Verification: python3 shared/scripts/qb_headless.py --root .",
    ])


def project_findings(findings, root: str, *, skipped=None) -> str:
    """Render findings as a planwright plan body (blank-line-separated item blocks). A
    finding that is not projectable is dropped; when ``skipped`` is a list, each drop is
    appended as ``(finding, reason)`` so it is reported, never silently lost."""
    blocks = []
    for finding in findings:
        f = Finding.from_dict(finding) if isinstance(finding, dict) else finding
        block = project_finding(f, root)
        if block is not None:
            blocks.append(block)
        elif skipped is not None:
            skipped.append((f, skip_reason(f, root)))
    return ("\n\n".join(blocks) + "\n") if blocks else ""


def load_findings(root: str, output_dir=None):
    """Load conformant findings from the run store under ``root`` (or ``output_dir``)."""
    out = Path(output_dir) if output_dir is not None else Path(root) / _store.OUTPUT_DIR_NAME
    return _store.RunStore(out).read_findings()
