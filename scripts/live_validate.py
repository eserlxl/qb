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
    ``tests.qb_corpus.CorpusRepo``). Each run gets its own ``QB-Audit/`` store
    under ``out_base/<name>/``.
    """
    out_base = Path(out_base)
    results = []
    for repo in repos:
        out = out_base / repo.name / _store.OUTPUT_DIR_NAME
        results.append(run_over_repo(repo.path, out, policy=policy))
    return results
