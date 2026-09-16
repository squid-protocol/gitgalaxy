#!/usr/bin/env python3
"""Record the cost of adding a language to GitGalaxy.

Appends one JSON line per language-addition effort to
``gitgalaxy/standards/language_addition_costs.jsonl`` — an append-only,
graphable ledger of wall-clock time, tokens, model mix, and estimated USD.

The heavy fields (duration, tokens, model mix, cost) are derived automatically
from a Claude Code session transcript (``~/.claude/projects/<slug>/<uuid>.jsonl``)
so the number is measured, not guessed. A ``--manual`` mode exists for entries
we only know roughly (e.g. a language added before this tool existed).

Token bases recorded (all of them — pick whichever you graph on):
  output_tokens      generated tokens; the most stable "work done" proxy
  fresh_tokens       input + cache_creation (net-new tokens the model read/wrote)
  cache_read_tokens  prompt-cache reads (cheap, but the bulk of throughput)
  total_tokens       fresh + output + cache_read (everything processed)

Cost is estimated from the per-model token split against the pricing table
below (USD / 1M tokens). Cache reads price at 0.1x input, cache writes at 1.25x.

Typical use, at the end of an addition (from the engine worktree):

    python tests/tools/record_language_cost.py \
        --lang nsalm --issue 2517 --phase combined \
        --session latest --primary-model fable-5 \
        --notes "assembler/positional family; reused hlasm comment gate"

`--session latest` picks the most recently modified transcript for THIS repo's
project slug. Pass an explicit uuid, a path, or repeat the flag to sum several
sessions into one record (engine + a separate corpus session).
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys

# USD per 1M tokens. input/output are list prices; cache_read ~= 0.1x input,
# cache_write ~= 1.25x input (5-minute TTL). Keep in sync with the claude-api
# skill's pricing table when models change.
PRICING = {
    "claude-fable-5": {"in": 10.0, "out": 50.0},
    "claude-mythos-5": {"in": 10.0, "out": 50.0},
    "claude-opus-4-8": {"in": 5.0, "out": 25.0},
    "claude-opus-4-7": {"in": 5.0, "out": 25.0},
    "claude-sonnet-5": {"in": 3.0, "out": 15.0},
    "claude-haiku-4-5": {"in": 1.0, "out": 5.0},
}
CACHE_READ_MULT = 0.1
CACHE_WRITE_MULT = 1.25

# Gaps longer than this (seconds) between transcript events are treated as the
# operator being away, not active work — so "active" time excludes idle.
IDLE_GAP_CAP = 300

LEDGER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "gitgalaxy",
    "standards",
    "language_addition_costs.jsonl",
)


def _model_key(m: str) -> str:
    """Normalize a transcript model id to a PRICING key; '' if unpriceable."""
    return m if m in PRICING else ""


def _cost_for(model: str, u: dict) -> float:
    p = PRICING.get(model)
    if not p:
        return 0.0
    return (
        u["inp"] / 1e6 * p["in"]
        + u["out"] / 1e6 * p["out"]
        + u["cw"] / 1e6 * (p["in"] * CACHE_WRITE_MULT)
        + u["cr"] / 1e6 * (p["in"] * CACHE_READ_MULT)
    )


def _project_slug_for_cwd() -> str:
    """Claude Code encodes the cwd as a project dir slug: / and _ -> -."""
    cwd = os.getcwd()
    return cwd.replace("/", "-").replace("_", "-")


def _resolve_sessions(specs, project_dir):
    """Turn --session values into transcript file paths."""
    paths = []
    for spec in specs:
        if spec == "latest":
            cands = sorted(
                glob.glob(os.path.join(project_dir, "*.jsonl")),
                key=os.path.getmtime,
                reverse=True,
            )
            if not cands:
                sys.exit(f"no transcripts under {project_dir}")
            paths.append(cands[0])
        elif os.path.sep in spec or spec.endswith(".jsonl"):
            paths.append(spec)
        else:  # bare uuid
            p = os.path.join(project_dir, spec + ".jsonl")
            if not os.path.exists(p):
                sys.exit(f"no transcript {p}")
            paths.append(p)
    return paths


def analyze(paths):
    """Sum tokens/time/model-mix/cost across one or more transcripts."""
    times = []
    per_model = {}
    for path in paths:
        with open(path) as fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                ts = o.get("timestamp")
                if ts:
                    times.append(dt.datetime.fromisoformat(ts.replace("Z", "+00:00")))
                msg = o.get("message")
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                model = msg.get("model")
                if not (usage and model):
                    continue
                d = per_model.setdefault(model, dict(inp=0, out=0, cw=0, cr=0))
                d["inp"] += usage.get("input_tokens", 0) or 0
                d["out"] += usage.get("output_tokens", 0) or 0
                d["cw"] += usage.get("cache_creation_input_tokens", 0) or 0
                d["cr"] += usage.get("cache_read_input_tokens", 0) or 0

    times.sort()
    elapsed = (times[-1] - times[0]).total_seconds() if len(times) > 1 else 0
    active = sum(min((b - a).total_seconds(), IDLE_GAP_CAP) for a, b in zip(times, times[1:]))

    agg = dict(input=0, output=0, cache_write=0, cache_read=0)
    cost = 0.0
    mix = {}
    for model, d in per_model.items():
        agg["input"] += d["inp"]
        agg["output"] += d["out"]
        agg["cache_write"] += d["cw"]
        agg["cache_read"] += d["cr"]
        cost += _cost_for(model, d)
        mix[model] = d["out"]  # assistant-message count proxy -> output tokens

    return dict(
        started_at=times[0].isoformat() if times else None,
        elapsed_min=round(elapsed / 60, 1),
        active_min=round(active / 60, 1),
        output_tokens=agg["output"],
        fresh_tokens=agg["input"] + agg["cache_write"],
        cache_read_tokens=agg["cache_read"],
        total_tokens=sum(agg.values()),
        est_cost_usd=round(cost, 2),
        model_output_split={k: v for k, v in sorted(mix.items(), key=lambda x: -x[1])},
        unpriced_models=sorted(m for m in per_model if not _model_key(m)),
    )


def report(ledger_path):
    """Print the ledger as a table + per-runner totals (for eyeballing / graphing)."""
    if not os.path.exists(ledger_path):
        sys.exit(f"no ledger at {ledger_path}")
    with open(ledger_path) as f:
        rows = [json.loads(l) for l in f if l.strip()]
    rows.sort(key=lambda r: r.get("started_at") or "")
    hdr = f"{'started':10} {'lang':9} {'phase':8} {'runner':11} {'active':>8} {'output':>9} {'est $':>9}"
    print(hdr)
    print("-" * len(hdr))
    by_runner = {}
    for r in rows:
        am = r.get("active_min")
        out = r.get("output_tokens")
        cost = r.get("est_cost_usd")
        print(
            f"{(r.get('started_at') or '')[:10]:10} {r['lang']:9} {r['phase']:8} "
            f"{r['runner']:11} {(str(am) + 'm' if am else '-'):>8} "
            f"{(f'{out:,}' if out else '-'):>9} {(f'${cost:,.0f}' if cost is not None else '-'):>9}"
        )
        acc = by_runner.setdefault(r["runner"], dict(n=0, cost=0.0, out=0, measured=0, costs=[], mins=[]))
        acc["n"] += 1
        if cost is not None:
            acc["cost"] += cost
            acc["out"] += out or 0
            acc["measured"] += 1
            if r.get("phase") == "combined":
                acc["costs"].append(cost)
                if am:
                    acc["mins"].append(am)
    print("\ntotals by runner (measured rows only; token bases NOT comparable across runners):")
    for runner, a in sorted(by_runner.items()):
        print(f"  {runner:11} {a['n']} rows ({a['measured']} measured)  output={a['out']:,}  est=${a['cost']:,.0f}")
    # The point of the ledger is a quotable cost for a NEW language: report the min-max
    # (and median) of full engine+corpus additions, per runner, as a forecast envelope.
    print("\npredicted envelope for a NEW language (combined rows only -- forecast within a runner):")
    printed = False
    for runner, a in sorted(by_runner.items()):
        cs = sorted(a["costs"])
        if not cs:
            continue
        printed = True
        med = cs[len(cs) // 2]
        span = f"${cs[0]:,.0f}-${cs[-1]:,.0f} (median ${med:,.0f})"
        if a["mins"]:
            ms = sorted(a["mins"])
            span += f", {ms[0]:.0f}-{ms[-1]:.0f} min"
        print(f"  {runner:11} n={len(cs)}  {span}")
    if not printed:
        print("  (no combined measured rows yet)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", action="store_true", help="print the ledger as a table + per-runner totals, then exit")
    ap.add_argument("--lang", help="language id, e.g. nsalm")
    ap.add_argument("--issue", help="tracking issue #, e.g. 2517")
    ap.add_argument(
        "--phase",
        default="combined",
        choices=["engine", "corpus", "combined"],
        help="engine PR, keyword-rosetta corpus PR, or both in one effort",
    )
    ap.add_argument(
        "--runner",
        default="claude-code",
        help="agent that did the work (claude-code, agy-gemini, ...). "
        "Token bases are NOT comparable across runners: Claude Code "
        "totals are cache-read-inflated; a headless Gemini run is not.",
    )
    ap.add_argument(
        "--session", action="append", default=[], help="'latest', a session uuid, or a transcript path; repeatable"
    )
    ap.add_argument("--primary-model", default="", help="model that did most of the judgment work (freeform label)")
    ap.add_argument("--notes", default="", help="one-line context")
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--dry-run", action="store_true", help="print, don't append")

    # --manual: record an effort we only know roughly (no transcript).
    ap.add_argument("--manual", action="store_true", help="skip transcript parsing; take numbers from the flags below")
    ap.add_argument("--active-min", type=float)
    ap.add_argument("--output-tokens", type=int)
    ap.add_argument("--total-tokens", type=int)
    ap.add_argument("--est-cost-usd", type=float)
    ap.add_argument("--started-at", help="ISO date/time this effort began")
    args = ap.parse_args()

    if args.report:
        report(args.ledger)
        return
    if not (args.lang and args.issue):
        ap.error("--lang and --issue are required (unless --report)")

    if args.manual:
        derived = dict(
            started_at=args.started_at,
            elapsed_min=None,
            active_min=args.active_min,
            output_tokens=args.output_tokens,
            fresh_tokens=None,
            cache_read_tokens=None,
            total_tokens=args.total_tokens,
            est_cost_usd=args.est_cost_usd,
            model_output_split={},
            unpriced_models=[],
            estimate=True,
        )
    else:
        if not args.session:
            args.session = ["latest"]
        project_dir = os.path.join(os.path.expanduser("~/.claude/projects"), _project_slug_for_cwd())
        paths = _resolve_sessions(args.session, project_dir)
        derived = analyze(paths)
        derived["estimate"] = False
        derived["sessions"] = [os.path.basename(p) for p in paths]

    record = dict(
        recorded_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        lang=args.lang,
        issue=str(args.issue),
        phase=args.phase,
        runner=args.runner,
        primary_model=args.primary_model,
        notes=args.notes,
        **derived,
    )

    line = json.dumps(record, separators=(",", ":"))
    if args.dry_run:
        print(json.dumps(record, indent=2))
        return
    os.makedirs(os.path.dirname(args.ledger), exist_ok=True)
    with open(args.ledger, "a") as fh:
        fh.write(line + "\n")
    print(f"appended {args.lang} #{args.issue} ({args.phase}) -> {args.ledger}")
    print(
        f"  active={derived.get('active_min')}min  "
        f"output={derived.get('output_tokens')}  "
        f"est=${derived.get('est_cost_usd')}"
    )


if __name__ == "__main__":
    main()
