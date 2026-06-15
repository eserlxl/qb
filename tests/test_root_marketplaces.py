"""The repo-root marketplace manifests register the qb plugin for each host.

Cursor and Codex still self-host: Cursor reads ``.cursor-plugin/marketplace.json``
and Codex reads ``.agents/plugins/marketplace.json``. Each must register exactly
the ``qb`` plugin under the marketplace named ``eserlxl`` with a ``./``-relative
source that points at the real platform package (the directory holding that host's
per-plugin manifest). These root files are NOT covered by the per-platform
``validate.sh`` (which run inside ``platforms/<host>``), so this guards them at the
monorepo level.

Claude Code is deliberately NOT in this list: its package is plugin-only and is
distributed via the dedicated ``eserlxl/claude-marketplace`` aggregator repo (which
references this repo with a ``git-subdir`` source). Two repos cannot both claim the
marketplace name ``eserlxl`` without colliding, so this repo no longer ships a
Claude Code marketplace manifest. ``test_claude_code_package_is_plugin_only`` pins
that invariant so the manifests cannot silently return.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.qb_monorepo import REPO_ROOT

# (root marketplace manifest, per-plugin manifest expected inside the source dir)
# Claude Code is intentionally excluded: it is plugin-only and distributed via the
# external eserlxl/claude-marketplace aggregator. See the module docstring.
ROOT_MARKETPLACES = [
    (".agents/plugins/marketplace.json", ".codex-plugin/plugin.json"),
    (".cursor-plugin/marketplace.json", ".cursor-plugin/plugin.json"),
]

# Paths that must NOT exist: this repo no longer declares a Claude Code marketplace.
CLAUDE_CODE_MARKETPLACE_MANIFESTS = [
    ".claude-plugin/marketplace.json",
    "platforms/claude-code/.claude-plugin/marketplace.json",
]


def _source_path(plugin: dict) -> str:
    """Source is a ./-relative string (Claude Code / Cursor) or {source, path} (Codex)."""
    source = plugin["source"]
    return source["path"] if isinstance(source, dict) else source


class RootMarketplaceTests(unittest.TestCase):
    def test_each_root_marketplace_registers_qb_under_eserlxl(self) -> None:
        for manifest_rel, plugin_manifest_rel in ROOT_MARKETPLACES:
            with self.subTest(manifest=manifest_rel):
                manifest_path = REPO_ROOT / manifest_rel
                self.assertTrue(
                    manifest_path.is_file(), f"missing root marketplace: {manifest_rel}"
                )
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(
                    data.get("name"), "eserlxl", f"marketplace name in {manifest_rel}"
                )
                plugins = data.get("plugins")
                self.assertIsInstance(plugins, list, f"plugins[] in {manifest_rel}")
                self.assertEqual(
                    len(plugins), 1, f"expected exactly one plugin in {manifest_rel}"
                )
                plugin = plugins[0]
                self.assertEqual(plugin.get("name"), "qb", f"plugin name in {manifest_rel}")
                src = _source_path(plugin)
                self.assertTrue(
                    src.startswith("./"),
                    f"source must be ./-relative in {manifest_rel}: {src!r}",
                )
                src_dir = (REPO_ROOT / src).resolve()
                self.assertTrue(
                    src_dir.is_dir(), f"source dir missing for {manifest_rel}: {src}"
                )
                self.assertTrue(
                    (src_dir / plugin_manifest_rel).is_file(),
                    f"{src}/{plugin_manifest_rel} not found (referenced by {manifest_rel})",
                )

    def test_claude_code_package_is_plugin_only(self) -> None:
        # The Claude Code package ships NO marketplace manifest; it is distributed
        # via the external eserlxl/claude-marketplace aggregator. Re-introducing a manifest
        # here would re-create the marketplace-name collision on "eserlxl".
        for manifest_rel in CLAUDE_CODE_MARKETPLACE_MANIFESTS:
            with self.subTest(manifest=manifest_rel):
                self.assertFalse(
                    (REPO_ROOT / manifest_rel).exists(),
                    f"Claude Code is plugin-only; {manifest_rel} must not exist "
                    f"(it would collide with the eserlxl/claude-marketplace aggregator)",
                )
        # The plugin manifest itself must still be present.
        self.assertTrue(
            (REPO_ROOT / "platforms/claude-code/.claude-plugin/plugin.json").is_file(),
            "Claude Code plugin manifest missing",
        )


if __name__ == "__main__":
    unittest.main()
