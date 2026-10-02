#!/usr/bin/env python3
"""Deterministic ports of proven cases, proven by the equivalence harness (docs/language_status/det_port_design.md).

    python tests/tools/det_port.py run CASE [CASE ...] --work DIR [--faults all|none] [--jobs N]
    python tests/tools/det_port.py run --all-proven --work DIR

For each case: the program is translated (gitgalaxy/tools/cobol_to_java/det) onto the generated project's service
-- the estate is generated once, under DIR/estate, for the stubs -- the port is written to DIR/<case>/port (the
service and the cobolrt runtime), and `equivalence.py run CASE --port DIR/<case>/port` proves it. DIR/summary.json:
per case, statements / translated / holes, and the proof's verdict."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT))

PKG = "com.gitgalaxy.modernized"
PROOF_TIMEOUT = 3600  # seconds per case
PKG_DIR = PKG.replace(".", "/")


def estate(corpus: Path, work: Path) -> Path:
    """The generated project of the corpus (h2), generated once under work/estate."""
    done = work / "estate" / "project.txt"
    if done.is_file():
        return Path(done.read_text(encoding="utf-8").strip())
    import java_target_matrix as jtm

    (work / "estate").mkdir(parents=True, exist_ok=True)
    clean = jtm.refactor(corpus, work / "estate", scan=True)
    project = jtm.generate(clean, "h2", jtm.MATRIX["h2"], work / "estate")
    done.write_text(str(project) + "\n", encoding="utf-8")
    return project


def port_case(name: str, work: Path, project: Path, corpus: Path, style: str = "dispatch",
              typed: bool = False, groups: bool = False) -> dict[str, Any]:  # fmt: skip
    import equivalence as eq
    import equivalence_java as ej

    from gitgalaxy.tools.cobol_to_java.det import program as P

    case = eq.load_case(name)
    svc = ej._service_class(case["program"])
    stub = (project / "src/main/java" / PKG_DIR / "service" / f"{svc}.java").read_text(encoding="utf-8")
    dirs = [corpus / d for d in case.get("copy_dirs", ["app/cpy"])]
    # symbolic maps the estate does not check in, generated from its BMS sources (after its own copybooks)
    from gitgalaxy.tools.cobol_to_java.det.source import bms_copybooks

    bms = work / f"bms-{case['corpus']}"
    if not bms.is_dir():
        bms_copybooks([p for p in corpus.rglob("*") if p.is_file() and p.suffix.lower() == ".bms"
                       and ".git" not in p.parts], bms)  # fmt: skip
    dirs.append(bms)
    out: dict[str, Any] = {"case": name, "program": case["program"]}
    port = work / name / "port"
    try:
        r = P.translate(corpus / case["program_source"], dirs, stub, PKG, P.estate_files(project), project, style, typed,
                        groups)  # fmt: skip
    except Exception as e:
        out.update({"translated": False, "error": f"{type(e).__name__}: {e}"})
        return out
    (port / "service").mkdir(parents=True, exist_ok=True)
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    out.update({"statements": r.stats["statements"], "translated_statements": r.stats["translated"],
                "holes": r.stats["holes"]})  # fmt: skip
    return out


def prove(name: str, work: Path, faults: str) -> dict[str, Any]:
    keep = work / name / "proof"
    shutil.rmtree(keep, ignore_errors=True)  # equivalence.py --keep wants a fresh directory
    argv = [sys.executable, str(TOOLS / "equivalence.py"), "run", name, "--port", str(work / name / "port"),
            "--keep", str(keep), "--faults", faults]  # fmt: skip
    log = work / name / "proof.log"
    with log.open("wb") as fh:
        try:  # a port that loops (a translation fault) must not hang the run
            rc = subprocess.run(argv, stdout=fh, stderr=subprocess.STDOUT, cwd=REPO_ROOT, check=False,  # noqa: S603
                                timeout=PROOF_TIMEOUT).returncode  # fmt: skip
        except subprocess.TimeoutExpired:
            return {"proof_rc": None, "proved": False, "java_failed": True, "timed_out": True, "log": str(log)}
    report = keep / "report.json"
    rep = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    return {"proof_rc": rc, "proved": rc == 0 and bool(rep) and not rep.get("java_failed"),
            "java_failed": bool(rep.get("java_failed")), "log": str(log)}  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("cases", nargs="*")
    r.add_argument("--all-proven", action="store_true", help="every carddemo case with a proven port")
    r.add_argument("--work", type=Path, required=True)
    r.add_argument("--faults", default="all")
    r.add_argument("--jobs", type=int, default=2)
    r.add_argument("--translate-only", action="store_true")
    r.add_argument("--groups", action="store_true",
                   help="with --typed: items in groups used whole too, the group's bytes synced (typed groups)")
    r.add_argument("--typed", action="store_true",
                   help="standalone WORKING-STORAGE items as typed Java fields where every use allows (B3)")
    r.add_argument("--style", choices=("dispatch", "structured"), default="dispatch",
                   help="structured: paragraphs as named methods called directly where the program has no GO TO / "
                        "HANDLE (else dispatch)")  # fmt: skip
    args = ap.parse_args()
    import equivalence as eq
    import mainframe_corpus as mc

    names = list(args.cases)
    if args.all_proven:
        names += sorted(p.parent.name for p in eq.CASES.glob("carddemo-*/case.json") if (p.parent / "port").is_dir())
    args.work.mkdir(parents=True, exist_ok=True)
    results = []
    estates: dict[str, tuple[Path, Path]] = {}  # corpus name -> (clone, generated project)
    for n in names:
        cname = eq.load_case(n)["corpus"]
        if cname not in estates:
            (entry,) = mc.select([cname])
            corpus = mc.require_clone(entry)
            # CardDemo's estate in DIR/estate (as before); another corpus's in DIR/estate-<corpus>
            where = args.work if cname == "aws-mainframe-modernization-carddemo" else args.work / f"estate-{cname}"
            estates[cname] = (corpus, estate(corpus, where))
        corpus, project = estates[cname]
        results.append(port_case(n, args.work, project, corpus, args.style, args.typed, args.groups))
    if not args.translate_only:
        eq.build_image()
        todo = [x for x in results if x.get("statements") is not None]
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            for x, p in zip(todo, ex.map(lambda x: prove(x["case"], args.work, args.faults), todo)):
                x.update(p)
    (args.work / "summary.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for x in results:
        st = x.get("statements")
        what = "ERROR " + x["error"] if st is None else f"{x['translated_statements']}/{st} translated"
        verdict = "" if "proved" not in x else (
            "  PROVED" if x["proved"] else "  JAVA FAILED" if x["java_failed"] else "  DIFFERS")  # fmt: skip
        print(f"{x['case']:<28} {what}{verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
