"""#7434: a counter command's VALUE / MINIMUM / MAXIMUM / INCREMENT / COMPAREMIN / COMPAREMAX may name raw bytes (a PIC X item),
not a number. IBM (CICS TS, GET / QUERY / DEFINE / UPDATE / REWIND COUNTER and DCOUNTER): VALUE is a fullword (COUNTER) or
doubleword (DCOUNTER) binary value held in the data area, whatever its COBOL picture; a fullword area given a larger counter
holds the low-order 32 bits (LENGERR). The translator stored such a value through the numeric path, and Codec.write threw
`not a numeric item: ALPHANUMERIC`. It now reads and stores the area's bytes big-endian (Cobol.rawUnsigned / putRawUnsigned)."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cobol_mainframe"))
from test_det_translate import _LenCics  # noqa: E402


class _Item:
    def __init__(self, category):
        self.category = category


class _Cics(_LenCics):
    """X8 / X4 are PIC X items; N a numeric one."""

    def __init__(self):
        super().__init__()
        cats = {"X8": "ALPHANUMERIC", "X4": "ALPHANUMERIC", "GRP": "GROUP", "N": "NUMERIC"}
        self.g.resolve = lambda ref: _Item(cats[ref.name])
        self.g.field_expr = lambda ref: f"f_{ref.name}"


def _cmd(text):
    return "\n".join(_Cics().command(text, ""))


@pytest.mark.parametrize("area", ["X8", "X4", "GRP"])
def test_a_raw_area_receives_the_counter_value_as_bytes(area):
    for verb in ("GET DCOUNTER(K) VALUE", "GET COUNTER(K) VALUE", "QUERY DCOUNTER(K) VALUE", "QUERY COUNTER(K) VALUE"):
        out = _cmd(f"{verb}({area}) RESP(R)")
        assert f"Cobol.putRawUnsigned(f_{area}, " in out and "STORE(" not in out, verb
    out = _cmd(f"QUERY DCOUNTER(K) VALUE({area}) MINIMUM({area}) MAXIMUM({area}) RESP(R)")
    assert out.count("putRawUnsigned") == 3
    assert "& 0xFFFFFFFFL" in _cmd(f"QUERY COUNTER(K) VALUE({area}) RESP(R)")  # a fullword: the low 32 bits


@pytest.mark.parametrize("area", ["X8", "X4", "GRP"])
def test_a_raw_area_is_read_as_an_unsigned_big_endian_number(area):
    cmds = (
        f"DEFINE DCOUNTER(K) VALUE({area}) MINIMUM({area}) MAXIMUM({area}) RESP(R)",
        f"DEFINE COUNTER(K) VALUE({area}) MINIMUM({area}) MAXIMUM({area}) RESP(R)",
        f"GET DCOUNTER(K) VALUE(N) INCREMENT({area}) RESP(R)",
        f"GET COUNTER(K) VALUE(N) COMPAREMIN({area}) COMPAREMAX({area}) RESP(R)",
        f"UPDATE DCOUNTER(K) VALUE({area}) RESP(R)",
        f"REWIND COUNTER(K) INCREMENT({area}) RESP(R)",
    )
    for c in cmds:
        out = _cmd(c)
        assert f"Cobol.rawUnsigned(f_{area})" in out and f"LONG({area})" not in out and f"INT({area})" not in out, c


def test_a_numeric_area_keeps_the_numeric_path():
    out = _cmd("GET DCOUNTER(K) VALUE(N) INCREMENT(N) RESP(R)")
    assert "rawUnsigned" not in out and "putRawUnsigned" not in out
    assert "STORE(N, new BigDecimal(Long.toUnsignedString(" in out and "LONG(N)" in out
    assert "INT(N)" in _cmd("DEFINE COUNTER(K) VALUE(N) RESP(R)")
