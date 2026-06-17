# Contributing to QB

## Versioning and changelog

QB follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(`MAJOR.MINOR.PATCH`), anchored by the root [`VERSION`](VERSION) file — the single
source of version truth.

**`scripts/bump-version.sh` is the only sanctioned way to bump the version.** Do not
hand-edit `VERSION`, the platform plugin manifests, or SKILL.md frontmatter versions:
the bumper updates all of them — plus the README version badge — in lockstep, and
`make check` (via `tests/test_version_and_structure.py` and
`tests/test_doc_consistency.py`) fails if they drift.

```bash
scripts/bump-version.sh <patch|minor|major> -m "Describe the change"
scripts/bump-version.sh --sync     # re-materialize the lockstep targets without a bump
```

### Changelog entries

Each platform CHANGELOG follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/):
a `## [x.y.z] - YYYY-MM-DD` version header, then one or more recognized subsections.

```
## [x.y.z] - 2026-01-01

### Changed
- A concrete, non-placeholder description of what changed and why.
```

Recognized subsections are `### Added`, `### Changed`, `### Deprecated`,
`### Removed`, `### Fixed`, and `### Security`. The latest version section must carry
at least one such subsection with a **real bullet** — an empty or placeholder note
(e.g. a bare "Version bump.") fails `tests/test_changelog_governance.py`. The four
platform changelogs share the same latest version header
(`tests/test_doc_consistency.py`), so bump all of them together through
`scripts/bump-version.sh`.
