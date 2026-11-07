"""`cics_census.py check` (#7961): a branch against the census before its PR, counts only.

    python tests/tools/cics_census.py check [--jobs 2] [--sha SHA] [--root DIR] [--force]

Surveys the worktree HEAD (uncommitted edits included) WITH the census corpora, compares it with the cached origin/main
baseline (`cics_census.py survey --baseline`, surveyed with the census) and prints counts only: whole a -> b (all,
census, burned), accounted c -> d, and the gap rows gone / new by scrubbed key. The same CICS-program scope as the
baseline. Gated on box_status.py saying GREEN (exit 3 otherwise; --force skips the gate), run under `nice -n 10` with
`--jobs 2`, the survey directory deleted afterwards. Nothing census-named is printed: every key goes through
`gap_prevalence.scrub_key`, and a line that still names a census repo, path or program is refused (exit 1).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parents[1]))

import census_nightly  # noqa: E402
import cics_census as cc  # noqa: E402

NICE = census_nightly.NICE
JOBS = census_nightly.JOBS
NOT_GREEN = 3
REFUSED = "refused: the output names a census repo, path or program; nothing printed"
NO_ROW = "(no survey row)"

Rows = dict[tuple[str, str], dict[str, Any]]


def _classes(row: dict[str, Any] | None, scrub: Any) -> set[str]:
    return {NO_ROW} if row is None else {scrub(g) for g in cc.gap_classes(row)}


def measure(rows: Rows, cics: set[tuple[str, str]]) -> dict[str, Any]:
    """Counts of one survey over the CICS programs `cics`: whole (all / census / burned), accounted (whole, or only named
    source defects) and the programs per scrubbed gap key."""
    import gap_prevalence as gp  # lazy: gap_prevalence imports cics_census

    burned = cc.burned_names()
    out: dict[str, Any] = {"programs": len(cics), "whole": 0, "whole_census": 0, "whole_burned": 0, "accounted": 0}
    gaps: dict[str, int] = defaultdict(int)
    for k in cics:
        row = rows.get(k)
        classes = _classes(row, gp.scrub_key)
        if cc.whole(row):
            out["whole"] += 1
            out["whole_burned" if cc.is_burned(k[0], burned) else "whole_census"] += 1
        raw = set() if row is None else cc.gap_classes(row)
        out["accounted"] += row is not None and all(gp.is_named_defect(g) for g in raw)
        for g in classes - {""}:
            gaps[g] += 1
    out["gaps"] = dict(gaps)
    return out


def compare(before: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    gb, gh = before["gaps"], head["gaps"]
    return {"before": before, "head": head,
            "gone": sorted((g, gb[g]) for g in gb if g not in gh),
            "new": sorted((g, gh[g]) for g in gh if g not in gb)}  # fmt: skip


def format_check(res: dict[str, Any], sha: str) -> str:
    b, h = res["before"], res["head"]
    out = [f"census check: HEAD (worktree) vs origin/main {sha[:12]}, {h['programs']} CICS programs",
           f"whole {b['whole']} -> {h['whole']} (census {b['whole_census']} -> {h['whole_census']}, burned "
           f"{b['whole_burned']} -> {h['whole_burned']}), accounted {b['accounted']} -> {h['accounted']}, "
           f"gap rows {len(b['gaps'])} -> {len(h['gaps'])}"]  # fmt: skip
    for tag in ("gone", "new"):
        out.append(f"gap rows {tag} ({len(res[tag])}): " + ("; ".join(f"{g} [{n}]" for g, n in res[tag]) or "none"))
    return "\n".join(out)


def forbidden_names(rows: Rows, root: Path) -> list[str]:
    """What the output must not carry: census repo names and clone path, plus every non-burned corpus and program."""
    import equivalence_env

    names = [str(root / "census"), *(r.split("/")[-1] for r in equivalence_env.census_repos())]
    burned = cc.burned_names()
    for corpus, program in rows:
        if not cc.is_burned(corpus, burned):
            names += [corpus, program, Path(program).stem]
    return sorted({n for n in names if n})


def names_a_census(text: str, forbidden: list[str]) -> bool:
    """True when `text` carries a forbidden name as a whole token (the census-nightly rule, with word boundaries)."""
    if not forbidden:
        return False
    return census_nightly.names_census(text, [rf"(?<![A-Za-z0-9]){re.escape(n)}(?![A-Za-z0-9])" for n in forbidden])


def head_survey(args: argparse.Namespace, root: Path, mainframe: Path, census: Path) -> Rows:
    """Survey the worktree (its translator, --jobs 2, nice 10) into a scratch directory that is deleted afterwards."""
    root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="census-head-", dir=root))
    try:
        with contextlib.suppress(AttributeError, OSError):  # no os.nice on Windows
            os.nice(NICE)
        runs = cc.survey_runs(mainframe, census, None, None)
        sink = io.StringIO()  # run_det_survey prints census roots and log paths: keep them off the terminal
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            rc = cc.run_det_survey(tmp, "head", runs, jobs=args.jobs, compile_ports=False)
        if rc:
            raise SystemExit("census check: the HEAD survey failed (details withheld: they may name census paths)")
        return cc.load_surveys(tmp, "head")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_check(args: argparse.Namespace) -> int:
    verdict = census_nightly.box_verdict()
    if verdict != "GREEN" and not args.force:
        print(f"census check: box_status says {verdict}, the check needs GREEN (retry later, or --force)")
        return NOT_GREEN
    root = cc.scratch_root(args.root)
    sha = cc.resolve_sha(args.sha)
    d = cc.baseline_dir(args)
    if not json.loads((d / "meta.json").read_text(encoding="utf-8")).get("census"):
        raise SystemExit(f"the cached baseline of {sha[:12]} was surveyed without the census: run "
                         f"`cics_census.py survey --baseline --force` first")  # fmt: skip
    cics = {tuple(p) for p in json.loads((d / "cics_programs.json").read_text(encoding="utf-8"))}
    mainframe = cc.mainframe_root(args.corpora)
    census = cc.baseline_census(args, root)
    if census is None:
        raise SystemExit(
            "census check needs the census corpora (--census-corpora, $CICS_CENSUS_CORPORA or --provision)"
        )
    head = head_survey(args, root, mainframe, census)
    before = cc.load_surveys(d, "before")
    text = format_check(compare(measure(before, cics), measure(head, cics)), sha)  # type: ignore[arg-type]
    if names_a_census(text, forbidden_names({**before, **head}, root)):
        print(REFUSED, file=sys.stderr)
        return 1
    print(text)
    return 0
