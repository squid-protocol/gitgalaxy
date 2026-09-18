"""
PL/I strict structural-signature coverage (#2502, consolidating #1142). See
gitgalaxy/standards/how_to_add_a_language.md's Strict Testing & Crucible Verification
Framework for the methodology -- an adversarial pass against the signatures registered
in languages/pli.py, not a continuation of the generation work.

Every snippet is a real PL/I shape; most are lifted from the five corpora the rules were
measured on (navikt/DSF, Zowe PL/I language-support samples, IBM zopeneditor-sample,
IBM Bank-of-Z, Rocket BankDemo).
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

PLI = LANGUAGE_DEFINITIONS["pli"]
PLI_RULES = PLI["rules"]
COBOL_RULES = LANGUAGE_DEFINITIONS["cobol"]["rules"]

# ==============================================================================
# TEST 1: PER-SIGNATURE POSITIVE/NEGATIVE COVERAGE
# ==============================================================================
_PLI_SIMPLE_CASES = [
    ("branch", "IF B02.TT_16_66(IND) > 0 THEN", "X = 5;"),
    ("branch", "SELECT (TRANS_OPPL_OMR.BLANKETTYPE);", "EXEC SQL SELECT A INTO :A FROM T;"),
    ("branch", "DO WHILE (MORE_DATA);", "DO;"),
    ("branch", "DO K = (J + 1) TO STOPP_AAR;", "DO;"),
    ("branch", "WHEN ('AP') CALL AP_BLANKETT;", "X = 5;"),
    ("args", "PSAM2: PROCEDURE(CUSTFILE_RECORD, CUSTOMER_BALANCE_STATS);", "CALL PSAM2(A, B);"),
    ("structural_boundaries", "END PSAM1;", "X = 5;"),
    ("structural_boundaries", "DCL X FIXED BIN(31);", "X = 5;"),
    ("func_start", "PSAM1: PROC OPTIONS(MAIN);", "%SCOREGET: PROCEDURE(IDX);"),
    ("class_start", "DEFINE ORDINAL COLOR (RED, GREEN, BLUE);", "DEFINE ALIAS INT FIXED BIN(31);"),
    ("safety", "ON ENDFILE(CUSTFILE) EOF = '1'B;", "PUT LIST('CLOSED ON WEDNESDAY');"),
    ("safety", "ON ERROR SNAP BEGIN;", "ON CONVERSION;"),
    ("safety", "EXEC CICS HANDLE CONDITION NOTFND(NOT_FOUND);", "EXEC CICS IGNORE CONDITION ERROR;"),
    ("safety", "IF SQLCODE < 0 THEN", "IF SQLCODE_SAVED = 0 THEN"),
    ("safety", "(SUBSCRIPTRANGE): A(I) = 1;", "DCL X CHAR(SIZE);"),
    ("safety_bypasses", "GO TO L999;", "EXEC SQL WHENEVER SQLERROR GO TO ERR;"),
    ("safety_bypasses", "(NOSIZE): X = Y * Z;", "(SIZE): X = Y * Z;"),
    ("safety_bypasses", "ON CONVERSION;", "ON CONVERSION BEGIN;"),
    ("safety_bypasses", "EXEC CICS HANDLE CONDITION ERROR NOHANDLE;", "X = 5;"),
    ("high_risk_execution", "STOP;", "GO TO EXIT;"),
    ("high_risk_execution", "FETCH IRXINIT;", "EXEC SQL FETCH C1 INTO :A;"),
    ("high_risk_execution", "EXEC SQL EXECUTE IMMEDIATE :STMT;", "EXEC SQL SELECT 1 INTO :A FROM T;"),
    ("io", "READ FILE(CUSTFILE) INTO(CUSTOMER_RECORD);", "CALL READ_FILE(X);"),
    ("io", "OPEN FILE(TRANFILE) INPUT;", "CLOSE FILE(TRANFILE);"),
    ("io", "EXEC CICS READ FILE('BNKCUST') INTO(REC) RIDFLD(KEY);", "X = 5;"),
    ("io", "CALL PLITDLI (PARM_CT_4, PCB, IO_AREA, SSA1);", "CALL SKRIV_FEIL(X);"),
    ("io", "EXEC SQL SELECT CURRENT TIMESTAMP INTO :TS FROM SYSIBM.SYSDUMMY1;", "EXEC SQL INCLUDE SQLCA;"),
    ("io", "PUT FILE(REPORT) EDIT(LINE)(A);", "PUT SKIP LIST('HELLO');"),
    ("api", "R001152: PROC (COMMAREA_PEKER) OPTIONS (MAIN);", "TRANTOT: PROCEDURE;"),
    ("api", "PACK: PACKAGE EXPORTS(PROBE_A, PROBE_B);", "X = 5;"),
    ("api", "B: ENTRY(X, Y);", "DCL X ENTRY EXTERNAL;"),
    ("state_mutation", "DCL X FIXED BIN(31); X = 1;", "IF X = 1 THEN CALL P;"),
    ("state_mutation", "END; COUNT += 1;", "DO I = 1 TO 10;"),
    ("dead_code", "/*     IF X > 0 THEN   */", "/* this routine calls the ledger */"),
    ("dead_code", "// CALL OLD_ROUTINE(X);", "// just a note"),
    ("doc", "/**\n * Computes the balance.\n */", "/** SECTION BANNER **/"),
    ("doc", "/* PURPOSE: PRINT THE CUSTOMER REPORT */", "/* just a note */"),
    ("test", "%INCLUDE ZUNIT;", "DCL UNIT_COUNT FIXED;"),
    ("concurrency", "ATTACH WORKER THREAD(T);", "X = 5;"),
    ("concurrency", "EXEC CICS DELAY INTERVAL(005);", "X = 5;"),
    ("ui_framework", "EXEC CICS SEND MAP('S001014') MAPSET('S001013');", "X = 5;"),
    ("globals", "DCL COUNTER FIXED BIN(31) STATIC INIT(0);", "DCL PLITDLI EXTERNAL ENTRY;"),
    ("globals", "DCL SHARED_AREA CHAR(80) EXTERNAL;", "DCL BASE64E ENTRY(CHAR(8)) EXTERNAL('BASE64E');"),
    ("decorators", "*PROCESS SOURCE RULES(LAXIF);", "X = 5;"),
    ("decorators", "MAIN: PROC OPTIONS(MAIN);", "X = 5;"),
    ("scientific", "ANS = SIND(ARG1) * ARG2;", "SUM(I) = 0;"),
    ("reflection_metaprogramming", "DCL A CHAR(4) DEFINED B;", "X = 5;"),
    ("import", "%INCLUDE P0019908;", "DCL INCLUDE_FLAG BIT(1);"),
    ("import", "EXEC SQL INCLUDE SQLCA;", "X = 5;"),
    ("ownership", "/* Author: Doug Stout */", "/* just a note */"),
    ("planned_debt", "/* TODO: handle overflow */", "/* done */"),
    ("fragile_debt", "/* HACK: workaround for CICS 3.2 */", "/* clean */"),
    ("spec_exposure", "/* [SPEC-123] */", "/* just a note */"),
    ("ssr_boundaries", "EXEC CICS WEB SEND FROM(PAGE);", "X = 5;"),
    ("events", "CALL MQPUT (HCONN, HOBJ, MD, PMO, LEN, BUF, CC, RC);", "CALL MQGET (HCONN, HOBJ);"),
    ("macros", "%IF BUILDENV = 'PRODUCTION' %THEN %DO;", "%INCLUDE X;"),
    ("macros", "%DOUBLE: PROCEDURE(N) RETURNS(FIXED);", "DOUBLE: PROCEDURE(N);"),
    ("pointers", "DCL 1 B01 BASED (B01_PEKER),", "X = 5;"),
    ("pointers", "KOM_OMR.B01_PEKER = ADDR(B01);", "X = 5;"),
    ("pointers", "P->FIELD = 5;", "EXEC CICS HANDLE CONDITION ERROR(E);"),
    ("memory_alloc", "ALLOCATE B01;", "DCL ALLOCATION_COUNT FIXED;"),
    ("memory_alloc", "EXEC CICS GETMAIN SET(P) LENGTH(100);", "EXEC CICS FREE CHILD(TOKEN);"),
    ("telemetry", "CALL PLIDUMP('TFBHC');", "DCL PLIDUMP BUILTIN;"),
    ("telemetry", "EXEC CICS WRITE OPERATOR TEXT(MSG);", "X = 5;"),
    ("debug_prints", "PUT SKIP LIST('HELLO');", "PUT FILE(REPORT) EDIT(X)(A);"),
    ("debug_prints", "DISPLAY('INVALID REPLY');", "PUT STRING(BUF) EDIT(X)(A);"),
    ("explicit_casts", "PO = SUBSTR(UNSPEC(S99MISC), 7, 1);", "DCL NAME CHAR(8);"),
    ("explicit_casts", "S = CHAR(N);", "DCL (A, B) CHAR(8);"),
    ("panics_and_aborts", "SIGNAL ERROR;", "EXEC CICS SIGNAL EVENT(E);"),
    ("panics_and_aborts", "EXEC CICS ABEND ABCODE(FEIL);", "THEN GOTO EXIT;"),
    ("thread_sleeps", "DELAY(500);", "DCL DELAY_MS FIXED;"),
    ("bitwise_ops", "FLAGS = IAND(FLAGS, MASK);", "X = A & B;"),
    ("sync_locks", "EXEC CICS ENQ RESOURCE(ACCT);", "EXEC CICS DEQ RESOURCE(ACCT);"),
    ("immutability_locks", "DCL PI FLOAT VALUE(3.14159);", "DCL X FIXED INIT(5);"),
    ("immutability_locks", "DCL P POINTER NONASSIGNABLE;", "X = 5;"),
    ("cleanup", "CLOSE FILE(TRANFILE);", "CALL CLOSE_ALL;"),
    ("cleanup", "FREE B01;", "EXEC CICS FREE;"),
    ("encapsulation", "DCL IO_AREA AREA(2048) INTERNAL;", "CALL GET_ENTRY ('INTERNAL');"),
    ("listeners", "EXEC CICS HANDLE AID PF3(PF3) ENTER(ENTER);", "X = 5;"),
    ("serialization_parsing", "RC = JSONPUTVALUE(BUF, SIZE, REC);", "X = 5;"),
    ("time_date_logic", "DAGENS_DATO = DATE();", "DCL DATE_FIELD CHAR(6);"),
    ("time_date_logic", "EXEC CICS ASKTIME ABSTIME(T);", "X = 5;"),
    ("ipc_rpc_bridges", "EXEC CICS LINK PROGRAM('STRAC00P') COMMAREA(X) LENGTH(L);", "CALL LOCAL_PROC(X);"),
    ("ipc_rpc_bridges", "EXEC CICS PUT CONTAINER('REQ') CHANNEL('CH') FROM(REC);", "X = 5;"),
    ("auth_middleware", "EXEC CICS SIGNON USERID(WS_USER) PASSWORD(WS_PASS);", "SIGNON_FLAG = '1'B;"),
    ("auth_middleware", "EXEC SQL GRANT SELECT ON T1 TO PUBLIC;", "/* grant nothing */ X = 5;"),
]


@pytest.mark.parametrize("signature,positive,negative", _PLI_SIMPLE_CASES)
def test_pli_signature_positive_and_negative(signature, positive, negative):
    pattern = PLI_RULES[signature]
    assert pattern is not None, f"pli's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"pli {signature!r} failed its documented positive case: {positive!r}"
    if negative is not None:
        assert not pattern.search(negative), f"pli {signature!r} matched an excluded case: {negative!r}"


def test_every_non_none_rule_has_a_simple_case():
    covered = {sig for sig, _, _ in _PLI_SIMPLE_CASES}
    live = {k for k, v in PLI_RULES.items() if v is not None and not k.startswith("_")}
    assert live - covered == set(), f"rules with no positive/negative case: {sorted(live - covered)}"


# ==============================================================================
# TEST 2: SCHEMA COMPLETENESS (Rule 4 / Step 4 item 9)
# ==============================================================================
_BASELINE_KEYS = [
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

# PL/I has none of these: no anonymous procedures, no parametric types, no transform
# form, no IoC convention, no inline machine code, no test-skip marker, no regex facility;
# hardcoded_secrets is a baseline rule in three languages only (the security lens covers
# the rest).
_EXPECTED_NONE_KEYS = {
    "closures", "generics", "comprehensions", "hardcoded_secrets", "dependency_injection",
    "inline_asm", "test_skip", "regex_execution",
    "system_config_mutation",
}  # fmt: skip


def test_pli_schema_completeness():
    missing = set(_BASELINE_KEYS) - set(PLI_RULES)
    assert not missing, f"pli rules dict is missing baseline keys entirely (not even None): {missing}"
    extra = set(PLI_RULES) - set(_BASELINE_KEYS)
    assert extra == {"_visibility_export_list"}, f"unexpected non-baseline keys: {extra}"


def test_pli_none_keys_are_the_intended_set():
    actual_none = {k for k, v in PLI_RULES.items() if v is None}
    assert actual_none == _EXPECTED_NONE_KEYS, f"unexpected None keys: {actual_none ^ _EXPECTED_NONE_KEYS}"


def test_pli_registration():
    assert set(PLI["extensions"]) == {".pli", ".pl1", ".plinc"}
    assert ".inc" not in PLI["extensions"], ".inc belongs to half a dozen languages"
    assert PLI["case_insensitive_imports"] is True


# ==============================================================================
# TEST 3: LEXICAL-FAMILY SANITY CHECK (Step 4 item 8), through the real Prism
# ==============================================================================
def test_pli_lexical_family_strips_both_comment_styles_and_keeps_strings():
    from gitgalaxy.core.prism import Prism
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    assert PLI["lexical_family"] == "standard_block"
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    sample = (
        " /* HEADER: this probe never calls FETCH */                          00000100\r\n"
        " MAIN: PROC OPTIONS(MAIN);                                            00000200\r\n"
        "   DCL MSG CHAR(40) INIT('It''s /* not a comment */ here');\r\n"
        "   DCL URL CHAR(20) INIT('http://host/x');  // trailing line comment\r\n"
        "   /* multi-line\r\n      comment IF X THEN */ X = 1;\r\n"
        " END MAIN;\r\n"
    )
    result = prism.split_streams(sample, "pli")
    code, comments = result["code_stream"], result["comment_stream"]

    assert "never calls FETCH" in comments and "never calls FETCH" not in code
    assert "trailing line comment" in comments and "trailing line comment" not in code
    assert "comment IF X THEN" in comments and "comment IF X THEN" not in code
    # a quoted `/* */` and a quoted `//` are data, not comments
    assert "INIT('It''s /* not a comment */ here');" in code
    assert "INIT('http://host/x');" in code
    assert "MAIN: PROC OPTIONS(MAIN);" in code


# ==============================================================================
# TEST 4: SYMBOLIC-BOUNDARY AUDIT (Rule 9/10) -- `@ # $` are identifier characters
# ==============================================================================
def test_pli_keyword_guards_respect_the_identifier_alphabet():
    # `\b` would fire between `$` and a letter; the explicit guards must not.
    assert not PLI_RULES["high_risk_execution"].search("$STOP;")
    assert not PLI_RULES["branch"].search("IF@FLAG = 1;")
    assert not PLI_RULES["structural_boundaries"].search("#END = 1;")
    assert not PLI_RULES["globals"].search("STATIC$FLAG = 1;")
    # ...and a keyword followed by punctuation still matches.
    assert PLI_RULES["branch"].search("IF(X > 0) THEN")
    assert PLI_RULES["structural_boundaries"].search("END;")


def test_pli_call_forms_match_with_zero_and_quoted_first_arguments():
    assert PLI_RULES["time_date_logic"].search("D = DATE();")
    assert PLI_RULES["telemetry"].search("CALL PLIDUMP('TFBHC');")
    assert PLI_RULES["debug_prints"].search("DISPLAY('X');")
    assert PLI_RULES["io"].search("CALL PLITDLI(PARM);")


# ==============================================================================
# TEST 5: RE.M COMPLETENESS AUDIT (Rule 13)
# ==============================================================================
def test_pli_caret_anchored_rules_all_set_multiline_flag():
    caret = [k for k, p in PLI_RULES.items() if isinstance(p, re.Pattern) and re.search(r"(?<!\\)(?<!\[)\^", p.pattern)]
    assert caret, "expected ^-anchored rules (decorators/doc/ownership) -- audit is a no-op otherwise"
    for key in caret:
        assert PLI_RULES[key].flags & re.M, f"pli {key!r} uses ^ without re.M"


# ==============================================================================
# TEST 6: CICS / SQL / DLI PARITY WITH COBOL (#2502's "identically to COBOL")
# ==============================================================================
_CICS_PARITY = [
    ("safety", "EXEC CICS HANDLE ABEND LABEL(ABEND_RTN)"),
    ("safety", "EXEC CICS SYNCPOINT ROLLBACK"),
    ("safety", "EXEC SQL COMMIT"),
    ("safety_bypasses", "EXEC CICS IGNORE CONDITION LENGERR"),
    ("safety_bypasses", "EXEC SQL WHENEVER SQLERROR CONTINUE"),
    ("io", "EXEC CICS READQ TS QUEUE('Q') INTO(REC)"),
    ("io", "EXEC CICS STARTBR FILE('F') RIDFLD(K)"),
    ("io", "EXEC CICS GET COUNTER('C') VALUE(V)"),
    ("state_mutation", None),
    ("concurrency", "EXEC CICS RUN TRANSID('T') CHILD(C)"),
    ("concurrency", "EXEC CICS FETCH CHILD(C)"),
    ("ui_framework", "EXEC CICS SEND TEXT FROM(MSG)"),
    ("ssr_boundaries", "EXEC CICS DOCUMENT CREATE DOCTOKEN(D)"),
    ("events", "EXEC CICS SIGNAL EVENT(E)"),
    ("pointers", "EXEC CICS ADDRESS EIB(P)"),
    ("memory_alloc", "EXEC CICS FREEMAIN64 DATAPOINTER(P)"),
    ("telemetry", "EXEC CICS WRITEQ TD QUEUE('CSMT') FROM(MSG)"),
    ("panics_and_aborts", "EXEC CICS ABEND ABCODE('X')"),
    ("thread_sleeps", "EXEC CICS SUSPEND"),
    ("sync_locks", "EXEC CICS ENQ RESOURCE(R)"),
    ("cleanup", "EXEC CICS ENDBR FILE('F')"),
    ("cleanup", "EXEC CICS FREE CHILD(C)"),
    ("listeners", "EXEC CICS RECEIVE MAP('M')"),
    ("serialization_parsing", "EXEC CICS TRANSFORM DATATOXML CHANNEL(C)"),
    ("time_date_logic", "EXEC CICS FORMATTIME ABSTIME(T)"),
    ("ipc_rpc_bridges", "EXEC CICS XCTL PROGRAM('P')"),
    ("ipc_rpc_bridges", "EXEC CICS GET CONTAINER('C') CHANNEL('CH') INTO(R)"),
    ("reflection_metaprogramming", "EXEC DLI GU USING PCB(1)"),
]


@pytest.mark.parametrize("signature,statement", [c for c in _CICS_PARITY if c[1]])
def test_pli_counts_embedded_mainframe_commands_like_cobol(signature, statement):
    cobol_hits = len(COBOL_RULES[signature].findall(statement + " END-EXEC."))
    pli_hits = len(PLI_RULES[signature].findall(statement + ";"))
    assert cobol_hits >= 1, f"fixture error: cobol {signature!r} does not own {statement!r}"
    assert pli_hits == cobol_hits, f"{signature!r} on {statement!r}: cobol {cobol_hits}, pli {pli_hits}"


def test_pli_deliberate_divergences_from_cobol():
    """
    Three places the PL/I rule is narrower than cobol's on purpose, each because the
    PL/I construct means something else.
    """
    # A PL/I CALL invokes a procedure -- usually an internal one in the same program.
    # cobol's CALL invokes a separately compiled program and stays a bridge.
    assert COBOL_RULES["ipc_rpc_bridges"].search("CALL 'SUBPROG' USING A.")
    assert not PLI_RULES["ipc_rpc_bridges"].search("CALL SKRIV_FEIL(X);")
    # EXEC SQL INCLUDE binds a structure (import's), and DECLARE / WHENEVER move no data.
    for stmt in (
        "EXEC SQL INCLUDE SQLCA;",
        "EXEC SQL DECLARE C1 CURSOR FOR SELECT 1;",
        "EXEC SQL WHENEVER NOT FOUND GO TO X;",
    ):
        assert not PLI_RULES["io"].search(stmt), stmt
    # MQGET receives; the declared events row excludes the receiving side.
    assert not PLI_RULES["events"].search("CALL MQGET (HCONN, HOBJ);")
    assert PLI_RULES["listeners"].search("CALL MQGET (HCONN, HOBJ);")


# ==============================================================================
# TEST 7: AMBIGUITY SWEEP (Rule 6) -- intended duals and enforced separations
# ==============================================================================
def test_pli_intentional_double_classifications():
    duals = [
        ("STOP;", "high_risk_execution", "panics_and_aborts"),  # #2878's termination dual
        ("FREE B01;", "memory_alloc", "cleanup"),  # #1142's pair; cobol counts FREE in both
        ("DELETE FILE(MASTER) KEY(K);", "io", "cleanup"),  # cobol's DELETE dual
        ("CALL PLITDLI(PARM, PCB, AREA);", "io", "ipc_rpc_bridges"),  # the IMS bridge
        ("EXEC CICS ENQ RESOURCE(R);", "concurrency", "sync_locks"),
        ("EXEC CICS DELAY INTERVAL(5);", "concurrency", "thread_sleeps"),
        ("MAIN: PROC OPTIONS(MAIN);", "api", "decorators"),
        ("EXEC CICS WRITEQ TD QUEUE('CSMT') FROM(M);", "io", "telemetry"),
    ]
    for text, a, b in duals:
        assert PLI_RULES[a].search(text), f"{a} should own {text!r}"
        assert PLI_RULES[b].search(text), f"{b} should also own {text!r}"


def test_pli_enforced_separations():
    # A WHENEVER ... GO TO installs a handler; it is not also a bypass.
    stmt = "EXEC SQL WHENEVER SQLERROR GO TO ERR;"
    assert PLI_RULES["safety"].search(stmt) and not PLI_RULES["safety_bypasses"].search(stmt)
    # A null on-unit swallows the condition; it is not also a handler.
    assert PLI_RULES["safety_bypasses"].search("ON CONVERSION;") and not PLI_RULES["safety"].search("ON CONVERSION;")
    # PUT is exactly one of print / io / neither.
    for stmt, owner in (
        ("PUT SKIP LIST('HELLO');", "debug_prints"),
        ("PUT FILE(SYSPRINT) SKIP LIST(X);", "debug_prints"),
        ("PUT FILE(REPORT) EDIT(X)(A);", "io"),
        ("PUT STRING(BUF) EDIT(X)(A);", None),
    ):
        owners = {r for r in ("debug_prints", "io") if PLI_RULES[r].search(stmt)}
        assert owners == ({owner} if owner else set()), (stmt, owners)
    # An embedded CICS READ is one io hit, not two.
    assert len(PLI_RULES["io"].findall("EXEC CICS READ FILE('BNKCUST') INTO(REC);")) == 1
    # A declaration attribute is not a cast.
    assert not PLI_RULES["explicit_casts"].search("DCL NAME CHAR(8) INIT('');")
    # CICS spells HANDLE with the same word pointers would want.
    assert not PLI_RULES["pointers"].search("EXEC CICS HANDLE ABEND LABEL(X);")
    # A preprocessor procedure is macros', never a function or its parameters.
    pp = "%DOUBLE: PROCEDURE(N) RETURNS(FIXED);"
    assert PLI_RULES["macros"].search(pp)
    assert not PLI_RULES["func_start"].search(pp) and not PLI_RULES["args"].search(pp)


def test_pli_state_mutation_counts_writes_not_comparisons():
    """
    PL/I spells assignment and equality the same way; the statement-start anchor is the
    whole rule. Nine writes below; the IF conditions, the DO loop header, the continued
    condition line and the DECLARE initial value are not writes.
    """
    code = (
        " P: PROC;\n"
        "   DCL X FIXED BIN(31) INIT(0);\n"
        "   X = 1;\n"
        "   IF X = 1 THEN Y = 2; ELSE Z = 3;\n"
        "   DO I = 1 TO 10;\n"
        "      A(I) = I;\n"
        "   END;\n"
        "   IF (B01.X = 'A' !\n"
        "       B01.Y = 'U') THEN\n"
        "      COUNT += 1;\n"
        "   P->FIELD = 5;\n"
        "   A, B = 0;\n"
        "   SELECT (X);\n"
        "     WHEN (1) W = 1;\n"
        "     OTHERWISE W = 0;\n"
        "   END;\n"
        " END P;\n"
    )
    assert len(PLI_RULES["state_mutation"].findall(code)) == 9


def test_pli_state_mutation_crosses_a_sequence_field():
    # navikt/DSF: `;` then columns 73-80 carry a sequence number before the next line.
    code = "FEIL_BLANKETT = '0'B;                                    00001200\n   FEIL_FUNNET = '0'B;"
    assert len(PLI_RULES["state_mutation"].findall(code)) == 1  # the second statement


# ==============================================================================
# TEST 8: THE REAL EXTRACTOR -- Mode A slicing and per-procedure args (#2502)
# ==============================================================================
def test_pli_procedures_slice_through_mode_a_with_their_own_args():
    """
    pli is registered in detector.py's Mode A tuple (ada's slot). Without it the language
    falls through to brace slicing and keeps almost no procedure bodies. The preprocessor
    procedure between the two is compile-time code and must not become a function.
    """
    from gitgalaxy.core.detector import StructuralExtractor

    program = (
        " MAIN: PROC OPTIONS(MAIN);\n"
        "   DCL X FIXED BIN(31) INIT(0);\n"
        "   CALL WORKER(X, 2);\n"
        " %DOUBLE: PROCEDURE(N) RETURNS(FIXED);\n"
        "   RETURN(2*N);\n"
        " %END;\n"
        " END MAIN;\n"
        " WORKER: PROCEDURE(A, B);\n"
        "   DCL (A, B) FIXED BIN(31);\n"
        "   A = B;\n"
        " END WORKER;\n"
    )
    functions = StructuralExtractor("pli", LANGUAGE_DEFINITIONS).splice(program, "")["functions"]
    by_name = {f["name"]: f for f in functions}

    assert set(by_name) == {"MAIN", "WORKER"}
    assert by_name["MAIN"]["args"] == 0
    assert by_name["WORKER"]["args"] == 2
    assert by_name["WORKER"]["start_line"] == 8


def test_pli_is_in_the_mode_a_dispatch_and_named_class_allowlist():
    import inspect

    from gitgalaxy.core import detector

    assert "pli" in detector._CLASS_START_NAMED_EXTRACTION_LANGS
    source = inspect.getsource(detector)
    assert '"ada",' in source and '"pli",' in source


# ==============================================================================
# TEST 9: REDOS ADVERSARIAL SWEEP (Rule 5/14) -- absolute ceilings on large payloads
# ==============================================================================
_N = 200000


@pytest.mark.parametrize(
    "signature,payload",
    [
        ("func_start", "A:" + " " * _N),
        ("func_start", ("A:" + " " * 70 + "00000100\n") * 20000),
        ("args", "X: PROC(" + "A," * (_N // 2)),
        ("state_mutation", ";" + " " * _N),
        ("state_mutation", "; X(" + "A" * _N),
        ("state_mutation", "; A" + ", A" * (_N // 3)),
        ("state_mutation", "WHEN (" + "(" * _N),
        ("state_mutation", (";" + " " * 70 + "00000100\n") * 20000),
        ("safety", "(SIZE" + ", AA" * (_N // 4)),
        ("safety", "ON KEY(" + "A" * _N),
        ("safety_bypasses", "(NOSIZE" + ", AA" * (_N // 4)),
        ("safety_bypasses", "ON CONVERSION" + " " * _N),
        ("high_risk_execution", "FETCH " + "A" * _N),
        ("high_risk_execution", "FETCH X TITLE(" + "A" * _N),
        ("io", "PUT " + "A" * _N),
        ("io", "LOCATE " + "A" * _N),
        ("debug_prints", "PUT SKIP " + "A" * _N),
        ("dead_code", "/* IF " + "A" * _N),
        ("doc", "/**" + "A" * _N),
        ("api", "OPTIONS(" + "A" * _N),
        ("_visibility_export_list", "EXPORTS(" + "A" * _N),
        ("_dependency_capture", "%INCLUDE SYSLIB(" + " " * _N),
        ("class_start", "DEFINE STRUCTURE " + " " * _N),
        ("globals", "STATIC" + " " * _N),
        ("ownership", "/* Author:" + " " * _N),
        ("macros", "%" + "A" * _N),
        ("spec_exposure", "[SPEC-" + "1" * _N),
        ("explicit_casts", "=" + " " * _N),
        ("memory_alloc", "ALLOCATE" + " " * _N),
        ("branch", "DO " + "A" * _N),
    ],
    ids=lambda v: v if len(v) <= 30 else f"{v[:10].strip()}...x{len(v)}",
)
def test_pli_redos_immunity(signature, payload):
    assert_redos_immune(PLI_RULES[signature], payload, timeout_sec=3.0)


# ==============================================================================
# TEST 10: API CONTRACT (#2730) -- publishing markers, not references
# ==============================================================================
def test_pli_api_contract_2730():
    api = PLI_RULES["api"]
    assert api.search("PSAM1: PROC OPTIONS(MAIN) RETURNS(DEC(12,2));")
    assert api.search("ZBNKEXT1: PROC(P) OPTIONS(FETCHABLE);")
    assert api.search("PACK: PACKAGE EXPORTS(*);")
    assert api.search("SECOND: ENTRY(X);")

    assert not api.search("TRANTOT: PROCEDURE;")  # internal procedure, nothing publishes it
    assert not api.search("DCL PLITDLI EXTERNAL ENTRY;")  # a reference to someone else's entry
    assert not api.search("DCL E ENTRY(CHAR(8)) EXTERNAL('BASE64E');")
    assert not api.search("CALL PSAM2(A, B);")


def test_pli_export_list_captures_the_exported_names():
    rx = PLI_RULES["_visibility_export_list"]
    m = rx.search("PACK: PACKAGE EXPORTS(PROBE_GLOBALS, PROBE_TEST, PROBE_SAFETY);")
    assert m and [n.strip() for n in m.group(1).split(",")] == ["PROBE_GLOBALS", "PROBE_TEST", "PROBE_SAFETY"]
