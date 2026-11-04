"""#7607: a scenario's untyped COMMAREA (`commarea_hex`, #5859) reaches a program whose facade has a DTO and a
byte-carrying overload. The facade leg used to refuse it ("cannot take the COMMAREA ([B)"), so a bytes-in write-back
mutant (ZECSPLT's `caBack`) stayed unkilled. The generated region now hands the raw bytes to
`handleTransaction(transid, null, bytes)` and accepts a null typed request for exactly that case. The end-to-end proof
is `det_port.py run zecs-zecsplt` (short-ca-first, long-ca on the facade leg); these pin the generated text."""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import equivalence_cics as ec  # noqa: E402

_JAVA = ec.FACADE_JAVA


def test_untyped_bytes_go_to_the_byte_overload_with_no_typed_request():
    assert "commarea instanceof byte[] && twoB != null" in _JAVA
    assert "scenario.transid(), null, (byte[]) commarea" in _JAVA


def test_the_region_matches_a_null_request_only_for_untyped_bytes():
    assert "boolean untyped = commarea instanceof byte[] && ca == null;" in _JAVA
    assert "(ca != commarea && !untyped)" in _JAVA


def test_every_other_commarea_still_refuses():
    assert 'throw new FacadeRefused("handleTransaction of " + program + " cannot take the COMMAREA ("' in _JAVA
    # the untyped branch sits before the refusal and after the typed ones, so a typed COMMAREA never takes it
    typed = _JAVA.index("two.getParameterTypes()[1].isInstance(commarea)")
    untyped = _JAVA.index("commarea instanceof byte[] && twoB != null")
    refusal = _JAVA.index("cannot take the COMMAREA (")
    assert typed < untyped < refusal


# ---- the bytes handed back to the caller are compared (caBack write-back) ---------------------------------------
def _ca(b64, **extra):
    return [{"event": "COMMAREA", "commarea": b64, **extra}]


def test_the_caller_bytes_the_facade_hands_back_must_be_those_the_port_left():
    sc = {"name": "long-ca", "commarea_hex": "4142434445"}
    assert ec.caller_bytes_diff(sc, _ca("wcLDxMU="), _ca("wcLDxMU=")) is None
    # a write-back that copies from the wrong offset / length changes the caller's array
    assert ec.caller_bytes_diff(sc, _ca("wcLDxMU="), _ca("wsPExQ==")) == {"task": "wcLDxMU=", "facade": "wsPExQ=="}
    # the area the port left absent on one side is a difference too, never a pass
    assert ec.caller_bytes_diff(sc, _ca("wcLDxMU="), []) == {"task": "wcLDxMU=", "facade": None}


def test_a_scenario_with_no_untyped_bytes_is_not_judged_by_it():
    sc = {"name": "next-task"}
    assert ec.caller_bytes_diff(sc, _ca("AA=="), _ca("AQ==")) is None


def test_the_facade_verdict_reads_it_and_the_report_says_so():
    import inspect

    src = inspect.getsource(ec.judge_facade)
    assert "caller_bytes_diff(" in src and 'o["caller_bytes"] = moved' in src
    assert "the bytes handed back to the caller" in inspect.getsource(ec)
