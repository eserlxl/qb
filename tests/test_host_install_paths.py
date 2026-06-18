"""Host package installation docs and standalone marketplace paths.

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
READMES = {
    "claude-code": REPO_ROOT / "platforms/claude-code/README.md",
    "cursor": REPO_ROOT / "platforms/cursor/README.md",
    "codex": REPO_ROOT / "platforms/codex/README.md",
    "antigravity": REPO_ROOT / "platforms/antigravity/README.md",
}


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


class HostReadmeInstallContractTest(unittest.TestCase):
    def _read(self, host: str) -> str:
        path = READMES[host]
        self.assertTrue(path.is_file(), f"{host} README missing: {path}")
        return path.read_text(encoding="utf-8")

    def test_readmes_name_install_paths_that_exist(self):
        expected = {
            "claude-code": [
                "platforms/claude-code",
                "/plugin marketplace add eserlxl/qb",
                "/plugin install qb@eserlxl",
            ],
            "cursor": [
                "qb/platforms/cursor",
                "~/.cursor/plugins/local/qb",
            ],
            "codex": [
                "codex plugin marketplace add eserlxl/qb --ref main",
                "cd /absolute/path/to/qb/platforms/codex",
                "codex plugin marketplace add .",
            ],
            "antigravity": [
                "cd platforms/antigravity",
                "scripts/install.sh --scope app-global --force",
                "scripts/install.sh --scope ide-project --target /path/to/project",
                "scripts/install.sh --scope cli-global",
            ],
        }
        for host, fragments in expected.items():
            text = self._read(host)
            with self.subTest(host=host):
                for fragment in fragments:
                    self.assertIn(fragment, text, f"{host} README omits install fragment: {fragment}")

        self.assertTrue((REPO_ROOT / "platforms/claude-code").is_dir())
        self.assertTrue((REPO_ROOT / "platforms/cursor").is_dir())
        self.assertTrue((REPO_ROOT / "platforms/codex").is_dir())
        self.assertTrue((REPO_ROOT / "platforms/antigravity/scripts/install.sh").is_file())

    def test_readmes_name_correct_runtime_entrypoints(self):
        expectations = {
            "claude-code": ("/qb-plan", "/qb-harden"),
            "cursor": ("/qb-plan", "/qb-harden"),
            "codex": ("Use $qb to inspect this repo and plan this project.",
                      "Use $qb. Run the audit and harden engine over this repository."),
            "antigravity": ("/qb-plan", "/qb-plan auto"),
        }
        for host, fragments in expectations.items():
            text = self._read(host)
            with self.subTest(host=host):
                for fragment in fragments:
                    self.assertIn(fragment, text, f"{host} README omits runtime entrypoint: {fragment}")

        self.assertTrue((REPO_ROOT / "platforms/claude-code/commands/qb-harden.md").is_file())
        self.assertTrue((REPO_ROOT / "platforms/cursor/commands/qb-harden.md").is_file())
        self.assertTrue((REPO_ROOT / "platforms/codex/plugins/qb/skills/qb/scripts/qb_headless.py").is_file())
        self.assertTrue((REPO_ROOT / "platforms/antigravity/skills/qb/SKILL.md").is_file())

    def test_antigravity_readme_does_not_overclaim_engine_support(self):
        text = self._read("antigravity")
        self.assertIn("planning-only", text.lower())
        self.assertIn("not the audit/harden engine", text)
        self.assertNotIn("/qb-harden", text)
        self.assertNotIn("$qb", text)


if __name__ == "__main__":
    unittest.main()
