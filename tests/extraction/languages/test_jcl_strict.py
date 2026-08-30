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
    ("high_risk_execution", "//STEP1   EXEC PGM=IEFBR14", "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR"),
    ("io", "//SYSPRINT DD SYSOUT=*", "//STEP1   EXEC PGM=IEFBR14"),
    ("state_mutation", "//         SET SYMVAR=VALUE", "//STEP1   EXEC PGM=IEFBR14"),
    ("import", "//         INCLUDE MEMBER=STDPROC1", "//STEP1   EXEC PGM=IEFBR14"),
    ("ownership", "//*Author: Jane Doe", "//* just a routine comment"),

# --- ADVERSARIAL CASES ---
    # branch: anchored properly vs inline data
    ("branch", "//IF1     IF (STEP1.RC=0) THEN", "IF (STEP1.RC=0) THEN"),
    ("branch", "//        ELSE", "ELSE inside some text"),
    ("branch", "//ENDIF1  ENDIF", "//* ENDIF in a comment"),
    ("branch", "//$IF     IF (RC > 0) THEN", "    IF  "),
    ("branch", "//#IF_A   ELSE", "//* IF"),
    ("branch", "//@123    ENDIF", "//STEP IFX"), # IFX is not IF

    # args: unnamed procs, spaces, etc
    ("args", "//PROC1   PROC A=1,B=2", "//PROC1   PROC"), # no parm/proc args
    ("args", "//        EXEC PGM=FOO,PARM='A,B,C'", "//        EXEC PGM=FOO"),
    ("args", "//STEP1   EXEC PGM=FOO, PARM='A,B,C'", "//STEP1   EXEC PGM=FOO, COND=(0,NE)"),
    ("args", "//STEP1   EXEC PGM=FOO,PARM=(A,B,C)", "//* STEP1 EXEC PGM=FOO,PARM=A"),
    ("args", "//STEP1   EXEC PGM=FOO,PARM=A", "//* EXEC PGM=FOO,PARM=A"),
    ("args", "//STEP1   EXEC PGM=FOO,  PARM='FOO,BAR'", "//STEP EXEC PGM=FOO,PARM="), # PARM is empty
    ("args", "//$TEP    EXEC PGM=F,PARM='  '", "//STEP PARM='A'"), # PARM without EXEC
    ("args", "//A       PROC ARG=1", "//A       PROC  "), # trailing spaces but no args

    # func_start: unnamed steps, trailing strings
    ("func_start", "//        EXEC PGM=FOO", "EXEC PGM=FOO"),
    ("func_start", "//$TEP#@  EXEC PGM=FOO", "//STEP EXECUTING"),
    ("func_start", "//STEP123 EXEC PGM=FOO", "//* EXEC PGM=FOO"),
    ("func_start", "//STEP_1  EXEC PGM=FOO", "//STEP_1 EXECUTING"),
    ("func_start", "//123456  EXEC PGM=FOO", "//*123456 EXEC PGM=FOO"),
    ("func_start", "//@@@@    EXEC PGM=FOO", "//EXEC PGM=FOO"), # No space between // and EXEC is actually an unnamed step with EXEC as operation? No, if no space it's name=EXEC. Operation follows.
    ("func_start", "//        EXEC", "EXEC "), # just EXEC

    # class_start: symbols in job name, but not empty
    ("class_start", "//#JOB@$  JOB (123),'TEST'", "JOB (123),'TEST'"),
    ("class_start", "//JOB1    JOB (123),'TEST'", "// JOB (123),'TEST'"), # Job must have name
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
    assert branch.search("//         ENDIF")


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
