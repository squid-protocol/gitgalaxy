#!/usr/bin/env bash
# heavy-run.sh <cmd...>
# Run a heavy command (pr_gates, a scan sweep, the full suite) in one of N shared slots so a box's
# cores are used, not serialized behind one lock and not oversubscribed (#4247: load-induced regex
# timeouts faked 2,911 golden diffs).
#   N = ${GG_HEAVY_SLOTS:-$(( $(nproc) / 4 ))}, minimum 1.   Locks: ${GG_LOCK_DIR:-/tmp/gitgalaxy-scratch/locks}
# Golden bless/check must NOT use this: use golden-lock.sh (exclusive). Decide the slot count BEFORE
# launching a fleet and never change it mid-run. Exit status is the command's.
set -u
[ $# -ge 1 ] || { sed -n '2,8p' "$0" >&2; exit 2; }
# without flock(1) no slot is ever taken and the loop below would sleep forever (#4840: macOS)
command -v flock >/dev/null || { echo "heavy-run.sh: flock(1) not found (Linux util-linux)" >&2; exit 127; }
n=${GG_HEAVY_SLOTS:-$(( $(nproc) / 4 ))}
[ "$n" -ge 1 ] 2>/dev/null || n=1
dir=${GG_LOCK_DIR:-/tmp/gitgalaxy-scratch/locks}
mkdir -p "$dir"
while true; do
  for ((i = 1; i <= n; i++)); do
    exec 9>"$dir/heavy.slot$i"
    if flock -n 9; then "$@"; rc=$?; exec 9>&-; exit $rc; fi
    exec 9>&-
  done
  sleep "${GG_HEAVY_POLL:-5}"
done
