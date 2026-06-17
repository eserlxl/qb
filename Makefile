.PHONY: sync check test baseline export-sanitized

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

export-sanitized:
	git archive --format=zip --output QB-sanitized.zip HEAD
