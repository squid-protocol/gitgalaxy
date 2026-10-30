#!/usr/bin/env python3
"""#4628: mutation testing of the DET ports, and every survivor accounted for (evidence level L5, #4601).

The evidence ladder's L5 (owner decision on #4601, 2026-10-07) is "L4 + every surviving mutant accounted for":
`tests/tools/mutation.py` (#4047) run on the deterministic translator's port of a case -- the same operators, fast
mode and seeded sample -- and each mutant the proof does not kill either killed by a strengthened scenario or stated
`equivalent` / `unreachable` with its reason, reviewed by the owner (the #4602 pattern).

    python tests/tools/det_mutation.py run CASE [CASE ...] --work DIR [--sample 150] [--seed 0] [--jobs 3]
    python tests/tools/det_mutation.py record CASE RUN_DIR PORT_DIR      # a mutation.py run dir -> the ledger
    python tests/tools/det_mutation.py refresh [CASE ...] --work DIR     # an input moved: same port? carry the verdicts
        [--run-moved [--budget-min N]]                                   # ... and `run` the ports that moved (#5862)
    python tests/tools/det_mutation.py check                             # the ledgers' form and the claims
    python tests/tools/det_mutation.py stale-check [--vs REF]            # exit 1: a ledger an input moved (the PR's cases)
    python tests/tools/det_mutation.py table [CASE ...]                  # per program, as the PR table
    python tests/tools/det_mutation.py survivors [CASE ...]              # the survivors and their stated verdicts
    python tests/tools/det_mutation.py state CASE TRIAGE.json            # {id: {verdict, reason}} -> the list

Two committed directories, one <CASE>.json per case in each (two PRs measuring different cases never collide):

  tests/equivalence/det_mutation/ -- written only by `run` / `record` / `refresh`: per case the run's counts,
    every judged mutant's verdict, the survivors in full, and the fingerprints of what the score depends on: the det
    port's own files (`port`), the case, the corpus pin, the harness and the oracle (tests/tools/evidence.py's), and
    the Java generator (`generator`), the cheap stand-in for the port: a reader cannot translate. An entry is
    trusted while the inputs that decide the score match the tree (`BLOCKING`: the case, the corpus pin and the
    survivors list; the det port's bytes are checked by `refresh`, which translates); stale or missing is unknown
    (`status` returns None). The generator, harness and oracle (`INFO`) are whole-tree hashes: their drift alone
    does not stale an entry (owner 2026-10-23, #5862), it is recorded and shown. `refresh` translates the case again
    and, when the port is byte-identical, renews the fingerprints (a case / corpus / survivors move re-runs only
    the recorded survivors, same seed, and carries the rest); a port whose bytes moved marks the entry stale
    (`port`) until `run` records it again.

  tests/equivalence/det_mutation_survivors/ -- written by a person: per case, a surviving mutant (by id, with
    the Java line before / after) and its verdict, `equivalent` (the change cannot alter anything the program
    shows: an initial value overwritten before use, a pad the field's width truncates) or `unreachable` (no input
    gets there: an entry point the case's kind never calls is out of scope already; this is code after a transfer,
    a guard every path has satisfied), and the reason. Proposed in the PR, reviewed by the owner.

    A run that KILLS a stated mutant fails (`record` exits 1 and `check` fails): the claim was wrong, the entry goes.

Scope (`SCOPE`): a det port's service file carries every entry point the translator writes; the ones the case's kind
never calls (a CICS program's runProgram / runBatch) are left out before sampling and counted as out of scope.
The cobolrt runtime is never mutated (tests/cobol_mainframe/test_cobolrt.py checks it against GnuCOBOL).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

CASES = REPO / "tests" / "equivalence"
LEDGER_DIRS = {"det_mutation", "det_mutation_survivors"}  # under CASES but not cases
LEDGER = CASES / "det_mutation"  # one <CASE>.json per case (like det_sweep_coverage/, #4789: PRs do not collide)
SURVIVORS = CASES / "det_mutation_survivors"  # one <CASE>.json per case
FORMAT = "det-mutation/1"
SURVIVORS_FORMAT = "det-mutation-survivors/1"
INPUTS = ("port", "generator", "case", "corpus", "harness", "oracle", "survivors")
# what decides a recorded score: a moved one makes the entry stale. The generator / harness / oracle fingerprints are
# whole-tree hashes kept as information (`drifted`); the port's bytes are what they could change, checked by `refresh`
BLOCKING = ("case", "corpus", "survivors")
INFO = ("generator", "harness", "oracle")
VERDICTS = {
    "equivalent": "the change cannot alter anything the program shows (output, screen, files, COMMAREA, abend)",
    "unreachable": "no input of the program reaches the changed code",
    # triaged but NOT accounted for: the survivor is a real weakness of the proof, kept with what would kill it
    "harness-gap": "the change alters behaviour the proof runs but does not compare (open: the harness must)",
    "case-gap": "an input the case lacks would kill it (open: strengthen the case)",
}
ACCOUNTED = ("equivalent", "unreachable")
FILES = "service/*.java"  # the translated program(s); never the cobolrt runtime
# entry points the case's kind never calls: their mutants are out of scope (not sampled, not scored)
SCOPE = {"cics": ("runProgram", "runBatch", "dd"), "batch": ("runTask", "handleTransaction", "handleLink"),
         "call": ("runTask", "handleTransaction", "handleLink", "runBatch", "dd")}  # fmt: skip
ABOUT = ("#4628: mutation testing of each det port (tests/tools/mutation.py on `det_port.py run --translate-only`'s "
         "port, fast mode, seeded sample), written only by tests/tools/det_mutation.py. An entry is trusted only while "
         "its fingerprints match the tree; stale or missing is unknown. Survivors are accounted for in "
         "det_mutation_survivors/ (reviewed).")  # fmt: skip
SURVIVORS_ABOUT = ("#4628: each surviving det-port mutant stated `equivalent` or `unreachable`, with the Java change and "
                   "why it cannot alter observable behaviour; proposed in a PR, reviewed by the owner. A run that kills a "
                   "stated mutant fails (the claim was wrong). Ids are mutation.py's; before / after are the Java line.")  # fmt: skip


# ---- the det port and its fingerprints ------------------------------------------------------------------------------
def port_sha(port: Path) -> str:
    """sha256 over the det port's .java files (path \\0 bytes \\0, sorted): the port the mutants were cut from."""
    h = hashlib.sha256()
    for f in sorted(port.rglob("*.java")):
        h.update(f.relative_to(port).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def fingerprints(case: str) -> dict[str, Any]:
    """The case's inputs in the tree now, but `port` (the det port is not committed: `port_sha`): per input its
    sha256 and, for the harness / oracle / generator, the per-component fingerprints of what the case's target uses
    (evidence.py's, #4731)."""
    import evidence as ev  # (git-backed: only when a ledger is written / read)

    now = ev.compute_inputs(ev.equivalence_target(case))
    out = {name: {k: now[name][k] for k in ("sha256", "components") if k in now[name]} for name in INPUTS
           if name not in ("port", "survivors")}  # fmt: skip
    out["survivors"] = {"sha256": survivors_sha(case)}
    return out


def survivors_sha(case: str) -> str:
    """sha256 of the case's stated survivors (the reviewed list), canonical JSON: a hand edit moves it."""
    body = json.dumps(load_survivors().get(case, []), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _sha(v: Any) -> Any:
    return v.get("sha256") if isinstance(v, dict) else v


def _moved(entry: dict[str, Any], now: dict[str, Any], names: tuple[str, ...]) -> list[str]:
    """The `names` inputs whose fingerprint differs from the tree's. As for an evidence record (#4731), an input whose
    components the entry stores differs only when a component the case's target uses changed. An input the entry
    never recorded (a ledger older than the `survivors` fingerprint) is not counted."""
    import evidence as ev

    held = entry.get("inputs") or {}
    comps = entry.get("components") or {}
    out = []
    for n in names:
        if n not in held or held[n] == _sha(now.get(n)):
            continue
        cur = now.get(n)
        moved = (ev.component_changed({"components": comps[n]}, cur)
                 if n in comps and isinstance(cur, dict) else None)  # fmt: skip
        if moved is None or moved:
            out.append(n)
    return out


def stale(entry: dict[str, Any], now: dict[str, Any]) -> list[str]:
    """The inputs that make the entry stale (#5862): a `BLOCKING` one (case, corpus, survivors list) whose fingerprint
    differs from the tree's, or `port` when `refresh` found the det port's bytes moved. The generator, harness and
    oracle alone never stale it (`drifted`): `refresh` compares the port's bytes, which is what they could change."""
    return _moved(entry, now, BLOCKING) + (["port"] if entry.get("port_moved") else [])


def drifted(entry: dict[str, Any], now: dict[str, Any]) -> list[str]:
    """The `INFO` inputs (generator, harness, oracle) that differ from the tree's: recorded, not staling (#5862)."""
    return _moved(entry, now, INFO)


def case_kind(case: str) -> str:
    return str(json.loads((CASES / case / "case.json").read_text(encoding="utf-8")).get("kind", "batch"))


def member_spans(text: str, names: tuple[str, ...]) -> list[tuple[int, int]]:
    """(first line, last line), 1-based, of each class member named in `names` (a method: its signature to its
    closing brace)."""
    import mutation as mu

    mask, _ = mu.code_mask(text)
    spans = []
    for m in re.finditer(r"(?m)^    (?:public|private|protected)[^;{=\n]*?\b(\w+)\(", text):
        if m.group(1) not in names:
            continue
        open_at = next((k for k in range(m.end(), len(text)) if mask[k] and text[k] == "{"), None)
        if open_at is None:
            continue
        depth, end = 0, None
        for k in range(open_at, len(text)):
            if not mask[k]:
                continue
            depth += {"{": 1, "}": -1}.get(text[k], 0)
            if depth == 0:
                end = k
                break
        if end is not None:
            spans.append((text.count("\n", 0, m.start()) + 1, text.count("\n", 0, end) + 1))
    return spans


def scope_filter(kind: str, port: Path) -> Callable[[list[Any]], list[Any]]:
    """mutation.run's `select`: drops the mutants inside the entry points `kind` never calls."""
    names = SCOPE.get(kind, ())
    spans = {f.relative_to(port).as_posix(): member_spans(f.read_text(encoding="utf-8"), names)
             for f in port.glob(FILES)}  # fmt: skip

    def select(mutants: list[Any]) -> list[Any]:
        return [m for m in mutants if not any(a <= m.line <= b for a, b in spans.get(m.file, []))]

    return select


# ---- the ledgers -----------------------------------------------------------------------------------------------------
def load(path: Path = LEDGER) -> dict[str, dict[str, Any]]:
    """{case: ledger entry}, from path/<CASE>.json."""
    out = {}
    for f in sorted(path.glob("*.json")) if path.is_dir() else []:
        out[f.stem] = json.loads(f.read_text(encoding="utf-8"))["entry"]
    return out


def load_survivors(path: Path = SURVIVORS) -> dict[str, list[dict[str, Any]]]:
    """{case: stated survivors}, from path/<CASE>.json."""
    out = {}
    for f in sorted(path.glob("*.json")) if path.is_dir() else []:
        out[f.stem] = json.loads(f.read_text(encoding="utf-8"))["survivors"]
    return out


def write(case: str, entry: dict[str, Any], path: Path = LEDGER) -> None:
    """The case's ledger entry, as path/<CASE>.json."""
    path.mkdir(parents=True, exist_ok=True)
    body = {"format": FORMAT, "issue": "#4628", "about": ABOUT, "case": case, "entry": entry}
    (path / f"{case}.json").write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")


def write_survivors(case: str, entries: list[dict[str, Any]], path: Path = SURVIVORS) -> None:
    """The case's reviewed survivors, as path/<CASE>.json (removed when none is left)."""
    f = path / f"{case}.json"
    if not entries:
        f.unlink(missing_ok=True)
        return
    path.mkdir(parents=True, exist_ok=True)
    body = {"format": SURVIVORS_FORMAT, "issue": "#4628", "about": SURVIVORS_ABOUT, "verdicts": VERDICTS,
            "case": case, "survivors": entries}  # fmt: skip
    f.write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def stated(case: str, survivors: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, dict[str, Any]]:
    """The case's stated survivors, by mutant id."""
    return {e["id"]: e for e in (load_survivors() if survivors is None else survivors).get(case, [])}


def entry_from_run(case: str, run: dict[str, Any], port: Path, out_of_scope: int) -> dict[str, Any]:
    """A ledger entry from mutation.py's mutation.json (`run`) for the det port `port`."""
    import evidence as ev

    results = run["results"]
    now = fingerprints(case)
    by = {v: [r for r in results if r["verdict"] == v] for v in ("killed", "timeout", "survived", "stillborn",
                                                                  "error", "pending")}  # fmt: skip
    return {
        "program": run.get("program"),
        "commit": ev.harness_commit(),
        "date": datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        "mode": run.get("mode"),
        "seed": run.get("seed"),
        "mutants": run["mutants"],
        "out_of_scope": out_of_scope,
        "chosen": run["chosen"],
        "coverage": run.get("coverage"),
        "counts": {v: len(rs) for v, rs in by.items()},
        "killed": sorted(r["id"] for r in by["killed"] + by["timeout"]),
        "stillborn": sorted(r["id"] for r in by["stillborn"]),
        "survived": [{k: r[k] for k in ("id", "op", "file", "line", "before", "after")} for r in by["survived"]],
        "inputs": {"port": port_sha(port), **{n: v["sha256"] for n, v in now.items()}},
        "components": {n: v["components"] for n, v in now.items() if "components" in v},
    }


def refuted(case: str, entry: dict[str, Any], survivors: dict[str, list[dict[str, Any]]] | None = None) -> list[str]:
    """The stated `equivalent` / `unreachable` mutants of `case` the entry's run killed: wrong claims. (A killed
    `case-gap` / `harness-gap` entry is the gap closed: its entry is simply removed.)"""
    killed = set(entry.get("killed", []))
    return sorted(i for i, e in stated(case, survivors).items() if i in killed and e.get("verdict") in ACCOUNTED)


def account(case: str, entry: dict[str, Any], survivors: dict[str, list[dict[str, Any]]] | None = None
            ) -> tuple[list[str], list[str]]:  # fmt: skip
    """(accounted, unaccounted) survivor ids of the entry: a survivor is accounted for by a stated `equivalent` /
    `unreachable` entry with its id and the same Java line before / after (a `harness-gap` / `case-gap` entry is
    triaged, not accounted for)."""
    st = stated(case, survivors)
    ok, open_ = [], []
    for s in entry.get("survived", []):
        e = st.get(s["id"])
        same = e and e.get("before") == s["before"] and e.get("after") == s["after"]
        (ok if same and e["verdict"] in ACCOUNTED else open_).append(s["id"])
    return ok, open_


def summary(case: str, entry: dict[str, Any], survivors: dict[str, list[dict[str, Any]]] | None = None
            ) -> dict[str, Any]:  # fmt: skip
    c = entry["counts"]
    caught = c.get("killed", 0) + c.get("timeout", 0)
    survived = c.get("survived", 0)
    ok, open_ = account(case, entry, survivors)
    judged = caught + survived
    return {"case": case, "program": entry.get("program"), "score": round(caught / judged, 4) if judged else None,
            "killed": caught, "survived": survived, "stillborn": c.get("stillborn", 0), "error": c.get("error", 0),
            "pending": c.get("pending", 0), "accounted": len(ok), "unaccounted": len(open_),
            "chosen": entry.get("chosen"), "mutants": entry.get("mutants"), "seed": entry.get("seed"),
            "refuted": refuted(case, entry, survivors),
            "l5": bool(judged) and not open_ and not c.get("pending") and not c.get("error")
                  and not refuted(case, entry, survivors)}  # fmt: skip


def measured(case: str, program: str | None = None) -> dict[str, Any] | None:
    """The case's det-port mutation result, fresh or stale, or None (no entry, or the entry is another program's):
    `summary`'s keys plus `current` (every fingerprint matches the tree) and `stale_inputs` (the ones that moved;
    ["unknown"] when the fingerprints cannot be computed); `drifted` (only when non-empty) lists the generator /
    harness / oracle inputs that differ from the tree, which do not stale it (#5862)."""
    entry = load().get(case)
    if not entry or not (CASES / case / "case.json").is_file():
        return None
    if program and entry.get("program") and str(entry["program"]).upper() != program.upper():
        return None
    info: list[str] = []
    try:
        now = fingerprints(case)
        moved, info = stale(entry, now), drifted(entry, now)
    except (RuntimeError, KeyError, OSError):
        moved = ["unknown"]
    return {**summary(case, entry), "current": not moved, "stale_inputs": moved, **({"drifted": info} if info else {})}


def status(case: str, program: str | None = None) -> dict[str, Any] | None:
    """The evidence report's L5 hook (#4603): the case's det-port mutation result while its ledger entry is fresh
    (the case, corpus and survivors list unchanged and the port not found moved; #5862), else None (missing, stale, or for another program). Keys: score (caught / judged, 0-1), killed (killed +
    timeout), survived, stillborn, accounted / unaccounted (survivors with / without a reviewed verdict), chosen /
    mutants / seed (the sample), refuted (stated mutants the run killed), and l5: every survivor accounted for, no
    error, no refuted claim."""
    s = measured(case, program)
    return s if s and s["current"] else None


def describe(s: dict[str, Any] | None) -> str:
    """One line for a report: the raw score beside the accounting (the owner's rule: the raw score always shows). A
    stale result (`measured`'s) is shown as the last measurement, marked stale."""
    if s is None:
        return "not measured (no det_mutation/ entry)"
    score = f"{100 * s['score']:.0f}%" if s["score"] is not None else "n/a"
    acc = (f"every survivor accounted for ({s['accounted']})" if s["l5"]
           else f"{s['unaccounted']} of {s['survived']} survivors unaccounted"
           + (f", {len(s['refuted'])} stated claims refuted" if s["refuted"] else ""))  # fmt: skip
    line = (f"raw {score} ({s['killed']}/{s['killed'] + s['survived']} caught; {s['chosen']} of {s['mutants']} "
            f"mutants, seed {s['seed']}); {acc}")  # fmt: skip
    if s.get("current") is False:
        line = f"stale ({', '.join(s['stale_inputs'])} moved), last measured: {line}"
    elif s.get("drifted"):
        line += f" (recorded {', '.join(s['drifted'])} differ from the tree; the port's bytes are checked by refresh)"
    return line


# ---- the checks ------------------------------------------------------------------------------------------------------
def _tracked(path: Path) -> bool:
    return subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", str(path)],  # noqa: S603, S607
                          capture_output=True, check=False).returncode == 0  # fmt: skip


def problems_in_survivors(survivors: dict[str, list[dict[str, Any]]]) -> list[str]:
    out = []
    for case, entries in sorted(survivors.items()):
        if not (CASES / case / "case.json").is_file():
            out.append(f"det mutation survivors: {case}: no such case")
        seen = set()
        for e in entries:
            missing = [
                f for f in ("id", "op", "line", "before", "after", "verdict", "reason") if e.get(f) in (None, "")
            ]
            if missing:
                out.append(f"det mutation survivors: {case}: an entry lacks {', '.join(missing)}: {e.get('id')}")
                continue
            if e["verdict"] not in VERDICTS:
                out.append(f"det mutation survivors: {case}: {e['id']}: unknown verdict {e['verdict']!r}")
            if e["id"] in seen:
                out.append(f"det mutation survivors: {case}: {e['id']} listed twice")
            seen.add(e["id"])
    return out


def check(ledger: dict[str, dict[str, Any]] | None = None, survivors: dict[str, list[dict[str, Any]]] | None = None,
          tracked: bool = True) -> tuple[list[str], list[str]]:  # fmt: skip
    """(problems, warnings): the files committed, the survivor list's form, and every stated claim against the
    ledger: a stated mutant the ledger's run killed fails; one the run did not judge (another sample, a changed
    port) warns."""
    ledger = load() if ledger is None else ledger
    survivors = load_survivors() if survivors is None else survivors
    problems: list[str] = []
    warnings: list[str] = []
    if tracked:
        files = [LEDGER / f"{c}.json" for c in ledger] + [SURVIVORS / f"{c}.json" for c in survivors]
        problems += [f"det mutation: {f.relative_to(REPO)} is not a committed file (git-ignored?)" for f in files
                     if not f.is_file() or not _tracked(f)]  # fmt: skip
    problems += problems_in_survivors(survivors)
    for case in sorted(ledger):
        if not (CASES / case / "case.json").is_file():
            problems.append(f"det mutation: {case}: no such case any more")
    for case, entries in sorted(survivors.items()):
        entry = ledger.get(case)
        if entry is None:
            warnings.append(f"det mutation survivors: {case}: stated, but no run in the ledger")
            continue
        for i in refuted(case, entry, survivors):
            problems.append(f"det mutation survivors: {case}: {i} is stated {stated(case, survivors)[i]['verdict']}, "
                            f"but the run killed it: the claim is wrong -- remove the entry and say why in the PR")  # fmt: skip
        judged = {s["id"]: s for s in entry.get("survived", [])}
        for e in entries:
            s = judged.get(e["id"])
            if s is None and e["id"] in entry.get("killed", []) and e.get("verdict") not in ACCOUNTED:
                warnings.append(f"det mutation survivors: {case}: {e['id']} ({e['verdict']}) is killed now: drop it")
            elif s is None and e["id"] not in entry.get("killed", []):
                warnings.append(f"det mutation survivors: {case}: {e['id']} not judged by the ledger's run")
            elif s is not None and (s["before"], s["after"]) != (e["before"], e["after"]):
                problems.append(f"det mutation survivors: {case}: {e['id']}: the stated line differs from the run's")
    return problems, warnings


# ---- running ---------------------------------------------------------------------------------------------------------
def translate(cases: list[str], work: Path) -> Path:
    """The det ports of `cases`, translated by this checkout (det_port.py run --translate-only) under work/det."""
    det = work / "det"
    argv = [sys.executable, str(TOOLS / "det_port.py"), "run", *cases, "--translate-only", "--work", str(det)]
    subprocess.run(argv, cwd=REPO, check=True)  # noqa: S603
    return det


def record(case: str, run_dir: Path, port: Path) -> int:
    """Write the case's ledger entry from a mutation.py run directory; 1 when the run killed a stated mutant."""
    import mutation as mu

    run = json.loads((run_dir / "mutation.json").read_text(encoding="utf-8"))
    every = mu.all_mutants(port, set(mu.OPERATORS), FILES)
    in_scope = scope_filter(case_kind(case), port)(every)
    entry = entry_from_run(case, run, port, len(every) - len(in_scope))
    import tempfile

    try:
        import fcntl  # (POSIX; two runs recording at once must not lose an entry)
    except ImportError:  # Windows: no concurrent runs there, write unlocked
        fcntl = None
    with (Path(tempfile.gettempdir()) / "gitgalaxy-det-mutation.lock").open("w") as lock:
        if fcntl is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)
        write(case, entry)
    s = summary(case, entry)
    print(_row(s))
    for i in s["refuted"]:
        print(f"{case}: {i} is stated {stated(case)[i]['verdict']} but this run killed it: the claim is wrong")
    return 1 if s["refuted"] else 0


def run(cases: list[str], work: Path, sample: int | None, seed: int, jobs: int, full: bool) -> int:
    import mutation as mu

    det = translate(cases, work)
    rc = 0
    for case in cases:
        port = det / case / "port"
        if not port.is_dir():
            print(f"{case}: no det port (translation failed: see {det / 'summary.json'})")
            rc = 1
            continue
        try:
            mu.run(case, work / case, jobs, sample, seed, set(mu.OPERATORS), None, False, full, port=port,
                   files=FILES, select=scope_filter(case_kind(case), port))  # fmt: skip
        except SystemExit as e:  # the det port is not proven: nothing to measure; the batch goes on
            print(f"{case}: {e}")
            rc = 1
            continue
        rc |= record(case, work / case, port)
    return rc


def merge_survivors(entry: dict[str, Any], rerun: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The entry with its recorded survivors replaced by `rerun`'s verdicts (mutation.py results, same seed and port):
    a survivor still surviving with the same Java line before / after stays; a killed one moves to `killed` (a timeout
    counts as killed, as in `entry_from_run`); an error / pending one stays listed and is counted, so L5 is withheld.
    The killed and stillborn lists are carried. None when a survivor was not re-run or its line moved (not the same
    mutant: re-run the case)."""
    got = {r["id"]: r for r in rerun}
    out = json.loads(json.dumps(entry))  # (a copy)
    counts = out["counts"]
    kept, killed = [], list(out.get("killed", []))
    for s in entry.get("survived", []):
        r = got.get(s["id"])
        if r is None or any(r.get(k, s[k]) != s[k] for k in ("before", "after")):
            return None
        v = r["verdict"]
        if v == "survived":
            kept.append(s)
            continue
        counts["survived"] -= 1
        counts[v] = counts.get(v, 0) + 1
        if v in ("killed", "timeout"):
            killed.append(s["id"])
        else:  # error / pending: not a verdict to carry
            kept.append(s)
    out["survived"] = kept
    out["killed"] = sorted(set(killed))
    return out


def _outdated(entry: dict[str, Any], now: dict[str, Any]) -> bool:
    """A blocking input moved, or a generator / harness / oracle drifted (the port's bytes need comparing)."""
    return bool(stale(entry, now) or drifted(entry, now))


def rerun_moved(cases: list[str], work: Path, budget_min: float | None = None,
                clock: Callable[[], float] = time.monotonic) -> tuple[list[str], int]:  # fmt: skip
    """`run` each case whose det port moved, with the sample, seed and mode its ledger entry was cut with (so the new
    score is comparable), oldest entry first; no new case starts once `budget_min` minutes are spent (None: no limit).
    A fresh `record` drops `port_moved`. Returns (the cases still flagged, the worst `run` status): a case left for
    the next night, or one whose run failed, keeps its flag (#5862)."""
    ledger = load()
    order = sorted(cases, key=lambda c: (str(ledger[c].get("date") or ""), c))
    start, rc = clock(), 0
    for i, case in enumerate(order):
        if budget_min is not None and clock() - start >= budget_min * 60:
            print(f"det mutation: budget of {budget_min:g} min spent: {', '.join(order[i:])} left for the next run")
            break
        e = ledger[case]
        rc |= run([case], work, e.get("chosen") or None, e.get("seed") or 0, 3, e.get("mode") == "full")
    now = load()
    return [c for c in order if (now.get(c) or {}).get("port_moved")], rc


def refresh(cases: list[str], work: Path, run_moved: bool = False, budget_min: float | None = None) -> int:
    """Renew each stale or drifted entry whose det port bytes did not move (#5862). Only generator / harness / oracle
    drifted: translate again, compare the port's bytes, renew the fingerprints. Case / corpus / survivors list moved:
    re-run only the recorded survivors (same seed, operators, scope and mode) and carry the other verdicts; a survivor that now dies drops out of the survivors (a stated
    `equivalent` / `unreachable` one is a wrong claim: exit 1), one still surviving with the same Java line before /
    after keeps its stated verdict. Mutants killed before are not re-proven (a case weakened since would not show).
    A port whose bytes moved marks the entry stale (`port_moved`: `run` records it afresh). Exit 1: a wrong claim, an
    error, a survivor not re-run. Exit 2: only that a port moved (a person runs `run`); the
    scheduled lane (evidence-refresh.yml) warns on 2 and fails on 1. With `run_moved` the moved ports are run again
    here (`rerun_moved`, within `budget_min`), so exit 2 is left only for the cases the budget did not reach."""
    import evidence as ev
    import mutation as mu

    ledger = load()
    todo = [c for c in (cases or sorted(ledger))
            if c in ledger and (CASES / c / "case.json").is_file() and _outdated(ledger[c], fingerprints(c))]  # fmt: skip
    if not todo:
        print("det mutation: nothing stale")
        return 0
    det = translate(todo, work)
    rc, port_moved, moved_ports = 0, False, []
    for case in todo:
        entry, port = ledger[case], det / case / "port"
        if not port.is_dir() or port_sha(port) != entry["inputs"]["port"]:
            print(f"{case}: the det port changed: re-run (det_mutation.py run {case} --work DIR)")
            port_moved = True
            if port.is_dir():
                moved_ports.append(case)
            if port.is_dir() and not entry.get("port_moved"):  # stale until `run` records the new port
                write(case, {**entry, "port_moved": True})
            continue
        now = fingerprints(case)
        moved = stale(entry, now)
        info = drifted(entry, now)
        if moved and entry.get("survived"):
            only = work / case / "survivors"
            only.mkdir(parents=True, exist_ok=True)
            results = [{"id": s["id"], "verdict": "survived"} for s in entry["survived"]]
            (only / "mutation.json").write_text(json.dumps({"results": results}), encoding="utf-8")
            try:
                res = mu.run(case, work / case / "rerun", 3, None, entry["seed"], set(mu.OPERATORS), None, False,
                             entry.get("mode") == "full", only=only, port=port, files=FILES,
                             select=scope_filter(case_kind(case), port))  # fmt: skip
            except SystemExit as e:  # the det port is not proven now: nothing to carry
                print(f"{case}: {e}")
                rc = 1
                continue
            merged = merge_survivors(entry, res["results"])
            if merged is None:
                print(f"{case}: a recorded survivor was not re-run or moved: re-run (det_mutation.py run {case})")
                rc = 1
                continue
            merged["refreshed"] = {"from": entry.get("date"), "survivors_rerun": len(results), "stale": moved}
            merged["date"] = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
            merged["commit"] = ev.harness_commit()
            if res.get("coverage"):
                merged["coverage"] = res["coverage"]
            entry = merged
        entry.pop("port_moved", None)  # (the port is byte-identical again)
        for n, v in now.items():
            entry["inputs"][n] = v["sha256"]
            if "components" in v:
                entry.setdefault("components", {})[n] = v["components"]
        write(case, entry)
        s = summary(case, entry)
        print(f"{case}: the det port is unchanged: renewed ({', '.join(moved + info)}); {_row(s)}")
        for i in s["refuted"]:
            print(f"{case}: {i} is stated {stated(case)[i]['verdict']} but the re-run killed it: the claim is wrong")
            rc = 1
    if run_moved and moved_ports:
        left, rc_run = rerun_moved(moved_ports, work, budget_min)
        rc |= rc_run
        port_moved = bool(left)
    return rc or (2 if port_moved else 0)


def changed_cases(ref: str) -> set[str] | None:
    """The cases whose input files differ from `ref`'s merge base (what this PR changes), or None when git cannot say.
    Output files inside the case directory (`evidence.json`, `evidence.md`, refreshed by evidence-refresh.yml) are not
    case inputs (matching `evidence.py` `compute_inputs`), so refreshing a record does not flag the case as changed."""
    base = subprocess.run(["git", "merge-base", ref, "HEAD"], cwd=REPO, capture_output=True, text=True, check=False)
    if base.returncode:
        return None
    diff = subprocess.run(["git", "diff", "--name-only", base.stdout.strip(), "--", "tests/equivalence"], cwd=REPO,
                          capture_output=True, text=True, check=False)  # fmt: skip
    if diff.returncode:
        return None
    return {
        parts[2]
        for f in diff.stdout.split()
        if len(parts := f.split("/")) > 3
        and parts[2] not in LEDGER_DIRS
        and parts[3] not in ("evidence.json", "evidence.md")
    }


def cases_to_rerun(ref: str) -> list[str]:
    """The cases this PR changes that carry a ledger (what `stale-check --vs REF` would test): cheap, a git diff and a
    ledger read with no fingerprinting, so pr_gates can hint on every run (#5862)."""
    changed = changed_cases(ref)
    return sorted(changed & set(load())) if changed else []


def stale_check(ref: str | None = None) -> int:
    """Exit 1 when a ledger's case has an input that moved (cheap: fingerprints only, no translate). With `ref`, only
    the cases this PR changes: a case-strengthening PR re-runs its ledger in the same PR (#5862); drift main already
    carries is the nightly lane's (evidence-refresh.yml)."""
    ledger = load()
    scope = changed_cases(ref) if ref else None
    if ref and scope is None:
        print(f"det mutation: cannot diff against {ref}: checking every ledger")
    bad: list[str] = []
    drift: list[str] = []
    for case in sorted(ledger):
        if scope is not None and case not in scope or not (CASES / case / "case.json").is_file():
            continue
        info: list[str] = []
        try:
            now = fingerprints(case)
            moved, info = stale(ledger[case], now), drifted(ledger[case], now)
        except (RuntimeError, KeyError, OSError):
            moved = ["unknown"]
        if not moved and info:
            drift.append(case)
        if moved:
            bad.append(case)
            print(f"det mutation: {case}: stale ({', '.join(moved)}): python tests/tools/det_mutation.py refresh "
                  f"{case} --work DIR (a det port that moved needs `run`), then commit "
                  f"tests/equivalence/det_mutation/{case}.json")  # fmt: skip
    if drift:
        print(
            f"det mutation: {len(drift)} current ledger(s) with generator / harness / oracle drift (recorded, not "
            "staling; `refresh` compares the port's bytes)"
        )
    print("det mutation: no stale ledger" if not bad else f"det mutation: {len(bad)} stale ledger(s)")
    return 1 if bad else 0


def state(case: str, triage: dict[str, dict[str, str]]) -> int:
    """Write verdicts for the case's surviving mutants into the survivor list, the Java line before / after taken
    from the ledger's run (an id the run did not see survive is refused)."""
    survived = {s["id"]: s for s in (load().get(case) or {}).get("survived", [])}
    unknown = sorted(set(triage) - set(survived))
    if unknown:
        raise SystemExit(f"{case}: not survivors of the ledger's run: {', '.join(unknown)}")
    all_ = load_survivors()
    mine = {e["id"]: e for e in all_.get(case, [])}
    for i, t in triage.items():
        s = survived[i]
        mine[i] = {"id": i, "op": s["op"], "line": s["line"], "before": s["before"], "after": s["after"],
                   "verdict": t["verdict"], "reason": t["reason"]}  # fmt: skip
    entries = sorted(mine.values(), key=lambda e: (e["line"], e["id"]))
    problems = problems_in_survivors({case: entries})
    if problems:
        raise SystemExit("\n".join(problems))
    write_survivors(case, entries)
    entry = load()[case]
    if "survivors" in (entry.get("inputs") or {}):  # the person just reviewed these against the recorded run
        entry["inputs"]["survivors"] = survivors_sha(case)
        write(case, entry)
    s = summary(case, entry)
    print(_row(s))
    return 0


# ---- tables ----------------------------------------------------------------------------------------------------------
def _row(s: dict[str, Any]) -> str:
    score = f"{100 * s['score']:.0f}%" if s["score"] is not None else "n/a"
    return (f"| {s['program']} ({s['case']}) | {s['chosen']}/{s['mutants']} (seed {s['seed']}) | {s['killed']} | "
            f"{s['survived']} | {s['stillborn']} | {s['accounted']} | {s['unaccounted']} | "
            f"{s['killed']}/{s['killed'] + s['survived']} ({score}) | {'yes' if s['l5'] else 'no'} |")  # fmt: skip


def table(cases: list[str] | None = None) -> str:
    rows = [("| program (case) | mutants run / in scope | killed | survived | stillborn | stated equivalent / "
             "unreachable | unaccounted | raw score | L5 |"), "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for case, entry in sorted(load().items()):
        if not cases or case in cases:
            rows.append(_row(summary(case, entry)))
    return "\n".join(rows)


def survivors_table(cases: list[str] | None = None) -> str:
    rows = ["| case | mutant | op | Java line, before -> after | verdict | why |", "|---|---|---|---|---|---|"]
    for case, entry in sorted(load().items()):
        if cases and case not in cases:
            continue
        st = stated(case)
        for s in entry.get("survived", []):
            e = st.get(s["id"], {})
            before, after = (x.replace("|", "\\|") for x in (s["before"], s["after"]))
            rows.append(f"| {case} | `{s['id']}` | {s['op']} | {s['line']}: `{before}` -> `{after}` | "
                        f"{e.get('verdict', '**open**')} | {e.get('reason', '')} |")  # fmt: skip
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("cases", nargs="+")
    r.add_argument("--work", type=Path, required=True)
    r.add_argument("--sample", type=int, default=150, help="mutants per port (default 150; 0: all)")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--jobs", type=int, default=3)
    r.add_argument("--full", action="store_true", help="prove each mutant from scratch (mutation.py --full)")
    rec = sub.add_parser("record")
    rec.add_argument("case")
    rec.add_argument("run_dir", type=Path)
    rec.add_argument("port", type=Path)
    rf = sub.add_parser("refresh")
    rf.add_argument("cases", nargs="*")
    rf.add_argument("--work", type=Path, required=True)
    rf.add_argument("--run-moved", action="store_true", help="run the cases whose det port moved (oldest first)")
    rf.add_argument("--budget-min", type=float, help="with --run-moved: start no new case after this many minutes")
    sub.add_parser("check")
    sc = sub.add_parser("stale-check")
    sc.add_argument("--vs", metavar="REF", help="only the cases this branch changes against REF (merge base)")
    t = sub.add_parser("table")
    t.add_argument("cases", nargs="*")
    st = sub.add_parser("state")
    st.add_argument("case")
    st.add_argument("triage", type=Path, help="a JSON file {mutant id: {verdict, reason}}")
    sv = sub.add_parser("survivors")
    sv.add_argument("cases", nargs="*")
    args = ap.parse_args(argv)
    if args.cmd == "run":
        return run(args.cases, args.work, args.sample or None, args.seed, args.jobs, args.full)
    if args.cmd == "record":
        return record(args.case, args.run_dir, args.port)
    if args.cmd == "refresh":
        return refresh(args.cases, args.work, args.run_moved, args.budget_min)
    if args.cmd == "stale-check":
        return stale_check(args.vs)
    if args.cmd == "table":
        print(table(args.cases or None))
        return 0
    if args.cmd == "state":
        return state(args.case, json.loads(args.triage.read_text(encoding="utf-8")))
    if args.cmd == "survivors":
        print(survivors_table(args.cases or None))
        return 0
    problems, warnings = check()
    for w in warnings:
        print(f"warning: {w}")
    for p in problems:
        print(p)
    print("det mutation: ok" if not problems else f"det mutation: {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
