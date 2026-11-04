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


# the bytes a LINKing caller sees once the task ended (#7607): the oracle's commarea.out against the port's area


def _events(area: bytes | None) -> list[dict]:
    import base64

    return [{"event": "COMMAREA", "commarea": "x", **({} if area is None else {"area": base64.b64encode(area).decode()})}]


def test_caller_bytes_agree_differ_and_absent(tmp_path):
    sc = {"commarea_hex": "4142"}
    (tmp_path / "commarea.out").write_bytes(b"AB")
    assert ec.caller_bytes_diff(sc, tmp_path, _events(b"AB")) is None
    assert ec.caller_bytes_diff(sc, tmp_path, _events(b"BA")) == {"cobol": "4142", "java": "4241"}
    assert ec.caller_bytes_diff(sc, tmp_path, _events(None)) is None  # the port never took the area
    assert ec.caller_bytes_diff(sc, tmp_path, []) is None


def test_a_scenario_with_no_untyped_bytes_is_not_judged(tmp_path):
    (tmp_path / "commarea.out").write_bytes(b"AB")
    assert ec.caller_bytes_diff({"commarea_hex": ""}, tmp_path, _events(b"zz")) is None
    assert ec.caller_bytes_diff({}, tmp_path, _events(b"zz")) is None
    assert ec.caller_bytes_diff({"commarea_hex": "4142"}, tmp_path / "none", _events(b"zz")) is None


def test_run_case_judges_the_caller_bytes_and_reports_them():
    import inspect

    src = inspect.getsource(ec.run_case)
    assert 'caller_bytes_diff(sc, work / "cobol" / "scenarios" / name / "out"' in src
    assert 'report["outputs"][name]["caller_bytes"] = moved' in src
