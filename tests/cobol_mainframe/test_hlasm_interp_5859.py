"""#5859 slice 4: an independent interpreter (tests/tools/hlasm_interp.py, written from the Principles of Operation and
sharing nothing with det/hlasm.py) cross-checks the HLASM lowering. The oracle proves the det port of the LOWERED COBOL
(design-doc assumption 1); these tests compare the lowering's branch conditions and ZECS002's whole-program end state
against the interpreter, which has no COBOL in it."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import hlasm_interp as H  # noqa: E402

ZECS = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora")) / "zecs" / "Source"
CASE = ROOT / "tests" / "equivalence" / "zecs-zecs002" / "case.json"

PRELUDE = [
    "DFHEISTG DSECT",
    "W_A      DS    CL4",
    "W_B      DS    CL4",
    "W_C      DS    CL1",
    "W_H      DS    H",
    "W_F      DS    F",
    "DFHCA    DSECT",
    "CA_X     DS    CL2",
    "CA_L     EQU   *-CA_X",
]
REGS = [f"R{n}       EQU   {n}" for n in (2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 14)]


def snippet(*code: str) -> str:
    entry = "PROG     DFHEIENT CODEREG=(R12),DATAREG=R10,EIBREG=R11"
    return "\n".join([*PRELUDE, entry, *code, *REGS, "         END   PROG"]) + "\n"


def run(*code: str) -> H.Result:
    return H.Machine(snippet(*code, "         EXEC CICS RETURN")).run(bytes(2))


def taken(setter: list[str], mask: str) -> bool:
    res = run(
        *setter,
        f"         BC    {mask},TAKEN",
        "         LA    R7,0",
        "         B     DONE",
        "TAKEN    DS   0H",
        "         LA    R7,1",
        "DONE     DS   0H",
    )
    return res.regs[7] == 1


# ---- the condition code, bit by bit ------------------------------------------------------------------------------
@pytest.mark.parametrize(("a", "b"), [(0, 0), (1, 2), (2, 1), (4095, 4095), (0, 4095), (4095, 0)])
@pytest.mark.parametrize("mask", [8, 4, 2, 12, 10, 6, 14, 7])
def test_ch_condition_code_masks(a, b, mask):
    setter = [f"         LA    R2,{a}", f"         LA    R3,{b}", "         STH   R3,W_H", "         CH    R2,W_H"]
    cc = 0 if a == b else 1 if a < b else 2
    assert taken(setter, f"B'{mask:04b}'") == bool(mask & (8 >> cc))


def test_cli_and_clc_set_the_logical_condition_code():
    for lit, cc in (("C'A'", 0), ("C'B'", 1), ("C'0'", 2)):  # EBCDIC: A < B < 0 when compared as bytes
        res = run(
            "         MVC   W_C,=C'A'",
            f"         CLI   W_C,{lit}",
            "         BC    B'1000',EQ",
            "         LA    R7,9",
            "EQ       DS   0H",
        )
        assert (res.regs[7] == 0) == (cc == 0)
    assert taken(["         MVC   W_A,=C'ABCD'", "         MVC   W_B,=C'ABCE'", "         CLC   W_A,W_B"], "B'0100'")
    assert taken(["         MVC   W_A,=C'ABCD'", "         MVC   W_B,=C'ABCD'", "         CLC   W_A,W_B"], "B'1000'")


def test_oc_xc_sr_condition_codes():
    assert taken(["         XC    W_F,W_F", "         OC    W_F,W_F"], "B'1000'")
    assert taken(["         MVC   W_A,=X'00000001'", "         OC    W_A,W_A"], "B'0111'")
    assert taken(["         LA    R2,5", "         SR    R2,R2"], "B'1000'")


def test_the_instruction_semantics_the_base64_decoder_leans_on():
    # IC fills only the low byte; SLL drops bits shifted out; SLDL moves them across the even/odd pair; STCM stores the
    # selected bytes of the register in order; TR translates through a table; BAS saves the return address.
    res = run(
        "         SR    R5,R5",
        "         LA    R5,63",
        "         SLL   R5,26",  # 63 << 26 = 0xFC000000
        "         SR    R4,R4",
        "         SLDL  R4,6",  # 6 high bits of R5 move into R4's low bits
        "         STCM  R4,B'0001',W_C",
    )
    assert res.regs[4] == 0x3F and res.regs[5] == 0
    res = run("         LA    R5,1", "         SLL   R5,31", "         SLL   R5,1")
    assert res.regs[5] == 0
    res = run("         LA    R2,4095", "         SLL   R2,20")
    assert res.regs[2] == 0xFFF00000
    res = run("         LA    R3,3", "         BAS   R14,SUB", "         LA    R3,99", "SUB      DS   0H")
    assert res.regs[14] == H.CODE + 8 * 2


def test_mvc_overlap_propagates_byte_by_byte():
    res = run(
        "         MVC   W_A,=C'XYZW'",
        "         MVC   W_A+1(3),W_A",  # destructive overlap: X is smeared across the field (POPS)
        "         MVC   W_B,W_A",
    )
    a = res.mem[H.WS : H.WS + 4]
    assert a.decode(H.EBCDIC) == "XXXX"


def test_unsupported_instruction_is_refused_by_name():
    with pytest.raises(H.Unsupported, match="AR"):
        run("         AR    R2,R3")


# ---- the lowering's branch conditions against the interpreter ------------------------------------------------------
tsl = pytest.importorskip(
    "tree_sitter_language_pack"
)  # the det parser; the ground-truth CI job has no translator extra
from gitgalaxy.tools.cobol_to_java.det import hlasm  # noqa: E402


def _lowered_cond(setter: str, mask: str) -> str:
    entry = "PROG     DFHEIENT CODEREG=(R12),DATAREG=R10,EIBREG=R11"
    body = [setter, f"         BC    {mask},DONE", "DONE     DS    0H", "         EXEC CICS RETURN"]
    text = "\n".join([*PRELUDE[:6], entry, *body, *REGS, "         END   PROG"]) + "\n"
    out = hlasm.lower_text(text, "T.asm")
    m = re.search(r"IF (.*)\n\s+GO TO DONE", out)
    return m.group(1) if m else ("TRUE" if "GO TO DONE" in out else "FALSE")


def _eval(cond: str, env: dict[str, int]) -> bool:
    if cond in ("TRUE", "FALSE"):
        return cond == "TRUE"
    py = cond.replace(" NOT = ", " != ").replace(" = ", " == ")
    py = re.sub(r"[A-Z][A-Z0-9-]+", lambda m: f"v[{m.group(0)!r}]", py)
    return bool(eval(py, {"__builtins__": {}}, {"v": env}))  # noqa: S307 -- our own lowered text, names mapped to ints


@pytest.mark.parametrize("mask", range(16))
def test_lowered_ch_branch_conditions_agree_with_the_interpreter(mask):
    m = f"B'{mask:04b}'"
    try:
        cond = _lowered_cond("         CH    R2,W_H", m)
    except hlasm.Refused:
        assert mask in (1, 14)  # CC 3 alone, and CC 0-2 without CC 3: refused by name, never lowered wrongly
        return
    for a, b in ((0, 0), (1, 2), (2, 1), (4095, 4095), (0, 4095), (4095, 0)):
        setter = [f"         LA    R2,{a}", f"         LA    R3,{b}", "         STH   R3,W_H", "         CH    R2,W_H"]
        assert _eval(cond, {"HL-R2": a, "W-H": b}) == taken(setter, m), (cond, a, b)


# ---- ZECS002 end to end ----------------------------------------------------------------------------------------------
ORACLE = {
    "verified": (
        "30304040C1D3C9C3C5404040E2C5C3D9C5E34040D8E4A7D1D8F0E4F6E4F0E5C4E492E5E4C9C3C187C9C3C18740404040C1D3C9C3C57AE2C5C3D9C5E3404040404040",
        ("VERIFY-PASSWORD", "RETURN"),
    ),
    "userid-not-found": (
        "30384040C2D6C24040404040D7E6F14040404040D892F9C3D693C2E7D4E2C187C9C3C187C9C3C187C9C3C18740404040C2D6C27AD7E6F14040404040404040404040",
        ("VERIFY-PASSWORD", "WRITEQ-TD", "RETURN"),
    ),
    "password-wrong": (
        "30384040C3C1D9D6D3404040C2C1C4D7C1E2E240D8F0C6E2E3F0A6F6D892C6C5E4C5C6E3E4A8C187C9C3C18740404040C3C1D9D6D37AC2C1C4D7C1E2E24040404040",
        ("VERIFY-PASSWORD", "WRITEQ-TD", "RETURN"),
    ),
    "verify-invreq": (
        "30384040C4C1E5C540404040E7E8E94040404040D9C5C6E6D9E397E8E6E59687C9C3C187C9C3C187C9C3C18740404040C4C1E5C57AE7E8E940404040404040404040",
        ("VERIFY-PASSWORD", "WRITEQ-TD", "RETURN"),
    ),
    "userid-eight-chars": (
        "30304040C1C2C3C4C5C6C7C8D7C1E2E2E6D6D9C4D8E4D1C4D9C5E5C7D9F087F6E4C5C6E3E4F184D7E492D88740404040C1C2C3C4C5C6C7C87AD7C1E2E2E6D6D9C440",
        ("VERIFY-PASSWORD", "RETURN"),
    ),
    "userid-over-eight": (
        "30384040C1C2C3C4C5C6C7C8D17AD7E640404040D8E4D1C4D9C5E5C7D9F088D1E29197D8E5A8C187C9C3C18740404040C1C2C3C4C5C6C7C8C9D17AD7E64040404040",
        ("VERIFY-PASSWORD", "WRITEQ-TD", "RETURN"),
    ),
    "password-eight-chars": (
        "30304040C6D9C5C440404040F1F2F3F4F5F6F7F8D993D1C6D9C496A7D491D4F0D5E3E8F3D6C3C187C9C3C18740404040C6D9C5C47AF1F2F3F4F5F6F7F84040404040",
        ("VERIFY-PASSWORD", "RETURN"),
    ),
    "no-colon": (
        "30384040D1E4E2E3C1E4E2C5D5C1D4C5C8C5D9C5E293E5E3E5C5C6E5E4F0E5E2E392C6D5D9E488C6E492E48740404040D1E4E2E3C1E4E2C5D9D5C1D4C5C8C5D9C540",
        ("VERIFY-PASSWORD", "WRITEQ-TD", "RETURN"),
    ),
    "invalid-encoding": (
        "3132404040404040404040404040404040404040D8E4A7D1D8F0E4F6E4F0E5C4E492E5E47E7E7E7E7E7E7E7E40404040C1D3C9C3C57AE2C5C3D9C5E3202020202020",
        ("RETURN",),
    ),
    "commarea-short": (
        "4040404040404040",
        ("ABEND",),
    ),
    "commarea-long": (
        "4040404040404040404040404040404040404040D8E397C3C9C3C187C9C3C187C9C3C187C9C3C187C9C3C1874040404040404040404040404040404040404040404040",
        ("ABEND",),
    ),
}
TD_RECORD = {"VERIFY-PASSWORD": "VERIFY", "WRITEQ-TD": "WRITEQ TD", "RETURN": "RETURN", "ABEND": "ABEND"}


@pytest.mark.skipif(not (ZECS / "ZECS002.asm").is_file(), reason="zecs corpus not fetched (mainframe_corpus.py fetch)")
def test_zecs002_interpreted_end_states_equal_the_oracle_run_of_the_lowering():
    case = json.loads(CASE.read_text(encoding="utf-8"))
    machine_src = (ZECS / "ZECS002.asm").read_text(encoding="latin-1")
    assert set(ORACLE) == {s["name"] for s in case["scenarios"]}
    for sc in case["scenarios"]:
        verify = {f["userid_hex"]: f["resp"] for f in sc.get("faults", []) if f["cmd"] == "VERIFY"}
        res = H.Machine(machine_src).run(
            bytes.fromhex(sc["commarea_hex"]), facts={"transid": case["transid"], "verify": verify}
        )
        commarea, events = ORACLE[sc["name"]]
        assert tuple(e[0] for e in res.events) == tuple(TD_RECORD[e] for e in events), sc["name"]
        if "ABEND" in events:
            assert res.outcome == "ABEND:Z001", sc["name"]
        got, want = res.commarea, bytes.fromhex(commarea)
        if res.outcome == "RETURN":
            # the one byte-level difference: the lowering writes MVC CA_RC,=C'00' as ASCII text (design doc assumption 3,
            # character data is compared for equality only) where z/OS stores EBCDIC. Same characters, other encoding.
            assert got[:2].decode(H.EBCDIC) == want[:2].decode("ascii"), sc["name"]
            got, want = got[2:], want[2:]
        assert got == want, sc["name"]
