#!/usr/bin/env python3
"""#2720: outcome-label pilot -- do language strictness / per-file dynamism predict LATER fix commits?

The crucible is snapshot copies (no `.git`), so the pilot clones ~10 upstream repos WITH history at their
`data/PROVENANCE.json` pins, scans each pin, and joins every scanned file to the fix commits made after the pin:

    python tests/tools/outcome_pilot.py list                       # the pilot repos, their pins and language rows
    python tests/tools/outcome_pilot.py clone  --work DIR [REPO ...]
    python tests/tools/outcome_pilot.py scan   --work DIR [REPO ...]   # archive the pin, galaxyscope --db-only
    python tests/tools/outcome_pilot.py label  --work DIR [REPO ...]   # per-file later-fix counts + hand-check sample
    python tests/tools/outcome_pilot.py recall --work DIR [REPO ...]  # subject-only vs subject+body fix labels
    (label / analyze take --max-files-per-commit N: the bulk-commit guard, rows-bulkN.csv / analysis-bulkN.json)
    python tests/tools/outcome_pilot.py analyze --work DIR            # the stratified analysis (JSON + text)

Design (the memo is docs/research/outcome_label_pilot.md; this file is the reproducible half):
  * A "fix commit" is a non-merge commit whose SUBJECT matches the fix/bug/crash/leak/CVE/regression/revert family
    (`is_fix_subject`). Subject-only labels are noisy; `label` writes a seeded sample per repo for a hand check.
  * "Later" means after the pin and inside a fixed window (`--window-days`), so a repo's age cannot buy fixes.
    Renames after the pin are followed (`git log -M --name-status`, oldest first), so a file keeps its count.
  * Evidence is held equal by stratifying on repo x LOC bin x evidence bin. Evidence is the file's own
    structural-signal total WITHOUT dynamism (`EVIDENCE_COLUMNS`), so dynamism is not controlled away.
  * Dynamism is `state_heat_triggers` (the DB column of `reflection_metaprogramming`, what #2719 reads).
  * Strictness is the FILE's language row (`strictness_constants`), not the repo's, so polyglot repos
    (curl, redis, micropython) give within-repo contrast. Files of no-row languages are left out.
  * Stats are stdlib only: a Mantel-Haenszel rate ratio with a cluster bootstrap over files for dynamism, and the
    same for the strictness gap count (files with >=3 gaps vs <=1 gap). Magnitudes are reported with CIs, no verdict.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from collections.abc import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gitgalaxy.core.source_text import decode_bytes  # noqa: E402
from gitgalaxy.standards.analysis_lens import (  # noqa: E402
    LANGUAGE_STRICTNESS,
    resolve_language_family,
    strictness_constants,
)

SEED = 2720
DEFAULT_WINDOW_DAYS = 730
SAMPLE_PER_REPO = 40
BOOTSTRAP_ROUNDS = 400
LOC_BINS = 10
EVIDENCE_BINS = 4

# name -> (url, pin, note). Pins are the PROVENANCE.json commits; carddemo's provenance copy lives inside the
# che4z LSP repo, so the burned estate's own upstream is used and its pin is chosen by `--pin-fraction` of history.
PILOT_REPOS: dict[str, dict[str, Any]] = {
    "curl": {"url": "https://github.com/curl/curl", "pin": "8f3f470bae", "burned": False},
    "micropython": {"url": "https://github.com/micropython/micropython", "pin": "2dc2e30d98", "burned": False},
    "redis": {"url": "https://github.com/redis/redis", "pin": "2ba0194fbe", "burned": False},
    "mojo": {"url": "https://github.com/mojolicious/mojo.git", "pin": "19fc4f19a0", "burned": False},
    "guzzle": {"url": "https://github.com/guzzle/guzzle.git", "pin": "fb92d95f80", "burned": False},
    "fastapi": {"url": "https://github.com/tiangolo/fastapi.git", "pin": "1f442c454f", "burned": False},
    "serde": {"url": "https://github.com/serde-rs/serde.git", "pin": "fa7da4a935", "burned": False},
    "tokio": {"url": "https://github.com/tokio-rs/tokio", "pin": "1fc450aefb", "burned": False},
    "assemblyscript": {
        "url": "https://github.com/AssemblyScript/assemblyscript.git",
        "pin": "be8e56d524",
        "burned": False,
    },
    "carddemo": {
        "url": "https://github.com/aws-samples/aws-mainframe-modernization-carddemo",
        "pin": None,
        "burned": True,
    },
    # The other burned estates (estate4_draw.BURNED_NAMES). The local .mainframe_corpora copies are single-commit
    # squashes, so each needs its upstream clone for history. "subdir" limits the archive and the log to the estate.
    "cbsa": {
        "url": "https://github.com/cicsdev/cics-banking-sample-application-cbsa",
        "pin": None,
        "burned": True,
    },
    # The same sample at the end of its 2023 build-out (after the 2022-12..2023-02 renames and the 2023-08/09 burst):
    # the maintenance phase, where the midpoint pin above sits inside the build-out.
    "cbsa-late": {
        "url": "https://github.com/cicsdev/cics-banking-sample-application-cbsa",
        "pin": "f15453ba1d",
        "burned": True,
        "clone_as": "cbsa",
    },
    "genapp": {"url": "https://github.com/cicsdev/cics-genapp", "pin": None, "burned": True},
    # zECS's sources arrive with the 2016-11-29 "Initial commit on github"; a midpoint pin would scan only markdown.
    "zecs": {"url": "https://github.com/walmartlabs/zECS", "pin": "9ab1e35", "burned": True},
    "dbb-mortgage": {
        "url": "https://github.com/IBM/dbb",
        # zBuilder/MortgageApplication was moved in on 2025-09-11 (2 commits touch it): the pin is that move,
        # because an earlier mid-history pin has no such tree to archive.
        "pin": "0f8a61f",
        "burned": True,
        "subdir": "zBuilder/MortgageApplication",
    },
    # The same sample in its 2019 layout: Build/MortgageApplication, committed 2019-03-16 and deleted later. The 2025
    # zBuilder tree is a copy (all files "A" in 0f8a61f), so `--follow` cannot reach this history; it needs its own pin.
    "dbb-mortgage-2019": {
        "url": "https://github.com/IBM/dbb",
        "pin": "ecd713f",
        "burned": True,
        "subdir": "Build/MortgageApplication",
        # the scanner's aperture drops anything under a `Build/` directory, and `git archive` re-encodes the sources to
        # EBCDIC: export the raw blobs of the subtree at the snapshot root, prefix the subdir back on when joining history
        "strip_subdir": True,
        "clone_as": "dbb-mortgage",
    },
    "async-credit-card": {
        "url": "https://github.com/cicsdev/cics-async-api-credit-card-application-example",
        "pin": None,
        "burned": True,
    },
}

# The structural-signal columns summed into per-file "measured evidence". Dynamism (state_heat_triggers) is left out
# on purpose: holding it equal would remove the effect the pilot asks about.
EVIDENCE_COLUMNS = (
    "struct_branch",
    "state_danger",
    "state_pointers",
    "state_memory_alloc",
    "state_bailout_hits",
    "state_halt_hits",
    "state_cast_hits",
    "state_fragile_debt",
    "arch_io",
    "arch_concurrency",
)
DYNAMISM_COLUMN = "state_heat_triggers"

# --- fix-commit labelling -----------------------------------------------------------------------------------------
_FIX_WORDS = r"fix(?:e[sd]|ing)?|bug(?:s|fix(?:es)?)?|crash(?:e[sd]|es|ing)?|leak(?:s|ed|ing)?|regress(?:ion|ions)?|revert(?:s|ed)?"
_FIX_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:" + _FIX_WORDS + r"|CVE-\d{4}-\d{4,})(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
# "fixture(s)", "prefix", "bugzilla" are not fixes; the lookarounds above already reject the first two. These
# lead-ins describe a NOT-a-fix commit that merely mentions the word.
_NOT_FIX_RE = re.compile(r"^\s*(?:merge\b|bump\b|release\b|docs?:|typo\b)", re.IGNORECASE)
_MERGE_SUBJECT_RE = re.compile(r"^Merge (?:pull request|branch|remote-tracking|tag)\b")


def is_fix_subject(subject: str) -> bool:
    """True for a commit subject in the fix / bug / crash / leak / CVE / regression / revert family."""
    if not subject or _MERGE_SUBJECT_RE.match(subject):
        return False
    if _NOT_FIX_RE.match(subject):
        return False
    return _FIX_RE.search(subject) is not None


# A body-level fix label: a "fixes" keyword followed by an issue reference, a Fixes:/Bug: trailer, or a CVE id. "Closes"
# and "Resolves" are left out: curl-style projects put `Closes #N` on every merged PR, features included. The subject label misses fixes
# whose subject names no keyword ("dnscache: check hostname on lookup" + "Fixes #123").
_BODY_FIX_RE = re.compile(
    r"(?im)^\s*(?:(?:fix(?:e[sd])?)\s*:?\s+(?:[\w./-]+)?#\d+|(?:fixes|bug|cve)\s*:\s*\S+|.*\bCVE-\d{4}-\d{4,}\b)"
)


def is_fix_body(body: str) -> bool:
    """True when a commit message body links a fixed issue (Fixes #N, a Fixes:/Bug: trailer) or names a CVE."""
    return bool(body) and _BODY_FIX_RE.search(body) is not None


# --- git history --------------------------------------------------------------------------------------------------
def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)
    return decode_bytes(out.stdout)


def pin_date(repo: Path, pin: str) -> datetime:
    return datetime.fromisoformat(_git(repo, "show", "-s", "--format=%cI", pin).strip())


def parse_log(text: str) -> list[tuple[str, str, list[tuple[str, str, str | None]]]]:
    """Parse `git log --name-status -M --format=%x01%H%x02%s`, newest first.

    Returns (sha, subject, [(status_letter, path, old_path_or_None)]).
    """
    commits = []
    for chunk in text.split("\x01"):
        if not chunk.strip():
            continue
        head, _, rest = chunk.partition("\n")
        sha, _, subject = head.partition("\x02")
        changes: list[tuple[str, str, str | None]] = []
        for line in rest.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            status = parts[0][:1]
            if status in ("R", "C") and len(parts) >= 3:
                changes.append((status, parts[2], parts[1]))
            elif len(parts) >= 2:
                changes.append((status, parts[1], None))
        commits.append((sha.strip(), subject.strip(), changes))
    return commits


def later_fix_counts(
    commits_newest_first: Sequence[tuple[str, str, list[tuple[str, str, str | None]]]],
    pin_paths: Iterable[str],
    max_files: int | None = None,
) -> tuple[dict[str, int], dict[str, int], dict[str, str]]:
    """Per pin-time path: (fix commits, all commits) after the pin, following renames; plus final names.

    Walks oldest first, keeping `alias[current_name] = pin_path`. A delete ends the alias (the count so far stays);
    a re-add of the same name is a new file and is not credited to the pin path. With `max_files`, a commit that touches
    more than that many scanned files is a bulk edit: its renames still move the alias, but it is credited to no file
    (neither a touch nor a fix).
    """
    alias = {p: p for p in pin_paths}
    fixes: dict[str, int] = defaultdict(int)
    touches: dict[str, int] = defaultdict(int)
    final: dict[str, str] = {p: p for p in alias}
    for _sha, subject, changes in reversed(list(commits_newest_first)):
        fix = is_fix_subject(subject)
        seen: set[str] = set()
        for status, path, old in changes:
            if status in ("R", "C") and old is not None:
                origin = alias.get(old)
                if origin is not None and status == "R":
                    del alias[old]
                    alias[path] = origin
                    final[origin] = path
                elif origin is not None:  # copy: the original stays
                    pass
                target = alias.get(path)
            elif status == "D":
                target = alias.pop(path, None)
                if target is not None:
                    final[target] = ""
            else:
                target = alias.get(path)
            if target is not None:
                seen.add(target)
        if max_files is not None and len(seen) > max_files:
            continue
        for target in seen:
            touches[target] += 1
            if fix:
                fixes[target] += 1
    return dict(fixes), dict(touches), final


def history_after_pin(
    repo: Path, pin: str, window_days: int, subdir: str | None = None
) -> list[tuple[str, str, list[tuple[str, str, str | None]]]]:
    start = pin_date(repo, pin)
    end = start + timedelta(days=window_days)
    text = _git(
        repo,
        "log",
        "--no-merges",
        "-M",
        "--name-status",
        "--format=%x01%H%x02%s",
        f"--until={end.isoformat()}",
        f"{pin}..HEAD",
        *(["--", subdir] if subdir else []),
    )
    return parse_log(text)


# --- scanning ----------------------------------------------------------------------------------------------------
def _repo_dir(work: Path, name: str) -> Path:
    return work / "clones" / PILOT_REPOS[name].get("clone_as", name)


def resolve_pin(repo: Path, entry: dict[str, Any], pin_fraction: float = 0.5) -> str:
    if entry["pin"]:
        return _git(repo, "rev-parse", entry["pin"]).strip()
    shas = _git(repo, "rev-list", "--first-parent", "--reverse", "HEAD").split()
    return shas[min(len(shas) - 1, int(len(shas) * pin_fraction))]


def _strip_args(entry: dict[str, Any]) -> list[str]:
    if not (entry.get("strip_subdir") and entry.get("subdir")):
        return []
    return [f"--strip-components={len(Path(entry['subdir']).parts)}"]


def _history_path(entry: dict[str, Any], rel: str) -> str:
    return f"{entry['subdir']}/{rel}" if _strip_args(entry) else rel


def _subdir_args(entry: dict[str, Any]) -> list[str]:
    return [entry["subdir"]] if entry.get("subdir") else []


def cmd_clone(work: Path, names: list[str]) -> None:
    for name in names:
        dest = _repo_dir(work, name)
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--quiet", PILOT_REPOS[name]["url"], str(dest)], check=True)


def export_raw_tree(repo: Path, pin: str, subdir: str, dest: Path) -> None:
    """Write the blobs under `subdir` at `pin` to `dest` with the subdir prefix removed, bytes as committed.

    `git archive` applies `working-tree-encoding` attributes (the DBB sample's `zos-working-tree-encoding: ibm-1047`),
    which turns the committed ASCII sources into newline-less EBCDIC that the aperture refuses; `git show` does not.
    """
    listing = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "-z", "--name-only", pin, subdir], capture_output=True, check=True
    ).stdout
    for raw in listing.split(b"\0"):
        if not raw:
            continue
        path = raw.decode("utf-8")
        blob = subprocess.run(["git", "-C", str(repo), "show", f"{pin}:{path}"], capture_output=True, check=True).stdout
        target = dest / path[len(subdir) :].lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)


def cmd_scan(work: Path, names: list[str]) -> None:
    for name in names:
        repo = _repo_dir(work, name)
        pin = resolve_pin(repo, PILOT_REPOS[name])
        snap = work / "snapshots" / name
        out = work / "scans" / name
        if not snap.exists():
            snap.mkdir(parents=True)
            if _strip_args(PILOT_REPOS[name]):
                export_raw_tree(repo, pin, PILOT_REPOS[name]["subdir"], snap)
            else:
                archive = subprocess.Popen(
                    ["git", "-C", str(repo), "archive", pin, *_subdir_args(PILOT_REPOS[name])], stdout=subprocess.PIPE
                )
                subprocess.run(["tar", "-x", "-C", str(snap)], stdin=archive.stdout, check=True)
                archive.wait()
        out.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, GITGALAXY_DISABLE_GIT_HISTORY="1")
        subprocess.run(
            [sys.executable, "-m", "gitgalaxy.galaxyscope", str(snap), "--db-only", "--output", str(out)],
            check=True,
            env=env,
        )
        (out / "pin.txt").write_text(pin + "\n", encoding="utf-8")


def read_scan(db_path: Path) -> list[dict[str, Any]]:
    """One row per scanned file: path, language, loc, evidence, dynamism."""
    con = sqlite3.connect(str(db_path))
    try:
        cols = ", ".join(EVIDENCE_COLUMNS)
        rows = con.execute(
            f"SELECT file_path, language, total_loc, {DYNAMISM_COLUMN}, {cols} FROM file_data"
        ).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        out.append(
            {
                "path": r[0],
                "language": r[1],
                "loc": int(r[2] or 0),
                "dynamism": int(r[3] or 0),
                "evidence": sum(int(v or 0) for v in r[4:]),
            }
        )
    return out


def strictness_gaps(language: str) -> int | None:
    """Number of `False` strictness columns for the file's language, None when the language has no row."""
    row = LANGUAGE_STRICTNESS.get(resolve_language_family(language))
    if not row:
        return None
    return sum(1 for flag in row if not flag)


def relative_path(scanned_path: str, snapshot: Path) -> str:
    p = Path(scanned_path)
    try:
        return p.resolve().relative_to(snapshot.resolve()).as_posix()
    except ValueError:
        return p.as_posix().lstrip("/")


def rows_file(work: Path, max_files: int | None) -> Path:
    return work / ("rows.csv" if max_files is None else f"rows-bulk{max_files}.csv")


def cmd_label(work: Path, names: list[str], window_days: int, max_files: int | None = None) -> None:
    rows_out = rows_file(work, max_files)
    new = not rows_out.exists()
    mode = "a" if not new else "w"
    with rows_out.open(mode, newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, ["repo", "path", "language", "gaps", "loc", "evidence", "dynamism", "fixes", "touches"]
        )
        if new:
            writer.writeheader()
        for name in names:
            repo = _repo_dir(work, name)
            scan_dir = work / "scans" / name
            pin = (scan_dir / "pin.txt").read_text(encoding="utf-8").strip()
            dbs = sorted(scan_dir.glob("*.db"))
            files = read_scan(dbs[0])
            snap = work / "snapshots" / name
            entry = PILOT_REPOS[name]
            by_rel = {_history_path(entry, relative_path(f["path"], snap)): f for f in files}
            commits = history_after_pin(repo, pin, window_days, PILOT_REPOS[name].get("subdir"))
            fixes, touches, _final = later_fix_counts(commits, by_rel, max_files)
            sample_rng = random.Random(f"{SEED}:{name}")
            fix_commits = [(s, subj) for s, subj, _c in commits if is_fix_subject(subj)]
            other = [(s, subj) for s, subj, _c in commits if not is_fix_subject(subj)]
            sample = sample_rng.sample(fix_commits, min(SAMPLE_PER_REPO, len(fix_commits)))
            sample_other = sample_rng.sample(other, min(SAMPLE_PER_REPO, len(other)))
            hand = work / "handcheck" / f"{name}.tsv"
            hand.parent.mkdir(parents=True, exist_ok=True)
            hand.write_text(
                "".join(f"labelled_fix\t{s}\t{subj}\n" for s, subj in sample)
                + "".join(f"labelled_other\t{s}\t{subj}\n" for s, subj in sample_other),
                encoding="utf-8",
            )
            for rel, f in sorted(by_rel.items()):
                gaps = strictness_gaps(f["language"])
                if gaps is None:
                    continue
                writer.writerow(
                    {
                        "repo": name,
                        "path": rel,
                        "language": f["language"],
                        "gaps": gaps,
                        "loc": f["loc"],
                        "evidence": f["evidence"],
                        "dynamism": f["dynamism"],
                        "fixes": fixes.get(rel, 0),
                        "touches": touches.get(rel, 0),
                    }
                )


def commit_bodies(repo: Path, pin: str, window_days: int, subdir: str | None = None) -> list[tuple[str, str, str]]:
    """(sha, subject, body) of the non-merge commits in the pilot window."""
    end = pin_date(repo, pin) + timedelta(days=window_days)
    text = _git(
        repo,
        "log",
        "--no-merges",
        "--format=%x01%H%x02%s%x02%b",
        f"--until={end.isoformat()}",
        f"{pin}..HEAD",
        *(["--", subdir] if subdir else []),
    )
    out = []
    for chunk in text.split("\x01"):
        if chunk.strip():
            sha, _, rest = chunk.partition("\x02")
            subject, _, body = rest.partition("\x02")
            out.append((sha.strip(), subject.strip(), body))
    return out


def recall_counts(commits: Sequence[tuple[str, str, str]]) -> dict[str, int]:
    """Subject-only vs subject-or-body fix labels. `body_only` are the fixes the subject label misses."""
    subject = sum(1 for _s, subj, _b in commits if is_fix_subject(subj))
    body_only = sum(1 for _s, subj, b in commits if not is_fix_subject(subj) and is_fix_body(b))
    return {"commits": len(commits), "subject_fix": subject, "body_only_fix": body_only, "either": subject + body_only}


def cmd_recall(work: Path, names: list[str], window_days: int) -> dict[str, dict[str, int]]:
    result = {}
    for name in names:
        pin = (work / "scans" / name / "pin.txt").read_text(encoding="utf-8").strip()
        commits = commit_bodies(_repo_dir(work, name), pin, window_days, PILOT_REPOS[name].get("subdir"))
        result[name] = recall_counts(commits)
        rng = random.Random(f"{SEED}:recall:{name}")
        gained = [(s, subj) for s, subj, b in commits if not is_fix_subject(subj) and is_fix_body(b)]
        hand = work / "recall" / f"{name}.tsv"
        hand.parent.mkdir(parents=True, exist_ok=True)
        hand.write_text(
            "".join(f"body_only\t{s}\t{subj}\n" for s, subj in rng.sample(gained, min(SAMPLE_PER_REPO, len(gained)))),
            encoding="utf-8",
        )
    return result


# --- analysis ----------------------------------------------------------------------------------------------------
def _tercile_edges(values: Sequence[float], bins: int) -> list[float]:
    ordered = sorted(values)
    if not ordered:
        return []
    return [ordered[min(len(ordered) - 1, (len(ordered) * i) // bins)] for i in range(1, bins)]


def _bin(value: float, edges: Sequence[float]) -> int:
    return sum(1 for e in edges if value >= e)


def assign_strata(rows: list[dict[str, Any]]) -> None:
    """Add `stratum` = repo x LOC bin x evidence bin (edges per repo, so a repo's own scale sets its bins)."""
    by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_repo[r["repo"]].append(r)
    for repo, rs in by_repo.items():
        loc_edges = _tercile_edges([r["loc"] for r in rs], LOC_BINS)
        ev_edges = _tercile_edges([r["evidence"] for r in rs], EVIDENCE_BINS)
        for r in rs:
            r["stratum"] = (repo, _bin(r["loc"], loc_edges), _bin(r["evidence"], ev_edges))


def mh_rate_ratio(rows: Sequence[dict[str, Any]], exposed: Any) -> float | None:
    """Mantel-Haenszel rate ratio of later fixes per file, exposed vs unexposed, over strata.

    Each file is one unit of equal follow-up (same window), so the rate is fixes per file. None when no stratum
    holds both groups.
    """
    cells: dict[Any, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])  # fix1, n1, fix0, n0
    for r in rows:
        c = cells[r["stratum"]]
        if exposed(r):
            c[0] += r["fixes"]
            c[1] += 1
        else:
            c[2] += r["fixes"]
            c[3] += 1
    num = den = 0.0
    for fix1, n1, fix0, n0 in cells.values():
        total = n1 + n0
        if n1 == 0 or n0 == 0:
            continue
        num += fix1 * n0 / total
        den += fix0 * n1 / total
    if den == 0:
        return None
    return num / den


def bootstrap_ci(rows: Sequence[dict[str, Any]], exposed: Any, rounds: int, seed: int) -> tuple[float, float] | None:
    rng = random.Random(seed)
    by_stratum: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_stratum[r["stratum"]].append(r)
    draws = []
    for _ in range(rounds):
        sample = []
        for members in by_stratum.values():
            sample.extend(rng.choices(members, k=len(members)))
        v = mh_rate_ratio(sample, exposed)
        if v is not None and v > 0:
            draws.append(v)
    if len(draws) < max(20, rounds // 4):
        return None
    draws.sort()
    return draws[int(0.025 * len(draws))], draws[min(len(draws) - 1, int(0.975 * len(draws)))]


def _estimate(rows: Sequence[dict[str, Any]], exposed: Any, rounds: int) -> dict[str, Any]:
    n1 = sum(1 for r in rows if exposed(r))
    est = mh_rate_ratio(rows, exposed)
    ci = bootstrap_ci(rows, exposed, rounds, SEED) if est is not None else None
    return {
        "files_exposed": n1,
        "files_unexposed": len(rows) - n1,
        "mh_rate_ratio": None if est is None else round(est, 3),
        "ci95": None if ci is None else [round(ci[0], 3), round(ci[1], 3)],
    }


# (name, highest gap count of the lower-strictness group, lowest gap count of the higher group)
STRICTNESS_CONTRASTS = (
    ("gaps_ge3_vs_le1", 1, 3),
    ("gaps_ge3_vs_le2", 2, 3),
    ("gaps_ge2_vs_le1", 1, 2),
)


def contributing_repos(rows: Sequence[dict[str, Any]], exposed: Any) -> list[str]:
    """Repos with at least one stratum holding both groups: the only ones that carry the estimate."""
    seen: dict[Any, set[bool]] = defaultdict(set)
    for r in rows:
        seen[r["stratum"]].add(bool(exposed(r)))
    return sorted({k[0] for k, v in seen.items() if len(v) == 2})


def analyze_rows(rows: list[dict[str, Any]], rounds: int = BOOTSTRAP_ROUNDS) -> dict[str, Any]:
    """The pilot's questions on a list of per-file rows (repo, gaps, loc, evidence, dynamism, fixes)."""
    rows = [dict(r) for r in rows]
    assign_strata(rows)
    mixed = defaultdict(set)
    for r in rows:
        mixed[r["repo"]].add(r["gaps"])
    polyglot_repos = {k for k, v in mixed.items() if len(v) > 1}
    strict_rows = [r for r in rows if r["repo"] in polyglot_repos]
    result: dict[str, Any] = {
        "files": len(rows),
        "repos": sorted({r["repo"] for r in rows}),
        "files_with_fix": sum(1 for r in rows if r["fixes"] > 0),
        "total_fixes": sum(r["fixes"] for r in rows),
        "dynamism_any_vs_none": _estimate(rows, lambda r: r["dynamism"] > 0, rounds),
        "dynamism_contributing_repos": contributing_repos(rows, lambda r: r["dynamism"] > 0),
        "strictness_polyglot_repos": sorted(polyglot_repos),
    }
    for name, lo_max, hi_min in STRICTNESS_CONTRASTS:
        sub = [r for r in strict_rows if r["gaps"] <= lo_max or r["gaps"] >= hi_min]

        def high(r: dict[str, Any], hi_min: int = hi_min) -> bool:
            return bool(r["gaps"] >= hi_min)

        result[f"strictness_{name}"] = {
            **_estimate(sub, high, rounds),
            "contributing_repos": contributing_repos(sub, high),
        }
    return result


def cmd_analyze(work: Path, rounds: int, max_files: int | None = None) -> dict[str, Any]:
    with rows_file(work, max_files).open(newline="", encoding="utf-8") as fh:
        rows = [
            {
                "repo": r["repo"],
                "language": r["language"],
                "gaps": int(r["gaps"]),
                "loc": int(r["loc"]),
                "evidence": int(r["evidence"]),
                "dynamism": int(r["dynamism"]),
                "fixes": int(r["fixes"]),
            }
            for r in csv.DictReader(fh)
        ]
    result = analyze_rows(rows, rounds)
    per_repo = {}
    for name in result["repos"]:
        rs = [r for r in rows if r["repo"] == name]
        per_repo[name] = analyze_rows(rs, rounds)
    result["per_repo"] = per_repo
    out_name = "analysis.json" if max_files is None else f"analysis-bulk{max_files}.json"
    (work / out_name).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def cmd_list() -> None:
    for name, e in PILOT_REPOS.items():
        print(f"{name:16s} burned={e['burned']!s:5s} pin={e['pin'] or 'mid-history'} {e['url']}")
    rows = sorted(LANGUAGE_STRICTNESS)
    print(f"{len(rows)} language rows; Irc/Ot for python:", strictness_constants("python"))


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["list", "clone", "scan", "label", "recall", "analyze"])
    ap.add_argument("repos", nargs="*", help="pilot repo names (default: all)")
    ap.add_argument("--work", type=Path, default=Path("/tmp/gitgalaxy-scratch/claude/outcome-pilot"))
    ap.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    ap.add_argument("--burned-only", action="store_true", help="only the burned mainframe estates")
    ap.add_argument(
        "--max-files-per-commit",
        type=int,
        default=None,
        help="bulk-commit guard for label/analyze: credit no file for a commit touching more scanned files than this",
    )
    ap.add_argument("--rounds", type=int, default=BOOTSTRAP_ROUNDS)
    args = ap.parse_args(argv)
    names = args.repos or [n for n, e in PILOT_REPOS.items() if e["burned"] or not args.burned_only]
    unknown = [n for n in names if n not in PILOT_REPOS]
    if unknown:
        ap.error(f"unknown pilot repo(s): {unknown}")
    if args.command == "list":
        cmd_list()
    elif args.command == "clone":
        cmd_clone(args.work, names)
    elif args.command == "scan":
        cmd_scan(args.work, names)
    elif args.command == "label":
        cmd_label(args.work, names, args.window_days, args.max_files_per_commit)
    elif args.command == "recall":
        print(json.dumps(cmd_recall(args.work, names, args.window_days), indent=2, sort_keys=True))
    else:
        print(json.dumps(cmd_analyze(args.work, args.rounds, args.max_files_per_commit), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
