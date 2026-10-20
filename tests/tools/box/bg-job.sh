#!/usr/bin/env bash
# bg-job.sh start NAME -- cmd...   start cmd detached; its pid, log and exit code are kept under NAME
# bg-job.sh wait NAME [SECONDS]    wait up to SECONDS (default 540, under the 10-min tool cap) on NAME's pid; prints
#                                  "NAME exit=<status>" and the log tail, exits with the job's status; 124 = still
#                                  running (call wait again), "exit=unknown" = the job died without writing a status
# bg-job.sh status NAME            "running" / "exit=<status>" / "unknown", no waiting
# For a long proof / scan you check on later from another shell call: the pid survives the call, so no `pgrep -f`
# or `until grep <log>; do sleep` loop is needed (a hook denies those, 2026-10-20: 2 of 4 refused worker calls).
# Jobs live in $GG_BG_DIR (default /tmp/gitgalaxy-scratch/bg/<worktree name>), so workers never share a NAME.
set -u
usage() { sed -n '2,10p' "$0" >&2; exit 2; }
[ $# -ge 2 ] || usage
cmd=$1 name=$2
shift 2
case "$name" in */* | .* | "") echo "bg-job: NAME must be a plain word" >&2; exit 2 ;; esac
top=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
dir=${GG_BG_DIR:-/tmp/gitgalaxy-scratch/bg/$(basename "$top")}
pidf=$dir/$name.pid logf=$dir/$name.log exitf=$dir/$name.exit
alive() { [ -s "$pidf" ] && kill -0 "$(cat "$pidf")" 2>/dev/null \
  && [ "$(awk '/^State:/{print $2}' "/proc/$(cat "$pidf")/status" 2>/dev/null)" != Z ]; }
report() {  # prints the status line + log tail, returns the job's status
  if [ -s "$exitf" ]; then
    rc=$(cat "$exitf"); echo "$name exit=$rc"; tail -n 20 "$logf" 2>/dev/null; return "$rc"
  fi
  echo "$name exit=unknown (no status written; log: $logf)"; tail -n 20 "$logf" 2>/dev/null; return 1
}
case "$cmd" in
  start)
    [ "${1:-}" = "--" ] && shift
    [ $# -ge 1 ] || usage
    if alive; then echo "bg-job: $name is still running (pid $(cat "$pidf"))" >&2; exit 2; fi
    mkdir -p "$dir" && rm -f "$pidf" "$exitf"
    # setsid: the job outlives this shell call; the wrapper writes the status file when the command ends
    setsid bash -c '"$@"; echo $? > "$0"' "$exitf" "$@" > "$logf" 2>&1 < /dev/null &
    echo $! > "$pidf"
    echo "$name pid=$! log=$logf"
    ;;
  wait)
    max=${1:-540}
    [ -s "$pidf" ] || { echo "bg-job: no job $name in $dir" >&2; exit 2; }
    end=$((SECONDS + max))
    while alive; do
      if [ "$SECONDS" -ge "$end" ]; then
        echo "$name still running after ${max}s (pid $(cat "$pidf")); call wait again"; tail -n 5 "$logf"; exit 124
      fi
      sleep 2
    done
    report
    ;;
  status)
    if alive; then echo running; elif [ -s "$exitf" ]; then echo "exit=$(cat "$exitf")"; else echo unknown; fi
    ;;
  *) usage ;;
esac
