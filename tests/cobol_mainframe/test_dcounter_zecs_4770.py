"""#4770 (register X30 / X45 / X53), the verify slice: zECS ZECS001's key allocator, `EXEC CICS GET DCOUNTER(ZECS-COUNTER)
VALUE(ZECS-VALUE) INCREMENT(ZECS-INCREMENT) WRAP NOHANDLE`, translated by the det port (Cics.command) and the stub's harness
(equivalence_cics.translate_command) for every doubleword-capable receiver form (ZECS001 declares VALUE and INCREMENT
PIC 9(16) COMP; the issue wrote 9(18)), and the options GET DCOUNTER refuses by name.

IBM: https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-get-counter-get-dcounter -- DCOUNTER's value is "a doubleword
unsigned binary", INCREMENT the amount to add (default 1), WRAP resets a counter at its limit to its minimum. A store past
the receiver's PICTURE is the general binary-store mechanism (test_det_binary_store.py, #4684), not this command's."""

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "tools"))
import equivalence_cics as ec  # noqa: E402
from test_det_translate import _ChanCics, _LenCics  # noqa: E402

from gitgalaxy.core.source_text import read_source  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402

ZECS_GET = "GET DCOUNTER(ZECS-COUNTER) VALUE(ZECS-VALUE) INCREMENT(ZECS-INCREMENT) WRAP NOHANDLE"
DET = [_ChanCics, _LenCics]


@pytest.mark.parametrize("cls", DET)
def test_zecs001_get_dcounter_translates_to_an_unsigned_wrapping_get(cls):
    out = cls().command(ZECS_GET, "")
    assert out[0].startswith("long[] counter") and out[0].endswith(
        'task.getCounter("", ZECS-COUNTER.strip(), LONG(ZECS-INCREMENT), true);'
    )
    body = " ".join(out)
    assert "new BigDecimal(Long.toUnsignedString(" in body  # the doubleword VALUE is unsigned (past 2**63 stays positive)
    assert "fullwordGet" not in body  # LENGERR is the fullword form's


def test_zecs001_get_dcounter_translates_to_the_doubleword_stub_entry():
    out = "\n".join(ec.translate_command(ZECS_GET))
    assert "CALL 'GGCGDCN' USING GG-CICS" in out and "GGCGCNT" not in out
    assert "    BY REFERENCE ZECS-VALUE" in out and "    BY VALUE LENGTH OF ZECS-VALUE" in out
    assert "    BY REFERENCE ZECS-INCREMENT" in out and "    BY VALUE LENGTH OF ZECS-INCREMENT" in out
    assert "    BY VALUE 1" in out  # WRAP


@pytest.mark.parametrize("wrap", ["", " WRAP"])
@pytest.mark.parametrize("inc", ["", " INCREMENT(INC)"])
@pytest.mark.parametrize("cls", DET)
def test_every_increment_wrap_combination_picks_the_matching_getcounter_arity(cls, wrap, inc):
    out = cls().command(f"GET DCOUNTER(KEY) VALUE(V){inc}{wrap} NOHANDLE", "")[0]
    args = out.count(",")
    assert args == 1 + (2 if wrap else bool(inc))  # (pool, name[, increment][, wrap]); WRAP alone passes the default 1L
    assert out.endswith(", true);") == bool(wrap)
    if wrap and not inc:
        assert ", 1L, true);" in out
    stub = "\n".join(ec.translate_command(f"GET DCOUNTER(KEY) VALUE(V){inc}{wrap} NOHANDLE"))
    assert f"    BY VALUE {int(bool(wrap))}" in stub
    assert ("BY REFERENCE INC" in stub) == bool(inc)


@pytest.mark.parametrize("opt", ["MINIMUM(M)", "MAXIMUM(M)"])
@pytest.mark.parametrize("cls", DET)
def test_minimum_and_maximum_are_refused_by_name_on_get(cls, opt):
    """DEFINE / QUERY DCOUNTER model them (X45); GET has no such option, so it is refused, never ignored."""
    with pytest.raises(C.CicsError, match="not modelled"):
        cls().command(f"GET DCOUNTER(KEY) VALUE(V) {opt}", "")
    with pytest.raises(ec.Unsupported, match="not modelled"):
        ec.translate_command(f"GET DCOUNTER(KEY) VALUE(V) {opt}")


@pytest.mark.parametrize("cls", DET)
def test_get_dcounter_without_value_or_with_both_forms_is_refused(cls):
    for bad, why in (
        ("GET DCOUNTER(KEY) INCREMENT(INC) WRAP", "without VALUE"),
        ("GET DCOUNTER(KEY) COUNTER(KEY) VALUE(V)", "one of COUNTER and DCOUNTER"),
    ):
        with pytest.raises(C.CicsError, match=why):
            cls().command(bad, "")


@pytest.mark.skipif(not os.environ.get("GITGALAXY_MAINFRAME_CORPORA"), reason="no mainframe corpora")
def test_the_statement_is_the_one_in_zecs001():
    src = Path(os.environ["GITGALAXY_MAINFRAME_CORPORA"]) / "zecs" / "Source" / "ZECS001.cbl"
    if not src.is_file():
        pytest.skip("zecs corpus not fetched")
    text = " ".join(read_source(src).text.split())
    assert "EXEC CICS GET DCOUNTER(ZECS-COUNTER) VALUE(ZECS-VALUE) INCREMENT(ZECS-INCREMENT) WRAP" in text
    assert "ZECS-VALUE PIC 9(16) COMP" in text and "ZECS-INCREMENT PIC 9(16) COMP" in text
