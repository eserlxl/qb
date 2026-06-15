#!/usr/bin/env bash
set -euo pipefail

# Dependency-free repository validation for the Codex platform build of QB.
# Uses only bash and the Python standard library. No PyYAML, no network, no
# local Codex validator dependencies.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 1) Manifests parse as JSON.
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
python3 -m json.tool plugins/qb/.codex-plugin/plugin.json >/dev/null

# 2) Required component files exist (Codex nested plugin layout, including the
#    synced shared spec/reference/validator paths).
required_files=(
  ".agents/plugins/marketplace.json"
  "plugins/qb/.codex-plugin/plugin.json"
  "plugins/qb/skills/qb/SKILL.md"
  "plugins/qb/skills/qb/agents/openai.yaml"
  "plugins/qb/skills/qb/scripts/validate_planner_docs.py"
  "plugins/qb/skills/qb/scripts/validate_planwright_plan.py"
  "plugins/qb/skills/qb/references/First-Planner.md"
  "plugins/qb/skills/qb/references/Assessment-Planner.md"
  "plugins/qb/skills/qb/references/Second-Planner.md"
  "plugins/qb/skills/qb/references/Third-Planner.md"
  "plugins/qb/skills/qb/references/Fourth-Planner.md"
  "plugins/qb/skills/qb/references/Export-Planner.md"
  "plugins/qb/skills/qb/references/repo-aware-intake.md"
  "plugins/qb/skills/qb/references/workflow-quality.md"
  "README.md"
  "CHANGELOG.md"
  "docs/INSTALLATION.md"
  "docs/USAGE.md"
  "docs/MAINTAINING.md"
  "LICENSE"
  "Makefile"
  "scripts/validate.sh"
)

for path in "${required_files[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "missing_required_file=$path"
    exit 1
  fi
done

# 3) Plugin manifest name == platform id.
python3 - <<'PY'
import json
import sys

data = json.loads(open("plugins/qb/.codex-plugin/plugin.json", encoding="utf-8").read())
name = data.get("name")
if name != "qb":
    print(f"unexpected_plugin_name={name!r}")
    sys.exit(1)

market = json.loads(open(".agents/plugins/marketplace.json", encoding="utf-8").read())
if market.get("name") != "eserlxl":
    print(f"unexpected_marketplace_name={market.get('name')!r}")
    sys.exit(1)
PY

# 4) Skill frontmatter name == its directory name.
python3 - <<'PY'
import sys
from pathlib import Path


def frontmatter_name(text: str):
    for line in text.splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    return None


problems = []
for skill in Path("plugins/qb/skills").rglob("SKILL.md"):
    name = frontmatter_name(skill.read_text(encoding="utf-8"))
    if name != skill.parent.name:
        problems.append(f"skill_name_mismatch={skill}::name={name}::dir={skill.parent.name}")

if problems:
    for problem in problems:
        print(problem)
    sys.exit(1)
PY

# 5) agents/openai.yaml semantic fields (quote-tolerant, no PyYAML).
python3 - <<'PY'
from pathlib import Path
import sys

text = Path("plugins/qb/skills/qb/agents/openai.yaml").read_text(encoding="utf-8")


def scalar(key: str):
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(f"{key}:"):
            continue
        value = stripped.split(":", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value
    return None


display_name = scalar("display_name")
short_description = scalar("short_description")
default_prompt = scalar("default_prompt")

errors = []
if display_name != "QB":
    errors.append(f"display_name={display_name!r}")
if short_description is None:
    errors.append("missing short_description")
elif len(short_description) > 80:
    errors.append(f"short_description_too_long={len(short_description)}")
if default_prompt is None:
    errors.append("missing default_prompt")
else:
    if "$qb" not in default_prompt:
        errors.append("default_prompt_missing_codex_invocation")
    if len(default_prompt) > 220:
        errors.append(f"default_prompt_too_long={len(default_prompt)}")

if errors:
    print("openai_yaml_semantic_check_failed")
    for error in errors:
        print(error)
    sys.exit(1)
PY

# 6) No stale invocation text in hand-authored host files.
python3 - <<'PY'
from pathlib import Path
import sys

needles = ("project-" + "planner", "Project " + "Planner", "$" + "project-" + "planner")
host_files = [
    Path("plugins/qb/skills/qb/SKILL.md"),
    Path("plugins/qb/skills/qb/agents/openai.yaml"),
    Path("plugins/qb/.codex-plugin/plugin.json"),
    Path(".agents/plugins/marketplace.json"),
    Path("README.md"),
    Path("docs/INSTALLATION.md"),
    Path("docs/USAGE.md"),
    Path("docs/MAINTAINING.md"),
]
findings = []
for path in host_files:
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle in text:
            findings.append(f"{path}: contains stale invocation text")
            break

if findings:
    print("stale_invocation_references_found")
    for finding in findings:
        print(finding)
    sys.exit(1)
PY

# 7) No cross-host residue in hand-authored host files.
#    The synced, host-neutral planner specs, reference docs, and shared
#    validate_planner_docs.py are exempt: they only say "QB". README/docs MAY
#    mention all platforms for attribution, so they are not scanned here.
#    This script (scripts/validate.sh) is not in the host-file list, so the
#    forbidden tokens below are data, not residue.
python3 - <<'PY'
from pathlib import Path
import sys

forbidden = {
    "claude_plugin_dir": ".claude-plugin",
    "cursor_plugin_dir": ".cursor-plugin",
}
host_files = [
    Path("plugins/qb/skills/qb/SKILL.md"),
    Path("plugins/qb/skills/qb/agents/openai.yaml"),
    Path("plugins/qb/.codex-plugin/plugin.json"),
    Path(".agents/plugins/marketplace.json"),
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

# 8) Tracked-file secret hygiene over the whole package (length-bounded
#    patterns so normal filenames are not flagged).
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

echo "qb_repo_validation=passed"
