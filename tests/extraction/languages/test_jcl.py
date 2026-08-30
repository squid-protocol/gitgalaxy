"""
JCL extraction hardening. See
tests/extraction/how_to_harden_extraction.md for the methodology.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

JCL_RULES = LANGUAGE_DEFINITIONS["jcl"]["rules"]

# ==============================================================================
# FUNC_START (func_start) - EXEC steps
# ==============================================================================
FUNC_START_VALID = [
    ("//STEP1 EXEC PGM=IEFBR14", "STEP1"),
    ("//S$#@  EXEC PROC=MYPROC", "S$#@"),
    ("//STEP2 EXEC MYPROC", "STEP2"),
    # If a step is unnamed, it can be tested here, we will see if the engine supports empty names.
    ("//   EXEC PGM=XYZ", ""),
    ("//STEP3 EXEC \\\n// PGM=LONGPGM", "STEP3"),
    ("//PGM EXEC PGM=PGM", "PGM"),
]

FUNC_START_INVALID = [
    "//* EXEC PGM=A",
    "//DD1 DD DSN='//FAKE EXEC PGM=A'",
    pytest.param(
        "//SYSUDUMP DD DATA,DLM=$$\n//BAD EXEC PGM=X\n$$",
        marks=pytest.mark.xfail(reason="Known limitation: No block shielding for instream data in JCL"),
    ),
    "// STEP EXEC PGM=A",  # Space after // means not a named statement
]


@pytest.mark.parametrize("payload,expected_name", FUNC_START_VALID)
def test_jcl_func_start_valid(payload, expected_name):
    assert_valid_match(JCL_RULES["func_start"], payload, expected_name, "jcl.func_start")


@pytest.mark.parametrize("payload", FUNC_START_INVALID)
def test_jcl_func_start_invalid(payload):
    assert_invalid_no_match(JCL_RULES["func_start"], payload, "jcl.func_start")


def test_jcl_func_start_redos_immunity():
    assert_redos_immune(JCL_RULES["func_start"], "//" + "A" * 1000 + " EXEC PGM=A", timeout_sec=1.0)


# ==============================================================================
# CLASS_START (class_start) - JOB cards
# ==============================================================================
CLASS_START_VALID = [
    ("//MYJOB    JOB 1", "MYJOB"),
    ("//$#@JOB   JOB (ACCT),'JOHN DOE'", "$#@JOB"),
    ("//LONGJOB  JOB (1234,\n//         5678),\n//         CLASS=A", "LONGJOB"),
    ("//MYJOB JOB 1  //NOT A COMMENT IF NO SPACE BEFORE THIS", "MYJOB"),
    ("//JOB JOB 1", "JOB"),
]

CLASS_START_INVALID = [
    "//* //FAKE JOB 1",
    pytest.param(
        "//SYSIN DD *\n//FAKE JOB 1\n/*",
        marks=pytest.mark.xfail(reason="Known limitation: No block shielding for instream data in JCL"),
    ),
    "//STEP1 EXEC PGM=XYZ,PARM='//FAKE JOB'",
    "// NOTAJOB JOB 1",
    "JOB NO SLASHES",
]


@pytest.mark.parametrize("payload,expected_name", CLASS_START_VALID)
def test_jcl_class_start_valid(payload, expected_name):
    assert_valid_match(JCL_RULES["class_start"], payload, expected_name, "jcl.class_start")


@pytest.mark.parametrize("payload", CLASS_START_INVALID)
def test_jcl_class_start_invalid(payload):
    assert_invalid_no_match(JCL_RULES["class_start"], payload, "jcl.class_start")


# ==============================================================================
# ARGS (args)
# ==============================================================================
# We will test args extraction for PARM= strings on EXEC steps.
ARGS_VALID = [
    ("//STEP EXEC PGM=X,PARM='A=B'", "'A=B'"),
    ("//STEP EXEC PGM=X,PARM=ABC", "ABC"),
    ("//STEP EXEC PGM=X,PARM=('A','B')", "('A','B')"),
    ("//STEP EXEC PGM=X,PARM='O''BRIEN'", "'O''BRIEN'"),
    ("//MYPROC PROC P1=ABC,P2='DEF'", "P1=ABC,P2='DEF'"),
    pytest.param(
        "//STEP1    EXEC PGM=PROG,PARM='THIS STRING CONTINUES                    X\n//             AT COLUMN 16'",
        "'THIS STRING CONTINUES                    X\n//             AT COLUMN 16'",
        marks=pytest.mark.xfail(reason="Known limitation: Engine cannot parse JCL line continuations"),
    ),
    # #2482: PARM= on a `//` continuation line, reached via the trailing-comma
    # continuation marker -- no longer an xfail, this is the exact shape fixed.
    ("//STEP EXEC PGM=X, \n//   PARM='A=B'", "'A=B'"),
]

ARGS_INVALID = [
    "//STEP EXEC PGM=X   PARM='A=B'",
    "//* //STEP EXEC PGM=X,PARM='A=B'",
]


@pytest.mark.parametrize("payload,expected_args", ARGS_VALID)
def test_jcl_args_valid(payload, expected_args):
    # args capture logic tests
    if JCL_RULES.get("args") is None:
        pytest.skip("args is None for jcl")
    assert_valid_match(JCL_RULES["args"], payload, expected_args, "jcl.args")


@pytest.mark.parametrize("payload", ARGS_INVALID)
def test_jcl_args_invalid(payload):
    if JCL_RULES.get("args") is None:
        pytest.skip("args is None for jcl")
    assert_invalid_no_match(JCL_RULES["args"], payload, "jcl.args")


def test_jcl_args_mode_a_window_bounded_no_over_count():
    """
    Pipeline-level regression for #2483: Mode A's generic args-count
    derivation used to search the WHOLE greedy block (this step's own
    signature through to the next EXEC step), not just this step's own
    statement -- a real corpus bug (docs/language_status/jcl.md:
    ZOSCSEC.jcl's BPXIT step read `args=7` off an unbounded sweep of its own
    multi-line `PARM='SH chmod ...'` string) and, more seriously, a step
    with NO `PARM=` of its own could pick up a LATER, unrelated step's
    PARM= instead. `args_search_text` must now be bounded to just this
    step's own (possibly continuation-extended) statement via jcl's `,`
    entry in `_MODE_A_ARGS_CONTINUATION_MARKER`.
    """
    from gitgalaxy.core.detector import StructuralExtractor

    extractor = StructuralExtractor("jcl", LANGUAGE_DEFINITIONS)

    # A step with no PARM= of its own, followed by an unrelated step that
    # DOES have one -- the first step must read args=0, never borrowing the
    # second step's PARM=.
    two_steps = "//STEP1   EXEC PGM=FOO\n//STEP2   EXEC PGM=BAR,PARM='SHOULDNOTBLEED'\n"
    segments = extractor._partition_segments(two_steps, "jcl")
    functions, _ = extractor._function_slice(segments, [{} for _ in segments], {}, {}, None)
    step1 = next(f for f in functions if f["name"] == "STEP1")
    step2 = next(f for f in functions if f["name"] == "STEP2")
    assert step1["args"] == 0, f"STEP1 must not borrow STEP2's PARM=, got args={step1['args']}"
    assert step2["args"] == 1, f"STEP2's own PARM= should still count normally, got args={step2['args']}"

    # A single-value PARM= must not be over-counted just because the window
    # now spans a multi-line continuation -- one PARM= is still one value.
    continued = "//CICS    EXEC PGM=DFHSIP,REGION=&REG,TIME=1440,\n// COND=(1,NE,CICSCNTL),\n// PARM='START=&START,SYSIN',MEMLIMIT=16G\n//NEXT     EXEC PGM=OTHER\n"
    segments2 = extractor._partition_segments(continued, "jcl")
    functions2, _ = extractor._function_slice(segments2, [{} for _ in segments2], {}, {}, None)
    cics_step = next(f for f in functions2 if f["name"] == "CICS")
    assert cics_step["args"] == 1, f"a single PARM= value must count as 1, got args={cics_step['args']}"


# ==============================================================================
# DEPENDENCY CAPTURE (_dependency_capture)
# ==============================================================================
DEPENDENCY_VALID = [
    ("//  INCLUDE MEMBER=COMMON", "COMMON"),
    ("//STEP INCLUDE MEMBER=COMMON", "COMMON"),
    ("//MYLIB JCLLIB ORDER=(SYS1.PROCLIB,USER.PROCLIB)", "SYS1.PROCLIB"),
    ("//DD1 DD DSN=PROD.DATA,DISP=SHR", "PROD.DATA"),
    ("//DD1 DD DSN=PROD.LIB(MEM1),DISP=SHR", "PROD.LIB(MEM1)"),
    ("//DD1 DD DSN=A.B.C,DISP=SHR\n//    DD DSN=D.E.F,DISP=SHR", "A.B.C"),
    ("//DD1 DD DSN=&ENV..MY.DATA,DISP=SHR", "&ENV..MY.DATA"),
]

DEPENDENCY_INVALID = [
    "//DD1 DD DSN=&&TEMP,DISP=(NEW,PASS)",
    "//DD1 DD DSN=*.STEP1.DD1,DISP=SHR",
    pytest.param(
        "//DD DATA \n INCLUDE MEMBER=NOPE \n/*",
        marks=pytest.mark.xfail(reason="Known limitation: No block shielding for instream data in JCL"),
    ),
    pytest.param(
        "//STEP1 EXEC PGM=PROG1   THIS COMMENT CONTAINS // INCLUDE MEMBER=FAKE",
        marks=pytest.mark.xfail(reason="Known limitation: Inline comments aren't stripped before dependency capture"),
    ),
]


@pytest.mark.parametrize("payload,expected_name", DEPENDENCY_VALID)
def test_jcl_dependency_valid(payload, expected_name):
    assert_valid_dependency_match(JCL_RULES["_dependency_capture"], payload, expected_name, "jcl.dependency")


@pytest.mark.parametrize("payload", DEPENDENCY_INVALID)
def test_jcl_dependency_invalid(payload):
    assert_invalid_no_match(JCL_RULES["_dependency_capture"], payload, "jcl.dependency")
