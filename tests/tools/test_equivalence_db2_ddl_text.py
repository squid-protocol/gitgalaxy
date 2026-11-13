"""#8121: `ddl_text` keeps only a job's in-stream SQL, whichever way the block ends (`/*` or the next `//` card) and
whatever the member's suffix (DB2CRE.jcl, and HCMobile_DB2.txt, a JCL job kept as plain text)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_db2 as db2

# Two SYSIN blocks: the first ends at the next `//` card (no `/*`), the second at `/*`.
JOB = """//CRTABS1  EXEC PGM=IKJEFT01
//SYSTSIN  DD *
 DSN SYSTEM(DB1S)
 RUN  PROGRAM(DSNTIAD) PLAN(DSNTIA10) -
      LIB('DB2.V10.DB1S.RUNLIB.LOAD')
//SYSIN    DD *
  SET CURRENT SQLID='DDS1491' ;
CREATE TABLE HCZMSA1.patient (
     patientId INTEGER NOT NULL)
   CCSID EBCDIC
   IN HCZMSA1.HCZMTS00;
CREATE UNIQUE INDEX HCZMSA1.iPatient ON HCZMSA1.patient (patientId) COPY YES ;
//*
//CRTABS2  EXEC PGM=IKJEFT01
//SYSTSIN  DD *
 DSN SYSTEM(DB1S)
 RUN  PROGRAM(DSNTIAD) PLAN(DSNTIA10) -
//SYSIN    DD *
CREATE TABLE HCZMSA1.medication (
     medicationId INTEGER NOT NULL)
   IN HCZMSA1.HCZMTS02;
/*
//
"""
# Plain SQL first, then the job: HCMobile_DB2.txt's shape.
MIXED = "-- licence header\nCREATE TABLE HCZMSA1.user (userName CHAR(10)) IN HCZMSA1.HCZMTS01;\n\n" + JOB


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="latin-1")
    return path


def _check_job(out: str) -> None:
    for leak in ("//", "DSN", "RUN", "PROGRAM", "DSNTIAD", "/*"):
        assert leak not in out, leak
    assert "CREATE TABLE HCZMSA1.patient" in out
    assert "CREATE TABLE HCZMSA1.medication" in out  # the block after a `//`-ended one is kept
    assert "SET CURRENT SQLID" not in out
    assert "IN HCZMSA1" not in out.replace("INDEX HCZMSA1", "")  # z/OS-only clauses stripped
    assert "COPY YES" not in out and "CCSID" not in out


def test_jcl_block_ended_by_a_slash_slash_card(tmp_path):
    _check_job(db2.ddl_text(_write(tmp_path, "DB2CRE.jcl", JOB)))


def test_jcl_block_ended_by_slash_star(tmp_path):
    text = "//SYSIN DD *\nCREATE TABLE T1 (A INTEGER);\n/*\n //SYSIN2 junk\n"
    out = db2.ddl_text(_write(tmp_path, "x.jcl", text))
    assert out == "CREATE TABLE T1 (A INTEGER);\n"


def test_jcl_shaped_txt_is_filtered_like_jcl(tmp_path):
    out = db2.ddl_text(_write(tmp_path, "HCMobile_DB2.txt", MIXED))
    _check_job(out)
    assert "CREATE TABLE HCZMSA1.user" in out  # the plain-SQL prefix survives


def test_plain_sql_txt_is_unchanged(tmp_path):
    text = "CREATE TABLE T1 (A INTEGER) IN DB.TS;\n-- note\nINSERT INTO T1 VALUES (1);\n"
    out = db2.ddl_text(_write(tmp_path, "plain.txt", text))
    assert out == "CREATE TABLE T1 (A INTEGER);\n-- note\nINSERT INTO T1 VALUES (1);\n"


def test_symbols_apply_to_both_sources(tmp_path):
    for name in ("a.jcl", "b.txt"):
        out = db2.ddl_text(
            _write(tmp_path, name, "//SYSIN DD *\nCREATE TABLE &Q..T (A INTEGER);\n"), {"&Q.": "HCZMSA1"}
        )
        assert "CREATE TABLE HCZMSA1.T" in out, name
