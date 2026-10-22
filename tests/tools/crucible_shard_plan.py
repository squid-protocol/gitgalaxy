#!/usr/bin/env python3
"""Shard counts and job timeouts for the CICS Crucible and DOOM-rosetta workflows (#5919 slice 2), from measured
weights through ci_shard_plan. Stdlib only: a plan job runs before anything is installed.

    --cics DIR   the cics-crucible checkout: its cases weigh CASE_SECONDS; emits `matrix` ({"include": [{shard, total}]})
                 and `timeout` (minutes of a measure job)
    --doom       tests/doom_rosetta/manifest.csv + the goldens' own per-file LOC; emits `matrix` (LOC-balanced shards,
                 each with its ports) and `timeout`

Neither workflow types a shard count or a shard timeout: adding cases (or ports) moves the plan, not the YAML. The model
constants below were calibrated so today's inputs reproduce today's counts (CICS 2 shards, DOOM 4).
"""

from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_shard_plan as sp  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

# Measured seconds of each CICS Crucible case on a CI runner (one at a time, #5498); a case missing here weighs the
# median of these (ci_shard_plan.weights) and is placed with DEFAULT_CASE_SECONDS by cics_crucible.shard_plan.
CASE_SECONDS = {
    "ca-address-commarea": 21, "ca-address-eib-commarea": 20, "ca-address-twa-tctua": 19, "ca-channel-containers": 22,
    "ca-container-byteoffset": 21, "ca-container-ccsid": 20, "ca-get-container-set": 21, "ca-getmain-pointer": 21,
    "ca-link-lengths": 50, "ca-receive-retrieve-set": 20, "ca-xctl-versions": 50, "gt-assign-startcode": 21,
    "gt-http-inbound": 19, "gt-send-text-terminal": 21, "gt-start-options": 22, "gt-start-retrieve": 51,
    "gt-terminal-coalesce": 49, "gt-urimap-browse": 21, "gt-web-parse-url": 21, "hc-abend-link": 49,
    "hc-counter-increment-wrap": 21, "hc-counter-shared-namespace": 21, "hc-dcounters": 21, "hc-deedit-uctranst": 21,
    "hc-eoc-error": 21, "hc-file-read-set": 20, "hc-file-unlock": 21, "hc-handle-aid": 21, "hc-ignore-error": 22,
    "hc-inquire-deleteq": 22, "hc-map-not-in-mapset": 21, "hc-named-counters": 22, "hc-perform-range": 48,
    "hc-readq-td": 21, "hc-resp-options": 21, "hc-terminal-eoc": 20, "hc-terminal-receive": 20, "hx-attr-bytes": 48,
    "hx-extended-cursor": 49, "pc-aid-menu": 51, "pc-return-channel": 20, "pc-return-immediate": 51, "pc-wizard": 53,
}  # fmt: skip
DEFAULT_CASE_SECONDS = 21

# CICS Crucible: a measure job starts a runner, installs, builds the GnuCOBOL image and warms Maven (CICS_SETUP_S), then
# measures --jobs 4 cases at once; four cases share the container and Maven, so the speed-up over one at a time is
# about CICS_JOBS, not 4.
CICS_SETUP_S = 300
CICS_JOBS = 2
CICS_TARGET_S = 11 * 60
CICS_MAX_SHARDS = 4  # this workflow's share of the 20-job pool
CICS_TIMEOUT_FLOOR, CICS_TIMEOUT_CEILING = 20, 30  # minutes

# DOOM-rosetta: the 44 ports are ~6.7M LOC and 7.5 min serial (~15k LOC/s). A shard checks out, installs and fetches
# its clones (DOOM_SETUP_S) before it scans.
DOOM_LOC_PER_S = 15000
DOOM_SETUP_S = 420
DOOM_TARGET_S = 9 * 60
DOOM_MAX_SHARDS = 6
DOOM_TIMEOUT_FLOOR, DOOM_TIMEOUT_CEILING = 20, 30


def cics_plan(case_ids: list[str], waiting: int | None = None) -> dict:
    """{"matrix": {"include": [{"shard": i, "total": N}]}, "timeout": minutes, "shards": N} for the cases."""
    w, missing = sp.weights(case_ids, CASE_SECONDS)
    sp.check_measured(missing, len(w))
    cap = sp.pool_cap(CICS_MAX_SHARDS, waiting)
    n = max(1, sp.shards_for(w, CICS_SETUP_S, CICS_JOBS, CICS_TARGET_S, cap))
    t = sp.timeout_minutes(w, n, CICS_SETUP_S, CICS_JOBS, CICS_TIMEOUT_FLOOR, CICS_TIMEOUT_CEILING)
    return {"matrix": {"include": [{"shard": i, "total": n} for i in range(1, n + 1)]}, "timeout": t, "shards": n}


def pack(weight: dict[str, float], n: int) -> list[list[str]]:
    """Ports into n shards, heaviest first into the lightest (ties by name): deterministic."""
    bins: list[tuple[float, list[str]]] = [(0.0, []) for _ in range(n)]
    for name in sorted(weight, key=lambda p: (-weight[p], p)):
        k = min(range(n), key=lambda j: (bins[j][0], j))
        bins[k] = (bins[k][0] + weight[name], [*bins[k][1], name])
    return [sorted(b[1]) for b in bins]


def doom_plan(loc: dict[str, int], ports: list[str], waiting: int | None = None) -> dict:
    """The DOOM-rosetta matrix: `loc` is each golden's LOC, `ports` the manifest's names."""
    known = {p: float(loc[p]) / DOOM_LOC_PER_S for p in ports if p in loc}
    w, missing = sp.weights(ports, known)
    sp.check_measured(missing, len(w), "port")
    cap = sp.pool_cap(DOOM_MAX_SHARDS, waiting)
    n = max(1, sp.shards_for(w, DOOM_SETUP_S, 1, DOOM_TARGET_S, cap))
    t = sp.timeout_minutes(w, n, DOOM_SETUP_S, 1, DOOM_TIMEOUT_FLOOR, DOOM_TIMEOUT_CEILING)
    # LOC-balanced as before: unmeasured ports weigh the median in LOC terms too
    by_loc = {p: w[p] * DOOM_LOC_PER_S for p in w}
    include = [
        {"shard": i + 1, "ports": ",".join(b), "loc": round(sum(by_loc[p] for p in b))}
        for i, b in enumerate(pack(by_loc, n))
    ]
    return {"matrix": {"include": include}, "timeout": t, "shards": n}


def golden_loc(golden_dir: Path) -> dict[str, int]:
    """{port: LOC} from the goldens' own per-file rows."""
    out = {}
    for path in glob.glob(str(golden_dir / "*.json.gz")):
        with gzip.open(path, "rt") as fh:
            files = json.load(fh)["files"]
        out[os.path.basename(path).removesuffix(".json.gz")] = sum(v[1] for v in files.values())
    return out


def manifest_ports(manifest: Path) -> list[str]:
    with open(manifest, newline="") as fh:
        return [r["name"] for r in csv.DictReader(fh)]


def case_ids(crucible: Path) -> list[str]:
    """Every case directory id under a crucible checkout (cases/<trap>/<case-id>/case.json), as cc.discover finds them."""
    return sorted(p.parent.name for p in Path(crucible).glob("cases/*/*/case.json"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    what = ap.add_mutually_exclusive_group(required=True)
    what.add_argument("--cics", type=Path, metavar="DIR", help="the cics-crucible checkout")
    what.add_argument("--doom", action="store_true", help="the DOOM-rosetta manifest and goldens")
    ap.add_argument("--waiting", type=int, help="queued PR jobs (halves the shard cap past ci_shard_plan.BUSY_ABOVE)")
    ap.add_argument("--root", type=Path, default=REPO_ROOT, help="the checkout holding tests/ (doom)")
    args = ap.parse_args(argv)
    try:
        if args.cics:
            p = cics_plan(case_ids(args.cics), args.waiting)
        else:
            tests = args.root / "tests"
            p = doom_plan(
                golden_loc(tests / "golden_doom_rosetta"),
                manifest_ports(tests / "doom_rosetta" / "manifest.csv"),
                args.waiting,
            )
    except sp.PlanError as e:
        print(f"::error::{e}", file=sys.stderr)
        return 1
    print("matrix=" + json.dumps(p["matrix"]))
    print(f"timeout={p['timeout']}")
    print(f"plan: {p['shards']} shard(s), {p['timeout']} min", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
