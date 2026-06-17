"""QB budgets + kill-switch for unattended runs (Phase 4.3).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
Bounds an unattended run on five independent ceilings (findings considered, fixes
applied, orchestration iterations, wall-time, token spend) and provides a
kill-switch honored only at safe checkpoints BETWEEN atomic fix units -- so a
stop never bisects a fix. Each ceiling is checked BEFORE consuming the next unit,
so the run halts AT the ceiling, never past it.

run_session composes with the Phase-4.2 orchestrator (run_finding is atomic:
isolate -> gate -> promote/revert -> teardown), polling budgets and the kill-switch
at the loop boundary. On stop it returns a StopReport with a distinct headless
exit code: clean-finish (0), budget-stop (2), kill-stop (3).
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from importlib import util as _import_util
from pathlib import Path

CLEAN_EXIT = 0
BUDGET_STOP_EXIT = 2
KILL_STOP_EXIT = 3

_DEFAULTS = {
    "max_findings": 100,
    "max_fixes": 20,
    "max_iterations": 100,
    "max_wall_seconds": 600.0,
    "max_tokens": 1_000_000,
}


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = _import_util.spec_from_file_location(module_name, path)
    module = _import_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_orch = _load_sibling("qb_orchestrator", "orchestrator.py")
_telemetry = _load_sibling("qb_telemetry", "telemetry.py")
_trends = _load_sibling("qb_telemetry_trends", "telemetry_trends.py")


@dataclass
class Budget:
    max_findings: int = _DEFAULTS["max_findings"]
    max_fixes: int = _DEFAULTS["max_fixes"]
    max_iterations: int = _DEFAULTS["max_iterations"]
    max_wall_seconds: float = _DEFAULTS["max_wall_seconds"]
    max_tokens: int = _DEFAULTS["max_tokens"]

    @classmethod
    def from_policy(cls, policy) -> "Budget":
        raw = dict(getattr(policy, "budgets", {}) or {})
        return cls(**{k: raw[k] for k in raw if k in _DEFAULTS})


class KillSwitch:
    def __init__(self) -> None:
        self._triggered = False

    def trigger(self) -> None:
        self._triggered = True

    def triggered(self) -> bool:
        return self._triggered


@dataclass
class StopReport:
    trigger: str            # completed | max_* | kill
    findings_considered: int
    fixes_applied: int
    fixes_reverted: int
    exit_code: int
    # The per-run quality/cost telemetry built at the run finale (Phase 4.3). Its
    # ``cost`` block carries the BudgetMeter's real wall_ms/iterations rather than
    # UNMEASURED. ``None`` only when telemetry construction was not performed.
    telemetry: dict | None = None

    def to_dict(self) -> dict:
        return {
            "trigger": self.trigger,
            "findings_considered": self.findings_considered,
            "fixes_applied": self.fixes_applied,
            "fixes_reverted": self.fixes_reverted,
            "exit_code": self.exit_code,
        }


class BudgetMeter:
    """Counts resources and reports which ceiling (if any) is reached -- checked
    before consuming the next unit."""

    def __init__(self, budget: Budget, clock=time.monotonic):
        self.budget = budget
        self._clock = clock
        self._start = clock()
        self.findings_considered = 0
        self.fixes_applied = 0
        self.fixes_reverted = 0
        self.iterations = 0
        self.tokens = 0

    def elapsed(self) -> float:
        return self._clock() - self._start

    def add_tokens(self, count: int) -> None:
        self.tokens += count

    def ceiling_reached(self):
        """Return the name of a reached ceiling, or None. Call BEFORE the next unit."""
        if self.elapsed() >= self.budget.max_wall_seconds:
            return "max_wall_time"
        if self.iterations >= self.budget.max_iterations:
            return "max_iterations"
        if self.findings_considered >= self.budget.max_findings:
            return "max_findings"
        if self.fixes_applied >= self.budget.max_fixes:
            return "max_fixes"
        if self.tokens >= self.budget.max_tokens:
            return "max_tokens"
        return None


def telemetry_cost(meter: BudgetMeter) -> dict:
    """Map BudgetMeter values to telemetry.build_telemetry cost fields.

    ``wall_ms`` is the meter's elapsed monotonic seconds converted once to
    integer milliseconds; iterations and tokens keep the meter's counters.
    """
    return {
        "wall_ms": int(round(meter.elapsed() * 1000)),
        "iterations": meter.iterations,
        "tokens": meter.tokens,
    }


def run_session(policy, repo_root, items, *, killswitch=None, run_id="session",
                enable_a3=False, telemetry=None, clock=time.monotonic):
    """Run findings under budget + kill-switch control. items: [(fix_plan, apply_fn), ...].

    ``telemetry`` is the prior-run quality record, loaded by the caller from the
    previous run store root with ``run_store.load_prior_telemetry``. It is threaded
    to each ``run_finding`` so the declared autonomy level is clamped by the earned
    ceiling; with no telemetry, the session promotes nothing above A1 (fail-closed)."""
    meter = BudgetMeter(Budget.from_policy(policy), clock=clock)
    results = []
    considered_findings = []
    trigger = "completed"

    for index, (fix_plan, apply_fn) in enumerate(items):
        # Safe checkpoint between atomic fix units: poll kill-switch, then budgets.
        if killswitch is not None and killswitch.triggered():
            trigger = "kill"
            break
        reached = meter.ceiling_reached()
        if reached:
            trigger = reached
            break

        meter.iterations += 1
        meter.findings_considered += 1
        result = _orch.run_finding(policy, repo_root, fix_plan, apply_fn,
                                   run_id=f"{run_id}-{index}", enable_a3=enable_a3,
                                   telemetry=telemetry)
        results.append(result)
        considered_findings.append(fix_plan.finding)
        if result["outcome"] == "kept":
            meter.fixes_applied += 1
        elif result["outcome"] == "reverted":
            meter.fixes_reverted += 1

    exit_code = {"completed": CLEAN_EXIT, "kill": KILL_STOP_EXIT}.get(trigger, BUDGET_STOP_EXIT)
    report = StopReport(trigger, meter.findings_considered, meter.fixes_applied,
                        meter.fixes_reverted, exit_code)

    # Run-finale telemetry build (Phase 4.3): forward the metered run-boundary cost
    # (real wall_ms + iterations from the BudgetMeter, not UNMEASURED) together with
    # the run's detection/action outcomes, so the per-run quality record carries
    # measured cost instead of leaving latency/iterations unmeasured.
    evidence = [{"outcome": r.get("outcome"),
                 "after_exit": (r.get("evidence") or {}).get("after_exit")}
                for r in results]
    report.telemetry = _telemetry.build_telemetry(
        run_id=run_id,
        autonomy_level=policy.autonomy_level,
        findings=considered_findings,
        evidence=evidence,
        cost=telemetry_cost(meter),
    )
    return results, report


# --- Phase 4.4: per-ceiling budget raise-path guidance -----------------------
# Each budget ceiling that can halt a run (a ``StopReport.trigger``) maps to a
# documented raise-path: the evidence that justifies raising it, a conservative
# step size, and the guardrail that must hold first. ``completed`` / ``kill`` are
# not budget ceilings, so they carry no raise-path (``raise_path`` returns None).
# This mapping is advisory documentation surfaced to operators; applying a raise
# is done only by editing ``policy.budgets`` -- never automatically (Phase 4.4
# fail-closed raise discipline).
RAISE_PATH_FIELDS = ("ceiling", "evidence", "step", "guardrail")

RAISE_PATHS = {
    "max_findings": {
        "ceiling": "max_findings",
        "evidence": "findings_considered reached max_findings with findings still unprocessed",
        "step": "raise policy.budgets.max_findings by one increment for the next run",
        "guardrail": "triage P0/P1 first -- a wider finding budget broadens scope, not fix depth",
    },
    "max_fixes": {
        "ceiling": "max_fixes",
        "evidence": "fixes_applied reached max_fixes while verified fixes remained queued",
        "step": "raise policy.budgets.max_fixes by one increment for the next run",
        "guardrail": "only when precision_estimate >= release_gate.PRECISION_FLOOR and fix_safety_ok",
    },
    "max_iterations": {
        "ceiling": "max_iterations",
        "evidence": "orchestration iterations reached max_iterations before the queue drained",
        "step": "raise policy.budgets.max_iterations by one increment for the next run",
        "guardrail": "confirm iterations are productive, not looping on the same finding",
    },
    "max_wall_time": {
        "ceiling": "max_wall_time",
        "evidence": "the run halted at max_wall_seconds with work still queued",
        "step": "raise policy.budgets.max_wall_seconds (e.g. +50%) for the next run",
        "guardrail": "confirm the run was making progress (fixes kept), not spinning",
    },
    "max_tokens": {
        "ceiling": "max_tokens",
        "evidence": "token spend reached max_tokens before the run completed",
        "step": "raise policy.budgets.max_tokens for the next run",
        "guardrail": "confirm token use is proportional to fixes kept, not waste",
    },
}


def raise_path(trigger: str):
    """Return the documented raise-path for a budget-ceiling ``StopReport.trigger``,
    or ``None`` for a non-ceiling trigger (``completed`` / ``kill``). Advisory only --
    it reads nothing and mutates nothing."""
    return RAISE_PATHS.get(trigger)


# --- Phase 4.4: advisory budget recommender (output-only) --------------------
# A ceiling that halts a run is either *constraining* (legitimately limiting useful
# work -> consider raising) or *protecting* (correctly guarding against waste or
# regression -> hold). When the trend evidence is too thin to tell, the advice is
# *insufficient-evidence* -> do not raise (fail-closed). The recommender is pure:
# it reads a StopReport + the aggregate telemetry series and returns advice; it never
# mutates a budget. Applying a raise is always an explicit policy.budgets edit.
ADVICE_CONSTRAINING = "constraining"
ADVICE_PROTECTING = "protecting"
ADVICE_INSUFFICIENT = "insufficient-evidence"

_INSUFFICIENT_VERDICTS = frozenset({_trends.VERDICT_INSUFFICIENT, _trends.VERDICT_UNMEASURED})


def recommend_budget(stop_report, aggregate, *, window: int = 3) -> dict:
    """Advise whether the ceiling a run hit is constraining vs. protecting vs.
    insufficient-evidence (Phase 4.4). Output only -- never mutates a budget.

    ``aggregate`` is an aggregate telemetry series (or a path to one). A raise is
    advised only when the run was producing good work -- precision and fix-safety
    holding (stable/improving) and not regressing on quality -- so a ceiling that
    halts a regressing run reads as protecting, and thin evidence reads as
    insufficient (fail-closed: do not raise)."""
    trigger = getattr(stop_report, "trigger", None)
    path = raise_path(trigger)

    # Non-ceiling trigger (completed/kill): the budget did not bind -> nothing to raise.
    if path is None:
        return {"advice": ADVICE_PROTECTING, "ceiling": None, "raise_path": None,
                "reason": f"trigger '{trigger}' is not a budget ceiling; the budget did not bind"}

    precision = _trends.direction_verdict(aggregate, "precision", window)
    fix_safety = _trends.direction_verdict(aggregate, "fix_safety", window)
    quality = _trends.direction_verdict(aggregate, "quality", window)

    # Fail-closed: without enough precision/fix-safety history, do not advise a raise.
    if precision in _INSUFFICIENT_VERDICTS or fix_safety in _INSUFFICIENT_VERDICTS:
        return {"advice": ADVICE_INSUFFICIENT, "ceiling": trigger, "raise_path": None,
                "reason": "insufficient precision/fix-safety trend evidence to justify a raise"}

    # The ceiling is correctly protecting against a regressing run -> hold.
    if _trends.VERDICT_REGRESSING in (precision, fix_safety, quality):
        return {"advice": ADVICE_PROTECTING, "ceiling": trigger, "raise_path": None,
                "reason": "precision/fix-safety/quality is regressing; the ceiling is guarding against waste"}

    # Good work being limited by the ceiling -> the ceiling is constraining.
    return {"advice": ADVICE_CONSTRAINING, "ceiling": trigger, "raise_path": path,
            "reason": "precision and fix-safety are holding/improving; the ceiling is limiting useful work"}
