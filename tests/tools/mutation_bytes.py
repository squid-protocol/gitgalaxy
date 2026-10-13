#!/usr/bin/env python3
r"""
#4965: are the byte overload's assign and accessor proven against the instrument?

Every region facade of a port has `handleTransaction(.., byte[])`: `lastAnswerBytes = task.returnedBytes();` after the
task ran, and a `lastAnswerBytes()` accessor. The equivalence harness (equivalence_cics.py) and the CICS crucible
(cics_crucible.py) both compare the accessor with the bytes the task's RETURN passed on. Those bytes exist only when
the port RETURNs through the byte-carrying `returnTransid(.., byte[])` (the deterministic port does, #4817); a
model-written port RETURNs through the DTO-only one, so `returnedBytes()` is null on every path and deleting the
assignment changes nothing: an equivalent mutant, not a case gap.

This tool proves exactly those two mutants (the deleted assignment, the inverted accessor test) on a case's committed
port and, with `--det-work`, on the deterministic port `det_port.py run CASE --work DIR` wrote:

    python tests/tools/mutation_bytes.py run CASE --work DIR [--det-work DETDIR]

A mutant of the deterministic port that the proof still calls proven is a failure (exit 1)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

import mutation as mu  # noqa: E402

TOKENS = ("returnedBytes", "lastAnswerBytes")


def bytes_mutants(port: Path) -> list[mu.Mutant]:
    """The assign and accessor mutants of a port's byte overload: the statements naming the overload's bytes."""
    return [m for m in mu.all_mutants(port, set(mu.OPERATORS)) if any(t in m.before for t in TOKENS)]


def judge(case: str, label: str, port: Path, work: Path) -> list[dict]:
    work.mkdir(parents=True, exist_ok=True)
    base = mu.prove(case, port, work / "baseline", 3600)
    if base["verdict"] != "proven":
        raise SystemExit(f"{label}: the port is not proven ({base['verdict']}); nothing to measure")
    classpath = mu.baseline_classpath(work / "baseline", work)
    (work / "proofs").mkdir(exist_ok=True)
    out = []
    for m in bytes_mutants(port):
        md = mu.write_mutant(port, m, work / "mutants" / m.id / "port")
        ok, _ = mu.compiles(md, classpath, work / "mutants" / m.id / "classes")
        if not ok:
            out.append({"port": label, "id": m.id, "op": m.op, "line": m.line, "verdict": "stillborn"})
            continue
        r = mu.prove(case, md, work / "proofs" / m.id, 1800, ("--reuse", str(work / "baseline"), "--first-difference"))
        v = "survived" if r["verdict"] == "proven" else "killed"
        out.append({"port": label, "id": m.id, "op": m.op, "line": m.line, "verdict": v, "after": m.after.strip()})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("case")
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--det-work", type=Path, help="det_port.py run's --work: its CASE/port is judged too")
    args = ap.parse_args(argv)
    rows = judge(args.case, "committed", mu.port_dir(args.case), args.work / "committed")
    det = []
    if args.det_work:
        det = judge(args.case, "det", args.det_work / args.case / "port", args.work / "det")
        rows += det
    for r in rows:
        print(f"{r['port']:9} {r['op']} line {r['line']:4} {r['verdict']:9} {r.get('after', '')[:70]}")
    return 1 if any(r["verdict"] == "survived" for r in det) else 0


if __name__ == "__main__":
    raise SystemExit(main())
