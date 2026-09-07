"""jcl strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

# ==============================================================================
# JCL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #590, part of epic #518)
# ==============================================================================
JCL_RULES = LANGUAGE_DEFINITIONS["jcl"]["rules"]

_JCL_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "//         IF (STEP1.RC = 0) THEN", "//STEP1   EXEC PGM=IEFBR14"),
    ("structural_boundaries", "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR", "//STEP1   EXEC PGM=IEFBR14"),
    ("func_start", "//STEP1   EXEC PGM=IEFBR14", "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR"),
    ("class_start", "//MYJOB   JOB (ACCT),'PROGRAMMER'", "//STEP1   EXEC PGM=IEFBR14"),
    ("high_risk_execution", "//STEP1   EXEC PGM=IKJEFT01,DYNAMNBR=20", "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR"),
    ("io", "//SYSPRINT DD SYSOUT=*", "//STEP1   EXEC PGM=IEFBR14"),
    ("state_mutation", "//         SET SYMVAR=VALUE", "//STEP1   EXEC PGM=IEFBR14"),
    ("import", "//         INCLUDE MEMBER=STDPROC1", "//STEP1   EXEC PGM=IEFBR14"),
    ("ownership", "//*Author: Jane Doe", "//* just a routine comment"),
    # --- ADVERSARIAL CASES ---
    # branch: anchored properly vs inline data
    ("branch", "//IF1     IF (STEP1.RC=0) THEN", "IF (STEP1.RC=0) THEN"),
    ("branch", "//        ELSE", "ELSE inside some text"),
    ("branch", "//ELSE1   ELSE", "//ENDIF1  ENDIF"),  # 2822 corollary 2: closing word
    ("branch", "//$IF     IF (RC > 0) THEN", "    IF  "),
    ("branch", "//#IF_A   ELSE", "//* IF"),
    ("branch", "//@123    IF (RC = 0)", "//@123    ENDIF"),  # IFX is not IF; ENDIF closed (#2822)
    # args: unnamed procs, spaces, etc
    ("args", "//PROC1   PROC A=1,B=2", "//PROC1   PROC"),  # no parm/proc args
    ("args", "//        EXEC PGM=FOO,PARM='A,B,C'", "//        EXEC PGM=FOO"),
    ("args", "//STEP1   EXEC PGM=FOO, PARM='A,B,C'", "//STEP1   EXEC PGM=FOO, COND=(0,NE)"),
    ("args", "//STEP1   EXEC PGM=FOO,PARM=(A,B,C)", "//* STEP1 EXEC PGM=FOO,PARM=A"),
    ("args", "//STEP1   EXEC PGM=FOO,PARM=A", "//* EXEC PGM=FOO,PARM=A"),
    ("args", "//STEP1   EXEC PGM=FOO,  PARM='FOO,BAR'", "//STEP EXEC PGM=FOO,PARM="),  # PARM is empty
    ("args", "//$TEP    EXEC PGM=F,PARM='  '", "//STEP PARM='A'"),  # PARM without EXEC
    ("args", "//A       PROC ARG=1", "//A       PROC  "),  # trailing spaces but no args
    # func_start: unnamed steps, trailing strings
    ("func_start", "//        EXEC PGM=FOO", "EXEC PGM=FOO"),
    ("func_start", "//$TEP#@  EXEC PGM=FOO", "//STEP EXECUTING"),
    ("func_start", "//STEP123 EXEC PGM=FOO", "//* EXEC PGM=FOO"),
    ("func_start", "//STEP_1  EXEC PGM=FOO", "//STEP_1 EXECUTING"),
    ("func_start", "//123456  EXEC PGM=FOO", "//*123456 EXEC PGM=FOO"),
    (
        "func_start",
        "//@@@@    EXEC PGM=FOO",
        "//EXEC PGM=FOO",
    ),  # No space between // and EXEC is actually an unnamed step with EXEC as operation? No, if no space it's name=EXEC. Operation follows.
    ("func_start", "//        EXEC", "EXEC "),  # just EXEC
    # class_start: symbols in job name, but not empty
    ("class_start", "//#JOB@$  JOB (123),'TEST'", "JOB (123),'TEST'"),
    ("class_start", "//JOB1    JOB (123),'TEST'", "// JOB (123),'TEST'"),  # Job must have name
    ("class_start", "//A       JOB", "//*JOB1 JOB"),
    ("class_start", "//$1      JOB CLASS=A", "JOB CLASS=A"),
    ("class_start", "//_JOB    JOB (0000)", "//_JOB JOBS"),
    # structural_boundaries: unnamed boundaries, etc
    ("structural_boundaries", "//        DD DSN=...", "//DD1 DATA"),
    ("structural_boundaries", "//        INCLUDE MEMBER=...", "//* INCLUDE MEMBER=..."),
    ("structural_boundaries", "//        SET A=1", "SET A=1"),
    ("structural_boundaries", "//        PROC", "PROC"),
    ("structural_boundaries", "//        PEND", "PEND"),
    ("structural_boundaries", "//$DD     DD DUMMY", "// DUMMY"),
    ("structural_boundaries", "//INC     INCLUDE MEMBER=A", "INCLUDE MEMBER=A"),
    ("structural_boundaries", "//@SET    SET X=Y", "SET X=Y"),
    # #2610: safety = COND= return-code tests; the bare bypass forms are
    # excluded (they belong to safety_bypasses, not safety)
    ("safety", "//S1      EXEC PGM=X,COND=(4,LT)", "//S2      EXEC PGM=Y,COND=EVEN"),
    ("safety", "//        COND=(0,NE,STEP1)", "//S2      EXEC PGM=Y,COND=ONLY"),
    ("safety", "//S3      EXEC PGM=Z,COND=((4,LT),EVEN)", "//S4      EXEC PGM=W,CONDX=(4,LT)"),
    # #2610: safety_bypasses = COND=EVEN / COND=ONLY (run despite abend)
    ("safety_bypasses", "//S2      EXEC PGM=Y,COND=EVEN", "//S1      EXEC PGM=X,COND=(4,LT)"),
    ("safety_bypasses", "//S2      EXEC PGM=Y,COND=ONLY", "//S1      EXEC PGM=X,COND=(4,LT,STEP1)"),
    ("safety_bypasses", "//S3      EXEC PGM=Z,COND=((4,LT),EVEN)", "//S4      EXEC PGM=W,COND=(4,LT),PARM='EVENT'"),
    # #2610: telemetry = job-log verbosity/routing operands
    ("telemetry", "//J       JOB 1,MSGLEVEL=(1,1)", "//S1      EXEC PGM=X"),
    ("telemetry", "//J       JOB 1,MSGCLASS=H", "//J       JOB 1,CLASS=A"),
    # #2610: comment-anchored debt markers (shared GLOBAL_* patterns; only
    # meaningful now that prism routes //* lines to the comment stream)
    ("planned_debt", "//* TODO wire the FTP step", "//* all wired up here"),
    ("fragile_debt", "//* HACK: overrides the region size", "//* routine banner comment"),
    # #2732: dead_code = a statement commented out by turning `//` into `//*`.
    # Each negative is a real prose-banner shape from the pool corpus that a
    # bare `(?:EXEC|DD|JOB|SET|INCLUDE)\b` keyword rule would have counted.
    ("dead_code", "//*STEP1   EXEC PGM=IEFBR14", "//* EXECUTE DUMP UTILITY PROGRAM TO PRINT THE"),
    ("dead_code", "//*        DD DSN=OLD.FILE,DISP=SHR", "//* SET THE RETURN CODE TO CONTROL IF CICS"),
    ("dead_code", "//*CREL005 JOB ,,CLASS=A,MSGCLASS=H,", "//* PROC statements are documented in the runbook"),
    ("dead_code", "//*        SET COUNTER=1", "//* JOB scheduling notes live in the runbook"),
    ("dead_code", "//*        INCLUDE MEMBER=OLDPROC", "//* INCLUDE the operations team on any change"),
    # #2733: sync_locks = the exclusive-ENQ dispositions. DISP=SHR (shared
    # access, the default request) and DISP=NEW (allocation) are excluded.
    ("sync_locks", "//SYSLIN   DD DISP=OLD,DSN=HLQ.SAMPLE.OBJ(SAM1)", "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR"),
    (
        "sync_locks",
        "//DD1      DD DSN=HLQ.CUSTRPT,DISP=(MOD,DELETE,DELETE),",
        "//SYSUT2   DD DISP=(NEW,CATLG),DSN=HLQ.OUT",
    ),
    ("sync_locks", "//SYSLIN   DD  DSNAME=&&LOADSET,DISP=(OLD,DELETE)", "//S1      EXEC PGM=IEBGENER,PARM='OLDMODE'"),
    # #2732: spec_exposure = the generic traceability tag, `//*`-anchored
    ("spec_exposure", "//* [SPEC-4412] see the change request", "//* nothing traceable here"),
    ("spec_exposure", "//* raised under [audit] last quarter", "//* the behaviour is [specified] upstream"),
    # #2748: api = the PROC statement (the callable surface `EXEC name` invokes)
    ("api", "//IGYWCLG PROC LNGPRFX='IGY630',LIBPRFX='CEE',SRC=COBOL", "//CBL0001  EXEC IGYWCLG"),
    ("api", "//DB2JCL   PROC", "//STEP1    EXEC PROC=DB2JCL"),
    ("api", "//         PROC", "//SYSPROC  DD DSN=SYS1.SYSPROC,DISP=SHR"),
    # #2749: cleanup = DELETE as the normal-termination disposition
    (
        "cleanup",
        "//DD1      DD DSN=HLQ.CUSTRPT,DISP=(MOD,DELETE,DELETE),",
        "//SYSUT2   DD DISP=(NEW,CATLG,DELETE),DSN=HLQ.OUT",
    ),
    ("cleanup", "//SYSLIN   DD DISP=(OLD,DELETE),DSN=&&LOADSET", "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR"),
    (
        "cleanup",
        "//TEMP     DD DISP=(,DELETE),UNIT=SYSDA,SPACE=(TRK,1)",
        "//SYSIN    DD *\n  DELETE HLQ.OLD.CLUSTER CLUSTER",
    ),
    # #2750: globals = the job-scoped declarations (JOBLIB, SET, EXPORT SYMLIST)
    ("globals", "//JOBLIB   DD DSN=DSNC10.SDSNLOAD,DISP=SHR", "//STEPLIB  DD DSN=DSNC10.SDSNLOAD,DISP=SHR"),
    ("globals", "//    SET HLQ='IBMUSER'       *TSO USER ID", "//IGYWCLG PROC LNGPRFX='IGY630'"),
    ("globals", "// EXPORT SYMLIST=*", "//JOBLIBX  DD DSN=MY.LOAD,DISP=SHR"),
    # #2751: high_risk_execution = the command executors only, not every PGM=
    ("high_risk_execution", "//GRANT    EXEC PGM=IKJEFT01,DYNAMNBR=20", "//STEP1    EXEC PGM=IEFBR14"),
    ("high_risk_execution", "//SH       EXEC PGM=BPXBATCH,PARM='SH ls /tmp'", "//COBOL    EXEC PGM=IGYCRCTL,REGION=0M"),
    ("high_risk_execution", "//REXX     EXEC PGM=IRXJCL,PARM='MYEXEC'", "//DEL      EXEC PGM=IDCAMS"),
]


@pytest.mark.parametrize("signature,positive,negative", _JCL_SIMPLE_CASES)
def test_jcl_signature_positive_and_negative(signature, positive, negative):
    pattern = JCL_RULES[signature]
    assert pattern is not None, f"jcl's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"jcl {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"jcl {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_jcl_func_start_and_class_start_capture_names():
    func_start = JCL_RULES["func_start"]
    m = func_start.search("//STEP1   EXEC PGM=IEFBR14")
    assert m and m.group(1) == "STEP1"

    class_start = JCL_RULES["class_start"]
    m2 = class_start.search("//MYJOB   JOB (ACCT),'PROGRAMMER'")
    assert m2 and m2.group(1) == "MYJOB"


def test_jcl_dependency_capture_extracts_include_member():
    """
    `_dependency_capture` was missing entirely for jcl despite `import` being
    non-None -- unlike nearly every other language in the registry with a
    non-None `import`, jcl's dependency graph never captured which member a
    job/proc pulls in via INCLUDE. Added to fix that gap; covers both the
    named and (more common) unnamed INCLUDE statement forms.
    """
    pattern = JCL_RULES["_dependency_capture"]
    assert pattern is not None, "jcl's _dependency_capture should no longer be missing"
    m = pattern.search("//         INCLUDE MEMBER=STDPROC1")
    assert m and m.group(1) == "STDPROC1"
    m2 = pattern.search("//INCMEM   INCLUDE MEMBER=COMMLIB1")
    assert m2 and m2.group(1) == "COMMLIB1"


def test_jcl_structural_boundaries_unnamed_dd_regression():
    """
    Regression test for a real bug: the name segment between `//` and the
    statement keyword was required (`+`), missing the very common unnamed
    continuation-DD form (`//         DD DSN=...`, concatenating a dataset
    onto the preceding DD with no ddname of its own) -- a routine, everyday
    JCL idiom (e.g. STEPLIB concatenation across multiple load libraries),
    not a synthetic edge case.
    """
    old_pattern = re.compile(r"^[ \t]*//[A-Za-z0-9_#$@]+[ \t]+(?:DD|INCLUDE|SET|PROC|PEND)\b", re.M | re.I)
    unnamed = "//         DD DSN=USER.LOADLIB,DISP=SHR"
    assert not old_pattern.search(unnamed), "sanity check: bug must reproduce against the old pattern"

    pattern = JCL_RULES["structural_boundaries"]
    assert pattern.search(unnamed), "unnamed continuation-DD form still didn't match"
    assert pattern.search("//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR"), "named DD form regressed"
    assert pattern.search("//MYPROC   PROC"), "PROC form regressed"


def test_jcl_import_unnamed_include_regression():
    """
    Regression test for a real bug: same shape as structural_boundaries'
    unnamed-DD gap above -- INCLUDE statements, like DD, are commonly
    written unnamed.
    """
    old_pattern = re.compile(r"^[ \t]*//[A-Za-z0-9_#$@]+[ \t]+INCLUDE\b", re.M | re.I)
    unnamed = "//         INCLUDE MEMBER=STDPROC1"
    assert not old_pattern.search(unnamed), "sanity check: bug must reproduce against the old pattern"

    pattern = JCL_RULES["import"]
    assert pattern.search(unnamed), "unnamed INCLUDE form still didn't match"
    assert pattern.search("//INCMEM   INCLUDE MEMBER=COMMLIB1"), "named INCLUDE form regressed"


def test_jcl_state_mutation_anchored_no_false_positive_regression():
    """
    Regression test for a real bug: `state_mutation` was completely
    unanchored (`\\bSET\\s+NAME=`), matching "SET" anywhere in the scanned
    text -- including inline SYSIN card data (`//SYSIN DD *` ... `/*`),
    which is arbitrary payload data, not a JCL statement at all. A embedded
    SQL/shell/config payload containing "SET X=1" would be misattributed to
    jcl's own state mutation. Anchored to a real `//name SET var=value`
    statement line, mirroring structural_boundaries' own SET handling.
    """
    old_pattern = re.compile(r"\bSET\s+[A-Za-z0-9_#$@]+=", re.I)
    inline_sysin_data = "SET X=1;"
    assert old_pattern.search(inline_sysin_data), "sanity check: bug must reproduce against the old pattern"

    pattern = JCL_RULES["state_mutation"]
    assert not pattern.search(inline_sysin_data), "inline SYSIN data still incorrectly matched"
    assert pattern.search("//         SET SYMVAR=VALUE"), "real SET statement form regressed"
    assert pattern.search("//SETVAR   SET SYMVAR=VALUE"), "named SET statement form regressed"


def test_jcl_cross_line_false_match_regression():
    """
    Regression test for a real, shared bug across five rules
    (structural_boundaries, func_start, class_start, import, state_mutation,
    ownership): the gap between the name segment and the statement keyword
    (or, for ownership, between the label and its value) used `\\s+`, which
    includes `\\n` under `re.M`. Confirmed this lets a name on one physical
    line falsely bind to a keyword starting an *entirely different* line
    that has no `//` prefix of its own -- JCL statements never span a
    physical line via bare whitespace (only via explicit continuation
    columns; the name+keyword pair itself never wraps, only a continued
    PARAMETER list can -- see test_jcl_args_parm_continuation_line_regression
    for the `args` rule's own bounded support for that, added by #2482).
    Bounded to `[ \\t]+`.
    """
    old_func_start = re.compile(r"^[ \t]*//([A-Za-z0-9_#$@]+)\s+EXEC\b", re.M | re.I)
    old_class_start = re.compile(r"^[ \t]*//([A-Za-z0-9_#$@]+)\s+JOB\b", re.M | re.I)
    old_ownership = re.compile(r"^//\*\s*(?:Author|Created by|Maintainer):\s+(.*)", re.I | re.M)

    cross_line_step = "//STEP01\nEXEC PGM=FOO\n"
    m = old_func_start.search(cross_line_step)
    assert m and m.group(1) == "STEP01", "sanity check: bug must reproduce against the old func_start pattern"

    cross_line_job = "//MYJOB\nJOB (ACCT)\n"
    m2 = old_class_start.search(cross_line_job)
    assert m2 and m2.group(1) == "MYJOB", "sanity check: bug must reproduce against the old class_start pattern"

    cross_line_author = "//*Author:\n//*Jane Doe\n"
    m3 = old_ownership.search(cross_line_author)
    assert m3 and m3.group(1) == "//*Jane Doe", "sanity check: bug must reproduce against the old ownership pattern"

    assert not JCL_RULES["func_start"].search(cross_line_step), "cross-line func_start false match still occurs"
    assert not JCL_RULES["class_start"].search(cross_line_job), "cross-line class_start false match still occurs"
    assert not JCL_RULES["ownership"].search(cross_line_author), "cross-line ownership false match still occurs"
    assert not JCL_RULES["structural_boundaries"].search("//STEPLIB\nDD DSN=X\n"), (
        "cross-line structural_boundaries false match still occurs"
    )

    # real same-line forms must still work after the fix
    assert JCL_RULES["func_start"].search("//STEP01  EXEC PGM=IEFBR14")
    assert JCL_RULES["class_start"].search("//MYJOB   JOB (ACCT)")
    assert JCL_RULES["ownership"].search("//*Author: Jane Doe").group(1) == "Jane Doe"


def test_jcl_args_parm_continuation_line_regression():
    """
    Regression test for #2482: the `args` regex only ever saw `PARM=` when it
    sat on the EXEC statement's own physical line -- a real, common JCL idiom
    (docs/language_status/jcl.md documented ~16-18 corpus occurrences missed
    this way) since `PARM=` routinely lands on a `//` continuation line
    instead, sometimes more than one hop away.
    """
    old_pattern = re.compile(
        r"^[ \t]*//[A-Za-z0-9_#$@]*[ \t]+(?:EXEC(?:[ \t].*?)?,[ \t]*PARM=('(?:[^']|'')*'|\([^)]*\)|[^ \t\n,]+)|PROC[ \t]+(\S.*))",
        re.M | re.I,
    )
    pattern = JCL_RULES["args"]

    # cics-genapp/cobol.jcl:68 shape -- PARM= one continuation line down.
    one_hop = "//LKED     EXEC PGM=HEWL,COND=(7,LT,COBL),\n//  PARM='LIST,XREF,RENT,NAME=&MEM'\n"
    assert not old_pattern.search(one_hop), "sanity check: bug must reproduce against the old pattern"
    m = pattern.search(one_hop)
    assert m and m.group(1) == "'LIST,XREF,RENT,NAME=&MEM'", "single-continuation PARM= still not found"

    # cics-banking-sample-application-cbsa/CICSTS56.jcl:45 shape -- a second
    # continuation line (COND=...,) sits between EXEC and the PARM= line.
    two_hop = "//CICS    EXEC PGM=DFHSIP,REGION=&REG,TIME=1440,\n// COND=(1,NE,CICSCNTL),\n// PARM='START=&START,SYSIN',MEMLIMIT=16G\n"
    m2 = pattern.search(two_hop)
    assert m2 and m2.group(1) == "'START=&START,SYSIN'", "two-hop continuation PARM= still not found"

    # cics-genapp/defdrep.jcl shape -- PARM=(...) itself keeps going across
    # several MORE continuation lines after the hop that reaches it; the
    # value capture already spans newlines (`[^)]*` doesn't exclude `\n`),
    # this only needed the hop to reach the opening `PARM=(` at all.
    multiline_value = (
        "//DREPINIT EXEC PGM=EYU9XDUT,\n"
        "//             COND=(8,LT),\n"
        "//             PARM=('CMASNAME=<CMASAPPL>',\n"
        "//             'DAYLIGHT=N',\n"
        "//             'ZONEOFFSET=0')\n"
    )
    m3 = pattern.search(multiline_value)
    assert m3 and m3.group(1).startswith("('CMASNAME=<CMASAPPL>'") and m3.group(1).endswith("'ZONEOFFSET=0')"), (
        "multi-line PARM=(...) continuation value not fully captured"
    )

    # Same-line PARM= (the common case) must be unaffected.
    assert pattern.search("//STEP1   EXEC PGM=FOO,PARM='SAME-LINE'").group(1) == "'SAME-LINE'"

    # A step with NO PARM= anywhere, even across a trailing-comma
    # continuation, must still not match -- the hop must not manufacture a
    # match out of thin air.
    no_parm = "//STEP2   EXEC PGM=FOO,REGION=1M,\n//        COND=(4,LT)\n"
    assert not pattern.search(no_parm), "hop mechanism must not match when no PARM= is ever present"

    # A later, unrelated step's own PARM= must never be attributed to an
    # earlier step that has none of its own (no cross-step bleed).
    two_steps = "//STEP1   EXEC PGM=FOO\n//STEP2   EXEC PGM=BAR,PARM='STEP2ONLY'\n"
    all_matches = list(pattern.finditer(two_steps))
    assert len(all_matches) == 1, "exactly one match expected (STEP2's own), not a bleed onto STEP1"
    assert all_matches[0].group(1) == "'STEP2ONLY'"
    assert all_matches[0].start() == two_steps.index("//STEP2"), "match must anchor to STEP2's own line, not STEP1's"


def test_jcl_args_redos_immunity():
    """
    ReDoS immunity for #2482's continuation-hop addition specifically --
    the hop group is bounded ({0,7} repetitions) and every repetition's
    `[^\\n]*` is itself bounded to a single physical line, so this can't
    backtrack catastrophically even when fed a long run of comma-heavy
    lines that never actually reach a `//`-prefixed continuation (the
    shape that would matter if the bound were missing).
    """
    pattern = JCL_RULES["args"]
    assert_redos_immune(pattern, "//X EXEC PGM=Y," + "A," * 20000, timeout_sec=3.0)
    many_fake_hops = "//X EXEC PGM=Y,\n" + "\n".join(f"//   FIELD{i}=VAL{i}," for i in range(20000))
    assert_redos_immune(pattern, many_fake_hops, timeout_sec=3.0)


def test_jcl_cond_safety_vs_bypass_partition():
    """
    #2610: the two COND= rules partition by semantics, not by keyword --
    a plain RC test is safety only, a bare EVEN/ONLY is bypass only, and
    the combined form carries both (a real RC test AND a run-after-abend
    bypass on the same step). An EVEN-shaped token *outside* the COND
    value's own parentheses must not leak into the bypass count.
    """
    safety = JCL_RULES["safety"]
    bypass = JCL_RULES["safety_bypasses"]

    plain = "//S1      EXEC PGM=X,COND=(4,LT)"
    assert safety.search(plain) and not bypass.search(plain)

    bare_even = "//S2      EXEC PGM=Y,COND=EVEN"
    assert bypass.search(bare_even) and not safety.search(bare_even)

    combined = "//S3      EXEC PGM=Z,COND=((4,LT),EVEN)"
    assert safety.search(combined) and bypass.search(combined)

    # EVEN-ish text later on the line, outside the COND parens, is not a bypass
    outside = "//S4      EXEC PGM=W,COND=(4,LT),PARM='EVENT'"
    assert safety.search(outside) and not bypass.search(outside)

    # continuation-line COND= (the same real-corpus shape #2482 documents
    # for PARM=) still counts -- the rule is operand-anchored, not line-anchored
    continuation = "//S5      EXEC PGM=V,\n//             COND=ONLY"
    assert bypass.search(continuation)


def test_jcl_cond_bypass_redos_immunity():
    """
    #2610: the combined-form branch's scan is the bounded one-level-paren
    idiom -- alternatives disjoint on their first character, inner star
    inside literal parens -- fed here with an adversarial run that never
    closes and never reaches EVEN/ONLY (the shape that would matter if
    the alternation partitioned ambiguously).
    """
    pattern = JCL_RULES["safety_bypasses"]
    assert_redos_immune(pattern, "//X EXEC PGM=Y,COND=(" + "(A)," * 20000, timeout_sec=3.0)
    assert_redos_immune(pattern, "//X EXEC PGM=Y,COND=(" + "A" * 100000, timeout_sec=3.0)


def test_jcl_sync_locks_only_the_exclusive_enq_dispositions():
    """
    #2733: DISP=OLD/MOD request an exclusive system ENQ on the dataset; DISP=SHR
    and DISP=NEW do not declare contention over an existing resource and must
    stay out of the lock signal. The rule is a deliberately narrow subset of the
    `DISP=` operand `io` already counts (~9% of corpus occurrences), so the
    exclusions are the substance of the design -- assert them directly rather
    than trusting the positive cases alone.
    """
    sync_locks = JCL_RULES["sync_locks"]

    for exclusive in (
        "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=OLD",
        "//SYSLIN   DD DISP=(OLD,DELETE),DSN=&&LOADSET",
        "//DD1      DD DSN=HLQ.CUSTRPT,DISP=(MOD,DELETE,DELETE),",
        "//SYSUT1   DD DISP=(MOD,PASS),SPACE=(CYL,(1,1))",
    ):
        assert sync_locks.search(exclusive), f"missed an exclusive-ENQ disposition: {exclusive!r}"

    for shared_or_new in (
        "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR",
        "//SYSUT2   DD DISP=(NEW,CATLG,DELETE),DSN=HLQ.OUT",
        "//SYSUT3   DD DISP=(,PASS),UNIT=SYSDA",
    ):
        assert not sync_locks.search(shared_or_new), f"counted a non-exclusive disposition: {shared_or_new!r}"

    # The disposition keyword itself is required -- a bare OLD/MOD token
    # elsewhere on the statement (a PARM value, a dataset name) is not a lock.
    for not_a_disposition in (
        "//S1      EXEC PGM=IEBGENER,PARM='OLDMODE'",
        "//SYSUT1   DD DSN=HLQ.OLD.BACKUP,DISP=SHR",
        "//SYSUT1   DD DISP=OLDER",
        "//SYSUT1   DD DISPOSITION=OLD",
    ):
        assert not sync_locks.search(not_a_disposition), f"false positive: {not_a_disposition!r}"

    # Operand-anchored, not line-anchored: DISP= routinely sits on a `//`
    # continuation line rather than the line carrying the ddname (the #2482
    # shape), exactly as io/safety/telemetry already assume.
    continuation = "//SYSUT1   DD DSN=HLQ.WORK,\n//            DISP=(MOD,DELETE,DELETE),\n//            UNIT=SYSDA"
    assert sync_locks.search(continuation)


def test_jcl_sync_locks_overlaps_io_by_design():
    """
    #2733: every sync_locks hit is also an `io` hit, because `io` counts the
    bare `DISP=` keyword. That overlap is the design decision the issue records
    (accepted for a narrow OLD/MOD subset, unlike the broad `cleanup` rule
    #2610 rejected), so pin it as intended behaviour -- if a later change makes
    the two rules disjoint, that is a decision to re-make, not a silent drift.
    """
    sync_locks = JCL_RULES["sync_locks"]
    io = JCL_RULES["io"]

    exclusive = "//SYSLIN   DD DISP=(OLD,DELETE),DSN=&&LOADSET"
    assert sync_locks.search(exclusive) and io.search(exclusive)

    # ...but the converse does not hold: the overwhelming majority of DISP=
    # occurrences (427 of 525 in the corpus) are DISP=SHR, io-only.
    shared = "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR"
    assert io.search(shared) and not sync_locks.search(shared)


def test_jcl_sync_locks_redos_immunity():
    """#2733: no nesting and no unbounded repetition, but hold the line on it."""
    pattern = JCL_RULES["sync_locks"]
    assert_redos_immune(pattern, "//X DD " + "DISP=(" * 20000, timeout_sec=3.0)
    assert_redos_immune(pattern, "//X DD DISP=(" + "OLD" * 50000, timeout_sec=3.0)


def test_jcl_dead_code_counts_through_the_real_comment_stream():
    """
    #2732: end-to-end proof that jcl's two new comment-stream rules actually
    reach counts, not just that the regexes match a string.

    This is the shape #2610 fixed for the debt rules and left half-done: a
    `//*` line is stripped OUT of the code stream by prism._strip_jcl_comments,
    so a rule anchored to `//*` can ONLY ever score via comment_analysis. The
    sample interleaves the three real pool shapes -- commented-out statements,
    English prose banners opening on the same keywords, and a JES3 control verb
    (`//*MAIN`, which JCL_COMMENT_LINE_PATTERN deliberately leaves in the CODE
    stream) -- so a regression in either direction shows up as a count change.
    """
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.core.prism import Prism
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    sample = (
        "//CREL005  JOB ,,CLASS=A,MSGCLASS=H\n"
        "//*CREL005 JOB ,,CLASS=A,MSGCLASS=H,\n"  # commented-out JOB card
        "//*STEP1   EXEC PGM=IEFBR14\n"  # commented-out EXEC
        "//*        DD DSN=OLD.FILE,DISP=SHR\n"  # commented-out DD
        "//*        SET COUNTER=1\n"  # commented-out SET
        "//*        INCLUDE MEMBER=OLDPROC\n"  # commented-out INCLUDE
        "//* SET THE RETURN CODE TO CONTROL IF CICS SHOULD BE\n"  # prose
        "//* EXECUTE DUMP UTILITY PROGRAM TO PRINT THE\n"  # prose
        "//* [SPEC-77] see change request\n"
        "//*MAIN SYSTEM=SY1\n"  # JES3 verb: stays in the code stream
        "//STEP1    EXEC PGM=IEFBR14\n"
    )

    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    streams = prism.split_streams(sample, "jcl")

    # the anchor is only meaningful because `//*` never survives into code
    assert "//*CREL005" not in streams["code_stream"]
    assert "//*MAIN SYSTEM=SY1" in streams["code_stream"]
    assert not JCL_RULES["dead_code"].search(streams["code_stream"])

    equations = StructuralExtractor("jcl", LANGUAGE_DEFINITIONS).splice(
        streams["code_stream"], streams["comment_stream"], raw_content=sample
    )["equations"]

    assert equations["dead_code"] == 5, "one per commented-out statement, no prose banners"
    assert equations["spec_exposure"] == 1


def test_jcl_new_comment_rules_redos_immunity():
    """
    #2732: both new rules use bounded runs whose character class excludes the
    delimiter that must follow it (`[^\\n\\[]{0,200}` before a literal `[`,
    `[^\\]\\n]{0,300}` before a literal `]`, the name charset before `[ \\t]+`),
    so each quantifier has exactly one landing site and there is no ambiguous
    partition to backtrack over. Payloads are long unterminated runs of exactly
    the character each bounded class accepts.
    """
    assert_redos_immune(JCL_RULES["dead_code"], "//*" + "A" * 100000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["dead_code"], "//*" + "A \t" * 40000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["spec_exposure"], "//*" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["spec_exposure"], "//* [spec" + "a" * 100000, timeout_sec=3.0)

    assert JCL_RULES["dead_code"].search("//*STEP1   EXEC PGM=IEFBR14")
    assert JCL_RULES["spec_exposure"].search("//* [SPEC-4412] traceable")


def test_jcl_api_proc_declaration_not_the_call_site():
    """
    #2748: `//name PROC` is JCL's callable surface -- what `EXEC name` and
    `EXEC PROC=name` in other members invoke -- so it is the api rule under
    the #2730 contract's fallback family. Corollary 1 (a reference is not a
    declaration) is the substance: the call sites must stay out, and so must
    every other statement that merely contains the letters PROC.
    """
    api = JCL_RULES["api"]
    assert api is not None, "jcl's api rule is None again (#2748)"

    for declaration, name in (
        ("//IGYWCLG PROC LNGPRFX='IGY630',LIBPRFX='CEE',SRC=COBOL", "IGYWCLG"),
        ("//BATCH  PROC MEMBER=", "BATCH"),
        ("//DB2JCL   PROC                   ", "DB2JCL"),
        ("//COMPROC  PROC", "COMPROC"),
        ("//         PROC", ""),  # a cataloged PROC statement may be unnamed
        ("//$PROC#@  PROC A=1", "$PROC#@"),
    ):
        m = api.search(declaration)
        assert m, f"missed a procedure declaration: {declaration!r}"
        assert m.group(1) == name

    for reference_or_lookalike in (
        "//CBL0001  EXEC IGYWCLG",  # the call site
        "//STEP1    EXEC PROC=DB2JCL",  # the explicit call-site form
        "//SYSPROC  DD DSN=SYS1.SYSPROC,DISP=SHR",  # a ddname ending in PROC
        "//PROCLIB  DD DSN=SYS1.PROCLIB,DISP=SHR",  # a ddname starting with PROC
        "//         PEND",  # closes an in-stream proc; not a second declaration
        "//         PROCESS",  # keyword prefix
        "//* PROC statements are documented in the runbook",  # a comment
        "PROC",  # bare token, no statement prefix
    ):
        assert not api.search(reference_or_lookalike), f"false positive: {reference_or_lookalike!r}"

    # One declaration, one hit, however many parameters it carries across
    # continuation lines.
    multi = (
        "//DSNUPROC PROC LIB='DSNC10.SDSNLOAD',SYSTEM=DBCG,\n//         UID='',UTPROC=''\n//DSNUPROC EXEC PGM=DSNUTILB"
    )
    assert len(api.findall(multi)) == 1


def test_jcl_cleanup_only_the_normal_termination_delete():
    """
    #2749: DELETE as a dataset's normal-termination disposition is JCL's
    teardown idiom (IEFBR14 + DISP=(MOD,DELETE,DELETE) is how a batch job
    deletes a dataset). The rule is deliberately narrower than "DELETE appears
    in a DISP=": the abnormal-termination positional of an allocation,
    `DISP=(NEW,CATLG,DELETE)`, is a conditional disposition on a CREATE and
    stays out, the way DISP=SHR/NEW stay out of sync_locks (#2733). As there,
    the exclusions are the design, so assert them directly.
    """
    cleanup = JCL_RULES["cleanup"]
    assert cleanup is not None, "jcl's cleanup rule is None again (#2749)"

    for teardown in (
        "//DD1      DD DSN=&HLQ..SAMPLE.CUSTRPT,DISP=(MOD,DELETE,DELETE),",
        "//SYSLIN   DD DISP=(OLD,DELETE),DSN=&&LOADSET",
        "//SYSIN    DD DSN=&&TEMPM,DISP=(OLD,DELETE)",
        "//TEMP     DD DISP=(,DELETE),UNIT=SYSDA,SPACE=(TRK,1)",  # omitted status = NEW, scratch dataset
        "//X        DD DISP=( OLD , DELETE )",  # blank-padded positionals
    ):
        assert cleanup.search(teardown), f"missed a teardown disposition: {teardown!r}"

    for not_teardown in (
        "//SYSUT2   DD DISP=(NEW,CATLG,DELETE),DSN=HLQ.OUT",  # abend-only DELETE on an allocation
        "//SYSUT2   DD DISP=(NEW,KEEP,DELETE),DSN=HLQ.OUT",
        "//SYSUT3   DD DISP=(,PASS),UNIT=SYSDA",
        "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR",
        "//SYSUT1   DD DISP=(OLD,KEEP),DSN=HLQ.KEEP",
        "//SYSUT1   DD DISP=OLD,DSN=HLQ.DELETE.ME",  # DELETE in a dataset name
        "//S1       EXEC PGM=IDCAMS,PARM='DELETE'",  # a PARM value
        "//SYSIN    DD *\n  DELETE HLQ.OLD.CLUSTER CLUSTER\n/*",  # IDCAMS command in SYSIN payload
        "//X        DD DISPOSITION=(OLD,DELETE)",
    ):
        assert not cleanup.search(not_teardown), f"counted a non-teardown: {not_teardown!r}"

    # Operand-anchored, not line-anchored: DISP= routinely sits on a `//`
    # continuation line (the #2482 shape), as io/sync_locks already assume.
    continuation = "//SYSUT1   DD DSN=HLQ.WORK,\n//            DISP=(MOD,DELETE,DELETE),\n//            UNIT=SYSDA"
    assert cleanup.search(continuation)

    # The status positional cannot cross a paren or a newline: a DELETE in the
    # NEXT statement's DISP= is not this statement's disposition.
    two_statements = "//A        DD DISP=(NEW,CATLG),DSN=HLQ.A\n//B        DD DISP=(OLD,DELETE),DSN=HLQ.B"
    assert len(cleanup.findall(two_statements)) == 1


def test_jcl_cleanup_overlaps_io_and_sync_locks_by_design():
    """
    #2749: the overlap #2610 declined is accepted on #2742's terms -- a narrow,
    semantically distinct subset of an operand io already counts. Every
    cleanup hit is also an `io` hit (the DD's DSN=), and the OLD/MOD forms are
    also `sync_locks` hits: the step holds an exclusive ENQ on the dataset it
    then drops. Pin all three so a later change re-makes the decision rather
    than drifting.
    """
    cleanup, io, sync_locks = JCL_RULES["cleanup"], JCL_RULES["io"], JCL_RULES["sync_locks"]

    exclusive_then_dropped = "//SYSLIN   DD DISP=(OLD,DELETE),DSN=&&LOADSET"
    assert cleanup.search(exclusive_then_dropped)
    assert io.search(exclusive_then_dropped)
    assert sync_locks.search(exclusive_then_dropped)

    # ...and the converse does not hold in either direction.
    shared = "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR"
    assert io.search(shared) and not cleanup.search(shared)
    held_and_kept = "//SYSUT1   DD DISP=(OLD,KEEP),DSN=HLQ.KEEP"
    assert sync_locks.search(held_and_kept) and not cleanup.search(held_and_kept)


def test_jcl_globals_job_scoped_declarations():
    """
    #2750: JCL's scoped-vs-global distinction is JOBLIB (every step) vs STEPLIB
    (one step), a SET symbol (every later statement) vs a PROC parameter (the
    procedure), and EXPORT SYMLIST (symbols reaching in-stream data). The rule
    counts the job-scoped side of each pair and nothing else -- STEPLIB is the
    negative that matters, and `SET` must stay statement-anchored so an inline
    SYSIN payload containing "SET X=1" does not count (the state_mutation
    precedent).
    """
    globals_ = JCL_RULES["globals"]
    assert globals_ is not None, "jcl's globals rule is None again (#2750)"

    for job_scoped in (
        "//JOBLIB   DD DSN=DSNC10.SDSNLOAD,DISP=SHR",
        "//JOBLIB  DD  DISP=SHR,DSN=DSNC10.SDSNLOAD",
        "//    SET HLQ='IBMUSER'       *TSO USER ID",
        "// SET DB2HLQ=@DB2_HLQ@",
        "//SET1     SET COUNTER=1",
        "// EXPORT SYMLIST=*",
        "//         EXPORT SYMLIST=(HLQ,DB2HLQ)",
    ):
        assert globals_.search(job_scoped), f"missed a job-scoped declaration: {job_scoped!r}"

    for step_scoped_or_lookalike in (
        "//STEPLIB  DD DSN=DSNC10.SDSNLOAD,DISP=SHR",  # step-scoped twin
        "//         DD DSN=CEE.SCEERUN,DISP=SHR",  # a JOBLIB concatenation line is not a second JOBLIB
        "//JOBLIBX  DD DSN=MY.LOAD,DISP=SHR",  # ddname merely starting with JOBLIB
        "//JOBLIB   DISP=SHR",  # not a DD statement
        "//IGYWCLG PROC LNGPRFX='IGY630'",  # a PROC parameter is the scoped twin of SET
        "//SYSIN    DD *\nSET X=1\n/*",  # payload, not a statement
        "//S1       EXEC PGM=X,PARM='SET A=1'",
        "//         SETX A=1",
        "//         EXPORT",  # EXPORT without SYMLIST is not a JCL statement
        "//* SET THE RETURN CODE TO CONTROL IF CICS SHOULD BE",
    ):
        assert not globals_.search(step_scoped_or_lookalike), f"false positive: {step_scoped_or_lookalike!r}"


def test_jcl_globals_set_is_also_state_mutation_by_design():
    """
    #2750: a `// SET` creates a job-wide symbol AND assigns it, so it is both
    `globals` and `state_mutation` -- dockerfile's `ENV` shape exactly (dual
    globals + state_mutation, ledgered in the rosetta corpus). JOBLIB is also
    an `io` hit through its DSN=, which is correct: a JOBLIB is a dependency
    of every step. Pin both so the overlap stays a decision.
    """
    globals_, state, io = JCL_RULES["globals"], JCL_RULES["state_mutation"], JCL_RULES["io"]
    assert globals_.search("//    SET HLQ='IBMUSER'") and state.search("//    SET HLQ='IBMUSER'")
    assert globals_.search("//JOBLIB   DD DSN=X.LOAD,DISP=SHR") and io.search("//JOBLIB   DD DSN=X.LOAD,DISP=SHR")
    # EXPORT SYMLIST is the one alternative with no overlap at all.
    assert globals_.search("// EXPORT SYMLIST=*") and not state.search("// EXPORT SYMLIST=*")


def test_jcl_high_risk_execution_counts_executors_not_every_step():
    """
    #2751: the rule was a bare `PGM=<anything>`, which counted every step --
    running a program is what a JCL step IS -- so a compile-link-go job scored
    three high-risk executions for compiling and IEFBR14 (a program that does
    nothing) counted the same as a TSO batch step that executes whatever
    SYSTSIN carries. Narrowed to the programs whose purpose is to execute
    caller-supplied commands; the negatives are the crucible's most frequent
    PGM= values, which are exactly what must NOT count.
    """
    danger = JCL_RULES["high_risk_execution"]

    for executor in (
        "//GRANT    EXEC PGM=IKJEFT01,DYNAMNBR=20",
        "//TSO      EXEC PGM=IKJEFT1B",
        "//SH       EXEC PGM=BPXBATCH,PARM='SH ls /tmp'",
        "//SHL      EXEC PGM=BPXBATSL",
        "//UNIX     EXEC PGM=AOPBATCH",
        "//REXX     EXEC PGM=IRXJCL,PARM='MYEXEC'",
        "//OPER     EXEC PGM=SDSF",
        "//lower    exec pgm=ikjeft01",
    ):
        assert danger.search(executor), f"missed an executor: {executor!r}"

    for a_step_not_an_execution in (
        "//STEP1    EXEC PGM=IEFBR14",  # no-op, run for its DD side effects
        "//COBOL    EXEC PGM=IGYCRCTL,REGION=0M",  # compiler
        "//LKED     EXEC PGM=IEWL",  # linker
        "//DEL      EXEC PGM=IDCAMS",  # catalog utility: a fixed command language
        "//COPY     EXEC PGM=IEBGENER",
        "//SORT     EXEC PGM=ICEGENER",
        "//RUN      EXEC PGM=CBL0001",  # the job's own application program
        "//X        EXEC PGM=IKJEFT01X",  # not the executor, a longer name
        "//X        EXEC PGM=MYIKJEFT01",
        "//X        EXEC PGM=X,PARM='IKJEFT01'",  # the name as a PARM value
        "//X        EXEC IKJEFT01",  # a procedure named like the program
    ):
        assert not danger.search(a_step_not_an_execution), f"counted a step as execution: {a_step_not_an_execution!r}"

    # PGM= on a continuation line (the #2482 shape) still counts.
    assert danger.search("//STEP0001 EXEC TIME=1440,REGION=0M,\n//             PGM=IKJEFT01")


def test_jcl_new_rules_count_through_the_real_pipeline():
    """
    #2748/#2749/#2750/#2751 end to end: the four rules score through
    prism + StructuralExtractor.splice, not just as regexes on a string. The
    deck is a cut-down real shape -- a cataloged proc header, a JOBLIB, two
    SETs, an IEFBR14 delete step, a TSO batch step, and the call site that
    invokes the proc -- and the SYSIN payload carries the lookalikes every
    rule must ignore.
    """
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.core.prism import Prism
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    sample = (
        "//DB2JCL   PROC\n"
        "//* SET THE RETURN CODE TO CONTROL IF CICS SHOULD BE\n"
        "//JOBLIB   DD DSN=DSNC10.SDSNLOAD,DISP=SHR\n"
        "//         DD DSN=CEE.SCEERUN,DISP=SHR\n"
        "//    SET HLQ='IBMUSER'\n"
        "//    SET DB2SYS=DBCG\n"
        "//DELETE   EXEC PGM=IEFBR14\n"
        "//DD1      DD DSN=&HLQ..CUSTRPT,DISP=(MOD,DELETE,DELETE),\n"
        "//            UNIT=SYSDA,SPACE=(CYL,(0))\n"
        "//SYSUT2   DD DISP=(NEW,CATLG,DELETE),DSN=&HLQ..OUT\n"
        "//GRANT    EXEC PGM=IKJEFT01,DYNAMNBR=20\n"
        "//SYSTSIN  DD *\n"
        "  DSN SYSTEM(DBCG)\n"
        "  SET X=1\n"
        "  DELETE HLQ.OLD.CLUSTER CLUSTER\n"
        "/*\n"
        "//CALL     EXEC DB2JCL\n"
        "//STEPLIB  DD DSN=DSNC10.SDSNLOAD,DISP=SHR\n"
        "//         PEND\n"
    )

    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    streams = prism.split_streams(sample, "jcl")
    equations = StructuralExtractor("jcl", LANGUAGE_DEFINITIONS).splice(
        streams["code_stream"], streams["comment_stream"], raw_content=sample
    )["equations"]

    assert equations.get("api", 0) == 1, "the PROC statement, not the EXEC that calls it"
    assert equations.get("cleanup", 0) == 1, "the (MOD,DELETE,DELETE), not the (NEW,CATLG,DELETE)"
    assert equations.get("globals", 0) == 3, "JOBLIB + two SETs; not the concatenation, STEPLIB or the SYSIN SET"
    assert equations.get("high_risk_execution", 0) == 1, "IKJEFT01 only; IEFBR14 is a step"


def test_jcl_new_rules_redos_immunity():
    """
    #2748-#2751: every new alternation is a literal keyword behind a bounded
    name/whitespace gap or a single negated class that excludes its own
    terminator (`[^,()\\n]*` then `,`), so each quantifier has one landing
    site. Hold the line on it with the same detonations the other rules get.
    """
    assert_redos_immune(JCL_RULES["api"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["api"], "//" + " " * 50000 + "PROC", timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["cleanup"], "DISP=(" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["cleanup"], "DISP=(" + ", " * 25000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["cleanup"], "//X DD " + "DISP=(" * 20000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["globals"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["globals"], "//JOBLIB" + " " * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["globals"], "// SET " + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["high_risk_execution"], "PGM=" + "IKJEFT0" * 10000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["high_risk_execution"], "PGM=IKJEFT01" * 10000, timeout_sec=3.0)

    assert JCL_RULES["api"].search("//DB2JCL   PROC")
    assert JCL_RULES["cleanup"].search("//SYSLIN   DD DISP=(OLD,DELETE),DSN=&&LOADSET")
    assert JCL_RULES["globals"].search("//JOBLIB   DD DSN=X,DISP=SHR")
    assert JCL_RULES["high_risk_execution"].search("//GRANT    EXEC PGM=IKJEFT01")


def test_jcl_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: jcl is `line_exclusive` -- no block comment
    delimiters at all, so no rule tracks open/close block-comment state.
    Every keyword-presence rule matches via flat line-anchored scanning.
    JCL's own `//*` comment marker only ever appears as a whole-line
    prefix, so there's no stray closing-tag shape for the engine to be
    fooled by in the first place.
    """
    branch = JCL_RULES["branch"]
    assert branch.search("//         IF (STEP1.RC = 0) THEN")
    # 2822 corollary 2: ENDIF is the construct's closing word; boundaries owns it
    assert not branch.search("//         ENDIF")
    assert JCL_RULES["structural_boundaries"].search("//         ENDIF")


def test_jcl_redos_immunity():
    """
    ReDoS immunity sweep. Every jcl rule has at most one quantified segment
    per adjacent gap, with non-overlapping character classes between
    consecutive quantifiers (name-charset vs. `[ \\t]+` whitespace vs. the
    literal keyword), so none of them have the adjacent-overlapping-
    quantifier shape that produces real O(n^2) backtracking. Verified via
    assert_redos_immune's subprocess-kill timeout on adversarial payloads
    sized to each rule's actual quantifiers (a long run of name-charset
    characters, or digits/letters, with no legitimate terminator).
    """
    assert_redos_immune(JCL_RULES["branch"], "IF " * 20000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["structural_boundaries"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["func_start"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["class_start"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["high_risk_execution"], "PGM=" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["io"], "DISP=" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["state_mutation"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["import"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["_dependency_capture"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["ownership"], "//*Author:" + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert JCL_RULES["branch"].search("//         IF (STEP1.RC = 0) THEN")
    assert JCL_RULES["structural_boundaries"].search("//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR")
