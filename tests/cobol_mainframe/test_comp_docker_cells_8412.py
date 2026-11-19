"""COMP boundary cells that need the two runtimes (#8412, slice 3 after #8663 / #8666): a binary or packed item read
through a sign it was not written with, and a binary item driven past its PICTURE, each run through GnuCOBOL (Docker)
and the det port (JDK 17) and compared line by line.

IBM is the reference, GnuCOBOL the instrument (`.claude/rules/mainframe-evidence-policy.md`).

* NUMPROC(PFD): "the compiler assumes that the sign in your data is one of three preferred signs" -- C signed positive,
  D signed negative, F unsigned (Enterprise COBOL for z/OS 6.4 Programming Guide, "NUMPROC"; Language Reference,
  "Sign representation of zoned and packed-decimal data"). GnuCOBOL has no PFD: it reads every sign as NOPFD does.
  So a preferred sign is equal on the oracle, the port under NOPFD and the port under PFD; a non-preferred one is read
  by the oracle and by the port under NOPFD (equal), and REFUSED by name by the port under PFD, never read as a wrong
  value (the register C5 stop, `Codec.nonPreferredSign`).
* TRUNC(BIN): a COMP / COMP-4 / BINARY receiver keeps the full halfword / fullword / doubleword, not the PICTURE's
  digits (6.4 Programming Guide, "TRUNC"). `cobc -std=ibm` alone is TRUNC(BIN) (`-fbinary-truncate` is STD), and the det
  port runs both as the oracle does. The binary-store test (#4684) owns the unsigned-below-zero wrap (declared C4) and
  the per-statement native-add choice; this one drives every width edge through ADD / MULTIPLY / DIVIDE / COMPUTE with a
  full-width intermediate, and reads the result back through its bytes.

Every cell is equal on both runtimes or the test names the one that differs. Needs Docker and a JDK 17
(`EQUIVALENCE_E2E=1`, `JAVA_HOME` / `JDK_17`); the rest of the cells in the #8412 COMP matrix (layout and image,
option resolution) need neither (`test_comp_layout_matrix_8412.py`)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_det_programs as T  # noqa: E402

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker") or T._java() is None,
        reason="needs Docker and a JDK 17 (EQUIVALENCE_E2E=1, JAVA_HOME / JDK_17)",
    ),
    pytest.mark.slow(reason="each program runs on GnuCOBOL in Docker and on the det port after a javac (#8412)"),
]

# ---- NUMPROC(PFD): the sign nibble a boundary hands over ----------------------------------------------------------
# (tag, item, USAGE-and-PICTURE, bytes written through the X redefinition)
ZS, ZU, PS, PU = "S9(3)", "9(3)", "S9(3) COMP-3", "9(3) COMP-3"
PREFERRED = [
    ("ZSC", ZS, "'12C'"),  # C overpunch: positive
    ("ZSL", ZS, "'12L'"),  # D overpunch: negative
    ("ZUF", ZU, "'123'"),  # F: unsigned
    ("PSC", PS, "X'123C'"),
    ("PSD", PS, "X'123D'"),
    ("PUF", PU, "X'123F'"),
]
NON_PREFERRED = [
    ("ZSF", ZS, "'123'"),  # F on a signed item
    ("ZUC", ZU, "'12C'"),  # an overpunch on an unsigned item
    ("ZSN", ZS, "'00}'"),  # negative zero
    ("PSF", PS, "X'123F'"),  # F on a signed item
    ("PUC", PU, "X'123C'"),  # C on an unsigned item
    ("PSZ", PS, "X'000D'"),  # negative zero
]


def _sign_program(cells: list[tuple[str, str, str]]) -> str:
    data = ["01 EW PIC -(8)9."]
    proc = []
    for tag, pic, lit in cells:
        width = 3 if "COMP-3" not in pic else 2
        data += [f"01 V{tag} PIC {pic}.", f"01 X{tag} REDEFINES V{tag} PIC X({width})."]
        proc += [f"MOVE {lit} TO X{tag}", f"MOVE V{tag} TO EW", f"DISPLAY '{tag} ' EW"]
    return T.program("SIGNS", data, proc)


def _lines(out: str) -> dict[str, str]:
    return {x.split()[0]: " ".join(x.split()[1:]) for x in out.splitlines() if x.strip()}


def test_preferred_signs_are_read_alike_by_the_oracle_and_the_port_under_either_numproc(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    src = _sign_program(PREFERRED)
    (tmp_path / "o").mkdir()
    oracle = _lines(T._cobol(src, tmp_path / "o"))
    assert oracle == {"ZSC": "123", "ZSL": "-123", "ZUF": "123", "PSC": "123", "PSD": "-123", "PUF": "123"}
    for pfd in (False, True):
        (tmp_path / f"p{pfd}").mkdir()
        assert _lines(T._java_run("signs", src, tmp_path / f"p{pfd}", numproc_pfd=pfd)) == oracle, pfd


def test_a_non_preferred_sign_is_read_alike_under_nopfd_by_the_oracle_and_the_port(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    src = _sign_program(NON_PREFERRED)
    (tmp_path / "o").mkdir()
    (tmp_path / "p").mkdir()
    oracle = _lines(T._cobol(src, tmp_path / "o"))
    port = _lines(T._java_run("signs", src, tmp_path / "p"))
    assert port == oracle, (port, oracle)


@pytest.mark.parametrize(("tag", "pic", "lit"), NON_PREFERRED, ids=[c[0] for c in NON_PREFERRED])
def test_a_non_preferred_sign_is_refused_by_name_under_pfd_never_misread(tag, pic, lit, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    with pytest.raises(subprocess.CalledProcessError) as e:
        T._java_run("signs", _sign_program([(tag, pic, lit)]), tmp_path, numproc_pfd=True)
    assert "NUMPROC(PFD)" in e.value.stderr, e.value.stderr
    assert tag not in e.value.stdout  # nothing was displayed: no wrong value escaped


# ---- TRUNC(BIN): the full width ----------------------------------------------------------------------------------
DATA = [
    "01 SH PIC S9(4) COMP.",
    "01 SHX REDEFINES SH PIC X(2).",
    "01 UH PIC 9(4) COMP-4.",
    "01 SW PIC S9(9) BINARY.",
    "01 SWX REDEFINES SW PIC X(4).",
    "01 UW PIC 9(9) COMP.",
    "01 SQ PIC S9(18) COMP.",
    "01 UQ PIC 9(18) COMP-4.",
    "01 EW PIC -(20)9.",
]
# (tag, receiver, statement lines); the receiver starts at the value given
CASES = [
    ("H1", "SH", "32767", ["ADD 1 TO SH"]),  # past the halfword
    ("H2", "SH", "30000", ["MULTIPLY 4 BY SH"]),
    ("H3", "SH", "30000", ["COMPUTE SH = SH * 4 / 2"]),  # a full-width intermediate, then stored
    ("H4", "SH", "0", ["COMPUTE SH = 40000"]),
    ("H5", "SH", "0", ["MOVE 12345 TO SH"]),  # past the PICTURE, inside the halfword
    ("H6", "SH", "20000", ["DIVIDE 3 INTO SH"]),
    ("H7", "UH", "65535", ["ADD 1 TO UH"]),
    ("H8", "UH", "0", ["COMPUTE UH = 300 * 300"]),
    ("H9", "UH", "0", ["MOVE 99999 TO UH"]),
    ("W1", "SW", "2147483647", ["ADD 1 TO SW"]),
    ("W2", "SW", "0", ["COMPUTE SW = 3000000 * 1000"]),
    ("W3", "SW", "0", ["MOVE 1234567890 TO SW"]),  # past 9 digits, inside the fullword
    ("W4", "UW", "4294967295", ["ADD 1 TO UW"]),
    ("W5", "UW", "0", ["COMPUTE UW = 70000 * 70000"]),
    ("D1", "SQ", "0", ["COMPUTE SQ = 999999999999 * 999999"]),
    ("D2", "SQ", "999999999999999999", ["ADD 1 TO SQ"]),
    ("D3", "UQ", "0", ["MOVE 1234567890123456789 TO UQ"]),
]


def _bin_program() -> str:
    proc = []
    for tag, recv, start, stmt in CASES:
        proc += [f"MOVE {start} TO {recv}", *stmt, f"MOVE {recv} TO EW", f"DISPLAY '{tag} ' EW"]
    # the bytes behind the value, as a COMMAREA / container / record would carry them: the full halfword / fullword
    # (TRUNC(BIN)) or the PICTURE's digits (TRUNC(STD))
    for tag, recv, value, full, pic in (
        ("BH", "SH", "12345", "3039", "0929"),
        ("BW", "SW", "1234567890", "499602D2", "0DFB38D2"),
    ):
        proc += [f"MOVE {value} TO {recv}", f"IF {recv}X = X'{full}'", f"  DISPLAY '{tag} FULL'", "ELSE",
                 f"  IF {recv}X = X'{pic}'", f"    DISPLAY '{tag} PIC'", "  ELSE", f"    DISPLAY '{tag} OTHER'",
                 "  END-IF", "END-IF"]  # fmt: skip
    return T.program("TRUNCBIN", DATA, proc)


@pytest.mark.parametrize("trunc", ["bin", "std"])
def test_a_binary_item_driven_past_its_picture_is_stored_as_the_oracle_stores_it(trunc, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    (tmp_path / "o").mkdir()
    (tmp_path / "p").mkdir()
    src = _bin_program()
    std = trunc == "std"
    oracle = T._cobol(src, tmp_path / "o", flags="-fbinary-truncate" if std else "")
    port = T._java_run("truncbin", src, tmp_path / "p", trunc_std=std)
    o, p = oracle.splitlines(), port.splitlines()
    assert o[-2:] == (
        ["BH PIC", "BW PIC"] if std else ["BH FULL", "BW FULL"]
    )  # IBM: STD keeps the digits, BIN the bytes
    assert len(o) == len(CASES) + 2
    assert p == o, [(a, b) for a, b in zip(o, p, strict=True) if a != b]
