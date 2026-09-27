from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.tools.cobol_to_cobol.cobol_schema_forge import parse_cobol_picture
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import EngineDataItem, _elementary_bytes


def test_dbcs_usages_and_widths():
    src = """
       01 R.
          05 A PIC N(5).
          05 B PIC G(4) DISPLAY-1.
          05 C PIC N(3) USAGE NATIONAL.
          05 D PIC X(2).
"""
    records = extract_boundary("cobol", src)["records"]
    assert records[1]["usage"] == "NATIONAL"  # A
    assert records[2]["usage"] == "DISPLAY-1"  # B
    assert records[3]["usage"] == "NATIONAL"  # C
    assert records[4]["usage"] is None  # D

    # Check widths using EngineDataItem
    a_width = _elementary_bytes(
        EngineDataItem(
            pic=records[1]["pic"],
            usage=records[1]["usage"],
            name="A",
            level=5,
            occurs_max=None,
            line=0,
            ordinal=0,
            parent_ordinal=None,
            redefines=None,
            value=None,
            attributes=None,
            section=None,
            fd_name=None,
            occurs_min=None,
            occurs_depending_on=None,
        )
    )
    assert a_width == 10

    b_width = _elementary_bytes(
        EngineDataItem(
            pic=records[2]["pic"],
            usage=records[2]["usage"],
            name="B",
            level=5,
            occurs_max=None,
            line=0,
            ordinal=0,
            parent_ordinal=None,
            redefines=None,
            value=None,
            attributes=None,
            section=None,
            fd_name=None,
            occurs_min=None,
            occurs_depending_on=None,
        )
    )
    assert b_width == 8

    c_width = _elementary_bytes(
        EngineDataItem(
            pic=records[3]["pic"],
            usage=records[3]["usage"],
            name="C",
            level=5,
            occurs_max=None,
            line=0,
            ordinal=0,
            parent_ordinal=None,
            redefines=None,
            value=None,
            attributes=None,
            section=None,
            fd_name=None,
            occurs_min=None,
            occurs_depending_on=None,
        )
    )
    assert c_width == 6

    d_width = _elementary_bytes(
        EngineDataItem(
            pic=records[4]["pic"],
            usage=records[4]["usage"],
            name="D",
            level=5,
            occurs_max=None,
            line=0,
            ordinal=0,
            parent_ordinal=None,
            redefines=None,
            value=None,
            attributes=None,
            section=None,
            fd_name=None,
            occurs_min=None,
            occurs_depending_on=None,
        )
    )
    assert d_width == 2


def test_nsymbol_dbcs():
    src = """
CBL NSYMBOL(DBCS)
       01 R.
          05 A PIC N(5).
"""
    records = extract_boundary("cobol", src)["records"]
    assert records[1]["usage"] == "DISPLAY-1"
    width = _elementary_bytes(
        EngineDataItem(
            pic=records[1]["pic"],
            usage=records[1]["usage"],
            name="A",
            level=5,
            occurs_max=None,
            line=0,
            ordinal=0,
            parent_ordinal=None,
            redefines=None,
            value=None,
            attributes=None,
            section=None,
            fd_name=None,
            occurs_min=None,
            occurs_depending_on=None,
        )
    )
    assert width == 10


def test_pic_9_national():
    src = """
       01 R.
          05 N PIC 9(4) USAGE NATIONAL.
"""
    records = extract_boundary("cobol", src)["records"]
    assert records[1]["usage"] == "NATIONAL"
    width = _elementary_bytes(
        EngineDataItem(
            pic=records[1]["pic"],
            usage=records[1]["usage"],
            name="N",
            level=5,
            occurs_max=None,
            line=0,
            ordinal=0,
            parent_ordinal=None,
            redefines=None,
            value=None,
            attributes=None,
            section=None,
            fd_name=None,
            occurs_min=None,
            occurs_depending_on=None,
        )
    )
    assert width == 8


def test_group_national():
    src = """
       01 R USAGE NATIONAL.
          05 A PIC 9(2).
          05 B PIC X(3).
"""
    records = extract_boundary("cobol", src)["records"]
    assert records[1]["usage"] == "NATIONAL"
    assert records[2]["usage"] == "NATIONAL"
    width = _elementary_bytes(
        EngineDataItem(
            pic=records[2]["pic"],
            usage=records[2]["usage"],
            name="B",
            level=5,
            occurs_max=None,
            line=0,
            ordinal=0,
            parent_ordinal=None,
            redefines=None,
            value=None,
            attributes=None,
            section=None,
            fd_name=None,
            occurs_min=None,
            occurs_depending_on=None,
        )
    )
    assert width == 6


def test_schema_types():
    assert parse_cobol_picture("N(5)", False, "NATIONAL")["sql"] == "NVARCHAR(5)"
    assert parse_cobol_picture("X(10)", False, "NATIONAL")["sql"] == "NVARCHAR(10)"
    assert parse_cobol_picture("9(4)", False, "NATIONAL")["sql"] != "NVARCHAR(4)"  # a national number stays numeric
    assert parse_cobol_picture("X(10)", False, None)["sql"] == "VARCHAR(10)"


def test_other_group_usages_are_not_pushed_onto_members():
    """#3816 scope: only NATIONAL / DISPLAY-1 groups pass their usage down; a COMP-3 group's members are unchanged."""
    src = """
       01 R COMP-3.
          05 A PIC S9(5).
"""
    records = extract_boundary("cobol", src)["records"]
    assert records[1]["usage"] is None


def test_national_in_a_value_literal_is_not_a_usage():
    """#3816: NIST CCVS85's `VALUE "... NATIONAL INSTITUTE OF STD & TECH."` must not make a PIC X NATIONAL."""
    src = """
       01 R.
          02 FILLER PIC X(58) VALUE
            "ON-SITE VALIDATION, NATIONAL INSTITUTE OF STD & TECH.     ".
          02 N1 PIC X(4) USAGE NATIONAL.
"""
    records = extract_boundary("cobol", src)["records"]
    assert records[1]["usage"] is None
    assert records[2]["usage"] == "NATIONAL"


def test_a_malformed_picture_with_a_g_is_not_dbcs():
    """#3816: GnuCOBOL's sqlda.cpy has `PIC USAGE BINARY-SHORT` -- the captured "picture" USAGE is not PIC G."""
    src = """
       01 R.
          07 SQLNAMEL PIC USAGE BINARY-SHORT.
          07 E PIC NNBNN.
          07 X PIC X(4).
"""
    usages = [r["usage"] for r in extract_boundary("cobol", src)["records"][1:]]
    assert usages == [None, "NATIONAL", None]
