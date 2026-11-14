#!/usr/bin/env bash
# mvs38j.sh <image|tapes|stage|dasd STAGE|sysgen starter|smp1|smp2|stage1|start|run DECK|stop|status> -- the MVS 3.8J box for the JCL oracle tier 2 (#8414).
# Internal use only until counsel answers Q16. Never z/OS; never TK4-/TK5: the system is built from IBM's
# distribution tapes (Jay Moseley's sysgen). Nothing here is committed or run in CI; the work dir holds the
# system image and stays outside the repo. Heavy steps take a slot:  tests/tools/box/heavy-run.sh mvs38j.sh image
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${MVS38J_WORK:-/srv/storage_16tb/projects/gitgalaxy/mvs38j}
IMAGE=${MVS38J_IMAGE:-gitgalaxy-mvs38j-hyperion}
NAME=${MVS38J_NAME:-gg-mvs38j}
BASE=https://www.jaymoseley.com/hercules/downloads/archives
# archive, md5 as published on jaymoseley.com/hercules/installMVS/iPREREQv8.htm (checked 2026-11-13)
TAPES=(
  "vs2StarterTapes.tar.gz 7c12c99c387193c8650f8ef78b4771c3"
  "vs2DistributionTapes.tar.gz ec9f1c8672bd406a4ff7bc00f139f5bc"
  "mvsInstallationResources.tar.gz 129898e0f0881078448358553bc6b4c1"
)
usage() { sed -n '2,6p' "$0" >&2; exit 2; }
[ $# -ge 1 ] || usage
case "$1" in
  image)
    docker build -t "$IMAGE" "$HERE" ;;
  tapes)
    # each archive goes in its own empty dir under $WORK/dl; downloaded files are untrusted data (never executed here)
    for t in "${TAPES[@]}"; do
      read -r f md5 <<<"$t"; d="$WORK/dl/${f%.tar.gz}"
      mkdir -p "$d"
      [ -f "$d/$f" ] || curl -fsSL -o "$d/$f" "$BASE/$f"
      echo "$md5  $d/$f" | md5sum -c - || { rm -f "$d/$f"; exit 1; }
      [ -d "$d/x" ] || { mkdir "$d/x"; tar -xzf "$d/$f" -C "$d/x"; }
    done ;;
  stage)
    # lay the three unpacked archives out the way Jay Moseley's configs expect (conf/ jcl/ tape/ sajobs/ dasd/, paths
    # relative to $WORK). Idempotent; the tapes are copied, never moved, so `tapes` stays the verified source.
    R="$WORK/dl/mvsInstallationResources/x"
    [ -d "$R" ] && [ -d "$WORK/dl/vs2StarterTapes/x" ] && [ -d "$WORK/dl/vs2DistributionTapes/x" ] \
      || { echo "run '$0 tapes' first" >&2; exit 1; }
    mkdir -p "$WORK/dasd" "$WORK/tape"
    cp -a "$R/conf" "$R/jcl" "$R/sajobs" "$R/create.dasd.sh" "$R/submit.sh" "$R/stage2.rexx" "$R/stage2.awk" "$R/condcode.rexx" "$WORK/"
    cp -a "$R"/tape/*.het "$WORK/dl/vs2StarterTapes/x/tape/"*.het "$WORK/dl/vs2DistributionTapes/x/tape/"*.het "$WORK/tape/"
    echo "staged into $WORK" ;;
  dasd)
    # create one stage's empty DASD volumes with the image's dasdinit, answering "n" to the compression prompt
    [ $# -eq 2 ] || { echo "usage: $0 dasd starter|dlibs|sysgen|user" >&2; exit 2; }
    case "$2" in starter | dlibs | sysgen | user) ;; *) echo "unknown stage: $2" >&2; exit 2 ;; esac
    [ -f "$WORK/create.dasd.sh" ] || { echo "run '$0 stage' first" >&2; exit 1; }
    echo n | docker run --rm -i --name "${NAME}-dasd" --user "$(id -u):$(id -g)" -v "$WORK:/mvs" -w /mvs \
      --entrypoint sh "$IMAGE" ./create.dasd.sh "$2" ;;
  sysgen)
    # Jay Moseley's sysgen is a staged console procedure (starter system -> stage 1 -> stage 2 -> user mods), driven
    # by sysgen.py over Hercules' console. Only `starter` is automated so far (docs/jcl_oracle_mvs38j.md).
    case "${2:-}" in starter | smp1 | smp2 | stage1) ;; *) echo "mvs38j.sh sysgen: only 'sysgen starter|smp1|smp2|stage1' are automated so far; see docs/jcl_oracle_mvs38j.md" >&2; exit 3 ;; esac
    stage=$2; shift 2
    MVS38J_WORK="$WORK" MVS38J_IMAGE="$IMAGE" MVS38J_NAME="$NAME" exec python3 -I "$HERE/sysgen.py" "$stage" "$@" ;;
  start)
    [ -f "$WORK/conf/mvs.conf" ] || { echo "no $WORK/conf/mvs.conf: generate the system first" >&2; exit 1; }
    # the card reader is a socket device on the loopback only; jobs are submitted through it
    docker run -d --rm --name "$NAME" -p 127.0.0.1:3505:3505 -p 127.0.0.1:3270:3270 -v "$WORK:/mvs" "$IMAGE" ;;
  run)
    # submit one JCL deck through the card reader of a started box and print the parsed JES2 job log as JSON
    # (runner.py, provenance mvs38j-run). The printer file defaults to the first 1403 of conf/mvs.conf.
    [ $# -ge 2 ] || { echo "usage: $0 run DECK [runner.py submit options]" >&2; exit 2; }
    deck=$2; shift 2
    [ -f "$deck" ] || { echo "no deck: $deck" >&2; exit 1; }
    case " $* " in
      *" --printer "*) ;;
      *)
        [ -f "$WORK/conf/mvs.conf" ] || { echo "no $WORK/conf/mvs.conf: generate the system first" >&2; exit 1; }
        prt=$(awk 'tolower($2) == "1403" { print $3; exit }' "$WORK/conf/mvs.conf")
        [ -n "$prt" ] || { echo "no 1403 printer in $WORK/conf/mvs.conf" >&2; exit 1; }
        set -- --printer "$WORK/$prt" "$@" ;;
    esac
    exec python3 -I "$HERE/runner.py" submit "$deck" "$@" ;;
  stop)
    docker stop "$NAME" ;;
  status)
    docker ps --filter "name=$NAME" --format '{{.Names}} {{.Status}}'
    for t in "${TAPES[@]}"; do read -r f _ <<<"$t"; [ -f "$WORK/dl/${f%.tar.gz}/$f" ] && echo "tape ok: $f" || echo "tape missing: $f"; done ;;
  *) usage ;;
esac
