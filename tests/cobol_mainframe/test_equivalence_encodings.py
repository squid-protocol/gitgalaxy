"""#3815: the equivalence harness reads sources and records in a declared encoding.

It assumed Latin-1 everywhere: a UTF-8 source's national names were staged as mojibake-in-waiting,
and an EBCDIC record's text and zoned fields were read as Latin-1 garbage. Pinned without Docker:
the harness's own read / encode / decode / compare functions, the default path byte-identical.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq  # noqa: E402
import equivalence_cics as ec  # noqa: E402
import equivalence_common as common  # noqa: E402
import equivalence_inputs as ei  # noqa: E402
import equivalence_java as ej  # noqa: E402

NATIONAL_SOURCE = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. BELOP.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  BELØP      PIC S9(7)V99.\n"
    "       01  नाम        PIC X(30).\n"
)
# a Danish / Norwegian record: name X(6), amount S9(3) zoned (overpunched), balance S9(5) COMP-3
RECORD = [
    {"name": "NAVN", "offset": 0, "bytes": 6, "pic": "X(06)", "usage": None},
    {"name": "BELOP", "offset": 6, "bytes": 3, "pic": "S9(03)", "usage": None},
    {"name": "SALDO", "offset": 9, "bytes": 3, "pic": "S9(05)", "usage": "COMP-3"},
]


def _record(values, enc, code_page="cp277"):
    return b"".join(
        ei.encode_field(values[f["name"]], f["pic"], f["usage"], f["bytes"], code_page, enc) for f in RECORD
    )


# ---- sources ----------------------------------------------------------------------------
def test_a_utf8_source_is_read_losslessly_and_staged_as_the_same_bytes(tmp_path):
    path = tmp_path / "BELOP.cbl"
    path.write_bytes(NATIONAL_SOURCE.encode("utf-8"))
    text, staged = common.read_program({}, path)
    assert "BELØP" in text and "नाम" in text  # the names, not Latin-1 mojibake (BELÃ\x98P)
    assert staged == "utf-8"
    assert text.encode(staged) == path.read_bytes()  # GnuCOBOL gets the very bytes


def test_a_latin1_source_is_staged_byte_identical_to_before(tmp_path):
    path = tmp_path / "OLD.cbl"
    raw = "       01  BELØP  PIC X VALUE 'Å'.\r\n       01  X\x81   PIC X.\n".encode("latin-1")  # 0x81: no cp1252
    path.write_bytes(raw)
    text, staged = common.read_program({}, path)
    before = path.read_text(encoding="latin-1")  # the harness's read before #3815 (universal newlines too)
    assert text == before
    assert text.encode(staged) == before.encode("latin-1")


def test_a_declared_ebcdic_source_is_decoded_and_staged_for_gnucobol(tmp_path):
    path = tmp_path / "EBC.cbl"
    path.write_bytes("       01  BELØP  PIC X.\n".encode("cp277"))
    text, staged = common.read_program({"source_encoding": "cp277"}, path)
    assert "BELØP" in text
    assert staged == "utf-8"  # GnuCOBOL reads ASCII-family bytes, never EBCDIC
    with pytest.raises(ValueError, match="source_encoding"):
        common.read_program({"source_encoding": "no-such-page"}, path)


# ---- records ----------------------------------------------------------------------------
@pytest.mark.parametrize("amount", [Decimal(0), Decimal(5), Decimal(-5), Decimal(-120), Decimal(999)])
def test_a_cp277_record_round_trips_through_encode_and_decode(amount):
    rec = _record({"NAVN": "æøå", "BELOP": amount, "SALDO": Decimal(-42)}, "cp277")
    assert rec[:6] == "æøå".encode("cp277") + b"\x40\x40\x40"  # padded with the EBCDIC space, not 0x20
    if amount == 0:
        assert rec[8:9] == b"\xc0"  # +0 overpunched: cp277's æ, the zoned byte a mainframe writes
    for f in RECORD:
        raw = rec[f["offset"] : f["offset"] + f["bytes"]]
        got = common.decode_field(raw, f["pic"], f["usage"], "cp277", data_encoding="cp277")
        want = {"NAVN": "æøå   ", "BELOP": amount, "SALDO": Decimal(-42)}[f["name"]]
        assert got == want
    # read as Latin-1 (the old assumption) the same bytes are neither the name nor a number
    assert common.decode_field(rec[:6], "X(06)", None) != "æøå   "
    assert str(common.decode_field(rec[6:9], "S9(03)", None, "cp277")).startswith("<invalid")


def test_cics_areas_encode_and_decode_in_the_declared_page():
    rec = ec.encode_record(RECORD, {"NAVN": "Åse", "BELOP": -7}, b"init", "cp277")
    assert rec[:6] == "Åse".encode("cp277") + b"\x40" * 3
    assert ec.decode_record(rec, RECORD, "cp277") == {"NAVN": "Åse", "BELOP": "-7", "SALDO": "0"}
    typed = ec.map_input([{"name": "NAVNI", "offset": 0, "bytes": 6, "pic": "X(06)", "usage": None},
                          {"name": "NAVNL", "offset": 6, "bytes": 2, "pic": "S9(04)", "usage": "COMP"}],
                         {"NAVNI": "Øyvind"}, "cp277")  # fmt: skip
    assert typed[:6] == "Øyvind".encode("cp277")
    # the zoned zero signs are the page's own bytes, 0xC0 / 0xD0 (cp037's `{` / `}` are elsewhere in cp277)
    zero = ec.encode_record(RECORD, {"BELOP": 10}, b"init", "cp277")[6:9]
    assert zero == b"\xf0\xf1\xc0" and ec.encode_record(RECORD, {"BELOP": -10}, b"init", "cp277")[8:9] == b"\xd0"
    assert (
        ec.decode_record(ec.encode_record(RECORD, {"BELOP": -10}, b"init", "cp277"), RECORD, "cp277")["BELOP"] == "-10"
    )
    assert ec.encode_record(RECORD, {"BELOP": -10}, b"init")[6:9] == b"01}"  # the default: as before


def test_utf8_text_is_cut_at_a_whole_character_and_nothing_unencodable_is_dropped():
    assert common.text_bytes("नाम", 4, "utf-8") == "न".encode("utf-8") + b" "  # never half a letter
    assert common.decode_field(common.text_bytes("नाम", 4, "utf-8"), "X(04)", None, data_encoding="utf-8") == "न "
    half = "न".encode("utf-8")[:2]
    assert common.decode_field(half, "X(02)", None, data_encoding="utf-8").startswith("<undecodable")
    with pytest.raises(UnicodeEncodeError):
        common.text_bytes("नाम", 6, "cp277")


def test_generated_inputs_use_the_page_and_the_default_is_unchanged():
    spec = {"reclen": 14, "generate": {"records": 12, "seed": 3, "alphabet": "mixed"}}
    before, _ = ei.generate_dataset("DD", spec, RECORD, {})
    assert before == ei.generate_dataset("DD", spec, RECORD, {}, "cp037", "latin-1")[0]
    ebcdic, values = ei.generate_dataset("DD", spec, RECORD, {}, "cp277", "cp277")
    recs = [ebcdic[i : i + 14] for i in range(0, len(ebcdic), 14)]
    assert all(r[12:] == b"\x40\x40" for r in recs)  # the unused tail is EBCDIC blanks
    for rec, name, amount in zip(
        recs, values["DD.NAVN"], values["DD.BELOP"], strict=False
    ):  # reason: length may differ
        assert common.decode_field(rec[:6], "X(06)", None, data_encoding="cp277").rstrip() == name.rstrip()
        assert common.decode_field(rec[6:9], "S9(03)", None, "cp277", data_encoding="cp277") == amount


# ---- the default path: byte-identical to before #3815 -----------------------------------
@pytest.mark.parametrize("value,pic,code_page", [
    ("ABC", "X(05)", "cp037"), ("SØREN-ÅSE", "X(06)", "cp037"), ("", "X(03)", "cp037"),
    (Decimal("-12.30"), "S9(3)V99", "cp037"), (Decimal(40), "S9(3)", "cp273"), (Decimal(7), "9(3)", "cp037"),
])  # fmt: skip
def test_the_default_encode_and_decode_are_what_they_were(value, pic, code_page):
    n = 6 if pic.startswith("X") else 5 if "V" in pic else 3
    got = ei.encode_field(value, pic, None, n, code_page)
    if common._pic_numeric(pic) is None:
        assert got == str(value).encode("latin-1")[:n].ljust(n, b" ")
    else:  # the zoned digits as Latin-1 text with the page's overpunch, as before
        pos, neg = common.zoned_sign_characters(code_page)
        digits = f"{abs(int(value * 10 ** common._pic_numeric(pic)[2])):0{n}d}"
        if pic.startswith("S"):
            digits = digits[:-1] + (neg if value < 0 else pos)[int(digits[-1])]
        assert got == digits.encode("latin-1")
    assert common.decode_field(got, pic, None, code_page) == (value if not isinstance(value, str)
                                                               else got.decode("latin-1"))  # fmt: skip


def test_the_default_fixed_input_and_java_charset_are_what_they_were(tmp_path):
    src = tmp_path / "data.txt"
    src.write_bytes(b"ABC\r\nS\xd8REN\n\nTOO-LONG-LINE\n")
    old = bytearray()
    for line in src.read_bytes().split(b"\n"):
        line = line.rstrip(b"\r")
        if line:
            old += line[:8].ljust(8, b" ")
    assert common._fixed(src, 8) == bytes(old)
    assert common.java_charset() == "StandardCharsets.ISO_8859_1"
    case = {"name": "x", "program": "PGM", "clock": "2024/01/01 00:00:00.00", "datasets": {}}
    assert "static final Charset TEXT = StandardCharsets.ISO_8859_1;" in ej.equivalence_test(case)
    assert 'Charset.forName("IBM277")' in ej.equivalence_test({**case, "data_encoding": "cp277"})
    assert common.java_charset("utf-8") == 'Charset.forName("UTF-8")'
    assert common.java_charset("cp1140") == 'Charset.forName("IBM01140")'
    assert common.java_charset("cp1252") == 'Charset.forName("windows-1252")'


def test_an_ebcdic_corpus_file_is_cut_into_records_in_its_page(tmp_path):
    lines = tmp_path / "nel.dat"
    lines.write_bytes("ÆØÅ".encode("cp277") + b"\x15" + "AB".encode("cp277") + b"\x15")
    assert common._fixed(lines, 4, "cp277") == "ÆØÅ ".encode("cp277") + "AB  ".encode("cp277")
    block = tmp_path / "fb.dat"
    block.write_bytes("ÆØÅXAB12".encode("cp277"))  # a fixed-block download: no line ends at all
    assert common._fixed(block, 4, "cp277") == "ÆØÅXAB12".encode("cp277")


# ---- the comparison ---------------------------------------------------------------------
def test_outputs_differing_only_in_encoding_compare_equal_in_their_declared_pages():
    values = {"NAVN": "Søren", "BELOP": Decimal(-3), "SALDO": Decimal(17)}
    cobol, java = _record(values, "cp277"), _record(values, "latin-1")
    assert cobol != java  # the same text, in two pages
    d = eq.diff_records(cobol, java, 12, RECORD, "cp277", "cp277", right_encoding="latin-1")
    assert (d["equal"], d["records"], d["diffs"]) == (1, 1, [])
    # both sides declared cp277: equal; one real difference is still found
    assert eq.diff_records(cobol, cobol, 12, RECORD, "cp277", "cp277")["equal"] == 1
    other = _record({**values, "NAVN": "Sören"}, "latin-1")
    d = eq.diff_records(cobol, other, 12, RECORD, "cp277", "cp277", right_encoding="latin-1")
    assert d["diffs"][0]["fields"] == [{"field": "NAVN", "cobol": "Søren ", "java": "Sören "}]
    # a binary field's bytes are the same in any page: a C vs F sign nibble is still a byte difference
    unsigned = java[:9] + bytes.fromhex("00017f")
    d = eq.diff_records(cobol, unsigned, 12, RECORD, "cp277", "cp277", right_encoding="latin-1")
    assert d["diffs"][0]["fields"][0]["field"] == "SALDO"


def test_encoding_declarations_are_checked():
    assert common.data_encoding({}) == "latin-1"
    assert common.data_encoding({"data_encoding": "ibm277"}) == "ibm277"
    with pytest.raises(ValueError, match="one byte"):
        common.data_encoding({"data_encoding": "utf-16"})
    with pytest.raises(ValueError, match="not a known"):
        common.data_encoding({"data_encoding": "cp9999"})
    common.require_ascii_runtime({"data_encoding": "utf-8"})
    with pytest.raises(common.UnsupportedOption, match="cp277"):
        common.require_ascii_runtime({"data_encoding": "cp277"})
