#!/usr/bin/env bash
# ci_retry.sh <attempts> <backoff-seconds> -- <cmd...>   (#5048)
# Run a network-flaky CI step (apt, npm, docker pull) up to <attempts> times, sleeping backoff, 2*backoff, ... between
# tries. When every try fails it prints an INFRASTRUCTURE marker -- tests/tools/ci_digest.py INFRA_LOG matches it, so
# the shepherd reruns the job instead of calling it a code defect -- and exits with the last status.
# CI_RETRY_SLEEP overrides the sleep command (tests).
set -u
[ $# -ge 4 ] && [ "$3" = "--" ] || { sed -n '2,3p' "$0" >&2; exit 2; }
attempts=$1
backoff=$2
shift 3
sleeper=${CI_RETRY_SLEEP:-sleep}
status=0
for ((i = 1; i <= attempts; i++)); do
  "$@" && exit 0
  status=$?
  echo "ci_retry: attempt $i/$attempts failed (exit $status): $*" >&2
  if [ "$i" -lt "$attempts" ]; then
    $sleeper "$backoff"
    backoff=$((backoff * 2))
  fi
done
echo "::error::INFRASTRUCTURE (not a code defect): '$*' failed after $attempts attempts (exit $status); re-run the job."
exit "$status"
