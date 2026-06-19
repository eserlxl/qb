#!/usr/bin/env bash
set -euo pipefail

# Dependency-free repository validation for the Antigravity platform build of QB.
# Uses only bash and the Python standard library. No PyYAML, no network, no git.
# All checks are scoped to this package directory so it validates identically as a
# monorepo subdirectory and as a standalone extracted copy.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 1) Required component files exist (Antigravity bare-skill-folder layout, including
#    the planner specs, behavior references, and bundled read-only validator).
required_files=(
  "skills/qb/SKILL.md"
  "skills/qb/scripts/validate_planner_docs.py"
  "skills/qb/references/first-planner.md"
  "skills/qb/references/assessment-planner.md"
  "skills/qb/references/second-planner.md"
  "skills/qb/references/third-planner.md"
  "skills/qb/references/fourth-planner.md"
  "skills/qb/references/repo-aware-intake.md"
  "skills/qb/references/workflow-quality.md"
  "skills/qb/references/vibecoding-principles.md"
  "skills/qb/references/task-delegation-playbook.md"
  "skills/qb/references/planning-ledger.md"
  "skills/qb/references/project-ontology.md"
  "skills/qb/references/assessment-and-budget.md"
  "skills/qb/references/engineering-principles.md"
  "README.md"
  "CHANGELOG.md"
  "docs/INSTALLATION.md"
  "docs/USAGE.md"
  "docs/MAINTAINING.md"
  "Makefile"
  "scripts/install.sh"
  "LICENSE"
)

for path in "${required_files[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "missing_required_file=$path"
    exit 1
  fi
done

# 2) SKILL.md frontmatter: name == "qb" (== skill directory name) and the required
#    description is present.
python3 - <<'PY'
from pathlib import Path
import re
import sys

text = Path("skills/qb/SKILL.md").read_text(encoding="utf-8")
match = re.match(r"---\n(.*?)\n---\n", text, flags=re.DOTALL)
if not match:
    print("skill_frontmatter_missing=true")
    sys.exit(1)
frontmatter = match.group(1)
required = {
    "name: qb",
    "description: Vibecoding-first Antigravity planning with assessment, ontology, ledger memory, helper-agent-aware QA, and gated handoff.",
}
missing = sorted(item for item in required if item not in frontmatter)
if missing:
    print("skill_frontmatter_missing_keys=" + ",".join(missing))
    sys.exit(1)
PY

# 3) Skill frontmatter name == its directory name.
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

if problems:
    for problem in problems:
        print(problem)
    sys.exit(1)
PY

# 4) No cross-host residue in hand-authored host files. The synced, host-neutral
#    planner specs and reference docs only say "QB"; README/docs MAY mention other
#    platforms for attribution, so they are not scanned here.
python3 - <<'PY'
from pathlib import Path
import sys

forbidden = {
    "claude_plugin_dir": ".claude-plugin",
    "cursor_plugin_dir": ".cursor-plugin",
    "codex_plugin_dir": ".codex-plugin",
    "codex_identity": "codex" + "qb",
    "cursor_identity": "cursor" + "qb",
    "codex_agent_manifest": "openai.yaml",
}
host_files = [
    Path("skills/qb/SKILL.md"),
    Path("scripts/install.sh"),
]
problems = []
for path in host_files:
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8")
    for label, needle in forbidden.items():
        if needle in text:
            problems.append(f"{label}={path}")

if problems:
    print("cross_host_residue_found")
    for problem in problems:
        print(problem)
    sys.exit(1)
PY

# 5) Package secret hygiene over the whole package (length-bounded patterns so
#    normal filenames are not flagged). Filesystem-scoped; no git.
python3 - <<'PY'
from pathlib import Path
import re
import sys

ignored_parts = {
    ".git",
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

# 6) install.sh dry-run smoke tests: project scopes preview cleanly, and a
#    project scope without --target fails closed.
tmp_project="$(mktemp -d)"
trap 'rm -rf "$tmp_project"' EXIT
bash scripts/install.sh --scope ide-project --target "$tmp_project" --dry-run >/dev/null
bash scripts/install.sh --scope cli-project --target "$tmp_project" --dry-run >/dev/null
bash scripts/install.sh --scope ide-project --dry-run >/dev/null 2>&1 && {
  echo "expected_missing_target_failure=false"
  exit 1
}

echo "qb_repo_validation=passed"
