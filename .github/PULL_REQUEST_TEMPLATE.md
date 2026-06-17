## Summary

<!-- What does this change do, and why? -->

## Checklist

- [ ] `make check` passes on a clean working tree (the gate of record).
- [ ] For `shared/` edits: ran `make sync` so the platform copies are byte-equal.
- [ ] Version / changelog updated via `scripts/bump-version.sh` (if release-worthy).
- [ ] No secret value is committed (`tests/test_no_committed_secrets.py` passes).

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full contribution workflow.
