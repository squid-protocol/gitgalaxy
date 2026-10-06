#!/usr/bin/env python3
"""The det translator's port of every program of a cics-crucible case, as port overlays for the crucible runner's
java-ported side -- the proof a #4270 slice gives that the det port of its new case passes.

    python tests/tools/cics_case_ports.py <case-dir> --project <generated project> --ports OUT
    python tests/tools/cics_case_ports.py <case-dir> --work W --ports OUT          # W: a forge-compile --keep dir
    python tests/tools/cics_case_ports.py <case-dir> --work W --forge --ports OUT  # run forge-compile into W first

then

    python tests/tools/cics_crucible.py --crucible <crucible> --cases <case> --sides cobol-stub java-ported \\
        --offline --ports OUT --keep W2 --out O2

The generated project is the one the runner's forge-compile side builds (`cics_crucible.py --cases <case> --sides
forge-compile --offline --keep W` leaves it at W/<case>/forge/java_h2); --forge runs that step itself. Per program the
translator (gitgalaxy/tools/cobol_to_java/det) writes OUT/<PROGRAM>/overlay/service/<Service>.java plus the cobolrt
runtime -- port_runner's overlay layout, what `--ports` reads -- and OUT/summary.json gives statements / translated /
holes per program. A hole is a statement the port does not translate: a case whose programs have holes is not proven
by a passing java-ported side alone (the hole's path may simply not run).

Why a separate tool and not a `--det` flag on cics_crucible.py: the overlays are the same inputs `port_runner prove`
and the committed ports use, so they stay on disk to inspect, diff and re-run against (--sides java-ported java-facade)
without retranslating, and the 2,700-line runner keeps one way of taking ports.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

_PKG = re.compile(r"^package\s+([\w.]+)\.service\s*;", re.M)


def project_in(work: Path, case_id: str) -> Path:
    project = work / case_id / "forge" / "java_h2"
    if not (project / "pom.xml").is_file():
        raise SystemExit(f"no generated project at {project}: run forge-compile with --keep {work} first (or --forge)")
    return project


def run_forge(case_dir: Path, case_id: str, work: Path) -> None:
    crucible = case_dir.resolve().parents[2]
    argv = [sys.executable, str(TOOLS / "cics_crucible.py"), "--crucible", str(crucible), "--cases", case_id,
            "--sides", "forge-compile", "--offline", "--keep", str(work)]  # fmt: skip
    print("forge-compile:", " ".join(argv), flush=True)
    env = dict(os.environ, PYTHONPATH=str(REPO))
    res = subprocess.run(argv, cwd=REPO, env=env, check=False)  # noqa: S603
    if res.returncode not in (0, 1):  # 1: a cell did not pass (the ledger's business); the project may still exist
        raise SystemExit(f"cics_crucible.py forge-compile exited {res.returncode}")


def translate_case(case_dir: Path, project: Path, ports: Path) -> dict[str, dict[str, Any]]:
    import cics_crucible_compare as cc
    import equivalence_java as ej

    from gitgalaxy.tools.cobol_to_java.det import program as P
    from gitgalaxy.tools.cobol_to_java.det.source import bms_copybooks

    case = cc.load_case(case_dir)
    bms = ports / "_bms"
    bms_copybooks(sorted(case_dir.glob("bms/*.bms")), bms)
    dirs = [case_dir / "copy", bms]
    summary: dict[str, dict[str, Any]] = {}
    for prog in case.programs:
        svc = ej._service_class(prog)
        stub_file = next(project.rglob(f"service/{svc}.java"), None)
        if stub_file is None:
            raise SystemExit(f"{prog}: no service/{svc}.java in {project} (is this the case's generated project?)")
        stub = stub_file.read_text(encoding="utf-8")
        m = _PKG.search(stub)
        if not m:
            raise SystemExit(f"{stub_file}: no `package <pkg>.service;` line")
        pkg = m.group(1)
        r = P.translate(case_dir / "src" / f"{prog}.cbl", dirs, stub, pkg, P.estate_files(project), project)
        out = ports / prog / "overlay"
        (out / "service").mkdir(parents=True, exist_ok=True)
        (out / "service" / f"{svc}.java").write_text(r.java, encoding="utf-8")
        for rel, text in P.runtime_files(pkg, P.has_batch(project)).items():
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            (out / rel).write_text(text, encoding="utf-8")
        summary[prog] = {"statements": r.stats["statements"], "translated": r.stats["translated"],
                         "holes": [str(h) for h in r.stats["holes"]]}  # fmt: skip
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case_dir", type=Path, help="cases/<trap>/<case-id> in a cics-crucible checkout")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--project", type=Path, help="the case's generated project (W/<case>/forge/java_h2)")
    src.add_argument("--work", type=Path, help="a cics_crucible.py --keep directory holding the forge-compile run")
    ap.add_argument("--forge", action="store_true", help="with --work: run forge-compile into it first")
    ap.add_argument("--ports", type=Path, required=True, help="write the overlays (and summary.json) here")
    args = ap.parse_args(argv)
    if not (args.case_dir / "case.json").is_file():
        raise SystemExit(f"{args.case_dir}: no case.json")
    case_id = json.loads((args.case_dir / "case.json").read_text(encoding="utf-8"))["id"]
    if args.forge and not args.work:
        raise SystemExit("--forge needs --work")
    if args.forge:
        run_forge(args.case_dir, case_id, args.work)
    project = args.project or project_in(args.work, case_id)
    args.ports.mkdir(parents=True, exist_ok=True)
    summary = translate_case(args.case_dir.resolve(), project.resolve(), args.ports.resolve())
    (args.ports / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    for prog, s in summary.items():
        print(f"{prog:<9} {s['translated']}/{s['statements']} translated, {len(s['holes'])} holes")
        for h in s["holes"]:
            print(f"      hole: {h[:110]}")
    holes = sum(len(s["holes"]) for s in summary.values())
    crucible = args.case_dir.resolve().parents[2]
    print(f"\n{len(summary)} programs, {holes} holes -> {args.ports}/summary.json\nprove: python tests/tools/"
          f"cics_crucible.py --crucible {crucible} --cases {case_id} --sides cobol-stub java-ported --offline "
          f"--ports {args.ports} --keep <W2> --out <O2>")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
