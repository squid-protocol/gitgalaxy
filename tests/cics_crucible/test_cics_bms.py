"""#4001: the harness's BMS model (tests/tools/cics_bms.py) -- what BMS sends for a SEND MAP and
what RECEIVE MAP delivers -- pinned rule by rule, with no GnuCOBOL or JDK."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cics_bms as bms  # noqa: E402

E = bms.EBCDIC


def _card(text: str, more: bool = False) -> str:
    """One assembler card: a continued statement has a non-blank column 72."""
    return (text.ljust(71) + "X" if more else text) + "\n"


BMS = "".join(
    [
        "* a test mapset\n",
        _card("TSET     DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL,STORAGE=AUTO,", True),
        _card("               TIOAPFX=YES,COLOR=PINK,DSATTS=(COLOR,HILIGHT)"),
        _card("TMAP     DFHMDI SIZE=(24,80),LINE=1,COLUMN=1,HILIGHT=REVERSE"),
        _card("         DFHMDF POS=(1,1),LENGTH=5,ATTRB=(ASKIP,BRT),INITIAL='TITLE'"),
        _card("NAME     DFHMDF POS=(2,1),LENGTH=6,ATTRB=(UNPROT,NORM,IC),COLOR=GREEN,", True),
        _card("               JUSTIFY=(LEFT,BLANK)"),
        _card("AMT      DFHMDF POS=(3,1),LENGTH=5,ATTRB=(UNPROT,NUM),", True),
        _card("               INITIAL='00,00'"),
        _card("NOTE     DFHMDF POS=(4,1),LENGTH=8,INITIAL='IT''S, OK'"),
        _card("         DFHMSD TYPE=FINAL"),
        _card("         END"),
    ]
)


def _map() -> bms.BmsMap:
    return bms.parse_bms(BMS)["TMAP"]


def test_the_bms_source_is_read_with_continuations_quotes_and_defaults():
    m = _map()
    assert (m.mapset, sorted(m.dsatts), m.mapset_color, m.hilight) == ("TSET", ["COLOR", "HILIGHT"], "PINK", "REVERSE")
    assert [f.name for f in m.fields] == [None, "NAME", "AMT", "NOTE"]
    name, amt, note = m.named()
    assert (name.length, name.attrb, name.color, name.justify, name.ic) == (6, ["UNPROT", "NORM", "IC"], "GREEN",
                                                                             ["LEFT", "BLANK"], True)  # fmt: skip
    assert (amt.initial, amt.numeric) == ("00,00", True)
    assert (note.initial, note.attrb) == ("IT'S, OK", None)


def test_attribute_bytes_follow_the_3270_graphic_encoding():
    # SPEC 6.3 / GA23-0059: omitted ATTRB is (ASKIP,NORM); no protection given means unprotected
    cases = {("ASKIP", "NORM"): 0xF0, ("ASKIP", "BRT"): 0xF8, ("ASKIP", "DRK", "FSET"): 0x7D,
             ("UNPROT", "NORM"): 0x40, ("UNPROT", "NORM", "FSET"): 0xC1, ("UNPROT", "BRT"): 0xC8,
             ("UNPROT", "DRK"): 0x4C, ("UNPROT", "NUM", "NORM"): 0x50, ("UNPROT", "NUM", "BRT", "FSET"): 0xD9,
             ("PROT", "NORM"): 0x60, ("PROT", "BRT"): 0xE8, ("PROT", "DRK"): 0x6C, ("PROT", "NUM", "BRT"): 0xF8,
             ("UNPROT", "DET"): 0xC4, ("FSET",): 0xC1, ("NUM",): 0x50}  # fmt: skip
    for attrb, want in cases.items():
        assert bms.attr_byte(list(attrb)) == want, attrb
    assert bms.attr_byte(None) == 0xF0


def test_send_map_takes_each_value_from_the_program_or_the_map():
    m = _map()
    prog = {
        "NAME": bms.ProgramField(attr=0x4D, data="ADA   ".encode(E), color=0xF2),
        "AMT": bms.ProgramField(attr=0x80, data=b"\x00" + "1234".encode(E)),  # an input flag; a null first byte
        "NOTE": bms.ProgramField(attr=0x00, data=b"\x00" * 8, hilight=0x00),
    }
    fields, cursor = bms.send_map(m, prog, ["ERASE"])
    assert fields["NAME"] == {"attr": "4D", "attr_from": "program", "data": "ADA   ".encode(E), "data_from": "program",
                              "color": "F2", "color_from": "program", "hilight": "F2", "hilight_from": "map"}  # fmt: skip
    # X'80' is never an attribute; a null first byte leaves the map's INITIAL; colour from the mapset
    assert fields["AMT"] == {"attr": "50", "attr_from": "map", "data": "00,00".encode(E), "data_from": "map",
                             "color": "F3", "color_from": "map", "hilight": "F2", "hilight_from": "map"}  # fmt: skip
    assert fields["NOTE"]["attr"] == "F0" and fields["NOTE"]["data"] == "IT'S, OK".encode(E)
    assert cursor == "NAME"  # IC


def test_mapsonly_sends_the_map_alone():
    fields, cursor = bms.send_map(_map(), None, ["ERASE", "MAPONLY"])
    assert fields["NAME"] == {"attr": "40", "attr_from": "map", "data": None, "data_from": "none",
                              "color": "F4", "color_from": "map", "hilight": "F2", "hilight_from": "map"}  # fmt: skip
    assert cursor == "NAME"


def test_dataonly_sends_program_values_only_and_omits_the_rest():
    m = _map()
    prog = {
        "NAME": bms.ProgramField(length=-1, data="ADA".encode(E)),
        "AMT": bms.ProgramField(attr=0xC1),
        "NOTE": bms.ProgramField(attr=0x82, data=b"\x00" * 8),  # nothing BMS would send
    }
    fields, cursor = bms.send_map(m, prog, ["DATAONLY"])
    assert set(fields) == {"NAME", "AMT"}
    assert fields["NAME"] == {"attr": None, "attr_from": "none", "data": "ADA".encode(E), "data_from": "program",
                              "color": None, "color_from": "none", "hilight": None, "hilight_from": "none"}  # fmt: skip
    assert (fields["AMT"]["attr"], fields["AMT"]["data"]) == ("C1", None)
    assert cursor is None  # no CURSOR, and DATAONLY sends no IC
    assert bms.send_map(m, prog, ["CURSOR", "DATAONLY"])[1] == "NAME"  # symbolic: the length is -1
    assert bms.send_map(m, prog, ["CURSOR", "DATAONLY"], 85)[1] == {"offset": 85}  # CURSOR(85)


def test_receive_map_justifies_what_the_terminal_sent():
    name, amt, note = _map().named()
    assert bms.received_value(name, "ADA") == "ADA   "
    assert bms.received_value(amt, "12") == "00012"  # NUM: right-justified, zero-filled
    assert bms.received_value(note, "LONGER THAN EIGHT") == "LONGER T"
