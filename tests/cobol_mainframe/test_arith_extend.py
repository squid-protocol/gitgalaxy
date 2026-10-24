"""#4706: ARITH(EXTEND) on both sides of a proof (oracle_assumptions.md C5 / C2).

IBM is the reference, GnuCOBOL the instrument. ARITH(EXTEND) differs from ARITH(COMPAT) in two ways: an intermediate
result may have 31 digits instead of 30 (items up to 31 digits instead of 18), and floating-point expressions use
extended precision (Enterprise COBOL for z/OS 6.x Programming Guide, "ARITH"). So the det runtime computes as COMPAT and
stops by name wherever an intermediate result would pass 30 digits, and the translator refuses a float under EXTEND; the
oracle runs the COMPAT flags. A scenario that would reach a wider intermediate stops on the port's side, so the
comparison never judges one. A port without that stop (a model port) is proven as ARITH(COMPAT), a declared difference
in its evidence record.

The runtime tests need a JDK 17 (JAVA_HOME / JDK_17)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import equivalence_common as common  # noqa: E402

PLAIN = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n"


# ---- the oracle -----------------------------------------------------------------------------------------------------
def test_arith_extend_runs_the_oracle_as_arith_compat():
    text, flags = common.compile_options({}, "       PROCESS ARITH(EXTEND)\n" + PLAIN)
    assert text == "\n" + PLAIN and flags == ["-fbinary-truncate", *common.BOUND_FLAGS]
    assert common.compile_options({"compiler_options": ["ARITH(EXTEND)"]}, PLAIN)[1] == [
        "-fbinary-truncate",
        *common.BOUND_FLAGS,
    ]


def _service(root: Path, text: str) -> Path:
    (root / "service").mkdir(parents=True)
    (root / "service" / "PService.java").write_text(text, encoding="utf-8")
    return root


def test_only_a_port_with_the_det_runtimes_stop_claims_arith_extend(tmp_path):
    case = {"compiler_options": ["ARITH(EXTEND)"]}
    model = _service(tmp_path / "model", "public class PService { }\n")
    det = _service(tmp_path / "det", common.DET_PORT_HEADER + " P\n        boolean extBefore = "
                   + common.ARITH_EXTEND_STOP + ";  // ARITH(EXTEND)\n")  # fmt: skip
    (d,) = common.option_differences(case, PLAIN, model)
    assert (d["kind"], d["option"], d["declared"], d["applied"]) == ("option", "ARITH", "EXTEND", "COMPAT")
    assert common.option_differences(case, PLAIN, None) == [d]
    assert common.option_differences(case, PLAIN, det) == []
    # the program's own card wins: nothing to declare
    assert common.option_differences(case, "       PROCESS ARITH(COMPAT)\n" + PLAIN, model) == []
    assert common.option_differences({}, PLAIN, model) == []


# ---- the det translator ----------------------------------------------------------------------------------------------
def test_each_entry_runs_arith_extend_with_its_stop_and_restores_it():
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    java = "class S {\n    public void runTask(CicsTask task) {\n        x();\n    }\n}\n"
    out = P.with_trunc(java, "STD", extend=True)
    assert "boolean extBefore = " + common.ARITH_EXTEND_STOP in out
    assert "Cobol.swapArithExtend(extBefore);" in out
    # COMPAT ports are as they were: no ARITH switch at all
    assert "swapArithExtend" not in P.with_trunc(java, "STD")
    assert P.with_trunc(java, "STD", extend=False) == P.with_trunc(java, "STD")


# ---- the runtime ------------------------------------------------------------------------------------------------------
def _jdk_or_skip():
    pytest.importorskip("tree_sitter_language_pack")
    import test_det_programs as T

    if T._java() is None:
        pytest.skip("needs a JDK 17 (JAVA_HOME / JDK_17)")
    return T


def _program(name: str, proc: list[str], card: str = "") -> str:
    data = ["01 A PIC 9(18) VALUE 999999999999999999.", "01 B PIC 9(18) VALUE 999999999999999999.",
            "01 R PIC 9(31).", "01 N PIC 9(4) VALUE 7."]  # fmt: skip
    src = [*([card] if card else []), "       IDENTIFICATION DIVISION.", f"       PROGRAM-ID. {name}.", "       DATA DIVISION.",
           "       WORKING-STORAGE SECTION.", *(f"       {x}" for x in data), "       PROCEDURE DIVISION.",
           *(f"           {x}" for x in proc), "           GOBACK."]  # fmt: skip
    assert all(len(x) <= 72 for x in src)
    return "\n".join(src) + "\n"


def _dir(root: Path, name: str) -> Path:
    (root / name).mkdir()
    return root / name


@pytest.mark.slow(reason="translates, javac-compiles and runs a program per case (#5178, #5606)")
@pytest.mark.parametrize("typed", [False, True])
def test_an_intermediate_within_30_digits_gives_compats_results(typed, tmp_path):
    T = _jdk_or_skip()
    # 18 x 18 digits is at most 36 digits, but 999999999999999999 * 10 is 19: well inside 30
    src = _program("EXTOK", ["COMPUTE R = A * N + B", "DISPLAY 'R ' R", "ADD A TO B", "DISPLAY 'B ' B"],
                   "       PROCESS ARITH(EXTEND)")  # fmt: skip
    ext = T._java_run("extok", src, _dir(tmp_path, "ext"), typed, arith_extend=True)
    cmp_ = T._java_run("extok", src, _dir(tmp_path, "cmp"), typed)
    assert ext == cmp_ and "R 0000000000000007999999999999999999" not in ext
    assert "R " in ext and "B " in ext


@pytest.mark.slow(reason="translates, javac-compiles and runs a program per case (#5178)")
@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize(
    "stmt",
    ["COMPUTE R = A * B", "MULTIPLY A BY B GIVING R", "COMPUTE R = A * A * N"],
)
def test_an_intermediate_past_30_digits_stops_by_name(typed, stmt, tmp_path):
    T = _jdk_or_skip()
    src = _program("EXTNO", ["DISPLAY 'BEFORE'", stmt, "DISPLAY 'AFTER'"], "       PROCESS ARITH(EXTEND)")
    with pytest.raises(subprocess.CalledProcessError) as e:
        T._java_run("extno", src, _dir(tmp_path, "ext"), typed, arith_extend=True)
    assert "ARITH(EXTEND): an intermediate result of" in e.value.stderr, e.value.stderr
    assert "BEFORE" in e.value.stdout and "AFTER" not in e.value.stdout
    # under ARITH(COMPAT) the same statement runs on
    cmp_ = _program("EXTNO", ["DISPLAY 'BEFORE'", stmt, "DISPLAY 'AFTER'"])
    assert "AFTER" in T._java_run("extno", cmp_, _dir(tmp_path, "cmp"), typed)
