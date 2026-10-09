#!/usr/bin/env python3
"""#4270: the det sweep's coverage, committed -- so main can see it.

    python tests/tools/det_coverage_ledger.py update SWEEP [SWEEP ...]   # write tests/equivalence/det_sweep_coverage/<CASE>.json
    python tests/tools/det_coverage_ledger.py check  SWEEP [SWEEP ...]   # the ratchet CI's det-sweep applies
    python tests/tools/det_coverage_ledger.py migrate                    # #4731: add component fingerprints to current entries
    python tests/tools/det_coverage_ledger.py split --all | --base REV   # #4789: the retired single file -> per-case files

SWEEP is a `proof_sweep.py --det-only` work directory (or its sweep.json): per case the proof's coverage line,
"proven on N scenarios, covering P/L paragraphs and B/T branches". The ledger keeps those numbers for each PROVEN
case, keyed to the fingerprints of the inputs the COBOL-side coverage depends on (tests/tools/evidence.py's: the case
directory, the corpus pin, the harness, the oracle -- not the Java generator, which cannot change what the COBOL runs):

  {"format": "det-sweep-coverage/1", "about": ..., "cases": {CASE: {"scenarios": N,
     "paragraphs": {"covered": P, "live": L}, "branches": {"covered": B, "total": T},
     "inputs": {"case": SHA, "corpus": SHA, "harness": SHA, "oracle": SHA,
                "components": {"harness": {COMPONENT: SHA}, "oracle": {COMPONENT: SHA}}}}}}

#4731: `components` holds the fingerprints of the harness / oracle components the case uses (tests/tools/evidence.py
COMPONENTS: the CICS stub and equivalence_cics.py, the Db2 layer, batch file I/O, ...). An entry that has them is stale on
harness / oracle only when a component it uses changed; one written before them (no `components`) keeps the whole-input
comparison until `update` rewrites it, or `migrate` adds them while the entry is current on the whole input.

Every number in it is read off a sweep's coverage line, none is computed or written by hand. A reader
(proof_blockers.py) trusts an entry as CURRENT only while `fresh_coverage()`; a missing entry is "unknown". #4730: a
stale entry stays readable through `last_coverage()` (the evidence report shows it as the last measurement, marked
stale) unless a BLOCKING input (case, corpus) changed, which makes it unknown as before. `update` also records
`measured_at`, the commit the numbers were measured at. #4758: an entry exists only while the last sweep that ran its
case proved it (`update` drops the entry of a case a sweep ran and did not prove), so it is also the case's det verdict:
the evidence report reads a Db2 case's verdict from it (CI's per-PR det-sweep skips Db2; the scheduled evidence
refresh's db2 job sweeps them), current or stale like its coverage.

The check (run by `proof_sweep.py --aggregate` in CI's det-sweep, after the verdict ratchet): for every proven case
in the sweep, the ledger must hold its numbers. It FAILS on a missing entry, on numbers the sweep disagrees with, and on
a stale case / corpus fingerprint (the change that moved them re-proves the case: refresh); a stale harness / oracle
fingerprint only warns (a scheduled refresh), as evidence records do. It also fails on an entry for a case that does
not exist. A case the sweep proved with no coverage line cannot be checked and is reported.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

CASES = REPO / "tests" / "equivalence"
LEDGER_DIR = CASES / "det_sweep_coverage"  # #4789: one <CASE>.json per case
LEGACY = CASES / "det_sweep_coverage.json"  # the retired single file (det-sweep-coverage/1)
FORMAT = "det-sweep-coverage/2"
INPUTS = ("case", "corpus", "harness", "oracle")
COMPONENT_INPUTS = ("harness", "oracle")  # #4731: also fingerprinted per component (evidence.py COMPONENTS)
BLOCKING = ("case", "corpus")  # stale here: the change re-proves the case, so the ledger is refreshed in the same PR
_LINE = re.compile(r"proven on (\d+) scenarios?, covering (\d+)/(\d+) paragraphs and (\d+)/(\d+) branches")


def parse_line(line: str) -> dict[str, Any] | None:
    """A sweep row's coverage line -> the ledger's numbers (None for a case not proven or with no line)."""
    m = _LINE.search(line or "")
    if not m:
        return None
    n, pc, pl, bc, bt = (int(x) for x in m.groups())
    return {"scenarios": n, "paragraphs": {"covered": pc, "live": pl}, "branches": {"covered": bc, "total": bt}}


def fingerprints(case: str) -> dict[str, Any]:
    """The case's input fingerprints in the tree now (tests/tools/evidence.py's scheme), plus (#4731) under `components`
    the per-component fingerprints of the harness / oracle components the case uses."""
    import evidence as ev  # noqa: PLC0415 -- git-backed; only when a ledger is written / checked

    now = ev.compute_inputs(ev.equivalence_target(case))
    return {**{name: now[name]["sha256"] for name in INPUTS},
            "components": {name: now[name]["components"] for name in COMPONENT_INPUTS}}  # fmt: skip


def path_of(case: str, directory: Path | None = None) -> Path:
    """#4789: the file of a case's entry."""
    return (directory or LEDGER_DIR) / f"{case}.json"


def load(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    """{CASE: entry} from the per-case files (#4789); {} when there are none."""
    directory = directory or LEDGER_DIR
    out = {}
    for f in sorted(directory.glob("*.json")) if directory.is_dir() else ():
        entry = json.loads(f.read_text(encoding="utf-8"))
        entry.pop("format", None)
        out[f.stem] = entry
    return out


def render(entry: dict[str, Any]) -> str:
    """A case file's text: deterministic, so an unchanged entry is an unchanged file."""
    return json.dumps({"format": FORMAT, **entry}, indent=1) + "\n"


def stale(entry: dict[str, Any], now: dict[str, Any]) -> list[str]:
    """The inputs whose fingerprint differs from the tree's. #4731: a harness / oracle fingerprint that differs is stale
    only when a component the case uses changed (an entry written before components kept none: the whole input decides)."""
    held = entry.get("inputs") or {}
    out = []
    for n in INPUTS:
        if held.get(n) == now.get(n):
            continue
        before, after = (held.get("components") or {}).get(n), (now.get("components") or {}).get(n)
        if isinstance(before, dict) and isinstance(after, dict) and all(before.get(c) == v for c, v in after.items()):
            continue
        out.append(n)
    return out


def fresh_coverage(case: str, ledger: dict[str, dict[str, Any]]) -> tuple[int, int, int, int] | None:
    """(paragraphs covered, live, branches covered, total) of a case whose entry is fresh in the tree, else None."""
    last = last_coverage(case, ledger)
    return last["coverage"] if last and not last["stale_inputs"] else None


def measured_at(entry: dict[str, Any]) -> str | None:
    """The commit an entry was measured at: the `measured_at` recorded by `update` (None for an older entry)."""
    sha = entry.get("measured_at")
    return sha if isinstance(sha, str) and sha else None


def last_coverage(case: str, ledger: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """#4730: the case's LAST MEASURED coverage and whether it is still current, or None (no entry / no case).

    {"coverage": (P covered, live, B covered, total), "stale_inputs": [...], "blocking": bool, "measured_at": sha|None}.
    stale_inputs lists the changed fingerprints; `blocking` is True when a BLOCKING one (case, corpus) changed: that
    is a real change to the program, the numbers no longer describe it, and a reader must treat it as unknown. A
    stale harness / oracle only means "not re-checked since": the numbers are still the last measurement."""
    entry = ledger.get(case)
    if not entry or not (CASES / case / "case.json").is_file():
        return None
    try:
        bad = stale(entry, fingerprints(case))
    except (RuntimeError, KeyError, OSError):
        return None
    p, b = entry["paragraphs"], entry["branches"]
    return {"coverage": (p["covered"], p["live"], b["covered"], b["total"]), "stale_inputs": bad,
            "blocking": any(n in BLOCKING for n in bad), "measured_at": measured_at(entry)}  # fmt: skip


def sweep_rows(dirs: list[Path]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for d in dirs:
        f = d / "sweep.json" if d.is_dir() else d
        out.update(json.loads(f.read_text(encoding="utf-8")).get("det", {}))
    return out


def build(det: dict[str, dict[str, Any]], old: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """`old` with the entries of the sweep's proven cases rewritten, the entry of a case the sweep ran and did NOT prove
    dropped (#4758: an entry means its last sweep proved it, so the evidence report reads a Db2 case's verdict from it),
    the cases the sweep did not run kept (a push refresh skips Db2), and an entry for a case no longer in the tree
    dropped."""
    cases = {c: e for c, e in old.items() if (CASES / c / "case.json").is_file()}
    head = _head()
    for case, row in sorted(det.items()):
        if not row.get("proved"):
            cases.pop(case, None)
            continue
        nums = parse_line(row.get("coverage", ""))
        if nums is not None:
            cases[case] = {**nums, "inputs": fingerprints(case), **({"measured_at": head} if head else {})}
    return dict(sorted(cases.items()))


def check(det: dict[str, dict[str, Any]], ledger: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    """(problems, warnings) of the sweep against the ledger."""
    problems, warnings = [], []
    if LEGACY.exists():
        problems.append(legacy_problem())
    if _ignored(path_of("any-case")):
        problems.append(
            f"coverage ledger: {LEDGER_DIR.relative_to(REPO)}/*.json is git-ignored, so it cannot be committed"
        )
    fix = "python tests/tools/det_coverage_ledger.py update <the sweep's DIR(s)>"
    for case in sorted(ledger):
        if not (CASES / case / "case.json").is_file():
            problems.append(f"coverage ledger: {case}: no such case any more -- {fix}")
    for case, row in sorted(det.items()):
        if not row.get("proved"):
            continue
        nums = parse_line(row.get("coverage", ""))
        if nums is None:
            warnings.append(f"coverage ledger: {case}: proven with no coverage line; cannot be checked")
            continue
        entry = ledger.get(case)
        if entry is None:
            problems.append(f"coverage ledger: {case}: no entry -- {fix}")
            continue
        got = {k: entry.get(k) for k in nums}
        if got != nums:
            problems.append(f"coverage ledger: {case}: the sweep covered {_show(nums)}, the ledger has {_show(got)} "
                            f"-- coverage moved: if intended, {fix}")  # fmt: skip
        now = fingerprints(case)
        bad = stale(entry, now)
        if [n for n in bad if n in BLOCKING]:
            problems.append(f"coverage ledger: {case}: stale ({', '.join(bad)} changed) -- {fix}")
        elif bad:
            warnings.append(f"coverage ledger: {case}: stale ({', '.join(bad)} changed); refresh when convenient")
    return problems, warnings


def _head() -> str | None:
    """HEAD's sha: the commit a refreshed entry is measured at (#4730; the report's "stale since", never a date)."""
    import subprocess  # noqa: PLC0415

    r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],  # noqa: S603, S607
                       capture_output=True, text=True, check=False)  # fmt: skip
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def _ignored(path: Path) -> bool:
    """git would ignore the file (a `*.json` ignore rule once kept the ledger out of PR #4606)."""
    import subprocess  # noqa: PLC0415

    return subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", "--no-index", str(path)],  # noqa: S603, S607
                          capture_output=True, check=False).returncode == 0  # fmt: skip


SPLIT_RECIPE = (
    "the single-file coverage ledger tests/equivalence/det_sweep_coverage.json is retired (#4789: one file per case under "
    "tests/equivalence/det_sweep_coverage/). Move your branch's entries over: while merging origin/main (the modify/delete "
    "conflict), run\n"
    '    python tests/tools/det_coverage_ledger.py split --base "$(git merge-base HEAD MERGE_HEAD)"\n'
    "    git add -A tests/equivalence/det_sweep_coverage.json tests/equivalence/det_sweep_coverage/\n"
    '(after the merge is committed: --base "$(git merge-base HEAD^1 HEAD^2)"), or delete the file and re-run '
    "`det_coverage_ledger.py update <your sweep DIR(s)>`."
)


def legacy_problem() -> str:
    return f"coverage ledger: {SPLIT_RECIPE}"


def _show(n: dict[str, Any]) -> str:
    try:
        return (f"{n['scenarios']} scenarios, {n['paragraphs']['covered']}/{n['paragraphs']['live']} paragraphs, "
                f"{n['branches']['covered']}/{n['branches']['total']} branches")  # fmt: skip
    except (KeyError, TypeError):
        return "?"


def write(cases: dict[str, dict[str, Any]], directory: Path | None = None) -> list[str]:
    """Make the per-case files exactly `cases` (#4789): write a file only when its text changes, delete the file of a case
    not in `cases`. Returns the cases whose file changed."""
    directory = directory or LEDGER_DIR
    directory.mkdir(parents=True, exist_ok=True)
    changed = []
    for case, entry in sorted(cases.items()):
        f, text = path_of(case, directory), render(entry)
        if not f.is_file() or f.read_text(encoding="utf-8") != text:
            f.write_text(text, encoding="utf-8")
            changed.append(case)
    for f in sorted(directory.glob("*.json")):
        if f.stem not in cases:
            f.unlink()
            changed.append(f.stem)
    return changed


def legacy_cases(text: str) -> dict[str, dict[str, Any]]:
    """The entries of a det-sweep-coverage/1 single file."""
    return dict(json.loads(text).get("cases", {}))


def _show_at(rev: str, path: Path) -> str | None:
    import subprocess  # noqa: PLC0415

    r = subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:{path.relative_to(REPO).as_posix()}"],  # noqa: S603, S607
                       capture_output=True, text=True, check=False)  # fmt: skip
    return r.stdout if r.returncode == 0 else None


def split(base: str | None, legacy: Path | None = None, directory: Path | None = None) -> list[str]:
    """#4789: move the retired single file's entries into the per-case files, then delete it. Returns the cases changed.

    base None (`--all`): the per-case files become exactly the single file's entries (the one-shot migration; re-run it
    after merging a main that still changed the single file). base REV (`--base`): only the entries the single file
    changed since REV (added, rewritten or dropped) are applied to the per-case files; every other case keeps the file
    main has. That is the merge of a branch from before #4789: REV is the merge base, where the single file still
    existed, so the branch's own sweeps land and main's newer entries for other cases stay."""
    legacy = legacy or LEGACY
    if not legacy.is_file():
        raise SystemExit(f"split: no {legacy.relative_to(REPO)} -- nothing to move")
    mine = legacy_cases(legacy.read_text(encoding="utf-8"))
    if base is None:
        cases = mine
    else:
        text = _show_at(base, legacy)
        if text is None:
            raise SystemExit(f"split: {base} has no {legacy.relative_to(REPO)}: --base must be the merge base from BEFORE "
                             f"the merge (the commit your branch started from), where the single file still existed")  # fmt: skip
        then, cases = legacy_cases(text), load(directory)
        for case in sorted(set(mine) | set(then)):
            if mine.get(case) == then.get(case):
                continue
            if case in mine:
                cases[case] = mine[case]
            else:
                cases.pop(case, None)
    changed = write(cases, directory)
    legacy.unlink()
    return changed


def migrate(ledger: dict[str, dict[str, Any]], history: bool = True) -> dict[str, dict[str, Any]]:
    """#4731: `ledger` with the per-component fingerprints added to every entry that has none AND whose harness / oracle
    fingerprints equal the tree's (so those are the components it was measured against), or equal those of the commit it
    was `measured_at` (evidence_history.ledger_components). Nothing else changes; any other entry is left for the next
    sweep's `update`."""
    out = {}
    for case, entry in ledger.items():
        inputs = entry.get("inputs") or {}
        if "components" not in inputs and (CASES / case / "case.json").is_file():
            now = fingerprints(case)
            comps = now["components"] if all(inputs.get(n) == now[n] for n in INPUTS) else None
            if comps is None and history:  # the commit the entry was measured at, if its files reproduce the entry
                import evidence_history  # noqa: PLC0415

                comps = evidence_history.ledger_components(case, entry)
            if comps is not None:
                entry = {**entry, "inputs": {**inputs, "components": comps}}
        out[case] = entry
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("update", "check", "migrate", "split"))
    ap.add_argument("sweep", type=Path, nargs="*", help="proof_sweep.py work directories (or sweep.json files)")
    how = ap.add_mutually_exclusive_group()
    how.add_argument(
        "--all", action="store_true", help="split: every entry of the single file (the one-shot migration)"
    )
    how.add_argument("--base", metavar="REV", help="split: only the entries the single file changed since REV")
    args = ap.parse_args(argv)
    where = LEDGER_DIR.relative_to(REPO)
    if args.mode == "split":  # #4789
        if not (args.all or args.base):
            ap.error("split needs --all (the whole single file) or --base REV (only what your branch changed)")
        changed = split(None if args.all else args.base)
        print(f"{where}/: {len(changed)} case file(s) written or removed; {LEGACY.relative_to(REPO)} deleted -- now "
              f"git add -A {LEGACY.relative_to(REPO)} {where}/")  # fmt: skip
        return 0
    if LEGACY.exists() and args.mode in ("update", "migrate"):
        print(legacy_problem(), file=sys.stderr)
        return 1
    if args.mode == "migrate":  # #4731: no sweep needed
        old = load()
        cases = migrate(old)
        write(cases)
        print(f"{where}/: {sum(1 for c in cases if cases[c] != old[c])} of {len(cases)} entries migrated")
        return 0
    if not args.sweep:
        ap.error("update / check need the sweep's work directories")
    det = sweep_rows(args.sweep)
    if args.mode == "update":
        cases = build(det, load())
        changed = write(cases)
        print(f"{where}/: {len(cases)} cases, {len(changed)} file(s) written or removed")
        return 0
    problems, warnings = check(det, load())
    for w in warnings:
        print(f"warning: {w}")
    for p in problems:
        print(p)
    print("coverage ledger: as expected" if not problems else f"coverage ledger: {len(problems)} unexpected")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
