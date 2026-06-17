#!/usr/bin/env bash
#
# sync.sh -- materialize the canonical shared/ source of truth into every platform.
#
# The files under shared/ are the single source of truth for QB's host-neutral IP:
# the five planner prompt specs, the two reference docs, and the read-only
# validator. They are deliberately host-neutral (they speak only of "QB"), so the
# platform copies are PLAIN byte-for-byte copies -- there is NO re-branding here.
#
# Modes:
#   (default)   Copy each shared file to all of its mapped platform destinations,
#               creating parent directories as needed. Prints a concise summary.
#   --check     Compare each destination to its shared source. Exits 1 and lists
#               every path that is missing or differs (used by CI). Writes nothing.
#
# Dependency-free: bash + coreutils (cmp / cp / mkdir / dirname).

set -euo pipefail

# --- Resolve repo root from this script's location (scripts/sync.sh) -----------
SCRIPT_SOURCE="${BASH_SOURCE[0]}"
# Resolve symlink chain so the repo root is correct even if invoked via a symlink.
while [ -h "$SCRIPT_SOURCE" ]; do
  dir="$(cd -P "$(dirname "$SCRIPT_SOURCE")" && pwd)"
  SCRIPT_SOURCE="$(readlink "$SCRIPT_SOURCE")"
  [[ "$SCRIPT_SOURCE" != /* ]] && SCRIPT_SOURCE="$dir/$SCRIPT_SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_SOURCE")" && pwd)"
REPO_ROOT="$(cd -P "$SCRIPT_DIR/.." && pwd)"

SHARED_DIR="$REPO_ROOT/shared"

# --- Parse mode ----------------------------------------------------------------
MODE="sync"
case "${1:-}" in
  "")        MODE="sync" ;;
  --check)   MODE="check" ;;
  -h|--help)
    cat <<'EOF'
Usage: scripts/sync.sh [--check]

  (no args)   Copy shared/ files into every platform destination (default).
  --check     Verify every platform copy byte-matches its shared source.
              Exits 1 and lists drifting/missing paths. Writes nothing.
EOF
    exit 0
    ;;
  *)
    echo "sync.sh: unknown argument: $1" >&2
    echo "Usage: scripts/sync.sh [--check]" >&2
    exit 2
    ;;
esac

# --- The SYNC CONTRACT mapping -------------------------------------------------
# One entry per (source, destination) pair. Source paths are relative to
# SHARED_DIR; destination paths are relative to REPO_ROOT. The grouping by source
# mirrors the SPEC: each shared file fans out to claude-code, cursor, and codex.
# (The antigravity platform is intentionally NOT a sync destination: its planner
# specs + bundled validator are host-authored, vibecoding-first, and divergent
# from shared/. It carries its own copies and is gated by its own validate.sh.)
MAP=(
  # shared/planners/first-planner.md
  "planners/first-planner.md|platforms/claude-code/skills/qb-planner/planners/first-planner.md"
  "planners/first-planner.md|platforms/cursor/skills/qb-planner/planners/first-planner.md"
  "planners/first-planner.md|platforms/codex/plugins/qb/skills/qb/references/first-planner.md"

  # shared/planners/second-planner.md
  "planners/second-planner.md|platforms/claude-code/skills/qb-subplanner/second-planner.md"
  "planners/second-planner.md|platforms/cursor/skills/qb-subplanner/second-planner.md"
  "planners/second-planner.md|platforms/codex/plugins/qb/skills/qb/references/second-planner.md"

  # shared/planners/third-planner.md
  "planners/third-planner.md|platforms/claude-code/skills/qb-auditor/third-planner.md"
  "planners/third-planner.md|platforms/cursor/skills/qb-auditor/third-planner.md"
  "planners/third-planner.md|platforms/codex/plugins/qb/skills/qb/references/third-planner.md"

  # shared/planners/fourth-planner.md
  "planners/fourth-planner.md|platforms/claude-code/skills/qb-implementer/fourth-planner.md"
  "planners/fourth-planner.md|platforms/cursor/skills/qb-implementer/fourth-planner.md"
  "planners/fourth-planner.md|platforms/codex/plugins/qb/skills/qb/references/fourth-planner.md"

  # shared/planners/assessment-planner.md
  "planners/assessment-planner.md|platforms/claude-code/skills/qb-assess/assessment-planner.md"
  "planners/assessment-planner.md|platforms/cursor/skills/qb-assess/assessment-planner.md"
  "planners/assessment-planner.md|platforms/codex/plugins/qb/skills/qb/references/assessment-planner.md"

  # shared/planners/export-planner.md
  "planners/export-planner.md|platforms/claude-code/skills/qb-planner/planners/export-planner.md"
  "planners/export-planner.md|platforms/cursor/skills/qb-planner/planners/export-planner.md"
  "planners/export-planner.md|platforms/codex/plugins/qb/skills/qb/references/export-planner.md"

  # shared/references/repo-aware-intake.md
  "references/repo-aware-intake.md|platforms/claude-code/references/repo-aware-intake.md"
  "references/repo-aware-intake.md|platforms/cursor/references/repo-aware-intake.md"
  "references/repo-aware-intake.md|platforms/codex/plugins/qb/skills/qb/references/repo-aware-intake.md"

  # shared/references/workflow-quality.md
  "references/workflow-quality.md|platforms/claude-code/references/workflow-quality.md"
  "references/workflow-quality.md|platforms/cursor/references/workflow-quality.md"
  "references/workflow-quality.md|platforms/codex/plugins/qb/skills/qb/references/workflow-quality.md"

  # shared/scripts/validate_planner_docs.py
  "scripts/validate_planner_docs.py|platforms/claude-code/scripts/validate_planner_docs.py"
  "scripts/validate_planner_docs.py|platforms/cursor/scripts/validate_planner_docs.py"
  "scripts/validate_planner_docs.py|platforms/codex/plugins/qb/skills/qb/scripts/validate_planner_docs.py"

  # shared/scripts/validate_planwright_plan.py
  "scripts/validate_planwright_plan.py|platforms/claude-code/scripts/validate_planwright_plan.py"
  "scripts/validate_planwright_plan.py|platforms/cursor/scripts/validate_planwright_plan.py"
  "scripts/validate_planwright_plan.py|platforms/codex/plugins/qb/skills/qb/scripts/validate_planwright_plan.py"

  # shared/scripts/finding_schema.py
  "scripts/finding_schema.py|platforms/claude-code/scripts/finding_schema.py"
  "scripts/finding_schema.py|platforms/cursor/scripts/finding_schema.py"
  "scripts/finding_schema.py|platforms/codex/plugins/qb/skills/qb/scripts/finding_schema.py"

  # shared/scripts/analyzer_interface.py
  "scripts/analyzer_interface.py|platforms/claude-code/scripts/analyzer_interface.py"
  "scripts/analyzer_interface.py|platforms/cursor/scripts/analyzer_interface.py"
  "scripts/analyzer_interface.py|platforms/codex/plugins/qb/skills/qb/scripts/analyzer_interface.py"

  # shared/scripts/analyzer_core.py
  "scripts/analyzer_core.py|platforms/claude-code/scripts/analyzer_core.py"
  "scripts/analyzer_core.py|platforms/cursor/scripts/analyzer_core.py"
  "scripts/analyzer_core.py|platforms/codex/plugins/qb/skills/qb/scripts/analyzer_core.py"

  # shared/scripts/audit_runner.py
  "scripts/audit_runner.py|platforms/claude-code/scripts/audit_runner.py"
  "scripts/audit_runner.py|platforms/cursor/scripts/audit_runner.py"
  "scripts/audit_runner.py|platforms/codex/plugins/qb/skills/qb/scripts/audit_runner.py"

  # shared/scripts/precision_harness.py
  "scripts/precision_harness.py|platforms/claude-code/scripts/precision_harness.py"
  "scripts/precision_harness.py|platforms/cursor/scripts/precision_harness.py"
  "scripts/precision_harness.py|platforms/codex/plugins/qb/skills/qb/scripts/precision_harness.py"

  # shared/scripts/command_safety.py
  "scripts/command_safety.py|platforms/claude-code/scripts/command_safety.py"
  "scripts/command_safety.py|platforms/cursor/scripts/command_safety.py"
  "scripts/command_safety.py|platforms/codex/plugins/qb/skills/qb/scripts/command_safety.py"

  # shared/scripts/analyzer_quality.py
  "scripts/analyzer_quality.py|platforms/claude-code/scripts/analyzer_quality.py"
  "scripts/analyzer_quality.py|platforms/cursor/scripts/analyzer_quality.py"
  "scripts/analyzer_quality.py|platforms/codex/plugins/qb/skills/qb/scripts/analyzer_quality.py"

  # shared/scripts/analyzer_dependency.py
  "scripts/analyzer_dependency.py|platforms/claude-code/scripts/analyzer_dependency.py"
  "scripts/analyzer_dependency.py|platforms/cursor/scripts/analyzer_dependency.py"
  "scripts/analyzer_dependency.py|platforms/codex/plugins/qb/skills/qb/scripts/analyzer_dependency.py"

  # shared/scripts/analyzer_license.py
  "scripts/analyzer_license.py|platforms/claude-code/scripts/analyzer_license.py"
  "scripts/analyzer_license.py|platforms/cursor/scripts/analyzer_license.py"
  "scripts/analyzer_license.py|platforms/codex/plugins/qb/skills/qb/scripts/analyzer_license.py"

  # shared/scripts/analyzer_config.py
  "scripts/analyzer_config.py|platforms/claude-code/scripts/analyzer_config.py"
  "scripts/analyzer_config.py|platforms/cursor/scripts/analyzer_config.py"
  "scripts/analyzer_config.py|platforms/codex/plugins/qb/skills/qb/scripts/analyzer_config.py"

  # shared/scripts/analyzer_breadth.py
  "scripts/analyzer_breadth.py|platforms/claude-code/scripts/analyzer_breadth.py"
  "scripts/analyzer_breadth.py|platforms/cursor/scripts/analyzer_breadth.py"
  "scripts/analyzer_breadth.py|platforms/codex/plugins/qb/skills/qb/scripts/analyzer_breadth.py"

  # shared/scripts/fixer.py
  "scripts/fixer.py|platforms/claude-code/scripts/fixer.py"
  "scripts/fixer.py|platforms/cursor/scripts/fixer.py"
  "scripts/fixer.py|platforms/codex/plugins/qb/skills/qb/scripts/fixer.py"

  # shared/scripts/isolation.py
  "scripts/isolation.py|platforms/claude-code/scripts/isolation.py"
  "scripts/isolation.py|platforms/cursor/scripts/isolation.py"
  "scripts/isolation.py|platforms/codex/plugins/qb/skills/qb/scripts/isolation.py"

  # shared/scripts/verification_gate.py
  "scripts/verification_gate.py|platforms/claude-code/scripts/verification_gate.py"
  "scripts/verification_gate.py|platforms/cursor/scripts/verification_gate.py"
  "scripts/verification_gate.py|platforms/codex/plugins/qb/skills/qb/scripts/verification_gate.py"

  # shared/scripts/policy.py
  "scripts/policy.py|platforms/claude-code/scripts/policy.py"
  "scripts/policy.py|platforms/cursor/scripts/policy.py"
  "scripts/policy.py|platforms/codex/plugins/qb/skills/qb/scripts/policy.py"

  # shared/scripts/orchestrator.py
  "scripts/orchestrator.py|platforms/claude-code/scripts/orchestrator.py"
  "scripts/orchestrator.py|platforms/cursor/scripts/orchestrator.py"
  "scripts/orchestrator.py|platforms/codex/plugins/qb/skills/qb/scripts/orchestrator.py"

  # shared/scripts/budget.py
  "scripts/budget.py|platforms/claude-code/scripts/budget.py"
  "scripts/budget.py|platforms/cursor/scripts/budget.py"
  "scripts/budget.py|platforms/codex/plugins/qb/skills/qb/scripts/budget.py"

  # shared/scripts/review.py
  "scripts/review.py|platforms/claude-code/scripts/review.py"
  "scripts/review.py|platforms/cursor/scripts/review.py"
  "scripts/review.py|platforms/codex/plugins/qb/skills/qb/scripts/review.py"

  # shared/scripts/run_store.py
  "scripts/run_store.py|platforms/claude-code/scripts/run_store.py"
  "scripts/run_store.py|platforms/cursor/scripts/run_store.py"
  "scripts/run_store.py|platforms/codex/plugins/qb/skills/qb/scripts/run_store.py"

  # shared/scripts/report.py
  "scripts/report.py|platforms/claude-code/scripts/report.py"
  "scripts/report.py|platforms/cursor/scripts/report.py"
  "scripts/report.py|platforms/codex/plugins/qb/skills/qb/scripts/report.py"

  # shared/scripts/qb_headless.py
  "scripts/qb_headless.py|platforms/claude-code/scripts/qb_headless.py"
  "scripts/qb_headless.py|platforms/cursor/scripts/qb_headless.py"
  "scripts/qb_headless.py|platforms/codex/plugins/qb/skills/qb/scripts/qb_headless.py"

  # shared/scripts/telemetry.py
  "scripts/telemetry.py|platforms/claude-code/scripts/telemetry.py"
  "scripts/telemetry.py|platforms/cursor/scripts/telemetry.py"
  "scripts/telemetry.py|platforms/codex/plugins/qb/skills/qb/scripts/telemetry.py"

  # shared/scripts/telemetry_aggregate.py
  "scripts/telemetry_aggregate.py|platforms/claude-code/scripts/telemetry_aggregate.py"
  "scripts/telemetry_aggregate.py|platforms/cursor/scripts/telemetry_aggregate.py"
  "scripts/telemetry_aggregate.py|platforms/codex/plugins/qb/skills/qb/scripts/telemetry_aggregate.py"

  # shared/scripts/telemetry_trends.py
  "scripts/telemetry_trends.py|platforms/claude-code/scripts/telemetry_trends.py"
  "scripts/telemetry_trends.py|platforms/cursor/scripts/telemetry_trends.py"
  "scripts/telemetry_trends.py|platforms/codex/plugins/qb/skills/qb/scripts/telemetry_trends.py"

  # shared/scripts/release_gate.py
  "scripts/release_gate.py|platforms/claude-code/scripts/release_gate.py"
  "scripts/release_gate.py|platforms/cursor/scripts/release_gate.py"
  "scripts/release_gate.py|platforms/codex/plugins/qb/skills/qb/scripts/release_gate.py"

  # shared/scripts/least_privilege.py
  "scripts/least_privilege.py|platforms/claude-code/scripts/least_privilege.py"
  "scripts/least_privilege.py|platforms/cursor/scripts/least_privilege.py"
  "scripts/least_privilege.py|platforms/codex/plugins/qb/skills/qb/scripts/least_privilege.py"

  # shared/scripts/production_gate.py
  "scripts/production_gate.py|platforms/claude-code/scripts/production_gate.py"
  "scripts/production_gate.py|platforms/cursor/scripts/production_gate.py"
  "scripts/production_gate.py|platforms/codex/plugins/qb/skills/qb/scripts/production_gate.py"
)

# Number of distinct shared source files (for the summary line).
SHARED_FILE_COUNT="$(printf '%s\n' "${MAP[@]}" | cut -d'|' -f1 | sort -u | wc -l | tr -d ' ')"

# --- Run -----------------------------------------------------------------------
if [ "$MODE" = "check" ]; then
  drift=()
  for entry in "${MAP[@]}"; do
    src_rel="${entry%%|*}"
    dst_rel="${entry#*|}"
    src="$SHARED_DIR/$src_rel"
    dst="$REPO_ROOT/$dst_rel"

    if [ ! -f "$src" ]; then
      echo "sync.sh: missing shared source: $src" >&2
      exit 1
    fi
    if [ ! -f "$dst" ]; then
      drift+=("MISSING  $dst_rel")
    elif ! cmp -s "$src" "$dst"; then
      drift+=("DIFFERS  $dst_rel")
    fi
  done

  if [ "${#drift[@]}" -gt 0 ]; then
    echo "sync.sh --check: out of sync (${#drift[@]} path(s)):" >&2
    for line in "${drift[@]}"; do
      echo "  $line" >&2
    done
    echo "Run 'scripts/sync.sh' to materialize the shared source of truth." >&2
    exit 1
  fi

  # Completeness: every file under shared/ must be a mapped source. An unmapped
  # shared file would silently never reach any platform, defeating the "single
  # source of truth" contract, so --check fails loudly on it.
  mapped_srcs=()
  for entry in "${MAP[@]}"; do
    mapped_srcs+=("${entry%%|*}")
  done
  unmapped=()
  while IFS= read -r abs; do
    rel="${abs#"${SHARED_DIR}/"}"
    found=0
    for m in "${mapped_srcs[@]}"; do
      if [ "$m" = "$rel" ]; then
        found=1
        break
      fi
    done
    if [ "$found" -eq 0 ]; then
      unmapped+=("$rel")
    fi
  done < <(find "$SHARED_DIR" -type f -not -path '*/__pycache__/*' | sort)

  if [ "${#unmapped[@]}" -gt 0 ]; then
    echo "sync.sh --check: ${#unmapped[@]} shared file(s) not wired into the sync MAP:" >&2
    for rel in "${unmapped[@]}"; do
      echo "  unmapped_shared_source=$rel" >&2
    done
    echo "Add a MAP entry in scripts/sync.sh so the file reaches every platform." >&2
    exit 1
  fi

  echo "sync.sh --check: in sync (${#MAP[@]} copies across 3 platforms)."
  exit 0
fi

# Default mode: copy.
copied=0
for entry in "${MAP[@]}"; do
  src_rel="${entry%%|*}"
  dst_rel="${entry#*|}"
  src="$SHARED_DIR/$src_rel"
  dst="$REPO_ROOT/$dst_rel"

  if [ ! -f "$src" ]; then
    echo "sync.sh: missing shared source: $src" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$dst")"
  cp -p "$src" "$dst"
  copied=$((copied + 1))
done

echo "sync.sh: synced $SHARED_FILE_COUNT shared file(s) to 3 platforms ($copied copies)."
