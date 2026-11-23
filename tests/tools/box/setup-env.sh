#!/usr/bin/env bash
# setup-env.sh [--check]
# One command that makes any machine (melek, the second computer, a fresh worktree) run the opt-in tests the same way.
# It runs tests/tools/box/env_check.py with --fix: checks Docker, JDK 17 + javac, Maven, universal-ctags, the selfscan venv,
# syncs the crucible checkouts to the pins, and fetches the mainframe corpora this checkout's e2e cases read. It prints a
# PASS/MISSING table (exact fix command per gap) and the `export` lines to put in your shell, and exits 1 if anything
# required is missing. Idempotent: a second run changes nothing. Never uses sudo or installs system packages.
#   bash tests/tools/box/setup-env.sh           # check and fix what needs no sudo
#   bash tests/tools/box/setup-env.sh --check   # check only, change nothing
#   eval "$(python3 tests/tools/box/env_check.py --exports)"   # then export the env into your shell
set -u
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mode=--fix
case "${1:-}" in
  --check) mode="" ;;
  "") ;;
  *) sed -n '2,12p' "$0" >&2; exit 2 ;;
esac
repo=$(git -C "$here" rev-parse --show-toplevel) || exit 2
common=$(git -C "$repo" rev-parse --git-common-dir)
case "$common" in /*) ;; *) common="$repo/$common" ;; esac
sibling=$(dirname "$(dirname "$(cd "$common" && pwd)")")
py=python3
for v in "${GG_VENV:-}" "$sibling/venvs/selfscan" "$repo/.venv"; do
  if [ -n "$v" ] && [ -x "$v/bin/python" ]; then py="$v/bin/python"; break; fi
done
# shellcheck disable=SC2086
exec "$py" "$here/env_check.py" $mode
