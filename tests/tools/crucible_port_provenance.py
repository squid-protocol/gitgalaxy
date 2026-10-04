"""#4308: a CICS crucible port's provenance names the crucible version it is proven at -- the pinned one.

Each tests/cics_crucible/ports/<case>/<PROGRAM>/provenance.json (format `cics-crucible-port/1`) records the proof
the porting loop made (`proof.crucible_ref`, e.g. "v0.1.0 (0c942cb8)"). The runner moves to a new crucible release
with a pin bump (tests/_cics_crucible_pin.py PINNED_REF); a port's provenance must then say what it is proven at
now. `proof.crucible_ref` stays as the loop wrote it (the history of how the port was made); a later proof is
APPENDED:

    "proof": {..., "reproven": [{"at", "crucible_ref", "summary", "port_sha256", "harness_commit", "by"}]}

and a port that could not be re-proven carries, instead, an explicit

    "proof": {..., "stale": {"against": PINNED_REF, "reason": "...", "needs": "..."}}

`current_ref()` is the ref of the latest proof; `problems()` lists every record whose latest proof is not at
PINNED_REF and that does not say it is stale against PINNED_REF (tests/cics_crucible/test_port_provenance.py fails
on them). Only `reprove` -- which RUNS the proof -- appends a `reproven` entry; nothing stamps one by hand.

    python tests/tools/crucible_port_provenance.py check
    python tests/tools/crucible_port_provenance.py reprove [--cases CASE ...]   # needs Docker, a JDK 17, Maven

`reprove` runs `cics_crucible.py --cases C --program P --sides java-ported --report-dir ...` for each committed
port, at the pinned checkout (the runner refuses any other), and writes the result into the record: a `reproven`
entry when every scenario that runs the program passes, else a `stale` mark with the failing summary.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PORTS = REPO_ROOT / "tests" / "cics_crucible" / "ports"
RUNNER = REPO_ROOT / "tests" / "tools" / "cics_crucible.py"
sys.path.insert(0, str(REPO_ROOT / "tests"))
from _cics_crucible_pin import PINNED_REF  # noqa: E402


def records(ports: Path = PORTS) -> list[Path]:
    return sorted(ports.glob("*/*/provenance.json"))


def ref_tag(ref: Optional[str]) -> Optional[str]:
    """"v0.2.0 (94f2afcb)" -> "v0.2.0"; a bare commit stays as it is."""
    return ref.split(" ", 1)[0] if ref else None


def current_ref(prov: dict[str, Any]) -> Optional[str]:
    """The crucible ref of the record's latest proof: the last re-proof, else the loop's own."""
    proof = prov.get("proof") or {}
    again = proof.get("reproven") or []
    return again[-1].get("crucible_ref") if again else proof.get("crucible_ref")


def problems(ports: Path = PORTS, pinned: str = PINNED_REF) -> list[str]:
    """One line per record that silently describes another crucible version than the pinned one."""
    out = []
    for path in records(ports):
        prov = json.loads(path.read_text(encoding="utf-8"))
        rel = path.relative_to(ports)
        ref = current_ref(prov)
        if ref_tag(ref) == pinned:
            continue
        stale = (prov.get("proof") or {}).get("stale")
        if stale and stale.get("against") == pinned and stale.get("reason"):
            continue
        out.append(f"{rel}: proven at {ref!r}, but the runner pins {pinned!r} (tests/_cics_crucible_pin.py); "
                   f"re-prove it (python tests/tools/crucible_port_provenance.py reprove) or mark it stale")  # fmt: skip
    return out


def tree_sha256(root: Path) -> str:
    """sha256 over the sorted root-relative paths, each fed as `path \\0 bytes \\0` (the port's overlay tree)."""
    h = hashlib.sha256()
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        h.update(f.relative_to(root).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def _git_head() -> str:
    return subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,  # noqa: S603, S607
                          check=False).stdout.strip()  # fmt: skip


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def reprove_one(path: Path, crucible: Path, work: Path, extra: tuple[str, ...] = ()) -> dict[str, Any]:
    """Run the program's proof at the pinned crucible and write the outcome into its provenance.json."""
    case, program = path.parent.parent.name, path.parent.name
    report_dir = work / case / program
    argv = [sys.executable, str(RUNNER), "--crucible", str(crucible), "--cases", case, "--program", program,
            "--sides", "java-ported", "--report-dir", str(report_dir), "--keep", str(work / "keep" / case / program), *extra]  # fmt: skip
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603
    prov = json.loads(path.read_text(encoding="utf-8"))
    proof = prov.setdefault("proof", {})
    report_file = report_dir / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else None
    summary = ({sc: f"{o['equal']}/{o['records']}" for sc, o in sorted(report["outputs"].items())}
               if report else {})  # fmt: skip
    ref = (report or {}).get("crucible_ref")
    if report and report.get("proven") and ref_tag(ref) == PINNED_REF:
        entry = {"at": _now(), "crucible_ref": ref, "summary": summary,
                 "port_sha256": tree_sha256(path.parent / "overlay"), "harness_commit": _git_head(),
                 "by": "tests/tools/crucible_port_provenance.py reprove (cics_crucible.py --sides java-ported "
                       f"--program {program} --report-dir)"}  # fmt: skip
        proof.setdefault("reproven", []).append(entry)
        proof.pop("stale", None)
        outcome = {"program": f"{case}/{program}", "reproven": True, "summary": summary}
    else:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
        reason = (f"re-proof at {ref or PINNED_REF} failed: {summary}" if report
                  else f"re-proof at {PINNED_REF} did not run: {' | '.join(tail)}")  # fmt: skip
        proof["stale"] = {"against": PINNED_REF, "at": _now(), "reason": reason,
                          "needs": "a port that passes every scenario of the program at the pinned crucible "
                                   "(port_runner prove), then reprove"}  # fmt: skip
        outcome = {"program": f"{case}/{program}", "reproven": False, "reason": reason}
    path.write_text(json.dumps(prov, indent=1) + "\n", encoding="utf-8")
    return outcome


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="list the records not at PINNED_REF and not marked stale against it")
    r = sub.add_parser("reprove", help="re-run each port's proof at the pinned crucible and record it")
    r.add_argument("--crucible", type=Path, help="the cics-crucible checkout (default: as cics_crucible.py finds it)")
    r.add_argument("--cases", nargs="+", help="only these cases")
    r.add_argument("--offline", action="store_true", help="run Maven offline")
    r.add_argument("--work", type=Path, help="keep the proofs' work trees here")
    args = ap.parse_args(argv)
    if args.cmd == "check":
        found = problems()
        for line in found:
            print(line)
        print(f"{len(records())} port provenance records, {len(found)} not at {PINNED_REF}")
        return 1 if found else 0
    sys.path.insert(0, str(RUNNER.parent))
    import cics_crucible  # noqa: PLC0415 -- the runner's checkout lookup, only for reprove

    crucible = cics_crucible.crucible_path(args.crucible).resolve()
    work = (args.work or Path(tempfile.mkdtemp(prefix="crucible_reprove_"))).resolve()
    extra = ("--offline",) if args.offline else ()
    failed = 0
    for path in records():
        if args.cases and path.parent.parent.name not in args.cases:
            continue
        got = reprove_one(path, crucible, work, extra)
        failed += not got["reproven"]
        print(f"{got['program']}: " + (f"re-proven at {PINNED_REF} {got['summary']}" if got["reproven"]
                                       else f"STALE -- {got['reason']}"))  # fmt: skip
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
