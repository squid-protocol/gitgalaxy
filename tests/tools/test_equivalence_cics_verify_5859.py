"""#5859 (register X32): EXEC CICS VERIFY PASSWORD in the equivalence harness. The region has no security manager, so a
scenario states the verdict for the USERID (`{"cmd": "VERIFY", "userid", "nth", "resp"}`); the stub (GGCVER), CicsTask and
the translator read the same plan. IBM (CICS TS 6.x, VERIFY PASSWORD "Conditions"): USERIDERR, NOTAUTH, INVREQ."""

import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import equivalence_cics as ec  # noqa: E402
from gitgalaxy.core.source_text import read_source  # noqa: E402

REPO = TESTS.parent


def _lines(**f):
    return ec.fault_lines({"name": "s", "faults": [f]})


@pytest.mark.parametrize(
    ("fault", "line"),
    [
        ({"userid": "ALICE", "resp": "NORMAL"}, "VERIFY ALICE 1 0 0"),
        ({"userid": "ALICE", "resp": "USERIDERR"}, "VERIFY ALICE 1 69 0"),
        ({"userid": "BOB", "resp": "NOTAUTH", "nth": 2}, "VERIFY BOB 2 70 0"),
        ({"userid": "BOB", "resp": "INVREQ", "nth": "*"}, "VERIFY BOB * 16 0"),
    ],
)
def test_a_stated_verdict_is_planned_without_a_resp2(fault, line):
    assert _lines(cmd="VERIFY", **fault) == [line]


@pytest.mark.parametrize("resp", sorted(set(ec.CICS_RESP) - {"NORMAL", "USERIDERR", "NOTAUTH", "INVREQ"}))
def test_every_other_condition_is_refused_naming_x32(resp):
    with pytest.raises(ec.Unsupported, match="X32"):
        _lines(cmd="VERIFY", userid="ALICE", resp=resp)


def test_a_resp2_is_refused():
    with pytest.raises(ec.Unsupported, match="no RESP2"):
        _lines(cmd="VERIFY", userid="ALICE", resp="NOTAUTH", resp2=1)


def test_a_verdict_must_name_its_userid():
    with pytest.raises(ec.Unsupported, match="userid"):
        _lines(cmd="VERIFY", resp="NOTAUTH")


def test_verify_translates_to_the_stub_call():
    out = ec._translate_command("VERIFY USERID(WS-USER) PASSWORD(WS-PASS) NOHANDLE")
    assert "CALL 'GGCVER' USING GG-CICS" in out
    assert "    BY REFERENCE WS-USER" in out
    assert "    BY VALUE LENGTH OF WS-USER" in out
    assert not any("WS-PASS" in line for line in out)  # the password is never compared


@pytest.mark.parametrize("src", ["VERIFY PASSWORD(P)", "VERIFY USERID(U)"])
def test_verify_needs_both_operands(src):
    with pytest.raises(ec.Unsupported, match="without"):
        ec._translate_command(src)


@pytest.mark.parametrize("src", ["VERIFY PHRASE(P) USERID(U)", "VERIFY TOKEN(T)"])
def test_the_other_verify_forms_stay_refused(src):
    with pytest.raises(ec.Unsupported):
        ec._translate_command(src)


def test_the_stub_the_task_and_the_translator_name_the_same_hook():
    stub = read_source(REPO / "tests/equivalence/cics/ggcics.c").text
    forge = read_source(REPO / "gitgalaxy/tools/cobol_to_java/cobol_to_java_transaction_forge.py").text
    assert "int GGCVER(" in stub
    assert 'injected("VERIFY", id' in stub
    assert 'injected("VERIFY", id)' in forge
    assert "VERIFY-PASSWORD userid=%s resp=%d" in stub
    assert 'event("VERIFY-PASSWORD", "userid"' in forge
