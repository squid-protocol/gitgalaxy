#!/usr/bin/env bash
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
# worktree_env.sh <name> [--corpus]   (#2916)
#
# Every environment trap of the #2908 session -- wrong-path worktree, background
# job from a drifted cwd, stale corpus worktree producing a phantom mismatch --
# is this script not existing. It:
#   1. refuses to run its checkout steps against the PRIMARY checkout;
#   2. `git fetch`es, then creates (or re-detaches to origin/main) the engine
#      worktree at <worktrees-root>/<name>, where <worktrees-root> is
#      <repo-parent>/gitgalaxy-worktrees -- ~/nyx_projects/gitgalaxy-worktrees on
#      the primary box, .../projects/gitgalaxy/gitgalaxy-worktrees elsewhere --
#      overridable via GITGALAXY_WORKTREES;
#   3. with --corpus, does the same for keyword-rosetta at
#      <corpus-parent>/keyword-rosetta-worktrees/<name> (KEYWORD_ROSETTA_WORKTREES);
#   4. prints the five exports as copy-paste lines. PYTHONPATH comes FIRST on
#      sys.path, so the worktree's engine code wins over the primary venv's
#      editable install even when GALAXYSCOPE_BIN is the primary venv's stub --
#      the confirmed-root-cause trap crucible_check.py's docstring documents.
set -euo pipefail

usage() { echo "usage: tests/tools/worktree_env.sh <name> [--corpus]" >&2; exit 2; }
[ $# -ge 1 ] || usage
NAME="$1"; shift
WANT_CORPUS=0
[ "${1:-}" = "--corpus" ] && WANT_CORPUS=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRIMARY="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
WT_ROOT="${GITGALAXY_WORKTREES:-$(dirname "$PRIMARY")/gitgalaxy-worktrees}"
WT="$WT_ROOT/$NAME"

if [ "$WT" = "$PRIMARY" ] || [ "$(cd "$WT" 2>/dev/null && pwd)" = "$PRIMARY" ]; then
  echo "refusing: target resolves to the primary checkout ($PRIMARY)" >&2
  exit 1
fi

git -C "$PRIMARY" fetch origin --quiet
mkdir -p "$WT_ROOT"
if [ -d "$WT/.git" ] || [ -f "$WT/.git" ]; then
  git -C "$WT" fetch origin --quiet || true
  git -C "$WT" checkout --detach origin/main --quiet
  echo "engine worktree re-detached at origin/main: $WT" >&2
else
  git -C "$PRIMARY" worktree add --detach "$WT" origin/main >&2
  echo "engine worktree created: $WT" >&2
fi

# Corpus roots via the same sibling logic rule_probe.py uses.
sibling() { # <name>
  for base in "$(dirname "$PRIMARY")" "$(dirname "$(dirname "$PRIMARY")")"; do
    if [ -d "$base/$1/data" ]; then echo "$base/$1"; return; fi
  done
  echo "$(dirname "$PRIMARY")/$1"
}
CRUCIBLE="${LANGUAGE_CRUCIBLE_PATH:-$(sibling language-crucible)}"
ROSETTA_MAIN="${KEYWORD_ROSETTA_PATH:-$(sibling keyword-rosetta)}"
ROSETTA="$ROSETTA_MAIN"

if [ "$WANT_CORPUS" = 1 ]; then
  KR_ROOT="${KEYWORD_ROSETTA_WORKTREES:-$(dirname "$ROSETTA_MAIN")/keyword-rosetta-worktrees}"
  KR_WT="$KR_ROOT/$NAME"
  if [ "$KR_WT" = "$ROSETTA_MAIN" ]; then
    echo "refusing: corpus target resolves to the primary corpus checkout" >&2
    exit 1
  fi
  git -C "$ROSETTA_MAIN" fetch origin --quiet
  mkdir -p "$KR_ROOT"
  if [ -d "$KR_WT/.git" ] || [ -f "$KR_WT/.git" ]; then
    git -C "$KR_WT" fetch origin --quiet || true
    git -C "$KR_WT" checkout --detach origin/main --quiet
    echo "corpus worktree re-detached at origin/main: $KR_WT" >&2
  else
    git -C "$ROSETTA_MAIN" worktree add --detach "$KR_WT" origin/main >&2
    echo "corpus worktree created: $KR_WT" >&2
  fi
  ROSETTA="$KR_WT"
fi

echo
CORPUS_FLAG=""
[ "$WANT_CORPUS" = 1 ] && CORPUS_FLAG=" --corpus"
echo "# copy-paste (or: eval \"\$(tests/tools/worktree_env.sh $NAME$CORPUS_FLAG 2>/dev/null)\"):"
echo "export PYTHONPATH=$WT"
echo "export GITGALAXY_PATH=$WT"
echo "export GALAXYSCOPE_BIN=$PRIMARY/.venv/bin/galaxyscope"
echo "export LANGUAGE_CRUCIBLE_PATH=$CRUCIBLE"
echo "export KEYWORD_ROSETTA_PATH=$ROSETTA"
