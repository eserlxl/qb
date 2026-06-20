# Releasing QB

The end-to-end release sequence. Every automated step uses a real, committed command;
**tagging and publishing are operator-only** manual steps performed deliberately —
this runbook embeds no unattended push or publish command.

See also the [RUNBOOK](RUNBOOK.md) gate-of-record and release-integrity sections, and
[CONTRIBUTING.md](CONTRIBUTING.md) for the versioning/changelog convention.

## Sequence

1. **Start from a clean working tree** — `git status --porcelain` is empty.

2. **Run the gate of record**, and proceed only on exit `0`:

   ```bash
   make check
   ```

   For an **M7-eligible release**, `make check` (the gate of record) is necessary but
   not sufficient: confirm the consolidated M7 release-gating conjunction — the six
   `production_gate.PRODUCTION_GATE_CHECKS` conjuncts **and** every Phase 0–5 row of the
   M7 readiness checklist (`BASELINE.md`) — holds fail-closed, per
   [RUNBOOK.md](RUNBOOK.md) ("M7-eligible release"). The joint operational + autonomy
   verdict is computed programmatically by the M7 readiness aggregator
   (`shared/scripts/m7_readiness.py`): run `python3 shared/scripts/m7_readiness.py
   --root .` (exit 0 = ready) to resolve the joint-signal conjunct. Any single false
   conjunct denies M7 eligibility and is named; passing authorizes operation only, so
   the tagging and publishing steps below stay manual, operator-only actions.

3. **Bump the version and write the changelog entry** through the sanctioned bump
   path (never hand-edit version fields):

   ```bash
   scripts/bump-version.sh <patch|minor|major> -m "A real, non-placeholder note"
   ```

   This updates `VERSION`, the three plugin manifests, every SKILL.md frontmatter, the
   README version badge, the gate-of-record version in `BASELINE.md`, and prepends a
   changelog entry to all four platform changelogs — in lockstep. (`BASELINE.md`'s
   test-suite counts are exact and are not auto-bumped; refresh them after a
   `make baseline` run whenever test discovery count changes.)

4. **Review the diff** of the version + changelog changes:

   ```bash
   git diff
   ```

5. **Re-run the gate of record** on the bumped tree:

   ```bash
   make check
   ```

6. **Commit the bump**, then build the sanitized export and verify its integrity:

   ```bash
   make export-sanitized
   python3 scripts/release-manifest.py --check --output QB-sanitized.manifest
   ```

   The `--check` must exit `0` (the built tree matches its manifest).
   This is deterministic integrity verification only: the manifest is not
   cryptographic signing, includes no GPG/sigstore signature, and does not prove
   artifact origin or authenticity.

   Optional authenticity is a separate, explicit release decision. If maintainers
   approve it for a candidate, add a detached GPG signature or sigstore attestation
   for `QB-sanitized.zip` and/or `QB-sanitized.manifest`, document the verifier
   command in the release notes, and keep the SHA-256 manifest path dependency-free.

7. **Tag the release — operator-only, manual.** The operator creates the annotated
   tag deliberately (for example `git tag -a v<version> -m "<version>"`, a *local*
   tag). Tagging is a manual operator action, not automated here.

8. **Publish — operator-only, manual.** Pushing the tag/commit and publishing the
   release artifact are deliberate operator actions taken outside this runbook. **No
   unattended push or publish command is embedded here;** QB never pushes or publishes
   on its own.

## What is intentionally manual

Tagging and publishing stay operator-only so a release is always a deliberate human
action. The automated steps above (`make check`, `scripts/bump-version.sh`,
`make export-sanitized`, the integrity `--check`) are repeatable and never touch a
remote; only the operator moves a release outward.
