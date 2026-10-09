"""#4749: a typed (lifted, det-port B3) binary item stores what its byte storage would, under every TRUNC mode.

IBM is the reference, GnuCOBOL the instrument (oracle_assumptions.md C1). TRUNC(STD): a COMP / COMP-4 / BINARY
receiver keeps its PICTURE's digits (cobc -fbinary-truncate); TRUNC(BIN): it keeps its halfword / fullword /
doubleword (cobc -fnotrunc); COMP-5 keeps its bytes under every TRUNC; TRUNC(OPT) computes as STD and stops by name
where a value past the PICTURE would be stored (#4706). A lifted item is a Java long, so every store into it goes
through one place (Gen.store_bin / Cobol.binary) -- a literal MOVE folded at translation time under the program's
mode, an item MOVE and an arithmetic result at run time -- and a synced group's bytes are written from it as they
are (Cobol.putBinary), never re-truncated. Each program runs in bytes and typed modes: typed must equal bytes, and
both the oracle.

The runtime tests need a JDK 17 (JAVA_HOME / JDK_17); the oracle comparison also Docker (EQUIVALENCE_E2E=1)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

E2E = os.environ.get("EQUIVALENCE_E2E") == "1" and shutil.which("docker") is not None

# receivers and senders: signed / unsigned, COMP / COMP-4 / BINARY / COMP-5, halfword / fullword / doubleword
DATA = [
    "01 ZH PIC S9(3) COMP.",
    "01 ZU PIC 9(3) COMP-4.",
    "01 ZF PIC S9(7) BINARY.",
    "01 ZV PIC 9(5) COMP.",
    "01 ZD PIC S9(12) COMP.",
    "01 ZQ PIC S9(15) BINARY.",
    "01 Z5 PIC S9(3) COMP-5.",
    "01 Z6 PIC 9(3) COMP-5.",
    "01 YH PIC S9(4) COMP.",
    "01 YF PIC S9(9) BINARY.",
    "01 YD PIC S9(18) COMP-4.",
    "01 Y5 PIC S9(4) COMP-5.",
    "01 Y6 PIC 9(4) COMP-5.",
    "01 EW PIC -(20)9.",
]
RECEIVERS = ["ZH", "ZU", "ZF", "ZV", "ZD", "ZQ", "Z5", "Z6"]
SENDERS = ["YH", "YF", "YD", "Y5", "Y6"]


def _show(tag: str, item: str) -> list[str]:
    return [f"MOVE {item} TO EW", f"DISPLAY '{tag} ' EW"]


def _literal_moves() -> list[str]:
    out = []
    for lit in ("1234", "-1234", "99999", "-70000", "123456789", "-9876543210123", "12.9"):
        for r in RECEIVERS:
            out += [f"MOVE {lit} TO {r}", *_show(f"L{lit}-{r}", r)]
    return out


def _item_moves() -> list[str]:
    out = []
    for vals in (("1234", "123456789", "123456789012345678", "30000", "40000"),
                 ("-4321", "-987654321", "-987654321098765432", "-30000", "65535")):  # fmt: skip
        out += [f"MOVE {v} TO {s}" for v, s in zip(vals, SENDERS, strict=True)]
        for s in SENDERS:
            for r in RECEIVERS:
                out += [f"MOVE {s} TO {r}", *_show(f"I{vals[0]}-{s}-{r}", r)]
    return out


def _arithmetic() -> list[str]:
    # (no unsigned target of ADD / SUBTRACT ... FROM: there cobc wraps where IBM keeps the absolute value, C4 #4684)
    out = ["MOVE 999 TO ZH", "ADD 2 TO ZH", *_show("A1", "ZH"),
           "MOVE 100 TO ZH", "SUBTRACT 300 FROM ZH", *_show("A2", "ZH"),
           "MOVE 123456789 TO YF", "COMPUTE ZF = YF * 7", *_show("A3", "ZF"),
           "COMPUTE ZV = YF / 3", *_show("A4", "ZV"),
           "COMPUTE Z5 = YF / 100000", *_show("A5", "Z5"),
           "MOVE 30000 TO Y5", "COMPUTE ZQ = Y5 * Y5 * Y5 * Y5", *_show("A6", "ZQ")]  # fmt: skip
    return out


def _program(name: str, proc: list[str], card: str = "", extra: tuple[str, ...] = ()) -> str:
    src = [*([card] if card else []), "       IDENTIFICATION DIVISION.", f"       PROGRAM-ID. {name}.", "       DATA DIVISION.",
           "       WORKING-STORAGE SECTION.", *(f"       {x}" for x in (*DATA, *extra)), "       PROCEDURE DIVISION.",
           *(f"           {x}" for x in proc), "           GOBACK."]  # fmt: skip
    assert all(len(x) <= 72 for x in src)
    return "\n".join(src) + "\n"


# mode -> (the program's card, the oracle's cobc flag, _java_run's runtime switch)
MODES = {
    "STD": ("       PROCESS TRUNC(STD)", "-fbinary-truncate", {"trunc_std": True}),
    "BIN": ("       PROCESS TRUNC(BIN)", "-fnotrunc", {}),
}


def _jdk_or_skip():
    pytest.importorskip("tree_sitter_language_pack")
    import test_det_programs as T

    if T._java() is None:
        pytest.skip("needs a JDK 17 (JAVA_HOME / JDK_17)")
    return T


def _dir(root: Path, name: str) -> Path:
    (root / name).mkdir()
    return root / name


def _lifted(src: str, work: Path, groups: bool = False) -> set[str]:
    """The items the typed translation holds as Java longs."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (work / "probe.cbl").write_text(src)
    (work / "project").mkdir()
    r = P.translate(work / "probe.cbl", [], "public class ProbeService {\n}\n", "com.example", None, work / "project",
                    typed=True, groups=groups)  # fmt: skip
    return set(re.findall(r"private long \w+;  // ([\w-]+) PIC", r.java))


def _three(T, name: str, src: str, card: str, flag: str, run: dict, tmp: Path, groups: bool = False,
           raw: bool = False):  # fmt: skip
    """bytes, typed and (with Docker) the oracle's output of `src` under the card's TRUNC."""
    full = card + "\n" + src
    by = T._java_run(name, full, _dir(tmp, "bytes"), False, raw=raw, **run)
    ty = T._java_run(name, full, _dir(tmp, "typed"), True, groups=groups, raw=raw, **run)
    cob = None
    if E2E:
        cob = T._cobol(src, _dir(tmp, "cobol"), raw=raw, flags=flag)  # the card is the flag
    return by, ty, cob


def _lines(out: str) -> list[str]:
    """The program's DISPLAY lines (a tag and a number), without the oracle's compile-time chatter (cobc and the
    C compiler warn of a literal past an item's PICTURE or bytes)."""
    return [" ".join(x.split()) for x in out.splitlines() if re.fullmatch(r"[A-Z][\w.-]* +-?\d+", x.strip())]


@pytest.mark.parametrize("mode", ["STD", "BIN"])
@pytest.mark.parametrize("part", ["literal", "item", "arithmetic"])
def test_typed_binary_stores_equal_bytes_and_the_oracle(mode, part, tmp_path):
    T = _jdk_or_skip()
    proc = {"literal": _literal_moves, "item": _item_moves, "arithmetic": _arithmetic}[part]()
    src = _program("LIFTB", proc)
    card, flag, run = MODES[mode]
    assert set(RECEIVERS) <= _lifted(card + "\n" + src, _dir(tmp_path, "probe"))  # the typed run is typed
    by, ty, cob = _three(T, "liftb", src, card, flag, run, tmp_path)
    assert len(_lines(by)) == sum(x.startswith("DISPLAY") for x in proc)
    assert _lines(ty) == _lines(by)
    if cob is not None:
        assert _lines(by) == _lines(cob)


# the issue's two cases, pinned (IBM TRUNC(STD): the PICTURE's digits)
@pytest.mark.parametrize("typed", [False, True])
def test_the_issue_cases_truncate_to_the_picture(typed, tmp_path):
    T = _jdk_or_skip()
    src = MODES["STD"][0] + "\n" + _program("LIFTI", ["MOVE 12345 TO ZH", *_show("C1", "ZH"),
                                                      "MOVE 1234 TO YH", "MOVE YH TO ZH", *_show("C2", "ZH"),
                                                      "MOVE -1234 TO YH", "MOVE YH TO ZU", *_show("C3", "ZU")])  # fmt: skip
    out = T._java_run("lifti", src, tmp_path, typed, trunc_std=True)
    assert _lines(out) == ["C1 345", "C2 234", "C3 234"]


GROUP_DATA = ["01 G.", "   05 GA PIC 9(4) COMP.", "   05 GB PIC S9(4) COMP.", "   05 GX PIC X(2).", "01 H PIC X(6)."]


@pytest.mark.parametrize("mode", ["STD", "BIN"])
def test_a_synced_groups_bytes_are_not_re_truncated(mode, tmp_path):
    """A group MOVE leaves a binary item's bytes past its PICTURE (X'FFFF' in a 9(4) COMP: 65535); writing the typed
    field back into the group's bytes before the next whole-group use must keep them as they are."""
    T = _jdk_or_skip()
    src = _program("LIFTG", ["MOVE HIGH-VALUES TO G", "MOVE G TO H", "DISPLAY H",
                             "MOVE GA TO EW", "DISPLAY 'GA ' EW", "MOVE GB TO EW", "DISPLAY 'GB ' EW",
                             "MOVE G TO H", "DISPLAY H"], extra=tuple(GROUP_DATA))  # fmt: skip
    card, flag, run = MODES[mode]
    assert {"GA", "GB"} <= _lifted(card + "\n" + src, _dir(tmp_path, "probe"), groups=True)
    by, ty, cob = _three(T, "liftg", src, card, flag, run, tmp_path, groups=True, raw=True)
    assert ty == by
    assert b"\xff" * 6 in by
    if cob is not None:
        assert by == cob


@pytest.mark.parametrize("typed", [False, True])
def test_trunc_opt_a_synced_groups_bytes_do_not_stop(typed, tmp_path):
    """Writing a typed field back into its group's bytes stores no new value: TRUNC(OPT)'s stop is not reached."""
    T = _jdk_or_skip()
    src = _program("LIFTO", ["MOVE HIGH-VALUES TO G", "MOVE G TO H", "MOVE G TO H", "DISPLAY 'DONE'"],
                   "       PROCESS TRUNC(OPT)", tuple(GROUP_DATA))  # fmt: skip
    out = T._java_run("lifto", src, tmp_path, typed, groups=True, trunc_opt=True)
    assert "DONE" in out


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize(
    ("stmt", "said"),
    [
        ("MOVE 1234 TO ZH", "1234 into a signed 3-digit binary item"),
        ("MOVE 1234 TO YH MOVE YH TO ZU", "1234 into a 3-digit binary item"),
        ("MOVE 30000 TO Y5 MOVE Y5 TO YH", "30000 into a signed 4-digit binary item"),
    ],
)
def test_trunc_opt_stops_on_a_typed_move_past_the_picture(typed, stmt, said, tmp_path):
    T = _jdk_or_skip()
    src = _program("LIFTN", ["DISPLAY 'BEFORE'", stmt, "DISPLAY 'AFTER'"], "       PROCESS TRUNC(OPT)")
    with pytest.raises(subprocess.CalledProcessError) as e:
        T._java_run("liftn", src, tmp_path, typed, trunc_opt=True)
    assert "TRUNC(OPT): value exceeds PICTURE; IBM result unpredictable" in e.value.stderr, e.value.stderr
    assert said in e.value.stderr, e.value.stderr
    assert "BEFORE" in e.value.stdout and "AFTER" not in e.value.stdout


@pytest.mark.parametrize("typed", [False, True])
def test_trunc_opt_conforming_typed_moves_are_stds(typed, tmp_path):
    T = _jdk_or_skip()
    proc = ["MOVE 123 TO ZH", *_show("O1", "ZH"), "MOVE 999 TO YH", "MOVE YH TO ZU", *_show("O2", "ZU"),
            "MOVE -999 TO Y5", "MOVE Y5 TO ZH", *_show("O3", "ZH"), "MOVE 12345 TO Z5", *_show("O4", "Z5"),
            "MOVE -77 TO YF", "MOVE YF TO ZV", *_show("O5", "ZV")]  # fmt: skip
    opt = T._java_run("lifto", _program("LIFTO", proc, "       PROCESS TRUNC(OPT)"), _dir(tmp_path, "o"), typed,
                      trunc_opt=True)  # fmt: skip
    std = T._java_run("lifto", _program("LIFTO", proc, "       PROCESS TRUNC(STD)"), _dir(tmp_path, "s"), typed,
                      trunc_std=True)  # fmt: skip
    assert _lines(opt) == _lines(std) == ["O1 123", "O2 999", "O3 -999", "O4 12345", "O5 77"]
