# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

"""
HLASM strict structural-signature coverage (#2503). See
gitgalaxy/standards/how_to_add_a_language.md's Strict Testing & Crucible Verification
Framework for the methodology -- an adversarial pass against the signatures registered
in languages/hlasm.py, not a continuation of the generation work.

Every snippet is a real HLASM shape: z/OS supervisor macros (ESTAE/GETMAIN/WTO/
ATTACH), the CICS command-level surface a CICS assembler program writes verbatim
(EXEC CICS ..., DFHEIENT/DFHEIRET), and the assembler's own section/macro
morphology (CSECT/DSECT/MACRO..MEND, column-1 `*`/`.*` comments, positional
remarks after the operand field).

#2503's core claims are pinned here too: `.asm` is a registered collision
(assembly vs hlasm) that never locks on extension alone, and DSECT is
class_start, NOT func_start -- the profile's documented deviation from the
issue text (#2856: a dummy section is a record layout, no executable logic).
"""

import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS, LENS_CONFIG

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

HLASM = LANGUAGE_DEFINITIONS["hlasm"]
HLASM_RULES = HLASM["rules"]

# A realistic CICS assembler member: comment banner + macro comment, a DSECT,
# two control sections, base-register setup, CICS entry/exit, native and CICS
# I/O, and the END closer. Remarks after operands are positional (no inline
# comment marker exists), so they stay in the code stream deliberately.
_REAL_MEMBER = (
    "*ACCTPGM -- ACCOUNT HANDLER\n"
    ".* MACRO-LEVEL COMMENT, COLUMN-1 '.*'\n"
    "* PURPOSE: EXERCISE THE HEADLINE SIGNATURES\n"
    "WSAREA   DSECT\n"
    "WSNAME   DS    CL8\n"
    "ACCTPGM  CSECT\n"
    "         USING WSAREA,10\n"
    "         STM   14,12,12(13)          SAVE CALLER REGISTERS\n"
    "         DFHEIENT CODEREG=12,DATAREG=13\n"
    "         L     15,=V(SUBRTN)\n"
    "         BALR  14,15\n"
    "         CLC   WSNAME,=C'CUSTOMER'\n"
    "         BE    DONE\n"
    "         BCT   4,DONE\n"
    "         EXEC CICS READ FILE('ACCTFIL') INTO(WSAREA) RIDFLD(WSNAME)\n"
    "         ABEND 777\n"
    "DONE     BR    14\n"
    "SUBRTN   RSECT\n"
    "FLAGS    DC    X'00'\n"
    "MAXLEN   EQU   256\n"
    "         BR    14\n"
    "         END\n"
)

# ==============================================================================
# TEST 1: PER-SIGNATURE POSITIVE/NEGATIVE COVERAGE
# Every positive is a form real members carry; every negative is the nearest
# realistic near-miss the rule's own documentation claims to exclude.
# ==============================================================================
_HLASM_SIMPLE_CASES = [
    ("calls_out", "         L     15,=V(PROBEBR)", "         BALR  14,15"),
    # Conditional branches only; the unconditional B/BR is structural (#2764).
    ("branch", "         BE    NOTFOUND", "         B     NOTFOUND"),
    ("branch", "         BNER  14", "         BR    14"),
    ("branch", "         BCR   8,14", "         BALR  14,15"),
    ("branch", "         BCT   4,LOOP", "         BAS   14,SUBR"),
    ("branch", "         CIJ   5,0,8,DONE", "         C     5,LIMIT"),
    ("branch", "         JNZ   RETRY", "         J     RETRY"),
    # args: the MACRO prototype's symbolic-parameter list, spanning the
    # MACRO line onto the prototype line. An invocation passes actuals.
    ("args", "         MACRO\n&LAB     PAYCALC &AMT,&RATE=5", "         PAYCALC 100,RATE=3"),
    ("structural_boundaries", "         MVC   WSNAME,=C'X'", None),
    ("structural_boundaries", "         BR    14", None),
    ("structural_boundaries", "         LTORG", None),
    ("func_start", "ACCTPGM  CSECT", "         CSECT"),
    ("func_start", "SUBSECT  RSECT", "WSAREA   DSECT"),
    ("func_start", "PGMSTART START 0", "RESTART  LA    1,4"),
    ("class_start", "WSAREA   DSECT", "ACCTPGM  CSECT"),
    # ESTAE 0 CANCELS the handler -- Rule 15's documented exclusion.
    ("safety", "         ESTAEX RTNADDR", "         ESTAEX 0"),
    ("safety", "         ESPIE SET,PGMCHK,(1,15)", None),
    ("safety", "         EXEC CICS HANDLE CONDITION NOTFND(NF)", None),
    ("safety_bypasses", "         ESTAE 0", "         ESTAE RTNADDR"),
    ("safety_bypasses", "         EXEC CICS IGNORE CONDITION ERROR", None),
    ("high_risk_execution", "         ABEND 777,DUMP", "         B     ABEND777"),
    ("high_risk_execution", "         MODESET KEY=ZERO,MODE=SUP", None),
    # LOAD/DELETE need the module-operand shape; CICS DELETE is io's.
    ("high_risk_execution", "         LOAD  EP=DYNMOD", "         DELETE FILE('ACCTFIL')"),
    ("io", "         OPEN  (ACCTDCB,(INPUT))", "         OPENED DS 0H"),
    ("io", "         GET   ACCTDCB,WSNAME", "         LA    1,4 GET THE PARM ADDRESS"),
    ("io", "         EXEC CICS READQ TS QUEUE(Q1)", "         EXEC SQL INCLUDE SQLCA"),
    ("api", "ACCTPGM  CSECT", "         EXTRN OTHRPGM"),
    ("api", "         ENTRY ALTENTRY", "         WXTRN SHRDSUB"),
    ("state_mutation", "         OI    FLAGS,X'80'", "         MVI   FLAGS,X'80'"),
    ("state_mutation", "         XC    WSBAL,WSBAL", "         XR    6,7"),
    ("dead_code", "*        MVC   WSNAME,=C'OLD',", "* THE MVC BELOW COPIES THE NAME"),
    ("dead_code", "*OLDLBL  DC    X'00'", "* DC POWER SUPPLY NOTES FOLLOW"),
    ("doc", "* PURPOSE: DISPATCH EACH PROBE ONCE", "* THE PURPOSE ELUDES US"),
    ("concurrency", "         ATTACH EP=SUBTASK", None),
    ("concurrency", "         WAIT  ECB=DONEECB", "               WAIT=YES"),
    ("ui_framework", "         EXEC CICS SEND MAP('M1') MAPSET('S1')", None),
    ("ui_framework", "CUSTMAP  DFHMDI SIZE=(24,80)", None),
    ("globals", "FLAGS    DC    X'00'", "WSNAME   DS    CL8"),
    ("decorators", "ACCTPGM  AMODE 31", None),
    ("decorators", "ACCTPGM  RMODE ANY", None),
    ("scientific", "         ADB   0,DBLVAL", None),
    ("scientific", "         SQDBR 0,2", None),
    ("reflection_metaprogramming", "         EX    1,MOVEIT", "         EXEC CICS RETURN"),
    ("import", "         COPY  ACCTDSCT", "COPYRT   DC    C'COPYRIGHT ACME'"),
    ("ownership", "* Author: MAINFRAME TEAM", "* THE AUTHOR OF THIS CSECT IS UNKNOWN"),
    ("planned_debt", "* TODO: WIDEN THE ACCOUNT FIELD", None),
    ("fragile_debt", "* HACK: SELF-MODIFYING LENGTH BYTE", None),
    ("spec_exposure", "* CONTROL TAG [SPEC-2503] FOR TRACEABILITY", None),
    ("ssr_boundaries", "         EXEC CICS WEB SEND", None),
    ("events", "         EXEC CICS SIGNAL EVENT('EVT1')", None),
    ("macros", "         MACRO", None),
    ("macros", "         MEND", None),
    ("macros", "&X       SETA  1", None),
    ("macros", ".SKIP    ANOP", None),
    ("pointers", "RETADDR  DC    A(0)", "         CLC   0(4,1),=C'ABCD'"),
    ("pointers", "         L     15,=V(SUBPGM)", None),
    ("memory_alloc", "         GETMAIN RU,LV=4096", None),
    ("memory_alloc", "         STORAGE OBTAIN,LENGTH=512", None),
    ("telemetry", "         SNAP  DCB=SNAPDCB,STORAGE=(A,B)", "         SNAPPY LA 1,4"),
    ("telemetry", "         WTL   'JOB STARTED'", None),
    ("debug_prints", "         WTO   'ACCOUNT PROCESSED'", "WTOFLAG  DC    X'00'"),
    ("debug_prints", "         WTOR  'REPLY Y/N',REPLY,1,RECB", None),
    ("explicit_casts", "         CVB   6,DOUBLE", None),
    ("explicit_casts", "         PACK  DOUBLE,WSBAL", None),
    ("panics_and_aborts", "         ABEND 777", None),
    ("thread_sleeps", "         STIMER WAIT,BINTVL=INTERVAL", "         STIMER REAL,EXIT,BINTVL=I"),
    ("thread_sleeps", "         EXEC CICS DELAY INTERVAL(100)", None),
    ("bitwise_ops", "         SLL   6,2", None),
    ("bitwise_ops", "         NR    6,7", "         OI    FLAGS,X'80'"),
    ("sync_locks", "         CS    8,9,LOCKWORD", None),
    ("sync_locks", "         ENQ   (QNAME,RNAME,E)", None),
    ("immutability_locks", "MAXLEN   EQU   256", "         EQU   256"),
    ("immutability_locks", "SUBSECT  RSECT", None),
    ("cleanup", "         CLOSE (ACCTDCB)", "CLOSEUP  LA    1,4"),
    ("cleanup", "         FREEMAIN RU,LV=4096,A=(1)", None),
    ("cleanup", "         EXEC SQL CLOSE C1", None),
    ("listeners", "         EXEC CICS RECEIVE MAP('M1')", None),
    ("serialization_parsing", "         EXEC CICS TRANSFORM XMLTODATA CHANNEL(CH1)", None),
    ("time_date_logic", "         TIME  DEC", "TIMEOUT  DS    F"),
    ("time_date_logic", "         STCK  CLOCKVAL", None),
    ("ipc_rpc_bridges", "         DFHEIENT CODEREG=12", None),
    ("ipc_rpc_bridges", "         DFHEIRET", None),
    ("auth_middleware", "         RACROUTE REQUEST=AUTH,CLASS='FACILITY'", "         MVC   RACROUTED,=C'X'"),
    ("auth_middleware", "         EXEC CICS SIGNON USERID(USER1)", "SIGNONFL DS    C"),
    ("ipc_rpc_bridges", "         LINK  EP=NEXTPGM", "         LR    2,3"),
    ("ipc_rpc_bridges", "         EXEC CICS XCTL PROGRAM('NEXTPGM')", None),
]


@pytest.mark.parametrize(("signature", "positive", "negative"), _HLASM_SIMPLE_CASES)
def test_hlasm_signature_positive_and_negative(signature, positive, negative):
    pattern = HLASM_RULES[signature]
    assert pattern is not None, f"hlasm's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"hlasm {signature!r} failed its documented positive case: {positive!r}"
    if negative is not None:
        assert not pattern.search(negative), f"hlasm {signature!r} matched an excluded case: {negative!r}"


def test_every_non_none_rule_has_a_simple_case():
    covered = {sig for sig, _, _ in _HLASM_SIMPLE_CASES}
    live = {k for k, v in HLASM_RULES.items() if v is not None and not k.startswith("_")}
    assert live - covered == set(), f"rules with no positive/negative case: {sorted(live - covered)}"


# ==============================================================================
# TEST 2: SCHEMA COMPLETENESS (Rule 4 / Step 4 item 9)
# ==============================================================================
_BASELINE_KEYS = [
    "calls_out",  # Epic #3264
    "branch", "args", "structural_boundaries", "func_start", "class_start",
    "safety", "safety_bypasses", "high_risk_execution", "io", "api",
    "state_mutation", "dead_code", "doc", "test",
    "concurrency", "ui_framework", "closures", "globals", "decorators",
    "generics", "comprehensions", "scientific", "reflection_metaprogramming",
    "import", "_dependency_capture", "ownership",
    "planned_debt", "fragile_debt", "hardcoded_secrets", "spec_exposure",
    "ssr_boundaries", "events", "dependency_injection",
    "macros", "pointers", "memory_alloc", "inline_asm",
    "telemetry", "debug_prints", "explicit_casts", "panics_and_aborts",
    "thread_sleeps", "bitwise_ops", "sync_locks", "immutability_locks",
    "cleanup", "encapsulation", "listeners", "test_skip",
    "serialization_parsing", "regex_execution", "time_date_logic", "ipc_rpc_bridges",
    "auth_middleware",
    "system_config_mutation",
]  # fmt: skip

# Each absence is a stated one: no anonymous callables (closures), no
# parametric types (generics), no transform form (comprehensions), no test
# framework executes assembler units (test/test_skip), no IoC (dependency_
# injection), nothing is inline in an assembler (inline_asm), no visibility
# marker below the linker surface (encapsulation -- lexical scope is not
# visibility, the perl/shell precedent), TR/TRT take no pattern
# (regex_execution), and hardcoded_secrets is the security lens's.
_EXPECTED_NONE_KEYS = {
    "closures", "generics", "comprehensions", "test", "test_skip",
    "dependency_injection", "inline_asm", "encapsulation", "regex_execution",
    "hardcoded_secrets",
    "system_config_mutation",
}  # fmt: skip


def test_hlasm_schema_completeness():
    baseline = set(_BASELINE_KEYS)
    missing = baseline - set(HLASM_RULES)
    assert not missing, f"hlasm rules dict is missing baseline keys entirely (not even None): {missing}"
    extra = set(HLASM_RULES) - baseline - {"_visibility_export_list"}
    assert extra == set(), f"unexpected non-baseline keys: {extra}"


def test_hlasm_none_keys_are_the_intended_set():
    actual_none = {k for k, v in HLASM_RULES.items() if v is None}
    assert actual_none == _EXPECTED_NONE_KEYS, f"unexpected None keys: {actual_none ^ _EXPECTED_NONE_KEYS}"


# ==============================================================================
# TEST 3: REGISTRATION -- THE #2503 .asm COLLISION ITSELF
# ==============================================================================
def test_hlasm_registration():
    assert set(HLASM["extensions"]) == {".asm", ".hlasm", ".mac"}
    assert HLASM["case_insensitive_imports"] is True
    assert HLASM["lexical_family"] == "positional_anchored"
    # by_name is DELIBERATE (unlike bms/jcl): =V(name)+BALR, the CALL macro
    # and USING reach hlasm's extracted units by name, so the census applies.
    assert "invocation_model" not in HLASM
    assert "invocation_model" not in HLASM_RULES


def test_asm_extension_is_a_registered_collision():
    # `.asm` is x86/ARM assembly's in the wild at least as often as it is
    # HLASM's; it must never lock on extension alone (Tier 1 refuses
    # COLLISION_FREQUENCIES members). `.mac`/`.hlasm` are uncontested.
    assert ".asm" in LENS_CONFIG["COLLISION_FREQUENCIES"]
    assert ".asm" in LANGUAGE_DEFINITIONS["assembly"]["extensions"], "the collision needs both claimants"
    assert HLASM.get("internal_discriminator") is not None
    assert {".s", ".ld", "CMakeLists.txt"} <= set(HLASM["disqualifiers"])


_NASM_CONTENT = (
    "; x86-64 bootstrap\nsection .text\nglobal _start\n_start:\n    mov rax, 60\n    xor rdi, rdi\n    syscall\n"
)


def test_internal_discriminator_separates_hlasm_from_x86():
    disc = HLASM["internal_discriminator"]
    assert disc.search(_REAL_MEMBER)
    assert disc.search("ACCTPGM  CSECT\n")
    assert disc.search("         USING WSAREA,10\n")
    assert disc.search("         DFHEIENT CODEREG=12\n")
    assert not disc.search(_NASM_CONTENT)
    # A '*' banner mentioning CSECT mid-line is a comment, and even as raw
    # text the name-field anchor refuses the '*' in column 1.
    assert not disc.search("* THIS CSECT HANDLES THE ACCOUNT MAP\n")


def test_asm_extension_with_hlasm_content_resolves_to_hlasm():
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    lang, _conf, _family = detector.focus("src/acctpgm.asm", _REAL_MEMBER)
    assert lang == "hlasm", f"real HLASM named .asm must resolve through the internal discriminator (got {lang!r})"


def test_asm_extension_with_x86_content_stays_assembly():
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    lang, _conf, _family = detector.focus("src/bootstrap.asm", _NASM_CONTENT)
    assert lang == "assembly", f"x86 .asm must keep resolving to assembly (got {lang!r})"


def test_hlasm_extension_classifies_directly():
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    lang, _conf, _family = detector.focus("src/acctpgm.hlasm", _REAL_MEMBER)
    assert lang == "hlasm"


_HLASM_EQU_COPYBOOK = (
    "* REGISTER EQUATES\nR0       EQU   0\nR1       EQU   1\nR2       EQU   2\nR3       EQU   3\nR15      EQU   15\n"
)

_MASM_EQU_CONTENT = (
    "; MASM style equates\n.model flat, c\n.data\nMAX_LEN  EQU   256\n.code\n         mov eax, MAX_LEN\n"
)


def test_asm_extension_with_equ_only_copybook_resolves_to_hlasm():
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    lang, _conf, _family = detector.focus("ASMCOPY/REGISTRS.asm", _HLASM_EQU_COPYBOOK)
    assert lang == "hlasm", f"EQU-only register copybook must resolve to hlasm (got {lang!r})"  # noqa: S101


def test_asm_extension_with_masm_equ_stays_assembly():
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    lang, _conf, _family = detector.focus("src/masm_equ.asm", _MASM_EQU_CONTENT)
    assert lang == "assembly", f"MASM file with EQU must keep resolving to assembly (got {lang!r})"  # noqa: S101


# ==============================================================================
# TEST 4: LEXICAL-FAMILY SANITY (Step 4 item 8), through the real Prism
# ==============================================================================
def test_hlasm_prism_strips_star_and_macro_comments_only():
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    streams = prism.split_streams(_REAL_MEMBER, "hlasm")
    code = streams["code_stream"]
    comments = streams["comment_stream"]

    assert "ACCOUNT HANDLER" in comments
    assert "MACRO-LEVEL COMMENT" in comments
    assert "ACCOUNT HANDLER" not in code
    # Statements stay whole: HLASM has no inline comment marker, so the
    # positional remark after STM's operands MUST remain in the code stream.
    assert "SAVE CALLER REGISTERS" in code
    assert "ACCTPGM  CSECT" in code


def test_hlasm_names_starting_with_shared_anchor_chars_survive():
    # The #1898 shape, third landing (abap #1898, bms #2505): the shared
    # positional anchor set ({'*','/','C','c','!'}) would erase any statement
    # whose column-1 name field starts with C/c/! or '/'. Real HLASM is full
    # of C-names (CHECKPT, CALCRTN...).
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    sample = "CHECKPT  LR    3,4\nclcrtn   CLC   0(4,1),0(2)\n"
    code = prism.split_streams(sample, "hlasm")["code_stream"]
    assert "CHECKPT  LR" in code
    assert "clcrtn   CLC" in code


def test_hlasm_no_inline_split_on_quote_bang_or_stargt():
    # '!', '*>' and '"' are ordinary characters inside a C'...' literal;
    # nothing may split on them (bms's #2505 guarantee, inherited verbatim).
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    sample = "MSGTXT   DC    C'ACCOUNT! *> \"INQUIRY\"'\n"
    code = prism.split_streams(sample, "hlasm")["code_stream"]
    assert "C'ACCOUNT! *> \"INQUIRY\"'" in code


def test_hlasm_debt_rules_fire_on_the_comment_stream():
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    sample = "* TODO: WIDEN THE ACCOUNT FIELD\nACCTNO   DC    CL8' '\n"
    comments = prism.split_streams(sample, "hlasm")["comment_stream"]
    assert HLASM_RULES["planned_debt"].search(comments)


# ==============================================================================
# TEST 5: REALISTIC-FORM & BOUNDARY AUDIT (Rules 9/10/15/18)
# ==============================================================================
def test_hlasm_counts_on_the_real_member_are_exact():
    counts = {k: len(list(HLASM_RULES[k].finditer(_REAL_MEMBER))) for k, v in HLASM_RULES.items() if v is not None}
    assert counts["func_start"] == 2  # ACCTPGM CSECT + SUBRTN RSECT
    assert counts["class_start"] == 1  # WSAREA DSECT
    assert counts["branch"] == 2  # BE + BCT; BALR/BR are structural
    assert counts["io"] == 1  # EXEC CICS READ
    assert counts["high_risk_execution"] == 1  # ABEND
    assert counts["globals"] == 1  # FLAGS DC (WSNAME DS is a DSECT field)
    assert counts["immutability_locks"] == 2  # MAXLEN EQU + SUBRTN RSECT
    assert counts["pointers"] == 1  # =V(SUBRTN)
    # DFHEIENT only: EXEC CICS READ is io's file command, not a bridge --
    # ipc's CICS list is the program-control/channel vocabulary (LINK/XCTL/
    # START/RETURN/CONTAINER), pli's split verbatim.
    assert counts["ipc_rpc_bridges"] == 1
    assert counts["api"] == 2  # both sections; EQU/DC publish nothing


def test_hlasm_operation_field_anchor_rejects_keyword_operands():
    # A keyword operand on a continuation line sits in statement position too
    # (empty name field + column-16 indent); only the operation field's
    # blank/EOL terminator keeps it from reading as a statement. `\b` would
    # happily fire between `WAIT` and `=` -- the exact Rule 9 trap.
    assert not HLASM_RULES["concurrency"].search("               WAIT=YES\n")
    assert not HLASM_RULES["io"].search("               GET=ADDR\n")
    assert HLASM_RULES["concurrency"].search("         WAIT  ECB=DONEECB\n")


def test_hlasm_remarks_after_operands_do_not_fire_rules():
    # Remarks are positional, not delimited: they stay in the code stream, and
    # operation-field anchoring is the only shield (Rule 18).
    line = "         LA    1,PARMLIST GET THE PARM LIST AND OPEN THE DCB\n"
    assert not HLASM_RULES["io"].search(line)
    line2 = "         LR    2,3        WAIT UNTIL THE ECB POSTS\n"
    assert not HLASM_RULES["concurrency"].search(line2)


def test_hlasm_exec_cics_alternations_do_fire_mid_line():
    # The one deliberate exception to statement anchoring: the CICS/SQL
    # command surface matches at the translator level wherever it appears --
    # which is also why a danger phrase inside a C'...' literal counts
    # (gitgalaxy#2535; the rosetta shell's string decoy pins the same fact).
    lit = "DECOY    DC    C'EXEC CICS ABEND decoy text'\n"
    assert HLASM_RULES["high_risk_execution"].search(lit)
    assert HLASM_RULES["panics_and_aborts"].search(lit), "EXEC CICS ABEND is the #2878 termination dual"


def test_hlasm_abend_dual_is_deliberate():
    stmt = "         ABEND 777,DUMP\n"
    assert HLASM_RULES["high_risk_execution"].search(stmt)
    assert HLASM_RULES["panics_and_aborts"].search(stmt)


def test_hlasm_state_mutation_vs_bitwise_single_owner():
    # Storage RMW forms are state_mutation's; register forms are bitwise_ops'.
    for op, owner, other in (
        ("         OI    FLAGS,X'80'", "state_mutation", "bitwise_ops"),
        ("         XC    WSBAL,WSBAL", "state_mutation", "bitwise_ops"),
        ("         XR    6,7", "bitwise_ops", "state_mutation"),
        ("         OR    6,7", "bitwise_ops", "state_mutation"),
    ):
        assert HLASM_RULES[owner].search(op), f"{owner} must own {op.strip()!r}"
        assert not HLASM_RULES[other].search(op), f"{other} must not also match {op.strip()!r}"


def test_hlasm_unconditional_transfers_are_structural_not_branch():
    for stmt in ("         B     EXIT", "         BR    14", "         BAL   14,SUBR", "         BALR  14,15"):
        assert not HLASM_RULES["branch"].search(stmt), f"unconditional {stmt.strip()!r} is not a decision (#2764)"
        assert HLASM_RULES["structural_boundaries"].search(stmt)


def test_hlasm_freemain_dual_and_close_ownership():
    # FREEMAIN is memory_alloc AND cleanup (pli's ALLOCATE/FREE dual);
    # CLOSE is cleanup's alone (#2841 C2).
    stmt = "         FREEMAIN RU,LV=4096\n"
    assert HLASM_RULES["memory_alloc"].search(stmt)
    assert HLASM_RULES["cleanup"].search(stmt)
    close = "         CLOSE (ACCTDCB)\n"
    assert HLASM_RULES["cleanup"].search(close)
    assert not HLASM_RULES["io"].search(close)


def test_hlasm_visibility_export_list_captures_names_only():
    m = HLASM_RULES["_visibility_export_list"].search("         ENTRY ALTENTRY,OTHERENT\n")
    assert m and m.group(1).rstrip() == "ALTENTRY,OTHERENT"
    assert not HLASM_RULES["_visibility_export_list"].search("         ENTRY \n")


def test_hlasm_dependency_capture_extracts_the_member():
    m = HLASM_RULES["_dependency_capture"].search("         COPY  ACCTDSCT\n")
    assert m and m.group(1) == "ACCTDSCT"


def test_hlasm_lowercase_source_still_matches():
    assert HLASM_RULES["func_start"].search("acctpgm  csect")
    assert HLASM_RULES["branch"].search("         be    done")


# ==============================================================================
# TEST 6: `re.M` COMPLETENESS AUDIT (Rule 13)
# ==============================================================================
def test_hlasm_caret_anchored_rules_all_set_multiline_flag():
    for key, pattern in HLASM_RULES.items():
        if pattern is None or not isinstance(pattern, re.Pattern):
            continue
        if "^" in pattern.pattern.replace("[^", ""):
            assert pattern.flags & re.M, f"hlasm {key!r} uses '^' without re.M"
    disc = HLASM["internal_discriminator"]
    assert disc.flags & re.M, "internal_discriminator uses '^' without re.M"


# ==============================================================================
# TEST 7: ReDoS IMMUNITY (Rule 5/14), scaled adversarial payloads
# #2503's issue text names this explicitly: column-aware parsing must not
# ReDoS on long macros. Payloads: an unclosed MACRO prototype of extreme
# length, a long continuation-indent run, a long name-field token, and the
# never-terminating shapes for each bounded quantifier.
# ==============================================================================
_N = 32000


@pytest.mark.parametrize(
    ("signature", "payload"),
    [
        ("args", "         MACRO\n&LAB     ROSMAC " + "&P," * (_N // 3)),  # the long-macro detonation
        ("args", "         MACRO\n" + "A" * _N),
        ("args", " " * 71 + "MACRO" + " " * _N),
        ("branch", "A" * _N),
        ("branch", " " * _N + "B"),
        ("structural_boundaries", ("X" * 63 + " ") * (_N // 64)),
        ("func_start", "A" * _N + " CSECT"),
        ("func_start", "@" + "#" * _N),
        ("class_start", "A" * _N + " DSECT"),
        ("safety", "         ESTAEX" + " " * _N),
        ("high_risk_execution", "         LOAD  EP" + "=" * _N),
        ("io", "         EXEC  SQL" + " " * _N),
        ("io", "         OPEN  " + "(" * _N),
        ("api", "         ENTRY " + "A," * (_N // 2)),
        ("_visibility_export_list", "         ENTRY " + "A," * (_N // 2)),
        ("state_mutation", " " * _N + "OI"),
        ("dead_code", "*A       MVC   " + "A" * _N),
        ("dead_code", "*" + "A" * _N),
        ("doc", "*" * _N + " PURPOSE"),
        ("macros", "&" + "A" * _N),
        ("macros", " " * _N + "SETA"),
        ("pointers", "         DC    " + "0" * _N),
        ("pointers", "=" + "9" * _N + "V("),
        ("memory_alloc", "         STORAGE " + " " * _N),
        ("telemetry", "         WTL" + " " * _N),
        ("thread_sleeps", "         STIMER " + " " * _N + "NOTWAIT"),
        ("sync_locks", "         CS" + "G" * _N),
        ("immutability_locks", "A" * _N + " EQU 1"),
        ("cleanup", "         CLOSE " + " " * _N),
        ("ipc_rpc_bridges", "         LINK  " + "E" * _N),
        ("ownership", "* Author:" + " " * _N),
        ("spec_exposure", "*" + "A" * 199 + "[SPEC-" + "1" * _N),
        ("_dependency_capture", "X COPY " + "A" * _N),
    ],
    ids=lambda v: v if len(v) <= 30 else f"{v[:12].strip()}...x{len(v)}",
)
def test_hlasm_redos_immunity(signature, payload):
    pattern = HLASM_RULES[signature]
    assert_redos_immune(pattern, payload, timeout_sec=3.0)


def test_hlasm_internal_discriminator_redos_immune():
    assert_redos_immune(HLASM["internal_discriminator"], "A" * _N + " CSECT" + "A" * _N, timeout_sec=3.0)


# ==============================================================================
# TEST 8: FUNCTION SLICING through Mode A, DSECT through class_start
# ==============================================================================
def test_hlasm_sections_slice_through_mode_a_as_named_units():
    """hlasm is registered in detector.py's Mode A tuple (the bms/#3077 slot).
    Without it the language falls through to brace slicing -- HLASM has no
    braces -- and no CSECT would ever reach function_data."""
    from gitgalaxy.core.detector import StructuralExtractor

    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    streams = prism.split_streams(_REAL_MEMBER, "hlasm")
    functions = StructuralExtractor("hlasm", LANGUAGE_DEFINITIONS).splice(
        streams["code_stream"], streams["comment_stream"]
    )["functions"]
    names = {f["name"] for f in functions}
    assert names == {"ACCTPGM", "SUBRTN"}, f"the named sections are the units; got {names}"


def test_hlasm_is_in_the_mode_a_dispatch_and_named_class_allowlist():
    from gitgalaxy.core import detector

    assert "hlasm" in detector._CLASS_START_NAMED_EXTRACTION_LANGS


def test_hlasm_dsect_is_class_start_not_func_start():
    # The documented deviation from #2503's issue text, #2856-cited: a DSECT
    # is a named storage LAYOUT (record/struct family) with no executable
    # logic. It must extract as a class, never as a function.
    assert HLASM_RULES["class_start"].search("WSAREA   DSECT")
    assert not HLASM_RULES["func_start"].search("WSAREA   DSECT")
    m = HLASM_RULES["class_start"].search("WSAREA   DSECT")
    assert m.group(1) == "WSAREA"


def test_hlasm_calls_out_strict():
    """
    Epic #3264: Asserts that HLASM extracts targets from =V() constants only.
    """
    hlasm = LANGUAGE_DEFINITIONS["hlasm"]
    calls_out = hlasm["rules"]["calls_out"]

    # 1. Signature Tests (Positive matches)
    assert calls_out.findall("L 15,=V(PROBEBR)") == ["PROBEBR"]

    # 2. Negative Tests
    assert calls_out.findall("BALR 14,15") == []
    assert calls_out.findall("BR 14") == []
    assert calls_out.findall("OPEN (DCB)") == []

    assert calls_out.groups == 1

    # 3. ReDoS Scale Testing
    payload = "=V(" + ("A" * 10000) + ")"
    assert_redos_immune(calls_out, payload)
