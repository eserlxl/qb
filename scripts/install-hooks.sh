#!/usr/bin/env bash
#
# install-hooks.sh -- opt-in installer for QB's local git hooks.
#
# Installs scripts/hooks/pre-push into .git/hooks/pre-push so that `git push` first
# runs the gate of record (`make check`). This is ENTIRELY OPT-IN: nothing installs
# it automatically, it performs no network access and no push, and it only ever
# writes inside this repo's .git/hooks/ directory.
#
# Usage:
#   scripts/install-hooks.sh             install the pre-push hook (explicit opt-in)
#   scripts/install-hooks.sh --dry-run   print what would be installed; write nothing
#   scripts/install-hooks.sh --uninstall remove a pre-push hook this installer wrote
#
# Dependency-free: bash + coreutils (cp / chmod / rm).

set -euo pipefail

SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -P "$SCRIPT_DIR/.." && pwd)"
HOOK_SRC="$SCRIPT_DIR/hooks/pre-push"
HOOKS_DIR="$REPO_ROOT/.git/hooks"
HOOK_DST="$HOOKS_DIR/pre-push"

MODE="install"
case "${1:-}" in
  "")          MODE="install" ;;
  --dry-run)   MODE="dry-run" ;;
  --uninstall) MODE="uninstall" ;;
  -h|--help)
    echo "Usage: scripts/install-hooks.sh [--dry-run|--uninstall]"
    echo "  (no args)     install the pre-push hook (explicit opt-in; runs 'make check')"
    echo "  --dry-run     print what would be installed; write nothing"
    echo "  --uninstall   remove a pre-push hook this installer wrote"
    exit 0
    ;;
  *)
    echo "install-hooks.sh: unknown argument: $1" >&2
    echo "Usage: scripts/install-hooks.sh [--dry-run|--uninstall]" >&2
    exit 2
    ;;
esac

if [ ! -f "$HOOK_SRC" ]; then
  echo "install-hooks.sh: missing hook source: $HOOK_SRC" >&2
  exit 1
fi

if [ "$MODE" = "dry-run" ]; then
  echo "install-hooks.sh (dry-run): would install $HOOK_SRC -> $HOOK_DST"
  echo "install-hooks.sh (dry-run): the hook runs 'make check' before each push; no files written."
  exit 0
fi

if [ "$MODE" = "uninstall" ]; then
  if [ -f "$HOOK_DST" ]; then
    rm -f "$HOOK_DST"
    echo "install-hooks.sh: removed $HOOK_DST"
  else
    echo "install-hooks.sh: no pre-push hook to remove at $HOOK_DST"
  fi
  exit 0
fi

# install (explicit opt-in)
if [ ! -d "$HOOKS_DIR" ]; then
  echo "install-hooks.sh: $HOOKS_DIR does not exist (not a git repo?)" >&2
  exit 1
fi
cp "$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"
echo "install-hooks.sh: installed pre-push hook -> $HOOK_DST (runs 'make check' before each push)."
echo "install-hooks.sh: remove it any time with 'scripts/install-hooks.sh --uninstall'."
