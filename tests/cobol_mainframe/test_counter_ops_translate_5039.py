"""#5039 (register X53): REWIND / UPDATE COUNTER and DCOUNTER, GET COUNTER / DCOUNTER REDUCE / COMPAREMIN / COMPAREMAX and
NOSUSPEND on the six named-counter commands, translated by the stub's harness (equivalence_cics.translate_command) and the
det port (Cics.command). The runtimes' answers are tests/cics_crucible/test_counter_ops_runtimes_5039.py's."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "tools"))
import equivalence_cics as ec  # noqa: E402
from test_det_translate import _LenCics  # noqa: E402

from gitgalaxy.standards.cics.commands import COMMANDS as SPEC  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402

_SIX = [
    "DEFINE {k}(KEY) VALUE(V)",
    "GET {k}(KEY) VALUE(V)",
    "QUERY {k}(KEY) VALUE(V)",
    "UPDATE {k}(KEY) VALUE(V)",
    "REWIND {k}(KEY)",
    "DELETE {k}(KEY)",
]


@pytest.mark.parametrize("kind", ["COUNTER", "DCOUNTER"])
@pytest.mark.parametrize("text", _SIX)
def test_nosuspend_is_accepted_on_every_counter_command_and_changes_nothing(kind, text):
    """One task, no coupling-facility structure to rebuild: BUSY RESP2 500 cannot occur (X53, ASSUMED)."""
    plain = text.format(k=kind)
    with_it = plain + " NOSUSPEND"
    assert ec.translate_command(with_it) == ec.translate_command(plain)
    assert _LenCics().command(with_it, "") == _LenCics().command(plain, "")


def test_the_stub_translates_rewind_and_update():
    rw = ec.translate_command("REWIND COUNTER(KEY) POOL('P') INCREMENT(INC) RESP(R)")
    assert "CALL 'GGCRCNT' USING GG-CICS" in rw and "    BY REFERENCE INC" in rw
    dc = ec.translate_command("REWIND DCOUNTER(KEY)")
    assert "CALL 'GGCRDCN' USING GG-CICS" in dc and "    BY VALUE 0" in dc  # INCREMENT omitted: length 0
    up = ec.translate_command("UPDATE COUNTER(KEY) VALUE(V)")
    assert "CALL 'GGCUCNT' USING GG-CICS" in up and "    BY REFERENCE V" in up
    assert "CALL 'GGCUDCN' USING GG-CICS" in ec.translate_command("UPDATE DCOUNTER(KEY) VALUE(V)")


def test_the_stub_translates_get_reduce_and_compare_to_the_extended_entry_points():
    out = ec.translate_command("GET COUNTER(KEY) VALUE(V) REDUCE COMPAREMIN(LO) COMPAREMAX(HI)")
    assert "CALL 'GGCGCNX' USING GG-CICS" in out
    assert "    BY VALUE 1" in out and "    BY REFERENCE LO" in out and "    BY REFERENCE HI" in out
    assert "CALL 'GGCGDCX' USING GG-CICS" in ec.translate_command("GET DCOUNTER(KEY) VALUE(V) COMPAREMAX(HI)")
    assert "CALL 'GGCGCNT' USING GG-CICS" in ec.translate_command("GET COUNTER(KEY) VALUE(V) WRAP")  # unchanged


@pytest.mark.parametrize(
    "text",
    [
        "UPDATE COUNTER(KEY) VALUE(V) COMPAREMIN(LO)",  # IBM: new value or current value is not said
        "UPDATE DCOUNTER(KEY) VALUE(V) COMPAREMAX(HI)",
        "UPDATE COUNTER(KEY)",
        "UPDATE COUNTER(KEY) DCOUNTER(KEY) VALUE(V)",
        "UPDATE COUNTER(KEY) VALUE(5)",  # a data area is the COBOL form on the stub side
        "REWIND COUNTER(KEY) DCOUNTER(KEY)",
        "REWIND COUNTER(KEY) INCREMENT(2)",
        "GET COUNTER(KEY) VALUE(V) COMPAREMIN(5)",
    ],
)
def test_what_the_counter_class_leaves_open_is_refused_by_name_on_the_stub_side(text):
    with pytest.raises(ec.Unsupported):
        ec.translate_command(text)


def test_the_det_port_translates_rewind_and_update():
    rw = _LenCics().command("REWIND COUNTER(KEY) POOL('P') INCREMENT(5) RESP(R)", "")
    assert any("task.rewindCounter(" in x and ", LONG(5));" in x for x in rw)
    assert any("task.rewindCounter(" in x and ", 1L)" in x for x in _LenCics().command("REWIND DCOUNTER(KEY)", ""))
    up = " ".join(_LenCics().command("UPDATE COUNTER(KEY) VALUE(V) NOHANDLE", ""))
    assert "task.updateCounter(" in up and up.count(", true)") == 1
    assert ", false)" in " ".join(_LenCics().command("UPDATE DCOUNTER(KEY) VALUE(V)", ""))


def test_the_det_port_translates_get_reduce_and_compare():
    out = " ".join(_LenCics().command("GET COUNTER(KEY) VALUE(V) REDUCE COMPAREMAX(HI)", ""))
    assert ", 1L, false, true, null, Long.valueOf(LONG(HI)), true);" in out  # a COUNTER: a fullword
    dc = " ".join(_LenCics().command("GET DCOUNTER(KEY) VALUE(V) COMPAREMIN(LO)", ""))
    assert ", false, false, Long.valueOf(LONG(LO)), null, false);" in dc  # (a DCOUNTER: not a fullword)
    assert "task.getCounter(" in " ".join(_LenCics().command("GET COUNTER(KEY) VALUE(V) WRAP", ""))  # unchanged form


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("UPDATE COUNTER(KEY) VALUE(V) COMPAREMIN(LO)", "COMPAREMIN"),
        ("UPDATE DCOUNTER(KEY) VALUE(V) COMPAREMAX(HI)", "COMPAREMAX"),
        ("UPDATE COUNTER(KEY)", "without VALUE"),
        ("REWIND COUNTER(KEY) DCOUNTER(KEY)", "one of COUNTER and DCOUNTER"),
        ("REWIND COUNTER(KEY) VALUE(V)", "VALUE"),
    ],
)
def test_the_det_port_refuses_what_the_counter_class_leaves_open(text, why):
    with pytest.raises(C.CicsError, match=why):
        _LenCics().command(text, "")


def test_the_spec_models_every_counter_class_member():
    for key in ("REWIND COUNTER", "UPDATE COUNTER"):
        assert SPEC[key].status == "modelled" and SPEC[key].register == "X53"
    for key in ("DEFINE COUNTER", "GET COUNTER", "QUERY COUNTER", "DELETE COUNTER", "REWIND COUNTER", "UPDATE COUNTER"):
        assert "NOSUSPEND" in SPEC[key].options
    for o in ("REDUCE", "COMPAREMIN", "COMPAREMAX"):
        assert o in SPEC["GET COUNTER"].options and o not in SPEC["GET COUNTER"].refused
    assert set(SPEC["UPDATE COUNTER"].refused) == {"COMPAREMIN", "COMPAREMAX"}


def test_the_det_port_reads_a_fullword_counter_through_the_lengerr_helper_only_for_the_fullword_form():
    """#4770 (X30): GET COUNTER may meet a counter a DCOUNTER made past 31 bits (LENGERR, the low 32 bits written); GET DCOUNTER never."""
    c = _LenCics().command("GET COUNTER(KEY) VALUE(V) NOHANDLE", "")
    assert any("task.fullwordGet(" in x for x in c) and any("[0] == 22" in x for x in c)
    d = _LenCics().command("GET DCOUNTER(KEY) VALUE(V) NOHANDLE", "")
    assert not any("fullwordGet" in x or "== 22" in x for x in d)
    q = " ".join(_LenCics().command("QUERY COUNTER(KEY) VALUE(V) NOHANDLE", ""))
    assert "[0] == 22" in q
