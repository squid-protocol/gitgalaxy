"""#4706: TRUNC(OPT) on both sides of a proof (oracle_assumptions.md C5 / C1).

IBM is the reference, GnuCOBOL the instrument. "When TRUNC(OPT) is in effect, the compiler assumes that data conforms
to PICTURE specifications in USAGE BINARY receiving fields in MOVE statements and arithmetic expressions. The results
are manipulated in the most optimal way, either truncating to the number of digits in the PICTURE clause, or to the
size of the binary field in storage (halfword, fullword, or doubleword)" -- and for a value that does not conform
"unpredictable results could occur ... dependent on the particular code sequence generated" (Enterprise COBOL for z/OS
6.x Programming Guide, "TRUNC"). For conforming values OPT's results are TRUNC(STD)'s. So the det runtime computes as
STD and stops by name wherever a value past a COMP / COMP-4 / BINARY receiver's PICTURE would be stored (COMP-5: no
TRUNC truncates it); the oracle runs -fbinary-truncate (STD). A scenario that would reach such a value stops on the
port's side, so the comparison never judges one. A port without that stop (a model port) is proven as TRUNC(STD), a
declared difference in its evidence record.

The runtime tests need a JDK 17 (JAVA_HOME / JDK_17); the oracle comparison also Docker (EQUIVALENCE_E2E=1)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import equivalence_common as common  # noqa: E402

from gitgalaxy.core import estate_options as eo  # noqa: E402

PLAIN = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n"
CBSA = "cics-banking-sample-application-cbsa"


# ---- the oracle and the estate --------------------------------------------------------------------------------------
def test_trunc_opt_runs_the_oracle_as_trunc_std():
    text, flags = common.compile_options({}, "       PROCESS TRUNC(OPT)\n" + PLAIN)
    assert text == "\n" + PLAIN and flags == ["-fbinary-truncate"]
    assert common.compile_options({"compiler_options": ["TRUNC(OPT)"]}, PLAIN)[1] == ["-fbinary-truncate"]


def _service(root: Path, text: str) -> Path:
    (root / "service").mkdir(parents=True)
    (root / "service" / "PService.java").write_text(text, encoding="utf-8")
    return root


def test_only_a_port_with_the_det_runtimes_stop_claims_trunc_opt(tmp_path):
    case = {"compiler_options": ["TRUNC(OPT)"]}
    model = _service(tmp_path / "model", "public class PService { }\n")
    det = _service(tmp_path / "det", common.DET_PORT_HEADER + " P\n        boolean optBefore = "
                   + common.TRUNC_OPT_STOP + ";  // TRUNC(OPT)\n")  # fmt: skip
    (d,) = common.option_differences(case, PLAIN, model)
    assert (d["kind"], d["option"], d["declared"], d["applied"]) == ("option", "TRUNC", "OPT", "STD")
    assert common.option_differences(case, PLAIN, None) == [d]  # the generated service: no stop either
    assert common.option_differences(case, PLAIN, det) == []
    # the program's own card wins: nothing to declare
    assert common.option_differences(case, "       PROCESS TRUNC(STD)\n" + PLAIN, model) == []
    assert common.option_differences({}, PLAIN, model) == []


def test_cbsa_trunc_opt_is_honoured_not_a_deviation():
    for program in ("INQACC", "DELACC", "CUSTCTRL"):
        r = eo.effective_options({"corpus": CBSA, "program": program})
        assert r.values(PLAIN)["TRUNC"] == "OPT", program
        assert r.deviations(PLAIN) == [], program
        assert "TRUNC(OPT)" in r.layers and "TRUNC(OPT)" in r.declared
    # a program with its own TRUNC(STD) card (UPDACC, XFRFUN ...) still runs STD
    r = eo.effective_options({"corpus": CBSA, "program": "UPDACC"})
    assert r.values("       PROCESS CICS,NODYNAM,NSYMBOL(NATIONAL),TRUNC(STD)\n" + PLAIN)["TRUNC"] == "STD"
    est = eo.load_estate(CBSA)
    (trunc,) = [e for e in est["parm"]["default"] if e["option"] == "TRUNC"]
    assert trunc["value"] == "OPT" and "applied_value" not in trunc


# ---- the det translator ----------------------------------------------------------------------------------------------
def test_trunc_mode_reads_the_three_values(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "T.cbl"
    src.write_text(PLAIN, encoding="ascii")
    assert P.trunc_mode(src) == "STD"
    assert P.trunc_mode(src, ["TRUNC(BIN)"]) == "BIN"
    assert P.trunc_mode(src, ["TRUNC(OPT)"]) == "OPT"
    assert P.trunc_std(src, ["TRUNC(OPT)"]) is True  # OPT computes as STD
    src.write_text("       PROCESS TRUNC(OPT)\n" + PLAIN, encoding="ascii")
    assert P.trunc_mode(src, ["TRUNC(STD)"]) == "OPT"  # the program's own card wins


def test_each_entry_runs_trunc_opt_with_its_stop_and_restores_it():
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    java = "class S {\n    public void runTask(CicsTask task) {\n        x();\n    }\n}\n"
    out = P.with_trunc(java, "OPT")
    assert "boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(OPT)" in out
    assert common.TRUNC_OPT_STOP in out and "Cobol.swapTruncOpt(optBefore);" in out
    assert out.index("Cobol.swapTruncOpt(optBefore)") < out.index("Cobol.swapTruncBinary(truncBefore)")
    # STD and BIN ports are as they were: no TRUNC(OPT) switch at all
    assert P.with_trunc(java, "STD") == P.with_trunc(java, True) and "swapTruncOpt" not in P.with_trunc(java, True)
    assert P.with_trunc(java, "BIN") == P.with_trunc(java, False)


DATA = [
    "01 SH PIC S9(4) COMP.",
    "01 UW PIC 9(9) BINARY.",
    "01 NS PIC S9(4) COMP-5.",
    "01 K7 PIC S9(4) COMP VALUE 7.",
    "01 P0 PIC S9(7) COMP-3 VALUE 98765.",
    "01 EW PIC -(20)9.9(4).",
]

# every value fits its binary receiver's PICTURE (COMP-5 excepted: no TRUNC truncates it), and the one past it is
# under ON SIZE ERROR (Language Reference, "SIZE ERROR phrases": the receiver unchanged, nothing stored)
CONFORMING = [
    "MOVE 1234 TO SH", "ADD K7 TO SH", "MOVE SH TO EW", "DISPLAY 'C1 ' EW",
    "COMPUTE UW = P0 * 3", "MOVE UW TO EW", "DISPLAY 'C2 ' EW",
    "MOVE P0 TO UW", "SUBTRACT 9999 FROM SH", "MOVE SH TO EW", "DISPLAY 'C3 ' EW",
    "COMPUTE NS = 30000", "MOVE NS TO EW", "DISPLAY 'C4 ' EW",
    "ADD 20000 TO SH ON SIZE ERROR DISPLAY 'C5 SIZE' END-ADD", "MOVE SH TO EW", "DISPLAY 'C5 ' EW",
    "MOVE K7 TO SH", "MOVE SH TO K7", "MOVE K7 TO EW", "DISPLAY 'C6 ' EW",
]  # fmt: skip

WANT = {"C1": "1241.0000", "C2": "296295.0000", "C3": "-8758.0000", "C4": "30000.0000", "C5 SIZE": "",
        "C5": "-8758.0000", "C6": "7.0000"}  # fmt: skip


def _program(name: str, proc: list[str], card: str = "") -> str:
    src = [*([card] if card else []), "       IDENTIFICATION DIVISION.", f"       PROGRAM-ID. {name}.", "       DATA DIVISION.",
           "       WORKING-STORAGE SECTION.", *(f"       {x}" for x in DATA), "       PROCEDURE DIVISION.",
           *(f"           {x}" for x in proc), "           GOBACK."]  # fmt: skip
    assert all(len(x) <= 72 for x in src)
    return "\n".join(src) + "\n"


def _lines(out: str) -> dict[str, str]:
    return {" ".join(x.split()[:2 if "SIZE" in x else 1]): " ".join(x.split()[2 if "SIZE" in x else 1 :])
            for x in out.splitlines() if x.strip() and not x.startswith("prog.cbl")}  # fmt: skip


def _dir(root: Path, name: str) -> Path:
    (root / name).mkdir()
    return root / name


def _jdk_or_skip():
    pytest.importorskip("tree_sitter_language_pack")
    import test_det_programs as T

    if T._java() is None:
        pytest.skip("needs a JDK 17 (JAVA_HOME / JDK_17)")
    return T


@pytest.mark.parametrize("typed", [False, True])
def test_conforming_values_give_trunc_stds_results(typed, tmp_path):
    T = _jdk_or_skip()
    src = _program("OPTOK", CONFORMING)
    opt = T._java_run("optok", src, _dir(tmp_path, "opt"), typed, trunc_opt=True)
    std = T._java_run("optok", src, _dir(tmp_path, "std"), typed, trunc_std=True)
    assert opt == std
    assert _lines(opt) == WANT


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize(
    ("stmt", "said"),
    [
        ("MOVE 99999 TO SH", "99999 into a signed 4-digit binary item"),
        ("COMPUTE SH = P0", "98765 into a signed 4-digit binary item"),
        ("ADD 9999 TO K7", "10006 into a signed 4-digit binary item"),
        ("MOVE P0 TO UW MULTIPLY 100000 BY UW", "9876500000 into a 9-digit binary item"),
        ("MOVE 9999 TO SH MOVE SH TO NS ADD 1 TO NS MOVE NS TO SH", "10000 into a signed 4-digit binary item"),
    ],
)
def test_a_value_past_the_picture_stops_by_name(typed, stmt, said, tmp_path):
    T = _jdk_or_skip()
    # the program's own card: the translator reads TRUNC(OPT) too (a typed binary item's MOVE goes to the runtime)
    src = _program("OPTNO", ["DISPLAY 'BEFORE'", stmt, "DISPLAY 'AFTER'"], "       PROCESS TRUNC(OPT)")
    with pytest.raises(subprocess.CalledProcessError) as e:
        T._java_run("optno", src, _dir(tmp_path, "opt"), typed, trunc_opt=True)
    assert "TRUNC(OPT): value exceeds PICTURE; IBM result unpredictable" in e.value.stderr, e.value.stderr
    assert said in e.value.stderr, e.value.stderr
    assert "BEFORE" in e.value.stdout and "AFTER" not in e.value.stdout
    # under TRUNC(STD) the same statement runs on
    std = _program("OPTNO", ["DISPLAY 'BEFORE'", stmt, "DISPLAY 'AFTER'"], "       PROCESS TRUNC(STD)")
    assert "AFTER" in T._java_run("optno", std, _dir(tmp_path, "std"), typed, trunc_std=True)


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip
@pytest.mark.parametrize("typed", [False, True])
def test_conforming_values_equal_the_oracles_trunc_std(typed, tmp_path):
    T = _jdk_or_skip()
    src = _program("OPTOK", CONFORMING)
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = T._cobol(src, cob, flags="-fbinary-truncate")  # the oracle under TRUNC(OPT): equivalence_common
    got = T._java_run("optok", src, tmp_path, typed, trunc_opt=True)
    assert _lines(got) == _lines(want) == WANT
