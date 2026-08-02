import sys
import json
import csv
from unittest.mock import patch

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
    Proves that IBM Packed Decimal bytes are correctly parsed into Python floats,
    verifying nibble sign flags (C/F=Positive, D=Negative) and decimal shifts.
    """
    # 123C -> Positive 123 (0 decimals)
    assert etl_module.unpack_comp3(b"\x12\x3c", 0) == 123.0

    # 123D -> Negative 123 (0 decimals)
    assert etl_module.unpack_comp3(b"\x12\x3d", 0) == -123.0

    # 0123456C -> Positive 123456 (2 decimals) -> 1234.56
    assert etl_module.unpack_comp3(b"\x01\x23\x45\x6c", 2) == 1234.56

    # 0001234D -> Negative 1234 (2 decimals) -> -12.34
    assert etl_module.unpack_comp3(b"\x00\x01\x23\x4d", 2) == -12.34

    # 123F -> Unsigned (Positive) 123 (0 decimals)
    assert etl_module.unpack_comp3(b"\x12\x3f", 0) == 123.0


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

    with open(csv_out, "r", encoding="utf-8") as f:
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
