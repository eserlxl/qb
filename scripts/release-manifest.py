#!/usr/bin/env python3
"""QB release-integrity manifest (Phase 8.4) -- standard library only.

Emits a deterministic manifest of the SANITIZED export tree -- the git-tracked files
`git archive` ships (gitignored trees such as .qb/, QB-Audit/, .planwright/ are
excluded by construction) -- with a SHA-256 per file plus the root VERSION. The
manifest pins exactly what a release contains so a consumer can verify an artifact
byte-for-byte.

This is NOT cryptographic signing: it is an integrity/inventory manifest (a file list
+ content hashes + version), not an authenticity signature.

Usage:
  release-manifest.py [--root DIR]                       print the manifest to stdout
  release-manifest.py [--root DIR] --output FILE         write the manifest to FILE
  release-manifest.py [--root DIR] --check [--output F]
        --check without an existing --output: self-verify (the tree is fully hashable,
            VERSION is present + semver, the file set is non-empty) -> exit 0.
        --check with an existing --output: compare the freshly computed manifest to
            the stored one; exit 0 only when they match, 1 on any drift.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

MANIFEST_HEADER = "# QB release manifest v1"
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_ENTRY = re.compile(r"^[0-9a-f]{64}  ")


def _tracked_files(root: Path) -> list:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=str(root),
                            capture_output=True, text=True, check=True)
    return sorted(p for p in result.stdout.split("\0") if p)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _version(root: Path) -> str:
    version_file = root / "VERSION"
    if not version_file.is_file():
        raise FileNotFoundError("root VERSION file missing")
    return version_file.read_text(encoding="utf-8").strip()


def build_manifest(root) -> str:
    """Build the deterministic manifest text (sorted entries) for the tracked tree."""
    root = Path(root)
    version = _version(root)
    entries = []
    for rel in _tracked_files(root):
        fpath = root / rel
        if not fpath.is_file():     # a tracked path absent from the worktree -- skip
            continue
        entries.append(f"{_sha256(fpath)}  {rel}")
    lines = [MANIFEST_HEADER, f"version: {version}", f"files: {len(entries)}"]
    lines.extend(entries)
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit/verify the QB sanitized-export integrity manifest.")
    parser.add_argument("--root", default=".", help="Tree root to inventory (default: current dir).")
    parser.add_argument("--output", default=None, help="Write/compare the manifest at this path.")
    parser.add_argument("--check", action="store_true",
                        help="Verify the manifest matches the tree (exit 0 only when it does).")
    args = parser.parse_args(argv)

    try:
        manifest = build_manifest(args.root)
    except (FileNotFoundError, subprocess.CalledProcessError, OSError) as exc:
        sys.stderr.write(f"release-manifest: cannot build manifest: {exc}\n")
        return 1

    if not args.check:
        if args.output:
            Path(args.output).write_text(manifest, encoding="utf-8")
            print(f"release-manifest: wrote {args.output}")
        else:
            sys.stdout.write(manifest)
        return 0

    # --check: the manifest must be well-formed and match the tree.
    version_line = next((l for l in manifest.splitlines() if l.startswith("version: ")), "")
    version = version_line[len("version: "):].strip()
    if not _SEMVER.match(version):
        sys.stderr.write(f"release-manifest: --check failed: VERSION '{version}' is not semver\n")
        return 1
    file_count = sum(1 for l in manifest.splitlines() if _ENTRY.match(l))
    if file_count == 0:
        sys.stderr.write("release-manifest: --check failed: no tracked files in the tree\n")
        return 1
    if args.output and Path(args.output).is_file():
        if Path(args.output).read_text(encoding="utf-8") != manifest:
            sys.stderr.write(f"release-manifest: --check failed: tree drifted from {args.output}\n")
            return 1
        print(f"release-manifest: --check OK ({file_count} files) matches {args.output}")
        return 0
    print(f"release-manifest: --check OK ({file_count} files, version {version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
