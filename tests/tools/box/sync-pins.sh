#!/usr/bin/env bash
# sync-pins.sh [--dry-run]
# Align the shared sibling checkouts with the pins on THIS branch, so a golden/crucible run reads the
# corpus version the branch expects (a stale checkout gives thousands of phantom diffs, #3386):
#   language-crucible, cics-crucible, estate-crucible -> the refs in tests/crucible_pins.toml
# (tests/tools/crucible_pins.py check / sync does the same with a clearer report; this keeps the
# --dry-run and the refuse-all-first behaviour.)
# Paths: $LANGUAGE_CRUCIBLE_PATH / $CICS_CRUCIBLE_PATH / $ESTATE_CRUCIBLE_PATH, else <dir>/<name> beside the
# primary checkout (found via git-common-dir). Runs under golden-lock.sh (no golden run is reading a
# checkout mid-switch), does `git fetch --tags` + `checkout --detach`. Refuses, touching nothing, if any
# checkout has tracked modifications (untracked scan caches are fine). --dry-run: report only, no fetch,
# no lock, no change. A checkout that is absent is skipped with a note. Exit 1 if refused.
set -u
dry=0
case "${1:-}" in
  --dry-run) dry=1 ;;
  "") ;;
  *) sed -n '2,12p' "$0" >&2; exit 2 ;;
esac
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [ "$dry" = 0 ] && [ -z "${GG_SYNC_LOCKED:-}" ]; then
  GG_SYNC_LOCKED=1 exec "$here/golden-lock.sh" "$0" "$@"
fi
repo=$(git -C "$here" rev-parse --show-toplevel) || exit 2
common=$(git -C "$repo" rev-parse --git-common-dir)
case "$common" in /*) ;; *) common="$repo/$common" ;; esac
primary=$(dirname "$(cd "$common" && pwd)")
sibling=$(dirname "$primary")

pin() {  # pin <name>: the ref in this branch's tests/crucible_pins.toml
  python3 "$repo/tests/tools/crucible_pins.py" get "$1" 2>/dev/null
}
names=(language-crucible cics-crucible estate-crucible)
paths=("${LANGUAGE_CRUCIBLE_PATH:-$sibling/language-crucible}"
       "${CICS_CRUCIBLE_PATH:-$sibling/cics-crucible}"
       "${ESTATE_CRUCIBLE_PATH:-$sibling/estate-crucible}")
refs=("$(pin language)" "$(pin cics)" "$(pin estate)")

bad=0
for i in 0 1 2; do   # pass 1: refuse before touching anything
  n=${names[$i]}; p=${paths[$i]}; r=${refs[$i]}
  if [ -z "$r" ]; then echo "ERROR  $n: no pin found in tests/crucible_pins.toml" >&2; bad=1; continue; fi
  [ -e "$p/.git" ] || continue
  if [ -n "$(git -C "$p" status --porcelain --untracked-files=no)" ]; then
    echo "REFUSE $n ($p): tracked modifications; resolve them first" >&2; bad=1
  fi
done
[ "$bad" = 0 ] || exit 1

for i in 0 1 2; do
  n=${names[$i]}; p=${paths[$i]}; r=${refs[$i]}
  if [ ! -e "$p/.git" ]; then echo "SKIP   $n: no checkout at $p"; continue; fi
  head=$(git -C "$p" rev-parse HEAD)
  if [ "$dry" = 1 ]; then
    want=$(git -C "$p" rev-parse -q --verify "$r^{commit}" || echo "")
    if [ -z "$want" ]; then echo "WOULD  $n: fetch --tags, then checkout --detach $r (not known locally yet)"
    elif [ "$want" = "$head" ]; then echo "OK     $n: already at $r"
    else echo "WOULD  $n: checkout --detach $r (now at ${head:0:9}, $r is ${want:0:9})"; fi
    continue
  fi
  git -C "$p" fetch --tags -q || { echo "ERROR  $n: git fetch --tags failed" >&2; exit 1; }
  git -C "$p" checkout -q --detach "$r" || { echo "ERROR  $n: cannot check out $r" >&2; exit 1; }
  echo "SYNCED $n: $r ($(git -C "$p" rev-parse --short HEAD)) at $p"
done
