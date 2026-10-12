"""#4804: a RECORD KEY / ALTERNATE RECORD KEY item outside the file's record is refused by name.

IBM Enterprise COBOL Language Reference, RECORD KEY clause: the key data item is defined in a record description entry
of that file (GnuCOBOL, the instrument, refuses too: "'X' is not defined"). The det translator never invents a
translation for it, so a program with such a key stops counting as translated whole."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")
from test_det_programs import PKG, fprogram

WHY = "is not defined in a record of file"

# name -> (SELECT clauses, FILE SECTION, WORKING-STORAGE, refused key name or None)
SHAPES = {
    "key-in-fd": (
        "RECORD KEY IS K-ID",
        ["FD  F1.", "01  F1-REC.", "    05 K-ID PIC X(4).", "    05 FILLER PIC X(6)."],
        [],
        None,
    ),
    "key-in-ws": (
        "RECORD KEY IS K-ID",
        ["FD  F1.", "01  F1-REC PIC X(10)."],
        ["01  WS-K.", "    05 K-ID PIC X(4)."],
        "K-ID",
    ),
    "alt-key-outside": (
        "RECORD KEY IS K-ID ALTERNATE RECORD KEY IS K-ALT WITH DUPLICATES",
        ["FD  F1.", "01  F1-REC.", "    05 K-ID PIC X(4).", "    05 FILLER PIC X(6)."],
        ["01  K-ALT PIC X(3)."],
        "K-ALT",
    ),
    "alt-key-in-fd": (
        "RECORD KEY IS K-ID ALTERNATE RECORD KEY IS K-ALT",
        ["FD  F1.", "01  F1-REC.", "    05 K-ID PIC X(4).", "    05 K-ALT PIC X(3)."],
        [],
        None,
    ),
    "key-via-qualified-ws": (
        "RECORD KEY IS K-ID OF WS-K",
        ["FD  F1.", "01  F1-REC PIC X(10)."],
        ["01  WS-K.", "    05 K-ID PIC X(4)."],
        "K-ID",
    ),
    # several 01 records under one FD: a key in any of them is in the file's record
    "key-in-second-01": (
        "RECORD KEY IS K-ID",
        ["FD  F1.", "01  F1-REC-A PIC X(10).", "01  F1-REC-B.", "    05 K-ID PIC X(4).", "    05 FILLER PIC X(6)."],
        [],
        None,
    ),
    "key-in-other-files-record": (
        "RECORD KEY IS K-ID",
        [
            "FD  F1.",
            "01  F1-REC PIC X(10).",
            "FD  F2.",
            "01  F2-REC.",
            "    05 K-ID PIC X(4).",
            "    05 FILLER PIC X(6).",
        ],
        [],
        "K-ID",
    ),
}


def _holes(tmp_path: Path, select: str, files: list[str], data: list[str]) -> list[str]:
    from gitgalaxy.tools.cobol_to_java.det import program as P

    # one clause per line: fixed format ends at column 72
    head, *alts = select.split(" ALTERNATE ")
    selects = [
        "SELECT F1 ASSIGN TO F1DD ORGANIZATION IS INDEXED",
        "ACCESS MODE IS RANDOM",
        head,
        *[f"ALTERNATE {x}" for x in alts],
    ]
    selects[-1] += "."
    if any(x.startswith("FD  F2") for x in files):
        selects.append("SELECT F2 ASSIGN TO F2DD ORGANIZATION IS SEQUENTIAL.")
    src = fprogram(
        "KEYX",
        [],
        selects,
        files,
        [*data, "01  FS PIC XX."],
        ["MAIN-PARA.", "    OPEN I-O F1", "    CLOSE F1", "    GOBACK."],
    )
    (tmp_path / "KEYX.cbl").write_text(src)
    (tmp_path / "project").mkdir(exist_ok=True)
    return P.translate(
        tmp_path / "KEYX.cbl", [], "public class KeyxService {\n}\n", PKG, None, tmp_path / "project"
    ).stats["holes"]


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_record_key_outside_the_file_record_is_refused_by_name(name, tmp_path):
    select, files, data, refused = SHAPES[name]
    holes = _holes(tmp_path, select, files, data)
    hit = [h for h in holes if WHY in h]
    if refused is None:
        assert not hit, holes
    else:
        assert hit and all(refused in h for h in hit), holes
