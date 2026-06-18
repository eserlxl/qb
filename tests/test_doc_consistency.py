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
import accepted_findings  # noqa: E402
import budget  # noqa: E402
import finding_schema  # noqa: E402
import production_gate  # noqa: E402
import telemetry_aggregate  # noqa: E402
import telemetry_trends  # noqa: E402

ROOT_README = REPO_ROOT / "README.md"
ANALYZER_COVERAGE_DOC = REPO_ROOT / "docs/analyzer-coverage.md"
ROOT_VERSION = REPO_ROOT / "VERSION"
RUNBOOK = REPO_ROOT / "RUNBOOK.md"
SECURITY = REPO_ROOT / "SECURITY.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"

# Derived sources of truth (computed once, not copied into the test).
PRODUCER_ANALYZERS = sorted(
    type(a).__name__ for a in audit_runner.build_default_registry().analyzers()
)
FINDING_CATEGORIES = sorted(finding_schema.CATEGORIES)
# RUNBOOK budget raise-path terms, derived from the budget engine (not hardcoded).
BUDGET_CEILINGS = sorted(f.name for f in dataclasses.fields(budget.Budget))
BUDGET_ADVICE = sorted((budget.ADVICE_CONSTRAINING, budget.ADVICE_PROTECTING,
                        budget.ADVICE_INSUFFICIENT))
# RUNBOOK observability terms, derived from the trend/aggregate engine.
TREND_DIMENSIONS = sorted(telemetry_trends.DIMENSION_PATHS)
TREND_VERDICTS = sorted({
    telemetry_trends.VERDICT_IMPROVING, telemetry_trends.VERDICT_STABLE,
    telemetry_trends.VERDICT_REGRESSING, telemetry_trends.VERDICT_INSUFFICIENT,
    telemetry_trends.VERDICT_UNMEASURED,
})
AGGREGATE_FILENAME = telemetry_aggregate.AGGREGATE_TELEMETRY_FILENAME
# RUNBOOK production-gate conjuncts, derived from the gate engine (not hardcoded).
PRODUCTION_GATE_CHECKS = sorted(production_gate.PRODUCTION_GATE_CHECKS)
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
_ANALYZER_DOC_REGISTRY = re.compile(
    r"It currently registers:\n\n(?P<body>(?:- `[^`]+`\n)+)",
    re.MULTILINE,
)
_ANALYZER_DOC_CATEGORIES = re.compile(
    r"frozen categories from\n`shared/scripts/finding_schema\.py`: (?P<body>.*?)\.",
    re.DOTALL,
)
# The "## Production gate" section (to the next "## " heading or end of file), and
# each per-conjunct step's bold backtick-wrapped conjunct name within it.
_PRODUCTION_GATE_SECTION = re.compile(
    r"^## Production gate\s*$(?P<body>.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
_GATE_CONJUNCT = re.compile(r"^\d+\.\s+\*\*`([a-z_]+)`\*\*", re.MULTILINE)


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

    def test_analyzer_coverage_doc_registry_matches_engine(self):
        text = self._read(ANALYZER_COVERAGE_DOC)
        match = _ANALYZER_DOC_REGISTRY.search(text)
        self.assertIsNotNone(match, "analyzer coverage doc has no registry list")
        declared = _backtick_values(match.group("body"))
        self.assertEqual(declared, PRODUCER_ANALYZERS)

    def test_analyzer_coverage_doc_categories_match_schema(self):
        text = self._read(ANALYZER_COVERAGE_DOC)
        match = _ANALYZER_DOC_CATEGORIES.search(text)
        self.assertIsNotNone(match, "analyzer coverage doc has no category list")
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

    def test_platform_readme_version_badges_match_version_file(self):
        # The per-host plugin READMEs carry the same shields.io badge as the root
        # README; scripts/bump-version.sh now keeps them in lockstep, so guard them
        # too. A platform README without a badge (e.g. antigravity) is skipped.
        declared = self._read(ROOT_VERSION).strip()
        readmes = sorted((REPO_ROOT / "platforms").glob("*/README.md"))
        self.assertTrue(readmes, "no platform READMEs found")
        checked = []
        for readme in readmes:
            match = _README_BADGE.search(self._read(readme))
            if match is None:
                continue  # this package README has no version badge to check
            badge = match.group(1).replace("--", "-").replace("__", "_")
            rel = readme.relative_to(REPO_ROOT)
            self.assertEqual(
                badge,
                declared,
                f"{rel} version badge ({badge}) != VERSION ({declared}); "
                f"run scripts/bump-version.sh --sync",
            )
            checked.append(str(rel))
        self.assertTrue(
            checked, "no platform README version badges found to check (guard vacuous)"
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

    def test_runbook_observability_terms_match_engine(self):
        # The RUNBOOK observability section must name every trend dimension and
        # verdict derived from telemetry_trends, the aggregate artifact filename,
        # and the unmeasured sentinel, so the operator narrative cannot drift from
        # the trend/aggregate engine.
        text = self._read(RUNBOOK)
        missing_dims = [d for d in TREND_DIMENSIONS if d not in text]
        self.assertEqual(missing_dims, [], f"RUNBOOK omits trend dimensions: {missing_dims}")
        missing_verdicts = [v for v in TREND_VERDICTS if v not in text]
        self.assertEqual(missing_verdicts, [], f"RUNBOOK omits trend verdicts: {missing_verdicts}")
        self.assertIn(AGGREGATE_FILENAME, text,
                      "RUNBOOK must name the aggregate telemetry artifact filename")
        self.assertIn(telemetry_trends.UNMEASURED, text,
                      "RUNBOOK must document the unmeasured-value distinction")

    def test_runbook_production_gate_names_exactly_the_engine_conjuncts(self):
        # The runbook production-gate procedure must list EXACTLY the conjuncts
        # production_gate.PRODUCTION_GATE_CHECKS defines -- failing on any extra or
        # missing conjunct, so the operator procedure cannot drift from the engine.
        text = self._read(RUNBOOK)
        section = _PRODUCTION_GATE_SECTION.search(text)
        self.assertIsNotNone(section, "RUNBOOK has no '## Production gate' section")
        listed = sorted(set(_GATE_CONJUNCT.findall(section.group("body"))))
        self.assertEqual(
            listed, PRODUCTION_GATE_CHECKS,
            f"RUNBOOK production-gate conjuncts {listed} != engine {PRODUCTION_GATE_CHECKS}")

    def test_governance_docs_consistent_with_readme_posture(self):
        # The Phase-8.3 policy docs must restate the README's load-bearing posture:
        # SECURITY.md the trusted-code precondition, CONTRIBUTING.md the no-secrets
        # rule -- so the new governance docs cannot drift from the README.
        readme = self._read(ROOT_README)
        security = self._read(SECURITY)
        contributing = self._read(CONTRIBUTING)

        # Trusted-code precondition: the README references it; SECURITY.md states it.
        self.assertIn("trusted-code precondition", readme.lower(),
                      "README must reference the trusted-code precondition")
        self.assertIn("trusted code", security.lower(),
                      "SECURITY.md must state the trusted-code precondition")
        self.assertIn("not yet shipped", security.lower(),
                      "SECURITY.md must mirror the sandbox-not-yet-shipped posture")

        # No-secrets rule: the README carries the secret-hygiene posture; CONTRIBUTING
        # carries the rule and names the enforcing guard.
        self.assertIn("secret hygiene", readme.lower(),
                      "README must carry the secret-hygiene posture")
        self.assertIn("## No secrets", contributing,
                      "CONTRIBUTING.md must carry the No secrets section")
        self.assertIn("test_no_committed_secrets", contributing,
                      "CONTRIBUTING.md no-secrets rule must name the enforcing guard")

    def test_accepted_findings_register_requires_explicit_records(self):
        sample = (
            "# Accepted findings register\n\n"
            "## Accepted\n"
            "- `QBF-VALID-1` -- reviewed false positive (reviewer: maintainer)\n"
            "- `QBF-VALID-2` \u2014 reviewed false positive (reviewer: maintainer)\n"
            "- `QBF-NO-REVIEWER` -- rationale only\n"
            "- `QBF-NO-RATIONALE` (reviewer: maintainer)\n"
            "- `   ` -- blank id (reviewer: maintainer)\n"
            "Prose mentioning `QBF-PROSE` should not count.\n\n"
            "## Other\n"
            "- `QBF-OTHER` -- different section (reviewer: maintainer)\n"
        )
        self.assertEqual(
            accepted_findings.parse_accepted_ids(sample),
            {"QBF-VALID-1", "QBF-VALID-2"},
        )

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
