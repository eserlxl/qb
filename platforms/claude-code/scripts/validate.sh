#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 1) Manifest parses.
python3 -m json.tool .claude-plugin/plugin.json >/dev/null

# 2) Required files exist (Claude Code single-plugin-at-root layout).
required_files=(
  ".claude-plugin/plugin.json"
  ".claude-plugin/marketplace.json"
  "scripts/validate_planner_docs.py"
  "skills/claudeqb-planner/SKILL.md"
  "skills/claudeqb-planner/planners/first-planner.md"
  "skills/claudeqb-autopsy/SKILL.md"
  "skills/claudeqb-autopsy/autopsy-planner.md"
  "skills/claudeqb-subplanner/SKILL.md"
  "skills/claudeqb-subplanner/second-planner.md"
  "skills/claudeqb-auditor/SKILL.md"
  "skills/claudeqb-auditor/third-planner.md"
  "skills/claudeqb-implementer/SKILL.md"
  "skills/claudeqb-implementer/fourth-planner.md"
  "commands/claudeqb-plan.md"
  "commands/claudeqb-autopsy.md"
  "commands/claudeqb-audit.md"
  "commands/claudeqb-implement.md"
  "agents/claudeqb-autopsy.md"
  "agents/claudeqb-subplanner.md"
  "agents/claudeqb-auditor.md"
  "agents/claudeqb-implementer.md"
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
if data.get("name") != "claudeqb":
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
    "cursorqb_residue": "cursorqb",
    "codexqb_residue": "codexqb",
    "codex_invocation": "$codexqb",
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

# 6) Unit tests (validator behavior + skill-content invariants).
python3 -m unittest discover -s tests

echo "claudeqb_repo_validation=passed"
