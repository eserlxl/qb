"""QB fix-planning contract -- bind a Finding to a bounded fix plan (Phase 3.1).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
This is the finding-driven successor to the slice-driven discipline in
``shared/planners/fourth-planner.md``: where that spec selects a plan slice from
``sub-planning-audit.md``, this contract takes a single Phase-1 ``Finding`` and
produces a deterministic ``FixPlan`` -- the bound fix recipe, the verification
command chosen FIRST (before any edit), and whether the finding may be
auto-applied or must be proposed for human review.

It performs NO writes and runs NO commands. Phase 3.2 (isolation + rollback) and
Phase 3.3 (verification gate, keep/revert) consume the ``FixPlan`` this produces.

Contract summary
----------------
- BINDING (category -> recipe): every Finding category resolves to one named
  recipe; an unmapped category falls back to ``manual-review`` (propose-only).
- VERIFICATION COMMAND (chosen first, argv form, existing commands preferred):
  ``make test`` -> ``make check`` -> ``python3 -m unittest discover -s tests`` ->
  None. A finding whose repo yields no verify command is never auto-fixable.
- AUTO-FIXABLE vs PROPOSE-ONLY: conservative. Only categories in
  ``AUTO_FIXABLE`` may auto-apply, and only when (a) a verify command is
  derivable AND (b) the finding's confidence meets the category's floor.
  Everything else -- secrets, injection, traversal, correctness, dependencies --
  is propose-only, because applying those without human judgment is the
  "confidently-wrong autofix" risk this contract exists to prevent.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
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
Finding = _ai.Finding
compute_finding_id = _ai.compute_finding_id

# category -> named fix recipe
RECIPE_BINDING = {
    "secret": "remove-committed-secret-reference",
    "injection": "shell-string-to-argv",
    "path-traversal": "path-traversal-guard",
    "quality": "lint-autofix",
    "correctness": "manual-correctness-review",
    "dependency": "pin-or-upgrade-dependency",
    "license": "license-review",
    "config": "config-review",
}
_FALLBACK_RECIPE = "manual-review"

# category -> (auto_fixable, confidence_floor, rationale). Absent => propose-only.
AUTO_FIXABLE = {
    "quality": (True, "medium",
                "Lint autofixes are mechanical and are gated by a verification command."),
}

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}

_MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9_.\-]+)\s*:", re.MULTILINE)


@dataclass
class FixPlan:
    finding: object
    recipe: str
    verify_command: list | None   # argv list, or None when no command is derivable
    mode: str                     # "autofix" or "propose"
    reason: str


def _make_targets(makefile_text: str) -> set:
    return set(_MAKE_TARGET_RE.findall(makefile_text))


def select_verify_command(repo_root, finding=None) -> list | None:
    """Deterministically choose ONE verify command (argv), preferring repo commands."""
    root = Path(repo_root)
    makefile = root / "Makefile"
    if makefile.is_file():
        try:
            targets = _make_targets(makefile.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError):
            targets = set()
        for target in ("test", "check"):
            if target in targets:
                return ["make", target]
    if (root / "tests").is_dir():
        return ["python3", "-m", "unittest", "discover", "-s", "tests"]
    return None


def bind_recipe(category: str) -> str:
    return RECIPE_BINDING.get(category, _FALLBACK_RECIPE)


def plan_fix(finding, repo_root) -> FixPlan:
    """Turn one Finding into a bounded, deterministic fix plan (no writes)."""
    category = getattr(finding, "category", "")
    confidence = getattr(finding, "confidence", "low")
    recipe = bind_recipe(category)
    verify_command = select_verify_command(repo_root, finding)

    classification = AUTO_FIXABLE.get(category)
    if not classification or not classification[0]:
        return FixPlan(finding, recipe, verify_command, "propose",
                       "category is not classified auto-fixable; routed to proposal")

    _, floor, rationale = classification
    if verify_command is None:
        return FixPlan(finding, recipe, verify_command, "propose",
                       "no derivable verification command; routed to proposal")
    if _CONFIDENCE_RANK.get(confidence, 0) < _CONFIDENCE_RANK.get(floor, 0):
        return FixPlan(finding, recipe, verify_command, "propose",
                       f"confidence '{confidence}' below floor '{floor}'; routed to proposal")
    return FixPlan(finding, recipe, verify_command, "autofix", rationale)
