"""#8121: `EXEC SQL INCLUDE member END-EXEC` lays out like `COPY member.` (HCAVDB01's DFHCOMMAREA is only that)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_common as common

# An HCCMAREA-shaped member: a header group and a REDEFINES-free request group.
MEMBER = [
    "           03 CA-REQUEST-ID            PIC X(6).",
    "           03 CA-RETURN-CODE           PIC 9(2).",
    "           03 CA-PATIENT-ID            PIC 9(10).",
    "           03 CA-REQUEST-SPECIFIC      PIC X(32482).",
    "           03 CA-VISIT.",
    "              05 CA-VISIT-DATE         PIC X(10).",
    "              05 CA-VISIT-TIME         PIC X(10).",
]
VIA_COPY = ["       01 DFHCOMMAREA.", "           COPY HCCMAREA.", ""]
MULTI = ["       01 DFHCOMMAREA.", "           EXEC SQL", "             INCLUDE HCCMAREA", "           END-EXEC.", ""]
ONE = ["       01 DFHCOMMAREA.", "           EXEC SQL INCLUDE HCCMAREA END-EXEC.", ""]


def _w(path: Path, lines: list[str], crlf: bool = False) -> None:
    path.write_text(("\r\n" if crlf else "\n").join(["      * x"] + lines), encoding="latin-1")


def _fields(tmp_path: Path, main: list[str], crlf: bool = False, member_dir: Path | None = None):
    d = member_dir or tmp_path
    d.mkdir(exist_ok=True)
    _w(d / "HCCMAREA.cpy", MEMBER)
    _w(tmp_path / "main.cpy", main, crlf)
    return common.layout_fields(tmp_path, "main.cpy", copy_dirs=[tmp_path, d])


def _shape(fields):
    return [(f["name"], f["offset"], f["bytes"]) for f in fields]


@pytest.mark.parametrize("form", [MULTI, ONE], ids=["multi-line", "one-line"])
@pytest.mark.parametrize("crlf", [False, True], ids=["lf", "crlf"])
def test_include_lays_out_like_copy(tmp_path, form, crlf):
    got = _fields(tmp_path, form, crlf)
    assert got, "the record has fields"
    assert _shape(got) == _shape(_fields(tmp_path, VIA_COPY))
    assert [f["name"] for f in got][:2] == ["CA-REQUEST-ID", "CA-RETURN-CODE"]
    assert got[-1]["offset"] == 6 + 2 + 10 + 32482 + 10


def test_lowercase_member_in_another_directory(tmp_path):
    d = tmp_path / "cpy"
    d.mkdir()
    _w(d / "hccmarea.cpy", MEMBER)
    _w(tmp_path / "main.cpy", MULTI)
    got = common.layout_fields(tmp_path, "main.cpy", copy_dirs=[tmp_path, d])
    assert got[0]["name"] == "CA-REQUEST-ID"


def test_include_nested_in_an_included_member(tmp_path):
    _w(tmp_path / "OUTER.cpy", ["           EXEC SQL INCLUDE HCCMAREA END-EXEC."])
    _w(tmp_path / "HCCMAREA.cpy", MEMBER)
    _w(tmp_path / "main.cpy", ["       01 DFHCOMMAREA.", "           COPY OUTER.", ""])
    assert _shape(common.layout_fields(tmp_path, "main.cpy")) == _shape(_fields(tmp_path, VIA_COPY))


def test_unresolved_member_in_the_record_raises(tmp_path):
    _w(
        tmp_path / "main.cpy",
        ["       01 DFHCOMMAREA.", "           EXEC SQL INCLUDE NOSUCH END-EXEC.", "           03 A PIC X."],
    )
    with pytest.raises(common.LayoutError):
        common.layout_fields(tmp_path, "main.cpy")


def test_sqlca_include_is_left_alone(tmp_path):
    _w(
        tmp_path / "main.cpy",
        [
            "       01 REC.",
            "           03 A PIC X(2).",
            "           EXEC SQL INCLUDE SQLCA END-EXEC.",
            "           03 B PIC X(3).",
        ],
    )
    assert _shape(common.layout_fields(tmp_path, "main.cpy")) == [("A", 0, 2), ("B", 2, 3)]


def test_other_exec_sql_is_left_alone(tmp_path):
    _w(
        tmp_path / "main.cpy",
        [
            "       01 REC.",
            "           03 A PIC X(2).",
            "           EXEC SQL DECLARE C1 CURSOR FOR SELECT 1 END-EXEC.",
            "           03 B PIC X(3).",
        ],
    )
    assert _shape(common.layout_fields(tmp_path, "main.cpy")) == [("A", 0, 2), ("B", 2, 3)]
