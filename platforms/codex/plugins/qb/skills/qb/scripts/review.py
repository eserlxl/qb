"""QB role separation + cross-review gate (Phase 4.4).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
Closes the trust loop on autonomy: the model/role that AUTHORED a fix must not be
the sole judge of a fix that matters. Four roles with bounded capabilities --
Analyzer (read-only), Fixer (write-under-isolation), Verifier (runs validation),
Reviewer (independent keep/revert verdict) -- and a cross-review gate that composes
with the Phase-3 verification result at the Phase-4.2 promotion seam.

Rules:
  * "It matters" => mandatory cross-review: security-category findings
    (secret / injection / path-traversal) or P0/P1 severity. Widening is the safe
    direction; low-risk fixes stay single-gated by verification.
  * Author-distinct-from-reviewer: for a mattering fix the reviewing role must
    differ from the authoring role (and the model/family where the host can assign
    it). Single-model fallback: a distinct ROLE still reviews and verification
    remains an independent second check; the limitation is recorded.
  * Verdict composition: a mattering fix is promoted only when verification passed
    AND the reviewer returns keep. Either failing demotes it.
  * Self-approval of a mattering fix (reviewer == author) is blocked with a stable
    reason code, never warned.
"""

from __future__ import annotations

ROLE_ANALYZER = "analyzer"
ROLE_FIXER = "fixer"
ROLE_VERIFIER = "verifier"
ROLE_REVIEWER = "reviewer"
ROLES = (ROLE_ANALYZER, ROLE_FIXER, ROLE_VERIFIER, ROLE_REVIEWER)

# Capabilities (write-access) per role -- non-overlapping.
ROLE_CAPABILITIES = {
    ROLE_ANALYZER: {"read": True, "write_isolation": False, "promote": False, "judge": False},
    ROLE_FIXER: {"read": True, "write_isolation": True, "promote": False, "judge": False},
    ROLE_VERIFIER: {"read": True, "write_isolation": False, "promote": False, "judge": "verification"},
    ROLE_REVIEWER: {"read": True, "write_isolation": False, "promote": False, "judge": "keep/revert"},
}

SECURITY_CATEGORIES = frozenset({"secret", "injection", "path-traversal"})
_MATTERS_SEVERITIES = frozenset({"P0", "P1"})


def requires_cross_review(finding, policy=None) -> bool:
    """The 'it matters' criteria: mandatory cross-review for security/high-severity."""
    if getattr(finding, "category", "") in SECURITY_CATEGORIES:
        return True
    if getattr(finding, "severity", "") in _MATTERS_SEVERITIES:
        return True
    return False


def evaluate_review(finding, *, verification_passed, author_role, reviewer_role,
                    reviewer_keep, policy=None) -> dict:
    """Compose verification + cross-review into a promote/demote decision."""
    matters = requires_cross_review(finding, policy)
    if not matters:
        return {
            "matters": False,
            "promote": bool(verification_passed),
            "reason": "single-gated" if verification_passed else "verification-failed",
        }
    if reviewer_role == author_role:
        return {"matters": True, "promote": False, "reason": "self-approval-blocked"}
    if not verification_passed:
        return {"matters": True, "promote": False, "reason": "verification-failed"}
    if not reviewer_keep:
        return {"matters": True, "promote": False, "reason": "cross-review-revert"}
    return {"matters": True, "promote": True, "reason": "verified-and-reviewed"}


def make_promotion_review(*, author_role, reviewer_role, reviewer_fn, policy=None):
    """Build a run_finding review hook: finding -> {promote, reason}.

    At the promotion point verification has already passed (the gate kept the fix),
    so verification_passed is True here; the reviewer is consulted only for
    mattering fixes, and self-approval is blocked before the reviewer runs.
    """
    def _review(finding):
        if requires_cross_review(finding, policy) and reviewer_role == author_role:
            return {"promote": False, "reason": "self-approval-blocked"}
        keep = bool(reviewer_fn(finding)) if requires_cross_review(finding, policy) else True
        decision = evaluate_review(
            finding, verification_passed=True, author_role=author_role,
            reviewer_role=reviewer_role, reviewer_keep=keep, policy=policy,
        )
        return {"promote": decision["promote"], "reason": decision["reason"]}

    return _review
