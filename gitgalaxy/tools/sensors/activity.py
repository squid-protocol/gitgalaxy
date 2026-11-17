# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""`gitgalaxy activity`: how active is each file, how long has it been settled, and who looks after it? From git history alone.

    gitgalaxy activity REPO [--rev REV] [--scan-db DB] [--top N] [--json FILE]

Per file, in plain units (no score): commits in the last 365 and 90 days, days since the last change, age in years (first commit) and lifetime
commits, authors in the last year, the top author's share of the last year's commits and whether that author has committed in the last two years.
History follows renames (`git log -M`), so a file moved by a reorganisation keeps its age. Lists default to source files; each file carries its role.

Worklists: hot now (top tenth by 365-day commits), ownership context (one author does most of a file's recent work, or that author has gone
quiet), and dormant files (two or more years untouched), which with `--scan-db` (a scan of the same tree) are split into those many files
depend on ("quiet foundations") and the rest. Read-only: runs `git log` once, opens the scan immutable.

Not a risk read. Design, evidence and limits: temporal-crucible `docs/sensor-overhaul/sensors/activity.md`; the engine's agreement with that mock-up:
wiki 08-27."""

from __future__ import annotations

import argparse
import bisect
import collections
import json
import statistics
import subprocess
import sys
from pathlib import Path

from gitgalaxy.core.source_text import decode_bytes
from gitgalaxy.tools.sensors import reach

DAY = 86400
YEAR = 365.25 * DAY
HOT_FRACTION = 0.10  # the top tenth of active files by 365-day commits
CONCENTRATED = 0.60  # one author made this share of a file's last-year commits
DORMANT_YEARS = 2.0
FOUNDATION_FRACTION = 0.10  # the top tenth of source files by files that call into them


# languages the engine knows that are data or prose, not code: a file in one is "other", not a source file
_NOT_CODE = frozenset({"css", "csv", "html", "json", "markdown", "plaintext", "xml", "yaml", "pbtxt"})
_code_names: tuple[frozenset[str], frozenset[str]] | None = None


def is_code(path: str) -> bool:
    """True when the engine has a code language for this file's extension or exact name."""
    global _code_names
    if _code_names is None:
        from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

        defs = [d for name, d in LANGUAGE_DEFINITIONS.items() if name not in _NOT_CODE]
        _code_names = (
            frozenset(e.lower() for d in defs for e in d.get("extensions", ())),
            frozenset(n for d in defs for n in d.get("exact_matches", ())),
        )
    name = path.rsplit("/", 1)[-1]
    return name in _code_names[1] or ("." in name and "." + name.rsplit(".", 1)[-1].lower() in _code_names[0])


def _role(path: str) -> str:
    role = reach.role(path)
    return "other" if role == "source" and not is_code(path) else role


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(  # noqa: S603
        ["git", "-c", "core.quotepath=off", "-C", str(repo), *args],  # noqa: S607
        capture_output=True,
        check=False,
    )
    if out.returncode:
        raise RuntimeError(decode_bytes(out.stderr).strip() or f"git {' '.join(args)} failed")
    return decode_bytes(out.stdout)


def history(repo: Path, rev: str) -> tuple[dict[str, list[tuple[int, str]]], dict[str, list[int]]]:
    """Every commit that touched each file present at `rev` as (time, author), following renames, and each author's commit times.

    Walks oldest to newest keeping a file identity: a rename (or copy) carries the identity to the new path, an add makes one, a delete drops it.
    Merge commits are left out (their changes are counted where they were made)."""
    log = _git(repo, "log", "--no-merges", "--reverse", "-M", "--name-status", "--format=@@%ct%x09%ae", rev)
    ident: dict[str, int] = {}
    nid = 0
    events: dict[int, list[tuple[int, str]]] = collections.defaultdict(list)
    authors: dict[str, list[int]] = collections.defaultdict(list)
    cur: tuple[int, str] | None = None
    for line in log.splitlines():
        if line.startswith("@@"):
            t, _, a = line[2:].partition("\t")
            cur = (int(t), a.lower())
            authors[cur[1]].append(cur[0])
        elif line and cur:
            parts = line.split("\t")
            status = parts[0][:1]
            if status in "RC" and len(parts) == 3:
                i = ident.get(parts[1])
                if i is None:
                    i, nid = nid, nid + 1
                if status == "R":
                    ident.pop(parts[1], None)
                ident[parts[2]] = i
                events[i].append(cur)
            elif status == "A" and len(parts) >= 2:
                ident[parts[1]] = nid
                events[nid].append(cur)
                nid += 1
            elif status == "M" and len(parts) >= 2:
                i = ident.get(parts[1])
                if i is None:
                    i, nid = nid, nid + 1
                    ident[parts[1]] = i
                events[i].append(cur)
            elif status == "D" and len(parts) >= 2:
                ident.pop(parts[1], None)
    return {p: events[i] for p, i in ident.items()}, {a: sorted(v) for a, v in authors.items()}


def panel(events: dict[str, list[tuple[int, str]]], authors: dict[str, list[int]], now: int) -> list[dict]:
    """One row per file: the activity readings at time `now`."""
    rows = []
    for path, evs in sorted(events.items()):
        times = [t for t, _ in evs]
        n = bisect.bisect_right(times, now)
        if not n:
            continue
        last = times[n - 1]
        recent = [a for t, a in evs[:n] if t > now - 365 * DAY]
        counts = collections.Counter(recent)
        top = counts.most_common(1)[0][0] if counts else evs[n - 1][1]
        theirs = authors.get(top, [])
        k = bisect.bisect_right(theirs, now)
        rows.append(
            {
                "path": path,
                "role": _role(path),
                "commits_90d": sum(1 for t in times[:n] if t > now - 90 * DAY),
                "commits_365d": len(recent),
                "commits_lifetime": n,
                "days_since_last_change": round((now - last) / DAY, 1),
                "age_years": round((now - times[0]) / YEAR, 2),
                "authors_365d": len(counts),
                "top_author": top,
                "top_author_share": round(max(counts.values()) / len(recent), 3) if recent else None,
                "owner_active": bool(k and theirs[k - 1] > now - DORMANT_YEARS * YEAR),
            }
        )
    return rows


def worklists(rows: list[dict], reach_files: dict[str, int] | None) -> dict:
    """Hot now, ownership context, dormant (split by reach when a scan was given). Source files only."""
    src = [r for r in rows if r["role"] == "source"]
    active = sorted((r["commits_365d"] for r in src if r["commits_365d"] > 0), reverse=True)
    cut = active[max(int(len(active) * HOT_FRACTION), 1) - 1] if active else 0
    hot = sorted((r for r in src if r["commits_365d"] >= max(cut, 1)), key=lambda r: (-r["commits_365d"], r["path"]))
    concentrated = [
        r
        for r in src
        if r["commits_365d"] > 0
        and r["top_author_share"] >= CONCENTRATED
        and (not r["owner_active"] or r["top_author_share"] >= 0.9)
    ]
    concentrated.sort(key=lambda r: (-r["commits_365d"], r["path"]))
    dormant = [r for r in src if r["days_since_last_change"] >= DORMANT_YEARS * 365.25]
    dormant.sort(key=lambda r: (-r["days_since_last_change"], r["path"]))
    out = {"hot_now": hot, "ownership_context": concentrated, "dormant": dormant, "hot_threshold_commits_365d": cut}
    if reach_files is not None:
        measured = sorted((reach_files[r["path"]] for r in src if r["path"] in reach_files), reverse=True)
        rcut = measured[max(int(len(measured) * FOUNDATION_FRACTION), 1) - 1] if measured else None
        out["reach_threshold_files"] = rcut
        out["quiet_foundations"] = (
            sorted(
                (
                    dict(r, reach_files=reach_files[r["path"]])
                    for r in dormant
                    if r["path"] in reach_files and reach_files[r["path"]] >= max(rcut, 1)
                ),
                key=lambda r: (-r["reach_files"], r["path"]),
            )
            if rcut is not None
            else []
        )
    return out


def build_report(repo: Path, rev: str, scan_db: Path | None) -> dict:
    sha = _git(repo, "rev-parse", rev).strip()
    now = int(_git(repo, "show", "-s", "--format=%ct", sha).strip())
    events, authors = history(repo, sha)
    rows = panel(events, authors, now)
    reach_files = None
    if scan_db:
        built = reach.build(scan_db)
        reach_files = {r["path"]: r["reach_files"] for r in built["rows"] if r["kind"] == "source"}
    src = [r for r in rows if r["role"] == "source"]
    summary = {
        "files": len(rows),
        "source_files": len(src),
        "active_365d": sum(1 for r in src if r["commits_365d"] > 0),
        "dormant_2y": sum(1 for r in src if r["days_since_last_change"] >= DORMANT_YEARS * 365.25),
        "median_age_years": round(statistics.median(r["age_years"] for r in src), 1) if src else None,
    }
    return {"rev": sha, "summary": summary, "worklists": worklists(rows, reach_files), "files": rows}


def _line(r: dict, extra: str = "") -> str:
    own = (
        ""
        if r["top_author_share"] is None
        else f", top author {100 * r['top_author_share']:.0f}%{'' if r['owner_active'] else ' (quiet 2y+)'}"
    )
    return (
        f"  {r['path']}: {r['commits_365d']} commits in 365 d ({r['commits_90d']} in 90 d), last change {r['days_since_last_change']:.0f} d ago, "
        f"{r['age_years']:.1f} y old{own}{extra}"
    )


def report(res: dict, top: int = 8) -> str:
    s, w = res["summary"], res["worklists"]
    out = [
        f"ACTIVITY at {res['rev'][:10]}: {s['source_files']} source files; {s['active_365d']} changed in the last year, {s['dormant_2y']} untouched for 2+ years; median age {s['median_age_years']} y"
    ]
    out.append(
        f"HOT NOW (top tenth of active source files: {w['hot_threshold_commits_365d']}+ commits in 365 days; {len(w['hot_now'])} files)"
    )
    out.extend(_line(r) for r in w["hot_now"][:top])
    out.append(
        f"OWNERSHIP CONTEXT ({len(w['ownership_context'])} active files where one author did 60%+ of last year's commits and has gone quiet, or did 90%+)"
    )
    out.extend(_line(r) for r in w["ownership_context"][:top])
    out.append(
        "  Describes who looks after a file, not whether it is at risk: its direction changes between repositories."
    )
    if "quiet_foundations" in w:
        q = w["quiet_foundations"]
        out.append(
            f"QUIET FOUNDATIONS ({len(q)} files untouched 2+ years and called from {w['reach_threshold_files']}+ files)"
        )
        out.extend(_line(r, f", called from {r['reach_files']} files") for r in q[:top])
        out.append(
            "  A change to one of these reaches many callers. In the study behind this list, fixes landed in such files less often than in the repository as a whole."
        )
    else:
        out.append(
            f"DORMANT ({len(w['dormant'])} files untouched 2+ years); give --scan-db to see which of them many files depend on"
        )
        out.extend(_line(r) for r in w["dormant"][:top])
    return "\n".join(out)


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("repo", type=Path, help="a git repository (full history; a shallow clone gives short ages)")
    p.add_argument("--rev", default="HEAD", help="the revision to read as 'now' (default HEAD)")
    p.add_argument(
        "--scan-db",
        type=Path,
        help="a scan of the tree at REV: adds the quiet-foundations list (who depends on a quiet file)",
    )
    p.add_argument("--top", type=int, default=8)
    p.add_argument(
        "--json", type=Path, metavar="FILE", help="also write the full result (every file's readings) as JSON"
    )


def run(args: argparse.Namespace) -> int:
    if args.scan_db and not args.scan_db.is_file():
        print(f"gitgalaxy activity: no such database: {args.scan_db}", file=sys.stderr)
        return 2
    try:
        if _git(args.repo, "rev-parse", "--is-shallow-repository").strip() == "true":
            print(
                "gitgalaxy activity: this is a shallow clone; ages and dormancy are read from the history it has",
                file=sys.stderr,
            )
        res = build_report(args.repo, args.rev, args.scan_db)
    except (RuntimeError, OSError) as exc:
        print(f"gitgalaxy activity: {exc}", file=sys.stderr)
        return 2
    print(report(res, args.top))
    if args.json:
        args.json.write_text(json.dumps(res, indent=1))
    return 0
