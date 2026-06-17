"""QB live-validation driver (Phase 3.1).

Runs the real ``qb_headless`` audit->report loop over a set of target repos and
reads back each run's telemetry, returning a structured result per repo. Standard
library only; loads the engine modules from ``shared/scripts/`` by path so it runs
from a checkout without installation.

This is a harness for the trusted/neutralized corpus (see
docs/live-validation-protocol.md); it never relaxes the engine's own gates.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "shared" / "scripts"


def _load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_headless = _load("qb_headless", "qb_headless.py")
_store = _headless._store  # reuse the run_store instance qb_headless already loaded
_policy = _load("qb_policy", "policy.py")
_fixer = _load("qb_fixer", "fixer.py")
_budget = _load("qb_budget", "budget.py")
_telemetry = _load("qb_telemetry", "telemetry.py")

# Campaign fixable target. The corpus repos verify with a stdlib-only no-op
# (their Makefile `test` target), so a synthetic quality finding + a .txt apply
# exercises the full isolate -> apply -> verify -> keep path without running
# untrusted code. The corpus supplies the target repo; the campaign supplies the
# fixable scenario (the same pattern tests/test_autonomy_levels.py uses).
_FIX_TARGET = "fix_target.txt"


@dataclass(frozen=True)
class CampaignRun:
    repo: str
    declared_level: str
    results: list
    report: object
    telemetry: dict
    output_dir: Path

    def outcomes(self) -> list:
        return [r["outcome"] for r in self.results]

    def promoted(self) -> list:
        return [p for r in self.results for p in r.get("promoted", [])]

    def changesets(self) -> list:
        return [r["changeset"] for r in self.results if r.get("changeset")]


def _quality_finding():
    ev = _FIX_TARGET + ":1"
    return _fixer.Finding(
        id=_fixer.compute_finding_id("quality", ev, "lint:style"),
        category="quality", severity="P3", confidence="medium",
        evidence=ev, rationale="style", suggested_fix="clean it", fix_strategy="propose",
    )


def make_plan(verify_command, *, finding_id="QBF-campaign000", category="quality",
              severity="P3", confidence="medium", evidence="fix_target.txt:1"):
    """A FixPlan-shaped object with an explicit verify command, for campaigns that
    must exercise a specific green/non-green verification outcome (the corpus's own
    verify is an always-green no-op)."""
    finding = types.SimpleNamespace(id=finding_id, category=category, severity=severity,
                                    confidence=confidence, evidence=evidence)
    return types.SimpleNamespace(finding=finding, verify_command=list(verify_command))


def session_policy(declared_level, *, categories=("quality",), allowlist=("*.txt",)):
    """The standard campaign policy at a declared level (quality auto-fixable, .txt writes)."""
    return _policy.parse_policy({
        "autonomy_level": declared_level,
        "auto_fixable_categories": list(categories),
        "default_min_confidence": "medium",
        "write_allowlist": list(allowlist),
    })


def run_campaign(repo, declared_level, output_dir, *, prior_telemetry=None, enable_a3=False):
    """Run one declared-level session over a corpus repo, persist + return telemetry.

    ``repo`` exposes ``.name`` and ``.path`` (a tests.qb_corpus.CorpusRepo).
    """
    policy = session_policy(declared_level)
    finding = _quality_finding()
    plan = _fixer.plan_fix(finding, repo.path)
    results, report = _budget.run_session(
        policy, repo.path,
        [(plan, lambda iso: iso.write_file(_FIX_TARGET, "clean\n"))],
        run_id=f"{repo.name}-{declared_level}", telemetry=prior_telemetry, enable_a3=enable_a3,
    )
    evidence = [r["evidence"] for r in results if r.get("evidence")]
    telemetry = _telemetry.build_telemetry(
        run_id=f"{repo.name}-{declared_level}", autonomy_level=declared_level,
        findings=[{"category": "quality", "severity": "P3", "confidence": "medium"}],
        evidence=evidence,
    )
    output_dir = Path(output_dir)
    _store.RunStore(output_dir).open(overwrite=True).write_telemetry(telemetry)
    return CampaignRun(repo=repo.name, declared_level=declared_level, results=results,
                       report=report, telemetry=telemetry, output_dir=output_dir)


@dataclass(frozen=True)
class RunResult:
    repo: str
    exit_code: int
    output_dir: Path
    telemetry: dict
    findings_present: bool


def run_over_repo(repo_root, output_dir, *, policy=None) -> RunResult:
    """Run qb_headless over one repo and read back its telemetry (never raises on read)."""
    repo_root = Path(repo_root)
    output_dir = Path(output_dir)
    code = _headless.run_headless(repo_root, policy=policy, output_dir=output_dir)
    telemetry = _store.load_prior_telemetry(output_dir)
    return RunResult(
        repo=repo_root.name,
        exit_code=code,
        output_dir=output_dir,
        telemetry=telemetry if isinstance(telemetry, dict) else {},
        findings_present=(code == _headless.EXIT_FINDINGS),
    )


def run_over_corpus(repos, out_base, *, policy=None) -> list:
    """Run qb_headless over every corpus repo; return a RunResult per repo.

    ``repos`` is an iterable of objects exposing ``.name`` and ``.path`` (e.g.
    ``tests.qb_corpus.CorpusRepo``). Each run gets its own ``.qb/audit/`` store
    under ``out_base/<name>/``.
    """
    out_base = Path(out_base)
    results = []
    for repo in repos:
        out = out_base / repo.name / _store.OUTPUT_DIR_NAME
        results.append(run_over_repo(repo.path, out, policy=policy))
    return results
