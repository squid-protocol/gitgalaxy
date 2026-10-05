#!/usr/bin/env python3
"""#4423: every committed port must compile against the generator at HEAD.

A generator change that renames a DTO or changes a generated method (#4390, #4342) can leave the committed ports no
longer compiling. Until now that showed only as ratcheted cells of the CICS crucible (which needs Docker and
GnuCOBOL, and reports per scenario) or as stale evidence records. This check names the ports, and runs no COBOL:

  * crucible ports (tests/cics_crucible/ports/<case>/<PROGRAM>/overlay): the case's Spring project is generated as
    the crucible's java-ported side does it (cics_crucible.forge: refactor, cobol-to-java h2), the case's overlays
    are laid over it and `mvn compile` runs. A port is named when the compiler's errors name one of its files (all
    of the case's ports when they name none).
  * equivalence ports (tests/equivalence/<case>/port, the CardDemo / CBSA / GenApp model and det ports): the
    corpus's project is generated once, as the equivalence harness does it (equivalence_java.prepare_project:
    refactor, h2, the case's culture), and compiled with Maven; then each port's files -- after the files of the
    ports it `uses_ports` -- are compiled with javac against that build. The harness's --reuse compiles a port the
    same way.

The fixture's scaffolding ports (tests/cics_crucible/fixture/ports) are not ports anyone proved; the runner's own
end-to-end test covers them.

    python tests/tools/ports_compile_check.py [--crucible ../cics-crucible] [--only crucible|equivalence]
        [--cases C ...] [--keep DIR] [--offline]

Exit 0 when every port compiles, 1 naming each one that does not, 2 when nothing could be checked.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import cics_crucible as cx  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
import equivalence_java as ej  # noqa: E402

EQUIVALENCE = HERE.parent / "equivalence"


def culprits(files: dict[str, list[Path]], errors: str) -> list[str]:
    """The ports whose files `errors` (the compiler's output) names; all of them when it names none."""
    named = [key for key, fs in files.items() if any(f.name in errors for f in fs)]
    return named or list(files)


def _error_lines(text: str) -> str:
    lines = [ln for ln in text.splitlines() if "ERROR" in ln or "error:" in ln]
    return "\n".join(lines[:20]) or "\n".join(text.splitlines()[-20:])


# ---- crucible ports -----------------------------------------------------------------------------
def check_crucible(root: Path, cases: Optional[set[str]], work: Path, offline: bool) -> tuple[int, list[str]]:
    """(ports checked, `crucible:<case>/<PROGRAM>` of each that does not compile)."""
    checked, failed = 0, []
    for d in cc.discover(root, cases):
        case = cc.load_case(d)
        overlays = cx.case_overlays(cx.PORTS_DIR / case.id)
        if not overlays:
            continue
        t0 = time.monotonic()
        verdict, _ = cx.forge(case, work / "crucible" / case.id, offline, list(overlays.values()))
        checked += len(overlays)
        ok = verdict.status == "pass"
        print(f"{'ok  ' if ok else 'FAIL'} crucible {case.id}: {', '.join(overlays)} ({time.monotonic() - t0:.0f}s)",
              flush=True)  # fmt: skip
        if not ok:
            files = {k: sorted(t.rglob("*.java")) for k, t in overlays.items()}
            bad = culprits(files, f"{verdict.reason}\n{verdict.detail}")
            failed += [f"crucible:{case.id}/{k}" for k in bad]
            print(f"::error title=Port does not compile::crucible {case.id}: {', '.join(bad)}: {verdict.reason}")
            print(f"{verdict.detail}\n", flush=True)
    return checked, failed


# ---- equivalence ports --------------------------------------------------------------------------
def equivalence_ports(cases: Optional[set[str]]) -> list[dict[str, Any]]:
    """Every equivalence case with a committed port directory holding Java, with its case.json."""
    out = []
    for cj in sorted(EQUIVALENCE.glob("*/case.json"), key=lambda p: p.parent.name):
        port = cj.parent / "port"
        if (cases is None or cj.parent.name in cases) and port.is_dir() and any(port.rglob("*.java")):
            out.append(json.loads(cj.read_text(encoding="utf-8")) | {"_name": cj.parent.name, "_port": port})
    return out


def port_files(case: dict[str, Any]) -> dict[str, Path]:
    """{path under the package root: file}: the ports it uses first, its own port's files over them."""
    files: dict[str, Path] = {}
    for other in case.get("uses_ports", []):
        base = EQUIVALENCE / other / "port"
        files.update({f.relative_to(base).as_posix(): f for f in sorted(base.rglob("*.java"))})
    base = case["_port"]
    files.update({f.relative_to(base).as_posix(): f for f in sorted(base.rglob("*.java"))})
    return files


def generate(corpus_name: str, culture: Optional[dict[str, Any]], work: Path) -> Path:
    """The corpus's generated Spring project, as the equivalence harness generates it (equivalence_java.prepare_project:
    refactor, config h2, the case's culture); not built. tests/tools/port_surface.py resurfaces ports against it."""
    import equivalence_cache
    import java_target_matrix as jtm
    import mainframe_corpus as mc

    (entry,) = mc.select([corpus_name])
    corpus = mc.require_clone(entry)
    work.mkdir(parents=True, exist_ok=True)
    with cx.quiet(work / "generate.log"):
        clean = equivalence_cache.refactor(corpus, work, scan=True)
        config = {**jtm.MATRIX["h2"], "culture": culture} if culture else jtm.MATRIX["h2"]
        return jtm.generate(clean, "h2", config, work)


def estate(corpus_name: str, culture: Optional[dict[str, Any]], work: Path,
           offline: bool) -> tuple[Optional[Path], Optional[str], str]:  # fmt: skip
    """The corpus's generated project, built: (target/classes, its compile classpath, '') or (None, None, errors)."""
    project = generate(corpus_name, culture, work)
    cp_file = work / "classpath.txt"
    ok, errors = cx.maven(project, ["compile", "dependency:build-classpath", f"-Dmdep.outputFile={cp_file}"],
                          offline, work / "compile.log")  # fmt: skip
    if not ok:
        return None, None, errors
    return project / "target" / "classes", cp_file.read_text(encoding="utf-8").strip(), ""


def javac(files: list[Path], classes: Path, classpath: str, out: Path) -> tuple[bool, str]:
    import java_target_matrix as jtm

    out.mkdir(parents=True, exist_ok=True)
    home = jtm._jdk(17) or os.environ.get("JAVA_HOME", "")
    exe = str(Path(home) / "bin" / "javac") if home else "javac"
    cp = os.pathsep.join(p for p in (str(classes), classpath) if p)
    proc = subprocess.run([exe, *ej.JAVAC_OPTIONS, "-d", str(out), "-cp", cp, *map(str, files)],  # noqa: S603
                          capture_output=True, text=True, check=False)  # fmt: skip
    return proc.returncode == 0, proc.stdout + proc.stderr


def check_equivalence(cases: Optional[set[str]], work: Path, offline: bool) -> tuple[int, list[str]]:
    """(ports checked, `equivalence:<case>` of each that does not compile)."""
    checked, failed = 0, []
    groups: dict[str, list[dict[str, Any]]] = {}
    for case in equivalence_ports(cases):
        groups.setdefault(json.dumps([case["corpus"], case.get("culture")], sort_keys=True), []).append(case)
    for n, (key, members) in enumerate(sorted(groups.items())):
        corpus, culture = json.loads(key)
        t0 = time.monotonic()
        classes, classpath, errors = estate(corpus, culture, work / "equivalence" / f"{n}_{corpus}", offline)
        names = [c["_name"] for c in members]
        checked += len(members)
        if classes is None:  # the generated project itself does not build: no port can be judged
            failed += [f"equivalence:{c}" for c in names]
            print(
                f"::error title=Generated project does not compile::{corpus}: {errors.splitlines()[0] if errors else ''}"
            )
            print(
                f"FAIL {corpus}: the generated project does not compile, so none of {', '.join(names)} does\n{errors}"
            )
            continue
        print(f"     {corpus}: generated and built ({time.monotonic() - t0:.0f}s)", flush=True)
        for case in members:
            files = port_files(case)
            ok, out = javac(
                list(files.values()), classes, classpath or "", work / "equivalence" / "ports" / case["_name"]
            )
            print(f"{'ok  ' if ok else 'FAIL'} equivalence {case['_name']}: {', '.join(sorted(files))}", flush=True)
            if not ok:
                failed.append(f"equivalence:{case['_name']}")
                print(f"::error title=Port does not compile::equivalence {case['_name']}: "
                      f"{_error_lines(out).splitlines()[0]}")  # fmt: skip
                print(_error_lines(out) + "\n", flush=True)
    return checked, failed


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crucible", type=Path, help="the cics-crucible checkout (default: $CICS_CRUCIBLE_PATH, else "
                    "../cics-crucible)")  # fmt: skip
    ap.add_argument("--only", choices=("crucible", "equivalence"), help="check only these ports")
    ap.add_argument("--cases", nargs="+", help="case ids (default: every case with committed ports)")
    ap.add_argument("--keep", type=Path, help="keep the work tree here (default: a temporary directory)")
    ap.add_argument("--offline", action="store_true", help="run Maven offline (mvn -o)")
    args = ap.parse_args(argv)
    cases = set(args.cases) if args.cases else None
    work = (args.keep or Path(tempfile.mkdtemp(prefix="ports_compile_"))).resolve()
    checked, failed = 0, []
    if args.only != "equivalence":
        root = cx.crucible_path(args.crucible)
        problem = cx.pin_mismatch(root)
        if problem:
            print(problem, file=sys.stderr)
            return 2
        n, bad = check_crucible(root, cases, work, args.offline)
        checked, failed = checked + n, failed + bad
    if args.only != "crucible":
        n, bad = check_equivalence(cases, work, args.offline)
        checked, failed = checked + n, failed + bad
    if not checked:
        print("no committed ports found: nothing was checked", file=sys.stderr)
        return 2
    if failed:
        print(f"\n{len(failed)} of {checked} committed port(s) do not compile against the generator at HEAD:")
        for key in failed:
            print(f"  - {key}")
        return 1
    print(f"\nall {checked} committed port(s) compile against the generator at HEAD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
