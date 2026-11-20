#!/usr/bin/env bash
# ci_retry.sh <attempts> <backoff-seconds> -- <cmd...>   (#5048)
# Run a network-flaky CI step (apt, npm, docker pull) up to <attempts> times, sleeping backoff, 2*backoff, ... between
# tries. When every try fails it prints an INFRASTRUCTURE marker -- tests/tools/ci_digest.py INFRA_LOG matches it, so
# the shepherd reruns the job instead of calling it a code defect -- and exits with the last status.
# CI_RETRY_SLEEP overrides the sleep command (tests).
# CI_RETRY_CACHED=<shell command>: a cache probe run first; when it succeeds the fetch is skipped (cache first).
# On the final failure the last output line of the failing command is printed as `ci_retry: cause: ...`.
set -u
[ $# -ge 4 ] && [ "$3" = "--" ] || { sed -n '2,3p' "$0" >&2; exit 2; }
attempts=$1
backoff=$2
shift 3
sleeper=${CI_RETRY_SLEEP:-sleep}
status=0
# No explicit probe: a digest-pinned `docker pull` is content-addressed, so a local image under that ref is exact.
# A tag-only ref is never inferred (a stale local tag would be accepted).
if [ -z "${CI_RETRY_CACHED:-}" ] && [ "$1" = "docker" ] && [ "${2:-}" = "pull" ]; then
  for arg in "${@:3}"; do
    case "$arg" in
      -*) ;;
      *@sha256:*) CI_RETRY_CACHED="docker image inspect '$arg'" ;;
    esac
  done
fi
if [ -n "${CI_RETRY_CACHED:-}" ] && bash -c "$CI_RETRY_CACHED" > /dev/null 2>&1; then
  echo "ci_retry: cache hit, skipping: $*" >&2
  exit 0
fi
log=$(mktemp)
trap 'rm -f "$log"' EXIT
for ((i = 1; i <= attempts; i++)); do
  "$@" 2>&1 | tee "$log"
  status=${PIPESTATUS[0]}
  [ "$status" -eq 0 ] && exit 0
  echo "ci_retry: attempt $i/$attempts failed (exit $status): $*" >&2
  if [ "$i" -lt "$attempts" ]; then
    $sleeper "$backoff"
    backoff=$((backoff * 2))
  fi
done
cause=$(grep -v '^[[:space:]]*$' "$log" | tail -n 1 | cut -c1-300)
echo "ci_retry: cause: ${cause:-no output}"
echo "::error::INFRASTRUCTURE (not a code defect): '$*' failed after $attempts attempts (exit $status); re-run the job."
exit "$status"
