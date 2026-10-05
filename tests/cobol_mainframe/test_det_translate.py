"""det-port translator pieces that need no corpus: COBOL conditions and expressions (det/expr.py), statement parsing
(det/stmt.py) and EXEC CICS options (det/cics.py). Each case is a COBOL rule the proofs of the det ports depend on;
the ports themselves are proven by tests/tools/det_port.py against GnuCOBOL."""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import expr as E  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import stmt as S  # noqa: E402


def R(name: str) -> E.Ref:  # noqa: N802 -- a Ref, as the AST writes it
    return E.Ref(name)


def test_abbreviated_relation_repeats_subject_and_operator():
    c = E.parse_condition("A = 1 OR 2")
    assert c == E.Or(E.Rel("=", R("A"), E.Lit(Decimal(1))), E.Rel("=", R("A"), E.Lit(Decimal(2))))


def test_abbreviated_not_applies_to_every_object():
    # A NOT = 'Y' AND 'N' is A NOT = 'Y' AND A NOT = 'N'
    c = E.parse_condition("A NOT = 'Y' AND 'N'")
    assert c == E.And(E.Not(E.Rel("=", R("A"), E.Lit("Y"))), E.Not(E.Rel("=", R("A"), E.Lit("N"))))


def test_abbreviated_data_name_objects_carry_the_relation():
    # EIBAID NOT = DFHENTER AND DFHPF7 AND DFHPF3: DFHPF7 / DFHPF3 are objects unless they are condition-names
    c = E.parse_condition("EIBAID NOT = DFHENTER AND DFHPF7 AND DFHPF3")
    assert c.right.abbrev == ("=", R("EIBAID"), True)
    assert c.left.right.abbrev == ("=", R("EIBAID"), True)


def test_dfhresp_is_its_resp_value():
    assert E.parse_condition("WS-RESP-CD = DFHRESP(NOTFND)") == E.Rel("=", R("WS-RESP-CD"), E.Lit(Decimal(13)))


def test_dfhvalue_is_its_cvda():
    # IBM CICS TS API Reference, CVDAs and numeric values: UCTRAN 450, IMMEDIATE 2
    assert E.parse_condition("WS-X = DFHVALUE(UCTRAN)") == E.Rel("=", R("WS-X"), E.Lit(Decimal(450)))
    assert E.parse_arith("DFHVALUE(IMMEDIATE)") == E.Lit(Decimal(2))


def test_arithmetic_precedence_and_signed_literal():
    e = E.parse_arith("A + B * 2 ** 3 - -1")
    assert e == E.Bin(
        "-", E.Bin("+", R("A"), E.Bin("*", R("B"), E.Bin("**", E.Lit(Decimal(2)), E.Lit(Decimal(3))))),
        E.Lit(Decimal(-1)),
    )  # fmt: skip


def test_class_condition_with_reference_modification():
    c = E.parse_condition("WS-DATE(1:4) NOT NUMERIC")
    assert isinstance(c, E.ClassCond) and c.negated and c.operand.refmod == (E.Lit(Decimal(1)), E.Lit(Decimal(4)))


@pytest.mark.parametrize(
    ("text", "kinds"),
    [
        ("INSPECT X TALLYING I FOR ALL 'S' ALL 'U'", [("tally", "ALL"), ("tally", "ALL")]),
        ("INSPECT X REPLACING ALL 'S' BY '1' ALL 'U' BY '1' CHARACTERS BY '0'",
         [("replace", "ALL"), ("replace", "ALL"), ("replace", "CHARACTERS")]),
        ("INSPECT X CONVERTING 'abc' TO 'ABC'", [("convert", None)]),
        ("INSPECT X TALLYING I FOR LEADING SPACES REPLACING FIRST 'A' BY 'B' AFTER INITIAL 'C'",
         [("tally", "LEADING"), ("replace", "FIRST")]),
    ],
)  # fmt: skip
def test_inspect_clauses(text, kinds):
    s = S._statement(text, 1)
    assert s.kind == "INSPECT"
    got = [(c[0], c[2] if c[0] == "tally" else c[1] if c[0] == "replace" else None) for c in s.data["clauses"]]
    assert got == kinds


def test_perform_varying():
    s = S._statement("PERFORM P1 VARYING I FROM 1 BY 1 UNTIL I > 10", 1)
    assert s.kind == "PERFORM" and s.data["target"] == "P1" and s.data["varying"][0] == R("I")


def test_exec_cics_options():
    words, opts = C.parse_exec(
        "EXEC CICS SEND MAP('COSGN0A') MAPSET('COSGN00') FROM(COSGN0AO) ERASE CURSOR RESP(WS-RESP) END-EXEC"
    )
    assert words == ["SEND"]
    assert opts == {"MAP": "'COSGN0A'", "MAPSET": "'COSGN00'", "FROM": "COSGN0AO", "ERASE": None, "CURSOR": None,
                    "RESP": "WS-RESP"}  # fmt: skip


def test_exec_cics_two_word_verb_and_nested_parentheses():
    words, opts = C.parse_exec("EXEC CICS HANDLE ABEND LABEL(ABEND-ROUTINE) END-EXEC")
    assert words == ["HANDLE", "ABEND"] and opts == {"LABEL": "ABEND-ROUTINE"}
    _, opts = C.parse_exec("EXEC CICS READ DATASET(F) RIDFLD(K) KEYLENGTH(LENGTH OF K(1:4)) END-EXEC")
    assert opts["KEYLENGTH"] == "LENGTH OF K(1:4)"


def test_syncpoint_rollback_is_a_rollback():
    words, opts = C.parse_exec("EXEC CICS SYNCPOINT ROLLBACK END-EXEC")
    assert " ".join(words) == "SYNCPOINT ROLLBACK" and opts == {}


def test_statements_keep_their_source_lines_past_a_multi_line_exec_block(tmp_path):
    """A statement's line is its source line (the Db2 repositories' methods are found by it): a multi-line EXEC
    block before it must not shift it, and the block's own period must still end its sentence."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import source as SRC

    src = "\n".join([
        "       IDENTIFICATION DIVISION.", "       PROGRAM-ID. LINES.", "       DATA DIVISION.",
        "       WORKING-STORAGE SECTION.", "       01 A PIC X.", "       PROCEDURE DIVISION.", "       P1.",
        "           EXEC SQL", "               DELETE FROM T", "               WHERE C = 1", "           END-EXEC.",
        "           MOVE 'X' TO A.", "       P2.", "           EXEC CICS RETURN", "           END-EXEC.",
        "           MOVE 'Y' TO A.",
    ]) + "\n"  # fmt: skip
    (tmp_path / "LINES.cbl").write_text(src)
    proc = S.parse(SRC.program_lines(tmp_path / "LINES.cbl", []))
    assert [p.name for p in proc.paragraphs] == ["P1", "P2"]
    p1, p2 = proc.paragraphs
    assert [(s.kind, s.line) for s in p1.body] == [("EXEC", 8), ("MOVE", 12)]
    assert [(s.kind, s.line) for s in p2.body] == [("EXEC", 14), ("MOVE", 16)]


def test_a_when_condition_keeps_its_leading_not():
    """EVALUATE TRUE WHEN NOT A AND B = C: NOT is the condition's own -- (NOT A) AND B = C. Only a value or a range
    takes WHEN NOT as its negation (COTRTUPC's NOT CDEMO-PGM-REENTER AND CDEMO-FROM-PROGRAM = LIT-ADMINPGM)."""
    obj = S._when_object("NOT A-FLAG AND B = C")
    assert obj == ("COND", E.And(E.Not(E.CondName(R("A-FLAG"))), E.Rel("=", R("B"), R("C"))), None, False)
    assert S._when_object("NOT 5") == ("VALUE", E.Lit(Decimal(5)), None, True)
    assert S._when_object("NOT 1 THRU 9")[0] == "RANGE" and S._when_object("NOT 1 THRU 9")[3] is True


def test_each_entry_runs_with_its_programs_trunc(tmp_path):
    """#4102: TRUNC(STD) is IBM's default; a program's CBL card or the compile PARM says otherwise. Each entry swaps it
    in and restores the caller's, so a LINK into a program compiled otherwise leaves the caller's as it was."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "T.cbl"
    src.write_text("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. T.\n", encoding="ascii")
    assert P.trunc_std(src) is True
    assert P.trunc_std(src, ["TRUNC(BIN)"]) is False
    src.write_text(
        "       PROCESS TRUNC(STD)\n       IDENTIFICATION DIVISION.\n       PROGRAM-ID. T.\n", encoding="ascii"
    )
    assert P.trunc_std(src, ["TRUNC(BIN)"]) is True  # the program's own card wins
    java = (
        'class S {\n    public void runTask(CicsTask task) {\n        x("{");\n        return;\n    }\n'
        "    void other() {\n    }\n}\n"
    )
    out = P.with_trunc(java, True)
    assert "boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(STD)" in out
    assert out.index("finally") < out.index("void other()") and 'x("{");' in out


def test_an_item_nothing_uses_has_no_field():
    """A Field is a view of its storage's bytes: one nothing reads or writes is dead code, so it is not emitted. The
    storage keeps every byte (its image and its length), so the proof sees the same bytes; only the view goes."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    java = (
        "class S {\n"
        "    private final Field f1_REC = Field.group(s_REC, 0, 4);\n"
        "    private final Field f2_A = Field.alphanumeric(s_REC, 0, 2, false);\n"
        "    private final Field f3_A_B = Field.alphanumeric(s_REC, 2, 2, false);\n"
        "    private final Field f4_C = Field.zoned(s_REC, 2, 2, 0, false, false, false);\n"
        "    private int p0() {\n        Cobol.move(f2_A, f1_REC, CS);\n        return 1;\n    }\n"
        '    private boolean isOk() { return Cobol.compare(f4_C, "00", CS) == 0; }\n'
        "}\n"
    )
    out = P.drop_unused_fields(java)
    assert "f3_A_B" not in out
    assert all(f in out for f in ("f1_REC = Field.group", "f2_A = Field.", "f4_C = Field."))
    assert P.drop_unused_fields(out) == out


class _RbaCics(C.Cics):
    """A Cics with operands resolved by name (no program): RIDFLD a fullword, INTO a 56-byte record."""

    SIZES = {"RID": 4, "SHORT": 2, "REC": 56}

    def __init__(self):
        class G:
            n = 0

            def tmpname(self, base):
                G.n += 1
                return f"{base}{G.n}"

        super().__init__(G(), None, "p")

    def field(self, text):
        return f"f_{text}"

    def read_field(self, text):
        return f"f_{text}"

    def size(self, text):
        return self.SIZES[text]

    def name(self, text):
        return f"{text}.strip()"

    def store(self, opts):
        raise AssertionError("an RBA browse needs no keyed store")

    def outcome(self, opts, resp, resp2, ind):
        return [f"{ind}OUTCOME({resp}, {resp2});"]


def test_an_esds_browse_by_rba_is_translated_and_the_rest_refused():
    """#4213 (IBM DBB EPSMLIST): STARTBR / READNEXT / READPREV ... RBA run as CicsTask's RBA browse -- RIDFLD's fullword
    is the RBA, and READNEXT sets it to the RBA of the record read; the record goes INTO. Before #4213 the translator
    dropped RBA and browsed by key. GTEQ / KEYLENGTH with RBA, XRBA, RRN, and READ / WRITE / DELETE by RBA are holes."""
    c = _RbaCics()
    assert c.command("STARTBR DATASET('EPSMORTF') RIDFLD(RID) RBA EQUAL RESP(R)", "") == [
        "int resp1 = task.startbrRba('EPSMORTF'.strip(), CicsTask.rba(DetCics.bytes(f_RID, 4)));",
        "OUTCOME(resp1, 0);",
    ]
    assert c.command("READNEXT FILE('EPSMORTF') INTO(REC) RIDFLD(RID) RBA RESP(R)", "") == [
        "CicsTask.BrowsedRba read2 = task.readnextRba('EPSMORTF'.strip(), CicsTask.rba(DetCics.bytes(f_RID, 4)), 56);",
        "if (read2.record() != null) {",
        "    DetCics.put(f_RID, CicsTask.rbaBytes(read2.rba()));",
        "    DetCics.put(f_REC, read2.record());",
        "}",
        "OUTCOME(read2.resp(), read2.resp2());",
    ]
    assert "task.readprevRba(" in c.command("READPREV FILE(F) INTO(REC) RIDFLD(RID) RBA", "")[0]
    for bad in (
        "STARTBR FILE(F) RIDFLD(RID) RBA GTEQ",
        "STARTBR FILE(F) RIDFLD(RID) RBA KEYLENGTH(4)",
        "STARTBR FILE(F) RIDFLD(SHORT) RBA",
        "STARTBR FILE(F) RIDFLD(RID) XRBA",
        "STARTBR FILE(F) RIDFLD(RID) RRN",
        "READNEXT FILE(F) INTO(REC) RIDFLD(RID) XRBA",
        "READPREV FILE(F) INTO(REC) RIDFLD(RID) RRN",
        "READ FILE(F) INTO(REC) RIDFLD(RID) RBA",
        "WRITE FILE(F) FROM(REC) RIDFLD(RID) RBA",
        "DELETE FILE(F) RIDFLD(RID) RBA",
    ):
        with pytest.raises(C.CicsError):
            c.command(bad, "")


# ---- #4411: accepted-but-ignored options and swallowed parse errors are refused --------------------------------
class _KeyCics(_RbaCics):
    """A keyed file KSDS (key 10 bytes); KEY a 10-byte item, SHORTKEY 6, VARLEN a data item the program writes."""

    SIZES = {**_RbaCics.SIZES, "KEY": 10, "SHORTKEY": 6, "REC": 56}

    def __init__(self):
        super().__init__()

        class GP:
            files = {"KSDS": ("ksdsRepository", "Ksds", None)}

            def file(self, name):
                return self.files.get(name)

            def entity_key(self, entity, prop):
                return 0, 10

        class Untouched:
            values = [("num", Decimal(10))]

        def resolve(ref):
            if ref.name == "KLEN":
                return Untouched()
            from gitgalaxy.tools.cobol_to_java.det.gen import Untranslatable

            raise Untranslatable(f"{ref.name}: varies")

        self.gp = GP()
        self.g.resolve = resolve
        self.g.never_written = lambda it: True

    def store(self, opts):
        return "store(F)"


@pytest.mark.parametrize(
    "text",
    [
        "RETURN IMMEDIATE",  # 9 programs: IMMEDIATE ignored
        "RETURN TRANSID('T1') IMMEDIATE",
        "READ FILE('KSDS') INTO(REC) RIDFLD(KEY) GTEQ",
        "READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(6) GENERIC",
        "STARTBR FILE('KSDS') RIDFLD(KEY) GENERIC KEYLENGTH(6)",
        "STARTBR FILE('KSDS') RIDFLD(KEY) REQID(2)",
        "READNEXT FILE('KSDS') INTO(REC) RIDFLD(KEY) REQID(2)",
        "ENDBR FILE('KSDS') REQID(2)",
        "LINK PROGRAM('P') COMMAREA(REC) SYNCONRETURN",  # 10 programs, one repo
        "LINK PROGRAM('P') COMMAREA(REC) DATALENGTH(KEY)",
        "ASSIGN USERID(REC)",
        "ASSIGN NETNAME(REC) APPLID(REC)",
        "FORMATTIME ABSTIME(REC) YYYYMMDD(REC) DAYOFMONTH(KEY)",
        "ASKTIME ABSTIME(REC) RESP(R)",
        "RECEIVE MAP('M') MAPSET('S') INTO(REC) ASIS",
        "WRITEQ QUEUE('Q') FROM(REC) TD",  # a TD option after the verb is not TS
        "READQ TS QUEUE('Q') SET(PTR)",
        "SEND TEXT FROM(REC) CURSOR(KEY)",
        "HANDLE ABEND LABEL(X) RESP(R)",
        "INQUIRE PROGRAM('P') STATUS(REC)",
    ],
)
def test_an_option_the_translation_would_ignore_is_refused_by_name(text):
    with pytest.raises(C.CicsError, match="not modelled"):
        _KeyCics().command(text, "")


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(6)", "a partial key"),  # (CICS: INVREQ)
        ("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(LENGTH OF SHORTKEY)", "a partial key"),
        ("WRITE FILE('KSDS') FROM(REC) RIDFLD(KEY) KEYLENGTH(VARLEN)", "not a known length"),
        ("DELETE FILE(WS-FILE) RIDFLD(KEY) KEYLENGTH(10)", "not a known length on a known file"),
        ("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) LENGTH(VARLEN)", "not INTO's length"),  # GenApp LGUCVS01
        ("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) LENGTH(10)", "not INTO's length"),
    ],
)
def test_keylength_and_read_length_only_where_they_change_nothing(text, why):
    with pytest.raises(C.CicsError, match=why):
        _KeyCics().command(text, "")


def test_full_key_keylength_and_into_length_translate_as_before():
    c = _KeyCics()
    plain = c.command("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) RESP(R)", "")
    for extra in (
        "KEYLENGTH(10)",
        "KEYLENGTH(LENGTH OF KEY)",
        "KEYLENGTH(KLEN)",
        "LENGTH(LENGTH OF REC)",
        "LENGTH(56)",
    ):
        assert _KeyCics().command(f"READ FILE('KSDS') INTO(REC) RIDFLD(KEY) {extra} RESP(R)", "") == plain


# A CICS option the translator recognises must be honoured or refused (#4411). IBM CICS TS API reference: the
# options of each modelled command. Every one is either in det.cics.OPTIONS (honoured; the table says why where it
# has no code of its own) or refused by name.
_IBM_OPTIONS = {
    "RETURN": "TRANSID COMMAREA LENGTH CHANNEL IMMEDIATE INPUTMSG INPUTMSGLEN ENDACTIVITY",
    "LINK": "PROGRAM COMMAREA CHANNEL LENGTH DATALENGTH SYSID SYNCONRETURN TRANSID INPUTMSG INPUTMSGLEN",
    "XCTL": "PROGRAM COMMAREA CHANNEL LENGTH INPUTMSG INPUTMSGLEN",
    "READ": "FILE DATASET UNCOMMITTED CONSISTENT REPEATABLE UPDATE TOKEN INTO SET RIDFLD KEYLENGTH GENERIC SYSID "
    "LENGTH DEBKEY DEBREC RBA RRN XRBA EQUAL GTEQ NOSUSPEND",
    "READNEXT": "FILE DATASET UNCOMMITTED CONSISTENT REPEATABLE UPDATE TOKEN INTO SET LENGTH RIDFLD KEYLENGTH REQID "
    "SYSID RBA RRN XRBA NOSUSPEND",
    "STARTBR": "FILE DATASET RIDFLD KEYLENGTH GENERIC REQID SYSID DEBKEY DEBREC RBA RRN XRBA EQUAL GTEQ",
    "ENDBR": "FILE DATASET REQID SYSID",
    "WRITE": "FILE DATASET MASSINSERT FROM RIDFLD KEYLENGTH SYSID LENGTH RBA RRN XRBA NOSUSPEND",
    "REWRITE": "FILE DATASET TOKEN FROM SYSID LENGTH NOSUSPEND",
    "DELETE": "FILE DATASET TOKEN RIDFLD KEYLENGTH GENERIC NUMREC SYSID RBA RRN XRBA NOSUSPEND",
    "ASSIGN": "ABCODE APPLID INVOKINGPROG PROGRAM SYSID USERID NETNAME OPID TERMCODE STARTCODE TWALENG CWALENG",
    "ABEND": "ABCODE CANCEL NODUMP",
    "FORMATTIME": "ABSTIME DATE FULLDATE DATEFORM DATESEP DAYCOUNT DAYOFMONTH DAYOFWEEK DDMMYY DDMMYYYY MILLISECONDS "
    "MMDDYY MMDDYYYY MONTHOFYEAR STRINGFORMAT TIME TIMESEP YEAR YYDDD YYDDMM YYMMDD YYYYDDD YYYYDDMM YYYYMMDD",
    "SEND MAP": "MAP MAPSET FROM DATAONLY MAPONLY LENGTH CURSOR FORMFIELD ERASE ERASEAUP PRINT FREEKB ALARM FRSET "
    "MSR OUTPARTN ACTPARTN LDC FMHPARMS NLEOM REQID SET PAGING TERMINAL WAIT LAST HONEOM L40 L64 L80 ACCUM",
    "RECEIVE MAP": "MAP MAPSET INTO SET FROMLENGTH FROM TERMINAL ASIS INPARTN",
}


@pytest.mark.parametrize("verb", sorted(_IBM_OPTIONS))
def test_every_option_of_a_modelled_command_is_honoured_or_refused(verb):
    first = verb.split()[0]
    for opt in _IBM_OPTIONS[verb].split():
        words, opts = [first], {opt: "X"}
        if verb.endswith("MAP"):
            opts = {"MAP": "'M'", opt: "X"}
        if opt in C.OPTIONS[C.command_key(words, opts)]:
            continue
        with pytest.raises(C.CicsError, match=f"{opt}: option not modelled"):
            C.check_options(words, opts)


def test_options_honoured_without_code_say_why():
    """An OPTIONS entry is read by the translator (its name appears in det/cics.py's code) or is one of the options
    whose having no effect the table states."""
    src = Path(C.__file__).read_text(encoding="utf-8")
    code = src[src.index("def command_key") :]
    stated = {"NODUMP", "MAIN", "AUXILIARY", "NOSUSPEND", "EQUAL", "GTEQ", "TASK", "UOW", "MAXLIFETIME", "RESOURCE",
              "FOR", "INTERVAL", "TIME", "HOURS", "MINUTES", "SECONDS", "MILLISECS", "TS"}  # fmt: skip
    flags = {*C.MAP_OPTIONS, *C.TEXT_OPTIONS, *C._FORMS}
    for key, allowed in C.OPTIONS.items():
        for opt in allowed or ():
            read = f'"{opt}"' in code or f"'{opt}'" in code
            assert opt in stated | flags or read, f"{key} {opt}: accepted but never read"


# ---- #4437: RESP / RESP2 on SYNCPOINT are written, and every command that accepts RESP writes it ---------------
class _RespCics(_KeyCics):
    """Records the options each outcome() was given; stores (RESP2 alone) as STORE(name, value)."""

    def __init__(self):
        super().__init__()
        self.outcomes = []
        self.g.store_into = lambda ref, value, _rounded: f"STORE({ref.name}, {value});"
        self.g.p = type("P", (), {"name": "PROG"})()

    def outcome(self, opts, resp, resp2, ind):
        self.outcomes.append(dict(opts))
        return [f"{ind}OUTCOME({resp}, {resp2});"]


@pytest.mark.parametrize(
    ("text", "call"),
    [
        ("SYNCPOINT ROLLBACK RESP(R) RESP2(R2)", "task.rollback();"),  # CBSA DBCRFUN 564, INQACC 682
        ("SYNCPOINT ROLLBACK RESP(R) RESP2(R2)".replace("SYNCPOINT ROLLBACK", "SYNCPOINT ROLLBACK NOHANDLE"),
         "task.rollback();"),
        ("SYNCPOINT RESP(R) RESP2(R2)", "task.syncpoint();"),  # XFRFUN 407
        ("SYNCPOINT", "task.syncpoint();"),
    ],
)  # fmt: skip
def test_syncpoint_writes_normal_into_eibresp_resp_and_resp2(text, call):
    """#4437 (left by #4411): RESP / RESP2 on SYNCPOINT [ROLLBACK] were accepted and never written, so a program
    testing `WS-CICS-RESP NOT = DFHRESP(NORMAL)` read what the previous command left there. In the region NORMAL is
    the only outcome (det.cics.OPTIONS says why); it is written as CICS writes it, and no condition is raised."""
    c = _RespCics()
    assert c.command(text, "") == [call, "OUTCOME(0, 0);"]
    (opts,) = c.outcomes
    assert "NOHANDLE" in opts  # NORMAL raises nothing: no HANDLE CONDITION dispatch
    assert ("RESP" in opts) == ("RESP(" in text) and ("RESP2" in opts) == ("RESP2(" in text)


def test_syncpoint_resp2_alone_is_written_too():
    assert _RespCics().command("SYNCPOINT ROLLBACK RESP2(R2)", "") == [
        "task.rollback();", "OUTCOME(0, 0);", "STORE(R2, BigDecimal.valueOf(0));"]  # fmt: skip


# A sample of each modelled command that accepts RESP; the commands this double cannot translate say why their RESP
# is written (or need not be).
_RESP_SAMPLES = {
    "ENQ": "ENQ RESOURCE(REC) LENGTH(10)", "DEQ": "DEQ RESOURCE(REC) LENGTH(10)", "DELAY": "DELAY FOR SECONDS(1)",
    "SEND TEXT": "SEND TEXT FROM(REC)", "XCTL": "XCTL PROGRAM('P')", "ASSIGN": "ASSIGN APPLID(REC)",
    "READ": "READ FILE('KSDS') INTO(REC) RIDFLD(KEY)", "READNEXT": "READNEXT FILE('KSDS') INTO(REC) RIDFLD(KEY)",
    "READPREV": "READPREV FILE('KSDS') INTO(REC) RIDFLD(KEY)", "STARTBR": "STARTBR FILE('KSDS') RIDFLD(KEY)",
    "ENDBR": "ENDBR FILE('KSDS')", "WRITE": "WRITE FILE('KSDS') FROM(REC) RIDFLD(KEY)",
    "REWRITE": "REWRITE FILE('KSDS') FROM(REC)", "DELETE": "DELETE FILE('KSDS') RIDFLD(KEY)",
    "INQUIRE PROGRAM": "INQUIRE PROGRAM('P')", "WRITEQ TD": "WRITEQ TD QUEUE('Q') FROM(REC)",
    "WRITEQ TS": "WRITEQ TS QUEUE('Q') FROM(REC)", "READQ TS": "READQ TS QUEUE('Q') INTO(REC)",
    "GET COUNTER": "GET COUNTER(KEY) VALUE(REC)", "SYNCPOINT": "SYNCPOINT", "SYNCPOINT ROLLBACK": "SYNCPOINT ROLLBACK",
}  # fmt: skip
_RESP_ELSEWHERE = {
    "RETURN": "control never comes back from a RETURN (OPTIONS)",
    "SEND MAP": "Cics.send_map ends in outcome() (screens: covered by the det ports' CICS proofs)",
    "RECEIVE MAP": "Cics.receive_map ends in outcome() (covered by the det ports' CICS proofs)",
    "LINK": "Cics.link ends in outcome() (covered by the CBSA / GenApp LINK proofs)",
}


@pytest.mark.parametrize("key", sorted(k for k, a in C.OPTIONS.items() if a is not None and "RESP" in a))
def test_every_command_that_accepts_resp_writes_it(key):
    """#4437: an accepted RESP is honoured. Accepting RESP and never writing it is a silent divergence."""
    if key in _RESP_ELSEWHERE:
        return
    assert key in _RESP_SAMPLES, f"{key} accepts RESP: add a sample, or say in _RESP_ELSEWHERE why it is written"
    c = _RespCics()
    out = c.command(f"{_RESP_SAMPLES[key]} RESP(R)", "")
    assert any("OUTCOME(" in line for line in out) and any("RESP" in o for o in c.outcomes), out


def _proc(body: list[str]):
    from gitgalaxy.tools.cobol_to_java.det.source import Line

    head = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. T.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
            "01 A PIC X.", "PROCEDURE DIVISION.", "P1."]  # fmt: skip
    return S.parse([Line(t, "t", k + 1) for k, t in enumerate(head + body)])


@pytest.mark.parametrize(
    "body",
    [
        ["    ENTRY 'DLITCBL' USING PAUTBPCB.", "    DISPLAY 'X'.", "    GOBACK."],  # DBUNLDGS: no statement kept
        ["    PERFORM P2 THRU.", "    GOBACK.", "P2.", "    EXIT."],  # GOBACK and P2 were dropped
        ["    CALL 'X' USING BY REFERENCE.", "    GOBACK."],
        ["    SET A TO.", "    GOBACK."],
    ],
)
def test_a_parse_error_outside_the_procedure_node_refuses_the_program(body):
    pytest.importorskip("tree_sitter_language_pack")
    with pytest.raises(E.ExprError, match="does not parse at line"):
        _proc(body)


def test_a_parse_error_inside_a_statement_is_a_hole():
    pytest.importorskip("tree_sitter_language_pack")
    proc = _proc(["    MOVE ALL TO A.", "    IF (A = 1 CONTINUE END-IF.", "    GOBACK."])
    kinds = [(s.kind, s.data.get("why")) for p in proc.paragraphs for s in S.walk(p.body)]
    assert kinds[0] == ("HOLE", "does not parse")  # MOVE ALL TO A: was a MOVE
    assert kinds[1] == ("IF", None) and proc.paragraphs[0].body[1].data["cond"][0] == "UNPARSED"
    assert kinds[-1] == ("GOBACK", None)


# ---- #4412: joined continuation lines re-wrapped to fixed form for the parser ---------------------------------
def _lines(texts: list[str]):
    from gitgalaxy.tools.cobol_to_java.det.source import Line

    return [Line(t, "t", k + 1) for k, t in enumerate(texts)]


def test_lines_within_column_72_reach_the_parser_byte_identical():
    from gitgalaxy.tools.cobol_to_java.det import source as SRC

    lines = _lines(["01 A PIC X(10) VALUE 'ABC'.", "X" * 65, "    MOVE A TO B."])
    text, rows = SRC.as_fixed_rows(lines)
    assert text == "".join(f"       {ln.text}\n" for ln in lines) and rows == [0, 1, 2]


def test_a_long_line_is_rewrapped_and_its_literal_joined_again():
    from gitgalaxy.tools.cobol_to_java.det import source as SRC

    lit = " FEATURE" + " " * 14 + "PASS  PARAGRAPH-NAME" + " " * 33 + "REMARKS" + "*" * 70
    line = f'    02 FILLER  PIC IS X({len(lit)})    VALUE IS "{lit}".'
    text, rows = SRC.as_fixed_rows(
        _lines([line, "    MOVE A TO B C D E F G H I J K L M N O P Q R S T U V W X Y Z AA BB"])
    )
    assert all(len(r) <= 72 for r in text.splitlines())
    assert len(rows) > 3 and set(rows[:-2]) == {0} and rows[-2:] == [1, 1]
    assert text.splitlines()[1].startswith('      -  "')  # '-' in column 7, the quote again in column 10
    assert SRC.unwrap(text).splitlines()[0][7:] == line


def test_a_rewrapped_value_literal_and_statement_literal_decode_verbatim():
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import layout as L

    v99 = " FEATURE              PASS  PARAGRAPH-NAME" + " " * 51 + "REMARKS"
    v65 = "*" * 65
    lines = _lines(["IDENTIFICATION DIVISION.", "PROGRAM-ID. T.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
                    "01 R.", f'    02 F1  PIC IS X(99)    VALUE IS "{v99}".', f'    02 F2 PIC X(65) VALUE "{v65}".',
                    "01 A PIC X(99).", "PROCEDURE DIVISION.", "P1.", f'    MOVE "{v99}" TO A.',
                    "    GOBACK."])  # fmt: skip
    rec = L.parse(lines)[0]
    assert [(c.name, c.values[0][1], c.line) for c in rec.children] == [("F1", v99, 6), ("F2", v65, 7)]
    proc = S.parse(lines)
    move, goback = proc.paragraphs[0].body
    assert move.data["from"] == E.Lit(v99) and move.line == 11 and goback.line == 12  # the row map keeps lines


_CCVS85 = Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", "/nonexistent")) / "data/cobol/che-che4z_nist_ccvs85"


@pytest.mark.skipif(not _CCVS85.is_dir(), reason="needs the language-crucible's NIST CCVS85 corpus")
def test_nist_ccvs85_parses_with_continuations_rewrapped():
    """#4412: with joined continuations run past column 72, 39 of the 150 NIST programs parsed (the #4378 bake-off);
    re-wrapped, 143 parse and 136 pass the translator's front end whole (the rest: DECLARATIVES, SEARCH ... WHEN)."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import source as SRC

    ok = 0
    progs = sorted(_CCVS85.glob("*.cbl"))
    for p in progs:
        try:
            lines = SRC.program_lines(p, [_CCVS85])
            L.parse(lines)
            proc = S.parse(lines)
        except Exception:  # noqa: BLE001 -- a refusal is a program that does not count
            continue
        ok += not any(s.kind == "HOLE" and s.data.get("why") == "does not parse"
                      for para in proc.paragraphs for s in S.walk(para.body))  # fmt: skip
    assert len(progs) == 150 and ok >= 130, ok


def test_missing_language_pack_names_the_translator_extra(monkeypatch):
    # tree-sitter-language-pack is the optional `translator` extra: without it both parsers say how to install it
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det.source import Line

    monkeypatch.setitem(sys.modules, "tree_sitter_language_pack", None)  # import raises ImportError
    monkeypatch.setattr(S, "_PARSER", None)
    for call in (L._parser, lambda: S.parse([Line("PROCEDURE DIVISION.", "x", 1)])):
        with pytest.raises(ImportError, match=r"pip install gitgalaxy\[translator\]"):
            call()
