"""QB production gate + self-audit acceptance (Phase 7.4, roadmap finale).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
Composes every prior Phase-7 signal into the single, fail-closed authorization to
operate autonomously in earnest: telemetry emitted (7.1), rollback drills passing
and release gates satisfied (7.2), least-privilege + supply-chain invariants
holding (7.3), the kill-switch proven to halt recoverably (Phase 4 + 7.2), and a
clean (or explicitly-accepted) self-audit of QB by QB.

A3 (deliver / commit / push / PR) remains explicit opt-in even after the gate
passes -- passing the gate authorizes autonomous operation, never auto-delivery.
The gate re-evaluates current signals; it is not a one-time checkbox.
"""

from __future__ import annotations

# A3 is never enabled by default, regardless of gate outcome.
A3_DEFAULT_ENABLED = False

PRODUCTION_GATE_CHECKS = (
    "telemetry_emitted",
    "rollback_drill_passed",
    "least_privilege_ok",
    "supply_chain_ok",
    "killswitch_proven",
    "self_audit_clean",
)


def _finding_id(finding):
    return finding.get("id") if isinstance(finding, dict) else getattr(finding, "id", None)


def self_audit_clean(findings, accepted_ids=()) -> bool:
    """A self-audit is clean when every finding is either fixed or explicitly accepted."""
    accepted = set(accepted_ids)
    return all(_finding_id(f) in accepted for f in findings)


def unaccepted_findings(findings, accepted_ids=()):
    """Findings that are neither fixed nor in the accepted-findings register."""
    accepted = set(accepted_ids)
    return [f for f in findings if _finding_id(f) not in accepted]


def production_gate(*, telemetry_emitted, rollback_drill_passed, least_privilege_ok,
                    supply_chain_ok, killswitch_proven, self_audit_clean) -> dict:
    """Composite, fail-closed production gate. Passes only when every conjunct holds."""
    checks = {
        "telemetry_emitted": bool(telemetry_emitted),
        "rollback_drill_passed": bool(rollback_drill_passed),
        "least_privilege_ok": bool(least_privilege_ok),
        "supply_chain_ok": bool(supply_chain_ok),
        "killswitch_proven": bool(killswitch_proven),
        "self_audit_clean": bool(self_audit_clean),
    }
    failures = sorted(name for name, ok in checks.items() if not ok)
    return {
        "passed": not failures,
        "failures": failures,
        "checks": checks,
        "a3_enabled_by_default": A3_DEFAULT_ENABLED,   # always False
    }
