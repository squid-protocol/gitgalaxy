#!/usr/bin/env python3
"""The local census run (#6064): the non-burned translation rate, measured on the owner box and published as counts only.

    python tests/tools/census_nightly.py [--dry-run] [--force] [--root DIR]

The nightly CI survey is `--no-census` by design: census clones never reach CI or a commit (blind-estate rule). This is
the local half, run by a systemd timer (docs/agents/census-nightly.md). One run:

  1. gate: box_status.py must say GREEN (else it exits 0, "skipped");
  2. once per main SHA per UTC day: a done-stamp under <scratch>/census-nightly/, and the SHA is skipped when the
     published census series already holds it;
  3. `equivalence_env.py --provision`, then `cics_census.py survey --baseline --jobs 2` under `nice -n 10`;
  4. one nightly history line (`history append --nightly`) into docs/language_status/blockers/census_history.jsonl,
     published to the `generated` branch through generated_branch.publish.

Only that history line is published: counts, the top gaps by key and the scope. Never blockers.txt / blockers.json
(program rows), a survey directory, a census path or a census repo name; `counts_only` refuses a line that carries one.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

import cics_census  # noqa: E402
import equivalence_env  # noqa: E402
import generated_branch  # noqa: E402

JOBS = 2
NICE = 10
STAMPS = "census-nightly"
HISTORY_KEYS = {"pr", "main_sha", "date", "whole", "total", "whole_burned", "total_burned", "whole_non_burned",
                "total_non_burned", "refused_whole", "top_gaps", "scope", "nightly", "note"}  # fmt: skip
GAP_KEYS = {"gap", "only", "only_burned", "only_non_burned", "refuses_program"}


def box_verdict() -> str:
    """box_status.py's verdict (GREEN / YELLOW / RED / UNKNOWN); anything it cannot say is UNKNOWN."""
    res = subprocess.run([sys.executable, str(TOOLS / "box" / "box_status.py"), "--json"],  # noqa: S603
                         capture_output=True, text=True, check=False)  # fmt: skip
    try:
        return str(json.loads(res.stdout)["verdict"])
    except (ValueError, KeyError, TypeError):
        return "UNKNOWN"


def counts_only(line: str, forbidden: list[str]) -> str | None:
    """None when the history line carries counts and gap keys only, else why it must not be published."""
    entry = json.loads(line)
    extra = set(entry) - HISTORY_KEYS
    if extra:
        return f"unexpected keys {sorted(extra)}"
    for g in entry.get("top_gaps", []):
        if set(g) - GAP_KEYS:
            return f"unexpected gap keys {sorted(set(g) - GAP_KEYS)}"
    low = line.lower()
    for bad in forbidden:
        if bad and bad.lower() in low:
            return "the line names a census path or repo"
    return None


def stamp_file(root: Path, sha: str) -> Path:
    return root / STAMPS / f"{time.strftime('%Y-%m-%d', time.gmtime())}-{sha}.done"


def survey_argv(sha: str, root: Path) -> list[str]:
    return ["nice", "-n", str(NICE), sys.executable, str(TOOLS / "cics_census.py"), "survey", "--baseline",
            "--jobs", str(JOBS), "--no-fetch", "--sha", sha, "--root", str(root)]  # fmt: skip


def run(args: argparse.Namespace) -> int:
    verdict = box_verdict()
    if verdict != "GREEN" and not args.force:
        print(f"skipped: box_status says {verdict}, the census run needs GREEN")
        return 0
    root = equivalence_env.scratch_root(args.root)
    sha = cics_census.resolve_sha(None, fetch=True)
    stamp = stamp_file(root, sha)
    if stamp.is_file() and not args.force:
        print(f"skipped: {sha[:12]} was already run today ({stamp.name})")
        return 0
    rel = cics_census.GENERATED_CENSUS_HISTORY
    forbidden = [str(root / "census"), *(r.split("/")[-1] for r in equivalence_env.census_repos())]
    with tempfile.TemporaryDirectory() as td:
        pub = Path(td)  # an empty clone-less repo: generated_branch fetches and pushes through its `origin`
        for argv in (["init", "-q"], ["remote", "add", "origin", cics_census._git("remote", "get-url", "origin")]):
            subprocess.run(["git", "-C", str(pub), *argv], check=True)  # noqa: S603, S607
        hist = pub / rel
        data = generated_branch.read_published(rel, pub)
        hist.parent.mkdir(parents=True)
        if data is not None:
            hist.write_bytes(data)
        if any(e["main_sha"] == sha for e in cics_census.read_history(hist)) and not args.force:
            print(f"skipped: the published census series already has {sha[:12]}")
            return 0
        prov = subprocess.run([sys.executable, str(TOOLS / "equivalence_env.py"), "--provision", "--root", str(root)],  # noqa: S603
                              check=False)  # fmt: skip
        if prov.returncode:
            print("census provisioning failed: nothing surveyed", file=sys.stderr)
            return 1
        res = subprocess.run(survey_argv(sha, root) + (["--force"] if args.force else []), check=False)  # noqa: S603
        if res.returncode:
            print(f"census survey exited {res.returncode}: nothing published", file=sys.stderr)
            return res.returncode
        d = cics_census.cache_dir(root, sha)
        if not json.loads((d / "meta.json").read_text(encoding="utf-8")).get("census"):
            print("the baseline of this SHA was surveyed without the census: nothing published", file=sys.stderr)
            return 1
        before = hist.read_text(encoding="utf-8") if hist.is_file() else ""
        rc = cics_census.append_history(hist, d, 0, args.note, nightly=True)
        if rc not in (0, 2):
            return rc
        line = hist.read_text(encoding="utf-8")[len(before) :].strip()
        if not line:  # rc 2: already in the series
            return 0
        why = counts_only(line, forbidden)
        if why:
            print(f"refusing to publish: {why}", file=sys.stderr)
            return 1
        if args.dry_run:
            print(f"dry run, not published: {line}")
            return 0
        commit = generated_branch.publish([rel], f"census nightly {sha[:12]}: counts only", root=pub)
        print(f"published {rel} to {generated_branch.BRANCH}: {commit}")
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(f"{sha}\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="survey and build the line, publish and stamp nothing")
    ap.add_argument("--force", action="store_true", help="ignore the box verdict, the stamp and the cached survey")
    ap.add_argument("--root", type=Path, help="the shared scratch root (default: $GG_SCRATCH, else _shared-scratch)")
    ap.add_argument("--note", help="a note for the history line")
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
