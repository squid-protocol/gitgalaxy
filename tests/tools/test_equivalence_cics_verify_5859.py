"""#5859 (register X32): EXEC CICS VERIFY PASSWORD in the equivalence harness. The region has no security manager, so a
scenario states the verdict for the USERID (`{"cmd": "VERIFY", "userid", "nth", "resp"}`); the stub (GGCVER), CicsTask and
the translator read the same plan. IBM (CICS TS 6.x, VERIFY PASSWORD "Conditions"): USERIDERR, NOTAUTH, INVREQ."""

import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import equivalence_cics as ec  # noqa: E402
import ggcics_source  # noqa: E402
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
    stub = ggcics_source.stub_source()
    forge = read_source(REPO / "gitgalaxy/tools/cobol_to_java/cobol_to_java_transaction_forge.py").text
    assert "int GGCVER(" in stub
    assert 'injected("VERIFY", id' in stub
    assert 'injected("VERIFY", id)' in forge
    assert "VERIFY-PASSWORD userid=%s resp=%d" in stub
    assert 'event("VERIFY-PASSWORD", "userid"' in forge


def test_userid_hex_is_the_fields_own_bytes_as_latin_1_text():
    assert _lines(cmd="VERIFY", userid_hex="C1D3C9C3C5404040", resp="NORMAL") == [
        "VERIFY \xc1\xd3\xc9\xc3\xc5@@@ 1 0 0"
    ]


@pytest.mark.parametrize(
    ("fault", "match"),
    [
        ({"userid": "ALICE", "userid_hex": "C1"}, "once"),
        ({"userid_hex": "C1G1"}, "userid_hex"),
        ({"userid_hex": "C1C2C3C4C5C6C7C8C9"}, "userid_hex"),
        ({"userid_hex": "C120C2"}, "userid_hex"),
        ({"userid_hex": "C101"}, "userid_hex"),
        ({"userid_hex": ""}, "userid_hex"),
    ],
)
def test_a_bad_userid_hex_is_refused(fault, match):
    with pytest.raises(ec.Unsupported, match=match):
        _lines(cmd="VERIFY", resp="NORMAL", **fault)


def test_fired_reads_each_side_in_its_own_encoding_and_splits_on_newline_only(tmp_path):
    line = "VERIFY \xc1\x85\xd3@@@ 1 0 0"  # \x85 is a line break to str.splitlines
    cobol, java = tmp_path / "c.txt", tmp_path / "j.txt"
    cobol.write_bytes((line + "\n").encode("latin-1"))
    java.write_bytes((line + "\n").encode("utf-8"))
    assert ec._fired(cobol, "latin-1") == ec._fired(java) == [line]
