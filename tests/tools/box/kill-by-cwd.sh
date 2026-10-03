#!/usr/bin/env bash
# kill-by-cwd.sh <dir> [--dry-run]
# Kill every process whose cwd is <dir> or below it (an agent's orphaned helper, its queued flock'd
# pr_gates). Matching by cwd, not by command pattern, cannot hit the caller's own shell the way
# `pkill -f <pattern>` did (exit 144). Never kills itself or its ancestors. Always lists first;
# --dry-run lists only. SIGTERM, then SIGKILL after 3s for survivors.
set -u
[ $# -ge 1 ] || { sed -n '2,7p' "$0" >&2; exit 2; }
dir=$(readlink -f "$1") || exit 2
dry=0; [ "${2:-}" = "--dry-run" ] && dry=1
[ -d "$dir" ] || { echo "no such dir: $dir" >&2; exit 2; }
[ "$dir" != / ] || { echo "refusing /" >&2; exit 2; }
skip=" "; p=$$
while [ "$p" -gt 1 ] 2>/dev/null; do skip="$skip$p "; p=$(awk '/^PPid:/{print $2}' "/proc/$p/status" 2>/dev/null); [ -n "$p" ] || break; done
pids=()
for d in /proc/[0-9]*; do
  pid=${d#/proc/}
  case "$skip" in *" $pid "*) continue;; esac
  cwd=$(readlink "$d/cwd" 2>/dev/null) || continue
  case "$cwd" in "$dir"|"$dir"/*) pids+=("$pid"); echo "$pid  $cwd  $(tr '\0' ' ' < "$d/cmdline" 2>/dev/null | cut -c1-100)";; esac
done
echo "${#pids[@]} process(es) under $dir"
[ "$dry" = 1 ] || [ "${#pids[@]}" -eq 0 ] && exit 0
kill "${pids[@]}" 2>/dev/null; sleep 3
for pid in "${pids[@]}"; do kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null; done
exit 0
