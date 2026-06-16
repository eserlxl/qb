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

# Antigravity (Google's Gemini-based IDE) ships as a bare Agent Skill folder with
# NO JSON plugin manifest -- its version and identity live in skills/qb/SKILL.md
# frontmatter. It is kept OUT of ALL_PLATFORMS (the JSON-manifest set the
# version/manifest-id tests iterate) and exercised by dedicated antigravity tests
# plus its own scripts/validate.sh. Its planner specs are host-authored
# (vibecoding-first, divergent from shared/), so it is intentionally NOT a
# scripts/sync.sh destination.
ANTIGRAVITY = {
    "id": "qb",
    "root": PLATFORMS_DIR / "antigravity",
    "manifest": None,
    "skill": PLATFORMS_DIR / "antigravity/skills/qb/SKILL.md",
    "forbidden": (
        "$qb",
        "define-goal",
        "create_goal",
        "get_goal",
        ".claude-plugin",
        ".cursor-plugin",
        ".codex-plugin",
    ),
}

# The JSON-manifest platforms (version-lockstep + manifest-id tests iterate these).
ALL_PLATFORMS = (CLAUDE_CODE, CURSOR, CODEX)

# Every shipped platform package, including the manifest-less antigravity skill.
ALL_PACKAGES = (CLAUDE_CODE, CURSOR, CODEX, ANTIGRAVITY)


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


def frontmatter_version(text: str) -> str | None:
    """Return the ``metadata: version:`` value from a component's frontmatter, or None.

    Mirrors ``frontmatter_name``'s discipline: only the leading ``---`` block is
    consulted, and the version is read from the indented ``version:`` line that
    ``scripts/bump-version.sh`` writes under ``metadata:``. Surrounding quotes are
    stripped so ``version: "0.8.0"`` and ``version: 0.8.0`` both parse.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        # Indented version line (nested under metadata:); ignore a top-level one.
        if line[:1] in (" ", "\t") and line.strip().startswith("version:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return None
