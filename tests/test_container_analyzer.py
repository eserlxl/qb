"""Net-new container-config analyzer.

Extends the ``config`` breadth coverage from dotenv/npmrc hygiene to container
runtime manifests, closing the ``docs/analyzer-coverage.md`` gap "Dockerfiles,
compose files, and Kubernetes manifests are not checked for high-risk defaults".
Pins: the deterministic high-risk tokens (privileged, host namespaces, privilege
escalation, docker-socket mount) on Compose and Kubernetes manifests, the
manifest-only file gating (a stray ``privileged: true`` in unrelated YAML is NOT
flagged), the ``false``/absent no-finding cases, schema conformance, read-only
behavior, confidence-policy coverage, and registration in the default registry.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

CONTAINER_PATH = SHARED_DIR / "scripts/analyzer_container.py"
INTERFACE_PATH = SHARED_DIR / "scripts/analyzer_interface.py"
CORE_PATH = SHARED_DIR / "scripts/analyzer_core.py"
RUNNER_PATH = SHARED_DIR / "scripts/audit_runner.py"

_COMPOSE_RISKY = """services:
  app:
    image: example/app:1.0.0
    privileged: true
    network_mode: host
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
"""

_K8S_RISKY = """apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      hostNetwork: true
      hostPID: true
      containers:
        - name: app
          securityContext:
            privileged: true
            allowPrivilegeEscalation: true
"""


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ContainerAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        if not CONTAINER_PATH.exists():
            self.skipTest("analyzer_container not built yet")
        self.mod = _load("qb_analyzer_container_under_test", CONTAINER_PATH)
        self.ai = _load("qb_analyzer_interface", INTERFACE_PATH)
        self.cfg = self.ai.AnalyzerConfig()

    def _analyze(self, files: dict) -> list:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, content in files.items():
                (root / name).write_text(content, encoding="utf-8")
            return self.mod.ContainerConfigAnalyzer().analyze(str(root), self.cfg)

    def _rules(self, findings) -> set:
        # Re-derive the rule_key from the finding id: compute_finding_id hashes
        # (category, evidence, rule_key), so match each finding back to its rule.
        compute = self.ai.compute_finding_id
        keys = {"privileged-container", "host-network", "host-namespace",
                "allow-privilege-escalation", "docker-socket-mount"}
        out = set()
        for f in findings:
            for key in keys:
                if compute("config", f.evidence, key) == f.id:
                    out.add(key)
        return out

    def test_compose_high_risk_tokens_flagged(self) -> None:
        findings = self._analyze({"docker-compose.yml": _COMPOSE_RISKY})
        self.assertEqual(
            {f.evidence for f in findings},
            {"docker-compose.yml:4", "docker-compose.yml:5", "docker-compose.yml:7"},
        )
        self.assertEqual(
            self._rules(findings),
            {"privileged-container", "host-network", "docker-socket-mount"},
        )
        for f in findings:
            self.assertEqual(f.category, "config")
            self.assertEqual(f.fix_strategy, "manual")
            self.assertEqual(self.ai.validate_finding(f), [])

    def test_compose_name_variants_are_scanned(self) -> None:
        for name in ("compose.yaml", "docker-compose.prod.yml"):
            findings = self._analyze({name: "services:\n  a:\n    privileged: true\n"})
            self.assertEqual([f.evidence for f in findings], [f"{name}:3"], name)

    def test_kubernetes_high_risk_tokens_flagged(self) -> None:
        findings = self._analyze({"deploy.yaml": _K8S_RISKY})
        self.assertEqual(
            {f.evidence for f in findings},
            {"deploy.yaml:6", "deploy.yaml:7", "deploy.yaml:11", "deploy.yaml:12"},
        )
        self.assertEqual(
            self._rules(findings),
            {"host-network", "host-namespace", "privileged-container",
             "allow-privilege-escalation"},
        )

    def test_non_manifest_yaml_is_not_scanned(self) -> None:
        # The exact same risky token in a YAML file that is NOT a compose/k8s
        # manifest must be ignored -- this is the false-positive control.
        self.assertEqual(
            self._analyze({"settings.yaml": "foo: bar\nprivileged: true\n"}),
            [],
        )

    def test_hardened_manifests_yield_nothing(self) -> None:
        clean_compose = "services:\n  web:\n    image: nginx\n    read_only: true\n"
        clean_k8s = (
            "apiVersion: apps/v1\nkind: Deployment\nspec:\n  template:\n    spec:\n"
            "      containers:\n        - name: app\n          securityContext:\n"
            "            privileged: false\n            allowPrivilegeEscalation: false\n"
            "            runAsNonRoot: true\n"
        )
        self.assertEqual(self._analyze({"docker-compose.yml": clean_compose}), [])
        self.assertEqual(self._analyze({"k8s.yaml": clean_k8s}), [])

    def test_compose_only_rule_does_not_fire_in_k8s(self) -> None:
        # network_mode is a compose key; a k8s manifest that happens to contain
        # the substring must not produce a host-network finding from that rule.
        k8s = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: x\n# network_mode: host\n"
        self.assertEqual(self._analyze({"pod.yaml": k8s}), [])

    def test_clean_repo_yields_nothing(self) -> None:
        self.assertEqual(self._analyze({"README.md": "# p\n", "config.json": "{}\n"}), [])

    def test_findings_are_sorted_and_deterministic(self) -> None:
        first = self._analyze({"docker-compose.yml": _COMPOSE_RISKY})
        second = self._analyze({"docker-compose.yml": _COMPOSE_RISKY})
        self.assertEqual([f.evidence for f in first], [f.evidence for f in second])
        self.assertEqual(
            [f.evidence for f in first], sorted(f.evidence for f in first)
        )

    def test_internal_vendor_dirs_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "docker-compose.yml").write_text(
                _COMPOSE_RISKY, encoding="utf-8")
            self.assertEqual(
                self.mod.ContainerConfigAnalyzer().analyze(str(root), self.cfg), [])

    def test_analyzer_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docker-compose.yml").write_text(_COMPOSE_RISKY, encoding="utf-8")
            before = sorted(p.name for p in root.iterdir())
            self.mod.ContainerConfigAnalyzer().analyze(str(root), self.cfg)
            self.assertEqual(before, sorted(p.name for p in root.iterdir()))

    def test_descriptor_and_default_registration(self) -> None:
        descriptor = self.mod.ContainerConfigAnalyzer().descriptor
        self.assertEqual(descriptor.id, "container-config")
        self.assertEqual(descriptor.categories, ("config",))
        self.assertTrue(descriptor.offline)
        runner = _load("qb_audit_runner_container_test", RUNNER_PATH)
        ids = {a.descriptor.id for a in runner.build_default_registry().analyzers()}
        self.assertIn("container-config", ids)

    def test_confidence_policy_covers_every_rule(self) -> None:
        core = _load("qb_analyzer_core", CORE_PATH)
        for rule in ("privileged-container", "host-network", "host-namespace",
                     "allow-privilege-escalation", "docker-socket-mount"):
            self.assertIn(core.confidence_for_rule("container-config", rule),
                          ("low", "medium", "high"))


if __name__ == "__main__":
    unittest.main()
