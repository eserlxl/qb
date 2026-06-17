.PHONY: sync check test baseline self-audit install-hooks export-sanitized

sync:
	bash scripts/sync.sh

# baseline -- the full regression net in one invocation: materialize the shared
# core into the host packages, then run byte-equality + per-host validation +
# the full test discovery. Reuses the sync and check recipes (no new behavior).
# Recorded in BASELINE.md as the low-friction entry point for the gate of record.
baseline:
	$(MAKE) sync
	$(MAKE) check

check:
	bash scripts/sync.sh --check
	bash platforms/claude-code/scripts/validate.sh
	bash platforms/cursor/scripts/validate.sh
	bash platforms/antigravity/scripts/validate.sh
	cd platforms/codex && bash scripts/validate.sh
	python3 -m unittest discover -s tests

test:
	python3 -m unittest discover -s tests -v

# self-audit -- "QB audits QB": run the headless engine over this repository at the
# conservative A0 (report-only) default, writing the findings inventory + reports to
# the gitignored QB-Audit/ store. Exit 0 = clean and 1 = findings are both DOCUMENTED
# outcomes of a successful run (the produced QB-Audit/findings.jsonl is reconciled
# against the accepted-findings register, not gated here); only a boundary (2) or
# internal-error (3) code fails the target. See the RUNBOOK exit-code contract.
# install-hooks -- opt-in: install the local pre-push hook that runs `make check`
# (the gate of record) before every push. Explicit only; performs no push.
install-hooks:
	bash scripts/install-hooks.sh

self-audit:
	@python3 shared/scripts/qb_headless.py --root . --out QB-Audit; \
	code=$$?; \
	if [ $$code -gt 1 ]; then \
		echo "self-audit: run failed (exit $$code: boundary/internal error)" >&2; \
		exit $$code; \
	fi; \
	echo "self-audit: completed (exit $$code; 0=clean, 1=findings) -> QB-Audit/findings.jsonl"

export-sanitized:
	git archive --format=zip --output QB-sanitized.zip HEAD
