"""One command for every table of docs/research/doom-port-study.md (#5620): measurements read from the scans.

Reads the scans and clones ``doom_speedrun.py run --oracle`` leaves under ``<work>`` and runs the study tools over them
(``lineage``, ``distribution``, ``fidelity``, ``doom_diff``), then fills the marked blocks of the write-up. Licensed
ports only: a port outside ``lineage.LICENSED`` is never read or printed.

    python tests/tools/doom_speedrun/study_report.py --work DIR --write     # regenerate the tables in the doc
    python tests/tools/doom_speedrun/study_report.py --work DIR --check     # rc 1 when the doc's tables are stale
    python tests/tools/doom_speedrun/study_report.py --work DIR              # print the tables

The call-graph ("subway") tables come from ``sfs compare ... --subway-reference linuxdoom`` in
squid-protocol/gitgalaxy-population-analyses; pass its ``subway.csv`` as ``--subway`` and they are filtered to the
licensed ports (without it the block says so).
"""

import argparse
import collections
import csv
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))  # before any gitgalaxy import: a shared venv may editable-install another checkout
sys.path.insert(0, str(HERE))

import distribution  # noqa: E402
import doom_diff  # noqa: E402
import doom_speedrun  # noqa: E402
import fidelity  # noqa: E402
import lineage  # noqa: E402
import subsystem_distribution  # noqa: E402

DOC = REPO_ROOT / "docs" / "research" / "doom-port-study.md"
BEGIN, END = "<!-- study:{} begin -->", "<!-- study:{} end -->"
BLOCKS = ("clean-scan", "fidelity", "lineage", "distribution", "subsystem", "landmarks", "subway")
# The study's faithful translations (the manifest's own lineage text says so): the calibration question is asked of these.
TRANSLATIONS = ("managed-doom", "dartdoom", "kocoa-doom", "mochadoom", "doom-scheme", "doomf77", "gore")


def _md(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def _checks(row):
    return row.get("fails") or "-" if row else "n/a"


def _cell(row, key, empty="-"):
    return (row or {}).get(key) or empty


def clean_scan_block(rows, before, after):
    """Per port: failed checks, files seen, misses and the function-count agreement with ctags, round 2 and now."""
    body = []
    for r in rows:
        n = r["name"]
        b, a = before.get(n), after.get(n)
        if a is None:
            continue
        files = a.get("first_party_src", "")
        body.append([
            n, _checks(b), _checks(a), f"{files} (vacuous)" if files == "0" else files,
            _cell(b, "missed_src", "n/a"), a.get("missed_src", ""),
            _cell(b, "func_delta_pct", "n/a"), _cell(a, "func_delta_pct", "not compared"), _cell(a, "gg_functions"),
        ])  # fmt: skip
    perfect = sum(1 for r in rows if (after.get(r["name"]) or {}).get("fails") == "")
    gained = sum(
        1
        for r in rows
        if (before.get(r["name"]) or {}).get("fails") and (after.get(r["name"]) or {}).get("fails") == ""
    )
    head = (
        f"{perfect} of {len(body)} ports pass every scored check now; {gained} of them failed at least one in round 2 "
        f"(`n/a` = the port was added after round 2; `(vacuous)` = the scorer saw no first-party source files, so the "
        f"pass proves nothing; `not compared` = ctags has no reading of that language). The call-graph check did not "
        f"exist in round 2.\n\n"
    )
    return head + _md(
        ["port", "failed checks, round 2", "failed checks, now", "first-party files, now", "missed files, round 2", "now",
         "functions vs ctags %, round 2", "now", "functions now"],
        body,
    )  # fmt: skip


def lineage_block(out, rows):
    cls = {r["name"]: r["class"] for r in rows}
    fid = {r["name"]: r.get("fidelity") or "unstated" for r in rows}
    summary = sorted(out["survival.csv"], key=lambda r: -float(r["pct_name"]))
    return _md(
        ["port", "class", "stated fidelity", "parent", "name %", "exact %", "near %", "derived %", "exact vs parent"],
        [[r["variant"], cls[r["variant"]], fid[r["variant"]], r["parent"] or "-", r["pct_name"], r["pct_exact_body"],
          r["pct_near_ge_0_9"], r["pct_derived_ge_0_6"], r["exact_vs_parent"] if r["exact_vs_parent"] != "" else "-"]
         for r in summary],
    )  # fmt: skip


def distribution_block(summary, fid):
    ports = sorted(summary, key=lambda p: summary[p]["dist"])
    table = _md(
        ["port", "language", "stated fidelity", "functions", "complexity med", "% complexity >= 10", "LOC med", "dist"],
        [[p, summary[p]["lang"], fid.get(p, "unstated"), summary[p]["n"], f"{summary[p]['complexity_med']:.0f}",
          f"{summary[p]['cx10']:.1f}", f"{summary[p]['loc_med']:.0f}", f"{summary[p]['dist']:.2f}"] for p in ports],
    )  # fmt: skip
    pct = distribution.base_percentiles(summary)
    place = _md(
        ["metric", "linuxdoom median", "population median", "IQR of port medians", "linuxdoom percentile"],
        [[f, f"{r['linuxdoom']:.1f}", f"{r['population_median']:.1f}", f"{r['q1']:.1f} - {r['q3']:.1f}",
          r["linuxdoom_percentile"]] for f, r in pct.items()],
    )  # fmt: skip
    return table + "\n" + place


def _ratio_cell(row):
    if row is None:
        return ""
    ratio = row.get("complexity_vs_linuxdoom")
    if ratio is not None:
        return f"{ratio:.2f}"
    return f"{row['complexity_med']:g}/0" if row.get("comparable") else ""


def subsystem_block(result):
    """Median complexity of each port's subsystems over linuxdoom's same subsystem (``subsystem_distribution.run``).

    One row per port, one column per subsystem; blank where a side has under ``MIN_SUBSYSTEM`` functions. Where both
    sides are big enough but linuxdoom's median is 0 (its ``i_*`` platform code), a ratio is undefined and the cell
    shows the port's median over zero (``2/0``) instead of looking like missing data."""
    subs = sorted({r["subsystem"] for rows, _ in result.values() for r in rows if r["subsystem"] != "other"})
    body = []
    for port in sorted(result):
        if port == lineage.BASE:
            continue
        rows, other = result[port]
        got = {r["subsystem"]: r for r in rows}
        body.append([port, *(_ratio_cell(got.get(s)) for s in subs), f"{other:.0f}"])
    return _md(["port", *subs, "other %"], body)


def landmark_block(canon):
    """Landmark functions of each translation against linuxdoom's: complexity and LOC ratios (found / 12)."""
    by = collections.defaultdict(dict)
    for r in canon:
        by[r["variant"]][r["function"]] = r
    base = by[lineage.BASE]
    body = []
    for port in TRANSLATIONS:
        if port not in by:
            continue
        cx, loc = [], []
        for fn, b in base.items():
            r = by[port].get(fn)
            if r and r["complexity"] != "" and b["complexity"] != "":
                cx.append(float(r["complexity"]) / max(float(b["complexity"]), 1))
                loc.append(float(r["loc"]) / max(float(b["loc"]), 1))
        body.append([
            port, f"{len(cx)} / {len(base)}", f"{statistics.median(cx):.2f}" if cx else "-",
            f"{min(cx):.2f} - {max(cx):.2f}" if cx else "-", f"{statistics.median(loc):.2f}" if loc else "-",
            f"{min(loc):.2f} - {max(loc):.2f}" if loc else "-",
        ])  # fmt: skip
    return _md(
        ["port", "landmarks found", "complexity ratio, median", "range", "LOC ratio, median", "range"], body
    )  # fmt: skip


def subway_block(path, names):
    if path is None:
        return "_No `--subway` file given: run `sfs compare` (see the header of `study_report.py`) and pass its `subway.csv`._\n"
    with open(path, newline="") as fh:
        got = {r["repo"]: r for r in csv.DictReader(fh)}
    body = [[n, got[n]["functions"], got[n]["wiring_similarity"], got[n]["edges_kept"], got[n]["shape_distance"]]
            for n in names if n in got and n != lineage.BASE]  # fmt: skip
    body.sort(key=lambda r: -(float(r[2]) if r[2] not in ("", "nan") else -1.0))
    return _md(["port", "functions", "wiring similarity", "linuxdoom calls kept", "graph-shape distance"], body)


def build(work, sha, before_ref, manifest, subway):
    rows_all = doom_speedrun.read_manifest(manifest)
    rows = [r for r in rows_all if r["name"] in lineage.LICENSED]
    before = doom_diff.load(doom_diff.resolve_csv(before_ref, work))
    after = doom_diff.load(doom_diff.resolve_csv(sha, work))
    out, skipped = lineage.run([r for r in rows if r["name"] in lineage.LICENSED], work, sha)
    dist_rows = [r for r in rows if r["name"] in lineage.LICENSED]
    summary, _ = distribution.run(dist_rows, work, sha)
    sub_result, _ = subsystem_distribution.run(dist_rows, work, sha)
    fid = {r["name"]: r.get("fidelity") or "unstated" for r in rows}
    blocks = {
        "clean-scan": clean_scan_block(rows, before, after),
        "fidelity": fidelity.report(rows_all),
        "lineage": lineage_block(out, rows),
        "distribution": distribution_block(summary, fid),
        "subsystem": subsystem_block(sub_result),
        "landmarks": landmark_block(out["canonical_functions.csv"]),
        "subway": subway_block(subway, [r["name"] for r in rows]),
    }
    return blocks, skipped


def fill(doc, blocks):
    """Replace each marked block of ``doc`` with its table; a missing marker pair is an error."""
    for name, text in blocks.items():
        pat = re.compile(re.escape(BEGIN.format(name)) + r".*?" + re.escape(END.format(name)), re.S)
        if not pat.search(doc):
            raise SystemExit(f"study_report: {DOC.name} has no '{BEGIN.format(name)}' ... '{END.format(name)}' pair")
        doc = pat.sub(lambda _m, n=name, t=text: f"{BEGIN.format(n)}\n\n{t}\n{END.format(n)}", doc)
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--work", type=Path, default=doom_speedrun.DEFAULT_WORK, help="doom_speedrun work dir")
    ap.add_argument("--sha", help="engine SHA of the scans to read (default: this checkout's HEAD)")
    ap.add_argument("--before", default="round2", help="clean_check ref for the before column (default round2)")
    ap.add_argument("--manifest", type=Path, help="alternate manifest CSV")
    ap.add_argument("--subway", type=Path, help="sfs subway.csv (squid-protocol/gitgalaxy-population-analyses)")
    ap.add_argument("--doc", type=Path, default=DOC)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="rewrite the doc's marked tables")
    mode.add_argument("--check", action="store_true", help="rc 1 when the doc's tables differ from the scans")
    args = ap.parse_args(argv)
    work, sha = args.work.resolve(), args.sha or doom_speedrun.engine_sha()
    blocks, skipped = build(work, sha, args.before, args.manifest, args.subway)
    for name in skipped:
        print(f"study_report: no scan or clone for {name} at {sha}", file=sys.stderr)
    if not (args.write or args.check):
        for name, text in blocks.items():
            print(f"## {name}\n\n{text}")
        return 0
    old = args.doc.read_text()
    new = fill(old, blocks)
    if args.check:
        print("study_report: tables current" if new == old else "study_report: tables are stale (run with --write)")
        return 0 if new == old else 1
    args.doc.write_text(new)
    print(f"study_report: wrote {len(blocks)} tables into {args.doc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
