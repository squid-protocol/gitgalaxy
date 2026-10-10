"""
#4317 phase 5: the estate-crucible scorer as a ratchet.

    python tests/tools/estate_crucible_gate.py [--crucible PATH] [--update-baseline] [--md out.md]

Scans the pinned estate-crucible with this checkout's engine (tests/tools/estate_crucible.py), then
compares the score with the committed baseline, tests/estate_crucible/baseline.json. The run FAILS on
any regression:

  - a horror that passed in the baseline and does not now,
  - a channel whose pass count dropped (or whose fail / missing / phantom count grew),
  - a check that passed in the baseline and does not now (this also catches a fact lost inside a
    channel while another gains one),
  - a baseline recorded against a different PINNED_REF (re-baseline with the pin bump).

Improvements never fail the run; they are listed, and the baseline is lowered by re-running with
--update-baseline (commit the result). The baseline stores the per-horror verdicts, the channel table
and the NOT-passing checks only, so it stays a few KB and a diff shows exactly what moved.
Only a scan of the pinned crucible is accepted for --update-baseline.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import estate_crucible as ec  # noqa: E402
from _estate_crucible_pin import PINNED_REF  # noqa: E402

BASELINE = ec.TESTS / "estate_crucible" / "baseline.json"
FORMAT = "estate-crucible-baseline/1"
BAD = ("fail", "missing", "phantom")


def check_id(c: Any) -> str:
    return f"{c.channel}|{c.member}|{c.fact}"


def snapshot(sc: Any, crucible: Path) -> dict[str, Any]:
    horrors = {h["id"]: h["verdict"] for h in ec.horror_verdicts(sc, crucible)}
    # one entry per check id; if an id repeats, the worst status is the one that counts
    rank = {"pass": 0, "unscored": 1, "phantom": 2, "missing": 3, "fail": 4}
    status: dict[str, str] = {}
    for c in sc.checks:
        k = check_id(c)
        if k not in status or rank[c.status] > rank[status[k]]:
            status[k] = c.status
    return {
        "format": FORMAT,
        "pinned_ref": PINNED_REF,
        "key_generator": sc.key_generator,
        "horrors": horrors,
        "channels": ec.channel_table(sc),
        "not_passing": dict(sorted((k, s) for k, s in status.items() if s != "pass")),
        "checks_total": len(status),
    }


def compare(base: dict[str, Any], now: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(regressions, improvements)."""
    bad: list[str] = []
    good: list[str] = []
    if base.get("pinned_ref") != now["pinned_ref"]:
        bad.append(
            f"baseline was measured against {base.get('pinned_ref')} but PINNED_REF is {now['pinned_ref']}: "
            "re-baseline with the pin bump (--update-baseline) and review the diff"
        )
    for h, verdict in sorted(base["horrors"].items()):
        cur = now["horrors"].get(h)
        if verdict == "PASS" and cur != "PASS":
            bad.append(f"horror {h}: PASS -> {cur or 'absent'}")
        elif verdict != "PASS" and cur == "PASS":
            good.append(f"horror {h}: {verdict} -> PASS")
    for h in sorted(set(now["horrors"]) - set(base["horrors"])):
        if now["horrors"][h] != "PASS":
            bad.append(f"horror {h}: new and {now['horrors'][h]}")
    for ch, b in base["channels"].items():
        n = now["channels"].get(ch)
        if n is None:
            bad.append(f"channel {ch}: gone")
            continue
        if n["pass"] < b["pass"]:
            bad.append(f"channel {ch}: pass {b['pass']} -> {n['pass']}")
        elif n["pass"] > b["pass"]:
            good.append(f"channel {ch}: pass {b['pass']} -> {n['pass']}")
        for s in BAD:
            if n[s] > b[s]:
                bad.append(f"channel {ch}: {s} {b[s]} -> {n[s]}")
    for k, s in sorted(now["not_passing"].items()):
        if k not in base["not_passing"] and s in BAD:
            bad.append(f"check no longer passes: {s} {k}")
    for k in sorted(set(base["not_passing"]) - set(now["not_passing"])):
        good.append(f"check now passes: {k}")
    return bad, good


def report(base: dict[str, Any] | None, now: dict[str, Any], bad: list[str], good: list[str]) -> str:
    passed = sum(1 for v in now["horrors"].values() if v == "PASS")
    out = [f"### estate-crucible gate ({now['pinned_ref']}): horrors {passed}/{len(now['horrors'])}", ""]
    out += ["| channel | pass | fail | missing | phantom | unscored | baseline pass |", "|---|--:|--:|--:|--:|--:|--:|"]
    for ch, n in now["channels"].items():
        bp = base["channels"].get(ch, {}).get("pass", "-") if base else "-"
        out.append(f"| {ch} | " + " | ".join(str(n[s]) for s in ec.STATUSES) + f" | {bp} |")
    out += ["", f"**Regressions: {len(bad)}**"] + [f"- {m}" for m in bad]
    if good:
        out += [
            "",
            f"**Improvements: {len(good)}** (lower the baseline: `python tests/tools/estate_crucible_gate.py --update-baseline`)",
        ]
        out += [f"- {m}" for m in good]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--crucible", type=Path, help=f"estate-crucible checkout (default ${ec.PATH_ENV} or ../estate-crucible)"
    )
    ap.add_argument("--baseline", type=Path, default=BASELINE)
    ap.add_argument("--update-baseline", action="store_true", help="write the current score as the baseline")
    ap.add_argument("--md", type=Path, help="write the markdown report here")
    args = ap.parse_args(argv)

    crucible = ec.crucible_path(args.crucible)
    if not (crucible / "key" / "manifest.json").is_file():
        print(f"no estate-crucible checkout at {crucible} (set {ec.PATH_ENV} or pass --crucible)", file=sys.stderr)
        return 2
    msg = ec.pin_mismatch(crucible)
    if msg:
        print(msg, file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="estate-gate-") as tmp:
        sc = ec.score(crucible, ec.scan(crucible, Path(tmp)))
    now = snapshot(sc, crucible)
    passed = sum(1 for v in now["horrors"].values() if v == "PASS")

    if args.update_baseline:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(now, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"baseline written: {args.baseline} (horrors {passed}/{len(now['horrors'])})")
        return 0

    if not args.baseline.is_file():
        print(f"no baseline at {args.baseline}: run with --update-baseline", file=sys.stderr)
        return 2
    base = json.loads(args.baseline.read_text(encoding="utf-8"))
    bad, good = compare(base, now)
    text = report(base, now, bad, good)
    print(text, end="")
    if args.md:
        args.md.write_text(text, encoding="utf-8")
    if bad:
        print(f"FAIL: {len(bad)} regression(s) against {args.baseline.name}", file=sys.stderr)
        return 1
    print(f"OK: horrors {passed}/{len(now['horrors'])}, no regression against {args.baseline.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
