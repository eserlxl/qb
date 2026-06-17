"""Labelled corpus fixture builder for QB live validation (Phase 3.1).

Materializes deterministic, git-initialized target repositories that each carry a
known, labelled set of seeded findings across the frozen finding categories, plus
a ground-truth label set. Standard library only and free of host-state
dependence: the same inputs always yield the same repos and the same labels.

Trust model (honest scope): every corpus repo is either a *trusted-verification*
target or a *neutralized stdlib-only no-op* -- its verification command never runs
untrusted code. Untrusted or network-fetched, self-executing targets are out of
scope until full execution sandboxing ships (see docs/live-validation-protocol.md).

The seeded sink strings below are inert test data written only into throwaway
temp repos; they are never executed. They are assembled by concatenation so this
support module does not itself read like real sink code.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

# A neutralized, stdlib-only no-op verification command -- trusted to execute.
NEUTRAL_VERIFY = ["python3", "-c", ""]

_MIT_LICENSE = "MIT License\n\nPermission is hereby granted, free of charge, ...\n"
# A Makefile whose `test` target is a stdlib-only no-op (neutralized verification).
_NEUTRAL_MAKEFILE = "test:\n\tpython3 -c \"\"\n"

# Seeded sink content (inert; concatenated so the literal sink text is split).
_INJECTION_PAIR = "import os, subprocess\n" + "os." + "system(cmd)\n" + \
    "subprocess.run(payload, " + "shell=True)\n"
_TRAVERSAL = "def read(name):\n    return " + "open(\"../\" + name)\n"
_MIXED = "import os\n" + "os." + "system(cmd)\n" + "eval" + "(expr)\n" + \
    "data = " + "open(\"../\" + name)\n"
_CLEAN = "import subprocess\n" + "subprocess.run([\"ls\", \"-la\"], shell=False)\n"

# Each entry: (name, source filename, source text, ground-truth labels).
# Labels are category -> count of seeded findings, matching the documented
# CommandInjectionAnalyzer sinks (os.system / shell=True / eval / open("..")).
_SPECS = (
    ("injection_pair", "app.py", _INJECTION_PAIR, {"injection": 2}),
    ("traversal", "io.py", _TRAVERSAL, {"path-traversal": 1}),
    ("mixed", "svc.py", _MIXED, {"injection": 2, "path-traversal": 1}),
    ("clean", "safe.py", _CLEAN, {}),
)


@dataclass(frozen=True)
class CorpusRepo:
    name: str
    path: Path
    trust: str            # "trusted-verification" | "neutralized-noop"
    verify_command: list   # stdlib-only no-op verification argv
    labels: dict          # category -> count of seeded findings (ground truth)

    def total_seeded(self) -> int:
        return sum(self.labels.values())


def _git(repo: Path, *args) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True,
                   capture_output=True, text=True)
    _git(path, "config", "user.email", "corpus@example.com")
    _git(path, "config", "user.name", "QB Corpus")
    _git(path, "config", "commit.gpgsign", "false")


def build_corpus(base_dir) -> list:
    """Materialize the labelled corpus under ``base_dir``; return CorpusRepo list.

    Deterministic: identical specs always produce identical repos and labels.
    """
    base = Path(base_dir)
    repos: list = []
    for name, filename, text, labels in _SPECS:
        path = base / name
        _init_repo(path)
        (path / filename).write_text(text, encoding="utf-8")
        (path / "LICENSE").write_text(_MIT_LICENSE, encoding="utf-8")  # avoid a license finding
        (path / "Makefile").write_text(_NEUTRAL_MAKEFILE, encoding="utf-8")
        _git(path, "add", "-A")
        _git(path, "commit", "-q", "-m", "corpus")
        repos.append(CorpusRepo(
            name=name, path=path, trust="neutralized-noop",
            verify_command=list(NEUTRAL_VERIFY), labels=dict(labels),
        ))
    return repos
