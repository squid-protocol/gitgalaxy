"""A result stored in a binary receiver past its PICTURE or its bytes, without ON SIZE ERROR (#4684,
oracle_assumptions C1 / C4), as the oracle (GnuCOBOL 3.1.2 `-std=ibm`) stores it under TRUNC(BIN) (`-std=ibm`
alone) and TRUNC(STD) (`-fbinary-truncate`, IBM's default and the CICS cases').

Measured: libcob's decimal store keeps a binary item's 2 / 4 / 8 bytes under TRUNC(BIN) (a signed one wraps, an
unsigned one takes the absolute value first) and the PICTURE's digits under TRUNC(STD) -- the det runtime does the
same. cobc compiles ADD / SUBTRACT ... TO / FROM an unsigned binary item of no decimal places, with one operand that
fits a C int and no ROUNDED or SIZE ERROR phrase, to native integer arithmetic instead (cb_build_optim_add / _sub):
a result below zero wraps modulo 2 ** bits (1 - 3 is 65534 in a halfword) where the decimal store keeps 2; COMP-5
always, COMP / COMP-4 / BINARY only under TRUNC(BIN). The det port follows (gen.native_add, Cobol.storeNative).
The codegen tests need no Docker; the end-to-end tests run each program through GnuCOBOL and the det port
(EQUIVALENCE_E2E=1, Docker and a JDK 17)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

DATA = [
    "01 UH PIC 9(4) COMP.",
    "01 UW PIC 9(9) BINARY.",
    "01 UD PIC 9(18) COMP-4.",
    "01 NH PIC 9(4) COMP-5.",
    "01 NW PIC 9(9) COMP-5.",
    "01 SH PIC S9(4) COMP.",
    "01 Q8 PIC V9(4) COMP.",
    "01 K7 PIC S9(4) COMP VALUE 7.",
    "01 KM PIC S9(4) COMP VALUE -5.",
    "01 D0 PIC 9(3) VALUE 7.",
    "01 P0 PIC S9(7) COMP-3 VALUE 98765.",
    "01 DT PIC 9(10) VALUE 7.",
    "01 EW PIC -(20)9.9(4).",
]

# (tag, receivers, statement lines): each receiver starts at 1, then is shown
CASES = [
    # cobc's native ADD / SUBTRACT: an unsigned result below zero wraps (COMP-5 always, the rest under TRUNC(BIN))
    ("W1", ["UH"], ["SUBTRACT 3 FROM UH"]),
    ("W2", ["UW"], ["ADD -3 TO UW"]),
    ("W3", ["UD"], ["SUBTRACT K7 FROM UD"]),
    ("W4", ["NH"], ["SUBTRACT D0 FROM NH"]),
    ("W5", ["NW"], ["SUBTRACT P0 FROM NW"]),
    ("W6", ["UH"], ["ADD KM TO UH"]),
    ("W7", ["UH"], ["SUBTRACT 3 4 FROM UH"]),  # a list of literals is folded into one
    ("W8", ["UH", "NH"], ["ADD -3 TO UH NH"]),
    ("W9", ["NH"], ["SUBTRACT 3 FROM NH", "  NOT ON SIZE ERROR DISPLAY 'W9 N'", "END-SUBTRACT"]),
    # libcob's decimal store: the absolute value
    ("A1", ["UH"], ["SUBTRACT 3 FROM UH ROUNDED"]),
    ("A2", ["UH"], ["SUBTRACT 3 FROM UH", "  ON SIZE ERROR DISPLAY 'A2 Y'", "END-SUBTRACT"]),
    ("A3", ["UH"], ["SUBTRACT 3.0 FROM UH"]),
    ("A4", ["UH"], ["SUBTRACT DT FROM UH"]),  # 10 digits: past a C int
    ("A5", ["UH"], ["SUBTRACT D0 K7 FROM UH"]),
    ("A6", ["UW"], ["SUBTRACT 2147483648 FROM UW"]),
    ("A7", ["UH"], ["COMPUTE UH = UH - 3"]),
    ("A8", ["UH"], ["SUBTRACT 3 FROM 1 GIVING UH"]),
    ("A9", ["UH"], ["SUBTRACT 3 FROM UH", "  NOT ON SIZE ERROR DISPLAY 'A9 N'", "END-SUBTRACT"]),
    # past the PICTURE or the bytes: TRUNC(BIN) wraps at the bytes, TRUNC(STD) keeps the PICTURE's digits
    ("S1", ["SH"], ["SUBTRACT 40000 FROM SH"]),
    ("O1", ["UH"], ["ADD 70000 TO UH"]),
    ("O2", ["UH"], ["COMPUTE UH = 123456"]),
    ("O3", ["UW"], ["COMPUTE UW = P0 * P0 * 7"]),
    ("O4", ["NH"], ["ADD 70000 TO NH"]),
    ("M1", ["UH"], ["MOVE P0 TO UH"]),
    # the issue's case: ARITHMETIC-OSVS intermediates (#4287) into an unsigned scaled receiver
    ("I1", ["Q8"], ["SUBTRACT 3 D0 P0 FROM Q8"]),
]


def program() -> str:
    proc = []
    for tag, recv, stmt in CASES:
        proc.append(f"MOVE 1 TO {' '.join(recv)}")
        proc += stmt
        for r in recv:
            proc += [f"MOVE {r} TO EW", f"DISPLAY '{tag} {r} ' EW"]
    src = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. BINSTORE.", "       DATA DIVISION.",
           "       WORKING-STORAGE SECTION.", *(f"       {x}" for x in DATA), "       PROCEDURE DIVISION.",
           *(f"           {x}" for x in proc), "           GOBACK."]  # fmt: skip
    assert all(len(x) <= 72 for x in src)
    return "\n".join(src) + "\n"


def _translate(tmp_path: Path, proc: list[str]) -> str:
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NATIVE.", "       DATA DIVISION.",
           "       WORKING-STORAGE SECTION.", *(f"       {x}" for x in DATA), "       PROCEDURE DIVISION.",
           *(f"           {x}" for x in proc), "           GOBACK."]  # fmt: skip
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "native.cbl").write_text("\n".join(src) + "\n")
    project = tmp_path / "project"
    project.mkdir()
    r = P.translate(tmp_path / "native.cbl", [], "public class NativeService {\n}\n", "p", None, project)
    assert not r.stats["holes"], r.stats["holes"]
    return r.java


@pytest.mark.parametrize(
    ("stmt", "native"),
    [
        ("SUBTRACT 3 FROM UH", True),
        ("ADD KM TO NW", True),
        ("SUBTRACT P0 FROM UD", True),
        ("SUBTRACT 3 4 FROM UH", True),
        ("ADD 2147483647 TO UH", True),
        ("SUBTRACT 3 FROM SH", False),  # signed: the decimal store wraps the same way
        ("SUBTRACT 3 FROM Q8", False),  # decimal places
        ("SUBTRACT 3 FROM UH ROUNDED", False),
        ("SUBTRACT 3.0 FROM UH", False),
        ("SUBTRACT DT FROM UH", False),
        ("SUBTRACT D0 K7 FROM UH", False),
        ("ADD 2147483648 TO UH", False),
        ("SUBTRACT 3 FROM 1 GIVING UH", False),
    ],
)
def test_cobcs_native_add_is_chosen_as_cobc_chooses_it(stmt, native, tmp_path):
    java = _translate(tmp_path, [stmt])
    assert ("Cobol.storeNative(" in java or "Cobol.binaryNative(" in java) == native, java


def test_size_error_phrases_keep_the_decimal_store_but_comp5_ignores_a_lone_not_on_size_error(tmp_path):
    on = _translate(tmp_path / "a", ["SUBTRACT 3 FROM NH", "  ON SIZE ERROR DISPLAY 'Y'", "END-SUBTRACT"])
    assert "storeNative" not in on
    comp = _translate(tmp_path / "b", ["SUBTRACT 3 FROM UH", "  NOT ON SIZE ERROR DISPLAY 'N'", "END-SUBTRACT"])
    assert "storeNative" not in comp
    comp5 = _translate(tmp_path / "c", ["SUBTRACT 3 FROM NH", "  NOT ON SIZE ERROR DISPLAY 'N'", "END-SUBTRACT"])
    assert "storeNative" in comp5


# what the oracle prints (measured 2026-10-08, GnuCOBOL 3.1.2 -std=ibm, without and with -fbinary-truncate)
WANT = {
    "bin": {
        "W1 UH": "65534.0000", "W2 UW": "4294967294.0000", "W3 UD": "18446744073709551610.0000",
        "W4 NH": "65530.0000", "W5 NW": "4294868532.0000", "W6 UH": "65532.0000", "W7 UH": "65530.0000",
        "W8 UH": "65534.0000", "W8 NH": "65534.0000", "W9 N": "", "W9 NH": "65534.0000",
        "A1 UH": "2.0000", "A2 UH": "2.0000", "A3 UH": "2.0000", "A4 UH": "6.0000", "A5 UH": "13.0000",
        "A6 UW": "2147483647.0000", "A7 UH": "2.0000", "A8 UH": "2.0000", "A9 N": "", "A9 UH": "2.0000",
        "S1 SH": "25537.0000", "O1 UH": "4465.0000", "O2 UH": "57920.0000", "O3 UW": "3857167135.0000",
        "O4 NH": "4465.0000", "M1 UH": "33229.0000", "I1 Q8": "1.2480",
    },
    "std": {
        "W1 UH": "2.0000", "W2 UW": "2.0000", "W3 UD": "6.0000", "W4 NH": "65530.0000",
        "W5 NW": "4294868532.0000", "W6 UH": "4.0000", "W7 UH": "6.0000", "W8 UH": "2.0000", "W8 NH": "65534.0000",
        "W9 NH": "65534.0000", "A6 UW": "147483647.0000", "A9 N": "", "S1 SH": "-9999.0000", "O1 UH": "1.0000",
        "O2 UH": "3456.0000", "O3 UW": "281676575.0000", "O4 NH": "4465.0000", "M1 UH": "8765.0000",
        "I1 Q8": "0.0000",
    },
}  # fmt: skip


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip
@pytest.mark.parametrize("trunc", ["bin", "std"])
@pytest.mark.parametrize("mode", ["bytes", "typed"])
def test_binary_stores_are_the_oracles(trunc, mode, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    import test_det_programs as T

    if T._java() is None:
        pytest.skip("needs a JDK 17 (JAVA_HOME / JDK_17)")
    src = program()
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = T._cobol(src, cob, "-fbinary-truncate" if trunc == "std" else "")
    got = T._java_run("binstore", src, tmp_path, mode == "typed", trunc_std=trunc == "std")
    lines = [x for x in want.splitlines() if not x.startswith("prog.cbl")]
    shown = {" ".join(x.split()[:2]): " ".join(x.split()[2:]) for x in lines}
    for k, v in WANT[trunc].items():
        assert shown[k] == v, (k, shown[k])
    assert got.splitlines() == lines
