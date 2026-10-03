#!/usr/bin/env python3
"""Deterministic ports of proven cases, proven by the equivalence harness (docs/language_status/det_port_design.md).

    python tests/tools/det_port.py run CASE [CASE ...] --work DIR [--faults all|none] [--jobs N]
    python tests/tools/det_port.py run --all-proven --work DIR
    python tests/tools/det_port.py run --all-cases --translate-only --work DIR
    python tests/tools/det_port.py check --work DIR [--base-ref origin/main | --base DIR]

For each case: the program is translated (gitgalaxy/tools/cobol_to_java/det) onto the generated project's service
-- the estate is generated once, under DIR/estate, for the stubs -- the port is written to DIR/<case>/port (the
service and the cobolrt runtime), and `equivalence.py run CASE --port DIR/<case>/port` proves it. DIR/summary.json:
per case, statements / translated / holes, and the proof's verdict.

`check` answers "which ports does my change move?": every case translated with the current code (DIR/new) and with
the base -- a git ref translated in a throwaway worktree (DIR/base), or an earlier work directory -- and each port
compared file by file. A changed port is one to re-prove (`run CASE ...`); exit 1 when any changed.

Both print det_parity.py's structural warnings (methods and branch points far from what the COBOL predicts), and
summary.json / check.json carry them as parity_warnings: a hint where to look, never a failed proof or exit code."""

from __future__ import annotations

import argparse
import json
import os
import re
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
    import equivalence_cache
    import java_target_matrix as jtm

    (work / "estate").mkdir(parents=True, exist_ok=True)
    clean = equivalence_cache.refactor(corpus, work / "estate", scan=True)  # (once per corpus and engine)
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
    dirs += [corpus / d for d in (case.get("db2") or {}).get("include_dirs", [])]  # DCLGEN members
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
                        groups, case.get("compiler_options"))  # fmt: skip
    except Exception as e:
        out.update({"translated": False, "error": f"{type(e).__name__}: {e}"})
        return out
    (port / "service").mkdir(parents=True, exist_ok=True)
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for extra in case.get("programs", []):  # the programs the task LINKs to: translated the same way
        x_svc = ej._service_class(extra["program"])
        x_stub = (project / "src/main/java" / PKG_DIR / "service" / f"{x_svc}.java").read_text(encoding="utf-8")
        try:
            x = P.translate(corpus / extra["program_source"], dirs, x_stub, PKG, P.estate_files(project), project,
                            style, typed, groups, case.get("compiler_options"))  # fmt: skip
        except Exception as e:
            out.update({"translated": False, "error": f"{extra['program']}: {type(e).__name__}: {e}"})
            return out
        (port / "service" / f"{x.service}.java").write_text(x.java, encoding="utf-8")
        r.stats["statements"] += x.stats["statements"]
        r.stats["translated"] += x.stats["translated"]
        r.stats["holes"] += x.stats["holes"]
    for rel, text in P.runtime_files(PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    out.update({"statements": r.stats["statements"], "translated_statements": r.stats["translated"],
                "holes": r.stats["holes"]})  # fmt: skip
    out.update(_parity(port, corpus, [(case["program"], case["program_source"])]
                       + [(x["program"], x["program_source"]) for x in case.get("programs", [])]))  # fmt: skip
    return out


def _parity(port: Path, corpus: Path, programs: list[tuple[str, str]]) -> dict[str, Any]:
    """det_parity's structural check of each translated program: a warning to read, never a proof failure."""
    import det_parity
    import equivalence_java as ej

    rows, warnings = [], []
    for prog, src in programs:
        try:
            row = det_parity.parity_files(prog, corpus / src, port / "service" / f"{ej._service_class(prog)}.java")
        except Exception as e:  # the check must never cost a port its proof
            warnings.append(f"{prog}: parity check failed ({type(e).__name__}: {e})")
            continue
        rows.append(row)
        warnings += row["warnings"]
    return {"parity": rows, "parity_warnings": warnings}


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


def all_cases() -> list[str]:
    """Every equivalence case (the det port needs no model-written port)."""
    import equivalence as eq

    return sorted(p.parent.name for p in eq.CASES.glob("*/case.json"))


def _ports(work: Path) -> dict[str, dict[str, str]]:
    """{case: {file under its port: text}} of a translate-only work directory."""
    out: dict[str, dict[str, str]] = {}
    for port in sorted(work.glob("*/port")):
        out[port.parent.name] = {f.relative_to(port).as_posix(): f.read_text(encoding="utf-8")
                                 for f in sorted(port.rglob("*.java"))}  # fmt: skip
    return out


def compare(base: Path, new: Path) -> list[dict[str, Any]]:
    """Each case's port in `new` against `base`: unchanged, changed (the files and changed lines), new or gone.
    A runtime class (cobolrt/...) every port carries counts against a port only when its own code names that class
    (a DetSql change moves the Db2 ports, not every port): the files list says which runtime class moved it."""
    import difflib

    a, b = _ports(base), _ports(new)
    rows = []
    for case in sorted(set(a) | set(b)):
        if case not in a or case not in b:
            rows.append({"case": case, "status": "new" if case not in a else "gone"})
            continue
        own = " ".join(t for rel, t in b[case].items() if not rel.startswith("cobolrt/"))
        files = []
        for rel in sorted(set(a[case]) | set(b[case])):
            x, y = a[case].get(rel, ""), b[case].get(rel, "")
            if x == y:
                continue
            if rel.startswith("cobolrt/") and not re.search(rf"\b{re.escape(Path(rel).stem)}\b", own):
                continue  # a runtime class this port never names
            n = sum(1 for ln in difflib.unified_diff(x.splitlines(), y.splitlines(), lineterm="", n=0)
                    if ln[:1] in "+-" and ln[:3] not in ("+++", "---"))  # fmt: skip
            files.append({"file": rel, "lines": n})
        rows.append({"case": case, "status": "changed" if files else "unchanged", "files": files})
    return rows


def check(args: argparse.Namespace) -> int:
    """Translate every case with the current code and with the base, and list the ports that changed."""
    work: Path = args.work
    work.mkdir(parents=True, exist_ok=True)
    flags = ["--style", args.style] + (["--typed"] if args.typed else []) + (["--groups"] if args.groups else [])
    cases = args.cases or all_cases()

    def translate(repo: Path, out: Path) -> None:
        shutil.rmtree(out, ignore_errors=True)
        here = [c for c in cases if (repo / "tests" / "equivalence" / c / "case.json").is_file()]  # (new on one side)
        argv = [sys.executable, str(repo / "tests" / "tools" / "det_port.py"), "run", *here, "--translate-only",
                "--work", str(out), *flags]  # fmt: skip
        env = dict(os.environ)
        env.setdefault("GITGALAXY_LICENSE_KEY", "COMMUNITY_FREE_TIER")  # (no licence delay per estate scan)
        subprocess.run(argv, cwd=repo, check=True, stdout=subprocess.DEVNULL, env=env)  # noqa: S603

    base = args.base
    if base is None:
        tree = work / "base-tree"
        subprocess.run(["git", "-C", str(REPO_ROOT), "worktree", "remove", "--force", str(tree)],  # noqa: S603, S607
                       check=False, capture_output=True)  # fmt: skip
        subprocess.run(["git", "-C", str(REPO_ROOT), "worktree", "add", "--detach", str(tree), args.base_ref],  # noqa: S603, S607
                       check=True, capture_output=True)  # fmt: skip
        try:
            base = work / "base"
            translate(tree, base)
        finally:
            subprocess.run(["git", "-C", str(REPO_ROOT), "worktree", "remove", "--force", str(tree)],  # noqa: S603, S607
                           check=False, capture_output=True)  # fmt: skip
    translate(REPO_ROOT, work / "new")
    rows = compare(base, work / "new")
    summary = work / "new" / "summary.json"
    parity = {x["case"]: x.get("parity_warnings", [])
              for x in (json.loads(summary.read_text(encoding="utf-8")) if summary.is_file() else [])}  # fmt: skip
    for r in rows:
        if parity.get(r["case"]):
            r["parity_warnings"] = parity[r["case"]]
    (work / "check.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    changed = [r for r in rows if r["status"] != "unchanged"]
    for r in rows:
        detail = ", ".join(f"{f['file'].rsplit('/', 1)[-1]} {f['lines']} lines" for f in r.get("files", []))
        print(f"{r['case']:<28} {r['status'].upper() if r['status'] != 'unchanged' else 'unchanged'}"
              f"{'  ' + detail if detail else ''}")  # fmt: skip
        for w in r.get("parity_warnings", []):
            print(f"{'':<28}   parity warning: {w}")
    print(
        f"{len(rows) - len(changed)}/{len(rows)} ports unchanged"
        + (f"; re-prove: det_port.py run {' '.join(r['case'] for r in changed)} --work DIR" if changed else "")
    )
    return 1 if changed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("cases", nargs="*")
    r.add_argument("--all-proven", action="store_true", help="every carddemo case with a proven port")
    r.add_argument("--all-cases", action="store_true", help="every equivalence case")
    r.add_argument("--work", type=Path, required=True)
    r.add_argument("--faults", default="all")
    r.add_argument("--jobs", type=int, default=2)
    r.add_argument("--translate-only", action="store_true")
    r.add_argument(
        "--groups",
        action="store_true",
        help="with --typed: items in groups used whole too, the group's bytes synced (typed groups)",
    )
    r.add_argument(
        "--typed",
        action="store_true",
        help="standalone WORKING-STORAGE items as typed Java fields where every use allows (B3)",
    )
    r.add_argument("--style", choices=("dispatch", "structured"), default="dispatch",
                   help="structured: paragraphs as named methods called directly where the program has no GO TO / "
                        "HANDLE (else dispatch)")  # fmt: skip
    c = sub.add_parser("check", help="which ports change against a base (a git ref, or an earlier work directory)")
    c.add_argument("cases", nargs="*", help="default: every case")
    c.add_argument("--work", type=Path, required=True)
    c.add_argument("--base-ref", default="origin/main", help="the git ref translated as the base (default origin/main)")
    c.add_argument("--base", type=Path, help="an earlier translate-only work directory, instead of --base-ref")
    c.add_argument("--style", choices=("dispatch", "structured"), default="dispatch")
    c.add_argument("--typed", action="store_true")
    c.add_argument("--groups", action="store_true")
    args = ap.parse_args()
    if args.cmd == "check":
        return check(args)
    import equivalence as eq
    import mainframe_corpus as mc

    names = list(args.cases)
    if args.all_proven:
        names += sorted(p.parent.name for p in eq.CASES.glob("carddemo-*/case.json") if (p.parent / "port").is_dir())
    if args.all_cases:
        names += [n for n in all_cases() if n not in names]
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
        for w in x.get("parity_warnings", []):
            print(f"{'':<28}   parity warning: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
