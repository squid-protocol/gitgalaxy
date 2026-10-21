"""#5648: the expansion's line map lives in core.cobol_preprocessor: every expanded line says which file and line it
came from, a COPY member's lines keep the member's own numbers (nested, with REPLACING), fixed and free format."""

from __future__ import annotations

from gitgalaxy.core.cobol_preprocessor import MappedLine, line_map
from gitgalaxy.tools.cobol_to_java.det import source as SRC


def test_mapped_line_origin_and_short_origin():
    ln = MappedLine("MOVE A TO B.", "/est/cpy/CUSTREC.cpy", 12)
    assert ln.origin == "/est/cpy/CUSTREC.cpy:12"
    assert ln.short_origin == "CUSTREC.cpy:12"
    assert line_map([ln]) == [("/est/cpy/CUSTREC.cpy", 12)]


def test_translator_line_is_a_mapped_line_with_its_own_extras():
    ln = SRC.Line("X", "P.cbl", 3)
    assert isinstance(ln, MappedLine)
    assert (ln.cut, ln.lost, ln.lost_joined) == ("", "", False)
    assert ln.origin == "P.cbl:3"
    assert not any(hasattr(MappedLine, f) for f in ("cut", "lost", "lost_after", "lost_joined"))


def _write(path, rows, fixed):
    """Fixed form: code from column 8. Free form: a `>>SOURCE FORMAT FREE` first line, code from column 1."""
    if fixed:
        path.write_text("".join(f"       {r}\n" for r in rows))
    else:
        path.write_text("       >>SOURCE FORMAT FREE\n" + "".join(f"{r}\n" for r in rows))


def _expanded(tmp_path, fixed):
    cpy = tmp_path / "cpy"
    cpy.mkdir()
    _write(cpy / "OUTER.cpy", ["01  :T:-REC.", "    COPY INNER."], fixed)
    _write(cpy / "INNER.cpy", ["    05  CUST-ID PIC 9(4).", "    05  CUST-NAME PIC X(8)."], fixed)
    prog = tmp_path / "PROG.cbl"
    rows = [
        "IDENTIFICATION DIVISION.",
        "PROGRAM-ID. PROG.",
        "DATA DIVISION.",
        "WORKING-STORAGE SECTION.",
        "    COPY OUTER REPLACING ==:T:== BY ==CUST==.",
        "01  TAIL PIC X.",
    ]
    _write(prog, rows, fixed)
    lines = SRC.expand(SRC.logical_lines(rows_raw(prog), str(prog)), [cpy])
    return prog, cpy, lines


def rows_raw(path):
    return path.read_text().splitlines()


def test_member_lines_keep_member_file_and_line_fixed_and_free(tmp_path):
    for fixed in (True, False):
        d = tmp_path / ("fixed" if fixed else "free")
        d.mkdir()
        prog, cpy, lines = _expanded(d, fixed)
        first = 1 if fixed else 2  # the directive line comes first in a free-format file
        got = [(ln.text.strip(), ln.short_origin) for ln in lines if "CUST" in ln.text or "TAIL" in ln.text]
        assert got == [
            ("01  CUST-REC.", f"OUTER.cpy:{first}"),
            ("05  CUST-ID PIC 9(4).", f"INNER.cpy:{first}"),
            ("05  CUST-NAME PIC X(8).", f"INNER.cpy:{first + 1}"),
            ("01  TAIL PIC X.", f"PROG.cbl:{first + 5}"),
        ]
        assert [f for f, _ in line_map(lines)][-1] == str(prog)
        assert len(line_map(lines)) == len(lines)
