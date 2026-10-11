#!/usr/bin/env bash
# heavy-run.sh <cmd...>
# Run a heavy command (pr_gates, a scan sweep, the full suite) in one of N shared slots so a box's
# cores are used, not serialized behind one lock and not oversubscribed (#4247: load-induced regex
# timeouts faked 2,911 golden diffs).
#   N = ${GG_HEAVY_SLOTS:-$(( $(nproc) / 4 ))}, minimum 1.   Locks: ${GG_LOCK_DIR:-/tmp/gitgalaxy-scratch/locks}
# Golden bless/check must NOT use this: use golden-lock.sh (exclusive). Decide the slot count BEFORE
# launching a fleet and never change it mid-run. Exit status is the command's. The job gets GG_JOB_CORES (nproc / slots
# held when it starts): parallel tools (pr_gates' gauntlet) size their workers from it.
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
    if flock -n 9; then
      # a fair share of the cores for the job (#4882): one heavy job alone gets all of them, k jobs at once nproc/k each
      # (pr_gates' unicode gauntlet ran --jobs nproc in every slot: two gates = 2x the cores, load 52-60 on 12)
      held=1
      for ((j = 1; j <= n; j++)); do
        [ "$j" -eq "$i" ] && continue
        exec 8>"$dir/heavy.slot$j"
        if flock -n 8; then flock -u 8; else held=$((held + 1)); fi
        exec 8>&-
      done
      cores=$(nproc 2>/dev/null || echo 4)
      GG_JOB_CORES=$((cores / held)); [ "$GG_JOB_CORES" -ge 1 ] || GG_JOB_CORES=1
      export GG_JOB_CORES
      "$@"; rc=$?; exec 9>&-; exit $rc
    fi
    exec 9>&-
  done
  sleep "${GG_HEAVY_POLL:-5}"
done
