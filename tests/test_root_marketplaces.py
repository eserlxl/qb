"""The repo-root marketplace manifests register the qb plugin for each host.

Each host's CLI/UI installs from the repository ROOT: Claude Code reads
``.claude-plugin/marketplace.json``, Codex reads
``.agents/plugins/marketplace.json``, and Cursor reads
``.cursor-plugin/marketplace.json``. Each must register exactly the ``qb`` plugin
under the marketplace named ``eserlxl`` with a ``./``-relative source that points
at the real platform package (the directory holding that host's per-plugin
manifest). These root files are NOT covered by the per-platform ``validate.sh``
(which run inside ``platforms/<host>``), so this guards them at the monorepo level.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.qb_monorepo import REPO_ROOT

# (root marketplace manifest, per-plugin manifest expected inside the source dir)
ROOT_MARKETPLACES = [
    (".claude-plugin/marketplace.json", ".claude-plugin/plugin.json"),
    (".agents/plugins/marketplace.json", ".codex-plugin/plugin.json"),
    (".cursor-plugin/marketplace.json", ".cursor-plugin/plugin.json"),
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


if __name__ == "__main__":
    unittest.main()
