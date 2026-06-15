#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Eser KUBALI
# SPDX-License-Identifier: MIT
#
# Bump the QB version in lockstep across the whole monorepo.
#
# QB keeps the root VERSION file as the single source of version truth
# (tests/test_version_and_structure.py enforces that every platform manifest
# equals it). This script bumps VERSION and propagates the new value to:
#   - the three platform plugin manifests (claude-code / cursor / codex),
#   - the `metadata: version:` line in every platform SKILL.md, and
#   - a new entry at the top of each platform CHANGELOG.md.
#
# It does NOT create a git tag or GitHub release. Tags belong at release
# milestones; run this freely during development and tag manually later.
#
# Logic and the transactional/atomic hardening are adapted from planwright's
# scripts/bump-version.sh, re-homed onto QB's VERSION-anchored, three-platform
# monorepo layout.
#
# Usage:
#   scripts/bump-version.sh <major|minor|patch|X.Y.Z> [-m "changelog note"] [--dry-run]
#   scripts/bump-version.sh --sync [--dry-run]
#
# Modes:
#   <bump>     Increment VERSION, propagate to manifests + SKILL.md frontmatter,
#              and prepend a CHANGELOG entry to every platform.
#   --sync     Re-propagate the CURRENT VERSION to manifests + SKILL.md without
#              changing the version or writing a changelog. Use this to seed a
#              missing `version:` line, onboard a new skill, or repair drift.
#
# Examples:
#   scripts/bump-version.sh patch
#   scripts/bump-version.sh minor -m "Add foo option"
#   scripts/bump-version.sh 2.0.0 -m "Rewrite the pipeline"
#   scripts/bump-version.sh --sync
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_FILE="$ROOT/VERSION"

# Platform manifests, keyed for reporting. Codex nests its manifest under
# plugins/qb/.codex-plugin/ (an accepted structural asymmetry, pinned by
# tests/test_version_and_structure.py).
MANIFESTS=(
  "$ROOT/platforms/claude-code/.claude-plugin/plugin.json"
  "$ROOT/platforms/cursor/.cursor-plugin/plugin.json"
  "$ROOT/platforms/codex/plugins/qb/.codex-plugin/plugin.json"
)
CHANGELOGS=(
  "$ROOT/platforms/claude-code/CHANGELOG.md"
  "$ROOT/platforms/cursor/CHANGELOG.md"
  "$ROOT/platforms/codex/CHANGELOG.md"
)

# Portable repo-relative path. GNU realpath's relative mode is unavailable on
# stock macOS without Homebrew; python3 is already required by this script.
relpath() { python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$1" "$ROOT"; }

# Enumerate every platform SKILL.md (skipped silently if a platform is not built).
skill_files() {
  find "$ROOT/platforms" -type f -name SKILL.md 2>/dev/null | sort
}

usage() {
  echo "Usage: $(basename "$0") <major|minor|patch|X.Y.Z> [-m \"changelog note\"] [--dry-run]" >&2
  echo "       $(basename "$0") --sync [--dry-run]" >&2
  exit 1
}

[ $# -ge 1 ] || usage
case "$1" in
  -h|--help)
    echo "Usage: $(basename "$0") <major|minor|patch|X.Y.Z> [-m \"changelog note\"] [--dry-run]"
    echo "       $(basename "$0") --sync [--dry-run]"
    exit 0 ;;
esac

BUMP=""
SYNC_ONLY=""
NOTE=""
DRY_RUN=""
if [ "$1" = "--sync" ]; then
  SYNC_ONLY=1; shift
else
  BUMP="$1"; shift
fi
while [ $# -gt 0 ]; do
  case "$1" in
    -m|--message)
      [ $# -ge 2 ] || { echo "Option $1 requires a value" >&2; usage; }
      NOTE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      echo "Usage: $(basename "$0") <major|minor|patch|X.Y.Z> [-m \"changelog note\"] [--dry-run]"
      echo "       $(basename "$0") --sync [--dry-run]"
      exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage ;;
  esac
done

[ -z "$SYNC_ONLY" ] || [ -z "$NOTE" ] || { echo "--sync does not write a changelog; -m is not allowed with it." >&2; usage; }

[ -f "$VERSION_FILE" ] || { echo "Missing required file: $VERSION_FILE (single source of version truth)" >&2; exit 1; }
for f in "${MANIFESTS[@]}"; do
  [ -f "$f" ] || { echo "Missing required manifest: $f" >&2; exit 1; }
done
if [ -z "$SYNC_ONLY" ]; then
  for f in "${CHANGELOGS[@]}"; do
    [ -f "$f" ] || { echo "Missing required file: $f" >&2; exit 1; }
  done
fi

# All-or-nothing preflight: every text file we will *read* is decode-checked as
# strict UTF-8 before any write, so one bad byte cannot abort the run mid-way
# with some files already bumped — exactly the version drift the lockstep
# contract forbids.
python3 - "$ROOT" <<'PY' || exit 1
import glob, os, sys
root = sys.argv[1]
targets = []
targets += glob.glob(os.path.join(root, "platforms", "*", "CHANGELOG.md"))
targets += glob.glob(os.path.join(root, "platforms", "**", "SKILL.md"), recursive=True)
for path in sorted(set(targets)):
    try:
        with open(path, encoding="utf-8") as fh:
            fh.read()
    except UnicodeDecodeError:
        sys.stderr.write(f"bump-version: {os.path.relpath(path, root)} is not valid UTF-8; aborting before any edits\n")
        sys.exit(1)
PY

# Refuse to mutate a dirty tree so the bump's edits stay isolated and revertible.
# Skipped when not inside a git work tree or when ALLOW_DIRTY=1.
if [ "${ALLOW_DIRTY:-0}" != "1" ] && git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
    echo "Working tree not clean; commit or stash first, or set ALLOW_DIRTY=1." >&2
    exit 1
  fi
fi

CURRENT="$(tr -d '[:space:]' < "$VERSION_FILE")"
[ -n "$CURRENT" ] || { echo "VERSION file is empty" >&2; exit 1; }

if [ -n "$SYNC_ONLY" ]; then
  NEW="$CURRENT"
else
  NEW="$(python3 - "$CURRENT" "$BUMP" <<'PY'
import re, sys
cur, bump = sys.argv[1], sys.argv[2]
# Accept an explicit target version: strict X.Y.Z, optionally with a SemVer
# pre-release (-rc1) and/or build (+meta) suffix.
if re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", bump):
    print(bump); raise SystemExit
# A relative bump operates on the release core: strip any pre-release/build
# suffix from the current version first.
core = re.match(r"(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$", cur)
if not core:
    sys.stderr.write(f"Current version '{cur}' is not X.Y.Z\n"); raise SystemExit(1)
major, minor, patch = (int(g) for g in core.groups())
if bump == "major":   major, minor, patch = major + 1, 0, 0
elif bump == "minor": minor, patch = minor + 1, 0
elif bump == "patch": patch += 1
else:
    sys.stderr.write("bump must be one of: major | minor | patch | X.Y.Z\n"); raise SystemExit(1)
print(f"{major}.{minor}.{patch}")
PY
)"
  if [ "$NEW" = "$CURRENT" ]; then
    echo "Already at $CURRENT; use --sync to re-propagate without a changelog entry." >&2
    exit 1
  fi
fi

DATE="$(date -u +%Y-%m-%d)"

# --- Collect targets -------------------------------------------------------
mapfile -t SKILLS < <(skill_files)

# --- Transactional guard ---------------------------------------------------
# VERSION, manifests, SKILL.md frontmatter, and (for a real bump) CHANGELOGs are
# rewritten as separate steps below. Back up every target up front and restore
# them ALL if any step fails or the run is interrupted, so a partial bump is
# impossible. (Skipped on --dry-run, which writes nothing.)
if [ -z "$DRY_RUN" ]; then
  _bump_targets=("$VERSION_FILE" "${MANIFESTS[@]}")
  [ "${#SKILLS[@]}" -gt 0 ] && _bump_targets+=("${SKILLS[@]}")
  [ -z "$SYNC_ONLY" ] && _bump_targets+=("${CHANGELOGS[@]}")
  BUMP_BACKUP="$(mktemp -d)"
  for _i in "${!_bump_targets[@]}"; do
    cp -p "${_bump_targets[$_i]}" "$BUMP_BACKUP/$_i"
  done
  _bump_restore() {
    local _i
    for _i in "${!_bump_targets[@]}"; do
      [ -f "$BUMP_BACKUP/$_i" ] && cp -p "$BUMP_BACKUP/$_i" "${_bump_targets[$_i]}" 2>/dev/null || true
    done
    echo "bump-version: a step failed or was interrupted; restored all files to their pre-bump state." >&2
  }
  trap '_bump_restore' ERR INT TERM
fi

# --- Update VERSION + JSON manifests ---------------------------------------
if [ -z "$DRY_RUN" ]; then
python3 - "$VERSION_FILE" "$NEW" "${MANIFESTS[@]}" <<'PY'
import json, os, sys, tempfile
version_file, new, *manifests = sys.argv[1:]

def atomic_write(path, data):
    # Same-directory temp + os.replace: never truncate-then-write, so a crash
    # between truncate and the completed write (the one window the ERR/INT/TERM
    # trap cannot catch) cannot leave a partial/truncated file.
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".bump-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise

atomic_write(version_file, new + "\n")
for path in manifests:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["version"] = new
    atomic_write(path, json.dumps(data, indent=2) + "\n")
PY
fi

# --- Sync SKILL.md `metadata: version:` frontmatter ------------------------
# Insert-or-replace the version inside the leading YAML frontmatter block only,
# under a `metadata:` key (the sanctioned place for custom fields). The `name:`
# line is left untouched so tests/qb_monorepo.frontmatter_name keeps working.
SKILLS_SYNCED=""
for skill in "${SKILLS[@]}"; do
  [ -f "$skill" ] || continue
  rel="$(relpath "$skill")"
  changed="$(python3 - "$skill" "$NEW" "${DRY_RUN:-0}" <<'PY'
import os, re, sys, tempfile
path, new, dry = sys.argv[1], sys.argv[2], sys.argv[3]

def atomic_write(path, data):
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".bump-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise

with open(path, encoding="utf-8") as f:
    text = f.read()
lines = text.splitlines(keepends=True)
if not lines or lines[0].strip() != "---":
    print("noblock"); raise SystemExit          # no frontmatter; refuse to guess
# Locate the closing fence of the leading frontmatter block.
end = None
for i in range(1, len(lines)):
    if lines[i].strip() == "---":
        end = i
        break
if end is None:
    print("noblock"); raise SystemExit

block = lines[1:end]
newline = "\n"

def value_line(indent):
    return f'{indent}version: "{new}"{newline}'

# 1) Existing `  version:` under metadata -> replace in place.
for j, ln in enumerate(block):
    m = re.match(r'^(\s+)version:\s*', ln)
    if m and m.group(1):   # indented (i.e. nested under metadata)
        block[j] = value_line(m.group(1))
        break
else:
    # 2) A `metadata:` key exists -> add `  version:` right after it.
    for j, ln in enumerate(block):
        if re.match(r'^metadata:\s*$', ln):
            block.insert(j + 1, value_line("  "))
            break
    else:
        # 3) No metadata block -> append one at the end of the frontmatter.
        if block and not block[-1].endswith("\n"):
            block[-1] += newline
        block.append(f"metadata:{newline}")
        block.append(value_line("  "))

if dry != "0":
    print("would")
    raise SystemExit

new_text = lines[0] + "".join(block) + "".join(lines[end:])
if new_text != text:
    atomic_write(path, new_text)
    print("changed")
else:
    print("same")
PY
)"
  case "$changed" in
    noblock) echo "warning: no YAML frontmatter block in $rel; skipped" >&2 ;;
    "") echo "warning: frontmatter sync produced no result for $rel; skipped" >&2 ;;
    *) SKILLS_SYNCED="$SKILLS_SYNCED $rel" ;;
  esac
done

# --- Prepend a CHANGELOG entry to every platform ---------------------------
if [ -z "$DRY_RUN" ] && [ -z "$SYNC_ONLY" ]; then
python3 - "$NEW" "$DATE" "$NOTE" "${CHANGELOGS[@]}" <<'PY'
import os, sys, tempfile
new, date, note, *changelogs = sys.argv[1:]

def atomic_write(path, data):
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".bump-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise

note = note or "Version bump."
block = f"## [{new}] - {date}\n\n### Changed\n- {note}\n\n"
for path in changelogs:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    idx = next((i for i, ln in enumerate(lines) if ln.startswith("## [")), None)
    if idx is None:
        sys.stderr.write(f"warning: no '## [' version section in {os.path.basename(path)}; appending at end\n")
        idx = len(lines)
    lines[idx:idx] = [block]
    atomic_write(path, "".join(lines))
PY
fi

# All writes succeeded — commit the transaction: drop the trap and clean up.
if [ -z "$DRY_RUN" ]; then
  trap - ERR INT TERM
  rm -rf "$BUMP_BACKUP"
fi

# --- Report ----------------------------------------------------------------
if [ -n "$DRY_RUN" ]; then
  if [ -n "$SYNC_ONLY" ]; then
    echo "dry-run: re-propagate $CURRENT to all manifests + SKILL.md (files not modified)"
  else
    echo "dry-run: $CURRENT -> $NEW (files not modified)"
    echo
    echo "Would prepend to every platform CHANGELOG.md:"
    echo "## [$NEW] - $DATE"
    echo
    echo "### Changed"
    echo "- ${NOTE:-Version bump.}"
  fi
  # if/fi (not `[ ] && echo`): as the branch's last statement under set -e, a
  # false test would otherwise become the script's exit status.
  if [ -n "$SKILLS_SYNCED" ]; then echo "  would sync$SKILLS_SYNCED"; fi
else
  if [ -n "$SYNC_ONLY" ]; then
    echo "Synced: all manifests + SKILL.md re-propagated to $CURRENT"
  else
    echo "Bumped: $CURRENT -> $NEW"
    echo "  updated $(relpath "$VERSION_FILE")"
  fi
  for m in "${MANIFESTS[@]}"; do echo "  updated $(relpath "$m")"; done
  [ -n "$SKILLS_SYNCED" ] && echo "  updated$SKILLS_SYNCED"
  [ -z "$SYNC_ONLY" ] && echo "  changelog entry added to all platforms ($DATE)"
  echo
  echo "Next: review the diff, run 'make check', commit."
fi
