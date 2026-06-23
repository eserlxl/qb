#!/usr/bin/env python3
"""Repo-hygiene guard: no private / machine-local identifier in a public doc.

QB's release-facing docs ship publicly (they travel in the sanitized export and
live in a public tree), so a machine-local path such as ``/home/<user>/...`` or a
``/Users/<user>/...`` path, a resolved ``/private/tmp`` path, a Windows user path,
or a stray UUID leaked into one of them is a real privacy exposure. The credential
guard (``tests/test_no_committed_secrets.py`` over ``SECRET_PATTERNS``) covers
*credentials* only -- it does not flag filesystem paths or UUIDs -- so this module
is the single source of truth for the *private-identifier* class, mirroring how
``SECRET_PATTERNS`` lives once in ``analyzer_core.py`` and is imported (never
duplicated) by its guard test.

This is repo-level release tooling (a sibling of ``scripts/release-manifest.py``),
not host-neutral engine IP, so it lives under ``scripts/`` and is deliberately NOT
fanned into the per-host platform copies by ``scripts/sync.sh``.

Usage:
    python3 scripts/public_privacy.py [PATH ...]

With no PATH the canonical release-facing doc set (``PUBLIC_DOCS``) is scanned.
Prints ``<path>:<line>:<rule>`` for every match and exits non-zero when any
private identifier is found; exits 0 on a clean set. A line carrying the inline
``pragma: allowlist private`` marker is skipped (for a deliberate example).
Standard library only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# scripts/ lives directly under the repo root (like tests/).
REPO_ROOT = Path(__file__).resolve().parents[1]

# Inline opt-out for a deliberate documentation example (mirrors the secret
# guard's ``pragma: allowlist secret`` convention).
ALLOW_MARKER = "pragma: allowlist private"

# The canonical private-identifier classes. A list of ``(name, compiled)`` tuples,
# mirroring ``analyzer_core.SECRET_PATTERNS`` so a guard test can import this single
# source and stay in lockstep instead of hand-copying the patterns.
PRIVATE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Unix home directory with a concrete user segment: /home/<user>...
    ("unix_home_path", re.compile(r"/home/[A-Za-z0-9._-]+")),
    # macOS home directory with a concrete user segment: /Users/<user>...
    ("macos_users_path", re.compile(r"/Users/[A-Za-z0-9._-]+")),
    # macOS resolved private temp/var roots: /private/tmp/... or /private/var/...
    ("macos_private_path", re.compile(r"/private/(?:tmp|var)/")),
    # Windows user profile path: C:\Users\<user>...
    ("windows_user_path", re.compile(r"[A-Za-z]:\\Users\\[A-Za-z0-9._-]+")),
    # Canonical-form UUID (8-4-4-4-12 hex), a common machine-local identifier.
    (
        "uuid",
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        ),
    ),
]

# The release-facing documents that ship publicly. Root policy/readme docs plus the
# docs/ tree. Resolved lazily so the set tracks the actual docs/ contents.
_ROOT_DOCS = (
    "README.md",
    "RUNBOOK.md",
    "RELEASING.md",
    "BASELINE.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
)


def public_docs(root: Path = REPO_ROOT) -> list[Path]:
    """Return the canonical release-facing doc set that exists under ``root``."""
    docs = [root / name for name in _ROOT_DOCS]
    docs.extend(sorted((root / "docs").glob("*.md")))
    return [path for path in docs if path.is_file()]


def scan_text(text: str) -> list[tuple[int, str]]:
    """Return ``(line_number, rule_name)`` for each private identifier in ``text``.

    A line carrying the ``ALLOW_MARKER`` is skipped entirely.
    """
    findings: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        for name, pattern in PRIVATE_PATTERNS:
            if pattern.search(line):
                findings.append((line_number, name))
    return findings


def scan_paths(paths: list[Path], root: Path = REPO_ROOT) -> list[str]:
    """Scan each path, returning ``<relpath>:<line>:<rule>`` finding strings."""
    findings: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        try:
            rel = path.resolve().relative_to(root)
        except ValueError:
            rel = path
        for line_number, name in scan_text(text):
            findings.append(f"{rel}:{line_number}:{name}")
    return findings


def main(argv: list[str]) -> int:
    if argv:
        paths = [Path(arg) for arg in argv]
    else:
        paths = public_docs()
    findings = scan_paths(paths)
    for finding in findings:
        print(finding)
    if findings:
        print(
            f"public_privacy: {len(findings)} private identifier(s) found "
            f"(add an inline '{ALLOW_MARKER}' marker if an example is intentional).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
