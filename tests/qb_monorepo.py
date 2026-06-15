"""Shared helpers for the top-level QB monorepo invariant tests.

These tests assert cross-platform / monorepo-level invariants only. The
validator *behavior* is covered by each platform's own ``validate.sh`` unit
suite, so we do not duplicate that heavy testing here.

Platforms are built in parallel and a package may legitimately not exist yet
while the monorepo is under construction. Where a platform's manifest is
absent, the relevant test ``skipTest``s instead of failing, so the suite stays
green during construction while still fully asserting the invariants once every
platform is present.
"""

from __future__ import annotations

import json
from pathlib import Path

# tests/ lives directly under the repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED_DIR = REPO_ROOT / "shared"
PLATFORMS_DIR = REPO_ROOT / "platforms"


# --- Per-platform descriptors -------------------------------------------------
# Each platform declares: its expected plugin id, the manifest path (relative to
# the repo root), the manifest filename's own directory marker, and the set of
# cross-host tokens that must NOT appear in its hand-authored host files.

CLAUDE_CODE = {
    "id": "qb",
    "root": PLATFORMS_DIR / "claude-code",
    "manifest": PLATFORMS_DIR / "claude-code/.claude-plugin/plugin.json",
    "forbidden": ("$qb", "define-goal", ".cursor-plugin", ".codex-plugin"),
}

CURSOR = {
    "id": "qb",
    "root": PLATFORMS_DIR / "cursor",
    "manifest": PLATFORMS_DIR / "cursor/.cursor-plugin/plugin.json",
    "forbidden": ("$qb", ".claude-plugin", ".codex-plugin"),
}

CODEX = {
    "id": "qb",
    "root": PLATFORMS_DIR / "codex",
    "manifest": PLATFORMS_DIR / "codex/plugins/qb/.codex-plugin/plugin.json",
    "forbidden": (
        ".claude-plugin",
        ".cursor-plugin",
        "define-goal",
        "create_goal",
        "get_goal",
    ),
}

ALL_PLATFORMS = (CLAUDE_CODE, CURSOR, CODEX)


def load_manifest(platform: dict) -> dict:
    """Parse a platform manifest as JSON (raises on invalid JSON)."""
    return json.loads(platform["manifest"].read_text(encoding="utf-8"))


def frontmatter_name(text: str) -> str | None:
    """Return the YAML-frontmatter ``name:`` value of a markdown component, or None.

    Only the leading frontmatter block is consulted: scanning stops at the
    closing ``---`` so a ``name:`` mention in the body never leaks in.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        # No frontmatter block; fall back to a tolerant top-of-file scan.
        for line in lines:
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip()
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    return None
