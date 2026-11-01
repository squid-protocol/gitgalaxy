"""#5078 (register X52): the update TOKEN class -- READ UPDATE TOKEN / REWRITE TOKEN / DELETE TOKEN / UNLOCK TOKEN --
translated by the stub's harness (equivalence_cics.translate_command) and the det port (Cics.command), and the members
refused by name. The runtimes' answers (a valid, an invalid, a reused token ...) are tests/cics_crucible/
test_update_token_runtimes_5078.py's."""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "tools"))
import equivalence_cics as ec  # noqa: E402
from test_det_translate import _LenCics  # noqa: E402

from gitgalaxy.standards.cics.commands import COMMANDS as SPEC  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402


def test_the_stub_reads_for_update_under_a_token_and_hands_it_to_the_program():
    got = ec.translate_command("READ FILE('CUSTOMER') RIDFLD(K) INTO(REC) TOKEN(WS-TOKEN) RESP(R)")
    assert got[:3] == ["MOVE 'CUSTOMER' TO GG-NAME1", "MOVE 'UPDATE TOKEN' TO GG-FLAGS", "MOVE LENGTH OF REC TO GG-LEN"]
    at = got.index("IF GG-RESP = 0")
    assert got[at : at + 3] == ["IF GG-RESP = 0", "    MOVE GG-NUM TO WS-TOKEN", "END-IF"]  # only a read that found one


def test_the_stub_rewrites_deletes_and_unlocks_by_token():
    rw = ec.translate_command("REWRITE FILE('F') FROM(REC) TOKEN(T)")
    assert rw[:4] == [
        "MOVE 'F' TO GG-NAME1",
        "MOVE 'TOKEN' TO GG-FLAGS",
        "MOVE T TO GG-NUM",
        "CALL 'GGCREWR' USING GG-CICS",
    ]
    dl = ec.translate_command("DELETE FILE('F') TOKEN(T)")
    assert dl[:4] == [
        "MOVE 'F' TO GG-NAME1",
        "MOVE 'TOKEN' TO GG-FLAGS",
        "MOVE T TO GG-NUM",
        "CALL 'GGCDELT' USING GG-CICS",
    ]
    ul = ec.translate_command("UNLOCK FILE('F') TOKEN(T)")
    assert ul[:4] == [
        "MOVE 'F' TO GG-NAME1",
        "MOVE T TO GG-NUM",
        "MOVE 'TOKEN' TO GG-FLAGS",
        "CALL 'GGCUNLK' USING GG-CICS",
    ]


def test_write_massinsert_is_refused_by_name():  # #5079: the other thing a tokenless UNLOCK may match (IBM)
    with pytest.raises(ec.Unsupported):
        ec.translate_command("WRITE FILE('F') FROM(REC) RIDFLD(K) MASSINSERT")
    with pytest.raises(C.CicsError):
        _LenCics().command("WRITE FILE('KSDS') FROM(REC) RIDFLD(KEY) MASSINSERT", "")


def test_unlock_without_a_token_releases_the_files_hold_on_the_stub_and_the_det_port():  # #5079
    ul = ec.translate_command("UNLOCK FILE('F') RESP(R)")
    assert ul[:3] == ["MOVE 'F' TO GG-NAME1", "MOVE SPACES TO GG-FLAGS", "CALL 'GGCUNLK' USING GG-CICS"]
    ul = ec.translate_command("UNLOCK DATASET('F')")
    assert ul[:3] == ["MOVE 'F' TO GG-NAME1", "MOVE SPACES TO GG-FLAGS", "CALL 'GGCUNLK' USING GG-CICS"]
    for text in ("UNLOCK FILE('KSDS') RESP(R)", "UNLOCK DATASET('KSDS')"):
        assert any("task.unlock('KSDS'.stripTrailing())" in x for x in _LenCics().command(text, ""))


@pytest.mark.parametrize(
    "text",
    [
        "DELETE FILE('F') RIDFLD(K) TOKEN(T)",  # IBM does not say which record goes
        "DELETE FILE('F') RIDFLD(K) KEYLENGTH(2) GENERIC TOKEN(T)",
        "READNEXT FILE('F') INTO(R) RIDFLD(K) UPDATE TOKEN(T)",  # a browse for update: RLS only
        "READPREV FILE('F') INTO(R) RIDFLD(K) UPDATE",
        "UNLOCK FILE('F') TOKEN(T) SYSID('ABCD')",
    ],
)
def test_what_the_token_class_leaves_open_is_refused_by_name_on_the_stub_side(text):
    with pytest.raises(ec.Unsupported):
        ec.translate_command(text)


def test_the_det_port_holds_under_a_token_and_stores_it_into_the_field():
    out = _LenCics().command("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) TOKEN(TK) RESP(R)", "")
    assert (
        out[1] == "CicsTask.FileRead<byte[]> read1 = task.read('KSDS'.stripTrailing(), () -> store(F).find(rec2));"
    )  # no tokenless hold
    assert not any("heldKey" in line for line in out)
    assert any("task.holdToken('KSDS'.stripTrailing(), store(F).keyOf(read1.record()))" in line for line in out)
    assert any(line.strip().startswith("STORE(TK, BigDecimal.valueOf(") for line in out)


def test_the_det_port_token_read_implies_update_with_length_and_search():
    out = _LenCics().command(
        "READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(6) GENERIC GTEQ TOKEN(TK) LENGTH(VL)", ""
    )
    assert "task.readSearch('KSDS'.stripTrailing(), false, " in " ".join(out)  # held by its token, not the file's hold
    assert "DetCics.readInto(f_REC, read1.record(), INT(VL), true)" in " ".join(
        out
    )  # LENGERR refused: held or not unsaid


def test_the_det_port_rewrites_deletes_and_unlocks_by_token():
    c = _LenCics()
    assert any("task.rewriteToken('KSDS'.stripTrailing(), INT(TK), store(F).keyOf(" in x
               for x in c.command("REWRITE FILE('KSDS') FROM(REC) TOKEN(TK) RESP(R)", ""))  # fmt: skip
    assert any("task.deleteToken('KSDS'.stripTrailing(), INT(TK), k -> store(F).remove(k))" in x
               for x in _LenCics().command("DELETE FILE('KSDS') TOKEN(TK)", ""))  # fmt: skip
    assert any("task.unlockToken('KSDS'.stripTrailing(), INT(TK))" in x
               for x in _LenCics().command("UNLOCK FILE('KSDS') TOKEN(TK)", ""))  # fmt: skip


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("DELETE FILE('KSDS') RIDFLD(KEY) TOKEN(TK)", "together"),
        ("DELETE FILE('KSDS') RIDFLD(KEY) KEYLENGTH(2) GENERIC TOKEN(TK)", "together"),
        ("READNEXT FILE('KSDS') INTO(REC) RIDFLD(KEY) UPDATE TOKEN(TK)", "RLS"),
        ("READPREV FILE('KSDS') INTO(REC) RIDFLD(KEY) UPDATE", "RLS"),
        ("UNLOCK FILE('KSDS') TOKEN(TK) SYSID('ABCD')", "SYSID"),
    ],
)
def test_the_det_port_refuses_what_the_token_class_leaves_open(text, why):
    with pytest.raises(C.CicsError, match=why):
        _LenCics().command(text, "")


def test_the_spec_models_every_token_class_member():
    for verb in ("READ", "REWRITE", "DELETE", "UNLOCK"):
        assert "TOKEN" in SPEC[verb].options
    assert SPEC["UNLOCK"].status == "modelled" and SPEC["UNLOCK"].register == "X52"
    for verb in ("READNEXT", "READPREV"):
        assert "TOKEN" in SPEC[verb].refused and "UPDATE" in SPEC[verb].refused
