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
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT))

from equivalence_common import engine_layouts, program_file  # noqa: E402 -- #5649: the engine's layouts, shared with equivalence_java
from gitgalaxy.core.estate_options import effective_options  # noqa: E402 -- #4704: the one options resolver

PKG = "com.gitgalaxy.modernized"


def proof_order(names: list[str]) -> list[str]:
    """#5882: the cases longest first, by recorded duration (proof_sweep's; an unmeasured case weighs the median).
    In name order a long case could start last and hold the shard while the other workers idle."""
    import proof_sweep as ps

    weight = ps.case_weights(sorted(set(names)), ps.load_durations())
    return sorted(names, key=lambda c: (-weight.get(c, 0), c))  # weight is {} when no case has a recorded duration


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

    from gitgalaxy.tools.cobol_to_java.det import program as P

    case = eq.load_case(name)
    stub = _service_stub(project, case["program"], case["program_source"])
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
    translated: list[Any] = []  # every program translated into this port (the main one first)
    called_holes: list[str] = []  # #4803 (owner): the holes of the programs this one LINKs / CALLs count for it
    port = work / name / "port"
    try:
        # case.json `strict_copy` (#4486): refuse a SYSLIB collision instead of taking the first library's member
        r = P.translate(program_file(case, corpus), dirs, stub, PKG, P.estate_files(project), project, style, typed,
                        groups, effective_options(case).layers, strict_copy=bool(case.get("strict_copy")),
                        layouts=engine_layouts(project, corpus, case["program_source"]))  # fmt: skip
    except Exception as e:
        out.update({"translated": False, "error": f"{type(e).__name__}: {e}"})
        return out
    translated.append(r)
    (port / "service").mkdir(parents=True, exist_ok=True)
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for x in r.extra:  # #5106: the sibling programs of the same source the program CALLs, each its own service
        (port / "service" / f"{x.service}.java").write_text(x.java, encoding="utf-8")
        r.stats["statements"] += x.stats["statements"]
        r.stats["translated"] += x.stats["translated"]
        r.stats["holes"] = [*r.stats["holes"], *x.stats["holes"]]
        called_holes += [f"{x.stats['program']}: {h}" for h in x.stats["holes"]]  # (#4803: counted for the caller)
        translated.append(x)
    for extra in _extra_programs(case):  # the programs the task LINKs to, and those it CALLs: translated the same way
        x_stub = _service_stub(project, extra["program"], extra["program_source"])  # #6839: an HLASM LINK target too
        try:
            x = P.translate(corpus / extra["program_source"], dirs, x_stub, PKG, P.estate_files(project), project,
                            style, typed, groups, effective_options(case, program=extra["program"]).layers,
                            strict_copy=bool(case.get("strict_copy")),
                            layouts=engine_layouts(project, corpus, extra["program_source"]))  # fmt: skip
        except Exception as e:
            out.update({"translated": False, "error": f"{extra['program']}: {type(e).__name__}: {e}"})
            return out
        (port / "service" / f"{x.service}.java").write_text(x.java, encoding="utf-8")
        r.stats["statements"] += x.stats["statements"]
        r.stats["translated"] += x.stats["translated"]
        r.stats["holes"] += x.stats["holes"]
        called_holes += [f"{extra['program']}: {h}" for h in x.stats["holes"]]
        translated.append(x)
        r.stats["warnings"] = [*r.stats.get("warnings", []), *x.stats.get("warnings", [])]
    for rel, text in P.runtime_files(PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    _snapshot_generated(port.parent / "generated", project, stub, [t.java for t in translated])
    out.update({"statements": r.stats["statements"], "translated_statements": r.stats["translated"],
                "holes": r.stats["holes"]})  # fmt: skip
    called_holes += unlisted_callees(case, [t.stats for t in translated])
    if called_holes:
        out["called_holes"] = called_holes
    if r.stats.get("warnings"):  # #4486: the SYSLIB collisions taken through the first library's member
        out["warnings"] = r.stats["warnings"]
    out.update(_parity(port, corpus, [(case["program"], str(program_file(case, corpus)))]
                       + [(x["program"], x["program_source"]) for x in _extra_programs(case)]))  # fmt: skip
    return out


def _snapshot_generated(dest: Path, project: Path, stub: str, services: list[str]) -> None:
    """#4847: the generated classes this port is proven against, copied to `dest` so `check` sees a generator (forge)
    change: the service stub (what the port replaces) and every other class of the generated project (DTO, entity,
    repository ...) whose name the stub or a translated service uses. They are never part of the proven port."""
    shutil.rmtree(dest, ignore_errors=True)
    words = set(re.findall(r"\w+", " ".join([stub, *services])))
    root = project / "src/main/java"
    for f in sorted(root.rglob("*.java")):
        if f.stem in words:
            (dest / f.relative_to(root)).parent.mkdir(parents=True, exist_ok=True)
            (dest / f.relative_to(root)).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")


def unlisted_callees(case: dict[str, Any], stats: list[dict[str, Any]]) -> list[str]:
    """#4803: the programs the port's programs CALL (the translator's own list, `stats["callees"]`) that the case does
    not translate into the port and the runtime does not model (det.gen.LIBRARY): the Java side would run the
    generator's empty `<Name>Service` stub there, so they count as called holes."""
    from gitgalaxy.tools.cobol_to_java.det.gen import LIBRARY

    have = {case["program"].upper()} | {x["program"].upper() for x in _extra_programs(case)}
    have |= {str(s.get("program", "")).upper() for s in stats}
    called = {c.upper() for s in stats for c in s.get("callees", [])}
    return [f"{n}: not in the case (the Java side would run the generator's empty stub)"
            for n in sorted(called - have - set(LIBRARY))]  # fmt: skip


def _service_stub(project: Path, program: str, source: str) -> str:
    """The forge's service class for `program`, the stub the translator fills. The forge makes none for an HLASM
    program (#5859), so that stub is the translator's own: for the case's program and for a LINK target (#6839)."""
    import equivalence_java as ej

    stub_file = project / "src/main/java" / PKG_DIR / "service" / f"{ej._service_class(program)}.java"
    if stub_file.is_file():
        return stub_file.read_text(encoding="utf-8")
    from gitgalaxy.tools.cobol_to_java.det import hlasm

    return hlasm.service_stub(Path(source).stem, PKG)


def _extra_programs(case: dict[str, Any]) -> list[dict[str, str]]:
    """The case's other programs, each translated into the port: `programs` (LINK targets) and `subprograms` (CALLed
    programs, #4803: the Java side runs the real program through handleCall, not the generator's empty stub). The
    COBOL side compiles a subprogram as SUB<NAME> and a LINK target under its own name; the Java side needs neither."""
    out = list(case.get("programs", []))
    seen = {x["program"].upper() for x in out} | {case["program"].upper()}
    for rel in case.get("subprograms", []):
        name = Path(rel).stem.upper()
        if name not in seen:
            seen.add(name)
            out.append({"program": name, "program_source": rel})
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
    t0 = time.monotonic()
    out = _prove(name, work, faults)
    out["proof_seconds"] = round(time.monotonic() - t0, 1)  # (the sweep balances its shards by it)
    return out


def _prove(name: str, work: Path, faults: str) -> dict[str, Any]:
    keep = work / name / "proof"
    shutil.rmtree(keep, ignore_errors=True)  # equivalence.py --keep wants a fresh directory
    argv = [
        sys.executable,
        str(TOOLS / "equivalence.py"),
        "run",
        name,
        "--port",
        str(work / name / "port"),
        "--keep",
        str(keep),
        "--faults",
        faults,
        "--sql-faults",
        "none" if faults == "none" else "auto",
    ]  # fmt: skip  (#4173: SQL faults with the rest)
    log = work / name / "proof.log"
    with log.open("wb") as fh:
        try:  # a port that loops (a translation fault) must not hang the run
            rc = subprocess.run(argv, stdout=fh, stderr=subprocess.STDOUT, cwd=REPO_ROOT, check=False,  # noqa: S603
                                timeout=PROOF_TIMEOUT).returncode  # fmt: skip
        except subprocess.TimeoutExpired:
            return {"proof_rc": None, "proved": False, "java_failed": True, "timed_out": True, "log": str(log)}
    report = keep / "report.json"
    rep = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    phases = keep / "phases.json"  # #5882: where the proof's time went (equivalence_common.phase)
    out = {"proof_rc": rc, "proved": rc == 0 and bool(rep) and not rep.get("java_failed"),
           "java_failed": bool(rep.get("java_failed")), "log": str(log),
           "phases": json.loads(phases.read_text(encoding="utf-8")) if phases.is_file() else {}}  # fmt: skip
    if rep.get("cobol_compile_failed"):  # #4493: only when set (python-test-traps.md: no always-present empty key)
        out["cobol_compile_failed"] = True
        out["cobc_stderr"] = rep.get("cobc_stderr", "")
    return out


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
        gen = port.parent / "generated"  # #4847: the generated classes the port is proven against (the forges' output)
        out[port.parent.name].update({"generated/" + f.relative_to(gen).as_posix(): f.read_text(encoding="utf-8")
                                      for f in sorted(gen.rglob("*.java"))})  # fmt: skip
    return out


def java_segments(text: str) -> list[tuple[str, str]]:
    """Java source as [(kind, text)], kind "code", "comment" or "literal" (a string, text block or char literal, quotes
    included), in order; joined they are the text. ValueError on an unterminated comment or literal."""
    out: list[tuple[str, str]] = []
    i, start, n = 0, 0, len(text)
    while i < n:
        c, two = text[i], text[i : i + 2]
        if two in ("//", "/*") or c in "\"'":
            if start < i:
                out.append(("code", text[start:i]))
            if two == "//":
                j = text.find("\n", i)
                j = n if j < 0 else j
                kind = "comment"
            elif two == "/*":
                j = text.find("*/", i + 2)
                if j < 0:
                    raise ValueError("unterminated comment")
                j += 2
                kind = "comment"
            else:
                quote = '"""' if text.startswith('"""', i) else c
                j = i + len(quote)
                while not text.startswith(quote, j):
                    if j >= n or (len(quote) == 1 and text[j] == "\n"):
                        raise ValueError("unterminated literal")
                    j += 2 if text[j] == "\\" else 1
                j += len(quote)
                kind = "literal"
            out.append((kind, text[i:j]))
            i = start = j
        else:
            i += 1
    if start < n:
        out.append(("code", text[start:]))
    return out


def java_code(text: str) -> str:
    """Java source without its comments and with each run of whitespace outside a literal one space (#4711): what
    javac compiles, so a comment-only edit -- a rule ID cited at its code site -- leaves it unchanged. The text itself
    when it does not lex (an unterminated comment or literal), so such a change still counts."""
    try:
        segs = java_segments(text)
    except ValueError:
        return text
    out, gap = [], []  # gap: the code and comments since the last literal, collapsed as one run
    for k, t in segs + [("literal", "")]:
        if k == "literal":
            out += [re.sub(r"\s+", " ", "".join(gap)), t]
            gap = []
        else:
            gap.append(" " if k == "comment" else t)
    return "".join(out).strip()


def compare(base: Path, new: Path) -> list[dict[str, Any]]:
    """Each case's port in `new` against `base`: unchanged, changed (the files and changed lines), new or gone.
    A runtime class (cobolrt/...) every port carries counts against a port only when its own code names that class
    (a DetSql change moves the Db2 ports, not every port): the files list says which runtime class moved it. A runtime
    class is compared as java_code (#4711): a change to its comments or layout alone moves no port."""
    import difflib

    a, b = _ports(base), _ports(new)
    rows = []
    for case in sorted(set(a) | set(b)):
        if case not in a or case not in b:
            rows.append({"case": case, "status": "new" if case not in a else "gone"})
            continue
        own = " ".join(t for rel, t in b[case].items() if not rel.startswith(("cobolrt/", "generated/")))
        files = []
        # (a base from before the snapshot existed, #4847, has no generated/ files: compare those only when both have)
        both = any(r.startswith("generated/") for r in a[case]) and any(r.startswith("generated/") for r in b[case])
        for rel in sorted(set(a[case]) | set(b[case])):
            if rel.startswith("generated/") and not both:
                continue
            x, y = a[case].get(rel, ""), b[case].get(rel, "")
            if x == y or (rel.startswith("cobolrt/") and java_code(x) == java_code(y)):
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
    flags = (
        ["--style", args.style]
        + (["--typed"] if args.typed else ["--no-typed"])
        + (["--groups"] if args.groups else [])
    )
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
        action=argparse.BooleanOptionalAction,
        default=True,
        help="standalone WORKING-STORAGE items as typed Java fields where every use allows (B3; the default since "
        "2026-10: it proves every case the byte form proves; --no-typed for the byte form)",
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
    c.add_argument("--typed", action=argparse.BooleanOptionalAction, default=True)
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
        t0 = time.monotonic()
        results.append(port_case(n, args.work, project, corpus, args.style, args.typed, args.groups))
        results[-1]["translate_seconds"] = round(
            time.monotonic() - t0, 1
        )  # (the estate, shared by a corpus's cases, is not counted)
    if not args.translate_only:
        eq.build_image()
        todo = [x for x in results if x.get("statements") is not None]
        rank = {c: i for i, c in enumerate(proof_order([x["case"] for x in todo]))}
        todo.sort(key=lambda x: rank[x["case"]])  # (results keep their order: summary.json is unchanged)
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            for x, p in zip(
                todo, ex.map(lambda x: prove(x["case"], args.work, args.faults), todo), strict=False
            ):  # reason: length may differ
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
