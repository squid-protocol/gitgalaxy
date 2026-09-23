"""
#3250: the PL/I DECLARE record-layout channel of `mainframe_boundary`.

`extract_boundary("pli", ...)["records"]` carries a PL/I program's DECLAREd
structures in the same `record_data` shape as a COBOL DATA DIVISION (#3246):
level-number nesting, PICTURE, the data type, dimensions/REFER, DEFINED, INIT,
plus the full attribute text in `attributes`. Every fixture is a REAL corpus
shape -- IBM/zopeneditor-sample's PSAM1/CUSTPLI/MACSAMP and navikt/DSF's
fixed-format members -- and several of them broke a first draft:

  - DSF numbers columns 73-80, and PRISM leaves the number behind when it strips
    the comment before it, so orphaned sequence numbers (two in a row, after two
    commented `%INCLUDE` lines) sat in front of the next DCL and hid it. The
    answer key's independent reader caught this on 179 of 1,473 DSF files.
  - `DCL 1 B01 BASED(P), %INCLUDE P0019921;` -- the members come from an include.
  - `DCL (ADDR, NULL) BUILTIN;` and `DCL PSAM2 EXTERNAL ENTRY;` are not storage.
  - MACSAMP's `%DECLARE` and preprocessor-procedure `DECLARE` are compile-time.
"""

from gitgalaxy.core.mainframe_boundary import extract_boundary


def records(source):
    return extract_boundary("pli", source)["records"]


def by_name(recs):
    return {r["name"]: r for r in recs}


# IBM/zopeneditor-sample PLI/PSAM1.pli: a two-level structure with a nested
# group, PIC items, DEFINED overlays of the whole record, BIT flags with INIT,
# BIN FIXED counters, and a file/entry declaration that is not data.
PSAM1 = """\
 PSAM1: PROC OPTIONS(MAIN) RETURNS(DEC(12,2));
   DCL DUMP_FINDER CHAR(30) INIT('*STORAGE FOR PROGRAM PSAM1***');
   DCL CUSTFILE FILE INPUT RECORD SEQUENTIAL
              ENV(FB RECSIZE(80) BLKSIZE(0));
    DCL 1 TRAN_RECORD,
          2 TRAN_CODE          CHAR(6),
          2 TRAN_FILL3         CHAR(1),
          2 CRUNCH_PARMS,
            3 CRUNCH_IO_LOOPS    PIC '99999',
            3 CRUNCH_FILL1       CHAR(1),
            3 CRUNCH_CPU_LOOPS   PIC '999999999',
          2 CRUNCH_FILL2       CHAR(58);

    DCL TRAN_COMMENT           CHAR(1)    DEFINED TRAN_RECORD;
      %INCLUDE CUSTPLI;
   DCL  TRANFILE_EOF BIT(1) INIT ('0'B);
   DCL NUM_TRANFILE_RECS     BIN FIXED(15) INIT(0);
   DCL PSAM2 EXTERNAL ENTRY;
   DCL 1 HDR2,
         2 HDR2A CHAR(40) UNALIGNED
               INIT('ID    CUSTOMER NAME     OCCUPATION      ');
   DCL I FIXED DEC(2);
   PROGRAM_STATUS = 'DCL NOT_A_DECLARATION CHAR(1);';
 END PSAM1;
"""


def test_a_structure_nests_by_level_number():
    recs = records(PSAM1)
    tree = [(r["level"], r["name"], r["parent_ordinal"]) for r in recs if r["name"].startswith(("TRAN_", "CRUNCH"))]
    root = next(r["ordinal"] for r in recs if r["name"] == "TRAN_RECORD")
    group = next(r["ordinal"] for r in recs if r["name"] == "CRUNCH_PARMS")
    assert tree[:8] == [
        (1, "TRAN_RECORD", None),
        (2, "TRAN_CODE", root),
        (2, "TRAN_FILL3", root),
        (2, "CRUNCH_PARMS", root),
        (3, "CRUNCH_IO_LOOPS", group),
        (3, "CRUNCH_FILL1", group),
        (3, "CRUNCH_CPU_LOOPS", group),
        (2, "CRUNCH_FILL2", root),
    ]


def test_attributes_map_onto_the_record_columns():
    items = by_name(records(PSAM1))
    assert (items["TRAN_CODE"]["usage"], items["TRAN_CODE"]["pic"]) == ("CHAR(6)", None)
    assert (items["CRUNCH_IO_LOOPS"]["pic"], items["CRUNCH_IO_LOOPS"]["usage"]) == ("99999", None)
    # Group items carry no type of their own.
    assert (items["CRUNCH_PARMS"]["usage"], items["CRUNCH_PARMS"]["attributes"]) == (None, None)
    # The data type in canonical order, whichever keyword the precision sat on.
    assert items["NUM_TRANFILE_RECS"]["usage"] == "FIXED BIN(15)"
    assert items["NUM_TRANFILE_RECS"]["attributes"] == "BIN FIXED(15)"
    assert items["I"]["usage"] == "FIXED DEC(2)"
    # DEFINED is the REDEFINES analog: it names the item it overlays.
    assert items["TRAN_COMMENT"]["redefines"] == "TRAN_RECORD"


def test_init_is_the_value_literal():
    items = by_name(records(PSAM1))
    assert items["DUMP_FINDER"]["value"] == "*STORAGE FOR PROGRAM PSAM1***"
    assert items["TRANFILE_EOF"]["value"] == "'0'B"  # a bit literal keeps its suffix
    assert items["NUM_TRANFILE_RECS"]["value"] == "0"
    assert items["HDR2A"]["value"] == "ID    CUSTOMER NAME     OCCUPATION      "
    # INIT rides in `value`, never in `attributes`.
    assert items["HDR2A"]["attributes"] == "CHAR(40) UNALIGNED"


def test_files_entries_and_string_literals_are_not_items():
    names = set(by_name(records(PSAM1)))
    assert not names & {"CUSTFILE", "PSAM2", "NOT_A_DECLARATION"}


def test_line_is_the_source_line_of_the_item():
    items = by_name(records(PSAM1))
    assert items["TRAN_RECORD"]["line"] == 5
    assert items["CRUNCH_CPU_LOOPS"]["line"] == 11


# zopeneditor-sample INCLUDES/CUSTPLI.inc: two BASED overlays of one record.
CUSTPLI = """\
   DCL 1 CUSTFILE_RECORD     CHAR(80);
   DCL 1 CUSTOMER_RECORD  BASED(ADDR(CUSTFILE_RECORD)),
         2 CUSTOMER_KEY,
           3 CUST_ID         CHAR(5),
           3 RECORD_TYPE     CHAR(1),
         2 ACCT_BALANCE      PIC '9999999V99';
"""


def test_the_root_storage_class_is_every_members_section():
    """PL/I allows a storage class only on level 1; the members share it."""
    items = by_name(records(CUSTPLI))
    assert items["CUSTFILE_RECORD"]["section"] is None
    assert {items[n]["section"] for n in ("CUSTOMER_RECORD", "CUSTOMER_KEY", "CUST_ID", "ACCT_BALANCE")} == {"BASED"}
    # BASED names a pointer, not an overlaid item, so it is not `redefines`.
    assert items["CUSTOMER_RECORD"]["redefines"] is None
    assert items["CUSTOMER_RECORD"]["attributes"] == "BASED(ADDR(CUSTFILE_RECORD))"


# navikt/DSF shapes: fixed-format with a sequence number in columns 73-80, a
# comment before it that PRISM strips (leaving the number mid-line), the
# `DEF ... POS(n)` overlay idiom, factored BUILTINs, and a structure whose
# members come from an %INCLUDE.
def _seq(line: str, n: int) -> str:
    return f"{line:<72}{n:08d}"


DSF = "\n".join(
    [
        _seq(" R001B1: PROC(COMMAREA_PEKER) OPTIONS (MAIN);", 190),
        "    %INCLUDE P0019910;            00000230",  # PRISM left these two behind
        "    %INCLUDE S001A1;              00000250",
        "                                  00000260",
        _seq("    DCL", 280),
        _seq("      CSTG                       BUILTIN,", 290),
        _seq("      BMSMAPBR                   POINTER,", 310),
        _seq("      COMMAREA_PEKER             POINTER;", 320),
        _seq("    DCL  1  B01 BASED(B01_PEKER), %INCLUDE P0019921;", 330),
        _seq("   DCL", 340),
        _seq("      DATO_AMD PIC '(8)9',", 350),
        _seq("      DAGENS_DATO_AM DEF DATO_AMD POS(1) PIC '999999';", 360),
        _seq("    DCL (ADDR, NULL, SUBSTR) BUILTIN;", 370),
    ]
)


def test_sequence_numbers_never_hide_or_join_a_declaration():
    items = by_name(records(DSF))
    assert set(items) == {"BMSMAPBR", "COMMAREA_PEKER", "B01", "DATO_AMD", "DAGENS_DATO_AM"}
    assert items["BMSMAPBR"]["usage"] == "POINTER"
    assert items["BMSMAPBR"]["attributes"] == "POINTER"  # no `00000310` in it
    assert items["BMSMAPBR"]["line"] == 7


def test_def_pos_overlay_and_a_structure_filled_by_include():
    items = by_name(records(DSF))
    assert items["DATO_AMD"]["pic"] == "(8)9"
    assert (items["DAGENS_DATO_AM"]["redefines"], items["DAGENS_DATO_AM"]["pic"]) == ("DATO_AMD", "999999")
    assert items["DAGENS_DATO_AM"]["attributes"] == "DEF DATO_AMD POS(1) PIC'999999'"
    # The members are in P0019921, scanned on its own; here B01 is a childless root.
    assert (items["B01"]["level"], items["B01"]["section"]) == (1, "BASED")


# Dimensions, REFER (the OCCURS DEPENDING ON analog), UNION, LIKE, factoring,
# VARYING, national letters (DSF: `DATO_ÅMD`) and an ENTRY VARIABLE (data) next
# to an ENTRY constant (not).
SHAPES = """\
 dcl 1 msg based(p),
       2 cnt fixed bin(31),
       2 items(n refer(cnt)) char(8),
       2 grid(0:9, 3) bit(1),
       2 table(12) fixed dec(7,2),
       2 u union,
         3 as_char char(4),
         3 as_num  fixed bin(31);
 DCL 1 COPY2 LIKE MSG;
 DCL 1 S, 2 (A, B) FIXED BIN(31) INIT(0), 2 * CHAR(2);
 DCL W CHAR(10) VARYING STATIC EXTERNAL;
 DCL DATO_ÅMD PIC '(8)9';
 DCL E ENTRY(FIXED) RETURNS(FIXED), EV ENTRY VARIABLE;
"""


def test_dimensions_and_refer():
    items = by_name(records(SHAPES))
    assert (items["TABLE"]["occurs_min"], items["TABLE"]["occurs_max"]) == (12, 12)
    assert items["GRID"]["occurs_max"] == 10  # the first dimension, (0:9)
    assert (items["ITEMS"]["occurs_max"], items["ITEMS"]["occurs_depending_on"]) == (None, "CNT")
    assert items["TABLE"]["attributes"] == "(12) FIXED DEC(7,2)"
    assert items["TABLE"]["usage"] == "FIXED DEC(7,2)"


def test_union_like_factoring_and_filler():
    recs = records(SHAPES)
    items = by_name(recs)
    assert [r["name"] for r in recs if r["parent_ordinal"] == items["U"]["ordinal"]] == ["AS_CHAR", "AS_NUM"]
    assert items["U"]["attributes"] == "UNION"
    assert items["COPY2"]["attributes"] == "LIKE MSG"
    # `2 (A, B) ...` is two items sharing the attributes; `*` is unnamed filler.
    s = items["S"]["ordinal"]
    assert [(r["name"], r["usage"], r["value"]) for r in recs if r["parent_ordinal"] == s] == [
        ("A", "FIXED BIN(31)", "0"),
        ("B", "FIXED BIN(31)", "0"),
        ("*", "CHAR(2)", None),
    ]


def test_varying_national_letters_and_entry_variables():
    items = by_name(records(SHAPES))
    assert (items["W"]["usage"], items["W"]["section"]) == ("CHAR(10) VARYING", "STATIC")
    assert items["DATO_ÅMD"]["pic"] == "(8)9"
    assert "EV" in items and "E" not in items


# zopeneditor-sample PLI/MACSAMP.pli: compile-time declarations.
MACSAMP = """\
 %DECLARE PLATFORM CHARACTER;
 %PLATFORM = 'MVS';
 %SCOREGET: PROCEDURE(IDX) RETURNS(FIXED);
   DECLARE IDX FIXED;
   RETURN(SCORES(IDX));
 %END SCOREGET;
 MACROFEATURES: PROC OPTIONS(MAIN);
 DCL (ABABAB, WORLD) CHAR;
 %DO I = 1 TO COUNT;
   DCL FIELD%;J FIXED BIN(31);
 %END;
 DCL AFTER BIT(8) ALIGNED;
"""


def test_preprocessor_declarations_are_not_storage():
    assert [r["name"] for r in records(MACSAMP)] == ["ABABAB", "WORLD", "AFTER"]


def test_other_channels_stay_empty_and_other_dialects_carry_no_pli():
    boundary = extract_boundary("pli", PSAM1)
    assert boundary["calls"] == boundary["datasets"] == boundary["transactions"] == []
    assert extract_boundary("cobol", "       DCL 1 X CHAR(1);\n")["records"] == []


def test_an_unterminated_declare_is_linear():
    """No `;` anywhere: the statement runs to end of file and is still one pass."""
    import time

    src = " DCL 1 S,\n" + "   2 F CHAR(1),\n" * 20000
    start = time.perf_counter()
    assert len(records(src)) == 20001
    assert time.perf_counter() - start < 2.0
