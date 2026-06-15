"""QB least-privilege + supply-chain safety (Phase 7.3).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
Turns QB's safety promises into bounded, checkable invariants about its own
behavior and provenance.

Least privilege (enforcement view of the Phase-4 policy):
  * WRITES are default-deny: only repository-relative paths matching the policy's
    allowlist globs may be written; an empty allowlist denies all; a path that
    escapes the repo root (traversal) is refused. Fail-closed.
  * NETWORK is default-offline: an offline analyzer always runs; a networked one
    runs only when networking is explicitly enabled. No implicit egress.
  * Repo-provided scripts are NEVER auto-run without explicit sandboxed
    authorization (AUTO_RUN_REPO_SCRIPTS is False).

Supply chain:
  * ``assert_dependency_free_core`` checks every shared engine module imports only
    the Python standard library (plus sibling modules loaded by path), protecting
    the zero-setup property.
  * Manifest-version consistency is gated by Phase 6.4; CI action pinning is a
    documented policy in the operations runbook.
"""

from __future__ import annotations

import ast
import sys
from fnmatch import fnmatch
from importlib import util as _import_util
from pathlib import Path

# QB never auto-runs scripts supplied by the repository under audit.
AUTO_RUN_REPO_SCRIPTS = False


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
resolve_within = _cs.resolve_within


class PrivilegeError(Exception):
    pass


# --- write least privilege ----------------------------------------------------
def write_allowed(repo_root, rel_path: str, allowlist) -> bool:
    """Default-deny: only repo-contained paths matching an allowlist glob are writable."""
    if not allowlist:
        return False                       # empty allowlist => deny all writes
    try:
        resolve_within(repo_root, rel_path)  # refuses traversal / out-of-repo
    except (ValueError, Exception):
        return False
    return any(fnmatch(rel_path, glob) for glob in allowlist)


def assert_write(repo_root, rel_path: str, allowlist) -> None:
    """Fail-closed enforcement: raise unless the write is allowed."""
    if not write_allowed(repo_root, rel_path, allowlist):
        raise PrivilegeError(f"write denied by least-privilege policy: {rel_path}")


# --- network least privilege --------------------------------------------------
def network_allowed(*, analyzer_is_offline: bool, allow_networked: bool) -> bool:
    """Offline analyzers always run; networked ones only when explicitly enabled."""
    if analyzer_is_offline:
        return True
    return bool(allow_networked)


# --- repo-provided script execution ------------------------------------------
def may_run_repo_script(*, sandboxed_authorization: bool = False) -> bool:
    """A target-supplied script runs only under explicit, sandboxed authorization."""
    return bool(AUTO_RUN_REPO_SCRIPTS) or bool(sandboxed_authorization)


# --- supply chain: dependency-free core --------------------------------------
_ALLOWED_IMPORT_ROOTS = set(getattr(sys, "stdlib_module_names", set())) | {"__future__"}


def _top_level_import_roots(source: str):
    roots = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".", 1)[0])
    return roots


def assert_dependency_free_core(scripts_dir) -> list:
    """Return [(file, module), ...] for any non-stdlib import in the engine (empty == clean)."""
    violations = []
    for path in sorted(Path(scripts_dir).glob("*.py")):
        try:
            roots = _top_level_import_roots(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for root in sorted(roots):
            if root not in _ALLOWED_IMPORT_ROOTS:
                violations.append((path.name, root))
    return violations
