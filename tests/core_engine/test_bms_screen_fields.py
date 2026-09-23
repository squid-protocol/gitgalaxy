"""
#3347: the BMS screen-field channel -- `extract_boundary("bms", ...)["screen_fields"]`.

A BMS map source is HLASM macro code: DFHMSD (mapset), DFHMDI (map), DFHMDF
(field). Every row is one macro statement, flat and in source order, with the
mapset -> map -> field tree carried as `ordinal`/`parent_ordinal`. Every fixture
is a REAL corpus shape, and the three continuation styles are the three the
pinned corpora use:

  - aws-mainframe-modernization-carddemo `app/bms`: one keyword per line, `-` in
    column 72 (and `TYPE=&&SYSPARM`).
  - cics-banking-sample-application-cbsa `src/base/bms_src`: several operands
    per line, `*` in column 72, and an INITIAL literal continued MID-WORD onto
    column 16 of the next line (`...and pr*` / `ess Enter.'`).
  - language-crucible `data/bms/cbsa/ssmap.bms`: `X` in column 72,
    `JUSTIFY=(RIGHT,ZERO)`, zero-padded POS values.
"""

import re

from gitgalaxy.core.bms_screen_fields import _INTEGER, _KEYWORD, _NAME, _OPERATION, _POS_PAIR, bms_screen_fields
from gitgalaxy.core.mainframe_boundary import BOUNDARY_DIALECTS, extract_boundary
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _line(text: str, cont: str = " ") -> str:
    """One fixed-format HLASM line: text in columns 1-71, `cont` in column 72."""
    assert len(text) <= 71, text
    return f"{text:<71}{cont}"


def fields(source: str) -> list[dict]:
    return extract_boundary("bms", source)["screen_fields"]


def by_name(rows):
    return {r["name"]: r for r in rows if r["name"]}


# carddemo app/bms/COCRDLI.bms (head), verbatim shape: `-` continuation, one
# keyword per line, TYPE=&&SYSPARM, an unnamed literal and named fields.
CARDDEMO = "\n".join(
    [
        "******************************************************************",
        "*    CardDemo - Card Listing Screen",
        "        TITLE 'BMS MAP FOR CARD LISTING'",
        _line("COCRDLI DFHMSD LANG=COBOL,", "-"),
        _line("               MODE=INOUT,", "-"),
        _line("               STORAGE=AUTO,", "-"),
        _line("               TIOAPFX=YES,", "-"),
        "               TYPE=&&SYSPARM",
        _line("CCRDLIA DFHMDI CTRL=(FREEKB),", "-"),
        _line("               DSATTS=(COLOR,HILIGHT,PS,VALIDN),", "-"),
        _line("               MAPATTS=(COLOR,HILIGHT,PS,VALIDN),", "-"),
        "               SIZE=(24,80)",
        _line("        DFHMDF ATTRB=(ASKIP,NORM),", "-"),
        _line("               COLOR=BLUE,", "-"),
        _line("               LENGTH=5,", "-"),
        _line("               POS=(1,1),", "-"),
        "               INITIAL='Tran:'",
        _line("TRNNAME DFHMDF ATTRB=(ASKIP,FSET,NORM),", "-"),
        _line("               COLOR=BLUE,", "-"),
        _line("               LENGTH=4,", "-"),
        "               POS=(1,7)",
        _line("ACCTSID DFHMDF ATTRB=(FSET,IC,NORM,UNPROT),", "-"),
        _line("               COLOR=GREEN,", "-"),
        _line("               HILIGHT=UNDERLINE,", "-"),
        _line("               LENGTH=11,", "-"),
        _line("               PICIN='99999999999',", "-"),
        _line("               POS=(6,44),", "-"),
        "               VALIDN=(MUSTFILL)",
        "        DFHMSD TYPE=FINAL",
        "        END",
    ]
)


def test_the_mapset_map_field_tree_nests_by_macro():
    rows = fields(CARDDEMO)
    assert [(r["kind"], r["name"], r["parent_ordinal"]) for r in rows] == [
        ("mapset", "COCRDLI", None),
        ("map", "CCRDLIA", 0),
        ("field", None, 1),
        ("field", "TRNNAME", 1),
        ("field", "ACCTSID", 1),
    ]
    assert [r["ordinal"] for r in rows] == list(range(5))
    assert [r["line"] for r in rows] == [4, 9, 13, 18, 22]


def test_one_keyword_per_continuation_line_is_one_statement():
    items = by_name(fields(CARDDEMO))
    acct = items["ACCTSID"]
    assert (acct["pos_line"], acct["pos_column"], acct["length"]) == (6, 44, 11)
    assert acct["attrb"] == "FSET,IC,NORM,UNPROT"
    assert acct["picin"] == "99999999999"
    assert acct["attributes"] == "COLOR=GREEN,HILIGHT=UNDERLINE,VALIDN=(MUSTFILL)"
    literal = fields(CARDDEMO)[2]
    assert (literal["initial"], literal["pos_line"], literal["pos_column"], literal["length"]) == ("Tran:", 1, 1, 5)


def test_mapset_and_map_operands_are_kept_as_written():
    mapset, map_ = fields(CARDDEMO)[:2]
    assert mapset["attributes"] == "LANG=COBOL,MODE=INOUT,STORAGE=AUTO,TIOAPFX=YES,TYPE=&&SYSPARM"
    assert (
        map_["attributes"]
        == "CTRL=(FREEKB),DSATTS=(COLOR,HILIGHT,PS,VALIDN),MAPATTS=(COLOR,HILIGHT,PS,VALIDN),SIZE=(24,80)"
    )
    # Geometry columns are a field's; a map's SIZE stays in its operand text.
    assert all(map_[c] is None for c in ("pos_line", "pos_column", "length", "attrb", "initial"))


def test_type_final_closes_the_mapset_and_is_not_a_row():
    rows = fields(CARDDEMO)
    assert sum(1 for r in rows if r["kind"] == "mapset") == 1
    assert "FINAL" not in (rows[-1]["attributes"] or "")


# cics-banking-sample-application-cbsa src/base/bms_src/BNK1CAM.bms and
# BNK1ACC.bms: several operands per line, `*` continuation, an INITIAL continued
# mid-word, OCCURS, PICOUT, and a field whose INITIAL is on the continuation line.
CBSA = "\n".join(
    [
        _line("BNK1CAM  DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL,STORAGE=AUTO,", "*"),
        "               DSATTS=(COLOR,HILIGHT,OUTLINE,PS,SOSI)",
        _line("BNK1CA   DFHMDI SIZE=(24,80),", "*"),
        "               COLUMN=1,LINE=1",
        _line("         DFHMDF POS=(3,1),LENGTH=57,ATTRB=(NORM,PROT),COLOR=TURQUOISE,", "*"),
        _line("               INITIAL='Please provide the requested information and pr", "*"),
        "               ess Enter.'",
        _line("COMPANY  DFHMDF POS=(1,18),LENGTH=58,ATTRB=(NORM,PROT),COLOR=RED,", "*"),
        "               INITIAL='CICS Bank Sample Application- Create Account. '",
        "***********************************************************************",
        _line("ACCOUNT  DFHMDF POS=(9,1),LENGTH=79,ATTRB=(NORM,PROT,FSET,ASKIP),", "*"),
        "               COLOR=NEUTRAL,OCCURS=10",
        _line("INTRT    DFHMDF POS=(11,20),LENGTH=7,", "*"),
        _line("               ATTRB=(UNPROT,FSET,NORM),COLOR=GREEN,PICOUT='9999.99',", "*"),
        "               HILIGHT=UNDERLINE",
        "         DFHMDF POS=(11,28),LENGTH=1,ATTRB=(ASKIP,PROT)",
        "         DFHMSD TYPE=FINAL",
    ]
)


def test_an_initial_literal_continued_mid_word_is_rejoined():
    literal = fields(CBSA)[2]
    assert literal["initial"] == "Please provide the requested information and press Enter."
    assert (literal["pos_line"], literal["pos_column"], literal["length"]) == (3, 1, 57)
    assert literal["attributes"] == "COLOR=TURQUOISE"
    # A literal's own trailing blank survives; it is inside the quotes.
    assert by_name(fields(CBSA))["COMPANY"]["initial"] == "CICS Bank Sample Application- Create Account. "


def test_occurs_and_picout_have_their_own_columns():
    items = by_name(fields(CBSA))
    assert (items["ACCOUNT"]["occurs"], items["ACCOUNT"]["length"]) == (10, 79)
    assert items["INTRT"]["picout"] == "9999.99"
    assert items["INTRT"]["attributes"] == "COLOR=GREEN,HILIGHT=UNDERLINE"


def test_a_banner_comment_between_statements_is_not_a_continuation():
    """A `*` banner (blanked by PRISM) sits between two fields; the second field
    must still start a statement of its own."""
    src = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams(CBSA, "bms")["code_stream"]
    assert [r["name"] for r in fields(src) if r["kind"] == "field"] == [None, "COMPANY", "ACCOUNT", "INTRT", None]


# language-crucible data/bms/cbsa/ssmap.bms: `X` continuation, JUSTIFY=(RIGHT,ZERO),
# zero-padded POS, a one-line field with its INITIAL on the same line.
SSMAP = "\n".join(
    [
        _line("SSMAP   DFHMSD TYPE=MAP,MODE=INOUT,LANG=COBOL,STORAGE=AUTO,", "X"),
        "               TIOAPFX=YES,EXTATT=MAPONLY,CTRL=(FREEKB)",
        "SSMAPC1 DFHMDI SIZE=(24,80)",
        "        DFHMDF POS=(1,1),LENGTH=4,ATTRB=(ASKIP,BRT),INITIAL='SSC1'",
        _line("ENT1CNO DFHMDF POS=(04,50),LENGTH=10,ATTRB=(NORM,UNPROT,IC,FSET),", "*"),
        "               JUSTIFY=(RIGHT,ZERO)",
    ]
)


def test_x_continuation_and_parenthesised_operands():
    rows = fields(SSMAP)
    assert (
        rows[0]["attributes"] == "TYPE=MAP,MODE=INOUT,LANG=COBOL,STORAGE=AUTO,TIOAPFX=YES,EXTATT=MAPONLY,CTRL=(FREEKB)"
    )
    assert rows[2]["initial"] == "SSC1"
    cno = rows[3]
    assert (cno["name"], cno["pos_line"], cno["pos_column"], cno["attributes"]) == (
        "ENT1CNO",
        4,
        50,
        "JUSTIFY=(RIGHT,ZERO)",
    )


def test_remarks_after_the_operands_are_not_operands():
    """An operand field ends at the first blank outside quotes; the rest of the
    line, and any continuation line after an operand without a trailing comma,
    is positional remarks."""
    src = "\n".join(
        [
            "MAP1     DFHMDI SIZE=(24,80)",
            _line("NAME     DFHMDF POS=(2,5),LENGTH=8    THE CUSTOMER NAME, UPPER CASE", "*"),
            "               MORE REMARKS=NOT OPERANDS",
        ]
    )
    row = fields(src)[1]
    assert (row["name"], row["pos_line"], row["length"], row["attributes"]) == ("NAME", 2, 8, None)


def test_quotes_and_ampersands_in_a_literal_are_unescaped():
    src = "\n".join(
        [
            "MAP1     DFHMDI SIZE=(24,80)",
            "         DFHMDF POS=(1,1),LENGTH=12,INITIAL='IT''S A&&B, X'",
        ]
    )
    assert fields(src)[1]["initial"] == "IT'S A&B, X"


def test_sequence_columns_73_to_80_are_never_read():
    src = "\n".join(
        [
            f"{'MAP1     DFHMDI SIZE=(24,80)':<72}00000100",
            f"{'NAME     DFHMDF POS=(2,5),LENGTH=8,ATTRB=UNPROT':<72}00000200",
        ]
    )
    row = fields(src)[1]
    assert (row["attrb"], row["attributes"]) == ("UNPROT", None)


def test_a_scalar_pos_is_kept_as_written():
    src = "MAP1     DFHMDI SIZE=(24,80)\nNAME     DFHMDF POS=165,LENGTH=8"
    row = fields(src)[1]
    assert (row["pos_line"], row["pos_column"], row["attributes"]) == (None, None, "POS=165")


def test_a_commented_out_field_produces_no_fact():
    src = "\n".join(
        [
            "MAP1     DFHMDI SIZE=(24,80)",
            "*OLDFLD  DFHMDF POS=(2,5),LENGTH=8",
            ".*TMPFLD DFHMDF POS=(3,5),LENGTH=8",
            "LIVE     DFHMDF POS=(4,5),LENGTH=8",
        ]
    )
    code = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams(src, "bms")["code_stream"]
    assert [r["name"] for r in fields(code)] == ["MAP1", "LIVE"]


def test_other_statements_and_their_continuations_are_skipped():
    src = "\n".join(
        [
            "         PRINT NOGEN",
            _line("         COPY  FIELDS1", "X"),
            "               NOT A DFHMDF STATEMENT",
            "MAP1     DFHMDI SIZE=(24,80)",
            "&LABEL   DFHMDF POS=(1,1),LENGTH=1",
            "         END",
        ]
    )
    assert [(r["kind"], r["name"]) for r in fields(src)] == [("map", "MAP1")]


def test_a_field_before_any_map_is_a_partial_tree_not_an_error():
    rows = fields("SET1     DFHMSD TYPE=MAP\n         DFHMDF POS=(1,1),LENGTH=3")
    assert [(r["kind"], r["parent_ordinal"]) for r in rows] == [("mapset", None), ("field", 0)]


def test_a_runaway_continuation_is_bounded():
    """Column 72 set on every line: the statement stops after its bound rather
    than swallowing the whole file."""
    src = "\n".join([_line("MAP1     DFHMDI SIZE=(24,80),", "X")] + [_line("               A=1,", "X")] * 400)
    rows = bms_screen_fields(src)
    assert len(rows) == 1
    assert rows[0]["attributes"].count("A=1") == 200


def test_the_dialect_dispatches_and_other_channels_are_empty():
    out = extract_boundary("bms", CARDDEMO)
    assert (out["calls"], out["datasets"], out["records"], out["transactions"]) == ([], [], [], [])
    assert len(out["screen_fields"]) == 5
    assert "bms" in BOUNDARY_DIALECTS
    assert "screen_fields" not in extract_boundary("cobol", "       IDENTIFICATION DIVISION.")


def test_the_declaration_is_top_level_not_a_rule():
    """#2806: a `rules` string is re.compile()d by language_lens and would extract nothing."""
    bms = LANGUAGE_DEFINITIONS["bms"]
    assert bms["boundary_extraction"] == "bms"
    assert "boundary_extraction" not in bms["rules"]


def test_every_pattern_is_bounded():
    """ReDoS discipline: the per-statement patterns carry explicit repetition bounds."""
    for pat in (_NAME, _OPERATION, _KEYWORD, _POS_PAIR, _INTEGER):
        assert isinstance(pat, re.Pattern)
    long_line = "A" * 20000 + " DFHMDF POS=(" + "9" * 20000
    assert bms_screen_fields(long_line) == []
