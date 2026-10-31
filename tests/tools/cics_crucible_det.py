#!/usr/bin/env python3
r"""
#4965: a crucible scenario whose RETURN TRANSID passes a COMMAREA out through the byte-carrying handleTransaction.

The committed crucible ports are model-written and RETURN through the DTO-only `returnTransid(t, ca, len)`, so
`returnedBytes()` is null there and `lastAnswerBytes = task.returnedBytes();` can be deleted without any scenario
noticing. The deterministic port RETURNs through `returnTransid(.., byte[])` (#4817), so the crucible's java-facade
side (which compares `lastAnswerBytes()` with the task's RETURN bytes, converted from the runtime page, #5053) sees it.

`tests/cics_crucible/det-ports/<case>/<KEY>/overlay` holds the deterministic port of a crucible case's programs
(PCWIZ and PCCONF of `pc-wizard`, 39/39 and 47/47 statements, no holes). It is NOT a model port: no provenance, no
loop, regenerated from the COBOL by `build`, and kept out of tests/cics_crucible/ports so the port records stay
model-only. `ports_dir` lays the runtime beside it, ready for `--ports`:

    python tests/tools/cics_crucible.py --cases pc-wizard --sides java-facade --ports <ports_dir>
    python tests/tools/cics_crucible_det.py build pc-wizard --project <a crucible run's forge-ported/java_h2>
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT))

DET_PORTS = REPO_ROOT / "tests" / "cics_crucible" / "det-ports"
PKG = "com.gitgalaxy.modernized"
# case -> (the port's key, the programs it translates)
PROGRAMS = {
    "pc-wizard": ("PCWIZ", ("PCWIZ", "PCCONF")),
    "pc-return-channel": (
        "PCRC",
        ("PCRCA", "PCRCB", "PCRCL"),
    ),  # #5005: RETURN TRANSID CHANNEL carried to the next task
    "gt-web-client": ("GTWCLI", ("GTWCLI",)),  # #4767: WEB OPEN / CONVERSE / CLOSE against a stated peer
    "gt-web-parse-url": ("GTWPARS", ("GTWPARS",)),  # #4767: WEB PARSE URL, IPv6 host and LENGERR
    "ca-getmain-pointer": ("CAGM", ("CAGMPT", "CAGMZ")),  # #6876: GETMAIN / FREEMAIN DATA, pointer arithmetic
}


def ports_dir(case: str, dest: Path, root: Path = DET_PORTS) -> Path:
    """A `--ports` directory for `case`: the committed deterministic services plus the runtime they compile with."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    key = PROGRAMS[case][0]
    overlay = dest / key / "overlay"
    shutil.copytree(root / case / key / "overlay", overlay, dirs_exist_ok=True)
    for rel, text in P.runtime_files(PKG, False).items():
        (overlay / rel).parent.mkdir(parents=True, exist_ok=True)
        (overlay / rel).write_text(text, encoding="utf-8")
    return dest


def build(case: str, crucible: Path, project: Path, root: Path = DET_PORTS) -> dict[str, tuple[int, int]]:
    """Translate the case's programs with the deterministic translator over the stubs of a generated `project`."""
    from gitgalaxy.tools.cobol_to_java.det import program as P
    from gitgalaxy.tools.cobol_to_java.det.engine_layout import EngineLayouts
    from gitgalaxy.tools.cobol_to_java.det.source import bms_copybooks

    src = next(crucible.glob(f"cases/*/{case}"))
    key, programs = PROGRAMS[case]
    out = root / case / key / "overlay" / "service"
    out.mkdir(parents=True, exist_ok=True)
    bms = root / ".bms-scratch"
    try:
        maps = src / "bms"  # a case with no map ships no directory (git carries no empty one)
        bms_copybooks(sorted(p for p in maps.iterdir() if p.suffix.lower() == ".bms") if maps.is_dir() else [], bms)
        stats = {}
        for prog in programs:
            stub = (project / "src/main/java" / PKG.replace(".", "/") / "service"
                    / f"{prog.capitalize()}Service.java").read_text(encoding="utf-8")  # fmt: skip
            r = P.translate(src / "src" / f"{prog}.cbl", [src / "copy", bms], stub, PKG, P.estate_files(project),
                            project, layouts=EngineLayouts.for_project(project, src, f"src/{prog}.cbl"))  # fmt: skip
            (out / f"{r.service}.java").write_text(r.java, encoding="utf-8")
            stats[prog] = (r.stats["translated"], r.stats["statements"])
    finally:
        shutil.rmtree(bms, ignore_errors=True)
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["build"])
    ap.add_argument("case", choices=sorted(PROGRAMS))
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--crucible", type=Path, required=True)
    args = ap.parse_args(argv)
    for prog, (done, total) in build(args.case, args.crucible, args.project).items():
        print(f"{prog}: {done}/{total} statements translated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
