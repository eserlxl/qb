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

## Contribution workflow

1. Branch from `main` and make your change.
2. **For any change under `shared/`:** run `make sync` to materialize the canonical
   source into the host packages, then `make check`. `shared/` is the single source
   of truth; skipping `make sync` leaves the platform copies stale and fails
   `bash scripts/sync.sh --check` (and therefore `make check`). For changes outside
   `shared/`, `make check` alone is sufficient.
3. Satisfy the **gate of record** before opening a PR or pushing: a green local
   `make check` on a clean working tree is the one authoritative quality gate (cloud
   CI is disabled). See [RUNBOOK.md → Gate of record](RUNBOOK.md#gate-of-record); you
   may install the optional pre-push hook with `scripts/install-hooks.sh`.
4. Add a changelog entry and bump the version through `scripts/bump-version.sh` (see
   **Versioning and changelog** above) — never hand-edit version fields.
5. When QB-generated findings or planning docs become executable work, keep the
   hand-off one-directional: QB writes under `.qb/`; copy `.qb/plan.md` to
   `.planwright/plan.md` only when handing work to planwright, then run
   `planwright execute`.

## Test-suite count baseline

`BASELINE.md` freezes the gate-of-record test inventory; its recorded module and
test-case counts are the single source of truth. **Adding or removing a test module or test case must update the
`BASELINE.md` recorded counts in the same change.** `make check` runs
`tests/test_baseline_consistency.py`, which re-derives the live module and case
counts from the tree and fails if they drift from the recorded reference, so a
test add/remove that skips the baseline update turns the next `make check` red.

Diagnose a count failure by the **Guard-to-test mapping** in `BASELINE.md`:
re-run the single named per-module guard to localize the regression. A green
`make check` must report the recorded counts unchanged.

## No secrets

Never commit a real credential. Every tracked file is scanned by
`tests/test_no_committed_secrets.py` (run under `make check`); a committed
secret-shaped string fails the gate. A deliberate test fixture may opt out with an
inline `pragma: allowlist secret` marker, but production code, docs, and config must
carry no real secret value.
