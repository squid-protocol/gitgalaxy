"""#3820: currency signs in PICTURE strings, and the SPECIAL-NAMES that declare them.

Only `$` used to be read as a currency symbol. On CP285 (UK) the default currency
byte 0x5B decodes as `£`, so an ordinary `PIC $$$9.99` reads `PIC £££9.99`: the
engine saw no PIC at all and the item became a PIC-less group of unknown width;
`PIC 9(5)€` read as `9(5)`, one byte short, and every later field moved. A
multi-character currency string (`CURRENCY SIGN IS 'EUR ' WITH PICTURE SYMBOL
'U'`) was not read at all, so its symbol counted one byte instead of four.

The extractor now keeps the whole PIC as written and records the SPECIAL-NAMES
CURRENCY / DECIMAL-POINT clauses (special_names_data); GalaxyIR sizes each
currency symbol from the program's declaration -- or, for a copybook, the
estate's.
"""

import shutil
import sqlite3

import pytest

from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.special_names import special_names
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db


def _program(name: str, special: str, working_storage: str) -> str:
    return (
        "       IDENTIFICATION DIVISION.\n"
        f"       PROGRAM-ID. {name}.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       CONFIGURATION SECTION.\n"
        "       SPECIAL-NAMES.\n"
        f"{special}"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        f"{working_storage}"
        "       PROCEDURE DIVISION.\n"
        "           GOBACK.\n"
    )


POUND = _program(
    "POUND",
    "           CURRENCY SIGN IS '£'.\n",
    "       01  POUND-REC.\n"
    "           05 A    PIC X(3).\n"
    "           05 AMT  PIC £££,££9.99.\n"
    "           05 B    PIC X(4).\n",
)
EURO = _program(
    "EURO",
    "           CURRENCY SIGN IS 'EUR ' WITH PICTURE SYMBOL 'U'\n           DECIMAL-POINT IS COMMA.\n",
    "       01  EURO-REC.\n"
    "           05 A    PIC X(3).\n"
    "           05 AMT  PIC UUU.UU9,99.\n"
    "           05 B    PIC X(4).\n"
    "       COPY EUROCPY.\n",
)
# A copybook has no SPECIAL-NAMES of its own: its `U` is the program's 'EUR '.
EUROCPY = "       01  EURO-COPY.\n           05 PRICE PIC U9(5).\n           05 TAIL  PIC X(2).\n"
# No SPECIAL-NAMES at all: the CP285 decoding of an ordinary `$` PIC, and a
# trailing euro sign.
UK = (
    "       01  UK-REC.\n"
    "           05 A    PIC X(3).\n"
    "           05 AMT  PIC £££9.99.\n"
    "           05 EUR  PIC 9(5)€.\n"
    "           05 B    PIC X(4).\n"
    "           05 TAG  PIC :TAG:X.\n"
)


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("currency")
    repo = base / "estate"
    files = {"cbl/POUND.cbl": POUND, "cbl/EURO.cbl": EURO, "cpy/EUROCPY.cpy": EUROCPY, "cpy/UK.cpy": UK}
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


def _layout(ir, path: str, record: str) -> dict:
    ef = ir.files[path]
    (root,) = [r for r in ef.records if r.name == record]
    return ir.record_layout(ef, root)


def _fields(layout: dict) -> list:
    return [(f["name"], f["offset"], f["bytes"]) for f in layout["fields"]]


def test_the_special_names_clauses_are_read():
    assert special_names(EURO) == [
        {"clause": "CURRENCY", "value": "EUR ", "symbol": "U", "line": 6},
        {"clause": "DECIMAL-POINT", "value": "COMMA", "symbol": None, "line": 7},
    ]
    # With no PICTURE SYMBOL the sign is its own symbol; a hex literal is EBCDIC.
    stream = _program("X", "           CURRENCY '£'\n           CURRENCY SIGN X'5B'.\n", "")
    assert [(r["value"], r["symbol"]) for r in special_names(stream)] == [("£", "£"), ("$", "$")]
    # A data name CURRENCY is not a clause: only the SPECIAL-NAMES paragraph is read.
    assert special_names("       01  REC.\n           05 CURRENCY PIC X(3) VALUE 'EUR'.\n") == []


def test_the_extractor_keeps_the_whole_pic():
    rows = {r["name"]: r for r in extract_boundary("cobol", UK)["records"]}
    assert rows["AMT"]["pic"] == "£££9.99"  # was None: the item read as a PIC-less group
    assert rows["EUR"]["pic"] == "9(5)€"  # was 9(5)
    assert rows["B"]["pic"] == "X(4)"
    # A `;` separator ends the PIC like a space (NIST NC2454: `PIC S999;`).
    semi = extract_boundary("cobol", "       01  R.\n           05 N PIC S999; VALUE 1.\n")["records"]
    assert semi[1]["pic"] == "S999"


def test_a_single_character_currency_sign_is_one_byte_per_position(scanned):
    ir = load_galaxy_ir(scanned)
    layout = _layout(ir, "cbl/POUND.cbl", "POUND-REC")
    assert _fields(layout) == [("A", 0, 3), ("AMT", 3, 10), ("B", 13, 4)]
    assert layout["bytes"] == 17


def test_a_multi_character_currency_string_takes_its_length(scanned):
    ir = load_galaxy_ir(scanned)
    ef = ir.files["cbl/EURO.cbl"]
    assert [(n.clause, n.value, n.symbol) for n in ef.special_names] == [
        ("CURRENCY", "EUR ", "U"),
        ("DECIMAL-POINT", "COMMA", None),
    ]
    # `UUU.UU9,99`: ten positions, the currency string 'EUR ' three more.
    assert _fields(_layout(ir, "cbl/EURO.cbl", "EURO-REC")) == [("A", 0, 3), ("AMT", 3, 13), ("B", 16, 4)]


def test_a_copybook_takes_the_estates_currency_string(scanned):
    ir = load_galaxy_ir(scanned)
    # `U9(5)`: 'EUR ' and five digits.
    assert _fields(_layout(ir, "cpy/EUROCPY.cpy", "EURO-COPY")) == [("PRICE", 0, 9), ("TAIL", 9, 2)]


def test_currency_signs_without_special_names(scanned):
    ir = load_galaxy_ir(scanned)
    layout = _layout(ir, "cpy/UK.cpy", "UK-REC")
    assert _fields(layout)[:4] == [("A", 0, 3), ("AMT", 3, 7), ("EUR", 10, 6), ("B", 16, 4)]
    # A REPLACING tag is not a picture symbol: its width is unknown, never guessed.
    assert layout["bytes"] is None


def test_conflicting_declarations_leave_a_copybook_width_unknown(tmp_path):
    repo = tmp_path / "estate"
    other = _program("OTHER", "           CURRENCY SIGN IS 'USD' WITH PICTURE SYMBOL 'U'.\n", "       COPY EUROCPY.\n")
    for rel, text in {"cbl/EURO.cbl": EURO, "cbl/OTHER.cbl": other, "cpy/EUROCPY.cpy": EUROCPY}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    ir = load_galaxy_ir(scan_to_db(repo, tmp_path / "scan"))
    assert _layout(ir, "cpy/EUROCPY.cpy", "EURO-COPY")["bytes"] is None
    # A program's own declaration still wins for its own items.
    assert _layout(ir, "cbl/EURO.cbl", "EURO-REC")["bytes"] == 20


def test_a_pre_3820_db_loads(scanned, tmp_path):
    old = tmp_path / "old.db"
    shutil.copy(scanned, old)
    with sqlite3.connect(old) as conn:
        conn.execute("DROP TABLE special_names_data")
    ir = load_galaxy_ir(old)
    assert ir.files["cbl/EURO.cbl"].special_names == []
    # Without the declaration `U` is one position, as before #3820.
    assert _layout(ir, "cbl/EURO.cbl", "EURO-REC")["bytes"] == 17
