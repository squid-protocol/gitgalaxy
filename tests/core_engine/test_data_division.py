"""
#3246: the DATA DIVISION record-layout channel of `mainframe_boundary`.

`extract_boundary("cobol", ...)["records"]` is the schema of a COBOL system: the
01/05/... item tree with PIC, USAGE/COMP-3, OCCURS [DEPENDING ON], REDEFINES and
VALUE, each FILE SECTION `01` bound to its `FD`. Every fixture here is the shape
of REAL source from the pinned corpora (aws-mainframe-modernization-carddemo's
CBACT01C, CVACT01Y), not a minimal one -- the `USAGE IS COMP-3` on a continuation
line, the `REDEFINES` whose target name ends in a USAGE keyword, the OCCURS table,
the 88-level condition names, and the FD/WORKING-STORAGE section split. Each of
those broke a first draft of the walker.
"""

from gitgalaxy.core.mainframe_boundary import extract_boundary

# aws-mainframe-modernization-carddemo/app/cbl/CBACT01C.cbl's real shape: three
# FDs in the FILE SECTION (one an OCCURS table, several COMP-3), then
# WORKING-STORAGE with a BINARY item, a REDEFINES of it, 88-level condition
# names, and a numeric VALUE that ends the clause with a period.
COBOL_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CBACT01C.
       DATA DIVISION.
       FILE SECTION.
       FD  ACCTFILE-FILE.
       01  FD-ACCTFILE-REC.
           05 FD-ACCT-ID                        PIC 9(11).
           05 FD-ACCT-DATA                      PIC X(289).
       FD  ARRY-FILE.
       01  ARR-ARRAY-REC.
           05 ARR-ACCT-ID                       PIC 9(11).
           05 ARR-ACCT-BAL   OCCURS 5  TIMES.
              10 ARR-ACCT-CURR-BAL              PIC S9(10)V99.
              10 ARR-ACCT-DEBIT                 PIC S9(10)V99
                                         USAGE IS COMP-3.
       WORKING-STORAGE SECTION.
       01  TWO-BYTES-BINARY        PIC 9(4) BINARY.
       01  TWO-BYTES-ALPHA         REDEFINES TWO-BYTES-BINARY.
           05  TWO-BYTES-LEFT      PIC X.
           05  TWO-BYTES-RIGHT     PIC X.
       01  APPL-RESULT             PIC S9(9) COMP.
           88  APPL-AOK            VALUE 0.
           88  APPL-EOF            VALUE 16.
       01  WS-NAME                 PIC X(20) VALUE 'GNANthony'.
       01  FILLER                  PIC X(10).
       PROCEDURE DIVISION.
       0000-MAIN.
           05 NOT-A-DATA-ITEM MOVE 1 TO X.
           GOBACK.
"""

# CVACT01Y.cpy's real shape: a bare copybook, no DATA DIVISION header, one 01 and
# its 05 fields ending in a FILLER. A copybook carries its own layout.
COPYBOOK = """\
      *****************************************************************
       01  ACCOUNT-RECORD.
           05  ACCT-ID                           PIC 9(11).
           05  ACCT-CURR-BAL                     PIC S9(10)V99.
           05  FILLER                            PIC X(178).
"""


def records(source):
    return extract_boundary("cobol", source)["records"]


def by_name(recs):
    return {r["name"]: r for r in recs}


def test_a_copybook_with_no_division_headers_is_read_whole():
    recs = records(COPYBOOK)
    names = [r["name"] for r in recs]
    assert names == ["ACCOUNT-RECORD", "ACCT-ID", "ACCT-CURR-BAL", "FILLER"]
    # The 01 is the root; the 05s hang off it.
    assert recs[0]["parent_ordinal"] is None
    assert all(r["parent_ordinal"] == 0 for r in recs[1:])
    assert by_name(recs)["ACCT-CURR-BAL"]["pic"] == "S9(10)V99"


def test_fd_record_layouts_bind_to_their_file():
    recs = by_name(records(COBOL_PROGRAM))
    assert recs["FD-ACCTFILE-REC"]["section"] == "FILE"
    assert recs["FD-ACCTFILE-REC"]["fd_name"] == "ACCTFILE-FILE"
    assert recs["ARR-ARRAY-REC"]["fd_name"] == "ARRY-FILE"
    # A subordinate field inherits the FD of the 01 it lives under.
    assert recs["ARR-ACCT-ID"]["fd_name"] == "ARRY-FILE"


def test_working_storage_items_carry_no_fd():
    recs = by_name(records(COBOL_PROGRAM))
    assert recs["TWO-BYTES-BINARY"]["section"] == "WORKING-STORAGE"
    assert recs["TWO-BYTES-BINARY"]["fd_name"] is None


def test_nesting_is_by_level_number():
    recs = records(COBOL_PROGRAM)
    idx = {r["name"]: r["ordinal"] for r in recs}
    by = by_name(recs)
    # 10-level fields nest under the 05 OCCURS group, which nests under the 01.
    assert by["ARR-ACCT-CURR-BAL"]["parent_ordinal"] == idx["ARR-ACCT-BAL"]
    assert by["ARR-ACCT-BAL"]["parent_ordinal"] == idx["ARR-ARRAY-REC"]


def test_occurs_table_size_is_captured():
    by = by_name(records(COBOL_PROGRAM))
    assert (by["ARR-ACCT-BAL"]["occurs_min"], by["ARR-ACCT-BAL"]["occurs_max"]) == (5, 5)
    assert by["ARR-ACCT-BAL"]["pic"] is None  # a group table has no PIC


def test_usage_on_a_continuation_line_is_read():
    """`USAGE IS COMP-3.` sits on the line after the PIC; the entry window spans it."""
    assert by_name(records(COBOL_PROGRAM))["ARR-ACCT-DEBIT"]["usage"] == "COMP-3"


def test_a_redefines_target_ending_in_a_usage_keyword_is_not_a_usage():
    """`REDEFINES TWO-BYTES-BINARY` must not read BINARY as this item's USAGE:
    `-` is a COBOL name character, so a `\\b`-delimited keyword would match inside
    the name. The item is a group and carries no usage of its own."""
    alpha = by_name(records(COBOL_PROGRAM))["TWO-BYTES-ALPHA"]
    assert alpha["redefines"] == "TWO-BYTES-BINARY"
    assert alpha["usage"] is None
    assert by_name(records(COBOL_PROGRAM))["TWO-BYTES-BINARY"]["usage"] == "BINARY"


def test_condition_names_attach_to_the_item_above_and_are_not_parents():
    recs = records(COBOL_PROGRAM)
    by = by_name(recs)
    idx = {r["name"]: r["ordinal"] for r in recs}
    for cond, val in (("APPL-AOK", "0"), ("APPL-EOF", "16")):
        assert by[cond]["level"] == 88
        assert by[cond]["parent_ordinal"] == idx["APPL-RESULT"]
        # A numeric VALUE loses the clause-terminating period.
        assert by[cond]["value"] == val
    # An 88 is never itself a parent of anything.
    cond_ordinals = {r["ordinal"] for r in recs if r["level"] == 88}
    assert not (cond_ordinals & {r["parent_ordinal"] for r in recs})


def test_quoted_value_is_kept_verbatim():
    assert by_name(records(COBOL_PROGRAM))["WS-NAME"]["value"] == "GNANthony"


def test_filler_is_extracted_but_named_filler():
    """FILLER is real storage (byte offsets need it), so it is recorded, not dropped."""
    assert "FILLER" in by_name(records(COBOL_PROGRAM))


def test_the_procedure_division_is_not_read_as_data_items():
    """A numbered construct after PROCEDURE DIVISION is not a level number."""
    assert "NOT-A-DATA-ITEM" not in by_name(records(COBOL_PROGRAM))


def test_jcl_carries_no_record_layouts():
    assert extract_boundary("jcl", "//J JOB\n//S EXEC PGM=X\n")["records"] == []


# #4246: DBB MortgageApplication EPSCSMRD's real shape -- level-2 entries with no name, each an implicit
# FILLER whose first word is its PIC clause; beside them a named item and an explicit FILLER.
UNNAMED_ITEMS = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EPSCSMRD.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       1 EPSPDATA-HEADER.
         2 PIC X(40) USAGE DISPLAY VALUE 'HEADER LINE ONE'.
         2 TITLE-TEXT PIC X(10) VALUE 'TITLE'.
         2 COMP-3 PIC S9(5).
         2 FILLER PIC X(4).
         2 USAGE BINARY PIC 9(4).
         2 VALUE 'Z' PIC X.
         2 PICTURE IS 9(3) OCCURS 2 TIMES.
       PROCEDURE DIVISION.
           GOBACK.
"""


def test_an_unnamed_entry_is_an_implicit_filler_with_its_clauses():
    recs = records(UNNAMED_ITEMS)
    assert [(r["level"], r["name"], r["pic"], r["usage"], r["value"]) for r in recs] == [
        (1, "EPSPDATA-HEADER", None, None, None),
        (2, "FILLER", "X(40)", "DISPLAY", "HEADER LINE ONE"),  # not an item named PIC with no PIC
        (2, "TITLE-TEXT", "X(10)", None, "TITLE"),
        (2, "FILLER", "S9(5)", "COMP-3", None),
        (2, "FILLER", "X(4)", None, None),
        (2, "FILLER", "9(4)", "BINARY", None),
        (2, "FILLER", "X", None, "Z"),
        (2, "FILLER", "9(3)", None, None),
    ]
    assert recs[-1]["occurs_min"] == 2
    assert all(r["parent_ordinal"] == 0 for r in recs[1:])


def test_an_unnamed_entrys_value_is_no_call_target():
    """The VALUE of an unnamed entry belongs to no name, so it never resolves `CALL PIC`."""
    from gitgalaxy.core.mainframe_boundary import _cobol_value_map

    assert _cobol_value_map(UNNAMED_ITEMS) == {"TITLE-TEXT": "TITLE"}


def test_a_name_that_only_starts_with_a_clause_word_is_kept():
    """`PIC-CODE`, `VALUE-DATE`, `COMP-RATE`, `INDEX-NO`: names, not unnamed entries."""
    src = COPYBOOK.replace("ACCT-ID  ", "PIC-CODE ").replace("ACCT-CURR-BAL", "COMP-RATE    ")
    src += "           05  VALUE-DATE                        PIC X(8).\n"
    src += "           05  INDEX-NO                          PIC 9(4).\n"
    names = [r["name"] for r in records(src)]
    assert names == ["ACCOUNT-RECORD", "PIC-CODE", "COMP-RATE", "FILLER", "VALUE-DATE", "INDEX-NO"]
