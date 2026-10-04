#!/usr/bin/env bash
# wait-pids.sh <pid...>
# Block until every PID has exited; print "<pid> exit=<status>" (status only for our own children,
# else "exit=unknown"). Wait on PIDs, never on output files a job "will" write -- a job that never
# started never writes them and the watcher hangs forever. Exit 0 always unless usage error.
set -u
[ $# -ge 1 ] || { sed -n '2,5p' "$0" >&2; exit 2; }
for pid in "$@"; do
  if wait "$pid" 2>/dev/null; then echo "$pid exit=0"; continue; fi
  rc=$?
  if kill -0 "$pid" 2>/dev/null || [ "$rc" = 127 ]; then
    while kill -0 "$pid" 2>/dev/null && [ "$(awk '/^State:/{print $2}' "/proc/$pid/status" 2>/dev/null)" != Z ]; do sleep 0.5; done
    echo "$pid exit=unknown"
  else
    echo "$pid exit=$rc"
  fi
done
