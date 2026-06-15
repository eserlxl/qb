"""QB isolation & rollback runtime (Phase 3.2, net-new).

Canonical host-neutral QB IP under ``shared/`` (Python standard library + git).
Implements the safety primitive ASSESS-P0-02 flagged as the top unattended-write
risk: every autonomous write happens inside a dedicated, disposable git worktree
(never the operator's checked-out tree), and every state is reversible via a
captured git ref (the rollback handle).

Autonomy-to-isolation contract (main-planning section 5):
  * A0 (report-only): opens no isolation, writes nothing.
  * A1 (propose):     all writes confined to throwaway isolation; the operator's
                      working tree is never touched.
  * A2 (apply-verified): same isolation for fix attempts; promotion of verified
                      fixes to the working tree is DEFERRED to Phase 4 enablement
                      and intentionally not implemented here (this slice provides
                      only the reversible container + handle the gate acts on).

Guarantees:
  * Collision-safe branch naming (``qb-fix/<run_id>``), refusing to reuse an
    existing branch (fail-closed -- never overwrite user work).
  * Fail-closed: if the target is not a git repo or isolation cannot be created,
    raise rather than fall back to writing the live tree.
  * Path-allowlist write guard: writes are confined to the isolation root and, if
    an allowlist is given, to its globs.
  * Deterministic teardown: removes the worktree and branch; the operator's tree
    is byte-identical to its pre-run state when nothing is promoted.

All git invocations use the Phase-2.2 structured argv convention (no shell).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from fnmatch import fnmatch
from importlib import util as _import_util
from pathlib import Path

A0, A1, A2, A3 = "A0", "A1", "A2", "A3"
WRITES_BY_LEVEL = {A0: False, A1: True, A2: True, A3: True}


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = _import_util.spec_from_file_location(module_name, path)
    module = _import_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_cs = _load_sibling("qb_command_safety", "command_safety.py")
run_command = _cs.run_command
resolve_within = _cs.resolve_within


class IsolationError(Exception):
    """Raised when isolation cannot be established or restored (fail-closed)."""


def _git(repo, *args):
    return run_command(["git", "-C", str(repo), *args])


def _is_git_repo(path) -> bool:
    result = _git(path, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def _branch_exists(repo, branch: str) -> bool:
    result = _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    return result.returncode == 0


class Isolation:
    """A run-scoped, disposable git worktree with a rollback handle."""

    def __init__(self, repo_root, level=A1, run_id="run", allowlist=None):
        self.repo_root = Path(repo_root).resolve()
        self.level = level
        self.run_id = run_id
        self.allowlist = list(allowlist) if allowlist is not None else None
        self.branch = f"qb-fix/{run_id}"
        self.worktree_path = None
        self._base = None
        self.opened = False

    # -- lifecycle ---------------------------------------------------------
    def open(self) -> "Isolation":
        if not WRITES_BY_LEVEL.get(self.level, False):
            self.opened = False  # A0: report-only, no isolation
            return self
        if not _is_git_repo(self.repo_root):
            raise IsolationError(f"not a git repository: {self.repo_root}")
        if _branch_exists(self.repo_root, self.branch):
            raise IsolationError(f"branch collision: {self.branch}")
        self._base = Path(tempfile.mkdtemp(prefix=f"qb-iso-{self.run_id}-"))
        worktree = self._base / "wt"  # must not pre-exist for `git worktree add`
        result = _git(self.repo_root, "worktree", "add", "-b", self.branch, str(worktree), "HEAD")
        if result.returncode != 0:
            shutil.rmtree(self._base, ignore_errors=True)
            raise IsolationError(f"could not create worktree: {result.stderr.strip()}")
        self.worktree_path = worktree
        self.opened = True
        return self

    def capture_handle(self):
        """Capture the current git ref of the isolation container (rollback handle)."""
        if not self.opened:
            return None
        result = _git(self.worktree_path, "rev-parse", "HEAD")
        if result.returncode != 0:
            raise IsolationError("could not capture rollback handle")
        return result.stdout.strip()

    def restore(self, handle):
        """Reset the isolation container to ``handle`` and verify it matches."""
        if not self.opened:
            return
        _git(self.worktree_path, "reset", "--hard", handle)
        _git(self.worktree_path, "clean", "-fd")
        if self.capture_handle() != handle:
            raise IsolationError("post-restore tree does not match the rollback handle")

    def write_file(self, rel_path: str, content: str):
        """Write inside isolation, enforced by path containment + allowlist."""
        if not self.opened:
            raise IsolationError("cannot write: isolation is not open (A0/report-only)")
        # Write to the *resolved* path that containment validated, not the raw join:
        # a symlinked path component is then followed once, at check time, and the
        # write lands on the validated target rather than re-following at write time.
        target = resolve_within(self.worktree_path, rel_path)  # raises if it escapes the root
        if self.allowlist is not None and not any(fnmatch(rel_path, g) for g in self.allowlist):
            raise IsolationError(f"path not in write allowlist: {rel_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def teardown(self):
        """Remove the worktree and branch; leave the operator's tree untouched."""
        if not self.opened:
            return
        _git(self.repo_root, "worktree", "remove", "--force", str(self.worktree_path))
        _git(self.repo_root, "branch", "-D", self.branch)
        if self._base is not None:
            shutil.rmtree(self._base, ignore_errors=True)
        self.opened = False

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc, tb):
        self.teardown()
        return False
