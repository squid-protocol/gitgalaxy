"""
#3344: the DB2 `EXEC SQL DECLARE <table> TABLE (...)` / DCLGEN fact channel.

`extract_boundary("cobol"|"pli", ...)["sql_tables"]` carries one row per declared
column: table, colno, name, SQL type, length/precision, scale, nullability and
the option text. Every fixture below is a REAL corpus shape:

  - cicsdev/cics-banking-sample-application-cbsa ACCDB2.cpy -- a bare DECLARE
    (no DCLGEN banner), CRLF line ends, `DECIMAL(4, 2)` with a space after the
    comma, and the list's `)` on the last column's line.
  - aws-mainframe-modernization-carddemo DCLTRTYP.dcl -- a real DCLGEN member:
    banner comments, `owner.table`, `) END-EXEC.` on its own line, and the COBOL
    host structure (which is record_data's, not this channel's).
  - IBM's DSN8 sample DCLGEN as shipped with sequence numbers in columns 1-6 AND
    73-80 -- the numbers would otherwise read as column names.
  - a PL/I DCLGEN include (`;` terminator, `/* */` banner).
"""

from gitgalaxy.core.db2_declare_table import extract_sql_tables
from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def cols(source, dialect="cobol"):
    return extract_boundary(dialect, source)["sql_tables"]


def shape(c):
    return (c["table"], c["colno"], c["name"], c["sql_type"], c["length"], c["scale"], c["nullable"])


# CBSA src/base/cobol_copy/ACCDB2.cpy, verbatim (CRLF).
ACCDB2 = (
    "      ******************************************************************\r\n"
    "      *  Copyright IBM Corp. 2023                                      *\r\n"
    "      ******************************************************************\r\n"
    "           EXEC SQL DECLARE ACCOUNT TABLE\r\n"
    "              ( ACCOUNT_EYECATCHER             CHAR(4),\r\n"
    "                ACCOUNT_CUSTOMER_NUMBER        CHAR(10),\r\n"
    "                ACCOUNT_SORTCODE               CHAR(6) NOT NULL,\r\n"
    "                ACCOUNT_NUMBER                 CHAR(8) NOT NULL,\r\n"
    "                ACCOUNT_TYPE                   CHAR(8),\r\n"
    "                ACCOUNT_INTEREST_RATE          DECIMAL(4, 2),\r\n"
    "                ACCOUNT_OPENED                 DATE,\r\n"
    "                ACCOUNT_OVERDRAFT_LIMIT        INTEGER,\r\n"
    "                ACCOUNT_LAST_STATEMENT         DATE,\r\n"
    "                ACCOUNT_NEXT_STATEMENT         DATE,\r\n"
    "                ACCOUNT_AVAILABLE_BALANCE      DECIMAL(10, 2),\r\n"
    "                ACCOUNT_ACTUAL_BALANCE         DECIMAL(10, 2) )\r\n"
    "           END-EXEC.\r\n"
)


def test_cbsa_accdb2_every_column_in_order():
    got = cols(ACCDB2)
    assert [c["name"] for c in got] == [
        "ACCOUNT_EYECATCHER",
        "ACCOUNT_CUSTOMER_NUMBER",
        "ACCOUNT_SORTCODE",
        "ACCOUNT_NUMBER",
        "ACCOUNT_TYPE",
        "ACCOUNT_INTEREST_RATE",
        "ACCOUNT_OPENED",
        "ACCOUNT_OVERDRAFT_LIMIT",
        "ACCOUNT_LAST_STATEMENT",
        "ACCOUNT_NEXT_STATEMENT",
        "ACCOUNT_AVAILABLE_BALANCE",
        "ACCOUNT_ACTUAL_BALANCE",
    ]
    assert [c["colno"] for c in got] == list(range(1, 13))
    assert {c["table"] for c in got} == {"ACCOUNT"}
    assert {c["table_line"] for c in got} == {4}
    by = {c["name"]: c for c in got}
    assert shape(by["ACCOUNT_SORTCODE"]) == ("ACCOUNT", 3, "ACCOUNT_SORTCODE", "CHAR", 6, None, False)
    assert by["ACCOUNT_SORTCODE"]["attributes"] == "NOT NULL"
    assert shape(by["ACCOUNT_INTEREST_RATE"])[3:] == ("DECIMAL", 4, 2, True)
    assert by["ACCOUNT_INTEREST_RATE"]["attributes"] is None
    # No length written -> None (DB2's defaults are not invented).
    assert shape(by["ACCOUNT_OPENED"])[3:] == ("DATE", None, None, True)
    assert shape(by["ACCOUNT_OVERDRAFT_LIMIT"])[3:] == ("INTEGER", None, None, True)
    # The list's `)` shares the last column's line.
    assert shape(by["ACCOUNT_ACTUAL_BALANCE"])[3:] == ("DECIMAL", 10, 2, True)
    assert by["ACCOUNT_EYECATCHER"]["line"] == 5
    assert by["ACCOUNT_ACTUAL_BALANCE"]["line"] == 16


# carddemo app/app-transaction-type-db2/dcl/DCLTRTYP.dcl (a real DCLGEN member).
DCLTRTYP = """\
      ******************************************************************
      * DCLGEN TABLE(CARDDEMO.TRANSACTION_TYPE)                        *
      *        LIBRARY(SNJARAO.AWS.DCL(DCLTRTYP))                      *
      *        LANGUAGE(COBOL)                                         *
      * ... IS THE DCLGEN COMMAND THAT MADE THE FOLLOWING STATEMENTS   *
      ******************************************************************
           EXEC SQL DECLARE CARDDEMO.TRANSACTION_TYPE TABLE
           ( TR_TYPE                        CHAR(2) NOT NULL,
             TR_DESCRIPTION                 VARCHAR(50) NOT NULL
           ) END-EXEC.
      ******************************************************************
      * COBOL DECLARATION FOR TABLE CARDDEMO.TRANSACTION_TYPE          *
      ******************************************************************
       01  DCLTRANSACTION-TYPE.
           10 DCL-TR-TYPE          PIC X(2).
           10 DCL-TR-DESCRIPTION.
              49 DCL-TR-DESCRIPTION-LEN
                 PIC S9(4) USAGE COMP.
              49 DCL-TR-DESCRIPTION-TEXT
                 PIC X(50).
"""


def test_carddemo_dclgen_member_both_schemas_separate():
    boundary = extract_boundary("cobol", DCLTRTYP)
    assert [shape(c) for c in boundary["sql_tables"]] == [
        ("CARDDEMO.TRANSACTION_TYPE", 1, "TR_TYPE", "CHAR", 2, None, False),
        ("CARDDEMO.TRANSACTION_TYPE", 2, "TR_DESCRIPTION", "VARCHAR", 50, None, False),
    ]
    # The COBOL host structure is still the record channel's, untouched.
    assert "DCLTRANSACTION-TYPE" in [r["name"] for r in boundary["records"]]
    assert not any(r["name"] == "TR_TYPE" for r in boundary["records"])


def test_dcl_members_are_claimed_by_cobol_alone():
    """#3365: carddemo keeps its DCLGEN members (LANGUAGE(COBOL)) as `.dcl`. Until
    an extension claimed them, the file never reached the extractor above. cobol
    must be the ONLY claimant, so the extension map is deterministic and no
    collision vote is needed."""
    from gitgalaxy.standards.language_lens import LanguageDetector

    owners = [lid for lid, d in LANGUAGE_DEFINITIONS.items() if ".dcl" in d.get("extensions", [])]
    assert owners == ["cobol"]
    assert LanguageDetector(LANGUAGE_DEFINITIONS, {}).extension_map[".dcl"] == "cobol"


# IBM DSN8 EMP DCLGEN, as members are stored on the host: sequence numbers in
# columns 1-6 and 73-80 of every line.
DSN8_SEQ = """\
000100******************************************************************00010000
000200* DCLGEN TABLE(DSN8C10.EMP)                                      *00020000
000300******************************************************************00030000
000400     EXEC SQL DECLARE DSN8C10.EMP TABLE                           00040000
000500     ( EMPNO                          CHAR(6) NOT NULL,           00050000
000600       FIRSTNME                       VARCHAR(12) NOT NULL,       00060000
000700       MIDINIT                        CHAR(1) NOT NULL,           00070000
000800       HIREDATE                       DATE,                       00080000
000900       SALARY                         DECIMAL(9, 2)               00090000
001000     ) END-EXEC.                                                  00100000
"""


def test_sequence_numbers_in_both_areas_are_not_columns():
    got = cols(DSN8_SEQ)
    assert [c["name"] for c in got] == ["EMPNO", "FIRSTNME", "MIDINIT", "HIREDATE", "SALARY"]
    assert got[-1]["sql_type"] == "DECIMAL" and (got[-1]["length"], got[-1]["scale"]) == (9, 2)
    assert got[0]["attributes"] == "NOT NULL"  # not `NOT NULL 00050000`
    assert [c["line"] for c in got] == [5, 6, 7, 8, 9]


# A PL/I DCLGEN include: `/* */` banner, `;` terminator, host structure after.
PLI_DCLGEN = """\
 /*********************************************************************/
 /* DCLGEN TABLE(DSN8C10.DEPT)                                        */
 /*********************************************************************/
 EXEC SQL DECLARE DSN8C10.DEPT TABLE
           ( DEPTNO                         CHAR(3) NOT NULL,
             DEPTNAME                       VARCHAR(36) NOT NULL,
             MGRNO                          CHAR(6),
             ADMRDEPT                       CHAR(3) NOT NULL,
             LOCATION                       CHAR(16)
           ) ;
 DCL 1 DCLDEPT,
      5 DEPTNO    CHAR(3),
      5 DEPTNAME  CHAR(36) VAR,
      5 MGRNO     CHAR(6),
      5 ADMRDEPT  CHAR(3),
      5 LOCATION  CHAR(16);
"""


def test_pli_dclgen_include():
    boundary = extract_boundary("pli", PLI_DCLGEN)
    got = boundary["sql_tables"]
    assert [shape(c) for c in got] == [
        ("DSN8C10.DEPT", 1, "DEPTNO", "CHAR", 3, None, False),
        ("DSN8C10.DEPT", 2, "DEPTNAME", "VARCHAR", 36, None, False),
        ("DSN8C10.DEPT", 3, "MGRNO", "CHAR", 6, None, True),
        ("DSN8C10.DEPT", 4, "ADMRDEPT", "CHAR", 3, None, False),
        ("DSN8C10.DEPT", 5, "LOCATION", "CHAR", 16, None, True),
    ]
    # The PL/I host structure still rides record_data.
    assert "DCLDEPT" in [r["name"] for r in boundary["records"]]


# An inline declaration in a program's WORKING-STORAGE, next to a cursor and a
# DGTT -- neither of which is a table declaration.
INLINE_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EMPRPT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA END-EXEC.
           EXEC SQL DECLARE EMP_PHOTO TABLE
           ( EMPNO        CHAR(6)       NOT NULL,
             PHOTO_FORMAT VARCHAR(10)   NOT NULL WITH DEFAULT,
             PICTURE      BLOB(100K),
             RESUME       CLOB(1M),
             CHECKSUM     CHAR(8) FOR BIT DATA,
             UPDATED_TS   TIMESTAMP(6) WITH TIME ZONE NOT NULL,
             "MixedCase"  SMALLINT,          -- a delimited name
             RATE         DECIMAL(5),
             SCORE        DOUBLE PRECISION
           ) END-EXEC.
           EXEC SQL DECLARE C1 CURSOR FOR
               SELECT EMPNO FROM EMP_PHOTO
           END-EXEC.
           EXEC SQL DECLARE GLOBAL TEMPORARY TABLE SESSION.WORK
               (K CHAR(1)) END-EXEC.
       01  WS-MSG PIC X(40) VALUE 'EXEC SQL DECLARE FAKE TABLE (X INT)'.
       PROCEDURE DIVISION.
           GOBACK.
"""


def test_inline_declaration_type_variety():
    got = cols(INLINE_PROGRAM)
    assert {c["table"] for c in got} == {"EMP_PHOTO"}  # no cursor, no DGTT, no literal
    by = {c["name"]: c for c in got}
    assert by["PHOTO_FORMAT"]["attributes"] == "NOT NULL WITH DEFAULT"
    assert by["PHOTO_FORMAT"]["nullable"] is False
    # LOB lengths carry their K/M multiplier.
    assert (by["PICTURE"]["sql_type"], by["PICTURE"]["length"]) == ("BLOB", 100 * 1024)
    assert (by["RESUME"]["sql_type"], by["RESUME"]["length"]) == ("CLOB", 1024 * 1024)
    assert by["CHECKSUM"]["attributes"] == "FOR BIT DATA" and by["CHECKSUM"]["nullable"] is True
    # WITH TIME ZONE belongs to the type; NOT NULL is still an option.
    assert by["UPDATED_TS"]["sql_type"] == "TIMESTAMP WITH TIME ZONE"
    assert (by["UPDATED_TS"]["length"], by["UPDATED_TS"]["nullable"]) == (6, False)
    # A delimited name keeps its case; the `--` comment is not an attribute.
    assert by["MixedCase"]["sql_type"] == "SMALLINT" and by["MixedCase"]["attributes"] is None
    assert (by["RATE"]["length"], by["RATE"]["scale"]) == (5, None)
    assert by["SCORE"]["sql_type"] == "DOUBLE PRECISION"
    assert [c["colno"] for c in got] == list(range(1, 10))


def test_two_tables_number_their_columns_independently():
    src = (
        "           EXEC SQL DECLARE A TABLE (X CHAR(1), Y CHAR(2)) END-EXEC.\n"
        "           EXEC SQL DECLARE B TABLE (Z INTEGER NOT NULL) END-EXEC.\n"
    )
    assert [(c["table"], c["colno"], c["name"]) for c in cols(src)] == [
        ("A", 1, "X"),
        ("A", 2, "Y"),
        ("B", 1, "Z"),
    ]


def test_commented_out_declaration_via_prism():
    src = (
        "      *    EXEC SQL DECLARE OLD_T TABLE\n"
        "      *    ( A CHAR(1) ) END-EXEC.\n"
        "           EXEC SQL DECLARE NEW_T TABLE\n"
        "           ( B CHAR(2) ) END-EXEC.\n"
    )
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    code_stream = prism.split_streams(src, "cobol")["code_stream"]
    assert [(c["table"], c["name"], c["line"]) for c in cols(code_stream)] == [("NEW_T", "B", 4)]


def test_unbalanced_list_and_hyphen_boundary_yield_nothing():
    # An unclosed list is skipped rather than swallowing the rest of the file.
    assert cols("           EXEC SQL DECLARE T TABLE ( A CHAR(1)\n" + "       X.\n" * 10) == []
    # `-` is a COBOL name character: `WS-EXEC SQL` does not anchor a statement.
    assert cols("           MOVE WS-EXEC SQL DECLARE T TABLE (A CHAR(1)) END-EXEC.\n") == []


def test_non_sql_dialects_and_no_declaration():
    assert extract_boundary("cobol", "       PROCEDURE DIVISION.\n           GOBACK.\n")["sql_tables"] == []
    # JCL and CSD cannot embed SQL; they carry no key at all (read with a default).
    assert "sql_tables" not in extract_boundary("jcl", "//S1 EXEC PGM=X\n")
    assert extract_sql_tables("") == []


def test_long_file_is_linear():
    # Many DECLAREs with no TABLE and many near-miss headers stay fast (bounded runs).
    src = ("           EXEC SQL DECLARE C1 CURSOR FOR SELECT 1 END-EXEC.\n" * 5000) + ACCDB2
    got = cols(src)
    assert len(got) == 12 and got[0]["line"] == 5001 + 4
