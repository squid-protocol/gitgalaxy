import csv
import json
import sys
from decimal import Decimal
from unittest.mock import patch

import pytest

# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.tools.cobol_to_cobol.cobol_etl_unpacker as etl_module


# ==============================================================================
# TEST 1: The Schema Byte Calculator
# ==============================================================================
def test_calculate_byte_layout():
    """
    Proves the engine accurately parses PIC clauses from the JSON schema
    to calculate physical byte boundaries, especially COMP-3 compression math.
    """
    mock_schema = {
        "properties": {
            "FIRST_NAME": {"description": "Legacy PIC: X(10)"},  # 10 bytes text
            "AGE": {"description": "Legacy PIC: 999"},  # 3 bytes numeric (zoned)
            "BALANCE": {"description": "Legacy PIC: 9(5)V9(2) COMP-3"},  # 7 digits COMP-3 = 4 bytes
            "DEBT": {"description": "Legacy PIC: 9(4)V99 COMP-3"},  # 6 digits COMP-3 = 4 bytes
        }
    }

    layout = etl_module.calculate_byte_layout(mock_schema)

    assert len(layout) == 4

    # 1. Text Field (X)
    assert layout[0]["name"] == "FIRST_NAME"
    assert layout[0]["bytes"] == 10

    # 2. Zoned Decimal Field (9)
    assert layout[1]["name"] == "AGE"
    assert layout[1]["bytes"] == 3
    assert layout[1]["is_numeric"] is True
    assert layout[1]["is_comp3"] is False

    # 3. Packed Decimal COMP-3 Math: ceil((7 + 1) / 2) = 4
    assert layout[2]["name"] == "BALANCE"
    assert layout[2]["bytes"] == 4
    assert layout[2]["decimals"] == 2
    assert layout[2]["is_comp3"] is True

    # 4. Packed Decimal COMP-3 Math: ceil((6 + 1) / 2) = 4
    assert layout[3]["name"] == "DEBT"
    assert layout[3]["bytes"] == 4


# ==============================================================================
# TEST 2: The COMP-3 Hexadecimal Decoder
# ==============================================================================
def test_unpack_comp3():
    """
    Proves that IBM Packed Decimal bytes are correctly parsed into exact Decimals (#3833: not floats),
    verifying nibble sign flags (C/F=Positive, D=Negative) and decimal shifts.
    """
    # 123C -> Positive 123 (0 decimals)
    assert etl_module.unpack_comp3(b"\x12\x3c", 0) == Decimal("123")

    # 123D -> Negative 123 (0 decimals)
    assert etl_module.unpack_comp3(b"\x12\x3d", 0) == Decimal("-123")

    # 0123456C -> Positive 123456 (2 decimals) -> 1234.56
    assert etl_module.unpack_comp3(b"\x01\x23\x45\x6c", 2) == Decimal("1234.56")

    # 0001234D -> Negative 1234 (2 decimals) -> -12.34
    assert etl_module.unpack_comp3(b"\x00\x01\x23\x4d", 2) == Decimal("-12.34")

    # 123F -> Unsigned (Positive) 123 (0 decimals)
    assert etl_module.unpack_comp3(b"\x12\x3f", 0) == Decimal("123")


# ==============================================================================
# TEST 3: The E2E Binary Pipeline (EBCDIC -> CSV)
# ==============================================================================
def test_unpack_ebcdic_file_e2e(tmp_path):
    """
    Proves the system can ingest a raw binary file, chunk it perfectly according
    to the calculated layout, translate cp037 EBCDIC to UTF-8, and write a CSV.
    """
    work_dir = tmp_path / "etl_workspace"
    work_dir.mkdir()

    # 1. The Schema (Name: X(5), Balance: 9(5)V99 COMP-3) -> 5 + 4 = 9 bytes per record
    schema_file = work_dir / "account_schema.json"
    schema_file.write_text(
        json.dumps(
            {
                "properties": {
                    "NAME": {"description": "Legacy PIC: X(5)"},
                    "BALANCE": {"description": "Legacy PIC: 9(5)V99 COMP-3"},
                }
            }
        ),
        encoding="utf-8",
    )

    # 2. The Mock Binary Payload
    # Record 1: 'ALICE' in EBCDIC + 12345.67 in COMP-3
    r1_name = "ALICE".encode("cp037")  # 5 bytes
    r1_bal = b"\x01\x23\x45\x6c"  # 4 bytes (01 23 45 6C)

    # Record 2: 'BOB  ' in EBCDIC + -12.34 in COMP-3
    r2_name = "BOB  ".encode("cp037")  # 5 bytes
    r2_bal = b"\x00\x01\x23\x4d"  # 4 bytes (-00012.34)

    binary_file = work_dir / "MAINFRAME.DAT"
    binary_file.write_bytes(r1_name + r1_bal + r2_name + r2_bal)

    csv_out = work_dir / "output.csv"

    # 3. Execute the CLI
    test_args = [
        "cobol_etl_unpacker.py",
        str(binary_file),
        str(schema_file),
        "--out",
        str(csv_out),
    ]
    with patch.object(sys, "argv", test_args):
        # We don't trap SystemExit because a successful run exits normally
        etl_module.main()

    # 4. Verify CSV Output
    assert csv_out.exists(), "ETL Unpacker failed to generate the CSV!"

    with open(csv_out, encoding="utf-8") as f:
        reader = list(csv.reader(f))

        # Header
        assert reader[0] == ["NAME", "BALANCE"]

        # Record 1
        assert reader[1][0] == "ALICE"
        assert float(reader[1][1]) == 1234.56

        # Record 2
        assert reader[1][0] == "ALICE"  # Wait, let's check index 2 for BOB
        assert reader[2][0] == "BOB"
        assert float(reader[2][1]) == -12.34


# ==============================================================================
# #3833: any EBCDIC code page, Decimal not float, signed zoned, never a silent 0.0
# ==============================================================================
def _run(tmp_path, fields, data, *extra):
    """Unpacks `data` against a schema of {name: description} through the CLI; returns the CSV rows."""
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"properties": {n: {"description": d} for n, d in fields.items()}}), encoding="utf-8")
    binary = tmp_path / "DATA.DAT"
    binary.write_bytes(data)
    out = tmp_path / "out.csv"
    with patch.object(sys, "argv", ["cobol-etl-unpacker", str(binary), str(schema), "--out", str(out), *extra]):
        etl_module.main()
    with open(out, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def test_cp273_german_text_decodes(tmp_path):
    rows = _run(tmp_path, {"NAME": "Legacy PIC: X(8)"}, "MÜLLÄÖß ".encode("cp273"), "--code-page", "cp273")
    assert rows[1] == ["MÜLLÄÖß"]


def test_cp037_default_would_misread_the_german_file(tmp_path):
    """The same bytes under the old hard-coded cp037 are other letters: the page must be a parameter."""
    rows = _run(tmp_path, {"NAME": "Legacy PIC: X(4)"}, "ÄÖÜß".encode("cp273"))
    assert rows[1] != ["ÄÖÜß"]


def test_cp277_nordic_text_decodes(tmp_path):
    rows = _run(tmp_path, {"NAME": "Legacy PIC: X(6)"}, "ÆØÅæøå".encode("cp277"), "--code-page", "cp277")
    assert rows[1] == ["ÆØÅæøå"]


@pytest.mark.parametrize("code_page", ["cp037", "cp277", "cp273", "cp297"])
def test_signed_zoned_keeps_sign_and_scale(tmp_path, code_page):
    """S9(5)V99 -1234.50: digits 0123450 with the last byte overpunched negative-zero (X'D0')."""
    negative_zero = bytes([0xD0]).decode(code_page)  # cp037 '}', cp277 'å', cp273 'ü', cp297 'è'
    data = ("012345" + negative_zero).encode(code_page)
    assert data == bytes.fromhex("F0F1F2F3F4F5D0")
    rows = _run(tmp_path, {"AMOUNT": "Legacy PIC: S9(5)V99"}, data, "--code-page", code_page)
    assert rows[1] == ["-1234.50"]


def test_positive_overpunch_and_unsigned_zoned(tmp_path):
    fields = {"A": "Legacy PIC: S9(3)V99", "B": "Legacy PIC: 9(3)V99"}
    data = bytes.fromhex("F0F1F2F5C0") + bytes.fromhex("F0F0F0F1F0")  # +12.50 overpunched, unsigned 0.10
    rows = _run(tmp_path, fields, data)
    assert rows[1] == ["12.50", "0.10"]


def test_comp3_ten_cents_is_exact(tmp_path):
    """S9(7)V99 COMP-3 0.10 -> X'000000010C': exactly 0.10, not 0.1 or 0.09999999999999999."""
    rows = _run(tmp_path, {"AMT": "Legacy PIC: S9(7)V99 COMP-3"}, bytes.fromhex("000000010C"))
    assert rows[1] == ["0.10"]
    assert etl_module.unpack_comp3(bytes.fromhex("000000010C"), 2) == Decimal("0.10")


def test_comp3_negative_zero_and_tiny_values_have_no_exponent():
    assert etl_module.format_number(etl_module.unpack_comp3(bytes.fromhex("000000000D"), 2)) == "0.00"
    assert etl_module.format_number(etl_module.unpack_comp3(bytes.fromhex("1C"), 7)) == "0.0000001"


@pytest.mark.parametrize("raw", ["F1F2C1F3", "40404040", "F1F2F381"])
def test_corrupt_zoned_raises_never_zero(raw):
    """A sign mid-field, spaces, or a lowercase letter is not a zoned number (#3833)."""
    with pytest.raises(etl_module.UnpackError, match="not a valid zoned decimal"):
        etl_module.unpack_zoned(bytes.fromhex(raw), 2)


def test_corrupt_packed_raises_never_zero():
    with pytest.raises(etl_module.UnpackError, match="not a valid packed decimal"):
        etl_module.unpack_comp3(bytes.fromhex("1A3C"), 0)  # digit nibble A
    with pytest.raises(etl_module.UnpackError, match="not a valid packed decimal"):
        etl_module.unpack_comp3(bytes.fromhex("1234"), 0)  # sign nibble 4


def test_corrupt_record_stops_the_run_naming_record_and_field(tmp_path, capsys):
    """The old unpacker wrote 0.0 for the bad record; now the run fails loudly and leaves no CSV."""
    fields = {"NAME": "Legacy PIC: X(3)", "AMOUNT": "Legacy PIC: S9(3)V99"}
    good = "BOB".encode("cp037") + bytes.fromhex("F0F1F2F5C0")
    bad = "EVE".encode("cp037") + "12.50".encode("cp037")
    with pytest.raises(SystemExit) as exit_info:
        _run(tmp_path, fields, good + bad)
    assert exit_info.value.code == 1
    out = capsys.readouterr().out
    assert "record 2, field AMOUNT" in out
    assert not (tmp_path / "out.csv").exists()


def test_unpack_file_raises_for_bad_data(tmp_path):
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"properties": {"N": {"description": "Legacy PIC: 9(3)"}}}), encoding="utf-8")
    binary = tmp_path / "D.DAT"
    binary.write_bytes(bytes.fromhex("F1F2F3") + bytes.fromhex("F1C1F3"))  # a sign mid-field: garbage
    with pytest.raises(etl_module.UnpackError, match="record 2, field N"):
        etl_module.unpack_ebcdic_file(binary, schema, tmp_path / "o.csv")


@pytest.mark.parametrize("code_page, message", [("utf-8", "not an EBCDIC code page"), ("cp999", "not a known")])
def test_bad_code_page_is_rejected(tmp_path, capsys, code_page, message):
    with pytest.raises(SystemExit) as exit_info:
        _run(tmp_path, {"N": "Legacy PIC: 9(3)"}, bytes.fromhex("F1F2F3"), "--code-page", code_page)
    assert exit_info.value.code == 2
    assert message in capsys.readouterr().out


def test_a_never_filled_numeric_is_an_empty_cell_not_zero_nor_a_failure(tmp_path, capsys):
    """#3833: all EBCDIC spaces / low-values (an unfilled field) -> an empty cell, counted; garbage still fails."""
    fields = {"A": "Legacy PIC: S9(3)V99", "B": "Legacy PIC: S9(7)V99 COMP-3", "C": "Legacy PIC: 9(3)"}
    data = b"\x40" * 5 + b"\x00" * 5 + bytes.fromhex("F0F4F2")
    rows = _run(tmp_path, fields, data)
    assert rows[1] == ["", "", "42"]
    assert "2 numeric field(s) never filled" in capsys.readouterr().out
