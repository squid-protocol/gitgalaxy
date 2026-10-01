#!/usr/bin/env python3
"""How far the deterministic translator (gitgalaxy/tools/cobol_to_java/det) gets on whole estates -- every COBOL
program of each mainframe corpus, not only the ones with an equivalence case.

    python tests/tools/det_survey.py --work DIR [--corpus NAME ...] [--no-compile]

Per corpus: the estate is generated once (java_target_matrix, config h2) and built (`mvn -o compile`); each
program is translated onto its generated service and the port compiled (javac) against the built estate. Per
program: its statements, how many translate, the holes by reason, whether the port compiles. A survey measures
translation, not correctness -- proving a port needs its equivalence case (tests/tools/det_port.py).
DIR/survey.json, DIR/survey.md."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT))

PKG = "com.gitgalaxy.modernized"
PKG_DIR = PKG.replace(".", "/")
EXTS = {".cbl", ".cob", ".cobol"}
COPY_EXTS = {".cpy", ".copy", ".cbl", ".cob", ""}


def jdk() -> str:
    return os.environ.get("JDK_17") or os.environ.get("JAVA_HOME") or "/usr/lib/jvm/java-17-openjdk-amd64"


def estate(corpus: Path, work: Path) -> tuple[Path, bool]:
    """(the generated project, whether it built)."""
    done = work / "project.txt"
    if done.is_file():
        project, built = done.read_text(encoding="utf-8").split()
        return Path(project), built == "built"
    import java_target_matrix as jtm

    work.mkdir(parents=True, exist_ok=True)
    clean = jtm.refactor(corpus, work, scan=True)
    project = jtm.generate(clean, "h2", jtm.MATRIX["h2"], work)
    env = dict(os.environ, JAVA_HOME=jdk())
    log = work / "mvn.log"
    with log.open("wb") as fh:
        rc = subprocess.run(["mvn", "-q", "-o", "compile", "-DskipTests"], cwd=project, env=env, stdout=fh,  # noqa: S607
                            stderr=subprocess.STDOUT, check=False).returncode  # fmt: skip
    done.write_text(f"{project} {'built' if rc == 0 else 'failed'}\n", encoding="utf-8")
    return project, rc == 0


def copy_dirs(corpus: Path) -> list[Path]:
    """Every directory holding a copybook-like member, the program's own first."""
    dirs = sorted({p.parent for p in corpus.rglob("*") if p.is_file() and p.suffix.lower() in COPY_EXTS
                   and ".git" not in p.parts})  # fmt: skip
    return dirs


def classpath(project: Path) -> str:
    jars = [str(p) for p in Path.home().glob(".m2/repository/**/*.jar") if "-sources" not in p.name]
    return os.pathsep.join([str(project / "target/classes"), *jars])


def survey_program(program: Path, corpus: Path, project: Path, dirs: list[Path], work: Path) -> dict[str, Any]:
    import equivalence_java as ej

    from gitgalaxy.tools.cobol_to_java.det import program as P

    row: dict[str, Any] = {"program": str(program.relative_to(corpus))}
    svc = ej._service_class(program.stem.upper())
    stub_file = project / "src/main/java" / PKG_DIR / "service" / f"{svc}.java"
    stub = stub_file.read_text(encoding="utf-8") if stub_file.is_file() else f"public class {svc} {{\n}}\n"
    row["stub"] = stub_file.is_file()
    own = [program.parent, *[d for d in dirs if d != program.parent]]
    try:
        r = P.translate(program, own, stub, PKG, P.estate_files(project), project)
    except Exception as e:  # a program the translator cannot take is a result
        row["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        row["where"] = traceback.extract_tb(e.__traceback__)[-1].name
        return row
    port = work / "ports" / program.stem / "service"
    port.mkdir(parents=True, exist_ok=True)
    (port / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    row.update({"statements": r.stats["statements"], "translated": r.stats["translated"],
                "holes": list(r.stats["holes"]), "inferred": r.stats.get("inferred", []),
                "kind": "cics" if "runTask(CicsTask" in stub else "call" if "handleCall(" in stub else
                "batch" if "runBatch(" in stub else "other"})  # fmt: skip
    return row


def compile_port(row: dict[str, Any], work: Path, runtime: Path, cp: str) -> None:
    src = work / "ports" / Path(row["program"]).stem
    out = work / "classes" / Path(row["program"]).stem
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    files = [str(p) for p in src.rglob("*.java")] + [str(p) for p in runtime.rglob("*.java")]
    res = subprocess.run([str(Path(jdk()) / "bin/javac"), "-nowarn", "-encoding", "UTF-8", "--release", "17",  # noqa: S603
                          "-proc:none", "-cp", cp, "-d", str(out), *files], capture_output=True, text=True,
                         check=False)  # fmt: skip
    row["compiles"] = res.returncode == 0
    if res.returncode:
        row["compile_errors"] = [ln for ln in res.stderr.splitlines() if ": error:" in ln][:5]


def hole_reason(h: str) -> str:
    """'line 123: EXEC EXEC CICS: X not modelled' -> a reason without the specifics."""
    why = h.split(": ", 1)[1] if ": " in h else h
    why = re.sub(r"'[^']*'|\"[^\"]*\"", "'…'", why)
    why = re.sub(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b", "<name>", why)  # data / paragraph names
    return why[:90]


def markdown(rows_by: dict[str, list[dict[str, Any]]]) -> str:
    lines = ["# Deterministic translation survey", "",
             "Every COBOL program of each corpus translated onto its generated service and compiled against the "
             "built estate. Translation only: a port is proven by its equivalence case (tests/tools/det_port.py).", "",
             "| corpus | programs | translated whole | with holes | refused | statements | translated | compiles |",
             "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    reasons: Counter[str] = Counter()
    refusals: Counter[str] = Counter()
    tot = Counter()
    for corpus, rows in rows_by.items():
        ok = [r for r in rows if "statements" in r]
        whole = sum(1 for r in ok if not r["holes"])
        st = sum(r["statements"] for r in ok)
        tr = sum(r["translated"] for r in ok)
        comp = sum(1 for r in ok if r.get("compiles"))
        tot.update({"p": len(rows), "w": whole, "h": len(ok) - whole, "e": len(rows) - len(ok), "s": st, "t": tr,
                    "c": comp})  # fmt: skip
        lines.append(f"| {corpus} | {len(rows)} | {whole} | {len(ok) - whole} | {len(rows) - len(ok)} | {st:,} | "
                     f"{tr:,} ({100 * tr / max(st, 1):.1f}%) | {comp} |")  # fmt: skip
        for r in ok:
            for h in r["holes"]:
                reasons[hole_reason(h)] += 1
        for r in rows:
            if "error" in r:
                refusals[re.sub(r"/\S+", "<path>", r["error"])[:110]] += 1
    lines.append(f"| **all** | **{tot['p']}** | **{tot['w']}** | **{tot['h']}** | **{tot['e']}** | **{tot['s']:,}** | "
                 f"**{tot['t']:,} ({100 * tot['t'] / max(tot['s'], 1):.1f}%)** | **{tot['c']}** |")  # fmt: skip
    lines += ["", "## Holes by reason", "", "| statements | reason |", "|---|---|"]
    lines += [f"| {n} | {why} |" for why, n in reasons.most_common(40)]
    lines += ["", "## Programs not translated at all", "", "| programs | why |", "|---|---|"]
    lines += [f"| {n} | {why} |" for why, n in refusals.most_common(30)]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--corpus", action="append", help="a corpus name (default: every fetched one)")
    ap.add_argument("--no-compile", action="store_true")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    import mainframe_corpus as mc

    root = mc.cache_root() if hasattr(mc, "cache_root") else Path(os.environ["GITGALAXY_MAINFRAME_CORPORA"])
    names = args.corpus or sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("_"))
    from gitgalaxy.tools.cobol_to_java.det import program as P
    from gitgalaxy.tools.cobol_to_java.det.source import bms_copybooks

    rows_by: dict[str, list[dict[str, Any]]] = {}
    for name in names:
        corpus = root / name
        work = args.work / name
        try:
            project, built = estate(corpus, work / "estate")
        except Exception as e:  # an estate the generator cannot take is a result too
            rows_by[name] = [{"program": "(estate)", "error": f"generation failed: {type(e).__name__}: {e}"}]
            continue
        # the runtime for this estate (its batch adapters only where the project has a batch package)
        runtime = work / "runtime"
        shutil.rmtree(runtime, ignore_errors=True)
        for rel, text in P.runtime_files(PKG, P.has_batch(project)).items():
            (runtime / rel).parent.mkdir(parents=True, exist_ok=True)
            (runtime / rel).write_text(text, encoding="utf-8")
        # symbolic maps the estate does not check in, generated from its BMS sources (after its own copybooks)
        bms = [p for p in corpus.rglob("*") if p.is_file() and p.suffix.lower() == ".bms" and ".git" not in p.parts]
        made = bms_copybooks(bms, work / "bms-copy")
        dirs = [*copy_dirs(corpus), work / "bms-copy"]
        print(f"{name}: {len(made)} symbolic maps generated from BMS", flush=True)
        progs = sorted(
            p for p in corpus.rglob("*") if p.is_file() and p.suffix.lower() in EXTS and ".git" not in p.parts
        )
        rows = [survey_program(p, corpus, project, dirs, work) for p in progs]
        if built and not args.no_compile:
            cp = classpath(project)
            todo = [r for r in rows if "statements" in r]
            with ThreadPoolExecutor(max_workers=args.jobs) as ex:
                list(ex.map(compile_port, todo, [work] * len(todo), [runtime] * len(todo), [cp] * len(todo)))
        for r in rows:
            r["estate_built"] = built
        rows_by[name] = rows
        print(f"{name}: {len(rows)} programs", flush=True)
    (args.work / "survey.json").write_text(json.dumps(rows_by, indent=1) + "\n", encoding="utf-8")
    (args.work / "survey.md").write_text(markdown(rows_by), encoding="utf-8")
    print((args.work / "survey.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
