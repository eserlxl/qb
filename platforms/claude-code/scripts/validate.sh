#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 1) Manifest parses.
python3 -m json.tool .claude-plugin/plugin.json >/dev/null

# 2) Required files exist (Claude Code single-plugin-at-root layout).
#    This package is plugin-only: it ships no marketplace manifest. It is
#    distributed via the dedicated `eserlxl/claude-marketplace` aggregator, which
#    references it with a `git-subdir` source pointing at this directory.
required_files=(
  ".claude-plugin/plugin.json"
  "scripts/validate_planner_docs.py"
  "scripts/validate_planwright_plan.py"
  "scripts/qb_headless.py"
  "skills/qb-planner/SKILL.md"
  "skills/qb-planner/planners/first-planner.md"
  "skills/qb-planner/planners/export-planner.md"
  "skills/qb-assess/SKILL.md"
  "skills/qb-assess/assessment-planner.md"
  "skills/qb-subplanner/SKILL.md"
  "skills/qb-subplanner/second-planner.md"
  "skills/qb-auditor/SKILL.md"
  "skills/qb-auditor/third-planner.md"
  "skills/qb-implementer/SKILL.md"
  "skills/qb-implementer/fourth-planner.md"
  "commands/qb-plan.md"
  "commands/qb-assess.md"
  "commands/qb-audit.md"
  "commands/qb-implement.md"
  "commands/qb-harden.md"
  "agents/qb-assess.md"
  "agents/qb-subplanner.md"
  "agents/qb-auditor.md"
  "agents/qb-implementer.md"
  "agents/qb-runner.md"
  "references/workflow-quality.md"
  "references/repo-aware-intake.md"
  "README.md"
  "CHANGELOG.md"
  "LICENSE"
  "docs/INSTALLATION.md"
  "docs/USAGE.md"
  "docs/MAINTAINING.md"
)

for path in "${required_files[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "missing_required_file=$path"
    exit 1
  fi
done

# 3) Manifest name is the expected kebab-case id.
python3 - <<'PY'
import json
import sys

data = json.loads(open(".claude-plugin/plugin.json", encoding="utf-8").read())
if data.get("name") != "qb":
    print(f"unexpected_plugin_name={data.get('name')!r}")
    sys.exit(1)
PY

# 4) Frontmatter name == directory/filename for every skill, command, and agent.
python3 - <<'PY'
import sys
from pathlib import Path


def frontmatter_name(text: str):
    for line in text.splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    return None


problems = []
for skill in Path("skills").rglob("SKILL.md"):
    name = frontmatter_name(skill.read_text(encoding="utf-8"))
    if name != skill.parent.name:
        problems.append(f"skill_name_mismatch={skill}::name={name}::dir={skill.parent.name}")
for command in Path("commands").glob("*.md"):
    name = frontmatter_name(command.read_text(encoding="utf-8"))
    if name != command.stem:
        problems.append(f"command_name_mismatch={command}::name={name}::stem={command.stem}")
for agent in Path("agents").glob("*.md"):
    name = frontmatter_name(agent.read_text(encoding="utf-8"))
    if name != agent.stem:
        problems.append(f"agent_name_mismatch={agent}::name={name}::stem={agent.stem}")

if problems:
    for problem in problems:
        print(problem)
    sys.exit(1)
PY

# 5) No source-tooling residue and no parent-directory traversal in component docs.
#    (This script is not a component file, so the needles below are data, not residue.)
python3 - <<'PY'
import sys
from pathlib import Path

forbidden_substrings = {
    "codex_invocation": "$qb",
    "cursor_plugin_dir": ".cursor-plugin",
    "codex_plugin_dir": ".codex-plugin",
    "define_goal_residue": "define-goal",
    "create_goal_residue": "create_goal",
    "get_goal_residue": "get_goal",
    "codex_followup_button": "Hedefi Takip Et",
    "parent_traversal": "../",
}

problems = []
for base in ("skills", "references", "commands", "agents"):
    base_path = Path(base)
    if not base_path.exists():
        continue
    for path in base_path.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for label, needle in forbidden_substrings.items():
            if needle in text:
                problems.append(f"{label}={path}")

if problems:
    for problem in problems:
        print(problem)
    sys.exit(1)
PY

# 6) Tracked-file secret hygiene over the package (length-bounded patterns so
#    normal filenames are not flagged). The bundled `tests/` tree is skipped:
#    its fixtures intentionally embed secret-shaped literals to exercise the
#    engine's own secret detector, so scanning them would always false-positive.
python3 - <<'PY'
from pathlib import Path
import re
import sys

ignored_parts = {
    ".git",
    "tests",
    "__MACOSX",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "artifacts",
    "build",
    "dist",
    "logs",
    "tmp",
}
blocked_suffixes = {".key", ".pem", ".pyc", ".zip", ".png", ".jpg", ".jpeg", ".gif"}

secret_patterns = [
    ("openrouter_api_key", re.compile(r"\bsk-or-v1-[A-Za-z0-9_-]{20,}\b")),
    ("openai_api_key", re.compile(r"\bsk-(?!or-v1-)[A-Za-z0-9_-]{20,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("github_legacy_pat", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
]

findings = []
for path in Path(".").rglob("*"):
    if not path.is_file():
        continue
    if ignored_parts.intersection(path.parts):
        continue
    if path.suffix in blocked_suffixes:
        continue
    if path.name == ".DS_Store" or path.name.startswith(".env"):
        continue
    if path.name.endswith(".local") or ".local." in path.name:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    for line_number, line in enumerate(text.splitlines(), start=1):
        for name, pattern in secret_patterns:
            if pattern.search(line):
                findings.append(f"{path}:{line_number}: {name}")

if findings:
    print("tracked_secret_hygiene_failed")
    for finding in findings:
        print(finding)
    sys.exit(1)
PY

# 7) Unit tests (validator behavior + skill-content invariants).
python3 -m unittest discover -s tests

echo "qb_repo_validation=passed"
