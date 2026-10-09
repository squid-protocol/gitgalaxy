"""#4736: `CALL identifier` over the programs the identifier can hold (det/dyncall.py).

IBM Enterprise COBOL, CALL statement: with a data item as the program, the program is the item's content when the CALL
runs. The port resolves what the item can hold from the source (a VALUE clause, a VALUE table, MOVEs of literals) and
dispatches over those names; any other write, or a name it cannot call, is refused by name.

The end-to-end tests run each caller twice -- GnuCOBOL (`cobc -x -std=ibm`, the oracle, callees as `cobc -m` modules) and
the port (the callees' services written by hand: what the estate's generated services answer) -- and compare DISPLAY."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")
from test_det_programs import IMAGE, PKG, _java, program

E2E = pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker") or _java() is None,
                         reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip

CALLEE = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. {name}.\n       DATA DIVISION.\n       LINKAGE SECTION.\n"
    "       01 A PIC X(10).\n       PROCEDURE DIVISION USING A.\n           MOVE 'FROM-{tag}' TO A.\n           GOBACK.\n"
)
CALLEE_JAVA = (
    "package {pkg}.service;\nimport {pkg}.call.CobolRef;\npublic class {name}Service {{\n    public int handleCall(CobolRef<String> a) {{\n"
    '        a.set("FROM-{tag}".concat("          ").substring(0, 10));\n        return 0;\n    }}\n}}\n'
)
CALLEES = {"CALLEEA": "A", "CALLEEB": "B"}
ARG = ["01 ARG PIC X(10) VALUE 'UNCALLED'."]

# name -> (data, procedure): the output is the ARG each CALL leaves
SHAPES = {
    "value-only": (["01 PGM PIC X(8) VALUE 'CALLEEA'.", *ARG], ["CALL PGM USING ARG", "DISPLAY ARG"]),
    "move-literal": (["01 PGM PIC X(8).", *ARG], ["MOVE 'CALLEEB' TO PGM", "CALL PGM USING ARG", "DISPLAY ARG"]),
    "value-table": (
        [
            "01 TBL.",
            "   05 FILLER PIC X(8) VALUE 'CALLEEA'.",
            "   05 FILLER PIC X(8) VALUE 'NOT VLD'.",
            "   05 FILLER PIC X(8) VALUE 'CALLEEB'.",
            "01 TBL-R REDEFINES TBL.",
            "   05 T-NAME PIC X(8) OCCURS 3 TIMES.",
            "01 PGM PIC X(8).",
            *ARG,
        ],
        ["MOVE T-NAME(3) TO PGM", "CALL PGM USING ARG", "DISPLAY ARG"],
    ),  # the epscsmrt shape (the table's other entries are never moved)
    "two-values": (
        ["01 PGM PIC X(8) VALUE 'CALLEEA'.", "01 I PIC 9.", *ARG],
        [
            "PERFORM VARYING I FROM 1 BY 1 UNTIL I > 2",
            "    IF I = 1",
            "        MOVE 'CALLEEA' TO PGM",
            "    ELSE",
            "        MOVE 'CALLEEB' TO PGM",
            "    END-IF",
            "    CALL PGM USING ARG",
            "    DISPLAY ARG",
            "END-PERFORM",
        ],
    ),  # the straight-line MOVE is inside an IF: every write of PGM is a literal MOVE, so both names are dispatched
    "trailing-blanks": (["01 PGM PIC X(12) VALUE 'CALLEEB'.", *ARG], ["CALL PGM USING ARG", "DISPLAY ARG"]),
}


def _hole_whys(name: str, data: list[str], proc: list[str], tmp: Path, callees: dict | None = None) -> tuple:
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp / f"{name}.cbl"
    src.write_text(program(name.upper(), data, proc))
    project = tmp / f"project-{name}"
    svc = project / "src/main/java" / PKG / "service"
    svc.mkdir(parents=True)
    for c, tag in (callees or CALLEES).items():
        (svc / f"{c.title()}Service.java").write_text(CALLEE_JAVA.format(pkg=PKG, name=c.title(), tag=tag))
    r = P.translate(src, [], f"public class {name.title()}Service {{\n}}\n", PKG, None, project)
    return r.stats["holes"], r.java


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_the_shapes_translate_whole(shape, tmp_path):
    holes, java = _hole_whys(shape.replace("-", ""), *SHAPES[shape], tmp_path)
    assert not holes, holes
    assert "handleCall" in java
    if shape == "two-values":
        assert 'case "CALLEEA"' in java and 'case "CALLEEB"' in java and "default: throw new Hole(" in java
    else:
        assert 'replaceAll(" +$"' not in java  # a single name: the one call, no switch on the content


REFUSED = {
    "unknown-source": (
        ["01 PGM PIC X(8) VALUE 'CALLEEA'.", "01 OTHER PIC X(8).", *ARG],
        ["ACCEPT OTHER FROM DATE", "MOVE OTHER TO PGM", "CALL PGM USING ARG"],
        "not statically known",
    ),
    "no-value": (["01 PGM PIC X(8).", *ARG], ["CALL PGM USING ARG"], "no VALUE clause fixes its initial content"),
    "passed-by-reference": (
        ["01 PGM PIC X(8) VALUE 'CALLEEA'.", *ARG],
        ["CALL PGM USING PGM", "CALL PGM USING ARG"],
        "may change it",
    ),
    "redefines-alias": (
        ["01 PGM PIC X(8) VALUE 'CALLEEA'.", "01 ALIAS REDEFINES PGM PIC X(8).", *ARG],
        ["MOVE 'CALLEEB' TO ALIAS", "CALL PGM USING ARG"],
        "may change it",
    ),
    "group-move": (
        ["01 REC.", "   05 PGM PIC X(8) VALUE 'CALLEEA'.", "   05 FILL PIC X(2).", *ARG],
        ["MOVE SPACES TO REC", "CALL PGM USING ARG"],
        "may change it",
    ),
    "computed-subscript": (
        [
            "01 TBL.",
            "   05 FILLER PIC X(8) VALUE 'CALLEEA'.",
            "   05 FILLER PIC X(8) VALUE 'CALLEEB'.",
            "01 TBL-R REDEFINES TBL.",
            "   05 T-NAME PIC X(8) OCCURS 2 TIMES.",
            "01 PGM PIC X(8).",
            "01 I PIC 9.",
            *ARG,
        ],
        ["MOVE 1 TO I", "MOVE T-NAME(I) TO PGM", "CALL PGM USING ARG"],
        "a subscript that is not a literal",
    ),
    "dsntiac": (
        ["01 PGM PIC X(8) VALUE 'DSNTIAC'.", *ARG],
        ["CALL PGM USING ARG"],
        "DSNTIAC: Db2's message text is not modelled",
    ),
    "dsntiac-literal": (["01 X PIC X.", *ARG], ["CALL 'DSNTIAC' USING ARG"], "DSNTIAC: Db2's message text"),
    "not-in-the-estate": (
        ["01 PGM PIC X(8) VALUE 'NOPROG'.", *ARG],
        ["CALL PGM USING ARG"],
        "NOPROG: no program of that name",
    ),
    "a-reachable-bad-name": (
        ["01 PGM PIC X(8) VALUE 'CALLEEA'.", *ARG],
        ["MOVE 'NOT VLD' TO PGM", "CALL PGM USING ARG"],
        "'NOT VLD': not a program name the port matches",
    ),
    "lower-case": (
        ["01 PGM PIC X(8) VALUE 'calleea'.", *ARG],
        ["CALL PGM USING ARG"],
        "not a program name the port matches",
    ),
    "on-exception": (
        ["01 PGM PIC X(8) VALUE 'CALLEEA'.", *ARG],
        ["CALL PGM USING ARG", "    ON EXCEPTION DISPLAY 'NO'", "END-CALL"],
        "ON EXCEPTION / OVERFLOW phrases are not modelled",
    ),
}


@pytest.mark.parametrize("shape", sorted(REFUSED))
def test_what_cannot_be_known_is_refused_by_name(shape, tmp_path):
    data, proc, why = REFUSED[shape]
    holes, _ = _hole_whys(shape.replace("-", ""), data, proc, tmp_path)
    assert holes and all(why in h for h in holes[:1]), holes


def _cobc_run(work: Path, name: str, src: str) -> str:
    for c, tag in CALLEES.items():
        (work / f"{c}.cbl").write_text(CALLEE.format(name=c, tag=tag))
    (work / f"{name}.cbl").write_text(src)
    mods = " && ".join(f"cobc -m -std=ibm -fsign=EBCDIC {c}.cbl" for c in CALLEES)
    run = subprocess.run(["docker", "run", "--rm", "-v", f"{work}:/w", "-w", "/w", IMAGE, "sh", "-c",  # noqa: S607
                          f"{mods} && cobc -x -std=ibm -fsign=EBCDIC {name}.cbl -o prog 2>&1 && COB_LIBRARY_PATH=. ./prog"],
                         capture_output=True, text=True, check=False)  # fmt: skip
    assert run.returncode == 0, run.stdout + run.stderr
    return run.stdout


def _port_run(work: Path, name: str, src: str) -> str:
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (work / f"{name}.cbl").write_text(src)
    project = work / "project"
    svc = project / "src/main/java" / PKG / "service"
    svc.mkdir(parents=True)
    for c, tag in CALLEES.items():
        (svc / f"{c.title()}Service.java").write_text(CALLEE_JAVA.format(pkg=PKG, name=c.title(), tag=tag))
    r = P.translate(work / f"{name}.cbl", [], f"public class {name.title()}Service {{\n}}\n", PKG, None, project)
    assert not r.stats["holes"], r.stats["holes"]
    srcdir = work / "java"
    java = r.java.replace("import org.springframework.stereotype.Service;\n", "").replace("@Service\n", "")
    runtime = {k: v for k, v in P.runtime_files(PKG, batch=False).items() if not k.startswith("cobolrt/cics/")}
    extra = {
        "ObjectProvider.java": "package org.springframework.beans.factory;\npublic interface ObjectProvider<T> { T getObject(); }\n",
        f"{PKG}/call/CobolRef.java": f"package {PKG}.call;\npublic final class CobolRef<T> {{ private T v; "
        "public CobolRef(T v) { this.v = v; } public static <T> CobolRef<T> of(T v) { return new CobolRef<>(v); } "
        "public T get() { return v; } public void set(T v) { this.v = v; } }\n",
    }  # fmt: skip
    for rel, text in [(f"service/{r.service}.java", java), *runtime.items()]:
        (srcdir / PKG / rel).parent.mkdir(parents=True, exist_ok=True)
        (srcdir / PKG / rel).write_text(text)
    for rel, text in extra.items():
        p = srcdir / ("org/springframework/beans/factory" if rel == "ObjectProvider.java" else "") / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    for c, tag in CALLEES.items():
        (srcdir / PKG / "service" / f"{c.title()}Service.java").write_text(
            CALLEE_JAVA.format(pkg=PKG, name=c.title(), tag=tag)
        )
    rec = srcdir / PKG / "entity/vsam/CobolRecords.java"
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(f"package {PKG}.entity.vsam;\npublic final class CobolRecords {{\n    public static java.nio.charset."
                   "Charset charset() {\n        return java.nio.charset.StandardCharsets.ISO_8859_1;\n    }\n}\n")  # fmt: skip
    ctor = ", ".join(f"() -> new {PKG}.service.{c.title()}Service()" for c in CALLEES if f"{c.title()}Service>" in java)
    (srcdir / "Main.java").write_text(f"public class Main {{ public static void main(String[] a) {{ "
                                      f"new {PKG}.service.{r.service}({ctor}).runProgram(); }} }}\n")  # fmt: skip
    jdk = _java()
    subprocess.run([str(jdk / "javac"), "-nowarn", "-d", str(work / "classes"), *[str(f) for f in srcdir.rglob("*.java")]],  # noqa: S603
                   check=True)  # fmt: skip
    return subprocess.run([str(jdk / "java"), "-cp", str(work / "classes"), "Main"], capture_output=True, text=True,  # noqa: S603
                          check=True).stdout  # fmt: skip


@E2E
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_dynamic_call_end_to_end_against_cobc(shape, tmp_path):
    name = shape.replace("-", "")
    src = program(name.upper(), *SHAPES[shape])
    (tmp_path / "c").mkdir()
    (tmp_path / "j").mkdir()
    cobol = _cobc_run(tmp_path / "c", name.upper(), src)
    port = _port_run(tmp_path / "j", name, src)
    assert port == cobol and "FROM-" in cobol, (cobol, port)
