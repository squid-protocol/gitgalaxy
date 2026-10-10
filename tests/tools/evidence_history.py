#!/usr/bin/env python3
r"""
#4731: the evidence fingerprints at an earlier commit -- to measure the component fingerprints, and to migrate with them.

    python tests/tools/evidence_history.py replay [--merges 30] [--ref origin/main] [--json]
        For each of the last N commits on REF (first parent: the merged PRs) that touched tests/tools or the Java
        generator, how many evidence records, and how many det-coverage ledger entries, that change made stale on the
        harness / oracle / generator -- BEFORE (one fingerprint per input: any byte moved) and AFTER (per component: only
        a component the case uses). Each record is taken as proven at the PR's parent, which is what a refresh leaves.

`components_from_history` is what `evidence.py migrate` uses for a record that is stale on the whole input: it finds the
commit whose tree reproduces the record's stored whole-input fingerprint byte for byte (so the record WAS proven against
those files) and returns the component fingerprints of that tree. Nothing is guessed: no commit reproduces it, no
migration.

Targets are the committed ports of the tree now (their kind, Db2 flag and component usage as now), judged against the
files of each commit; a port added or removed between the two commits is not counted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence as ev  # noqa: E402

DIRS = ("tests/tools", "tests/equivalence", "tests/cics_crucible", "gitgalaxy/tools/cobol_to_java")
# what the fingerprints cover: a commit that touches none of these cannot move a harness / oracle / generator one
WATCHED = ("tests/tools", "tests/equivalence", "gitgalaxy/tools/cobol_to_java")
LEDGER_DIR = "tests/equivalence/det_sweep_coverage/"  # #4789: one <CASE>.json per case
LEDGER_PATH = "tests/equivalence/det_sweep_coverage.json"  # the single file it replaced (commits before #4789)


class Tree:
    """The files of a commit under DIRS: their paths and, read once per blob, their bytes."""

    _blobs: dict[str, bytes] = {}

    def __init__(self, commit: str) -> None:
        out = ev._git("ls-tree", "-r", "-z", commit, "--", *DIRS)
        if out is None:
            raise RuntimeError(f"no such commit {commit}")
        self.commit = commit
        self.sha: dict[str, str] = {}
        for row in filter(None, out.split("\0")):
            meta, _, path = row.partition("\t")
            self.sha[path] = meta.split()[2]
        self.files = tuple(sorted(self.sha))

    def read(self, path: str) -> bytes:
        blob = self.sha[path]
        if blob not in Tree._blobs:
            Tree._blobs[blob] = ev._git("cat-file", "blob", blob, binary=True) or b""
        return Tree._blobs[blob]

    def ledger(self) -> dict[str, Any]:
        """{CASE: entry} of the det-coverage ledger at this commit: the per-case files (#4789), else the single file."""
        out = {}
        for path in self.files:
            if path.startswith(LEDGER_DIR) and path.endswith(".json") and "/" not in path[len(LEDGER_DIR) :]:
                entry = json.loads(self.read(path).decode())
                entry.pop("format", None)
                out[path[len(LEDGER_DIR) : -len(".json")]] = entry
        if out or LEDGER_PATH not in self.sha:
            return out
        return dict(json.loads(self.read(LEDGER_PATH).decode()).get("cases", {}))


def _only(t: ev.Target) -> ev.Target:
    """The target with just the specs a replay needs: harness, oracle, generator (and the port, which decides usage)."""
    keep = (*ev.COMPONENT_INPUTS, "port")
    return ev.Target(**{**t.__dict__, "specs": {k: v for k, v in t.specs.items() if k in keep}})


def fingerprints(t: ev.Target, tree: Tree) -> dict[str, Any]:
    """The harness / oracle / generator fingerprints (whole and per component) of `t` in `tree`."""
    got = ev.spec_inputs(_only(t), tree.files, tree.read)
    return {k: got[k] for k in ev.COMPONENT_INPUTS}


def components_from_history(
    t: ev.Target, rec: dict[str, Any], names: list[str], limit: int = 200
) -> dict[str, dict[str, str]]:
    """{input: components} for the `names` inputs of `rec` whose stored whole-input fingerprint some commit's files
    reproduce (the commit the proof ran against, or an earlier / later main commit with the same bytes); the inputs no
    commit reproduces are left out. Newest commit first, `limit` commits that touched the inputs' files."""
    want = {n: (rec["inputs"].get(n) or {}).get("sha256") for n in names}
    found: dict[str, dict[str, str]] = {}
    head = str((rec.get("proof") or {}).get("harness_commit", "")).split("+")[0]
    log = ev._git("log", "-n", str(limit), "--format=%H", "--", *WATCHED) or ""
    for commit in dict.fromkeys([c for c in [head, *log.split()] if c]):
        if all(n in found for n in want):
            break
        try:
            tree = Tree(commit)
        except RuntimeError:
            continue
        fp = fingerprints(t, tree)
        for n, sha in want.items():
            if n not in found and sha and fp[n]["sha256"] == sha:
                found[n] = fp[n]["components"]
    return found


def ledger_components(case: str, entry: dict[str, Any]) -> dict[str, dict[str, str]] | None:
    """A det-coverage ledger entry's component fingerprints, from the commit it was measured at: only when that commit's
    files reproduce the entry's stored harness and oracle fingerprints (else None: left for the next sweep)."""
    commit = entry.get("measured_at")
    if not isinstance(commit, str):
        return None
    try:
        fp = fingerprints(ev.equivalence_target(case), Tree(commit))
    except (RuntimeError, KeyError, OSError):
        return None
    held = entry.get("inputs") or {}
    if any(fp[n]["sha256"] != held.get(n) for n in ("harness", "oracle")):
        return None
    return {n: fp[n]["components"] for n in ("harness", "oracle")}


# ---- the replay ----------------------------------------------------------------------------------------------------
def _stale_inputs(before: dict[str, Any], after: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(whole-input, per-component) lists of the inputs a change from `before` to `after` stales."""
    old = [n for n in ev.COMPONENT_INPUTS if before[n]["sha256"] != after[n]["sha256"]]
    new = ev.changed(before, after, ev.COMPONENT_INPUTS)
    return old, new


def replay(ref: str, merges: int) -> dict[str, Any]:
    import det_coverage_ledger as dcl  # noqa: PLC0415 -- (its fingerprint scheme, judged on the historical trees)

    log = ev._git("log", "--first-parent", "-n", str(merges), "--format=%H%x09%h%x09%s", ref, "--", *WATCHED) or ""
    targets = ev.targets()
    rows = []
    for line in log.strip().splitlines():
        commit, short, subject = line.split("\t", 2)
        parent = (ev._git("rev-parse", f"{commit}^") or "").strip()
        if not parent:
            continue
        a, b = Tree(parent), Tree(commit)
        led_a = a.ledger()
        old_recs, new_recs, old_led, new_led, by_input = [], [], [], [], {n: [0, 0] for n in ev.COMPONENT_INPUTS}
        for t in targets:
            rel = ev.rel_path(t.record)
            if rel not in a.sha or rel not in b.sha:
                continue
            fa, fb = fingerprints(t, a), fingerprints(t, b)
            old, new = _stale_inputs(fa, fb)
            old_recs += [t.key] if old else []
            new_recs += [t.key] if new else []
            for n in old:
                by_input[n][0] += 1
            for n in new:
                by_input[n][1] += 1
        for case in sorted(led_a):  # the det-coverage ledger: every case it holds (most have no committed port)
            if f"tests/equivalence/{case}/case.json" not in a.sha or f"tests/equivalence/{case}/case.json" not in b.sha:
                continue
            t = ev.equivalence_target(case)
            fa, fb = fingerprints(t, a), fingerprints(t, b)
            ea = {n: fa[n]["sha256"] for n in dcl.COMPONENT_INPUTS}
            eb = {n: fb[n]["sha256"] for n in dcl.COMPONENT_INPUTS}
            entry = {"inputs": {**ea, "case": "x", "corpus": "x", "components": {n: fa[n]["components"] for n in ea}}}
            now = {**eb, "case": "x", "corpus": "x", "components": {n: fb[n]["components"] for n in eb}}
            old_led += [case] if ea != eb else []
            new_led += [case] if dcl.stale(entry, now) else []
        rows.append({"commit": short, "subject": subject[:90], "records_before": len(old_recs),
                     "records_after": len(new_recs), "ledger_before": len(old_led), "ledger_after": len(new_led),
                     "by_input": {n: {"before": v[0], "after": v[1]} for n, v in by_input.items()},
                     "records_after_keys": sorted(new_recs)})  # fmt: skip
    return {"ref": ref, "records": len(targets), "rows": rows,
            "total": {k: sum(r[k] for r in rows)
                      for k in ("records_before", "records_after", "ledger_before", "ledger_after")}}  # fmt: skip


def table(rep: dict[str, Any]) -> str:
    out = [
        f"{len(rep['rows'])} merges on {rep['ref']} touching tests/tools or the Java generator; "
        f"{rep['records']} evidence records. Stale on harness / oracle / generator after each PR:",
        "",
        "| commit | records before | records after | ledger before | ledger after | subject |",
        "|---|---|---|---|---|---|",
    ]
    for r in rep["rows"]:
        out.append(
            f"| {r['commit']} | {r['records_before']} | {r['records_after']} | {r['ledger_before']} | "
            f"{r['ledger_after']} | {r['subject']} |"
        )
    t = rep["total"]
    out.append(
        f"| **total** | **{t['records_before']}** | **{t['records_after']}** | **{t['ledger_before']}** | "
        f"**{t['ledger_after']}** | |"
    )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("replay")
    r.add_argument("--merges", type=int, default=30)
    r.add_argument("--ref", default="origin/main")
    r.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rep = replay(args.ref, args.merges)
    print(json.dumps(rep, indent=1) if args.json else table(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
