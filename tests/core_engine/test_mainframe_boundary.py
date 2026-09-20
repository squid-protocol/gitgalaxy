"""
#3200/#3201: the named mainframe boundary channel.

`ipc_rpc_bridges` and `io` count THAT a COBOL program calls out and touches
files. These tests pin the channel that says WHAT: the call graph (COBOL `CALL`,
CICS `LINK`/`XCTL`, JCL `EXEC PGM=`) and the dataset boundary (`SELECT ...
ASSIGN` with its `OPEN` modes, and the JCL `DD` binding).

Every fixture here is the shape of REAL source from the pinned corpora, not a
minimal one -- the multi-line `OPEN`, the `EXEC CICS LINK` whose `PROGRAM(...)`
sits on the next line, the unnamed continuation `DD`, and the working-storage
`VALUE` indirection that 124 of CBSA's 144 call sites use. Each of those broke a
first draft of this module.
"""

import pytest

from gitgalaxy.core.mainframe_boundary import BOUNDARY_DIALECTS, extract_boundary
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# IBM/zopeneditor-sample SAM1.cbl's real shape: four SELECTs, one multi-line
# multi-mode OPEN, and a CALL through a working-storage VALUE.
COBOL_BATCH = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SAM1.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUSTOMER-FILE ASSIGN TO CUSTFILE
               ACCESS IS SEQUENTIAL
               FILE STATUS  IS  WS-CUSTFILE-STATUS.

           SELECT CUSTOMER-FILE-OUT ASSIGN TO CUSTOUT
               ACCESS IS SEQUENTIAL.

            SELECT TRANSACTION-FILE ASSIGN TO TRANFILE.
            SELECT REPORT-FILE      ASSIGN TO CUSTRPT.
       WORKING-STORAGE SECTION.

       01 SAM2                          PIC X(8) VALUE 'SAM2'.
       PROCEDURE DIVISION.
       100-MAIN.
           OPEN INPUT TRANSACTION-FILE
              CUSTOMER-FILE
                OUTPUT CUSTOMER-FILE-OUT
              REPORT-FILE.
           CALL SAM2 USING WS-PARMS.
           STOP RUN.
"""

# cics-banking-sample-application-cbsa BNK1CAC.cbl's real shape: the abend
# program reached through a VALUE clause, and a LINK whose PROGRAM operand is on
# the following line.
COBOL_CICS = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BNK1CAC.
       WORKING-STORAGE SECTION.

       01 WS-ABEND-PGM                 PIC X(8) VALUE 'ABNDPROC'.
       PROCEDURE DIVISION.
       CAD010.
           EXEC CICS LINK
              PROGRAM('CREACC')
              COMMAREA(SUBPGM-PARMS)
              RESP(WS-CICS-RESP)
           END-EXEC.

                EXEC CICS LINK PROGRAM(WS-ABEND-PGM)
                          COMMAREA(ABNDINFO-REC)
                END-EXEC
           EXEC CICS XCTL PROGRAM('BNKMENU') END-EXEC.
           CALL 'CEEGMT' USING WS-GMT.
"""

JCL_JOB = """\
//ZDERUN  JOB ,NOTIFY=&SYSUID,
// MSGCLASS=H,MSGLEVEL=(1,1),REGION=144M
//LINKSAM1 EXEC PGM=IEWL,REGION=3000K
//SYSLIB   DD  DISP=SHR,DSN=&LINKLIB
//         DD  DISP=SHR,DSN=&HLQ..SAMPLE.LOAD
//SYSLIN   DD *
     INCLUDE OBJ(SAM1)
/*
//SAM1  EXEC   PGM=SAM1
//STEPLIB DD DSN=&HLQ..SAMPLE.LOAD,DISP=SHR
//SYSOUT   DD SYSOUT=*
//CUSTFILE DD DISP=SHR,DSN=&HLQ..SAMPLE.CUSTFILE
//CUSTOUT  DD DSN=&HLQ..SAMPLE.CUSTOUT,
//    DISP=(NEW,CATLG),UNIT=SYSDA,SPACE=(TRK,(10,10),RLSE)
//WORKTEMP DD DSN=&&SCRATCH,DISP=(NEW,PASS)
"""


def _calls(dialect, source):
    return extract_boundary(dialect, source)["calls"]


def _datasets(dialect, source):
    return extract_boundary(dialect, source)["datasets"]


# ==============================================================================
# REGISTRY WIRING
# ==============================================================================
def test_the_declaration_is_top_level_not_a_rule():
    """`boundary_extraction` must not live in `rules`.

    language_lens.py's `_calibrate_lookup_maps` re.compile()s every STRING value
    inside a language's `rules` dict, as a guard for definitions loaded from
    external JSON. A string helper key placed there arrives at the worker as a
    compiled Pattern, matches no dialect, and silently extracts nothing -- while
    every unit test, which builds from LANGUAGE_DEFINITIONS directly, stays
    green. That is exactly how #2806 blessed a wrong golden master.
    """
    for lang in BOUNDARY_DIALECTS:
        definition = LANGUAGE_DEFINITIONS[lang]
        assert definition.get("boundary_extraction") == lang
        assert "boundary_extraction" not in definition["rules"]
        assert "_boundary_extraction" not in definition["rules"]


def test_only_the_declared_dialects_extract_anything():
    """An undeclared language degrades to no facts, never to an exception."""
    assert extract_boundary("python", "CALL 'X'\nSELECT A ASSIGN TO B.") == {"calls": [], "datasets": []}
    assert extract_boundary("cobol", "") == {"calls": [], "datasets": []}


# ==============================================================================
# #3200: THE CALL GRAPH
# ==============================================================================
def test_call_through_a_working_storage_value_resolves_to_the_literal():
    """The dominant real idiom: `CALL SAM2` where `01 SAM2 ... VALUE 'SAM2'`."""
    (call,) = _calls("cobol", COBOL_BATCH)
    assert (call["verb"], call["form"], call["operand"], call["target"]) == ("CALL", "identifier", "SAM2", "SAM2")


def test_value_clause_above_a_blank_line_is_still_found():
    """Regression: the entry anchor needs re.MULTILINE.

    Without it the level-number anchor only fired on the first line of the
    buffer it was handed, so a data item preceded by a blank line was invisible
    -- which silently lost ALL 124 of CBSA's VALUE-resolved LINK targets while
    every call site was still reported, just with target=None.
    """
    assert "\n\n       01 WS-ABEND-PGM" in COBOL_CICS
    by_operand = {c["operand"]: c for c in _calls("cobol", COBOL_CICS)}
    assert by_operand["WS-ABEND-PGM"]["target"] == "ABNDPROC"


def test_cics_link_and_xctl_including_a_program_operand_on_the_next_line():
    calls = _calls("cobol", COBOL_CICS)
    got = {(c["verb"], c["form"], c["operand"], c["target"]) for c in calls}
    assert ("LINK", "literal", "CREACC", "CREACC") in got
    assert ("LINK", "identifier", "WS-ABEND-PGM", "ABNDPROC") in got
    assert ("XCTL", "literal", "BNKMENU", "BNKMENU") in got
    assert ("CALL", "literal", "CEEGMT", "CEEGMT") in got


def test_line_numbers_are_the_exec_verb_line():
    """A call is recorded at its verb, not at the operand that may follow it."""
    lines = COBOL_CICS.split("\n")
    by_operand = {c["operand"]: c for c in _calls("cobol", COBOL_CICS)}
    assert "EXEC CICS LINK" in lines[by_operand["CREACC"]["line"] - 1]
    assert "PROGRAM('CREACC')" in lines[by_operand["CREACC"]["line"]]


def test_an_unreadable_target_keeps_the_site_and_reports_no_target():
    """A dynamic CALL whose VALUE clause is not in this file is data, not silence.

    The site, its verb and its operand are all recorded; only `target` is None.
    That distinction is what lets a consumer tell "dynamic dispatch the engine
    could not follow" from "no call here".
    """
    (call,) = _calls("cobol", "       PROCEDURE DIVISION.\n       CALL WS-PGM-FROM-COPYBOOK.\n")
    assert call["operand"] == "WS-PGM-FROM-COPYBOOK"
    assert call["target"] is None
    assert call["form"] == "identifier"


def test_a_verb_inside_a_string_literal_is_not_a_call():
    """`DISPLAY \'GNP CALL FAILED :\'` is a message, not a call to FAILED.

    Found on aws-mainframe-modernization-carddemo, which has no answer key and
    so was audited separately: 5 of 102 extracted sites were this exact shape,
    an IMS status message naming the verb that had just run. Neither
    answer-keyed corpus contains it.
    """
    src = (
        "       PROCEDURE DIVISION.\n"
        "           DISPLAY 'GNP CALL FAILED  :' PAUT-PCB-STATUS\n"
        "           DISPLAY 'GU CALL TO ROOT SEG SUCCESS'\n"
        "           DISPLAY 'LINK PROGRAM(NOTREAL) FAILED'\n"
    )
    assert _calls("cobol", src) == []


def test_the_literal_guard_does_not_swallow_a_real_call_on_the_same_line():
    """A quoted operand opens its literal AFTER the verb, so the verb is never shielded."""
    src = "       PROCEDURE DIVISION.\n           MOVE 'X' TO WS-A  CALL 'REALPGM'.\n"
    (call,) = _calls("cobol", src)
    assert (call["form"], call["target"]) == ("literal", "REALPGM")


def test_quote_state_resets_each_line():
    """An unbalanced apostrophe must not shield the rest of the file.

    `AUTHOR. James O'Grady.` is real accepted source, and tracking quote state
    across lines from it hid the remainder of a program from the answer-key
    drafter (#3210). Literals do not span a physical line here.
    """
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       AUTHOR. James O'Grady.\n"
        "       PROCEDURE DIVISION.\n"
        "           CALL 'STILLSEEN'.\n"
    )
    assert [c["target"] for c in _calls("cobol", src)] == ["STILLSEEN"]


def test_end_call_is_not_a_call():
    """`END-CALL` closes a CALL; it never opens one."""
    assert _calls("cobol", "       PROCEDURE DIVISION.\n       END-CALL.\n") == []


def test_jcl_exec_pgm_only_programs_not_procedures():
    """`EXEC PGM=` is a program; `EXEC name` / `EXEC PROC=` is jcl's `api` rule's."""
    calls = _calls("jcl", JCL_JOB)
    assert [(c["operand"], c["verb"]) for c in calls] == [("IEWL", "EXEC PGM"), ("SAM1", "EXEC PGM")]
    assert _calls("jcl", "//STEP1 EXEC MYPROC\n//STEP2 EXEC PROC=OTHER\n") == []


# ==============================================================================
# #3201: THE DATASET BOUNDARY
# ==============================================================================
def test_multi_line_multi_mode_open_assigns_each_file_its_own_mode():
    """`OPEN INPUT A B OUTPUT C D.` spanning four lines: the mode switches at each keyword."""
    modes = {d["internal_name"]: (d["dd_name"], d["modes"]) for d in _datasets("cobol", COBOL_BATCH)}
    assert modes == {
        "CUSTOMER-FILE": ("CUSTFILE", ["INPUT"]),
        "CUSTOMER-FILE-OUT": ("CUSTOUT", ["OUTPUT"]),
        "TRANSACTION-FILE": ("TRANFILE", ["INPUT"]),
        "REPORT-FILE": ("CUSTRPT", ["OUTPUT"]),
    }


def test_a_selected_file_that_is_never_opened_keeps_no_mode():
    """A SELECT is a declaration; only an OPEN is an access."""
    (rec,) = _datasets("cobol", "       FILE-CONTROL.\n           SELECT UNUSED-FILE ASSIGN TO NEVERDD.\n")
    assert (rec["dd_name"], rec["modes"]) == ("NEVERDD", [])


def test_io_and_extend_are_recorded_as_themselves():
    """I-O and EXTEND are their own modes; collapsing them to read/write is the consumer's call."""
    src = (
        "       FILE-CONTROL.\n"
        "           SELECT MASTER-FILE ASSIGN TO MASTER.\n"
        "           SELECT LOG-FILE ASSIGN TO AUDITLOG.\n"
        "       PROCEDURE DIVISION.\n"
        "           OPEN I-O MASTER-FILE EXTEND LOG-FILE.\n"
    )
    assert {d["dd_name"]: d["modes"] for d in _datasets("cobol", src)} == {
        "MASTER": ["I-O"],
        "AUDITLOG": ["EXTEND"],
    }


def test_assign_device_prefix_is_stripped_for_the_ddname_but_kept_raw():
    """`ASSIGN TO UT-S-CUSTFILE` binds DD CUSTFILE; the operand as written is kept."""
    (rec,) = _datasets("cobol", "       FILE-CONTROL.\n           SELECT C-FILE ASSIGN TO UT-S-CUSTFILE.\n")
    assert (rec["assign_name"], rec["dd_name"]) == ("UT-S-CUSTFILE", "CUSTFILE")


def test_jcl_dd_binding_carries_its_step_and_inherits_an_unnamed_continuation():
    """An unnamed `//  DD` concatenates onto the ddname above it."""
    by_line = {(d["step_name"], d["dd_name"], d["dsn"]) for d in _datasets("jcl", JCL_JOB)}
    assert ("LINKSAM1", "SYSLIB", "&LINKLIB") in by_line
    # the unnamed continuation DD belongs to SYSLIB, not to nothing
    assert ("LINKSAM1", "SYSLIB", "&HLQ..SAMPLE.LOAD") in by_line
    assert ("SAM1", "CUSTFILE", "&HLQ..SAMPLE.CUSTFILE") in by_line
    # DSN on a continuation line of its own DD statement
    assert ("SAM1", "CUSTOUT", "&HLQ..SAMPLE.CUSTOUT") in by_line


def test_jcl_skips_instream_payload_sysout_and_job_local_temporaries():
    """None of these is an external dataset binding."""
    bound = {d["dd_name"] for d in _datasets("jcl", JCL_JOB)}
    assert "SYSLIN" not in bound, "`DD *` opens in-stream data, not a dataset"
    assert "SYSOUT" not in bound, "SYSOUT= is spooled output, carrying no DSN"
    assert "WORKTEMP" not in bound, "DSN=&&NAME is a job-local temporary"


def test_instream_payload_cannot_be_read_as_jcl():
    """`INCLUDE OBJ(SAM1)` sits inside a `DD *` payload and is not a JCL statement."""
    assert all("OBJ" != d["dd_name"] for d in _datasets("jcl", JCL_JOB))


# ==============================================================================
# THE COMMENT STREAM IS NOT THE CODE STREAM
# ==============================================================================
def test_extraction_reads_whatever_stream_it_is_given():
    """The worker hands this module the prism CODE stream, so comments are already gone.

    Pinned as a contract rather than an implementation detail: if a caller ever
    passes raw source instead, a commented-out CALL becomes a call edge.
    """
    commented = "      * CALL 'GHOSTPGM' USING WS-X.\n"
    assert _calls("cobol", commented), "raw source WOULD yield a phantom call -- hence the code-stream contract"
    assert _calls("cobol", "\n") == []


# ==============================================================================
# REDOS: every pattern is bounded
# ==============================================================================
@pytest.mark.parametrize("dialect", BOUNDARY_DIALECTS)
@pytest.mark.parametrize(
    "payload",
    [
        "CALL " + "A" * 40000,
        "EXEC CICS LINK PROGRAM(" + "B" * 40000,
        "SELECT " + "C" * 20000 + " ASSIGN TO ",
        "       01 X PIC X VALUE '" + "D" * 40000,
        "//DD1 DD DSN=" + "E" * 40000,
        "//" + " " * 40000,
        ("OPEN INPUT " + "F" * 200 + " ") * 200,
        "." * 40000,
    ],
)
def test_pathological_input_is_bounded(dialect, payload):
    """No input may take super-linear time: every scan here is a bounded one."""
    import time

    start = time.perf_counter()
    extract_boundary(dialect, payload)
    assert time.perf_counter() - start < 2.0, f"{dialect} took too long on a {len(payload)}-char payload"


def test_an_unterminated_exec_cics_cannot_scan_the_whole_file():
    """A LINK with no END-EXEC is capped, so one malformed block cannot read the rest of the program."""
    src = "       EXEC CICS LINK\n" + "           MOVE X TO Y\n" * 500 + "           PROGRAM('TOOFAR')\n"
    (call,) = _calls("cobol", src)
    assert call["target"] is None, "a PROGRAM operand thousands of chars away is not this block's"
