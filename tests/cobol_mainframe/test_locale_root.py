"""#3823: locale-proof generated Java (Locale.ROOT)."""

import re
import shutil
import sys
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db

NIGHTLY = """\
//NIGHTLY  JOB (ACCT),'NIGHTLY RUN',CLASS=A,MSGCLASS=X
//RUN      EXEC PGM=SGNON,COND=(4,LT)
//TRANS    DD DSN=APP.TRANS.SORTED(+1),DISP=SHR
"""

BMS = (
    "\n".join(
        [
            "SGN00    DFHMSD TYPE=&SYSPARM,LANG=COBOL,MODE=INOUT,STORAGE=AUTO",
            "SGN0A    DFHMDI SIZE=(24,80),LINE=1,COLUMN=1",
            "         DFHMDF POS=(1,1),LENGTH=6,ATTRB=(ASKIP,NORM),INITIAL='Tran :',".ljust(71) + "X",
            "               COLOR=BLUE",
            "USERID   DFHMDF POS=(19,43),LENGTH=8,ATTRB=(FSET,IC,NORM,UNPROT)",
            "         DFHMSD TYPE=FINAL",
            "         END",
        ]
    )
    + "\n"
)

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SGNON.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PGM             PIC X(8).
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS RECEIVE MAP('SGN0A') MAPSET('SGN00') INTO(SGN0AI)
                END-EXEC.
           MOVE 'SUBPRG' TO WS-PGM.
           CALL WS-PGM.
           EXEC CICS RETURN END-EXEC.
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("locale_root")
    repo = base / "estate"
    for rel, text in {"jcl/NIGHTLY.jcl": NIGHTLY, "bms/SGN00.bms": BMS, "cbl/SGNON.cbl": PROGRAM}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


def _generate(scanned, tmp_path):
    repo, db = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")

    (tmp_path / "none.txt").write_text("", encoding="utf-8")
    argv = ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]

    with patch.object(sys, "argv", argv):
        java_controller.main()

    (java,) = tmp_path.glob("estate_gitgalaxy_java_spring_*")
    return java


def test_no_locale_unaware_string_operations(scanned, tmp_path):
    """Every String.format call names Locale.ROOT, and no case mapping uses the default locale: under
    ar/hi a %d prints other digits, under tr "i".toUpperCase() is "İ" (#3823)."""
    java = _generate(scanned, tmp_path)
    formats = 0
    for p in java.rglob("*.java"):
        code = p.read_text(encoding="utf-8")
        calls = re.findall(r"String\.format\(\s*([^,)]{0,40})", code)
        formats += len(calls)
        assert all(a.strip() in ("Locale.ROOT", "java.util.Locale.ROOT") for a in calls), (p.name, calls)
        assert not re.search(r"\.to(?:Upper|Lower)Case\(\)", code), p.name
    assert formats, "the estate should generate at least one String.format (the GDG generation name)"
