"""Phase 5.1 -- the Codex standalone package's marketplace source resolves to a
real package directory holding the launch entrypoint.

Scope note (no duplication): the two repo-root marketplace manifests
(`.agents/plugins/marketplace.json`, `.cursor-plugin/marketplace.json`) already
have their source paths resolved to a package directory by
`test_root_marketplaces`. The Codex *standalone* package ships its own marketplace
at `platforms/codex/.agents/plugins/marketplace.json`, and its local `source.path`
is resolved by neither that test nor codex `validate.sh` (which JSON-parses the
manifest and checks its name + required files directly, but never that the
marketplace source points at a real package). This guards that one uncovered link
so a broken standalone-install source path cannot ship.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.qb_monorepo import REPO_ROOT

CODEX_MARKETPLACE = REPO_ROOT / "platforms/codex/.agents/plugins/marketplace.json"


class CodexStandaloneInstallPathTest(unittest.TestCase):
    def test_marketplace_source_resolves_to_package_with_entrypoint(self):
        self.assertTrue(CODEX_MARKETPLACE.is_file(), f"missing manifest: {CODEX_MARKETPLACE}")
        data = json.loads(CODEX_MARKETPLACE.read_text(encoding="utf-8"))

        plugins = data.get("plugins")
        self.assertIsInstance(plugins, list, "marketplace plugins[] must be a list")
        self.assertEqual(len(plugins), 1, "expected exactly one registered plugin")
        plugin = plugins[0]
        self.assertEqual(plugin.get("name"), "qb")

        source = plugin["source"]
        path = source["path"] if isinstance(source, dict) else source
        self.assertTrue(path.startswith("./"), f"source path must be ./-relative: {path!r}")

        # The standalone package root is the directory that holds the .agents tree.
        package_root = CODEX_MARKETPLACE.parent.parent.parent  # platforms/codex
        resolved = (package_root / path).resolve()
        self.assertTrue(resolved.is_dir(),
                        f"marketplace source resolves to no package dir: {resolved}")
        # The resolved package must carry the Codex launch entrypoint.
        self.assertTrue((resolved / "skills/qb/SKILL.md").is_file(),
                        f"launch entrypoint skills/qb/SKILL.md missing under {resolved}")


if __name__ == "__main__":
    unittest.main()
