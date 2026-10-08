"""#4690 / #4691: every byte value as a COBOL hex literal translates to Java that compiles (a raw or \\u000a-escaped
control character cut the Java string literal open), and DISPLAY writes the record charset's single byte, as the
GnuCOBOL oracle does (the port wrote U+00FF as UTF-8 C3 BF)."""

from __future__ import annotations

import os
import shutil

import pytest
from test_det_programs import _cobol, _java, _java_run, program

E2E = pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker") or _java() is None,
                         reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip


def every_byte_program(name: str) -> str:
    """One MOVE X'hh' TO R and DISPLAY per byte 0x00-0xFF, then a multi-byte literal holding the line breaks."""
    proc: list[str] = []
    for b in range(256):
        proc += [f"MOVE X'{b:02X}' TO R", "DISPLAY R"]
    proc += ["MOVE X'3132330A0D2230' TO W", "DISPLAY W", "MOVE X'5C5C22' TO W", "DISPLAY W"]
    return program(name, ["01 R PIC X.", "01 W PIC X(8)."], proc)


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_every_byte_value_as_a_hex_literal_compiles(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    # _java_run runs javac with check=True: an unclosed string literal raises
    _java_run("HEXALL", every_byte_program("HEXALL"), tmp_path, raw=True)


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_jstr_never_emits_a_unicode_escape_for_a_line_break_or_quote():
    from gitgalaxy.tools.cobol_to_java.det.gen import jstr

    for b in range(256):
        lit = jstr(chr(b))
        assert "\\u" not in lit, (b, lit)
        assert all(ord(c) < 128 for c in lit)
    assert jstr("\n\r\x000") == '"\\012\\015\\0000"'


@E2E
@pytest.mark.parametrize("mode", ["bytes", "typed", "groups"])
def test_every_byte_hex_literal_and_display_equal_gnucobols(mode, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    src = every_byte_program("HEXALL")
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = _cobol(src, cob, raw=True)
    got = _java_run("HEXALL", src, tmp_path, mode != "bytes", mode == "groups", raw=True)
    assert isinstance(want, bytes) and want
    assert b"\xc3\xbf" not in got
    assert got == want
