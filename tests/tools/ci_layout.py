#!/usr/bin/env python3
"""The layout of the Mainframe Ground Truth jobs, chosen by CI queue depth and the scan cache (the `plan` job of
mainframe-ground-truth.yml, #5543).

    python3 tests/tools/ci_layout.py --event pull_request --mode full --cache-hit false \
        [--waiting N] [--busy-above 8] [--github-output PATH] [--summary PATH]     # env: GH_TOKEN, GITHUB_REPOSITORY

  calm   4 parts; a push, the nightly and a manual run also run a warm job (fetch, parallel scans, the ledger gate) whose
         scans the parts unpack and main saves. A pull request has no warm job: on a cache miss its parts warm for
         themselves (one fewer serial queue wait and runner). A cache hit on the scans (corpora.json + engine state, saved on main) skips the warm
         job: the parts restore the scans and part 1 runs the (cheap) gate.
  busy   2 parts and no warm job, each part warming its own scans (the pre-#5559 layout): fewer runners and fewer serial
         queue waits when PR jobs are waiting for one. Pull requests only: a push, the nightly and a manual run are
         always calm (they save the scans and append the history).

"Busy" is the signal of post_merge_dispatch.waiting_pr_jobs (queued PR runs plus queued jobs of running PR runs) above
BUSY_ABOVE. A signal that cannot be read is calm (the layout the workflow had before). The choice and why go to the job
summary, so timings and the per-test time ratchet can be split by layout. Stdlib only: the plan job installs nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

CALM_PARTS = 4
BUSY_PARTS = 2
BUSY_ABOVE = 8  # queued PR jobs; the box-wide pool is about 20 concurrent jobs and a calm run needs 5 runners


def choose(event: str, mode: str, cache_hit: bool, waiting: int | None, busy_above: int = BUSY_ABOVE) -> dict:
    """The layout: `warm` (a warm job runs), `parts`, and `gate_in_part` (part 1 runs the ledger gate, no warm job)."""
    if mode == "none":
        return {
            "layout": "none",
            "reason": "plan mode none: nothing runs",
            "warm": False,
            "parts": 0,
            "gate_in_part": False,
        }
    if event != "pull_request":
        why = f"{event}: always calm (it saves the scans and appends the history)"
    elif waiting is None:
        why = "queue depth unreadable: calm"
    elif waiting > busy_above:
        return {
            "layout": "busy",
            "reason": f"{waiting} PR jobs waiting for a runner (> {busy_above}): 2 self-warming parts",
            "warm": False,
            "parts": BUSY_PARTS,
            "gate_in_part": True,
        }
    else:
        why = f"{waiting} PR jobs waiting for a runner (<= {busy_above}): calm"
    # A pull request on a cache miss skips the warm job too: it would be a fourth serial queue wait and a fifth runner
    # request; the 4 parts scan for themselves. Push / nightly / manual runs keep it: it saves the scans cache.
    warm = not cache_hit and event != "pull_request"
    if cache_hit:
        how = "the scans are cached: no warm job"
    elif warm:
        how = "no cached scans: warm job + 4 parts (it saves the scans cache)"
    else:
        how = "no cached scans: no warm job (a serial queue wait), 4 self-warming parts"
    return {
        "layout": "calm",
        "reason": why + "; " + how,
        "warm": warm,
        "parts": CALM_PARTS,
        "gate_in_part": not warm,
    }


def matrix(parts: int) -> dict:
    return {"include": [{"group": g, "parts": parts, "shard": f"{g}/{parts}"} for g in range(1, parts + 1)]}


def waiting_now() -> int | None:
    try:
        import post_merge_dispatch as pmd

        return pmd.waiting_pr_jobs(os.environ["GITHUB_REPOSITORY"])
    except Exception as exc:  # noqa: BLE001 - any failure to read the queue means calm, never a failed plan
        print(f"cannot read the CI queue: {exc}", file=sys.stderr)
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", default="pull_request")
    ap.add_argument("--mode", default="full", help="the plan mode (none|full)")
    ap.add_argument("--cache-hit", default="false", help="true when the scans cache has this key")
    ap.add_argument("--waiting", type=int, help="queued PR jobs, instead of asking the GitHub API")
    ap.add_argument("--busy-above", type=int, default=BUSY_ABOVE)
    ap.add_argument("--github-output", type=Path)
    ap.add_argument("--summary", type=Path)
    ap.add_argument(
        "--print-waiting", action="store_true", help="#5919: print the queued PR jobs (empty when unreadable)"
    )
    args = ap.parse_args()
    if args.print_waiting:  # for a workflow step that hands the count to another planner; always exits 0
        n = waiting_now()
        print("" if n is None else n)
        return 0
    waiting = args.waiting
    if waiting is None and args.event == "pull_request" and args.mode != "none":
        waiting = waiting_now()
    hit = args.cache_hit == "true"
    lay = choose(args.event, args.mode, hit, waiting, args.busy_above)
    print(json.dumps({**lay, "waiting": waiting, "cache_hit": hit}, indent=1))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"layout={lay['layout']}\nwarm={str(lay['warm']).lower()}\nparts={lay['parts']}\n")
            fh.write(f"cache_hit={str(hit).lower()}\nmatrix={json.dumps(matrix(lay['parts'] or CALM_PARTS))}\n")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as fh:
            fh.write(f"## Ground-truth layout: {lay['layout']}\n\n{lay['reason']}\n\n")
            fh.write("| warm job | parts | gate in part 1 | scans cached | PR jobs waiting |\n|---|---|---|---|---|\n")
            fh.write(f"| {lay['warm']} | {lay['parts']} | {lay['gate_in_part']} | {hit} | {waiting} |\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
