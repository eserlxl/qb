"""Documentation drift guard (Phase 6.3).

A dependency-free (Python standard library only) root monorepo invariant test
that fails when the docs drift from the engine they describe. Each expected value
is derived from a source of truth rather than a hardcoded duplicate:

- producer-analyzer coverage   -> shared/scripts/audit_runner.build_default_registry()
- finding-category coverage    -> shared/scripts/finding_schema.CATEGORIES
- four-platform / planning-only -> filesystem (host packages + sync.sh exclusion)
- absence of "synced verbatim" -> filesystem (root + host READMEs)
- CHANGELOG version lockstep    -> filesystem (platforms/<host>/CHANGELOG.md)
- README version badge          -> root VERSION file

Scope: analyzer-naming is asserted against the root README (the product
source-of-truth doc for the audit/harden engine). Antigravity is planning-only
and ships no audit engine, so it is checked for the platform-model and CHANGELOG
invariants but intentionally excluded from the analyzer-naming assertion.
"""

from __future__ import annotations

import dataclasses
import re
import sys
import unittest

from tests.qb_monorepo import REPO_ROOT, SHARED_DIR, ALL_PACKAGES, ANTIGRAVITY

# Load the engine's registry/schema directly so the expected sets are derived,
# never hardcoded. shared/scripts is standard-library-only plus sibling imports.
_SCRIPTS_DIR = SHARED_DIR / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import audit_runner  # noqa: E402  (path set above)
import budget  # noqa: E402
import finding_schema  # noqa: E402

ROOT_README = REPO_ROOT / "README.md"
ROOT_VERSION = REPO_ROOT / "VERSION"
RUNBOOK = REPO_ROOT / "RUNBOOK.md"

# Derived sources of truth (computed once, not copied into the test).
PRODUCER_ANALYZERS = sorted(
    type(a).__name__ for a in audit_runner.build_default_registry().analyzers()
)
FINDING_CATEGORIES = sorted(finding_schema.CATEGORIES)
# RUNBOOK budget raise-path terms, derived from the budget engine (not hardcoded).
BUDGET_CEILINGS = sorted(f.name for f in dataclasses.fields(budget.Budget))
BUDGET_ADVICE = sorted((budget.ADVICE_CONSTRAINING, budget.ADVICE_PROTECTING,
                        budget.ADVICE_INSUFFICIENT))
HOST_NAMES = ("Claude Code", "Cursor", "Codex", "Antigravity")
_VERSION_HEADER = re.compile(r"^## \[([0-9]+\.[0-9]+\.[0-9]+)\]", re.MULTILINE)
# The shields.io badge: label 'version', the (possibly escaped) message, a
# 6-hex color, then the closing markdown-link paren. Mirrors the rewrite in
# scripts/bump-version.sh.
_README_BADGE = re.compile(r"https://img\.shields\.io/badge/version-(.+?)-[0-9A-Fa-f]{6}\)")
_COVERAGE_ANALYZERS = re.compile(
    r"The built-in producer analyzers are (?P<body>.*?)\.\s+Together",
    re.DOTALL,
)
_COVERAGE_CATEGORIES = re.compile(
    r"Together they cover the frozen finding categories (?P<body>.*?):",
    re.DOTALL,
)


def _backtick_values(text: str) -> list[str]:
    return sorted(set(re.findall(r"`([^`]+)`", text)))


class DocConsistencyTest(unittest.TestCase):
    def _read(self, path):
        self.assertTrue(path.is_file(), f"missing doc: {path}")
        return path.read_text(encoding="utf-8")

    def test_registry_is_nonempty(self):
        # Guards the derivation itself: an empty registry would make the coverage
        # assertions below vacuously pass.
        self.assertTrue(PRODUCER_ANALYZERS, "no producer analyzers derived from registry")
        self.assertTrue(FINDING_CATEGORIES, "no finding categories derived from schema")

    def test_root_readme_names_every_producer_analyzer(self):
        text = self._read(ROOT_README)
        missing = [name for name in PRODUCER_ANALYZERS if name not in text]
        self.assertEqual(
            missing, [], f"root README omits registered producer analyzers: {missing}"
        )

    def test_root_readme_names_every_finding_category(self):
        text = self._read(ROOT_README)
        missing = [c for c in FINDING_CATEGORIES if c not in text]
        self.assertEqual(
            missing, [], f"root README omits finding categories: {missing}"
        )

    def test_root_readme_analyzer_coverage_matches_registry(self):
        text = self._read(ROOT_README)
        match = _COVERAGE_ANALYZERS.search(text)
        self.assertIsNotNone(match, "root README has no producer-analyzer coverage sentence")
        declared = _backtick_values(match.group("body"))
        self.assertEqual(declared, PRODUCER_ANALYZERS)

    def test_root_readme_category_coverage_matches_schema(self):
        text = self._read(ROOT_README)
        match = _COVERAGE_CATEGORIES.search(text)
        self.assertIsNotNone(match, "root README has no finding-category coverage sentence")
        declared = _backtick_values(match.group("body"))
        self.assertEqual(declared, FINDING_CATEGORIES)

    def test_root_readme_version_badge_matches_version_file(self):
        # The shields.io version badge is prose, not frontmatter, so the manifest
        # lockstep does not cover it; scripts/bump-version.sh rewrites it and this
        # invariant guarantees it never drifts from VERSION.
        declared = self._read(ROOT_VERSION).strip()
        text = self._read(ROOT_README)
        match = _README_BADGE.search(text)
        self.assertIsNotNone(
            match, "root README has no shields.io version badge to check"
        )
        # shields.io escapes '-' as '--' and '_' as '__' in the message field;
        # undo that before comparing to the raw VERSION value.
        badge = match.group(1).replace("--", "-").replace("__", "_")
        self.assertEqual(
            badge,
            declared,
            f"README version badge ({badge}) != VERSION ({declared}); "
            f"run scripts/bump-version.sh --sync",
        )

    def test_root_readme_states_four_platform_model(self):
        text = self._read(ROOT_README)
        for host in HOST_NAMES:
            self.assertIn(host, text, f"root README does not name host: {host}")
        self.assertIn(
            "planning-only",
            text.lower(),
            "root README must mark Antigravity as planning-only",
        )

    def test_antigravity_readme_states_planning_only(self):
        # Antigravity is planning-only; its README must say so, but it is NOT
        # required to enumerate the producer analyzers (it ships no engine).
        text = self._read(ANTIGRAVITY["root"] / "README.md")
        self.assertIn(
            "planning-only", text.lower(), "antigravity README must state planning-only"
        )

    def test_runbook_budget_raise_paths_match_engine(self):
        # The RUNBOOK budget raise-path guidance must name every budget ceiling and
        # every recommender advice value derived from budget.py, plus the recommender
        # and the explicit raise mechanism, so the operator narrative cannot drift
        # from the engine's actual ceilings/recommender.
        text = self._read(RUNBOOK)
        missing_ceilings = [name for name in BUDGET_CEILINGS if name not in text]
        self.assertEqual(missing_ceilings, [],
                         f"RUNBOOK omits budget ceilings: {missing_ceilings}")
        missing_advice = [a for a in BUDGET_ADVICE if a not in text]
        self.assertEqual(missing_advice, [],
                         f"RUNBOOK omits recommender advice values: {missing_advice}")
        self.assertIn("recommend_budget", text,
                      "RUNBOOK must name the advisory recommender (recommend_budget)")
        self.assertIn("policy.budgets", text,
                      "RUNBOOK must state policy.budgets as the explicit raise mechanism")

    def test_no_synced_verbatim_phrasing(self):
        docs = [ROOT_README] + [pkg["root"] / "README.md" for pkg in ALL_PACKAGES]
        offenders = [
            str(p.relative_to(REPO_ROOT))
            for p in docs
            if p.is_file() and "synced verbatim" in p.read_text(encoding="utf-8").lower()
        ]
        self.assertEqual(
            offenders, [], f"'synced verbatim' phrasing reappeared in: {offenders}"
        )

    def test_four_changelogs_share_latest_version_header(self):
        latest = {}
        for pkg in ALL_PACKAGES:
            changelog = pkg["root"] / "CHANGELOG.md"
            text = self._read(changelog)
            match = _VERSION_HEADER.search(text)
            self.assertIsNotNone(
                match, f"no '## [x.y.z]' version header in {changelog}"
            )
            latest[pkg["root"].name] = match.group(1)
        self.assertEqual(
            len(set(latest.values())),
            1,
            f"CHANGELOG latest version headers diverge across hosts: {latest}",
        )


if __name__ == "__main__":
    unittest.main()
