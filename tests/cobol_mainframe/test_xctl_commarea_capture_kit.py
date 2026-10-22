"""#5060 / #4816: the CICS capture kit for XCTL of a LINK caller's COMMAREA (tests/tools/xctl_commarea_capture_kit.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import xctl_commarea_capture_kit as K  # noqa: E402


def _run(same: dict[str, bool]) -> str:
    """The output a CICS region would give if each case's target did (True) or did not (False) address the caller's storage."""
    return "".join(f"X39-{c}|{K.expected_area(c, same[c])}\n" for c in K.CASES)


def test_the_emitted_programs_are_deterministic_fixed_format_and_name_every_case():
    drv, mid, tgt = K.emit_driver(), K.emit_middle(), K.emit_target()
    assert (drv, mid, tgt) == (K.emit_driver(), K.emit_middle(), K.emit_target())
    for src in (drv, mid, tgt):
        for line in src.splitlines():
            body = line.lstrip(" ")
            assert len(line) <= 72 and (len(line) - len(body) == 7 or len(line) - len(body) >= 11), line  # area A or B
    for case in K.CASES:
        assert f"'X39-{case}|'" in drv and f"WHEN '{case}'" in mid
    assert drv.count("EXEC CICS LINK PROGRAM('GGXMID')") == len(K.CASES)
    assert drv.count(f"LENGTH({K.LEN})") >= len(K.CASES)
    assert mid.count("EXEC CICS XCTL PROGRAM('GGXTGT')") == len(K.CASES)
    for name in ("COMMAREA(DFHCOMMAREA)", "COMMAREA(CA-PART)", "COMMAREA(ALIAS-AREA)"):
        assert name in mid
    assert "SET ADDRESS OF ALIAS-AREA TO ADDRESS OF DFHCOMMAREA" in mid
    assert f"MOVE '{K.TARGET}' TO TGT-HEAD" in tgt and "RETURN" in tgt


def test_the_group_passed_in_case_p_sits_where_the_verdict_expects_it():
    # CA-HEAD X(6), CA-PART X(8): the part starts at byte offset 6 and holds the MID control at byte offset 9.
    name, off, length = K.CASES["P"]
    assert (name, off, length) == ("CA-PART", 6, 8)
    assert off <= K.CONTROL[1] and K.CONTROL[1] + len(K.CONTROL[0]) <= off + length
    assert "05 CA-HEAD PIC X(6)." in K.emit_middle() and "05 CA-PART PIC X(8)." in K.emit_middle()
    assert f"MOVE '{K.CONTROL[0]}' TO CA-PART(4:3)" in K.emit_middle()


@pytest.mark.parametrize("flags", [(True, True, True), (False, False, False)])
def test_a_uniform_run_is_judged_and_exits_zero(flags, tmp_path):
    same = dict(zip(K.CASES, flags, strict=True))
    out = tmp_path / "sysout.txt"
    out.write_text("DFHAC2206 noise\n" + _run(same), encoding="utf-8")
    want = "same-storage" if flags[0] else "copy"
    res = K.judge(out.read_text(encoding="utf-8"))
    assert res == {"W": want, "P": want, "A": want, "overall": want}
    assert K.main(["verdict", str(out)]) == 0


def test_a_mixed_run_is_reported_per_case_and_is_not_a_verdict(tmp_path):
    res = K.judge(_run({"W": True, "P": False, "A": True}))
    assert res == {"W": "same-storage", "P": "copy", "A": "same-storage", "overall": "mixed"}
    out = tmp_path / "sysout.txt"
    out.write_text(_run({"W": True, "P": False, "A": True}), encoding="utf-8")
    assert K.main(["verdict", str(out)]) == 1


def test_a_run_that_does_not_show_the_control_or_a_failed_xctl_is_invalid():
    good = _run({"W": False, "P": False, "A": False})
    assert K.judge(good)["overall"] == "copy"
    # a missing line, a missing MID control, a failed XCTL (ERR in the tail) and a changed byte are never guessed at
    missing = "".join(line + "\n" for line in good.splitlines() if "X39-A|" not in line)
    no_control = good.replace(K.CONTROL[0], "...")
    failed = good.replace("X39-W|W........MID........", "X39-W|W........MID.ERR....")
    odd = good.replace("X39-P|P", "X39-P|Q")
    for bad, case in ((missing, "A"), (no_control, "W"), (failed, "W"), (odd, "P")):
        res = K.judge(bad)
        assert res[case] == "invalid" and res["overall"] == "invalid", (case, res)


def test_emit_writes_the_three_programs_and_the_readme(tmp_path):
    paths = K.emit(tmp_path / "kit")
    assert [p.name for p in paths] == ["GGXDRV.cbl", "GGXMID.cbl", "GGXTGT.cbl", "README.md"]
    assert (tmp_path / "kit" / "GGXMID.cbl").read_text(encoding="utf-8") == K.emit_middle()
