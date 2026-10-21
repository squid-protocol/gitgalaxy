"""#5857 (register I5): a BMP's EXEC DLI, the oracle side. IMS enters a BMP `PROCEDURE DIVISION USING io-pcb db-pcb ...`
(PSB CMPAT=YES, the I/O PCB first); equivalence_ims.py stages it, rewrite_bmp lowers each EXEC DLI to a CALL of
ggdli.c (GGDLIX, GGDLICHKP), and GGDLIBMP binds the PCBs. The unit tests need nothing; the GnuCOBOL run needs
EQUIVALENCE_E2E=1, Docker and the oracle image."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_ims as ei  # noqa: E402

FIXTURE = ROOT / "tests" / "equivalence" / "ims" / "fixture"
IMAGE = "gitgalaxy-gnucobol:3"

E2E = pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                         reason="needs EQUIVALENCE_E2E=1 and Docker")  # fmt: skip

HEAD = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BMPCHK.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  IOA                    PIC X(20).
       01  CHK-ID                 PIC X(8) VALUE 'CHKP0001'.
       01  PCB-NUM                PIC S9(4) COMP VALUE +2.
       LINKAGE SECTION.
       01  IO-PCB                 PIC X.
       01  DB-PCB-1               PIC X.
       01  DB-PCB-2               PIC X.
       PROCEDURE DIVISION USING IO-PCB DB-PCB-1 DB-PCB-2.
"""
TAIL = "           GOBACK.\n"
SHOW = "           DISPLAY '{0} [' DIBSTAT '] ' IOA(1:4).\n"
STEPS = [  # (statement, label): D100 is deleted, then the CHKP releases the position
    ("EXEC DLI GN USING PCB(PCB-NUM) SEGMENT(DEPT) INTO(IOA) END-EXEC", "GN1"),
    ("EXEC DLI DLET USING PCB(PCB-NUM) SEGMENT(DEPT) FROM(IOA) END-EXEC", "DLET"),
    ("EXEC DLI GN USING PCB(PCB-NUM) SEGMENT(DEPT) INTO(IOA) END-EXEC", "GN2"),
    ("EXEC DLI GNP USING PCB(PCB-NUM) SEGMENT(EMP) INTO(IOA) END-EXEC", "GNP"),
    ("EXEC DLI CHKP ID(CHK-ID) END-EXEC", "CHKP"),
    ("EXEC DLI GN USING PCB(PCB-NUM) SEGMENT(DEPT) INTO(IOA) END-EXEC", "GN3"),
]


def _program(steps=STEPS, head: str = HEAD) -> str:
    body = "".join("           " + stmt.replace(" END-EXEC", "\n               END-EXEC") + "\n" + SHOW.format(label)
                   for stmt, label in steps)  # fmt: skip
    return head + body + TAIL


def _psb(cmpat: str = "YES") -> str:
    return (FIXTURE / "LVLPSB.psb").read_text(encoding="latin-1").replace("CMPAT=NO", f"CMPAT={cmpat}")


def _case(psb_name: str = "bmp.psb") -> dict:
    def seg(name: str, data: bytes) -> dict:
        return {"segment": name, "hex": data.ljust({"DEPT": 20, "EMP": 20}[name], b" ").hex()}

    emp = b"E003CAROL"
    return {"program": "BMPCHK", "ims": {"dbd": ["LVLDBD.dbd"], "psb": psb_name, "compare": ["LVLDBD"],
            "seed": {"LVLDBD": {"segments": [seg("DEPT", b"D100SALES"), seg("DEPT", b"D200OPS"),
                                              seg("EMP", emp), seg("DEPT", b"D300HR")]}}}}  # fmt: skip


def _corpus(tmp_path: Path, cmpat: str = "YES") -> Path:
    shutil.copy(FIXTURE / "LVLDBD.dbd", tmp_path / "LVLDBD.dbd")
    (tmp_path / "bmp.psb").write_text(_psb(cmpat), encoding="latin-1")
    return tmp_path


# ---- the harness reads a BMP -------------------------------------------------------------------------------------
def test_a_bmp_is_told_from_an_entry_dlitcbl_program():
    assert ei.bmp_using(_program()) == ["IO-PCB", "DB-PCB-1", "DB-PCB-2"]
    entry = _program().replace("PROCEDURE DIVISION USING IO-PCB DB-PCB-1 DB-PCB-2.",
                               "PROCEDURE DIVISION.\n           ENTRY 'DLITCBL' USING DB-PCB-1 DB-PCB-2.")  # fmt: skip
    assert ei.bmp_using(entry) is None and ei.entry_using(entry) == ["DB-PCB-1", "DB-PCB-2"]
    assert ei.bmp_using(_program().replace("EXEC DLI", "EXEC SQL")) is None  # no EXEC DLI: not a BMP


def test_a_bmp_stages_with_cmpat_yes_and_the_db_pcbs_only(tmp_path):
    pcbs = ei.stage(_case(), _corpus(tmp_path), _program(), tmp_path / "dli")
    assert [p["procopt"] for p in pcbs] == ["A", "G"]
    assert (tmp_path / "dli" / "psb.cfg").read_text().splitlines() == [
        "PCB LVLDBD A 10",
        "PCB LVLDBD G 10",
    ]  # no I/O PCB
    drv = ei.cobol_driver("BMPCHK", pcbs, io=True)
    assert "    CALL 'GGDLIBMP' USING PCB-IO PCB-1 PCB-2" in drv and "    CALL 'BMPCHK' USING PCB-IO PCB-1 PCB-2" in drv
    assert not any("GGDLINIT" in ln for ln in drv)
    assert "    CALL 'GGDLINIT' USING PCB-1 PCB-2" in ei.cobol_driver("DLITCBL", pcbs)


@pytest.mark.parametrize(
    "cmpat, source, why",
    [
        ("NO", _program(), "needs CMPAT=YES"),
        ("YES", _program().replace("DB-PCB-1 DB-PCB-2.", "DB-PCB-1."), "names 1 DB PCBs, the PSB has 2"),
        ("YES", _program().replace("USING IO-PCB DB-PCB-1 DB-PCB-2", "USING IO-PCB"), "not a BMP entered USING"),
        ("YES", _program().replace("PROCEDURE DIVISION USING IO-PCB DB-PCB-1 DB-PCB-2.",
                                   "PROCEDURE DIVISION.\n           ENTRY 'DLITCBL' USING DB-PCB-1 DB-PCB-2."),
         "only a BMP entered USING its I/O PCB"),
    ],
)  # fmt: skip
def test_a_bmp_and_psb_that_do_not_match_are_refused_by_name(tmp_path, cmpat, source, why):
    with pytest.raises(ei.Unsupported, match=re.escape(why)):
        ei.stage(_case(), _corpus(tmp_path, cmpat), source, tmp_path / "dli")


# ---- the EXEC DLI lowering ---------------------------------------------------------------------------------------
def test_a_bmps_exec_dli_becomes_the_calls_of_the_oracles_entry_points():
    out = ei.rewrite_bmp(_program())
    assert "EXEC DLI" not in out and "END-EXEC" not in out
    for verb in ("GN  ", "GNP ", "DLET"):
        assert f"BY CONTENT '{verb}'" in out
    assert re.search(r"CALL 'GGDLICHKP' USING BY REFERENCE DIBSTAT\s+BY REFERENCE CHK-ID", out)
    assert "BY VALUE LENGTH OF CHK-ID" in out
    assert out.count("01  DIB.") == 1 and out.index("01  DIB.") < out.index("PROCEDURE DIVISION")
    assert max(len(ln) for ln in out.splitlines()) <= 72


@pytest.mark.parametrize(
    "stmt, why",
    [
        ("EXEC DLI CHKP END-EXEC", "only ID(data name)"),
        ("EXEC DLI CHKP ID(CHK-ID) SAVE END-EXEC", "only ID(data name)"),
        ("EXEC DLI CHKP ID('RMAD0001') END-EXEC", "only ID(data name)"),
        ("EXEC DLI XRST END-EXEC", "XRST: not modelled"),
        ("EXEC DLI ROLB END-EXEC", "ROLB: not modelled"),
        ("EXEC DLI GN USING PCB(2) SEGMENT(DEPT)\n               INTO(IOA) FIELDLENGTH(4) END-EXEC", "FIELDLENGTH"),
        ("EXEC CICS SEND TEXT FROM(IOA) END-EXEC", "EXEC CICS in a batch program"),
    ],
)  # fmt: skip
def test_what_the_oracle_does_not_model_in_a_bmp_is_refused_by_name(stmt, why):
    with pytest.raises(ei.Unsupported, match=re.escape(why)):
        ei.rewrite_bmp(_program([(stmt, "X")]))


def test_ggdli_binds_a_bmp_and_models_chkp_as_the_det_runtime_does():
    c = (ROOT / "tests" / "equivalence" / "ims" / "ggdli.c").read_text(encoding="utf-8")
    for name in ("GGDLIBMP", "GGDLICHKP"):
        assert f"int {name}(" in c
    assert "the I/O PCB" in c and "outside a BMP" in c and "not 8 bytes" in c


# ---- GnuCOBOL runs a BMP against the model -----------------------------------------------------------------------
def _run(work: Path, steps) -> subprocess.CompletedProcess:
    (work / "corpus").mkdir()
    corpus = _corpus(work / "corpus")
    source = _program(steps)
    pcbs = ei.stage(_case(), corpus, source, work / "dli")
    (work / "dliout").mkdir()
    src = work / "src"
    src.mkdir()
    (src / "BMPCHK.cbl").write_text(ei.rewrite_bmp(source), encoding="ascii")
    (src / "EQDRIVER.cbl").write_text("\n".join(" " * 7 + ln for ln in ei.cobol_driver("BMPCHK", pcbs, io=True)) + "\n")
    shutil.copy(ei.STUB, src / "ggdli.c")
    script = ("cobc -x -std=ibm -fsign=EBCDIC -o prog src/EQDRIVER.cbl src/BMPCHK.cbl src/ggdli.c && "
              "GGDLI_DIR=/w/dli GGDLI_OUT=/w/dliout ./prog")  # fmt: skip
    return subprocess.run(["docker", "run", "--rm", "-v", f"{work}:/w", "-w", "/w", IMAGE, "sh", "-c", script],  # noqa: S607
                          capture_output=True, text=True, check=False)  # fmt: skip


@E2E
def test_a_bmp_runs_under_gnucobol_and_a_chkp_releases_the_position(tmp_path):
    """IBM: GN walks the roots, a DLET removes the held segment (D100 with its dependents), GNP stays under the parent,
    and after CHKP the next GN starts at the database's beginning (D200: D100 is gone) -- not at D300."""
    run = _run(tmp_path, STEPS)
    assert run.returncode == 0, run.stdout + run.stderr
    assert [ln.strip() for ln in run.stdout.splitlines()] == [
        "GN1 [  ] D100", "DLET [  ] D100", "GN2 [  ] D200", "GNP [  ] E003", "CHKP [  ] E003", "GN3 [  ] D200"]  # fmt: skip
    keys = [
        (n, d[:4].decode("latin-1").strip())
        for n, d in ei.split(
            (tmp_path / "dliout" / "LVLDBD.out").read_bytes(), {"DEPT": 20, "EMP": 20, "SKILL": 8, "PROJ": 12}
        )
    ]
    assert keys == [("DEPT", "D200"), ("EMP", "E003"), ("DEPT", "D300")]


@E2E
@pytest.mark.parametrize(
    "stmt, why",
    [
        ("EXEC DLI GN USING PCB(1) SEGMENT(DEPT) INTO(IOA) END-EXEC", "PCB(1), the I/O PCB is not modelled"),
        ("EXEC DLI GN USING PCB(4) SEGMENT(DEPT) INTO(IOA) END-EXEC", "a PCB number the scheduled PSB does not have"),
    ],
)  # fmt: skip
def test_a_bmp_pcb_the_psb_does_not_have_stops_the_run_by_name(tmp_path, stmt, why):
    run = _run(tmp_path, [(stmt, "X")])
    assert run.returncode == 98 and why in run.stderr + run.stdout, run.stdout + run.stderr
