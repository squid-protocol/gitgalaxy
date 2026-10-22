"""#4893: IMS DL/I database calls (CALL 'CBLTDLI') on both runtimes -- the det translator (det/dli.py), the det runtime
(cobolrt/dli/DetDli.java) and the harness's COBOL-side model (tests/equivalence/ims/ggdli.c), register family I.

The level fixture (tests/equivalence/ims/fixture: LVLDBD, LVLPSB, DLILVL and expected.txt, written from IBM's
documentation before either runtime ran it) issues every modelled call and status code; with EQUIVALENCE_E2E=1 both
runtimes run it and each must print expected.txt and leave the same database."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_ims as ei  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

FIXTURE = ROOT / "tests" / "equivalence" / "ims" / "fixture"
IMAGE = "gitgalaxy-gnucobol:3"
PKG = "p"  # test_det_programs.PKG: its _batch_package writes the batch package there


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


E2E = pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker") or _jdk() is None,
                         reason="needs EQUIVALENCE_E2E=1, Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip


def _segment(name: str, data: bytes) -> bytes:
    return name.ljust(8).encode("ascii") + data


def _emp(no: str, name: str, sal: int) -> bytes:
    return f"{no}{name:<10}".encode("latin-1") + bytes.fromhex(f"{sal:05d}C") + b"   "


# the fixture's database: D100 (E001 with two skills, E002, project P1), D200 (E003 with one skill), D300
SEED = b"".join([
    _segment("DEPT", b"D100SALES           "), _segment("EMP", _emp("E001", "ALICE", 1000)),
    _segment("SKILL", b"S1COBOL "), _segment("SKILL", b"S2JAVA  "), _segment("EMP", _emp("E002", "BOB", 2000)),
    _segment("PROJ", b"P1ALPHA     "), _segment("DEPT", b"D200OPS             "),
    _segment("EMP", _emp("E003", "CAROL", 3000)), _segment("SKILL", b"S1DB2   "),
    _segment("DEPT", b"D300HR              "),
])  # fmt: skip


def _stage(dest: Path, seed: bytes = SEED) -> list[dict]:
    db = ei.dbd((FIXTURE / "LVLDBD.dbd").read_text(encoding="latin-1"), "LVLDBD.dbd")
    pcbs = ei.psb((FIXTURE / "LVLPSB.psb").read_text(encoding="latin-1"), "LVLPSB.psb", {db["name"]: db})
    dbd_cfg, psb_cfg = ei.config({db["name"]: db}, pcbs)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "dbd.cfg").write_text(dbd_cfg, encoding="ascii")
    (dest / "psb.cfg").write_text(psb_cfg, encoding="ascii")
    (dest / "seed.LVLDBD").write_bytes(seed)
    return pcbs


def _lines(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.splitlines() if ln.strip()]


# ---- the harness's reading of DBD / PSB sources ------------------------------------------------------------------
def test_the_fixtures_dbd_and_psb_become_the_configuration_both_sides_read(tmp_path):
    pcbs = _stage(tmp_path)
    assert (tmp_path / "dbd.cfg").read_text().splitlines() == [
        "DBD LVLDBD", "SEGM LVLDBD DEPT 0 20", "SEGM LVLDBD EMP DEPT 20", "SEGM LVLDBD SKILL EMP 8",
        "SEGM LVLDBD PROJ DEPT 12", "FIELD LVLDBD DEPT DEPTNO 1 4 C S", "FIELD LVLDBD DEPT DNAME 5 16 C -",
        "FIELD LVLDBD EMP EMPNO 1 4 C S", "FIELD LVLDBD EMP ENAME 5 10 C -", "FIELD LVLDBD EMP SAL 15 3 P -",
        "FIELD LVLDBD SKILL SKCODE 1 2 C S", "FIELD LVLDBD PROJ PROJNO 1 2 X S",
    ]  # fmt: skip
    assert (tmp_path / "psb.cfg").read_text().splitlines() == ["PCB LVLDBD A 10", "PCB LVLDBD G 10"]
    assert [p["procopt"] for p in pcbs] == ["A", "G"]


DBD_HEAD = "         DBD     NAME=X,ACCESS=(HIDAM,VSAM)\n"
SEGM = "         SEGM    NAME=R,PARENT=0,BYTES=10\n"
KEY = "         FIELD   NAME=(K,SEQ,U),START=1,BYTES=2,TYPE=C\n"


@pytest.mark.parametrize(
    "text, why",
    [
        (DBD_HEAD.replace("HIDAM", "HDAM") + SEGM + KEY, "ACCESS=HDAM"),
        (DBD_HEAD.replace("HIDAM,VSAM", "GSAM,BSAM") + SEGM + KEY, "ACCESS=GSAM"),
        (DBD_HEAD + SEGM.replace("BYTES=10", "BYTES=(10,4)") + KEY, "variable-length"),
        (DBD_HEAD + SEGM + KEY.replace("SEQ,U", "SEQ,M"), "non-unique sequence field"),
        (DBD_HEAD + SEGM, "no sequence field"),
        (DBD_HEAD + SEGM + KEY + "         SEGM    NAME=C,PARENT=((R,),(L,PHYSICAL,LDB)),BYTES=4\n" + KEY,
         "logical relationship"),
    ],
)  # fmt: skip
def test_a_dbd_the_model_does_not_model_is_refused_by_name(text, why):
    with pytest.raises(ei.Unsupported, match=re.escape(why)):
        ei.dbd(text, "X.dbd")


PCB = "P1       PCB     TYPE=DB,DBDNAME=X,PROCOPT=A,KEYLEN=2\n         SENSEG  NAME=R,PARENT=0\n"
GEN = "         PSBGEN  LANG=COBOL,PSBNAME=P,CMPAT=NO\n"


@pytest.mark.parametrize(
    "text, why",
    [
        (PCB + GEN.replace("CMPAT=NO", "CMPAT=YES"), "CMPAT=YES"),
        ("IO       PCB     TYPE=TP,MODIFY=YES\n" + PCB + GEN, "TYPE=TP PCB"),
        ("G        PCB     TYPE=GSAM,DBDNAME=X,PROCOPT=LS\n" + GEN, "TYPE=GSAM PCB"),
        (PCB.replace("KEYLEN=2", "KEYLEN=2,PROCSEQ=XIDX") + GEN, "PROCSEQ"),
        (PCB.replace("PROCOPT=A", "PROCOPT=L") + GEN, "load mode"),
        (PCB.replace("PARENT=0", "PARENT=0,PROCOPT=G") + GEN, "segment-level PROCOPT"),
        (PCB.replace("DBDNAME=X", "DBDNAME=Y") + GEN, "not one of the case's DBDs"),
    ],
)  # fmt: skip
def test_a_psb_the_model_does_not_model_is_refused_by_name(text, why):
    db = ei.dbd(DBD_HEAD + SEGM + KEY + "         SEGM    NAME=C,PARENT=R,BYTES=4\n" + KEY, "X.dbd")
    with pytest.raises(ei.Unsupported, match=re.escape(why)):
        ei.psb(text, "P.psb", {"X": db})


def test_a_pcb_not_sensitive_to_every_segment_is_refused():
    db = ei.dbd(DBD_HEAD + SEGM + KEY + "         SEGM    NAME=C,PARENT=R,BYTES=4\n" + KEY, "X.dbd")
    with pytest.raises(ei.Unsupported, match="partial sensitivity"):
        ei.psb(PCB + GEN, "P.psb", {"X": db})


def test_entry_using_reads_the_dlitcbl_entry_only():
    src = "\n".join(" " * 7 + ln for ln in ["PROCEDURE DIVISION USING A B.", "MAIN.",
                                            "    ENTRY 'DLITCBL' USING BY REFERENCE A", "        B.", "    GOBACK."])  # fmt: skip
    assert ei.entry_using(src) == ["A", "B"]
    assert ei.entry_using(src.replace("DLITCBL", "OTHER")) is None


def _unload(segments: list[tuple[str, bytes, int]], counts: dict[str, int]) -> bytes:
    """An HD unload as CardDemo's is laid out (register I6): header, segment records, trailer with counts."""

    def rec(level: int, name: str, body: bytes, length: int) -> bytes:
        head = bytes(4) + bytes([level, 0x80]) + b"\x00\x23" + length.to_bytes(2, "big") + name.ljust(8).encode("cp037")
        r = head + bytes(21) + body + b"\x00"
        return len(r).to_bytes(2, "big") + r[2:]

    trailer = bytearray(b"\x00\x00\x00\x00\x00\x98\x00\x50")
    for name, n in counts.items():
        trailer += name.ljust(8).encode("cp037") + bytes(24) + n.to_bytes(4, "big")
    trailer[0:2] = len(trailer).to_bytes(2, "big")
    header = bytearray(b"\x00\x18\x00\x00\x00\x80\x00\x50") + bytes(16)
    return bytes(header) + b"".join(rec(lv, n, b, len(b)) for n, b, lv in segments) + bytes(trailer)


def test_an_hd_unload_is_read_and_checked_against_its_trailer(tmp_path):
    f = tmp_path / "db.dat"
    root, child = "D1".encode("cp037") + b"\x00\x1c", "AB".encode("cp037")
    f.write_bytes(_unload([("ROOT", root, 1), ("KID", child, 2), ("KID", child, 2)], {"ROOT": 1, "KID": 2}))
    assert ei.unload(f) == [("ROOT", root), ("KID", child), ("KID", child)]
    f.write_bytes(_unload([("ROOT", root, 1), ("KID", child, 2)], {"ROOT": 1, "KID": 2}))
    with pytest.raises(ei.Unsupported, match="1 KID segments read, the trailer counts 2"):
        ei.unload(f)
    f.write_bytes(b"\x00\x05abc")
    with pytest.raises(ei.Unsupported, match="not an HD unload"):
        ei.unload(f)


def test_an_ebcdic_segment_is_laid_out_into_the_data_page():
    layout = [{"offset": 0, "bytes": 3, "usage": None}, {"offset": 3, "bytes": 2, "usage": "COMP-3"},
              {"offset": 5, "bytes": 2, "usage": "BINARY"}]  # fmt: skip
    data = "A{1".encode("cp037") + b"\x12\x3c" + b"\x00\x40"
    assert ei.from_ebcdic(data, layout, "latin-1") == b"A{1\x12\x3c\x00\x40"


def test_diff_db_pairs_segments_and_names_the_ones_that_differ():
    case = {"ims": {"dbd": [], "psb": ""}}
    ei_definitions = ei.dbd_definitions
    try:
        ei.dbd_definitions = lambda c, corpus: {
            "X": {"segments": [{"name": "R", "bytes": 2}, {"name": "C", "bytes": 1}]}
        }
        same = _segment("R", b"r1") + _segment("C", b"c")
        assert ei.diff_db(case, ROOT, "X", same, same) == {"records": 2, "equal": 2, "filler_differs": 0, "diffs": []}
        d = ei.diff_db(case, ROOT, "X", same, _segment("R", b"r2") + _segment("C", b"c"))
        assert d["equal"] == 1 and d["diffs"] == [{"segment": 1, "name": "R", "cobol": "7231", "java": "7232"}]
        d = ei.diff_db(case, ROOT, "X", same, _segment("R", b"r1"))
        assert d["equal"] == 1 and d["diffs"] == [{"segment": 2, "cobol": "C", "java": None}]
    finally:
        ei.dbd_definitions = ei_definitions


# ---- the det translator ------------------------------------------------------------------------------------------
LINKAGE = ["LINKAGE SECTION.", "01  PCB1.", "    05 P-DBD PIC X(8).", "    05 P-REST PIC X(38).",
           "01  PCB2 PIC X(46)."]  # fmt: skip
WS = ["WORKING-STORAGE SECTION.", "01  FN PIC X(4) VALUE 'GU  '.", "01  CNT PIC S9(9) COMP VALUE 3.",
      "01  IOA PIC X(20).", "01  SSA PIC X(9) VALUE 'DEPT     '.", "01  SSAS.", "    05 SSA1 PIC X(9) OCCURS 2."]  # fmt: skip


def _program(proc: list[str], entry: str | None = "    ENTRY 'DLITCBL' USING PCB1 PCB2.", using: str = "") -> str:
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. DLIT.", "DATA DIVISION.", *WS, *LINKAGE,
             f"PROCEDURE DIVISION{using}.", "MAIN-PARA.", *([entry] if entry else []), *proc, "    GOBACK."]  # fmt: skip
    return "\n".join(" " * 7 + ln for ln in lines) + "\n"


def _translate(tmp_path: Path, src: str):
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(ROOT / "tests" / "cobol_mainframe"))
    import test_det_programs as tdp
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "DLIT.cbl").write_text(src)
    project = tmp_path / "project"
    tdp._batch_package(project / "src/main/java")
    return P.translate(tmp_path / "DLIT.cbl", [], "public class DlitService {\n}\n", PKG, None, project)


@pytest.mark.parametrize("using", ["", " USING PCB1 PCB2", " USING PCB2"])
def test_cbltdli_is_a_detdli_call_and_the_entry_binds_the_pcbs(tmp_path, using):
    """IMS enters the program at DLITCBL (with its own USING list) whatever PROCEDURE DIVISION USING says; every
    function, any number of SSAs; RETURN-CODE 0 after each call (I1)."""
    r = _translate(tmp_path, _program(["    CALL 'CBLTDLI' USING FN PCB1 IOA", "    CALL 'CBLTDLI' USING FN PCB2 IOA SSA SSA1(2)"],
                                      using=using))  # fmt: skip
    assert not r.stats["holes"], r.stats["holes"]
    java = r.java
    assert re.search(r"DetDli\.enter\(\w+, \w+\);", java)
    assert len(re.findall(r"DetDli\.call\(", java)) == 2
    assert re.search(r"DetDli\.call\(\w+, \w+, \w+, \w+, \w+\.at\(", java)
    assert java.count("BigDecimal.ZERO, false, CS);") >= 2
    assert "DetDli.leave();" in java
    assert "parmText" not in java  # no PARM written over the first PCB


@pytest.mark.parametrize(
    "proc, entry, why",
    [
        (["    CALL 'CBLTDLI' USING FN PCB1 IOA"], None, "a program IMS does not enter at ENTRY 'DLITCBL'"),
        (["    CALL 'CBLTDLI' USING CNT FN PCB1 IOA"], "    ENTRY 'DLITCBL' USING PCB1 PCB2.", "parameter-count form"),
        (["    CALL 'CBLTDLI' USING FN IOA IOA"], "    ENTRY 'DLITCBL' USING PCB1 PCB2.", "not one IMS passed"),
        (["    CALL 'CBLTDLI' USING FN PCB1"], "    ENTRY 'DLITCBL' USING PCB1 PCB2.", "up to 15 SSAs expected"),
        (["    CALL 'CBLTDLI' USING FN PCB1 'X'"], "    ENTRY 'DLITCBL' USING PCB1 PCB2.", "BY REFERENCE expected"),
        (["    CALL 'AIBTDLI' USING FN PCB1 IOA"], "    ENTRY 'DLITCBL' USING PCB1 PCB2.", "through an AIB"),
        (["    CALL 'CEETDLI' USING FN PCB1 IOA"], "    ENTRY 'DLITCBL' USING PCB1 PCB2.", "Language Environment DL/I"),
    ],
)  # fmt: skip
def test_what_the_translator_does_not_model_is_a_hole_by_name(tmp_path, proc, entry, why):
    r = _translate(tmp_path, _program(proc, entry=entry))
    assert len(r.stats["holes"]) == 1 and why in r.stats["holes"][0], r.stats["holes"]


# ---- the level fixture on both runtimes (the first-time number: PR body) ----------------------------------------------
def _cobol_side(work: Path, seed: bytes = SEED) -> tuple[str, bytes]:
    pcbs = _stage(work / "dli", seed)
    (work / "dliout").mkdir()
    src = work / "src"
    src.mkdir()
    shutil.copy(FIXTURE / "DLILVL.cbl", src / "DLILVL.cbl")
    shutil.copy(ei.STUB, src / "ggdli.c")
    (src / "EQDRIVER.cbl").write_text("\n".join(" " * 7 + ln for ln in ei.cobol_driver("DLITCBL", pcbs)) + "\n")
    script = ("cobc -x -std=ibm -fsign=EBCDIC -o prog src/EQDRIVER.cbl src/DLILVL.cbl src/ggdli.c && "
              "GGDLI_DIR=/w/dli GGDLI_OUT=/w/dliout ./prog")  # fmt: skip
    run = subprocess.run(["docker", "run", "--rm", "-v", f"{work}:/w", "-w", "/w", IMAGE, "sh", "-c", script],  # noqa: S607
                         capture_output=True, text=True, check=False)  # fmt: skip
    assert run.returncode == 0, run.stdout + run.stderr
    return run.stdout, (work / "dliout" / "LVLDBD.out").read_bytes()


def _java_side(work: Path, seed: bytes = SEED) -> tuple[str, bytes]:
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(ROOT / "tests" / "cobol_mainframe"))
    import test_det_programs as tdp
    from gitgalaxy.tools.cobol_to_java.det import program as P

    _stage(work / "dli", seed)
    (work / "dliout").mkdir()
    project = work / "project"
    tdp._batch_package(project / "src/main/java")
    r = P.translate(FIXTURE / "DLILVL.cbl", [], "public class DlilvlService {\n}\n", PKG, None, project)
    assert not r.stats["holes"], r.stats["holes"]
    srcdir = work / "java"
    java = r.java.replace("import org.springframework.stereotype.Service;\n", "").replace("@Service\n", "")
    runtime = {k: v for k, v in P.runtime_files(PKG, batch=True).items()
               if not k.startswith(("cobolrt/cics/", "cobolrt/sql/"))}  # fmt: skip
    for rel, text in [(f"service/{r.service}.java", java), *runtime.items()]:
        (srcdir / PKG / rel).parent.mkdir(parents=True, exist_ok=True)
        (srcdir / PKG / rel).write_text(text)
    tdp._batch_package(srcdir)
    rec = srcdir / PKG / "entity/vsam/CobolRecords.java"
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(f"package {PKG}.entity.vsam;\npublic final class CobolRecords {{\n    public static java.nio.charset."
                   "Charset charset() {\n        return java.nio.charset.StandardCharsets.ISO_8859_1;\n    }\n}\n")  # fmt: skip
    b = f"{PKG}.batch"
    (srcdir / "Main.java").write_text(
        f"public class Main {{ public static void main(String[] a) {{ new {PKG}.service.{r.service}("
        f'new {b}.DatasetResolver("{work}"), new {b}.CobolFiles("", ""), new {b}.MainframeClock("", "UTC"))'
        ".runBatch(java.util.List.of(), null); } }\n"
    )
    jdk = _jdk()
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(work / "classes"),  # noqa: S603
                    *map(str, srcdir.rglob("*.java"))], check=True)  # fmt: skip
    run = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8",  # noqa: S603
                          f"-Dgitgalaxy.dli.dir={work / 'dli'}", f"-Dgitgalaxy.dli.out={work / 'dliout'}",
                          "-cp", str(work / "classes"), "Main"], capture_output=True, check=True)  # fmt: skip
    return run.stdout.decode("utf-8"), (work / "dliout" / "LVLDBD.out").read_bytes()


@E2E
def test_the_level_fixture_prints_what_ibm_documents_on_both_runtimes(tmp_path):
    expected = _lines((FIXTURE / "expected.txt").read_text(encoding="latin-1"))
    cobol_out, cobol_db = _cobol_side(tmp_path / "cobol")
    java_out, java_db = _java_side(tmp_path / "java")
    assert _lines(cobol_out) == expected
    assert _lines(java_out) == expected
    assert cobol_db == java_db
    sizes = {"DEPT": 20, "EMP": 20, "SKILL": 8, "PROJ": 12}
    keys = [(n, d[:4].decode("latin-1").strip()) for n, d in ei.split(cobol_db, sizes)]
    assert keys == [("DEPT", "D100"), ("EMP", "E002"), ("EMP", "E005"), ("PROJ", "P1AL"), ("DEPT", "D150"),
                    ("DEPT", "D200"), ("EMP", "E003"), ("SKILL", "S1DB"), ("DEPT", "D300")]  # fmt: skip


@E2E
@pytest.mark.parametrize(
    "seed, why",
    [
        (_segment("EMP", _emp("E001", "X", 1)), "a seed segment before its parent"),
        (_segment("DEPT", b"D200".ljust(20)) + _segment("DEPT", b"D100".ljust(20)), "not in hierarchic sequence"),
        (_segment("NOSEG", b"x"), "a seed segment the DBD does not define"),
    ],
)  # fmt: skip
def test_a_seed_out_of_sequence_is_refused_by_both_runtimes(tmp_path, seed, why):
    with pytest.raises(AssertionError, match=re.escape(why)):
        _cobol_side(tmp_path / "cobol", seed)
    with pytest.raises(subprocess.CalledProcessError) as e:
        _java_side(tmp_path / "java", seed)
    assert why in (e.value.stderr or b"").decode("utf-8")


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_accept_from_date_day_and_time_read_the_runs_clock(tmp_path):
    """ACCEPT FROM DATE / DATE YYYYMMDD / DAY / DAY YYYYDDD / TIME (PAUDBUNL's 1000-INITIALIZE): the clock's digits as
    the unsigned integer item IBM names, the day of the year counted in a leap year."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    for rel, text in P.runtime_files("t", batch=False).items():
        if not rel.startswith(("cobolrt/cics/", "cobolrt/sql/")):
            (src / "t" / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / "t" / rel).write_text(text)
    forms = ["DATE", "DATE YYYYMMDD", "DAY", "DAY YYYYDDD", "TIME"]
    calls = " ".join(f'System.out.println(t.cobolrt.Cobol.displayText(t.cobolrt.Accept.from("2024031514302512+0000", '
                     f'"{f}"), java.nio.charset.StandardCharsets.ISO_8859_1));' for f in forms)  # fmt: skip
    (src / "Main.java").write_text(f"public class Main {{ public static void main(String[] a) {{ {calls} }} }}\n")
    jdk = _jdk()
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                    *map(str, src.rglob("*.java"))], check=True)  # fmt: skip
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp",  # noqa: S603
                          str(tmp_path / "classes"), "Main"], capture_output=True, check=True).stdout.decode("utf-8").split()  # fmt: skip
    assert out == ["240315", "20240315", "24075", "2024075", "14302512"]


# ---- EXEC DLI under CICS: SCHD PSB, TERM and DIBSTAT (#5278, register I5) ---------------------------------------------
CICS_STUB = "public class DlitService { void f() { runTask(CicsTask t); } }"


def _cics_program(proc: list[str]) -> str:
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. DLIT.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
             "01  PSB-NAME PIC X(8) VALUE 'PSBX'.", "01  PSB-NUM PIC S9(4) COMP VALUE 1.", "01  IMS-RC PIC XX.",
             "01  IOA PIC X(20).", "PROCEDURE DIVISION.", "MAIN-PARA.", *proc, "    GOBACK."]  # fmt: skip
    return "\n".join(" " * 7 + ln for ln in lines) + "\n"


def _wrap(stmt: str) -> list[str]:
    """The statement as lines inside fixed-form columns 8-72."""
    lines, cur = [], ""
    for w in stmt.split():
        if len(cur) + len(w) > 50:
            lines.append("    " + cur)
            cur = ""
        cur = f"{cur} {w}".strip()
    return [*lines, "    " + cur]


def _translate_cics(tmp_path: Path, src: str):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "DLIT.cbl").write_text(src)
    return P.translate(tmp_path / "DLIT.cbl", [], CICS_STUB, PKG, None, tmp_path / "project")


@pytest.mark.parametrize(
    "stmt, call",
    [
        ("EXEC DLI SCHD PSB((PSB-NAME)) NODHABEND END-EXEC", r"schedule\(\w+, true\)"),
        ("EXEC DLI SCHD PSB((PSB-NAME)) END-EXEC", r"schedule\(\w+, false\)"),
        ("EXEC DLI SCHD PSB(PSBPAUTB) NODHABEND END-EXEC", r'schedule\("PSBPAUTB", true\)'),
        ("EXEC DLI SCHD PSB('psbpautb') END-EXEC", r'schedule\("PSBPAUTB", false\)'),
        ("EXEC DLI TERM END-EXEC", r"terminate\(\)"),
    ],
)  # fmt: skip
def test_exec_dli_schd_and_term_answer_dibstat_through_the_runtime(tmp_path, stmt, call):
    """SCHD PSB (a name, a literal or a data area, with or without NODHABEND) and TERM are DetDli calls whose answer
    lands in DIBSTAT, the DIB item the translator supplies; every form is a whole translation."""
    r = _translate_cics(tmp_path, _cics_program([f"    {stmt}", "    MOVE DIBSTAT TO IMS-RC"]))
    assert not r.stats["holes"], r.stats["holes"]
    assert re.search(rf"Cobol\.move\(\w+\.cobolrt\.dli\.DetDli\.{call}, \w+_DIBSTAT, CS\);", r.java), r.java


@pytest.mark.parametrize("verb", ["GU", "GN", "GNP"])
@pytest.mark.parametrize("pcb, pcb_java", [("1", "1"), ("PSB-NUM", r"Cobol\.num\(\w+, CS\)\.intValue\(\)")])
@pytest.mark.parametrize(
    "segs, ssas",
    [
        ("", r""),
        ("SEGMENT(DEPT)", r', \w+\.cobolrt\.dli\.DetDli\.ssa\("DEPT"\)'),
        ("SEGMENT (DEPT) WHERE (DEPTNO = IOA) SEGMENT(EMP)",
         r', \w+\.cobolrt\.dli\.DetDli\.ssa\("DEPT", "DEPTNO", "EQ", \w+\), \w+\.cobolrt\.dli\.DetDli\.ssa\("EMP"\)'),
        ("SEGMENT(S1) WHERE(F1 >= IOA)", r', \w+\.cobolrt\.dli\.DetDli\.ssa\("S1", "F1", "GE", \w+\)'),
        ("SEGMENT(S1) WHERE(F1 NE IOA)", r', \w+\.cobolrt\.dli\.DetDli\.ssa\("S1", "F1", "NE", \w+\)'),
        ("SEGMENT(S1) WHERE(F1 <= IOA)", r', \w+\.cobolrt\.dli\.DetDli\.ssa\("S1", "F1", "LE", \w+\)'),
        ("SEGMENT(S1) WHERE(F1>IOA)", r', \w+\.cobolrt\.dli\.DetDli\.ssa\("S1", "F1", "GT", \w+\)'),
    ],
)  # fmt: skip
def test_exec_dli_gets_are_detdli_get_with_their_ssas_and_answer_dibstat(tmp_path, verb, pcb, pcb_java, segs, ssas):
    """GU / GN / GNP, the PCB a literal or a data item, no SEGMENT, a SEGMENT, a WHERE with each operator spelling and
    more than one level: one DetDli.get whose answer lands in DIBSTAT; a whole translation."""
    stmt = f"EXEC DLI {verb} USING PCB({pcb}) {segs} INTO(IOA) END-EXEC"
    r = _translate_cics(tmp_path, _cics_program([*_wrap(stmt), "    MOVE DIBSTAT TO IMS-RC"]))
    assert not r.stats["holes"], r.stats["holes"]
    rx = rf'Cobol\.move\(\w+\.cobolrt\.dli\.DetDli\.get\("{verb}", {pcb_java}, \w+{ssas}\), \w+_DIBSTAT, CS\);'
    assert re.search(rx, r.java), r.java


def test_exec_dli_get_without_using_is_the_same_command(tmp_path):
    r = _translate_cics(tmp_path, _cics_program(["    EXEC DLI GU PCB(1) SEGMENT(S1) INTO(IOA) END-EXEC"]))
    assert not r.stats["holes"], r.stats["holes"]
    assert 'DetDli.get("GU", 1, ' in r.java


@pytest.mark.parametrize(
    "stmt, why",
    [
        ("EXEC DLI GHU USING PCB(1) SEGMENT(S1) INTO(IOA) END-EXEC", "EXEC DLI GHU: this command is not modelled"),
        ("EXEC DLI GU USING PCB(1) SEGMENT(S1) END-EXEC", "one PCB(n) first and one INTO(area)"),
        ("EXEC DLI GU SEGMENT(S1) PCB(1) INTO(IOA) END-EXEC", "one PCB(n) first and one INTO(area)"),
        ("EXEC DLI GU USING PCB(1) SEGMENT(S1) INTO(IOA) FIELDLENGTH(4) END-EXEC", "FIELDLENGTH: only PCB"),
        ("EXEC DLI GU USING PCB(1) SEGMENT(S1) INTO(IOA) KEYS(IOA) END-EXEC", "KEYS: only PCB"),
        ("EXEC DLI GU USING PCB(1) SEGMENT(S1) WHERE(F1 = IOA AND F2 = IOA) INTO(IOA) END-EXEC", "only field op value"),
        ("EXEC DLI GU USING PCB(1) WHERE(F1 = IOA) INTO(IOA) END-EXEC", "WHERE must follow its SEGMENT"),
        ("EXEC DLI GU USING PCB(1) SEGMENT(S1) WHERE(F1 = 5) INTO(IOA) END-EXEC", "not a data area"),
        ("EXEC DLI GU USING PCB(1) SEGMENT(S1 S2) INTO(IOA) END-EXEC", "is not a segment name"),
        ("EXEC DLI REPL USING PCB(1) SEGMENT(S1) END-EXEC", "one PCB(n) first and one FROM(area)"),
        ("EXEC DLI REPL USING PCB(1) FROM(IOA) END-EXEC", "SEGMENT(s) expected, once"),
        ("EXEC DLI REPL USING PCB(1) SEGMENT(S1) SEGMENT(S2) FROM(IOA) END-EXEC", "SEGMENT(s) expected, once"),
        ("EXEC DLI REPL USING PCB(1) SEGMENT(S1) WHERE(F1 = IOA) FROM(IOA) END-EXEC", "REPL WHERE: only PCB"),
        ("EXEC DLI REPL USING PCB(1) SEGMENT(S1) FROM(IOA) SEGLENGTH(20) END-EXEC", "REPL SEGLENGTH: only PCB"),
        ("EXEC DLI DLET USING PCB(1) SEGMENT(S1) FROM(IOA) FIELDLENGTH(4) END-EXEC", "DLET FIELDLENGTH: only PCB"),
        ("EXEC DLI ISRT USING PCB(1) SEGMENT(S1) FROM(IOA) FROM(IOA) END-EXEC", "one PCB(n) first and one FROM(area)"),
        ("EXEC DLI ISRT USING PCB(1) SEGMENT(S1) FROM(IOA) KEYS(IOA) END-EXEC", "ISRT KEYS: only PCB"),
        ("EXEC DLI ISRT USING SEGMENT(S1) PCB(1) FROM(IOA) END-EXEC", "one PCB(n) first and one FROM(area)"),
        ("EXEC DLI ISRT USING PCB(1) FROM(IOA) END-EXEC", "SEGMENT(s) expected"),
        ("EXEC DLI ISRT USING PCB(1) WHERE(F1 = IOA) SEGMENT(S1) FROM(IOA) END-EXEC", "WHERE must follow its SEGMENT"),
        ("EXEC DLI ISRT USING PCB(1) SEGMENT(S1) FROM(5) END-EXEC", "not a data area"),
        ("EXEC DLI ISRT USING PCB(1) SEGMENT(S1 S2) FROM(IOA) END-EXEC", "is not a segment name"),
        ("EXEC DLI SCHD PSB((PSB-NAME)) NODHABEND SYSSERVE END-EXEC", "EXEC DLI SCHD: only PSB"),
        ("EXEC DLI SCHD END-EXEC", "EXEC DLI SCHD: only PSB"),
        ("EXEC DLI TERM PSB END-EXEC", "EXEC DLI TERM: no option"),
        ("EXEC DLI SCHD PSB((PSB-NUM)) END-EXEC", "not a DISPLAY item"),
    ],
)  # fmt: skip
def test_the_exec_dli_forms_not_modelled_are_holes_by_name(tmp_path, stmt, why):
    r = _translate_cics(tmp_path, _cics_program(_wrap(stmt)))
    assert len(r.stats["holes"]) == 1 and why in r.stats["holes"][0], r.stats["holes"]


@pytest.mark.parametrize("pcb, pcb_java", [("1", "1"), ("PSB-NUM", r"Cobol\.num\(\w+, CS\)\.intValue\(\)")])
@pytest.mark.parametrize(
    "stmt, call",
    [
        ("ISRT USING PCB({p}) SEGMENT(S1) FROM(IOA)", r'execIsrt\({p}, \w+, -1, {d}\.ssa\("S1"\)\)'),
        ("ISRT USING PCB({p}) SEGMENT(S1) FROM(IOA) SEGLENGTH(LENGTH OF IOA)", r'execIsrt\({p}, \w+, BigDecimal\.valueOf\(20\)\.intValue\(\), {d}\.ssa\("S1"\)\)'),
        ("ISRT USING PCB({p}) SEGMENT(S1) WHERE(F1 = IOA) SEGMENT(S2) FROM(IOA) SEGLENGTH(8)",
         r'execIsrt\({p}, \w+, 8, {d}\.ssa\("S1", "F1", "EQ", \w+\), {d}\.ssa\("S2"\)\)'),
        ("REPL USING PCB({p}) SEGMENT(s1) FROM(IOA)", r'execChange\("REPL", {p}, \w+, "S1"\)'),
        ("DLET USING PCB({p}) SEGMENT(S1) FROM(IOA)", r'execChange\("DLET", {p}, \w+, "S1"\)'),
    ],
)  # fmt: skip
def test_exec_dli_isrt_repl_dlet_are_detdli_calls_and_answer_dibstat(tmp_path, pcb, pcb_java, stmt, call):
    """ISRT (a root, a child under a qualified parent, with and without SEGLENGTH), REPL and DLET, the PCB a literal or
    a data item: one DetDli call whose answer lands in DIBSTAT; a whole translation."""
    d = r"\w+\.cobolrt\.dli\.DetDli"
    r = _translate_cics(
        tmp_path, _cics_program([*_wrap(f"EXEC DLI {stmt.format(p=pcb)} END-EXEC"), "    MOVE DIBSTAT TO IMS-RC"])
    )
    assert not r.stats["holes"], r.stats["holes"]
    rx = rf"Cobol\.move\({d}\.{call.format(p=pcb_java, d=d)}, \w+_DIBSTAT, CS\);"
    assert re.search(rx, r.java), r.java


def test_exec_dli_in_a_batch_program_is_a_hole_and_other_dib_fields_are_no_such_item(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    r = _translate(tmp_path, _program(["    EXEC DLI TERM END-EXEC"], entry="    ENTRY 'DLITCBL' USING PCB1 PCB2."))
    assert len(r.stats["holes"]) == 1 and "EXEC DLI outside CICS" in r.stats["holes"][0], r.stats["holes"]
    r = _translate_cics(tmp_path, _cics_program(["    MOVE DIBSEGM TO IOA"]))
    assert any("DIBSEGM" in h for h in r.stats["holes"]), r.stats["holes"]  # only DIBSTAT is supplied


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_detdli_get_answers_the_status_ibm_gives_through_the_pcb_by_number(tmp_path):
    """GU with and without WHERE, GN walking on, a miss (GE), an unknown segment (AC) and field (AK), PCB 2 (PROCOPT G,
    no hold); a get before SCHD, after TERM or through a PCB the PSB lacks is refused by name."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    _stage(tmp_path / "dli")
    src = tmp_path / "src"
    for rel, text in P.runtime_files("t", batch=False).items():
        if not rel.startswith(("cobolrt/cics/", "cobolrt/sql/")):
            (src / "t" / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / "t" / rel).write_text(text)
    d = "t.cobolrt.dli.DetDli"
    key = f'{d}.ssa("DEPT", "DEPTNO", "EQ", v)'
    steps = [
        f'try {{ {d}.get("GU", 1, into); }} catch (UnsupportedOperationException e) {{ p(e.getMessage()); }}',
        f'{d}.schedule("LVLPSB", true); v.storage().bytes = "D200".getBytes();',
        f'p({d}.get("GU", 1, into, {key}) + new String(st.bytes, 0, 20));',
        f'p({d}.get("GN", 2, into, {d}.ssa("EMP")));',
        f'p({d}.get("GU", 2, into, {key}, {d}.ssa("EMP")) + new String(st.bytes, 0, 14));',
        f'p({d}.get("GN", 2, into, {d}.ssa("EMP")));',
        'v.storage().bytes = "D999".getBytes();',
        f'p({d}.get("GU", 1, into, {key}));',
        f'p({d}.get("GU", 1, into, {d}.ssa("DEPT", "NOFIELD", "EQ", v)));',
        f'p({d}.get("GU", 1, into, {d}.ssa("NOSEG")));',
        f'try {{ {d}.get("GU", 3, into); }} catch (UnsupportedOperationException e) {{ p(e.getMessage()); }}',
        f'try {{ {d}.get("GU", 0, into); }} catch (UnsupportedOperationException e) {{ p(e.getMessage()); }}',
        f'{d}.terminate();',
        f'try {{ {d}.get("GU", 1, into); }} catch (UnsupportedOperationException e) {{ p(e.getMessage()); }}',
    ]  # fmt: skip
    setup = ("t.cobolrt.Storage st = new t.cobolrt.Storage(64); t.cobolrt.Field into = t.cobolrt.Field.group(st, 0, 20); "
             "t.cobolrt.Storage vs = new t.cobolrt.Storage(4); "
             "t.cobolrt.Field v = t.cobolrt.Field.alphanumeric(vs, 0, 4, false); ")  # fmt: skip
    (src / "Main.java").write_text(
        'public class Main { static void p(String s) { System.out.println("[" + s + "]"); } '
        f"public static void main(String[] a) {{ {setup}{' '.join(steps)} }} }}\n"
    )
    jdk = _jdk()
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                    *map(str, src.rglob("*.java"))], check=True)  # fmt: skip
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", f"-Dgitgalaxy.dli.dir={tmp_path / 'dli'}", "-cp", str(tmp_path / "classes"),  # noqa: S603
                          "Main"], capture_output=True, check=True).stdout.decode("utf-8").splitlines()  # fmt: skip
    no_pcb = "CBLTDLI: a PCB number the scheduled PSB does not have is not modelled"
    no_psb = "CBLTDLI: an EXEC DLI command with no PSB scheduled is not modelled"
    assert out == [f"[{no_psb}]", "[  D200OPS             ]", "[  ]", "[  E003CAROL     ]", "[GB]", "[GE]", "[AK]", "[AC]",
                   f"[{no_pcb}]", f"[{no_pcb}]", f"[{no_psb}]"]  # fmt: skip


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_detdli_schedule_and_terminate_answer_the_status_ibm_gives(tmp_path):
    """SCHD: blank, the PCBs at their start; a second SCHD of the scheduled PSB is TC (with NODHABEND; without it the
    task would abend: refused); TERM: blank, then SCHD is blank again; a TERM with nothing scheduled is refused."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    _stage(tmp_path / "dli")
    src = tmp_path / "src"
    for rel, text in P.runtime_files("t", batch=False).items():
        if not rel.startswith(("cobolrt/cics/", "cobolrt/sql/")):
            (src / "t" / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / "t" / rel).write_text(text)
    d = "t.cobolrt.dli.DetDli"
    body = (f'System.out.println("[" + {d}.schedule("PSBX", true) + "]"); '
            f'System.out.println("[" + {d}.schedule("PSBX", true) + "]"); '
            f'try {{ {d}.schedule("PSBX", false); }} catch (UnsupportedOperationException e) {{ '
            'System.out.println(e.getMessage()); } '
            f'System.out.println("[" + {d}.terminate() + "]"); '
            f'System.out.println("[" + {d}.schedule("PSBX", false) + "]"); {d}.terminate(); '
            f'try {{ {d}.terminate(); }} catch (UnsupportedOperationException e) {{ System.out.println(e.getMessage()); }}')  # fmt: skip
    (src / "Main.java").write_text(f"public class Main {{ public static void main(String[] a) {{ {body} }} }}\n")
    jdk = _jdk()
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                    *map(str, src.rglob("*.java"))], check=True)  # fmt: skip
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", f"-Dgitgalaxy.dli.dir={tmp_path / 'dli'}", "-cp", str(tmp_path / "classes"),  # noqa: S603
                          "Main"], capture_output=True, check=True).stdout.decode("utf-8").splitlines()  # fmt: skip
    assert out == [
        "[  ]",
        "[TC]",
        "CBLTDLI: a SCHD of a PSB already scheduled, without NODHABEND (the task would abend) is not modelled",
        "[  ]",
        "[  ]",
        "CBLTDLI: a TERM with no PSB scheduled is not modelled",
    ]


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize(
    ("plan", "expect"),
    [
        # TC means the task already holds the PSB: scheduled, so a TERM and a SCHD after it are valid (COPAUA0C's path)
        ("# DLI SCHD 1 TC", ["[TC]", "[  ]", "[  ]", "[  ]"]),
        # any other status is not performed: nothing is scheduled, so a TERM is refused
        ("# DLI SCHD 1 AI", ["[AI]", "CBLTDLI: a TERM with no PSB scheduled is not modelled"]),
        # a planned TC while the PSB is held: TC, still held, and no NODHABEND needed to answer it
        ("# DLI SCHD 2 TC", ["[  ]", "[TC]", "[  ]", "[  ]"]),
    ],
)
def test_detdli_a_planned_schd_tc_leaves_the_psb_scheduled(tmp_path, plan, expect):
    """#5233: a planned SCHD TC is IBM's 'PSB already scheduled', so the PSB is held and TERM after it is valid; a planned
    SCHD of another status is not performed and leaves nothing scheduled."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    _stage(tmp_path / "dli")
    (tmp_path / "plan.txt").write_text(plan + "\n")
    src = tmp_path / "src"
    for rel, text in P.runtime_files("t", batch=False).items():
        if not rel.startswith(("cobolrt/cics/", "cobolrt/sql/")):
            (src / "t" / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / "t" / rel).write_text(text)
    d = "t.cobolrt.dli.DetDli"
    if plan.endswith("AI"):
        body = (f'System.out.println("[" + {d}.schedule("PSBX", true) + "]"); '
                f'try {{ {d}.terminate(); }} catch (UnsupportedOperationException e) {{ System.out.println(e.getMessage()); }}')  # fmt: skip
    elif "SCHD 2" in plan:
        body = (f'System.out.println("[" + {d}.schedule("PSBX", true) + "]"); '
                f'System.out.println("[" + {d}.schedule("PSBX", false) + "]"); '
                f'System.out.println("[" + {d}.terminate() + "]"); '
                f'System.out.println("[" + {d}.schedule("PSBX", false) + "]");')  # fmt: skip
    else:
        body = (f'System.out.println("[" + {d}.schedule("PSBX", true) + "]"); '
                f'System.out.println("[" + {d}.terminate() + "]"); '
                f'System.out.println("[" + {d}.schedule("PSBX", false) + "]"); '
                f'System.out.println("[" + {d}.terminate() + "]");')  # fmt: skip
    (src / "Main.java").write_text(f"public class Main {{ public static void main(String[] a) {{ {body} }} }}\n")
    jdk = _jdk()
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                    *map(str, src.rglob("*.java"))], check=True)  # fmt: skip
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", f"-Dgitgalaxy.dli.dir={tmp_path / 'dli'}",  # noqa: S603
                          f"-Dgitgalaxy.faults.plan={tmp_path / 'plan.txt'}", "-cp", str(tmp_path / "classes"),
                          "Main"], capture_output=True, check=True).stdout.decode("utf-8").splitlines()  # fmt: skip
    assert out == expect


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_detdli_isrt_repl_dlet_answer_the_status_ibm_gives_through_the_pcb_by_number(tmp_path):
    """ISRT of a root and of a child under a qualified parent (blank), a duplicate (II), a missing parent (GE), a
    PROCOPT G PCB (AM); REPL after a get-hold (blank, the segment changed), with no hold (DJ), with the key changed
    (DA); DLET (blank, then GE); a SEGLENGTH that is not the fixed length, or a SEGMENT that is not the held type, is
    refused by name."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    _stage(tmp_path / "dli")
    src = tmp_path / "src"
    for rel, text in P.runtime_files("t", batch=False).items():
        if not rel.startswith(("cobolrt/cics/", "cobolrt/sql/")):
            (src / "t" / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / "t" / rel).write_text(text)
    d = "t.cobolrt.dli.DetDli"
    key = f'{d}.ssa("DEPT", "DEPTNO", "EQ", v)'
    refused = "catch (UnsupportedOperationException e) { p(e.getMessage()); }"
    steps = [
        f'{d}.schedule("LVLPSB", true); put("D200", v);',
        f'p({d}.get("GU", 1, into, {key}));',
        f'put("D200RENAMED        ", into); p({d}.execChange("REPL", 1, into, "DEPT"));',
        f'p({d}.execChange("REPL", 1, into, "DEPT"));',
        f'p({d}.get("GU", 1, into, {key}) + new String(st.bytes, 0, 20));',
        f'put("D999RENAMED        ", into); p({d}.execChange("REPL", 1, into, "DEPT"));',
        f'put("D200", v); {d}.get("GU", 1, into, {key});',
        f'try {{ {d}.execChange("REPL", 1, into, "EMP"); }} {refused}',
        f'put("D400NEWDEPT         ", into); p({d}.execIsrt(1, into, -1, {d}.ssa("DEPT")));',
        f'p({d}.execIsrt(1, into, 20, {d}.ssa("DEPT")));',
        f'put("E009ZED                 ", into); p({d}.execIsrt(1, into, 20, {key}, {d}.ssa("EMP")));',
        f'p({d}.get("GU", 1, into, {key}, {d}.ssa("EMP", "EMPNO", "EQ", ev)) + new String(st.bytes, 0, 8));',
        f'try {{ {d}.execIsrt(1, into, 19, {key}, {d}.ssa("EMP")); }} {refused}',
        f'put("D999", v); p({d}.execIsrt(1, into, 20, {key}, {d}.ssa("EMP")));',
        f'p({d}.execIsrt(2, into, -1, {d}.ssa("DEPT")));',
        f'put("D400", v); {d}.get("GU", 1, into, {key}); p({d}.execChange("DLET", 1, into, "DEPT"));',
        f'p({d}.get("GU", 1, into, {key}));',
        f'try {{ {d}.execIsrt(3, into, -1, {d}.ssa("DEPT")); }} {refused}',
    ]  # fmt: skip
    setup = ("static t.cobolrt.Storage st = new t.cobolrt.Storage(64); "
             "static t.cobolrt.Field into = t.cobolrt.Field.group(st, 0, 20); "
             "static t.cobolrt.Storage vs = new t.cobolrt.Storage(4); "
             "static t.cobolrt.Field v = t.cobolrt.Field.alphanumeric(vs, 0, 4, false); "
             "static t.cobolrt.Storage es = new t.cobolrt.Storage(4); "
             "static t.cobolrt.Field ev = t.cobolrt.Field.alphanumeric(es, 0, 4, false); "
             "static void put(String s, t.cobolrt.Field f) { byte[] b = s.getBytes(); "
             "System.arraycopy(b, 0, f.storage().bytes, f.offset(), b.length); } ")  # fmt: skip
    (src / "Main.java").write_text(
        'public class Main { static void p(String s) { System.out.println("[" + s + "]"); } '
        f'{setup}public static void main(String[] a) {{ put("E009", ev); {" ".join(steps)} }} }}\n'
    )
    jdk = _jdk()
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                    *map(str, src.rglob("*.java"))], check=True)  # fmt: skip
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", f"-Dgitgalaxy.dli.dir={tmp_path / 'dli'}", "-cp", str(tmp_path / "classes"),  # noqa: S603
                          "Main"], capture_output=True, check=True).stdout.decode("utf-8").splitlines()  # fmt: skip
    nothing = "CBLTDLI: an ISRT whose SEGLENGTH is not the segment's fixed length is not modelled"
    wrong = "CBLTDLI: an EXEC DLI REPL whose SEGMENT is not the held segment's type is not modelled"
    no_pcb = "CBLTDLI: a PCB number the scheduled PSB does not have is not modelled"
    assert out == ["[  ]", "[  ]", "[DJ]", "[  D200RENAMED         ]", "[DA]", f"[{wrong}]", "[  ]", "[II]", "[  ]",
                   "[  E009ZED ]", f"[{nothing}]", "[GE]", "[AM]", "[  ]", "[GE]", f"[{no_pcb}]"]  # fmt: skip


def test_every_burned_exec_dli_command_translates_cics_and_cbpaup0c_bmp(tmp_path):
    """#5278: CardDemo's EXEC DLI programs under CICS (COPAUA0C, COPAUS0C, COPAUS1C: SCHD, TERM, GU, GNP, ISRT, REPL)
    have no EXEC DLI hole; CBPAUP0C (a BMP: GN, GNP, DLET, CHKP) has none either (#5857)."""
    pytest.importorskip("tree_sitter_language_pack")
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    corpus = corpora / "aws-mainframe-modernization-carddemo"
    cbl = corpus / "app/app-authorization-ims-db2-mq/cbl"
    if not cbl.is_dir():
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    copies = [corpus / "app/cpy", corpus / "app/app-authorization-ims-db2-mq/cpy"]
    copies.append(corpus / "app/app-authorization-ims-db2-mq/cpy-bms")
    cics = "public class X { void f() { runTask(CicsTask t); } }"  # the marker that makes it a CICS port

    def holes(name: str, stub: str) -> list[str]:
        res = P.translate(cbl / f"{name}.cbl", copies, stub, "pkg", None, tmp_path / name)
        return [str(h) for h in res.stats["holes"]]

    for name in ("COPAUA0C", "COPAUS0C", "COPAUS1C"):
        got = holes(name, cics)
        assert not [h for h in got if "EXEC DLI" in h or "DIBSTAT" in h], (name, got)
    batch = holes("CBPAUP0C", "public class X { }")  # #5857: a BMP entered by USING its I/O PCB and DB PCB
    assert not [h for h in batch if "EXEC DLI" in h or "DIBSTAT" in h], batch
    res = P.translate(cbl / "CBPAUP0C.cbl", copies, "public class X { }", "pkg", None, tmp_path / "all")
    assert res.stats["holes"] == [] and res.stats["translated"] == res.stats["statements"], res.stats  # 110 of 110

    # #5278 checklist c:595f3352: COPAUA0C's INITIALIZE ... REPLACING of the table PA-ACCOUNT-STATUS (C17) is no hole,
    # and without an estate (no file is mapped) the only holes left are its three READ KEYLENGTH(LENGTH OF ...), which
    # translate once the case maps the files (det_port: carddemo-copaua0c 344/344 translated)
    left = holes("COPAUA0C", cics)
    assert not [h for h in left if "INITIALIZE" in h], left
    assert len(left) == 3 and all("READ KEYLENGTH(LENGTH OF" in h for h in left), left


BMP_WS = ["WORKING-STORAGE SECTION.", "01  PCB-NUM PIC S9(4) COMP VALUE +2.", "01  CHK-ID.", "    05 FILLER PIC X(4) VALUE 'RMAD'.",
          "    05 CHK-CTR PIC 9(4) VALUE ZEROES.", "01  SHORT-ID PIC X(4).", "01  SEG-A PIC X(20).", "01  SEG-B PIC X(20)."]  # fmt: skip


def _bmp(proc: list[str], using: str = " USING IO-PCB DB-PCB") -> str:
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. DLIT.", "DATA DIVISION.", *BMP_WS, "LINKAGE SECTION.",
             "01  IO-PCB PIC X.", "01  DB-PCB PIC X(46).", f"PROCEDURE DIVISION{using}.", "MAIN-PARA.", *proc,
             "    IF DIBSTAT = SPACES", "       DISPLAY 'OK'", "    END-IF", "    GOBACK."]  # fmt: skip
    return "\n".join(" " * 7 + ln for ln in lines) + "\n"


def _bmp_stmt(stmt: str) -> list[str]:
    return _wrap(stmt)


@pytest.mark.parametrize(
    "stmt, call",
    [
        ("EXEC DLI GN USING PCB(PCB-NUM) SEGMENT(DEPT) INTO(SEG-A) END-EXEC", r'DetDli\.get\("GN", .*Cobol\.num\(\w+, CS\)\.intValue\(\), \w+, .*ssa\("DEPT"\)\)'),
        ("EXEC DLI GNP USING PCB(2) SEGMENT(EMP) INTO(SEG-A) END-EXEC", r'DetDli\.get\("GNP", .*2, \w+, .*ssa\("EMP"\)\)'),
        ("EXEC DLI DLET USING PCB(PCB-NUM) SEGMENT(EMP) FROM(SEG-A) END-EXEC", r'DetDli\.execChange\("DLET", .*"EMP"\)'),
        ("EXEC DLI CHKP ID(CHK-ID) END-EXEC", r"DetDli\.checkpoint\(\w+\)"),
        ("EXEC DLI CHKP ID (CHK-ID) END-EXEC", r"DetDli\.checkpoint\(\w+\)"),
    ],
)  # fmt: skip
def test_a_bmp_with_exec_dli_is_entered_with_its_io_pcb_and_answers_dibstat(tmp_path, stmt, call):
    """#5857 (I5): PROCEDURE DIVISION USING io-pcb db-pcb, PCB(n) counting the I/O PCB; GN / GNP / DLET / CHKP answer
    DIBSTAT, which a batch port now has (the CICS lane's DIB)."""
    r = _translate(tmp_path, _bmp(_bmp_stmt(stmt)))
    assert not r.stats["holes"], r.stats["holes"]
    java = r.java
    assert re.search(r"DetDli\.enterBmp\(\w+, \w+\);", java), java
    assert re.search(call, java), java
    assert re.search(r"Cobol\.move\(__PKG__|Cobol\.move\(p\.cobolrt\.dli\.DetDli", java) or "Cobol.move(" in java
    assert "DetDli.leave();" in java
    assert "parmText" not in java


@pytest.mark.parametrize(
    "stmt, why",
    [
        ("EXEC DLI CHKP END-EXEC", "only ID(area) is modelled"),
        ("EXEC DLI CHKP ID(CHK-ID) SAVE END-EXEC", "only ID(area) is modelled"),
        ("EXEC DLI CHKP ID('RMAD0001') END-EXEC", "not a data area"),
        ("EXEC DLI ISRT USING PCB(2) SEGMENT(DEPT) FROM(SEG-A) END-EXEC", None),
        ("EXEC DLI XRST END-EXEC", "this command is not modelled"),
        ("EXEC DLI ROLB END-EXEC", "this command is not modelled"),
        ("EXEC DLI GN USING PCB(2) SEGMENT(DEPT) INTO(SEG-A) FIELDLENGTH(4) END-EXEC", "only PCB, SEGMENT, WHERE and INTO"),
    ],
)  # fmt: skip
def test_a_bmp_exec_dli_not_modelled_is_a_hole_by_name(tmp_path, stmt, why):
    r = _translate(tmp_path, _bmp(_bmp_stmt(stmt)))
    if why is None:  # the writes are the CICS lane's forms: the same DetDli calls in a BMP
        assert not r.stats["holes"], r.stats["holes"]
        assert "DetDli.execIsrt(" in r.java
        return
    assert len(r.stats["holes"]) == 1 and why in r.stats["holes"][0], r.stats["holes"]


def test_a_bmp_supplies_only_dibstat_of_the_dib(tmp_path):
    """#5857: the DIB of a BMP is the CICS lane's: DIBSTAT (the only field the runtime sets) reads, any other DIB field
    (DIBSEGM) is `no such item`, a hole by name."""
    r = _translate(tmp_path, _bmp(_bmp_stmt("EXEC DLI GN USING PCB(2) SEGMENT(DEPT) INTO(SEG-A) END-EXEC")
                                  + ["    MOVE DIBSEGM TO SEG-B"]))  # fmt: skip
    assert len(r.stats["holes"]) == 1 and "DIBSEGM" in r.stats["holes"][0], r.stats["holes"]


def test_chkp_outside_a_bmp_and_cbltdli_in_a_bmp_are_holes_by_name(tmp_path):
    r = _translate_cics(tmp_path, _cics_program(_wrap("EXEC DLI CHKP ID(IOA) END-EXEC")))
    assert any("CHKP" in h for h in r.stats["holes"]), r.stats["holes"]
    r = _translate(tmp_path, _bmp(["    CALL 'CBLTDLI' USING FN DB-PCB SEG-A"]))
    assert any("not modelled" in h and "CBLTDLI" in h for h in r.stats["holes"]), r.stats["holes"]
    # a USING of one item is not a BMP's I/O PCB and DB PCB: EXEC DLI stays a hole outside CICS
    r = _translate(tmp_path, _bmp(_bmp_stmt("EXEC DLI GN USING PCB(2) SEGMENT(DEPT) INTO(SEG-A) END-EXEC"),
                                  using=" USING IO-PCB"))  # fmt: skip
    assert any("EXEC DLI outside CICS" in h for h in r.stats["holes"]), r.stats["holes"]


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_detdli_bmp_entry_numbers_pcbs_after_the_io_pcb_and_chkp_releases_positions(tmp_path):
    """enterBmp: PCB(1) is the I/O PCB (refused by name), PCB(2) the first DB PCB; a GN walks on, CHKP answers blank
    and the next GN starts at the database's beginning; a CHKP ID of another length, or CHKP after a SCHD (not a BMP),
    is refused by name."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    _stage(tmp_path / "dli")
    src = tmp_path / "src"
    for rel, text in P.runtime_files("t", batch=False).items():
        if not rel.startswith(("cobolrt/cics/", "cobolrt/sql/")):
            (src / "t" / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / "t" / rel).write_text(text)
    d = "t.cobolrt.dli.DetDli"
    refused = "catch (UnsupportedOperationException e) { p(e.getMessage()); }"
    steps = [
        f'{d}.enterBmp(io, m1, m2);',
        f'try {{ {d}.get("GN", 1, into, {d}.ssa("DEPT")); }} {refused}',
        f'p({d}.get("GN", 2, into, {d}.ssa("DEPT")) + new String(st.bytes, 0, 4));',
        f'p({d}.get("GN", 2, into, {d}.ssa("DEPT")) + new String(st.bytes, 0, 4));',
        f'p({d}.checkpoint(id));',
        f'p({d}.get("GN", 2, into, {d}.ssa("DEPT")) + new String(st.bytes, 0, 4));',
        f'try {{ {d}.checkpoint(sid); }} {refused}',
        f'try {{ {d}.get("GN", 4, into); }} {refused}',
        f'{d}.reset(); {d}.schedule("LVLPSB", true);',
        f'try {{ {d}.checkpoint(id); }} {refused}',
    ]  # fmt: skip
    setup = ("static t.cobolrt.Storage st = new t.cobolrt.Storage(64); "
             "static t.cobolrt.Field into = t.cobolrt.Field.group(st, 0, 20); "
             "static t.cobolrt.Field io = t.cobolrt.Field.group(new t.cobolrt.Storage(8), 0, 8); "
             "static t.cobolrt.Field m1 = t.cobolrt.Field.group(new t.cobolrt.Storage(64), 0, 64); "
             "static t.cobolrt.Field m2 = t.cobolrt.Field.group(new t.cobolrt.Storage(64), 0, 64); "
             "static t.cobolrt.Field id = t.cobolrt.Field.group(new t.cobolrt.Storage(8), 0, 8); "
             "static t.cobolrt.Field sid = t.cobolrt.Field.group(new t.cobolrt.Storage(4), 0, 4); ")  # fmt: skip
    (src / "Main.java").write_text(
        'public class Main { static void p(String s) { System.out.println("[" + s + "]"); } '
        f"{setup}public static void main(String[] a) {{ {' '.join(steps)} }} }}\n"
    )
    jdk = _jdk()
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                    *map(str, src.rglob("*.java"))], check=True)  # fmt: skip
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", f"-Dgitgalaxy.dli.dir={tmp_path / 'dli'}", "-cp", str(tmp_path / "classes"),  # noqa: S603
                          "Main"], capture_output=True, check=True).stdout.decode("utf-8").splitlines()  # fmt: skip
    io_pcb = "CBLTDLI: an EXEC DLI database command on PCB(1), the I/O PCB is not modelled"
    no_pcb = "CBLTDLI: a PCB number the scheduled PSB does not have is not modelled"
    assert out == [f"[{io_pcb}]", "[  D100]", "[  D200]", "[  ]", "[  D100]",
                   "[CBLTDLI: a CHKP ID that is not 8 bytes is not modelled]", f"[{no_pcb}]",
                   "[CBLTDLI: an EXEC DLI CHKP outside a BMP entered by USING its I/O PCB is not modelled]"]  # fmt: skip
