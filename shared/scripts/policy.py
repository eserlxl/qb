"""QB policy schema + evaluation engine (Phase 4.1).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
Turns "autonomous" from a vibe into a bounded function of declared rules: a frozen,
closed-key declarative policy plus a pure, side-effect-free engine that answers,
for any candidate action, "is this allowed under this policy?" with a stable
reason code.

Fail-closed everywhere: a missing, unparseable, or malformed policy synthesizes
the MOST RESTRICTIVE policy (A0 report-only, empty auto-fix set, deny-all writes,
no commit/push/PR). An unknown top-level key is a hard parse error -- a typo can
never silently widen authority. The engine performs no I/O, runs no fix, and
commits nothing; it is a pure (policy, action) -> verdict function.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatch
from importlib import util as _import_util
from pathlib import Path

A0, A1, A2, A3 = "A0", "A1", "A2", "A3"
_LEVELS = (A0, A1, A2, A3)
_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def sandbox_autonomy_ceiling(*, sandbox_available: bool) -> str:
    """Effective-autonomy ceiling from execution-sandbox availability.

    When the required execution confinement cannot be established, cap autonomy
    below apply-verified (A1) so no A2/A3 working-tree apply is attempted -- a
    deterministic safe degradation rather than running analyzed-code verification
    unconfined or attempting-and-reverting per fix. With the sandbox available there
    is no sandbox-driven cap (A3).
    """
    return A3 if sandbox_available else A1

SCHEMA_VERSION = 2

# The CLOSED set of permitted top-level policy keys. Unknown key => parse error.
CLOSED_KEYS = frozenset({
    "schema_version",
    "autonomy_level",
    "auto_fixable_categories",
    "min_confidence",
    "default_min_confidence",
    "write_allowlist",
    "write_denylist",
    "allow_commit",
    "allow_push",
    "allow_pr",
    "budgets",
})

# Closed set of budget ceiling keys (Phase 4.3 reads these from the policy).
BUDGET_KEYS = frozenset({
    "max_findings", "max_fixes", "max_iterations", "max_wall_seconds", "max_tokens",
})


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
CATEGORIES = _fs.CATEGORIES
SEVERITIES = _fs.SEVERITIES


class PolicyError(Exception):
    """Raised when a policy is structurally invalid (strict parse)."""


@dataclass(frozen=True)
class Policy:
    schema_version: int = SCHEMA_VERSION
    autonomy_level: str = A0
    auto_fixable_categories: frozenset = field(default_factory=frozenset)
    min_confidence: dict = field(default_factory=dict)
    default_min_confidence: str = "high"
    write_allowlist: tuple = ()
    write_denylist: tuple = ()
    allow_commit: bool = False
    allow_push: bool = False
    allow_pr: bool = False
    budgets: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ActionDescriptor:
    action_kind: str          # "fix" | "commit" | "push" | "pr"
    category: str = ""
    severity: str = ""
    confidence: str = "low"
    target_path: str = ""


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    reason: str


def default_policy() -> Policy:
    """The most restrictive policy: A0 report-only, deny all writes and remote ops."""
    return Policy()


def parse_policy(data: dict) -> Policy:
    """Strictly parse a policy mapping; raise PolicyError on unknown/invalid input."""
    if not isinstance(data, dict):
        raise PolicyError("policy must be a mapping")
    unknown = set(data) - CLOSED_KEYS
    if unknown:
        raise PolicyError(f"unknown policy key(s): {sorted(unknown)}")

    level = data.get("autonomy_level", A0)
    if level not in _LEVELS:
        raise PolicyError(f"invalid autonomy_level: {level}")

    categories = data.get("auto_fixable_categories", [])
    bad = [c for c in categories if c not in CATEGORIES]
    if bad:
        raise PolicyError(f"unknown auto_fixable_categories: {bad}")

    min_confidence = data.get("min_confidence", {})
    for cat, band in min_confidence.items():
        if cat not in CATEGORIES:
            raise PolicyError(f"min_confidence references unknown category: {cat}")
        if band not in _CONFIDENCE_RANK:
            raise PolicyError(f"invalid confidence band: {band}")
    default_floor = data.get("default_min_confidence", "high")
    if default_floor not in _CONFIDENCE_RANK:
        raise PolicyError(f"invalid default_min_confidence: {default_floor}")

    for flag in ("allow_commit", "allow_push", "allow_pr"):
        if flag in data and not isinstance(data[flag], bool):
            raise PolicyError(f"{flag} must be a boolean")

    budgets = data.get("budgets", {})
    if not isinstance(budgets, dict):
        raise PolicyError("budgets must be a mapping")
    unknown_budget = set(budgets) - BUDGET_KEYS
    if unknown_budget:
        raise PolicyError(f"unknown budget key(s): {sorted(unknown_budget)}")
    for bkey, bval in budgets.items():
        if not isinstance(bval, (int, float)) or isinstance(bval, bool) or bval < 0:
            raise PolicyError(f"budget {bkey} must be a non-negative number")

    return Policy(
        schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        autonomy_level=level,
        auto_fixable_categories=frozenset(categories),
        min_confidence=dict(min_confidence),
        default_min_confidence=default_floor,
        write_allowlist=tuple(data.get("write_allowlist", ())),
        write_denylist=tuple(data.get("write_denylist", ())),
        allow_commit=bool(data.get("allow_commit", False)),
        allow_push=bool(data.get("allow_push", False)),
        allow_pr=bool(data.get("allow_pr", False)),
        budgets=dict(budgets),
    )


def load_policy(path) -> Policy:
    """Load a policy file, failing CLOSED to the default policy on any problem."""
    p = Path(path)
    if not p.is_file():
        return default_policy()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return parse_policy(data)
    except (json.JSONDecodeError, PolicyError, OSError, UnicodeDecodeError):
        return default_policy()


def _deny(reason: str) -> Verdict:
    return Verdict(False, reason)


def evaluate(policy: Policy, action: ActionDescriptor) -> Verdict:
    """Pure decision: is this action permitted under this policy? (no side effects)"""
    kind = action.action_kind
    if kind == "commit":
        return Verdict(True, "allowed") if policy.allow_commit else _deny("commit-not-permitted")
    if kind == "push":
        return Verdict(True, "allowed") if policy.allow_push else _deny("push-not-permitted")
    if kind == "pr":
        return Verdict(True, "allowed") if policy.allow_pr else _deny("pr-not-permitted")
    if kind != "fix":
        return _deny("unknown-action-kind")

    if policy.autonomy_level == A0:
        return _deny("autonomy-report-only")
    if action.category not in policy.auto_fixable_categories:
        return _deny("category-not-auto-fixable")
    floor = policy.min_confidence.get(action.category, policy.default_min_confidence)
    if _CONFIDENCE_RANK.get(action.confidence, 0) < _CONFIDENCE_RANK.get(floor, 2):
        return _deny("confidence-below-threshold")
    path = action.target_path
    if any(fnmatch(path, g) for g in policy.write_denylist):
        return _deny("path-in-denylist")           # deny always overrides allow
    if not policy.write_allowlist or not any(fnmatch(path, g) for g in policy.write_allowlist):
        return _deny("path-outside-allowlist")
    return Verdict(True, "allowed")
