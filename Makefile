.PHONY: sync check test export-sanitized

sync:
	bash scripts/sync.sh

check:
	bash scripts/sync.sh --check
	bash platforms/claude-code/scripts/validate.sh
	bash platforms/cursor/scripts/validate.sh
	cd platforms/codex && bash scripts/validate.sh
	python3 -m unittest discover -s tests

test:
	python3 -m unittest discover -s tests -v

export-sanitized:
	git archive --format=zip --output QB-sanitized.zip HEAD
