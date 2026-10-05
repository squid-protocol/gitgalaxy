"""#4393: five drafting-reader errors the #4377 referee panel found in the answer keys -- the key was
wrong, the engine right. Each is fixed in cobol_answer_key._data_items and the keys re-drafted with
`redraft-records`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cobol_answer_key as ak  # noqa: E402

SRC = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. KEYRDR.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PLUS               PIC S9(4) COMP VALUE +18.
       01  WS-MINUS              PIC S9(4) COMP VALUE -1.
       01  WS-CRLF               PIC X(2) VALUE X'0D25'.
       01  WS-TABLE.
           10   PIC X(20) VALUE '0000APPROVED'.
       01  WS-HTML.
           88  HTML-L08 VALUE '<table  align="center" frame="box" styl
      -             'e="width:70%">'.
       01  COMM-OVERDR           PIC X(2).
       PROCEDURE DIVISION.
           MOVE 'TO' TO COMM-OVERDR
           DISPLAY COMM-OVERDR
           GOBACK.
"""


def _items(tmp_path):
    path = tmp_path / "KEYRDR.cbl"
    path.write_text(SRC, encoding="utf-8")
    return {(it["name"], it["line"]): it for it in ak._data_items(ak.Source(path))}


def test_the_five_patterns(tmp_path):
    items = _items(tmp_path)
    assert items[("WS-PLUS", 5)]["value"] == "+18"
    assert items[("WS-MINUS", 6)]["value"] == "-1"
    assert items[("WS-CRLF", 7)]["value"] == "X'0D25'"
    assert items[("FILLER", 9)]["pic"] == "X(20)"  # `10 PIC X(20)`: an implicit FILLER, not `PIC`
    # a continued literal: the first line's characters through column 72, then the continuation's
    first = SRC.splitlines()[10][7:72].upper().ljust(65)  # columns 8-72, blank-padded
    head = first[first.index("'") + 1 :]
    assert items[("HTML-L08", 11)]["value"] == head + 'E="WIDTH:70%">'
    # the last DATA DIVISION entry takes nothing from the PROCEDURE DIVISION
    assert (items[("COMM-OVERDR", 13)]["value"], items[("COMM-OVERDR", 13)]["usage"]) == (None, None)


def test_redraft_keeps_the_stored_fields_and_notes_the_change(tmp_path):
    path = tmp_path / "KEYRDR.cbl"
    path.write_text(SRC, encoding="utf-8")
    stale = [dict(it, value=None) for it in ak._data_items(ak.Source(path))]
    for it in stale:
        it.pop("sign_separate"), it.pop("sign_leading")  # a key drafted before those fields existed
    key = {"programs": {"KEYRDR.cbl": {"records": stale, "records_validated": True, "verification": {"notes": []}}}}
    assert ak.redraft_records(tmp_path, key, "re-drafted") == 1
    prog = key["programs"]["KEYRDR.cbl"]
    assert prog["records"][0]["value"] == "+18" and "sign_separate" not in prog["records"][0]
    assert prog["records_validated"] is True and prog["verification"]["notes"] == ["re-drafted"]
    assert ak.redraft_records(tmp_path, key, "again") == 0  # idempotent
