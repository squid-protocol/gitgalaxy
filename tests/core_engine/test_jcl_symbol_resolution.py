"""
#3345: JCL symbolic-parameter resolution in the dataset fact channel.

The #3201 channel stored a DD's `DSN=` exactly as written, so a job that
parameterizes its datasets -- every DSN in IBM/zopeneditor-sample's RUN.jcl --
bound DDs to templates like `&HLQ..SAMPLE.CUSTFILE`, not to datasets. These pin
the resolution the engine now does beside the raw DSN: `SET`, in-stream PROC
defaults and EXEC overrides, the `&SYM.` delimiter, and the honest non-answers
(`proc_default`, `ambiguous`, `unresolved`) for what one file cannot determine.

Fixtures are the shapes of REAL members from the pinned corpora (named at each),
trimmed; the in-stream PROC cases, which no pinned corpus happens to contain,
follow the IBM JCL Reference's own procedure examples.
"""

import sys
import time
from pathlib import Path

import pytest

from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cobol_answer_key as ak  # noqa: E402 -- the independent reader the differential compares against


def _stream(src: str) -> str:
    """The PRISM code stream a real scan hands the extractor (`//*` lines blanked)."""
    return Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams(src, "jcl")["code_stream"]


def _bindings(src: str) -> list[tuple]:
    return [
        (d["step_name"], d["dd_name"], d["dsn"], d["dsn_resolved"], d["dsn_resolution"])
        for d in extract_boundary("jcl", _stream(src))["datasets"]
    ]


# IBM/zopeneditor-sample JCL/RUN.jcl: quoted SET values, a comment after each,
# a value with commas inside the quotes, and `&SYM..` / bare `&SYM` references.
RUN_JCL = """\
//ZDERUN  JOB ,NOTIFY=&SYSUID,
// MSGCLASS=H,MSGLEVEL=(1,1),REGION=144M
//*****************************************************************
//    SET HLQ='IBMUSER'                       *TSO USER ID
//    SET CMPLLIB='IGY.V6R5M0.SIGYCOMP'       *COMPILER LIBRARY
//    SET SPACE1='SYSALLDA,SPACE=(CYL,(1,1))' *SPACE ALLOCATION
//*
//CMPLSAM2 EXEC PGM=IGYCRCTL,PARM='LIST,MAP,NODYN'
//STEPLIB  DD DISP=SHR,DSN=&CMPLLIB
//SYSIN    DD DISP=SHR,DSN=&HLQ..SAMPLE.COBOL(SAM2)
//SYSUT1   DD UNIT=&SPACE1
//SAM1  EXEC   PGM=SAM1
//CUSTOUT  DD DSN=&HLQ..SAMPLE.CUSTOUT,
//    DISP=(NEW,CATLG),UNIT=SYSDA,SPACE=(TRK,(10,10),RLSE)
//REPORT   DD DSN=&SYSUID..REPORT,DISP=SHR
"""


def test_set_symbols_resolve_and_the_raw_dsn_is_kept():
    assert _bindings(RUN_JCL) == [
        ("CMPLSAM2", "STEPLIB", "&CMPLLIB", "IGY.V6R5M0.SIGYCOMP", "resolved"),
        ("CMPLSAM2", "SYSIN", "&HLQ..SAMPLE.COBOL(SAM2)", "IBMUSER.SAMPLE.COBOL(SAM2)", "resolved"),
        ("SAM1", "CUSTOUT", "&HLQ..SAMPLE.CUSTOUT", "IBMUSER.SAMPLE.CUSTOUT", "resolved"),
        # A system symbol is a runtime value -- never guessed.
        ("SAM1", "REPORT", "&SYSUID..REPORT", None, "unresolved"),
    ]


def test_a_literal_dsn_is_its_own_resolution():
    src = "//J JOB\n//S EXEC PGM=X\n//IN DD DSN=AWS.M2.CARDDEMO.ACCTDATA.PS,DISP=SHR\n"
    assert _bindings(src) == [("S", "IN", "AWS.M2.CARDDEMO.ACCTDATA.PS", "AWS.M2.CARDDEMO.ACCTDATA.PS", "literal")]


def test_the_period_delimiter_is_consumed_once():
    """`&A.B` is the value of A then B; `&A..B` keeps one period; `&A&B` abuts."""
    src = (
        "//J JOB\n// SET A=PROD,B=DATA\n//S EXEC PGM=X\n"
        "//D1 DD DSN=&A.B\n//D2 DD DSN=&A..B\n//D3 DD DSN=&A.&B\n//D4 DD DSN=X.&B..Y\n"
    )
    assert [b[3] for b in _bindings(src)] == ["PRODB", "PROD.B", "PRODDATA", "X.DATA.Y"]


def test_a_temporary_dataset_is_never_a_symbol():
    """`&&TEMP` stays outside the channel (it is job-local, #3201); a single-`&`
    name nothing defines is unresolved rather than invented."""
    src = "//J JOB\n//S EXEC PGM=X\n//T1 DD DSN=&&LOADSET,DISP=(NEW,PASS)\n//T2 DD DSN=&TEMP,DISP=(NEW,PASS)\n"
    assert _bindings(src) == [("S", "T2", "&TEMP", None, "unresolved")]


def test_a_set_takes_effect_in_source_order():
    src = "//J JOB\n// SET HLQ=OLD\n//S1 EXEC PGM=X\n//A DD DSN=&HLQ..F\n// SET HLQ=NEW\n//S2 EXEC PGM=X\n//B DD DSN=&HLQ..F\n"
    assert [b[3] for b in _bindings(src)] == ["OLD.F", "NEW.F"]


def test_a_set_value_is_substituted_when_it_is_read():
    """`SET HLQ=&HLQ..TEST` extends the previous HLQ; it cannot refer to itself."""
    src = "//J JOB\n// SET HLQ=PROD\n// SET HLQ=&HLQ..TEST\n//S EXEC PGM=X\n//A DD DSN=&HLQ..F\n"
    assert _bindings(src)[0][3] == "PROD.TEST.F"


def test_blanks_inside_a_quoted_value_end_the_dsn():
    """zopeneditor-sample's ASM job: `SET MACLIB='SYS1.MACLIB          '`."""
    src = "//J JOB\n//    SET MACLIB='SYS1.MACLIB          '  *Z/OS MACRO LIBRARY\n//S EXEC PGM=X\n//L DD DSN=&MACLIB,DISP=SHR\n"
    assert _bindings(src)[0][3:] == ("SYS1.MACLIB", "resolved")


def test_a_relative_gdg_generation_is_kept_whole():
    """carddemo TRANREPT.jcl `DSN=...BKUP(+1)` used to be cut to `BKUP(`."""
    src = "//J JOB\n//S EXEC PGM=SORT\n//SORTIN DD DISP=SHR,\n//         DSN=AWS.M2.CARDDEMO.TRANSACT.BKUP(+1)\n"
    assert _bindings(src) == [
        ("S", "SORTIN", "AWS.M2.CARDDEMO.TRANSACT.BKUP(+1)", "AWS.M2.CARDDEMO.TRANSACT.BKUP(+1)", "literal")
    ]


# ------------------------------------------------------------------------------
# PROCEDURES
# ------------------------------------------------------------------------------
# An in-stream PROC (IBM JCL Reference shape): defaults on the PROC statement, one
# of which names another symbol, invoked by EXEC with an override.
INSTREAM = """\
//BUILD    JOB (ACCT),'BUILD'
//    SET HLQ=JOBHLQ
//COMPILE  PROC MEM=,HLQ=DEFHLQ,
//            SOURCE=&HLQ..CARDDEMO.CBL
//C        EXEC PGM=IGYCRCTL
//SYSIN    DD DISP=SHR,DSN=&SOURCE(&MEM)
//SYSLIB   DD DISP=SHR,DSN=&HLQ..CARDDEMO.CPY
//         PEND
{invocations}
"""


def test_an_exec_override_beats_the_proc_default_which_beats_set():
    src = INSTREAM.format(invocations="//STEP1 EXEC COMPILE,MEM=CBACT01C,HLQ=TEST")
    assert _bindings(src) == [
        ("C", "SYSIN", "&SOURCE(&MEM)", "TEST.CARDDEMO.CBL(CBACT01C)", "resolved"),
        ("C", "SYSLIB", "&HLQ..CARDDEMO.CPY", "TEST.CARDDEMO.CPY", "resolved"),
    ]


def test_the_proc_default_wins_over_a_job_set():
    src = INSTREAM.format(invocations="//STEP1 EXEC PROC=COMPILE,MEM=CBACT01C")
    assert [b[3:] for b in _bindings(src)] == [
        ("DEFHLQ.CARDDEMO.CBL(CBACT01C)", "resolved"),
        ("DEFHLQ.CARDDEMO.CPY", "resolved"),
    ]


def test_invocations_that_agree_resolve_and_ones_that_disagree_are_ambiguous():
    agree = INSTREAM.format(invocations="//S1 EXEC COMPILE,MEM=A,HLQ=T\n//S2 EXEC COMPILE,MEM=B,HLQ=T")
    # SYSLIB depends only on HLQ (agrees), SYSIN also on MEM (differs).
    assert [b[3:] for b in _bindings(agree)] == [(None, "ambiguous"), ("T.CARDDEMO.CPY", "resolved")]


def test_an_override_is_substituted_in_the_callers_context():
    """carddemo BATCMP.jcl: `EXEC BUILDBAT,MEM=&MEMNAME,HLQ=&HLQ` passes the JOB's HLQ."""
    src = INSTREAM.format(invocations="//    SET MEMNAME=CBACT01C\n//S1 EXEC COMPILE,MEM=&MEMNAME,HLQ=&HLQ")
    assert [b[3] for b in _bindings(src)] == ["JOBHLQ.CARDDEMO.CBL(CBACT01C)", "JOBHLQ.CARDDEMO.CPY"]


def test_exec_keywords_are_not_overrides():
    src = INSTREAM.format(invocations="//S1 EXEC COMPILE,MEM=A,PARM.C='LIST',COND=(4,LT),REGION=0M")
    assert [b[3] for b in _bindings(src)] == ["DEFHLQ.CARDDEMO.CBL(A)", "DEFHLQ.CARDDEMO.CPY"]


def test_a_null_proc_default_is_a_required_parameter_not_an_empty_value():
    """`MEM=` on the PROC means "the caller must supply it"; an in-stream PROC this
    file never invokes resolves only through its defaults, so what does resolve is
    marked `proc_default` -- a caller could still override it."""
    src = INSTREAM.format(invocations="")
    assert [b[3:] for b in _bindings(src)] == [(None, "unresolved"), ("DEFHLQ.CARDDEMO.CPY", "proc_default")]


def test_a_cataloged_proc_member_resolves_only_through_its_own_defaults():
    """carddemo samples/proc/BUILDBAT.prc: a PROC before any JOB is a cataloged
    member; its callers live in other members, so nothing is taken as final."""
    src = """\
//BLDBAT PROC MEM=,
//            HLQ=,
//            COBLIB=IGY.SIGYCOMP.V63,
//            CPYBKS=&HLQ..CARDDEMO.CPY
//COMPILE EXEC PGM=IGYCRCTL,REGION=0M
//STEPLIB  DD DSN=&COBLIB,DISP=SHR
//SYSLIB   DD DISP=SHR,DSN=&CPYBKS
//         DD DISP=SHR,DSN=CEE.SCEESAMP
"""
    assert _bindings(src) == [
        ("COMPILE", "STEPLIB", "&COBLIB", "IGY.SIGYCOMP.V63", "proc_default"),
        ("COMPILE", "SYSLIB", "&CPYBKS", None, "unresolved"),
        ("COMPILE", "SYSLIB", "CEE.SCEESAMP", "CEE.SCEESAMP", "literal"),
    ]


def test_a_self_referencing_default_ends_unresolved():
    src = "//P PROC A=&B,B=&A\n//S EXEC PGM=X\n//D DD DSN=&A\n"
    assert _bindings(src) == [("S", "D", "&A", None, "unresolved")]


# ------------------------------------------------------------------------------
# STATEMENT WALKER (real shapes that used to lose a statement)
# ------------------------------------------------------------------------------
def test_a_comment_after_a_continuation_comma_still_continues():
    """CBSA MAPGEN.jcl: `//MAPGEN PROC  MEMBER=,     NAME OF MAPSET - REQUIRED`."""
    src = """\
//MAPGEN PROC  MEMBER=,                      NAME OF MAPSET - REQUIRED
//             LIB=CBSA.BMS,                 SOURCE LIBRARY
//             WORK=SYSDA                    WORK FILE UNIT
//COPY     EXEC PGM=IEBGENER
//SYSUT1   DD DISP=SHR,DSN=&LIB(&MEMBER)
//SYSUT3   DD DISP=SHR,DSN=&LIB..X
"""
    assert [b[3:] for b in _bindings(src)] == [(None, "unresolved"), ("CBSA.BMS.X", "proc_default")]


def test_a_comment_line_inside_a_continuation_does_not_drop_the_statement():
    """CBSA MAPGEN.jcl's `//ASMMAP EXEC ...,` / `//* NOLOAD ...` / `//  PARM=...`
    and carddemo BUILDONL.prc's `//SYSLMOD DD DSN=...,` / `//* DISP=...` both
    used to vanish: PRISM blanks the `//*` line and a blank ended the statement."""
    src = """\
//P PROC LOADLIB=A.LOAD,MEM=X
//COPY     EXEC PGM=IEBGENER
//ASMMAP   EXEC PGM=ASMA90,REGION=2048K,
//* NOLOAD CHANGED TO NOOBJECT
//  PARM='SYSPARM(MAP),DECK,NOOBJECT'
//SYSLIB   DD DSN=SYS1.MACLIB,DISP=SHR
//SYSLMOD  DD DSN=&LOADLIB(&MEM),
//*           DISP=(OLD,KEEP),SPACE=(CYL,(10,20,10)),
//            DISP=SHR
"""
    assert _bindings(src) == [
        ("ASMMAP", "SYSLIB", "SYS1.MACLIB", "SYS1.MACLIB", "literal"),
        ("ASMMAP", "SYSLMOD", "&LOADLIB(&MEM)", "A.LOAD(X)", "proc_default"),
    ]


def test_a_cobol_binding_carries_no_resolution():
    src = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT F ASSIGN TO CUSTFILE.
       PROCEDURE DIVISION.
           OPEN INPUT F.
"""
    (row,) = extract_boundary("cobol", src)["datasets"]
    assert "dsn_resolved" not in row and "dsn_resolution" not in row


# ------------------------------------------------------------------------------
# BOUNDED
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "src",
    [
        "//J JOB\n//S EXEC PGM=X\n//D DD DSN=" + "&A" * 20000 + "\n",
        "//J JOB\n// SET " + ",".join(f"S{i}=&S{i + 1}." for i in range(3000)) + "\n//S EXEC PGM=X\n//D DD DSN=&S0\n",
        "//P PROC " + "'" * 50001 + "\n//S EXEC PGM=X\n//D DD DSN=&A\n",
        "//D DD DSN=A,\n" + "//  X=(((((((((((((,\n" * 3000 + "//  Y=Z\n",
    ],
    ids=["many-refs", "long-chain", "unbalanced-quotes", "long-continuation"],
)
def test_pathological_input_stays_linear(src):
    start = time.perf_counter()
    extract_boundary("jcl", src)
    assert time.perf_counter() - start < 2.0


# ------------------------------------------------------------------------------
# THE ANSWER KEY'S INDEPENDENT READER AGREES (differential contract)
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "src",
    [
        RUN_JCL,
        INSTREAM.format(invocations="//STEP1 EXEC COMPILE,MEM=CBACT01C,HLQ=TEST"),
        INSTREAM.format(invocations="//S1 EXEC COMPILE,MEM=A,HLQ=T\n//S2 EXEC COMPILE,MEM=B,HLQ=T"),
        INSTREAM.format(invocations=""),
    ],
    ids=["run-jcl", "override", "ambiguous", "never-invoked"],
)
def test_the_key_reader_agrees_with_the_engine(src):
    """The differential's compared side (cobol_answer_key.jcl_dataset_bindings)
    reads the RAW member with its own scanner; on these shapes it must land on
    exactly the engine's bindings and resolutions."""
    engine = extract_boundary("jcl", _stream(src))["datasets"]
    assert ak.jcl_dsn_values(ak.jcl_dataset_bindings(src)) == ak.jcl_dsn_values(engine)
