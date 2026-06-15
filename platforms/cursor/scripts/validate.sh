#!/usr/bin/env bash
# QB repository validator (dependency-free).
#
# Validates the hand-authored Cursor host package plus the synced shared assets:
#   1) the manifest .cursor-plugin/plugin.json parses and declares name == "qb";
#   2) every required component file exists (manifest, the 5 SKILL.md, the 4 commands,
#      and the synced planner-spec / reference / validator paths);
#   3) each skill's frontmatter name == its directory and each command's name == its stem;
#   4) no cross-host residue in the HAND-AUTHORED host files (skills SKILL.md + commands).
#      The synced neutral planner specs, references, and validator are NOT brand-scanned.
#
# Pure POSIX shell: no python, no jq, no external runtimes. Ends with
#   qb_repo_validation=passed
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() {
  echo "$1"
  exit 1
}

# ---------------------------------------------------------------------------
# 1) Manifest exists, parses (balanced + minimally well-formed), name=="qb".
# ---------------------------------------------------------------------------
MANIFEST=".cursor-plugin/plugin.json"
[ -f "$MANIFEST" ] || fail "missing_required_file=$MANIFEST"

# Lightweight brace/bracket balance check (catches truncated/corrupt JSON).
opens=$(tr -cd '{' < "$MANIFEST" | wc -c | tr -d ' ')
closes=$(tr -cd '}' < "$MANIFEST" | wc -c | tr -d ' ')
[ "$opens" = "$closes" ] || fail "manifest_brace_mismatch=$MANIFEST"
[ "$opens" -ge 1 ] || fail "manifest_not_json_object=$MANIFEST"

# Extract the top-level "name" value with sed (no JSON parser dependency).
manifest_name="$(sed -n 's/.*"name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$MANIFEST" | head -n 1)"
[ "$manifest_name" = "qb" ] || fail "unexpected_plugin_name=$manifest_name"

# ---------------------------------------------------------------------------
# 2) Required component files exist.
#    Includes the synced spec/reference/validator paths placed by scripts/sync.sh.
# ---------------------------------------------------------------------------
required_files="
.cursor-plugin/plugin.json
skills/qb-planner/SKILL.md
skills/qb-assess/SKILL.md
skills/qb-subplanner/SKILL.md
skills/qb-auditor/SKILL.md
skills/qb-implementer/SKILL.md
commands/qb-plan.md
commands/qb-assess.md
commands/qb-audit.md
commands/qb-implement.md
skills/qb-planner/planners/first-planner.md
skills/qb-planner/planners/export-planner.md
skills/qb-assess/assessment-planner.md
skills/qb-subplanner/second-planner.md
skills/qb-auditor/third-planner.md
skills/qb-implementer/fourth-planner.md
references/repo-aware-intake.md
references/workflow-quality.md
scripts/validate_planner_docs.py
scripts/validate_planwright_plan.py
README.md
CHANGELOG.md
LICENSE
docs/INSTALLATION.md
docs/USAGE.md
docs/MAINTAINING.md
"

for path in $required_files; do
  [ -f "$path" ] || fail "missing_required_file=$path"
done

# ---------------------------------------------------------------------------
# Helper: read the YAML frontmatter "name:" value from a markdown file.
# ---------------------------------------------------------------------------
frontmatter_name() {
  # First "name:" line, value trimmed of surrounding whitespace.
  sed -n 's/^name:[[:space:]]*\(.*\)$/\1/p' "$1" | head -n 1 | sed 's/[[:space:]]*$//'
}

# ---------------------------------------------------------------------------
# 3) Frontmatter name == directory (skills) / filename stem (commands).
# ---------------------------------------------------------------------------
for skill_md in skills/*/SKILL.md; do
  [ -f "$skill_md" ] || continue
  dir="$(basename "$(dirname "$skill_md")")"
  name="$(frontmatter_name "$skill_md")"
  [ "$name" = "$dir" ] || fail "skill_name_mismatch=$skill_md::name=$name::dir=$dir"
done

for command_md in commands/*.md; do
  [ -f "$command_md" ] || continue
  stem="$(basename "$command_md" .md)"
  name="$(frontmatter_name "$command_md")"
  [ "$name" = "$stem" ] || fail "command_name_mismatch=$command_md::name=$name::stem=$stem"
done

# ---------------------------------------------------------------------------
# 4) No cross-host residue in the HAND-AUTHORED host files only.
#    Scan the 5 SKILL.md and the 4 commands; do NOT scan the synced neutral
#    planner specs, references, or the validator (those say only "QB").
# ---------------------------------------------------------------------------
host_files="
skills/qb-planner/SKILL.md
skills/qb-assess/SKILL.md
skills/qb-subplanner/SKILL.md
skills/qb-auditor/SKILL.md
skills/qb-implementer/SKILL.md
commands/qb-plan.md
commands/qb-assess.md
commands/qb-audit.md
commands/qb-implement.md
"

# Forbidden cross-host needles for the Cursor platform.
#   $qb                 -> Codex slash invocation token
#   .claude-plugin           -> Claude Code manifest dir
#   .codex-plugin            -> Codex manifest dir
forbidden_needles="\$qb .claude-plugin .codex-plugin"

for path in $host_files; do
  [ -f "$path" ] || continue
  for needle in $forbidden_needles; do
    if grep -qF -- "$needle" "$path"; then
      fail "cross_host_residue=$path::needle=$needle"
    fi
  done
done

echo "qb_repo_validation=passed"
