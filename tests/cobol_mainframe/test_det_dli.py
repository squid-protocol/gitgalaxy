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


def _stage(dest: Path, seed: bytes = SEED, psb: str | None = None) -> list[dict]:
    db = ei.dbd((FIXTURE / "LVLDBD.dbd").read_text(encoding="latin-1"), "LVLDBD.dbd")
    pcbs = ei.psb(psb or (FIXTURE / "LVLPSB.psb").read_text(encoding="latin-1"), "LVLPSB.psb", {db["name"]: db})
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
GSAM_DBD = "         DBD     NAME=G,ACCESS=(GSAM,BSAM)\nDSG001   DATASET DD1=IN,DD2=OUT,RECORD=(100),RECFM=F\n         DBDGEN\n"
SEGM = "         SEGM    NAME=R,PARENT=0,BYTES=10\n"
KEY = "         FIELD   NAME=(K,SEQ,U),START=1,BYTES=2,TYPE=C\n"


@pytest.mark.parametrize(
    "text, why",
    [
        (DBD_HEAD.replace("HIDAM", "HDAM") + SEGM + KEY, "ACCESS=HDAM"),
        (DBD_HEAD.replace("HIDAM,VSAM", "GSAM,BSAM") + SEGM + KEY, "a GSAM database needs one DATASET"),
        (GSAM_DBD.replace("RECFM=F", "RECFM=V"), "a GSAM database needs one DATASET"),
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
        ("G        PCB     TYPE=GSAM,DBDNAME=X,PROCOPT=LS\n" + GEN, "GSAM DBD X is not one of"),
        ("G        PCB     TYPE=GSAM,DBDNAME=G,PROCOPT=GO\n" + GEN, "reading a GSAM file is not"),
        (PCB.replace("KEYLEN=2", "KEYLEN=2,PROCSEQ=XIDX") + GEN, "PROCSEQ"),
        (PCB.replace("PROCOPT=A", "PROCOPT=AL") + GEN, "load mode with another option"),
        (PCB.replace("PROCOPT=A", "PROCOPT=L") + PCB.replace("P1", "P2") + GEN, "a load-mode PCB on X beside another PCB"),
        (PCB.replace("PARENT=0", "PARENT=0,PROCOPT=G") + GEN, "segment-level PROCOPT"),
        (PCB.replace("DBDNAME=X", "DBDNAME=Y") + GEN, "not one of the case's DBDs"),
    ],
)  # fmt: skip
def test_a_psb_the_model_does_not_model_is_refused_by_name(text, why):
    db = ei.dbd(DBD_HEAD + SEGM + KEY + "         SEGM    NAME=C,PARENT=R,BYTES=4\n" + KEY, "X.dbd")
    with pytest.raises(ei.Unsupported, match=re.escape(why)):
        ei.psb(text, "P.psb", {"X": db, "G": ei.dbd(GSAM_DBD, "G.dbd")})


def test_a_gsam_database_and_its_load_mode_pcb_become_a_gsam_line_and_a_record_comparison():
    """#5233: a GSAM DBD is its RECORD length; its LS PCB a `GSAM` line (no DBD / seed lines); its .out is records."""
    g = ei.dbd(GSAM_DBD, "G.dbd")
    assert g == {"name": "G", "gsam": 100, "segments": []}
    x = ei.dbd(DBD_HEAD + SEGM + KEY, "X.dbd")
    pcbs = ei.psb("G        PCB     TYPE=GSAM,DBDNAME=G,PROCOPT=LS\n" + PCB + GEN, "P.psb", {"X": x, "G": g})
    assert [(p["dbd"], p.get("gsam")) for p in pcbs] == [("G", 100), ("X", None)]
    dbd_cfg, psb_cfg = ei.config({"X": x, "G": g}, pcbs)
    assert "G" not in [ln.split()[1] for ln in dbd_cfg.splitlines() if ln.startswith("DBD ")]
    assert psb_cfg.splitlines() == ["GSAM G LS 100", "PCB X A 2"]
    case = {"ims": {"dbd": [], "psb": ""}}
    keep = ei.dbd_definitions
    try:
        ei.dbd_definitions = lambda c, corpus: {"G": g}
        a, b = bytes([65]) * 100, bytes([66]) * 100
        assert ei.diff_db(case, ROOT, "G", a + b, a + b) == {"records": 2, "equal": 2, "filler_differs": 0, "diffs": []}
        d = ei.diff_db(case, ROOT, "G", a + b, a)
        assert d["equal"] == 1 and d["diffs"] == [{"segment": 2, "cobol": b.hex(), "java": None}]
        assert ei.diff_db(case, ROOT, "G", a, b)["diffs"] == [{"segment": 1, "cobol": a.hex(), "java": b.hex()}]
        with pytest.raises(ei.Unsupported, match="whole number"):
            ei.diff_db(case, ROOT, "G", a[:5], a)
    finally:
        ei.dbd_definitions = keep


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


def test_ceetdli_is_the_same_detdli_call_as_cbltdli_at_the_entry_and_a_hole_in_a_bmp(tmp_path):
    """#5233: LE's CEETDLI takes CBLTDLI's USING list; in a BMP (entered USING its I/O PCB) it stays a hole by name."""
    r = _translate(
        tmp_path, _program(["    CALL 'CEETDLI' USING FN PCB1 IOA", "    CALL 'CEETDLI' USING FN PCB2 IOA SSA SSA1(2)"])
    )
    assert not r.stats["holes"], r.stats["holes"]
    assert len(re.findall(r"DetDli\.call\(", r.java)) == 2 and re.search(r"DetDli\.enter\(\w+, \w+\);", r.java)
    r = _translate(tmp_path, _program(["    CALL 'CEETDLI' USING FN PCB2 IOA"], entry=None, using=" USING PCB1 PCB2"))
    assert any("CEETDLI" in h for h in r.stats["holes"]), r.stats["holes"]


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
        (["    CALL 'CEETDLI' USING FN IOA IOA"], "    ENTRY 'DLITCBL' USING PCB1 PCB2.", "not one IMS passed"),
        (["    CALL 'CEETDLI' USING FN PCB1"], "    ENTRY 'DLITCBL' USING PCB1 PCB2.", "up to 15 SSAs expected"),
        (["    CALL 'CEETDLI' USING FN PCB1 IOA"], None, "a program IMS does not enter at ENTRY"),
    ],
)  # fmt: skip
def test_what_the_translator_does_not_model_is_a_hole_by_name(tmp_path, proc, entry, why):
    r = _translate(tmp_path, _program(proc, entry=entry))
    assert len(r.stats["holes"]) == 1 and why in r.stats["holes"][0], r.stats["holes"]


# ---- the level fixture on both runtimes (the first-time number: PR body) ----------------------------------------------
def _cobol_side(
    work: Path, seed: bytes = SEED, prog: str = "DLILVL", edit=None, psb: str | None = None
) -> tuple[str, bytes]:
    pcbs = _stage(work / "dli", seed, psb)
    (work / "dliout").mkdir()
    src = work / "src"
    src.mkdir()
    text = (FIXTURE / f"{prog}.cbl").read_text()
    (src / f"{prog}.cbl").write_text(edit(text) if edit else text)
    shutil.copy(ei.STUB, src / "ggdli.c")
    (src / "EQDRIVER.cbl").write_text("\n".join(" " * 7 + ln for ln in ei.cobol_driver("DLITCBL", pcbs)) + "\n")
    script = (f"cobc -x -std=ibm -fsign=EBCDIC -o prog src/EQDRIVER.cbl src/{prog}.cbl src/ggdli.c && "
              "GGDLI_DIR=/w/dli GGDLI_OUT=/w/dliout ./prog")  # fmt: skip
    run = subprocess.run(["docker", "run", "--rm", "-v", f"{work}:/w", "-w", "/w", IMAGE, "sh", "-c", script],  # noqa: S607
                         capture_output=True, text=True, check=False)  # fmt: skip
    assert run.returncode == 0, run.stdout + run.stderr
    return run.stdout, (work / "dliout" / "LVLDBD.out").read_bytes()


def _java_side(
    work: Path, seed: bytes = SEED, prog: str = "DLILVL", edit=None, psb: str | None = None
) -> tuple[str, bytes]:
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(ROOT / "tests" / "cobol_mainframe"))
    import test_det_programs as tdp
    from gitgalaxy.tools.cobol_to_java.det import program as P

    _stage(work / "dli", seed, psb)
    (work / "dliout").mkdir()
    project = work / "project"
    tdp._batch_package(project / "src/main/java")
    cbl = work / f"{prog}.cbl"
    cbl.write_text(edit((FIXTURE / f"{prog}.cbl").read_text()) if edit else (FIXTURE / f"{prog}.cbl").read_text())
    r = P.translate(cbl, [], f"public class {prog.capitalize()}Service {{\n}}\n", PKG, None, project)
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


# #5233: boolean SSAs, written from IBM's documentation (AND binds tighter than OR; * and & are AND, + and | are OR)
BOOL_EXPECTED = [
    "Q1 [  ] E001ALICE", "Q1 [  ] E003CAROL",  # a GU then a GN: ALICE | CAROL
    "Q2 [  ] E003CAROL",  # E003 + (E001 * BOB): AND first, so E003 alone matches (OR first would find nothing)
    "Q3 [  ] E002BOB",  # SAL > 1000 & SAL < 3000 on packed salaries
    "Q4 [  ] E003CAROL",  # (BOB & SAL > 5000) + E003
    "Q5 [AJ]",  # a character after a statement that is neither ) nor a boolean operator
    "Q6 [AK]",  # the second statement names a field the segment lacks
    "Q7 [GE]",  # E001 & E002: no segment satisfies both
]  # fmt: skip


@E2E
def test_boolean_ssas_answer_the_same_on_both_runtimes(tmp_path):
    cobol_out, cobol_db = _cobol_side(tmp_path / "cobol", prog="DLIBOOL")
    java_out, java_db = _java_side(tmp_path / "java", prog="DLIBOOL")
    assert _lines(cobol_out) == BOOL_EXPECTED
    assert _lines(java_out) == BOOL_EXPECTED
    assert cobol_db == java_db


@E2E
@pytest.mark.parametrize(
    "edit, why",
    [
        (lambda s: s.replace("VALUE '|'", "VALUE '#'"), "the independent AND operator (#)"),
        (lambda s: s.replace("COMP-3 VALUE 1000", "COMP-3 VALUE -1000"), "P-field qualification on operands"),
    ],
)  # fmt: skip
def test_what_a_boolean_ssa_still_leaves_out_is_refused_by_both_runtimes(tmp_path, edit, why):
    with pytest.raises(AssertionError, match=re.escape(why)):
        _cobol_side(tmp_path / "cobol", prog="DLIBOOL", edit=edit)
    with pytest.raises(subprocess.CalledProcessError) as e:
        _java_side(tmp_path / "java", prog="DLIBOOL", edit=edit)
    assert why in (e.value.stderr or b"").decode("utf-8")


# #5233: command codes F, L and -, written from IBM's documentation (L takes the last twin of the type under its parent;
# F is the default start of a GU; both are ignored on an ISRT into a unique sequence field)
CMD_EXPECTED = [
    "Q01 [  ] D300HR",  # GU DEPT*L: the last root
    "Q02 [GB]",  # the GN after it: position is on the last root, which has no successor
    "Q03 [  ] D100SALES", "Q04 [  ] D100SALES",  # DEPT*F and DEPT*-: the first root, as without a code
    "Q05 [  ] E002BOB",  # DEPT, EMP*L: the last EMP under the first DEPT
    "Q06 [  ] E003CAROL",  # DEPT*-(DEPTNO = D200), EMP*L: a null code before the qualification
    "Q07 [  ] E002BOB",  # EMP*FL: L decides
    "Q08 [  ] S2JAVA",  # DEPT, EMP, SKILL*L: the last SKILL under the first EMP
    "Q09 [  ] E004DAVE",  # ISRT EMP*F under D200: inserted in key order (F and L change nothing with a unique key)
    "Q10 [  ] E004DAVE",  # so the last EMP under D200 is now E004
    # P on a GU: parentage at the DEPT, so the GNPs walk everything under D100 (EMP E001, its skills, E002, the project)
    "Q11 [  ] E001ALICE", "Q12 [  ] S1COBOL", "Q13 [  ] S2JAVA",
    "Q14 [GA] E002BOB", "Q15 [GK] P1ALPHA", "Q16 [GE]",  # GA: up a level; GK: same level, another type; GE: D100 is done
    # P on the lowest SSA is the default: parentage at the EMP, so the GNPs stop after E001's two skills
    "Q17 [  ] E001ALICE", "Q18 [  ] S1COBOL", "Q19 [  ] S2JAVA", "Q20 [GE]",
    # P with a qualification: D200's dependents, including the E004 inserted by Q09
    "Q21 [  ] E003CAROL", "Q22 [  ] S1DB2", "Q23 [GA] E004DAVE", "Q24 [GE]",
    # C on a GU: the concatenated key names the segment (a dependent, a deeper one), parentage is the segment found
    "Q25 [  ] E002BOB", "Q26 [  ] S2JAVA", "Q27 [GE]",  # S2 is the last skill of E001, which has no dependents
    "Q28 [GE]", "Q29 [  ] E003CAROL",  # no such EMP under D100; an EMP under the second DEPT
    # D, a path call: DEPT, EMP and SKILL come back one after another (the first 4, 4 and 2 bytes of each); D on the last SSA adds nothing
    "Q30 [  ] D100/E001/S1",
    "Q31 [  ] E001/S2JA/",  # a GN of EMP*D, SKILL: the next skill, with its EMP in front
    "Q32 [  ] D100/E001/", "Q33 [  ] D100/    /",  # DEPT*D, EMP; DEPT*D alone
    "Q34 [  ] D200/E003/S1",  # a qualified DEPT with D
    # DEPT*DP, EMP (parentage the DEPT), then GNPs of EMP*D, SKILL: each skill under D100 with its EMP, then GE
    "Q35 [  ] D100/E001/", "Q36 [  ] E001/S1CO/", "Q37 [  ] E001/S2JA/", "Q38 [GE]     /    /",  # nothing found: the area is untouched (blank)
    "Q39 [  ] D100/E001/",  # GHU
    # Q (enqueue) changes nothing with one program: on an unqualified and a qualified SSA, a GN, a GNP that finds nothing,
    # a GHU, and beside L
    "Q40 [  ] D100SALES", "Q41 [  ] E003CAROL", "Q42 [  ] E004DAVE", "Q43 [GE]", "Q44 [  ] E003CAROL", "Q45 [  ] E002BOB",
    # U and V make the current position a qualification (U at its level, V at it and above): position E002 under D100, then
    # DEPT*U, EMP | DEPT*U, EMP(E002) | DEPT*V, EMP*V | DEPT, EMP*U | a GN DEPT*U, PROJ | DEPT*V | GNP EMP, SKILL | GNP
    # EMP*V, SKILL (the next skill of the same EMP) | DEPT*U, EMP(E003): E003 is under D200, not the position's D100
    "Q46 [  ] E001ALICE", "Q47 [  ] E002BOB", "Q48 [  ] E002BOB", "Q49 [  ] E002BOB", "Q50 [  ] P1ALPHA", "Q51 [  ] D100SALES",
    "Q52 [  ] E001ALICE", "Q53 [  ] S1COBOL", "Q54 [  ] S2JAVA", "Q55 [GE]",
    # N (no replace) beside D on a GHU, then REPL of the path: DEPT*DN, EMP: only the EMP is replaced (the DEPT name stays SALES)
    "Q56 [  ] D100/E001/", "Q57 [  ] D100/E001/", "Q58 [  ] E001XENIA", "Q59 [  ] D100SALES",
    # DEPT*D, EMP*DN: the DEPT is replaced and the EMP is not
    "Q60 [  ] D100/E001/", "Q61 [  ] D100/E001/", "Q62 [  ] D100ALPHA", "Q63 [  ] E001XENIA",
    # an N segment's sequence field is not compared (D999 in the DEPT's slice), the EMP is replaced
    "Q64 [  ] D100/E001/", "Q65 [  ] D999/E001/", "Q66 [  ] D100ALPHA", "Q67 [  ] E001NEWNM",
    # a changed sequence field in a replaced segment is DA, and nothing is replaced
    "Q68 [  ] D100/E001/", "Q69 [DA] D100/E999/", "Q70 [  ] E001NEWNM",
    # D on an ISRT before the last SSA, the path insert: DEPT*D, EMP inserts a new root and its child; the GU reads the child back
    "Q71 [  ] EMP", "Q72 [  ] E010ZED",
    # an existing D-coded DEPT is kept (its slice is not compared: its name, ALPHA since Q62, stays), the EMP is inserted under it; the same call again is II
    "Q73 [  ] EMP", "Q74 [  ] D100ALPHA", "Q75 [  ] E011ABEL", "Q76 [II] DEPT",
    # three levels, DEPT*D, EMP*D, SKILL; then a qualified DEPT without D (found by its SSA), EMP*D, SKILL; a qualified DEPT that is missing: GE
    "Q77 [  ] SKILL", "Q78 [  ] S9TEST", "Q79 [  ] SKILL", "Q80 [  ] E030CY", "Q81 [  ] S8X", "Q82 [GE]",
]  # fmt: skip


@E2E
def test_command_codes_answer_the_same_on_both_runtimes(tmp_path):
    cobol_out, cobol_db = _cobol_side(tmp_path / "cobol", prog="DLICMD")
    java_out, java_db = _java_side(tmp_path / "java", prog="DLICMD")
    assert _lines(cobol_out) == CMD_EXPECTED
    assert _lines(java_out) == CMD_EXPECTED
    assert cobol_db == java_db
    keys = [
        (n, d[:4].decode("latin-1").strip())
        for n, d in ei.split(cobol_db, {"DEPT": 20, "EMP": 20, "SKILL": 8, "PROJ": 12})
    ]
    assert ("EMP", "E004") in keys and keys.index(("EMP", "E004")) == keys.index(("EMP", "E003")) + 2


def _swap(old: str, new: str):
    def edit(s: str) -> str:
        assert old in s
        return s.replace(old, new, 1)

    return edit


def _swaps(*pairs: tuple[str, str]):
    edits = [_swap(old, new) for old, new in pairs]

    def edit(s: str) -> str:
        for one in edits:
            s = one(s)
        return s

    return edit


@E2E
@pytest.mark.parametrize(
    "edit, why",
    [
        (_swap("'DEPT    *L '", "'DEPT    *N '"), "the command code N"),
        (_swaps(("'DEPT    *L '", "'DEPT    *Q '"), ("F-GU PCB1 IOA C-DL", "F-ISRT PCB1 IOA C-DL")),
         "the command code Q on a ISRT"),  # Q is modelled on the gets only
        (_swap("'DEPT    *L '", "'DEPT    *U '"), "the command code U with no established position"),
        (_swap("'DEPT    *L '", "'DEPT    *V '"), "the command code V with no established position"),
        (_swaps(("'DEPT    *L '", "'DEPT    *U '"), ("F-GU PCB1 IOA C-DL", "F-ISRT PCB1 IOA C-DL")),
         "the command code U on a ISRT"),  # U and V are modelled on the gets only
        (_swaps(("'DEPT    *L '", "'DEPT    *V '"), ("F-GU PCB1 IOA C-DL", "F-ISRT PCB1 IOA C-DL")),
         "the command code V on a ISRT"),
        (_swaps(("'EMP     *CD'", "'EMP     *CU'"), ("CALL 'CBLTDLI' USING F-GU PCB1 IOA C-CE2",
                                                       "CALL 'CBLTDLI' USING F-GU PCB1 IOA C-CDE")),
         "the command code U beside C"),
        (_swap("'DEPT    *L '", "'DEPT    *3 '"), "the command code 3"),
        # #5233: the DEDB subset-pointer codes no burned program uses stay refused by name
        *[(_swap("'DEPT    *L '", f"'DEPT    *{c} '"), f"the command code {c}") for c in "MRSWZ19"],
        (_swap("PIC X(11) VALUE 'DEPT    *L '", "PIC X(12) VALUE 'DEPT    *-N '"),
         "the command code N other than with D on a get-hold call"),  # N later in the list, on a GU
        (_swap("F-GHU PCB1 IOP C-DDN S-EMP", "F-GU PCB1 IOP C-DDN S-EMP"), "the command code N other than with D on a get-hold call"),
        (_swap("'DEPT    *DN '", "'DEPT    *N  '"), "the command code N other than with D on a get-hold call"),  # N without D (a hold get)
        (_swap("CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DL", "CALL 'CBLTDLI' USING F-ISRT PCB1 IOA C-DDN"),
         "the command code N other than with D on a get-hold call (ISRT)"),  # no replace is a get-hold's, not a path insert's
        (_swap("F-ISRT PCB1 IOP C-DD S-EMP", "F-ISRT PCB1 IOP C-DDN S-EMP"),
         "the command code N other than with D on a get-hold call (ISRT)"),  # N beside D on a path insert
        (_swap("PIC X(4) VALUE 'REPL'", "PIC X(4) VALUE 'DLET'"), "a DLET after a path call"),
        (_swap("CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DL", "CALL 'CBLTDLI' USING F-GN PCB1 IOA C-DF"),
         "the command code F on a GN"),
        (_swap("CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DL", "CALL 'CBLTDLI' USING F-GN PCB1 IOA C-DL"),
         "the command code L other than"),
        (_swap("CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DL", "CALL 'CBLTDLI' USING F-GN PCB1 IOA C-DP"),
         "the command code P on a GN"),
        (_swap("F-ISRT PCB1 IOA C-DQ C-EF", "F-ISRT PCB1 IOA C-DQ C-EP"), "the command code P on a ISRT"),
        (_swap("IOA S-DEPT S-EMP C-SKL", "IOA C-DP C-EP C-SKL"), "the command code P on more than one SSA"),
        (_swap("CALL 'CBLTDLI' USING F-GU PCB1 IOA C-DL", "CALL 'CBLTDLI' USING F-GN PCB1 IOA C-CE2"),
         "the command code C other than"),
        (_swap("IOA S-DEPT S-EMP C-SKL", "IOA C-CE2 C-CS2"), "the command code C other than"),
        (_swap("CALL 'CBLTDLI' USING F-GU PCB1 IOA C-CE2", "CALL 'CBLTDLI' USING F-GU PCB1 IOA C-CDE"),
         "the command code D beside C"),
        (_swap("IOA S-DEPT C-EL", "IOA C-DL C-EL"), "the command code L other than"),  # L on a path SSA
        (_swap("IOA C-DQ C-EL", "IOA C-DQL C-EL"), "the command code L other than"),  # L on a qualified SSA
    ],
)  # fmt: skip
def test_the_command_codes_not_modelled_are_refused_by_name_on_both_runtimes(tmp_path, edit, why):
    def with_qualified_l(s: str) -> str:
        s = edit(s)
        return s.replace("       LINKAGE SECTION.", QL + "       LINKAGE SECTION.", 1)

    with pytest.raises(AssertionError, match=re.escape(why)):
        _cobol_side(tmp_path / "cobol", prog="DLICMD", edit=with_qualified_l)
    with pytest.raises(subprocess.CalledProcessError) as e:
        _java_side(tmp_path / "java", prog="DLICMD", edit=with_qualified_l)
    assert why in (e.value.stderr or b"").decode("utf-8")


# a DEPT SSA that carries L and a qualification (the refusal edit above points a call at it)
QL = """       01  C-DQL.
           05 FILLER             PIC X(11) VALUE 'DEPT    *L('.
           05 FILLER             PIC X(8) VALUE 'DEPTNO'.
           05 FILLER             PIC X(2) VALUE ' ='.
           05 FILLER             PIC X(4) VALUE 'D200'.
           05 FILLER             PIC X VALUE ')'.
"""


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


def test_chkp_outside_a_bmp_is_a_hole_by_name_and_cbltdli_in_a_bmp_is_not(tmp_path):
    r = _translate_cics(tmp_path, _cics_program(_wrap("EXEC DLI CHKP ID(IOA) END-EXEC")))
    assert any("CHKP" in h for h in r.stats["holes"]), r.stats["holes"]
    r = _translate(tmp_path, _bmp(["    CALL 'CBLTDLI' USING FN DB-PCB SEG-A"]))
    assert not any("CBLTDLI" in h for h in r.stats["holes"]), r.stats["holes"]  # #5233: a BMP's CBLTDLI is modelled
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


GSAM_MAIN = """
import {pkg}.cobolrt.Field;
import {pkg}.cobolrt.Storage;
import {pkg}.cobolrt.dli.DetDli;

public class Main {{
    static Field area(String s, int n) {{
        Storage st = new Storage(n);
        byte[] b = s.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);
        System.arraycopy(b, 0, st.bytes, 0, Math.min(n, b.length));
        return Field.group(st, 0, n);
    }}

    static String call(Field mask, String fn, Field io, Field... ssas) {{
        try {{
            DetDli.call(area(fn, 4), mask, io, ssas);
            return "[" + new String(mask.storage().bytes, mask.offset() + 10, 2) + "]";
        }} catch (UnsupportedOperationException e) {{
            return e.getMessage();
        }}
    }}

    public static void main(String[] a) {{
        Field m1 = area("", 36);
        Field m2 = area("", 36);
        try {{
            DetDli.enter(a[0].equals("dup") ? new Field[] {{ m1, m2 }} : new Field[] {{ m1 }});
        }} catch (UnsupportedOperationException e) {{
            System.out.println(e.getMessage());
            return;
        }}
        System.out.println("mask [" + new String(m1.storage().bytes, 0, 16) + "]");
        System.out.println(call(m1, "ISRT", area("AAAAAAAA", 8)));
        System.out.println(call(m1, "ISRT", area("BBBBBBBBXXXX", 12)));
        for (String fn : new String[] {{ "GU  ", "GN  ", "GNP ", "REPL", "DLET" }}) {{
            System.out.println(fn + " " + call(m1, fn, area("CCCCCCCC", 8)));
        }}
        System.out.println(call(m1, "ISRT", area("DDDDDDDD", 8), area("SEG     ", 8)));
        System.out.println(call(m1, "ISRT", area("EEEE", 4)));
        DetDli.leave();
    }}
}}
"""


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_detdli_a_gsam_pcb_in_load_mode_appends_records_and_refuses_what_it_does_not_model(tmp_path):
    """#5233, RT-DLI-GSAM (DetDli.gsamCall): ISRT appends one record of the DBD's length (the I/O area's first 8 bytes), any
    other function is AM, the mask's segment level is blank; an SSA, an I/O area shorter than the record and a second
    GSAM PCB on the database are refused by name."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    for rel, text in P.runtime_files("t", batch=False).items():
        if not rel.startswith(("cobolrt/cics/", "cobolrt/sql/")):
            (src / "t" / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / "t" / rel).write_text(text)
    (src / "Main.java").write_text(GSAM_MAIN.format(pkg="t"))
    jdk = _jdk()
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                    *map(str, src.rglob("*.java"))], check=True)  # fmt: skip

    def run(psb: str, arg: str) -> tuple[list[str], Path]:
        work = tmp_path / arg
        (work / "dli").mkdir(parents=True)
        (work / "out").mkdir()
        (work / "dli" / "dbd.cfg").write_text("", encoding="ascii")
        (work / "dli" / "psb.cfg").write_text(psb, encoding="ascii")
        out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8",  # noqa: S603
                              f"-Dgitgalaxy.dli.dir={work / 'dli'}", f"-Dgitgalaxy.dli.out={work / 'out'}",
                              "-cp", str(tmp_path / "classes"), "Main", arg], capture_output=True,
                             check=True).stdout.decode("utf-8").splitlines()  # fmt: skip
        return out, work / "out" / "G.out"

    lines, records = run("GSAM G LS 8\n", "one")
    assert lines[0] == "mask [G           LS  ]"  # DBD name, blank level and status, PROCOPT
    assert lines[1:] == [
        "[  ]",
        "[  ]",
        "GU   [AM]",
        "GN   [AM]",
        "GNP  [AM]",
        "REPL [AM]",
        "DLET [AM]",
        "CBLTDLI: a GSAM ISRT with an SSA is not modelled",
        "CBLTDLI: a GSAM ISRT whose I/O area is shorter than the DBD's record is not modelled",
    ]
    assert records.read_bytes() == b"AAAAAAAABBBBBBBB"
    dup, _ = run("GSAM G LS 8\nGSAM G LS 8\n", "dup")
    assert dup == ["CBLTDLI: two GSAM PCBs on one database is not modelled"]


@E2E
def test_a_path_isrt_with_an_area_shorter_than_its_segments_is_refused_by_the_java_runtime(tmp_path):
    # the C twin cannot see the area's size (register I5), so only the Java side refuses
    short = _swap("F-ISRT PCB1 IOP C-DD S-EMP", "F-ISRT PCB1 IOA C-DD S-EMP")
    with pytest.raises(subprocess.CalledProcessError) as e:
        _java_side(tmp_path / "java", prog="DLICMD", edit=short)
    assert "a path ISRT whose I/O area is shorter" in (e.value.stderr or b"").decode("utf-8")


# ---- #5233: load mode on a DB PCB (PROCOPT L / LS) -----------------------------------------------------------------
LOAD_PSB = ("LOADPCB  PCB     TYPE=DB,DBDNAME=LVLDBD,PROCOPT=L,KEYLEN=10\n"
            + "".join(f"         SENSEG  NAME={n},PARENT={par}\n"
                      for n, par in [("DEPT", 0), ("EMP", "DEPT"), ("SKILL", "EMP"), ("PROJ", "DEPT")])
            + "         PSBGEN  LANG=COBOL,PSBNAME=LOADPSB,CMPAT=NO\n         END\n")  # fmt: skip

# (call, segment, I/O area, IBM status): ISRT in hierarchic and key order loads; a duplicate key is LB, a lower key than
# the last twin LC, a segment type earlier than one already under the parent LE, no parent of its type loaded LD;
# every other function is AM (the call is not compatible with the load PROCOPT)
LOAD_STEPS = [
    ("ISRT", "DEPT", "D100SALES", "  "), ("ISRT", "EMP", "E001ALICE", "  "), ("ISRT", "SKILL", "S1COBOL", "  "),
    ("ISRT", "SKILL", "S2JAVA", "  "), ("ISRT", "SKILL", "S2JAVA", "LB"), ("ISRT", "SKILL", "S1COBOL", "LC"),
    ("ISRT", "EMP", "E002BOB", "  "), ("ISRT", "EMP", "E001ALICE", "LC"), ("ISRT", "PROJ", "P1ALPHA", "  "),
    ("ISRT", "EMP", "E003CAROL", "LE"), ("ISRT", "SKILL", "S3DB2", "LD"), ("ISRT", "DEPT", "D050OPS", "LC"),
    ("ISRT", "DEPT", "D100SALES", "LB"), ("ISRT", "DEPT", "D200OPS", "  "), ("ISRT", "SKILL", "S1COBOL", "LD"),
    ("GU", "DEPT", "", "AM"), ("GN", None, "", "AM"), ("GHU", "DEPT", "", "AM"), ("REPL", None, "", "AM"),
    ("DLET", None, "", "AM"),
]  # fmt: skip


def _load_program() -> str:
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. DLILOAD.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
             "01  W-Q PIC 99 VALUE 0.", "01  IOA PIC X(60)."]  # fmt: skip
    for fn in sorted({c for c, *_ in LOAD_STEPS}):
        lines.append(f"01  F-{fn} PIC X(4) VALUE '{fn:<4}'.")
    for seg in ("DEPT", "EMP", "SKILL", "PROJ"):
        lines.append(f"01  S-{seg} PIC X(9) VALUE '{seg:<9}'.")
    lines += ["LINKAGE SECTION.", "01  PCB1.", "    05 P1-DBD PIC X(8).", "    05 P1-LEVEL PIC X(2).",
              "    05 P1-STATUS PIC X(2).", "    05 FILLER PIC X(34).", "PROCEDURE DIVISION.", "MAIN-PARA.",
              "    ENTRY 'DLITCBL' USING PCB1."]  # fmt: skip
    for i, (fn, seg, area, _) in enumerate(LOAD_STEPS, 1):
        lines += [f"    MOVE {i} TO W-Q", f"    MOVE '{area}' TO IOA"]
        ssa = f" S-{seg}" if seg and fn != "REPL" else ""
        lines += [f"    CALL 'CBLTDLI' USING F-{fn} PCB1 IOA{ssa}", "    DISPLAY 'Q' W-Q ' [' P1-STATUS ']'"]
    lines.append("    GOBACK.")
    return "\n".join(" " * 7 + ln for ln in lines) + "\n"


def test_a_load_mode_pcb_is_one_the_harness_models():
    pcbs = ei.psb(LOAD_PSB, "LOADPSB.psb", {"LVLDBD": ei.dbd((FIXTURE / "LVLDBD.dbd").read_text(), "LVLDBD.dbd")})
    assert [(p["dbd"], p["procopt"]) for p in pcbs] == [("LVLDBD", "L")]
    assert "PCB LVLDBD L 10" in ei.config({}, pcbs)[1]
    with pytest.raises(ei.Unsupported, match="load mode under CICS"):
        ei.psb(LOAD_PSB.replace("PROCOPT=L", "PROCOPT=LS"), "LOADPSB.psb", {"LVLDBD": ei.dbd(
            (FIXTURE / "LVLDBD.dbd").read_text(), "LVLDBD.dbd")}, cics=True)  # fmt: skip


@E2E
def test_load_mode_answers_lb_lc_ld_le_and_am_the_same_on_both_runtimes(tmp_path):
    expected = [f"Q{i:02d} [{st}]" for i, (*_, st) in enumerate(LOAD_STEPS, 1)]
    cobol_out, cobol_db = _cobol_side(
        tmp_path / "cobol", seed=b"", prog="DLILVL", edit=lambda _: _load_program(), psb=LOAD_PSB
    )
    java_out, java_db = _java_side(
        tmp_path / "java", seed=b"", prog="DLILVL", edit=lambda _: _load_program(), psb=LOAD_PSB
    )
    assert _lines(cobol_out) == expected
    assert _lines(java_out) == expected
    assert cobol_db == java_db
    keys = [(n, d[:4].decode("latin-1").strip()[: 2 if n in ("SKILL", "PROJ") else 4])
            for n, d in ei.split(cobol_db, {"DEPT": 20, "EMP": 20, "SKILL": 8, "PROJ": 12})]  # fmt: skip
    assert keys == [("DEPT", "D100"), ("EMP", "E001"), ("SKILL", "S1"), ("SKILL", "S2"), ("EMP", "E002"),
                    ("PROJ", "P1"), ("DEPT", "D200")]  # fmt: skip


@E2E
def test_load_mode_into_a_database_that_holds_segments_is_refused_by_both_runtimes(tmp_path):
    with pytest.raises(AssertionError, match="load mode into a database that already holds segments"):
        _cobol_side(tmp_path / "cobol", prog="DLILVL", edit=lambda _: _load_program(), psb=LOAD_PSB)
    with pytest.raises(subprocess.CalledProcessError):
        _java_side(tmp_path / "java", prog="DLILVL", edit=lambda _: _load_program(), psb=LOAD_PSB)


def _ceetdli(text: str) -> str:
    return text.replace("'CBLTDLI'", "'CEETDLI'")


@E2E
@pytest.mark.parametrize("prog", ["DLILVL", "DLICMD", "DLIBOOL"])
def test_ceetdli_answers_what_cbltdli_answers_on_both_runtimes(tmp_path, prog):
    """#5233: each fixture (every modelled call, status, command code and boolean SSA) with CBLTDLI renamed CEETDLI:
    both runtimes print what the unrenamed fixture prints and leave the same database."""
    cobol_out, cobol_db = _cobol_side(tmp_path / "cobol", prog=prog, edit=_ceetdli)
    java_out, java_db = _java_side(tmp_path / "java", prog=prog, edit=_ceetdli)
    base_out, base_db = _cobol_side(tmp_path / "base", prog=prog)
    assert _lines(cobol_out) == _lines(java_out) == _lines(base_out)
    assert cobol_db == java_db == base_db
