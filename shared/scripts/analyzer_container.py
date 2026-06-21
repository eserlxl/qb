"""QB container-config analyzer (breadth completion, net-new).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).

Extends QB's ``config`` breadth coverage from dotenv/npmrc hygiene
(``ConfigHygieneAnalyzer``) to **container runtime manifests** -- closing the
``docs/analyzer-coverage.md`` gap: "Dockerfiles, compose files, and Kubernetes
manifests are not checked for high-risk defaults such as privileged containers,
broad host mounts, or missing non-root execution."

It is an ordinary instance of the existing read-only ``Analyzer`` contract (not a
new subsystem): it emits ``config`` findings -- the live category already bound to
the fixer's ``config-review`` recipe. Remediating a container privilege setting is
a human decision, so every finding is ``manual``.

Design (deliberately low-false-positive, stdlib-only -- no YAML parser):

  * It only scans files it can positively identify as container manifests:
      - Docker Compose files (``compose.y[a]ml`` / ``docker-compose*.y[a]ml``);
      - Kubernetes manifests (a ``.y[a]ml`` whose text declares both a top-level
        ``apiVersion:`` and a top-level ``kind:`` key).
    Arbitrary YAML is never scanned, so a stray ``privileged: true`` outside a
    container manifest is never flagged.
  * Within a scanned manifest it flags only **unambiguous, deterministic
    high-risk tokens**, each a documented container-escape / host-exposure
    default, matched line-by-line so every finding carries a precise locator:
      - ``privileged: true``                 -> full host device access;
      - ``hostNetwork: true`` (k8s) /
        ``network_mode: host`` (compose)     -> shares the host network namespace;
      - ``hostPID: true`` / ``hostIPC: true`` -> shares the host process/IPC namespace;
      - ``allowPrivilegeEscalation: true``   -> permits setuid privilege escalation;
      - a bind mount of ``/var/run/docker.sock`` -> hands the container control of
        the host Docker daemon.
    Booleans must be the literal YAML ``true``; ``false`` and absent keys are never
    flagged, so a manifest that explicitly hardens itself produces no finding.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_ai = _load_sibling("qb_analyzer_interface", "analyzer_interface.py")
_core = _load_sibling("qb_analyzer_core", "analyzer_core.py")
AnalyzerDescriptor = _ai.AnalyzerDescriptor
Finding = _ai.Finding
compute_finding_id = _ai.compute_finding_id
validate_finding = _ai.validate_finding
iter_repo_files = _core.iter_repo_files
confidence_for_rule = _core.confidence_for_rule

# A Docker Compose manifest by filename: compose.y[a]ml or docker-compose*.y[a]ml.
_COMPOSE_NAME_RE = re.compile(r"^(?:docker-compose.*|compose)\.ya?ml$", re.IGNORECASE)
# A Kubernetes manifest declares both keys at column 0 (top-level mapping). The
# combination is what distinguishes a k8s object from an arbitrary YAML document.
_K8S_APIVERSION_RE = re.compile(r"^apiVersion\s*:", re.MULTILINE)
_K8S_KIND_RE = re.compile(r"^kind\s*:", re.MULTILINE)


def _is_compose_file(name: str) -> bool:
    return bool(_COMPOSE_NAME_RE.match(name))


def _looks_like_k8s(text: str) -> bool:
    return bool(_K8S_APIVERSION_RE.search(text) and _K8S_KIND_RE.search(text))


# (rule_key, severity, scope, line-pattern, rationale, suggested_fix). ``scope`` is
# "compose", "k8s", or "any" -- a rule only fires on a manifest of a kind it applies
# to, so a compose-only key never produces a finding inside a k8s manifest.
_RULES: tuple[tuple[str, str, str, "re.Pattern[str]", str, str], ...] = (
    (
        "privileged-container", "P1", "any",
        re.compile(r"^\s*-?\s*privileged\s*:\s*true\b"),
        "runs the container in privileged mode, granting full access to host "
        "devices and effectively disabling container isolation",
        "Remove 'privileged: true'; grant only the specific capabilities the "
        "workload needs (e.g. cap_add) instead of full host-device access.",
    ),
    (
        "host-network", "P1", "k8s",
        re.compile(r"^\s*hostNetwork\s*:\s*true\b"),
        "shares the host network namespace (hostNetwork), exposing all host "
        "interfaces to the container and bypassing network policy",
        "Remove 'hostNetwork: true' and expose only the ports the workload needs "
        "through a Service.",
    ),
    (
        "host-network", "P1", "compose",
        re.compile(r"""^\s*network_mode\s*:\s*["']?host\b"""),
        "shares the host network namespace (network_mode: host), exposing all "
        "host interfaces to the container",
        "Drop 'network_mode: host' and publish only the required ports.",
    ),
    (
        "host-namespace", "P1", "k8s",
        re.compile(r"^\s*host(?:PID|IPC)\s*:\s*true\b"),
        "shares a host namespace (hostPID/hostIPC), letting the container observe "
        "or signal host processes and shared memory",
        "Remove the hostPID/hostIPC setting so the container keeps its own "
        "process and IPC namespaces.",
    ),
    (
        "allow-privilege-escalation", "P2", "k8s",
        re.compile(r"^\s*allowPrivilegeEscalation\s*:\s*true\b"),
        "permits setuid/file-capability privilege escalation "
        "(allowPrivilegeEscalation: true) inside the container",
        "Set 'allowPrivilegeEscalation: false' in the container securityContext.",
    ),
    (
        "docker-socket-mount", "P1", "any",
        re.compile(r"/var/run/docker\.sock\b"),
        "mounts the host Docker socket (/var/run/docker.sock), which hands the "
        "container full control of the host Docker daemon (a host-takeover path)",
        "Remove the /var/run/docker.sock mount; use a scoped API or a "
        "socket-proxy with a restricted allowlist if daemon access is required.",
    ),
)


class ContainerConfigAnalyzer:
    """Read-only analyzer: flags high-risk defaults in container manifests."""

    descriptor = AnalyzerDescriptor(
        id="container-config",
        categories=("config",),
        offline=True,
    )

    def analyze(self, repo_root: str, config) -> list:
        root = Path(repo_root).resolve()
        findings: list = []
        if not root.is_dir():
            return findings
        for path in iter_repo_files(root, config):
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            is_compose = _is_compose_file(path.name)
            is_k8s = _looks_like_k8s(text)
            if not (is_compose or is_k8s):
                continue
            rel = path.relative_to(root).as_posix()
            for line_number, raw in enumerate(text.splitlines(), start=1):
                for rule_key, severity, scope, pattern, rationale, fix in _RULES:
                    if scope == "compose" and not is_compose:
                        continue
                    if scope == "k8s" and not is_k8s:
                        continue
                    if not pattern.search(raw):
                        continue
                    evidence = f"{rel}:{line_number}"
                    finding = Finding(
                        id=compute_finding_id("config", evidence, rule_key),
                        category="config",
                        severity=severity,
                        confidence=confidence_for_rule(self.descriptor.id, rule_key),
                        evidence=evidence,
                        rationale=f"The container manifest {rel} {rationale}.",
                        suggested_fix=fix,
                        fix_strategy="manual",
                    )
                    # A non-conformant locator (e.g. a spaced directory in the path)
                    # must never enter the store; emit only conformant findings.
                    if validate_finding(finding):
                        continue
                    findings.append(finding)
        findings.sort(key=lambda item: (item.evidence, item.id))
        return findings
