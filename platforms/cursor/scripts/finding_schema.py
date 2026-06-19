"""QB Finding schema -- the frozen, host-neutral contract for an audit finding.

This module is canonical QB IP under ``shared/``. It is the single contract that
every QB analyzer (Phase 2) emits and that the fixer (Phase 3), the orchestrator
(Phase 4), and the reporter (Phase 5) consume. Freezing it here means a malformed
finding is rejected mechanically -- by ``validate_finding`` and the conformance
test -- before any analyzer logic is written, so downstream phases bind to a
stable interface instead of churning.

It is dependency-free (Python standard library only), to preserve QB's zero-setup
property.

================================================================================
THE FINDING RECORD (eight fields)
================================================================================
A finding is a structured record describing one defect located somewhere in an
arbitrary repository. The on-disk (serialized) field names are hyphenated; the
Python attribute names use underscores (shown in parentheses).

  Field            Required  Vocabulary   Meaning
  ---------------- --------  -----------  --------------------------------------
  id               yes       derived      Deterministic, rerun-stable identifier
                                          (see "IDENTITY" below). Form: QBF-<12 hex>.
  category         yes       CATEGORIES   What kind of defect this is.
  severity         yes       SEVERITIES   P0-P3, reusing the validator's grading.
  confidence       yes       CONFIDENCE_  How sure the analyzer is it is real.
                             BANDS
  evidence         yes       path:line    Repository-relative location of the
                                          defect: "path:line" or "path:start-end".
  rationale        yes       free text    Why this is a finding (non-empty).
  suggested-fix    yes       free text    What to change (non-empty); for
  (suggested_fix)                         non-autofixable findings this is the
                                          manual recommendation.
  fix-strategy     yes       FIX_         How the fixer must treat it.
  (fix_strategy)             STRATEGIES

All eight fields are required and must be non-empty. A value outside a closed
vocabulary, or an evidence string without a location, is non-conformant.

================================================================================
CLOSED VOCABULARIES
================================================================================
severity   : P0, P1, P2, P3
             (P0 blocks / dangerous; P1 serious; P2 quality; P3 minor) -- the
             exact grading ``count_audit_severities`` in
             ``validate_planner_docs.py`` already recognizes; no second scale.
confidence : high, medium, low
             The band Phase 4 thresholds auto-fix against; defined as a small
             closed set (not free text) so gating is unambiguous.
category   : secret, injection, path-traversal, dependency, quality,
             correctness, license, config
             Cross-checked against the Phase 2 analyzer set so the Phase 1.2
             interface can be typed to return conformant findings.
fix-strategy : autofix  -- safe to auto-apply under policy (Phase 4 / A2+).
               propose  -- write only to throwaway isolation for human review (A1).
               manual   -- requires a human; never auto-applied.
               none     -- report-only; no fix is proposed.

EXTENSION RULE: vocabularies are additive-only. A new value is added by
appending it to the relevant frozenset AND extending the conformance test in the
same change. Removing or renaming a value is a breaking change to the contract
and is not permitted without re-freezing the schema across all consumers.

================================================================================
IDENTITY (deterministic, rerun-stable)
================================================================================
``id = "QBF-" + sha256(f"{category}|{location}|{rule_key}").hexdigest()[:12]``
where ``location`` is the stripped evidence locator and ``rule_key`` names the
analyzer rule that fired. The id is a pure function of stable inputs (no
timestamp, no run counter), so the same defect at the same location yields the
same id across reruns -- enabling deduplication and run-to-run diffing.

Worked examples (reproducible; rerunning yields the identical id):
  compute_finding_id("secret", "config/app.py:42", "hardcoded-secret")
    -> QBF-276f98268551
  compute_finding_id("injection", "src/run.py:88", "shell-string-exec")
    -> QBF-94bba1534f13

================================================================================
SERIALIZATION
================================================================================
A finding persists as a single line of standard-library JSON with keys in sorted
(canonical) order and hyphenated field names (see ``serialize_finding``). One
finding per line yields a deterministic, line-stable JSONL findings file suitable
for byte-for-byte diffing between runs. No third-party serializer is used.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields

# --- Closed vocabularies -------------------------------------------------------
SEVERITIES: tuple[str, ...] = ("P0", "P1", "P2", "P3")
_SEV_RANK = {sev: index for index, sev in enumerate(SEVERITIES)}


def finding_sort_key(finding):
    """The one canonical total ordering on findings (severity, category, evidence,
    id), independent of analyzer discovery / filesystem timing. The single source
    every persistence path sorts by, so findings.jsonl is byte-identical no matter
    which entry point (audit_runner, qb_headless via RunStore) wrote it.
    """
    return (
        _SEV_RANK.get(finding.severity, len(SEVERITIES)),
        finding.category,
        finding.evidence,
        finding.id,
    )


CONFIDENCE_BANDS: frozenset[str] = frozenset({"high", "medium", "low"})
CATEGORIES: frozenset[str] = frozenset({
    "secret",
    "injection",
    "path-traversal",
    "dependency",
    "quality",
    "correctness",
    "license",
    "config",
})
FIX_STRATEGIES: frozenset[str] = frozenset({"autofix", "propose", "manual", "none"})

# Repository-relative locator: "path:line" or "path:start-end". Line numbers are
# 1-based positive integers (SARIF 2.1.0 region.startLine must be >= 1), so a
# leading zero / line 0 is non-conformant; an inverted range (start > end) is
# caught in validate_finding.
EVIDENCE_RE = re.compile(r"^\S+:[1-9]\d*(?:-[1-9]\d*)?$")

# Serialized (on-disk) key names for the underscore-named Python attributes.
_DISK_KEYS = {
    "suggested_fix": "suggested-fix",
    "fix_strategy": "fix-strategy",
}

_ID_RE = re.compile(r"^QBF-[0-9a-f]{12}$")


@dataclass
class Finding:
    """One audit finding. All eight fields are required and must be non-empty."""

    id: str
    category: str
    severity: str
    confidence: str
    evidence: str
    rationale: str
    suggested_fix: str
    fix_strategy: str

    def to_dict(self) -> dict[str, str]:
        """Canonical on-disk mapping (hyphenated keys)."""
        out: dict[str, str] = {}
        for f in fields(self):
            out[_DISK_KEYS.get(f.name, f.name)] = getattr(self, f.name)
        return out

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "Finding":
        """Build a Finding from an on-disk mapping (hyphenated or underscored)."""
        kwargs: dict[str, str] = {}
        for f in fields(cls):
            disk = _DISK_KEYS.get(f.name, f.name)
            kwargs[f.name] = data.get(disk, data.get(f.name, ""))
        return cls(**kwargs)


def compute_finding_id(category: str, evidence: str, rule_key: str) -> str:
    """Deterministic id from stable inputs. Same inputs -> same id, always."""
    location = (evidence or "").strip()
    payload = f"{category}|{location}|{rule_key}".encode("utf-8")
    return "QBF-" + hashlib.sha256(payload).hexdigest()[:12]


def validate_finding(finding: "Finding | dict[str, str]") -> list[str]:
    """Return a list of conformance error codes (empty list == conformant)."""
    if isinstance(finding, dict):
        finding = Finding.from_dict(finding)
    elif not hasattr(finding, "category"):  # duck-type: accept a Finding from any module instance
        return [f"not_a_finding={type(finding).__name__}"]

    errors: list[str] = []

    # Required, non-empty (after stripping) string fields.
    for f in fields(finding):
        value = getattr(finding, f.name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"empty_field={f.name}")

    if finding.category not in CATEGORIES:
        errors.append(f"invalid_category={finding.category}")
    if finding.severity not in SEVERITIES:
        errors.append(f"invalid_severity={finding.severity}")
    if finding.confidence not in CONFIDENCE_BANDS:
        errors.append(f"invalid_confidence={finding.confidence}")
    if finding.fix_strategy not in FIX_STRATEGIES:
        errors.append(f"invalid_fix_strategy={finding.fix_strategy}")
    if not EVIDENCE_RE.match(finding.evidence or ""):
        errors.append(f"invalid_evidence={finding.evidence}")
    else:
        # Non-inverted range: "path:start-end" requires start <= end.
        locator = finding.evidence.rsplit(":", 1)[-1]
        if "-" in locator:
            start_s, end_s = locator.split("-", 1)
            if int(start_s) > int(end_s):
                errors.append(f"invalid_evidence={finding.evidence}")
    if not _ID_RE.match(finding.id or ""):
        errors.append(f"invalid_id={finding.id}")

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for e in errors:
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return unique


def serialize_finding(finding: "Finding | dict[str, str]") -> str:
    """One canonical, std-lib JSON line: sorted keys, hyphenated, no newline."""
    if hasattr(finding, "to_dict"):  # Finding (from any module instance)
        data = finding.to_dict()
    else:
        data = Finding.from_dict(finding).to_dict()
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def is_conformant(finding: "Finding | dict[str, str]") -> bool:
    """Convenience boolean wrapper over ``validate_finding``."""
    return not validate_finding(finding)
