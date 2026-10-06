"""det-port translator pieces that need no corpus: COBOL conditions and expressions (det/expr.py), statement parsing
(det/stmt.py) and EXEC CICS options (det/cics.py). Each case is a COBOL rule the proofs of the det ports depend on;
the ports themselves are proven by tests/tools/det_port.py against GnuCOBOL."""

from __future__ import annotations

import json
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


def test_cics_facades_run_the_program_in_the_region():
    """#4465: a det port keeps the generated stub's handleTransaction / handleLink for their callers, and each runs the
    program -- one task of it in the region, through runTask -- as the generator's own facades do (#4343), never a
    stub that does nothing or throws (#4342). Return values follow the stub's signature."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    stub = (
        "public class MenuService {\n"
        "    public CaDto handleTransaction(String transid, CaDto request) {\n"
        '        log.info("Menu: handleTransaction");\n'
        "        CicsTask.Region region = CicsTask.region();\n"
        "        CicsTask task = region.transaction(transid, request);\n"
        '        region.run(task, "COMEN01C", this::runTask);\n'
        "        return task.returned(CaDto.class);\n    }\n"
        "    public void runTask(CicsTask task) {\n    }\n"
        "    public CaDto handleLink(CaDto request) {\n"
        "        CicsTask.Region region = CicsTask.region();\n"
        '        CicsTask task = region.linked("COMEN01C", request);\n'
        '        region.run(task, "COMEN01C", this::runTask);\n'
        "        return request;\n    }\n}\n"
    )
    java = "\n".join(P.facades(stub))
    assert (
        "    public CaDto handleTransaction(String transid, CaDto request) {\n"
        "        CicsTask.Region region = CicsTask.region();\n"
        "        CicsTask task = region.transaction(transid, request);\n"
        '        region.run(task, "COMEN01C", this::runTask);\n'
        "        return task.returned(CaDto.class);\n    }"
    ) in java
    assert (
        "    public CaDto handleLink(CaDto request) {\n"
        "        CicsTask.Region region = CicsTask.region();\n"
        '        CicsTask task = region.linked("COMEN01C", request);\n'
        '        region.run(task, "COMEN01C", this::runTask);\n'
        "        return request;\n    }"
    ) in java
    assert "UnsupportedOperationException" not in java and "log." not in java

    # no COMMAREA: a void transaction started from a cleared screen, a LINK with none
    bare = (
        "    public void handleTransaction(String transid) {\n"
        '        region.run(task, "ABNDPROC", this::runTask);\n    }\n'
        "    public void handleLink() {\n    }\n"
    )
    java = "\n".join(P.facades(bare))
    assert "CicsTask task = region.transaction(transid, null);" in java
    assert 'CicsTask task = region.linked("ABNDPROC", null);' in java
    assert java.count('region.run(task, "ABNDPROC", this::runTask);') == 2 and "return" not in java

    # a channel program's handler (no region facade in the stub): the entry stops by name, it never returns as if run
    java = "\n".join(P.facades("    public void handleLink(ChanIn request) {\n    }\n"))
    assert "throw new UnsupportedOperationException" in java and "region" not in java


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
        # #4436: a keyed READ's LENGTH is modelled; READNEXT / READPREV's and an RBA browse's are not
        ("READNEXT FILE('KSDS') INTO(REC) RIDFLD(KEY) LENGTH(VARLEN)", "not INTO's length"),
        ("READPREV FILE('KSDS') INTO(REC) RIDFLD(KEY) LENGTH(10)", "not INTO's length"),
        ("READNEXT FILE('KSDS') INTO(REC) RIDFLD(RID) RBA LENGTH(VARLEN)", "not INTO's length"),
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


class _LenCics(_KeyCics):
    """#4436: LENGTH operands as Java ints, stores as STORE(name, value)."""

    def __init__(self):
        super().__init__()
        self.g.store_into = lambda ref, value, _rounded: f"STORE({ref.name}, {value});"

    def int_(self, text):
        return f"INT({text})"


def test_read_length_is_modelled_in_and_out():
    """#4436 (GenApp LGUCVS01 / LGUPVS01: LENGTH(WS-Commarea-Len), set from EIBCALEN): IBM, EXEC CICS READ -- LENGTH
    is "the length ... of the data area where the record is to be put. On completion ... the actual length of the
    record"; a longer record is truncated, LENGERR RESP2 11. DetCics.readInto moves the record and answers NORMAL or
    LENGERR; LENGTH is then set to the record's length. Refused at #4411 because it was accepted and ignored."""
    out = _LenCics().command("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) LENGTH(VARLEN) KEYLENGTH(10) RESP(R) UPDATE", "")
    assert out == [
        "byte[] rec2 = DetCics.bytes(f_KEY);",
        "CicsTask.FileRead<byte[]> read1 = task.readForUpdate('KSDS'.strip(), () -> store(F).find(rec2));",
        "int resp3 = read1.resp();",
        "int resp24 = read1.resp2();",
        "if (read1.record() != null) {",
        "    resp3 = DetCics.readInto(f_REC, read1.record(), INT(VARLEN), true);",
        "    resp24 = resp3 == 22 ? 11 : 0;",
        "    heldKey.put('KSDS'.strip(), rec2);",
        "    STORE(VARLEN, BigDecimal.valueOf(read1.record().length));",
        "}",
        "OUTCOME(resp3, resp24);",
    ]


def test_read_length_literal_is_the_limit_with_nothing_to_set_back():
    out = _LenCics().command("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) LENGTH(10) RESP(R)", "")
    assert "    resp3 = DetCics.readInto(f_REC, read1.record(), INT(10), false);" in out
    assert not any("STORE(" in line or "heldKey" in line for line in out)


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
    # #4413: terminal control (SEND CONTROL; RECEIVE (3270 logical), (LUTYPE2/LUTYPE3), z/OS Communications Server)
    "SEND CONTROL": "CURSOR FORMFEED ERASE DEFAULT ALTERNATE ERASEAUP PRINT FREEKB ALARM FRSET MSR OUTPARTN "
    "ACTPARTN LDC ACCUM TERMINAL SET PAGING WAIT LAST REQID HONEOM L40 L64 L80",
    "RECEIVE": "INTO SET LENGTH FLENGTH MAXLENGTH MAXFLENGTH NOTRUNCATE ASIS BUFFER CONVID SESSION PARTN LDC",
}


@pytest.mark.parametrize("verb", sorted(_IBM_OPTIONS))
def test_every_option_of_a_modelled_command_is_honoured_or_refused(verb):
    first = verb.split()[0]
    for opt in _IBM_OPTIONS[verb].split():
        words, opts = ([first] if verb.endswith("MAP") else verb.split()), {opt: "X"}
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


# ---- #4468 (after #4467, ownership per #4273): the translator takes each COPY's member from the engine --------------
from gitgalaxy.tools.cobol_to_java.det import source as SRC  # noqa: E402


def _fixed(*body: str) -> str:
    return "".join(f"       {b}\n" for b in body)


def _estate(tmp_path, program_body, files):
    """An estate: cbl/PROG.cbl and the given members; returns (program, root)."""
    root = tmp_path / "estate"
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    prog = root / "cbl" / "PROG.cbl"
    prog.parent.mkdir(parents=True, exist_ok=True)
    head = ("IDENTIFICATION DIVISION.", "PROGRAM-ID. PROG.", "DATA DIVISION.", "WORKING-STORAGE SECTION.")
    prog.write_text(_fixed(*head, *program_body), encoding="utf-8")
    return prog, root


def _engine(prog, root, deps, gaps=(), collisions=()):
    """deps: importer -> its resolved files (a list, or file -> library-names); members are (importer, member)."""
    return SRC.EngineCopies.of(prog, root, deps, gaps, collisions)


_MEMBER = _fixed("05 A-FIELD PIC X(4).")


def _from(lines, name):
    # posix before splitting: on Windows ln.file has backslashes
    return {Path(ln.file).as_posix().split("/estate/", 1)[1] for ln in lines if name in ln.text}


def test_copy_resolved_by_the_engine_translates(tmp_path):
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY AREC."], {"cpy/AREC.cpy": _MEMBER})
    lines = SRC.program_lines(prog, [root / "cpy"], _engine(prog, root, {"cbl/PROG.cbl": ["cpy/AREC.cpy"]}))
    assert _from(lines, "A-FIELD") == {"cpy/AREC.cpy"}


def test_a_member_in_two_libraries_is_taken_from_the_engines_library(tmp_path):
    """#4461 (estate-crucible H-0034: DATEWS in apps/PAYR/copybook and shared/copylib): the translator's first-hit
    search took the first directory's member; it now takes the library the engine resolved, whatever `dirs` says."""
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY DATEWS."],
                         {"payr/DATEWS.cpy": _MEMBER, "shared/DATEWS.cpy": _fixed("05 S-FIELD PIC X(4).")})  # fmt: skip
    eng = _engine(prog, root, {"cbl/PROG.cbl": ["shared/DATEWS.cpy"]})
    lines = SRC.program_lines(prog, [root / "payr", root / "shared"], eng)
    assert _from(lines, "S-FIELD") == {"shared/DATEWS.cpy"} and not _from(lines, "A-FIELD")


def test_copy_in_a_library_takes_that_librarys_member(tmp_path):
    """#4265 (estate-crucible PAYMAIN H-0034): `COPY DATEWS` and `COPY DATEWS IN SHRCPY` in one program reach two
    files; each COPY takes the one its own form resolved to."""
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY DATEWS.", "01 WS-B.", "COPY DATEWS IN SHRCPY."],
                         {"payr/DATEWS.cpy": _MEMBER, "shared/DATEWS.cpy": _fixed("05 S-FIELD PIC X(4).")})  # fmt: skip
    eng = _engine(prog, root, {"cbl/PROG.cbl": {"payr/DATEWS.cpy": [""], "shared/DATEWS.cpy": ["SHRCPY"]}})
    lines = SRC.program_lines(prog, [], eng)
    assert _from(lines, "A-FIELD") == {"payr/DATEWS.cpy"} and _from(lines, "S-FIELD") == {"shared/DATEWS.cpy"}


def test_several_files_the_engine_cannot_tell_apart_are_refused(tmp_path):
    prog, root = _estate(
        tmp_path, ["01 WS-A.", "COPY DATEWS."], {"payr/DATEWS.cpy": _MEMBER, "shared/DATEWS.cpy": _MEMBER}
    )
    eng = _engine(prog, root, {"cbl/PROG.cbl": ["payr/DATEWS.cpy", "shared/DATEWS.cpy"]})
    with pytest.raises(SRC.CopyUnresolved, match="COPY DATEWS: the engine resolved several files: payr/DATEWS.cpy, "
                       "shared/DATEWS.cpy"):  # fmt: skip
        SRC.program_lines(prog, [root / "payr"], eng)


def test_a_nested_copy_takes_the_engines_member_too(tmp_path):
    """A COPY inside a copybook resolves through that copybook's own edges."""
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY OUTER."],
                         {"cpy/OUTER.cpy": _fixed("05 O-FIELD PIC X.", "COPY INNER."), "cpy/INNER.cpy": _MEMBER,
                          "lib2/INNER.cpy": _fixed("05 L-FIELD PIC X.")})  # fmt: skip
    eng = _engine(prog, root, {"cbl/PROG.cbl": ["cpy/OUTER.cpy"], "cpy/OUTER.cpy": ["lib2/INNER.cpy"]})
    lines = SRC.program_lines(prog, [root / "cpy"], eng)
    assert _from(lines, "L-FIELD") == {"lib2/INNER.cpy"} and not _from(lines, "A-FIELD")


def test_a_program_source_spliced_in_for_a_copy_is_refused(tmp_path):
    """#4460 (estate-crucible SHPINQ `COPY SHPRATE.` -> the program SHPRATE.cbl): the engine resolved no member."""
    prog, root = _estate(tmp_path, ["01 WS-RATE-PARM.", "COPY SHPRATE."],
                         {"cbl/SHPRATE.cbl": _fixed("IDENTIFICATION DIVISION.", "PROGRAM-ID. SHPRATE.")})  # fmt: skip
    with pytest.raises(SRC.CopyUnresolved, match="COPY SHPRATE: the engine resolved nothing; the estate holds "
                       "cbl/SHPRATE.cbl"):  # fmt: skip
        SRC.program_lines(prog, [], _engine(prog, root, {"cbl/PROG.cbl": []}))


def test_a_copy_after_other_text_on_its_line_is_expanded(tmp_path):
    """#4459 (estate-crucible ACCTRPT): `01 WS-RPT-HEAD.  COPY RPTHDR.` left the record empty; two COPYs on one
    line both expand, and the text before the first stays."""
    prog, root = _estate(tmp_path, ["01 WS-RPT-HEAD.  COPY RPTHDR.", "01 WS-RPT-TOTALS.  COPY RPTTOT. COPY RPTCNT."],
                         {"cpy/RPTHDR.cpy": _MEMBER, "cpy/RPTTOT.cpy": _fixed("05 T-FIELD PIC X.", "05 T2 PIC X."),
                          "cpy/RPTCNT.cpy": _fixed("05 C-FIELD PIC X.")})  # fmt: skip
    deps = {"cbl/PROG.cbl": ["cpy/RPTHDR.cpy", "cpy/RPTTOT.cpy", "cpy/RPTCNT.cpy"]}
    lines = SRC.program_lines(prog, [root / "cpy"], _engine(prog, root, deps))
    texts = [ln.text.strip() for ln in lines]
    assert texts[4:] == ["01 WS-RPT-HEAD.", "05 A-FIELD PIC X(4).", "01 WS-RPT-TOTALS.", "05 T-FIELD PIC X.",
                         "05 T2 PIC X.", "05 C-FIELD PIC X."]  # fmt: skip


def test_a_copy_with_its_member_on_the_next_line_is_expanded(tmp_path):
    """#4459 (estate-crucible ACCTUPD): `COPY` / `UPDCTL.` left the record empty."""
    prog, root = _estate(tmp_path, ["01 WS-UPD-CONTROL.", "COPY", "RPTHDR."], {"cpy/RPTHDR.cpy": _MEMBER})
    lines = SRC.program_lines(prog, [root / "cpy"], _engine(prog, root, {"cbl/PROG.cbl": ["cpy/RPTHDR.cpy"]}))
    assert _from(lines, "A-FIELD") == {"cpy/RPTHDR.cpy"}


def test_copy_inside_a_literal_is_not_a_copy(tmp_path):
    prog, root = _estate(tmp_path, ["01 WS-A PIC X(9) VALUE 'COPY RPTHDR.'."], {"cpy/RPTHDR.cpy": _MEMBER})
    lines = SRC.program_lines(prog, [root / "cpy"], None)
    assert not _from(lines, "A-FIELD")


@pytest.mark.parametrize("engine", [False, True])
def test_a_copy_member_that_is_a_program_is_refused(tmp_path, engine):
    """#4460: a member with IDENTIFICATION DIVISION / PROGRAM-ID is a program; `.cbl` copy members stay allowed."""
    prog_text = _fixed("IDENTIFICATION DIVISION.", "PROGRAM-ID. SHPRATE.", "DATA DIVISION.")
    prog, root = _estate(tmp_path, ["01 WS-RATE-PARM.", "COPY SHPRATE."], {"cbl/SHPRATE.cbl": prog_text})
    eng = _engine(prog, root, {"cbl/PROG.cbl": ["cbl/SHPRATE.cbl"]}) if engine else None
    with pytest.raises(SRC.CopyNotFound, match="COPY SHPRATE.*is a program"):
        SRC.program_lines(prog, [root / "cbl"], eng)


def test_a_cbl_copy_member_that_is_not_a_program_still_expands(tmp_path):
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY AREC."], {"cbl/AREC.cbl": _MEMBER})
    lines = SRC.program_lines(prog, [root / "cbl"], None)
    assert _from(lines, "A-FIELD") == {"cbl/AREC.cbl"}


@pytest.mark.parametrize(("kw", "why"), [({"gaps": [("cbl/PROG.cbl", "AREC")]}, "gap"),
                                         ({"collisions": [("cbl/PROG.cbl", "AREC")]}, "collision")])  # fmt: skip
def test_a_member_the_engine_reports_as_a_gap_or_collision_is_refused(tmp_path, kw, why):
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY AREC."], {"cpy/AREC.cpy": _MEMBER})
    deps = {"cbl/PROG.cbl": [] if why == "gap" else ["cpy/AREC.cpy"]}
    with pytest.raises(SRC.CopyUnresolved, match=f"COPY AREC: the engine (records a {why})"):
        SRC.program_lines(prog, [root / "cpy"], _engine(prog, root, deps, **kw))


def test_a_system_member_outside_the_estate_needs_no_engine_resolution(tmp_path):
    """DFHAID / DFHEIBLK and symbolic maps generated from BMS live outside the estate: the engine has none of them,
    and reports DFHAID as a gap where the scan declared copy libraries (estate-crucible CUSTINQ)."""
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY DFHAID."], {})
    lines = SRC.program_lines(
        prog, [C.COPY], _engine(prog, root, {"cbl/PROG.cbl": []}, gaps=[("cbl/PROG.cbl", "DFHAID")])
    )
    assert len(lines) > 5


def test_engine_copies_from_the_port_ticket(tmp_path):
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY AREC."], {"cpy/AREC.cpy": _MEMBER})
    jobs = tmp_path / "project" / "ai_agent_jobs"
    jobs.mkdir(parents=True)
    ticket = {"source": {"program": {"file": "cbl/PROG.cbl"}, "copybooks": [{"file": "cpy/AREC.cpy"}]}}
    (jobs / "PROG_port_ticket.json").write_text(json.dumps(ticket), encoding="utf-8")
    eng = SRC.engine_copies_from_ticket(tmp_path / "project", prog)  # (a ticket from before #4468)
    assert eng is not None and eng.root == root and eng.resolved == {"AREC": (root / "cpy/AREC.cpy",)}
    assert SRC.engine_copies_from_ticket(tmp_path / "project", root / "cbl" / "OTHER.cbl") is None
    ticket["facts"] = {"program": {"copy_edges": {"cbl/PROG.cbl": {"cpy/AREC.cpy": ["SHRCPY"]}, "cpy/AREC.cpy": {}},
                                   "copy_gaps": [["cpy/AREC.cpy", "SQLCA"]], "copy_collisions": []}}  # fmt: skip
    (jobs / "PROG_port_ticket.json").write_text(json.dumps(ticket), encoding="utf-8")
    eng = SRC.engine_copies_from_ticket(tmp_path / "project", prog)
    assert eng.edges == {
        "cbl/PROG.cbl": {"AREC": ((root / "cpy/AREC.cpy", frozenset({"SHRCPY"})),)},
        "cpy/AREC.cpy": {},
    }
    assert eng.gaps == frozenset({("cpy/AREC.cpy", "SQLCA")})


def test_galaxy_ir_copy_resolution_walks_every_copybook_the_program_reaches():
    from types import SimpleNamespace as NS

    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import GalaxyIR

    files = {"cbl/P.cbl": NS(copy_deps=["cpy/A.cpy", "bms/M.bms#M"], copy_dep_libraries={"cpy/A.cpy": ["", "LIB"]}),
             "cpy/A.cpy": NS(copy_deps=["cpy/B.cpy"], copy_dep_libraries={}),
             "cpy/B.cpy": NS(copy_deps=[], copy_dep_libraries={}),
             "cbl/Q.cbl": NS(copy_deps=["cpy/C.cpy"], copy_dep_libraries={})}  # fmt: skip
    ir = NS(files=files, copy_member_gaps=[{"importer": "cpy/A.cpy", "member": "x"}, {"importer": "cbl/Q.cbl", "member": "Y"}],
            copy_member_collisions=None)  # fmt: skip
    assert GalaxyIR.copy_resolution(ir, "cbl/P.cbl") == {
        "edges": {"cbl/P.cbl": {"cpy/A.cpy": ["", "LIB"]}, "cpy/A.cpy": {"cpy/B.cpy": []}, "cpy/B.cpy": {}},
        "gaps": [["cpy/A.cpy", "X"]], "collisions": []}  # fmt: skip


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
    "SEND CONTROL": "SEND CONTROL ERASE", "RECEIVE": "RECEIVE INTO(REC)",
    "PUSH HANDLE": "PUSH HANDLE", "POP HANDLE": "POP HANDLE",
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


# ---- #4413: SEND CONTROL and terminal RECEIVE (no map) ---------------------------------------------------------------
class _TermCics(_LenCics):
    """LS-REC a LINKAGE 01 record, WS-REC a WORKING-STORAGE one; INTO / SET targets as f_<name>."""

    def __init__(self):
        super().__init__()
        from gitgalaxy.tools.cobol_to_java.det import layout as L

        items = {"LS-REC": L.Item(1, "LS-REC", "LINKAGE"), "WS-REC": L.Item(1, "WS-REC", "WORKING-STORAGE"),
                 "LS-PART": L.Item(5, "LS-PART", "LINKAGE")}  # fmt: skip
        self.g.resolve = lambda ref: items[ref.name]

    def ref(self, text):
        return E.Ref(text.strip())


def test_send_control_records_its_options_and_cursor():
    """IBM, EXEC CICS SEND CONTROL ("sends device controls to a terminal"): CBSA's BNK1* send ERASE FREEKB before a
    RETURN. CURSOR(n) is the offset "relative to zero"; no condition IBM lists arises on a plain terminal."""
    c = _TermCics()
    assert c.command("SEND CONTROL ERASE FREEKB", "") == [
        'task.sendControl(null, "ERASE", "FREEKB");',
        "OUTCOME(0, 0);",
    ]
    assert c.command("SEND CONTROL CURSOR(CPOS) ALARM FRSET ERASEAUP RESP(R)", "") == [
        'task.sendControl(INT(CPOS), "ALARM", "CURSOR", "ERASEAUP", "FRSET");', "OUTCOME(0, 0);"]  # fmt: skip
    for bad, why in (("SEND CONTROL CURSOR", "without a value"), ("SEND CONTROL ERASE PRINT", "PRINT: option not"),
                     ("SEND CONTROL ACCUM PAGING", "option not modelled")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")


def test_receive_into_length_is_in_out_with_its_conditions():
    """IBM, EXEC CICS RECEIVE: with INTO and no MAXLENGTH, LENGTH "specifies the maximum length that the program
    accepts"; "When the data has been received, the data area is set to the length of the data" (LENGERR: "the
    original length of data"). GenApp LGSETUP / LGSTSQ / LGICVS01 / LGIPVS01: INTO LENGTH RESP."""
    out = _TermCics().command("RECEIVE INTO(WS-REC) LENGTH(RLEN) RESP(R)", "")
    assert out == [
        "CicsTask.Received received1 = task.receive(INT(RLEN), false);",
        "DetCics.received(f_WS-REC, received1.data(), CS);",
        "STORE(RLEN, BigDecimal.valueOf(received1.length()));",
        "OUTCOME(DetCics.resp(received1.resp()), 0);",
    ]
    # no LENGTH: INTO's length is the limit, nothing set back; a literal LENGTH is the limit only
    out = _TermCics().command("RECEIVE INTO(REC)", "")
    assert out[0] == "CicsTask.Received received1 = task.receive(56, false);" and not any("STORE" in x for x in out)
    out = _TermCics().command("RECEIVE INTO(REC) LENGTH(20)", "")
    assert out[0] == "CicsTask.Received received1 = task.receive(INT(20), false);" and not any(
        "STORE" in x for x in out
    )
    # MAXLENGTH overrides LENGTH as the limit; NOTRUNCATE keeps the rest (also when it comes first)
    for text in (
        "RECEIVE INTO(REC) LENGTH(RLEN) MAXLENGTH(10) NOTRUNCATE",
        "RECEIVE NOTRUNCATE INTO(REC) FLENGTH(RLEN) MAXFLENGTH(10)",
    ):
        out = _TermCics().command(text, "")
        assert out[0] == "CicsTask.Received received1 = task.receive(INT(10), true);"
        assert out[2] == "STORE(RLEN, BigDecimal.valueOf(received1.length()));"


def test_receive_set_addresses_a_linkage_record_and_the_rest_is_refused():
    out = _TermCics().command("RECEIVE SET(ADDRESS OF LS-REC) LENGTH(RLEN) MAXLENGTH(80)", "")
    assert out[:3] == ["CicsTask.Received received1 = task.receive(INT(80), false);",
                       "DetCics.receivedSet(f_LS-REC, received1.data(), CS);",
                       "STORE(RLEN, BigDecimal.valueOf(received1.length()));"]  # fmt: skip
    for bad, why in (
        ("RECEIVE SET(PTR) LENGTH(RLEN) MAXLENGTH(80)", "pointers are not modelled"),
        ("RECEIVE SET(ADDRESS OF WS-REC) LENGTH(RLEN) MAXLENGTH(80)", "not a LINKAGE 01"),
        ("RECEIVE SET(ADDRESS OF LS-PART) LENGTH(RLEN) MAXLENGTH(80)", "not a LINKAGE 01"),
        ("RECEIVE SET(ADDRESS OF LS-REC) LENGTH(RLEN)", "without MAXLENGTH"),
        ("RECEIVE SET(ADDRESS OF LS-REC) MAXLENGTH(80)", "without LENGTH"),
        ("RECEIVE LENGTH(RLEN)", "one of INTO / SET"),
        ("RECEIVE INTO(REC) SET(ADDRESS OF LS-REC) LENGTH(RLEN)", "one of INTO / SET"),
        ("RECEIVE INTO(REC) LENGTH(RLEN) FLENGTH(RLEN)", "together"),
        ("RECEIVE INTO(REC) ASIS", "ASIS: option not modelled"),
        ("RECEIVE INTO(REC) BUFFER", "BUFFER: option not modelled"),
    ):
        with pytest.raises(C.CicsError, match=why):
            _TermCics().command(bad, "")


def test_eoc_is_ignored_by_default_and_handled_like_any_condition():
    """IBM, RECEIVE (LUTYPE2/LUTYPE3): EOC (RESP 6), "Default action: ignore the condition". The program's
    condition() goes on (-1) for it when no HANDLE CONDITION names it; DetCics knows its RESP value."""
    import re

    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = Path(P.__file__).read_text(encoding="utf-8")
    body = src[src.index("private int condition(String cond)") :]
    assert (
        body.index("handlers.get(cond)") < body.index("DetCics.ignoredByDefault(cond)") < body.index("abendOnCondition")
    )
    rt = (Path(C.__file__).parent / "cobolrt/cics/DetCics.java").read_text(encoding="utf-8")
    assert 'case 6 -> "EOC";' in rt and 'case "EOC" -> 6;' in rt
    assert re.search(r'ignoredByDefault\(String condition\) \{\s*return "EOC"\.equals\(condition\);', rt)


def test_a_terminal_only_cics_program_translates_whole_and_imports_only_packages_that_exist(tmp_path):
    """#4413: CBSA's BNK1* SEND CONTROL ERASE FREEKB and GenApp's RECEIVE INTO LENGTH translate with no hole; an estate
    with no screens, contracts or repositories (a terminal-only program) gets no import of those packages, which
    javac refuses when they do not exist."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "T1.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. T1.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n       01  WS-IN                 PIC X(10) VALUE SPACES.\n"
        "       01  WS-LEN                PIC S9(4) COMP VALUE 10.\n       PROCEDURE DIVISION.\n"
        "           EXEC CICS SEND CONTROL ERASE FREEKB END-EXEC\n"
        "           EXEC CICS RECEIVE INTO(WS-IN) LENGTH(WS-LEN) END-EXEC\n           EXEC CICS RETURN END-EXEC.\n",
        encoding="utf-8",
    )
    vsam = tmp_path / "proj/src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class T1Service {\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    r = P.translate(tmp_path / "T1.cbl", [], stub, "com.x", {}, tmp_path / "proj")
    assert (r.stats["statements"], r.stats["translated"], r.stats["holes"]) == (3, 3, [])
    assert [x for x in r.java.splitlines() if x.startswith("import com.x.") and "*" in x] == [
        "import com.x.entity.vsam.*;"]  # fmt: skip
    assert 'task.sendControl(null, "ERASE", "FREEKB");' in r.java and "task.receive(" in r.java


# ---- #4414 / #4502: IGNORE CONDITION, HANDLE AID, PUSH / POP HANDLE, HANDLE CONDITION ERROR ---------------------------
class _HandleCics(_TermCics):
    """Paragraphs GOT-PF7 (3), GOT-ANY (4), GOT-ERR (5); a transfer as GOTO(to)."""

    def __init__(self, handle_aid=False):
        super().__init__()
        self.g.para_index = {"GOT-PF7": 3, "GOT-ANY": 4, "GOT-ERR": 5}
        self.g.jump = lambda target: f"GOTO({target});"
        self.handle_aid = handle_aid


def test_ignore_condition_marks_each_condition_ignored_and_refuses_what_ibm_does_not_document():
    """IBM, EXEC CICS IGNORE CONDITION: "no action is taken if a condition occurs ... control returns to the
    instruction following the command"; the last HANDLE or IGNORE for a condition wins (both share `handlers`, -1 for
    IGNORE, which condition() returns as "go on"). IGNORE CONDITION ERROR is refused: whether ERROR's action can be to
    ignore is not documented (oracle_assumptions X16)."""
    c = _HandleCics()
    assert c.command("IGNORE CONDITION LENGERR MAPFAIL", "") == [
        'handlers.put("LENGERR", -1);', 'handlers.put("MAPFAIL", -1);']  # fmt: skip
    assert c.command("HANDLE CONDITION ERROR(GOT-ERR) LENGERR", "") == [
        'handlers.put("ERROR", 5);', 'handlers.remove("LENGERR");']  # fmt: skip
    for bad, why in (("IGNORE CONDITION ERROR", "IGNORE CONDITION ERROR"),
                     ("IGNORE CONDITION LENGERR(GOT-ERR)", "names no label"),
                     ("IGNORE CONDITION NOSUCH", "not a documented condition"),
                     ("HANDLE CONDITION NOSUCH(GOT-ERR)", "not a documented condition"),
                     ("IGNORE CONDITION NORMAL", "not a documented condition")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")


def test_handle_aid_records_each_keys_label_or_deactivates_it():
    """IBM, EXEC CICS HANDLE AID: a key's label; "To ignore an AID, issue a HANDLE AID command that specifies the
    associated option without a label" (-1: deactivated, told from never handled by DetCics.aidLabel)."""
    c = _HandleCics()
    assert c.command("HANDLE AID PF7(GOT-PF7) ANYKEY(GOT-ANY) CLEAR", "") == [
        'aids.put("PF7", 3);', 'aids.put("ANYKEY", 4);', 'aids.put("CLEAR", -1);']  # fmt: skip
    for bad, why in (("HANDLE AID PF25(GOT-PF7)", "not an attention key"),
                     ("HANDLE AID PF7(NOWHERE)", "no such paragraph"),
                     ("HANDLE AID PF7(GOT-PF7) RESP(R)", "RESP: not an attention key")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")


def test_push_and_pop_handle_stack_the_programs_handlers_and_the_tasks_abend_exit():
    """IBM, EXEC CICS PUSH HANDLE suspends "the current effect of the IGNORE CONDITION, HANDLE ABEND, HANDLE AID, and
    HANDLE CONDITION commands"; POP HANDLE restores them, INVREQ when nothing was pushed ("no matching PUSH HANDLE
    command has been executed at the current link level"), through RESP / HANDLE CONDITION like any condition."""
    c = _HandleCics()
    assert c.command("PUSH HANDLE", "") == [
        "pushed.push(new DetCics.Handlers(handlers, aids));", "handlers.clear();", "aids.clear();",
        "int resp1 = DetCics.resp(task.pushHandle());", "OUTCOME(resp1, 0);"]  # fmt: skip
    assert c.command("POP HANDLE RESP(R)", "") == [
        "int resp2 = DetCics.resp(task.popHandle());", "if (resp2 == 0) {",
        "    pushed.pop().restore(handlers, aids);", "}", "OUTCOME(resp2, 0);"]  # fmt: skip


def test_an_input_command_takes_the_aid_label_after_its_outcome_unless_resp_or_nohandle():
    """IBM, HANDLE AID: "Control is passed after the input command is completed" -- the data moved and LENGTH set,
    then the outcome, then the key's label (aid()). The same aid() before the outcome refuses a label that applies
    while the command raised a condition (which comes first is not documented). RESP / NOHANDLE: none of it (IBM,
    RESP: "NOHANDLE overrides both the HANDLE AID and the HANDLE CONDITION command"). A program with no HANDLE AID
    gets no aid() at all."""
    out = _HandleCics(handle_aid=True).command("RECEIVE INTO(WS-REC) LENGTH(RLEN)", "")
    assert out[1:] == [
        "DetCics.received(f_WS-REC, received1.data(), CS);",
        "STORE(RLEN, BigDecimal.valueOf(received1.length()));",
        "aid(DetCics.resp(received1.resp()));",
        "OUTCOME(DetCics.resp(received1.resp()), 0);",
        "int aidTo2 = aid(DetCics.resp(received1.resp()));",
        "if (aidTo2 >= 0) GOTO(aidTo2);",
    ]
    for text in ("RECEIVE INTO(WS-REC) LENGTH(RLEN) RESP(R)", "RECEIVE INTO(WS-REC) LENGTH(RLEN) NOHANDLE"):
        assert not any("aid(" in x for x in _HandleCics(handle_aid=True).command(text, ""))
    assert not any("aid(" in x for x in _HandleCics().command("RECEIVE INTO(WS-REC) LENGTH(RLEN)", ""))


def test_condition_takes_the_error_label_only_for_a_condition_whose_default_is_an_abend():
    """#4502, IBM HANDLE CONDITION: "if the default action for such a condition terminates the task abnormally, and
    the condition ERROR has been specified, the action for ERROR is taken". condition(): the condition's own HANDLE /
    IGNORE, then a default of ignore (EOC), then ERROR's label, then the abend. DetCics.aidLabel: the key's label,
    else ANYKEY's for a PA / PF key or CLEAR (not ENTER); a deactivated key under an ANYKEY label is refused."""
    import re

    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = Path(P.__file__).read_text(encoding="utf-8")
    body = src[src.index("private int condition(String cond)") :]
    order = [body.index(x) for x in ("handlers.get(cond)", "DetCics.ignoredByDefault(cond)",
                                     'handlers.get("ERROR")', "task.abendOnCondition(cond)")]  # fmt: skip
    assert order == sorted(order)
    rt = (Path(C.__file__).parent / "cobolrt/cics/DetCics.java").read_text(encoding="utf-8")
    m = re.search(r"public static Integer aidLabel\(.*?\n    \}\n", rt, re.S)
    assert m and '"CLEAR".equals(key)' in m.group(0) and "ENTER" not in m.group(0).split("{", 1)[1]
    assert "ANYKEY takes the key is not documented" in m.group(0)
    assert "public record Handlers(" in rt and "public void restore(" in rt


def test_a_program_with_handle_aid_ignore_and_push_pop_translates_whole(tmp_path):
    """#4414: HANDLE AID, IGNORE CONDITION, PUSH / POP HANDLE and HANDLE CONDITION ERROR translate with no hole; the
    port declares the AID map and the PUSH HANDLE stack it uses, and clears them for each task."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "T2.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. T2.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n       01  WS-IN                 PIC X(10) VALUE SPACES.\n"
        "       01  WS-LEN                PIC S9(4) COMP VALUE 10.\n       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           EXEC CICS HANDLE AID PF7(GOT-KEY) ANYKEY(GOT-KEY) END-EXEC\n"
        "           EXEC CICS HANDLE CONDITION ERROR(GOT-KEY) END-EXEC\n"
        "           EXEC CICS IGNORE CONDITION LENGERR END-EXEC\n"
        "           EXEC CICS PUSH HANDLE END-EXEC\n           EXEC CICS POP HANDLE END-EXEC\n"
        "           EXEC CICS RECEIVE INTO(WS-IN) LENGTH(WS-LEN) END-EXEC.\n"
        "       GOT-KEY.\n           EXEC CICS RETURN END-EXEC.\n",
        encoding="utf-8",
    )
    (tmp_path / "proj/src/main/java/com/x").mkdir(parents=True)
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class T2Service {\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    r = P.translate(tmp_path / "T2.cbl", [], stub, "com.x", {}, tmp_path / "proj")
    assert (r.stats["statements"], r.stats["translated"], r.stats["holes"]) == (7, 7, [])
    for line in ("private final java.util.Map<String, Integer> aids", "java.util.ArrayDeque<DetCics.Handlers> pushed",
                 "private int aid(int resp)", "aids.clear();", "pushed.clear();", 'handlers.put("LENGERR", -1);'):  # fmt: skip
        assert line in r.java, line


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


# ---- #4523: a continued literal in either quote style ----------------------------------------------------------
def _fixed_rows(rows: list[str]) -> list[str]:
    """Fixed-format source rows: `-` first is a continuation row (indicator column 7), else code from column 8."""
    return [("      " + r) if r.startswith("-") else ("       " + r) for r in rows]


def _continued(q: str, head: str, tail: str, cont_col: int) -> list[str]:
    """`01 F PIC X(n) VALUE <q>head...` run to column 72, its continuation's quote in column `cont_col`."""
    first = f"01 F PIC X({len(head) + len(tail)}) VALUE {q}"
    first = (first + head)[:65]
    return [first, "-" + " " * (cont_col - 8) + q + tail + q + "."]


def _value_and_move(raw_data: list[str], raw_proc: list[str]):
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import source as SRC

    raw = _fixed_rows(["IDENTIFICATION DIVISION.", "PROGRAM-ID. T.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
                  *raw_data, "01 A PIC X(200).", "PROCEDURE DIVISION.", "P1.", *raw_proc, "    GOBACK."])  # fmt: skip
    lines = SRC.logical_lines(raw, "t")
    rec = L.parse(lines)[0]
    proc = S.parse(lines)
    return rec.values[0][1], proc.paragraphs[0].body


@pytest.mark.parametrize("q", ["'", '"'])
@pytest.mark.parametrize("cont_col", [12, 20])  # the continuation's quote in Area B (column 12 on)
def test_a_continued_literal_parses_in_either_quote_style(q, cont_col):
    pytest.importorskip("tree_sitter_language_pack")
    head = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    raw_data = _continued(q, head, "TAIL-END", cont_col)
    want = (raw_data[0][raw_data[0].index(q) + 1 :]).ljust(65 - raw_data[0].index(q) - 1) + "TAIL-END"
    move = [f"    MOVE {q}{'M' * 50}", "-" + " " * (cont_col - 8) + f"{q}MORE{q} TO A."]
    move[0] = move[0].ljust(65)
    value, body = _value_and_move(raw_data, move)
    assert value == want
    assert body[0].kind == "MOVE" and body[0].data["from"] == E.Lit(
        "M" * 50 + " " * (65 - len(move[0].rstrip())) + "MORE"
    )


@pytest.mark.parametrize("q", ["'", '"'])
def test_a_continued_literal_keeps_a_doubled_quote_and_the_other_quote(q):
    pytest.importorskip("tree_sitter_language_pack")
    other = '"' if q == "'" else "'"
    head = f"IT{q}{q}S A {other}QUOTED{other} WORD AND MORE TEXT TO REACH COLUMN SEVENTY-TWO"
    raw_data = _continued(q, head, f"END{q}{q}X", 12)
    value, _ = _value_and_move(raw_data, [])
    text = raw_data[0][raw_data[0].index(q) + 1 :].ljust(65 - raw_data[0].index(q) - 1) + f"END{q}{q}X"
    assert value == text.replace(q * 2, q) and f"IT{q}S A {other}QUOTED{other}" in value


@pytest.mark.parametrize("q", ["'", '"'])
def test_a_doubled_quote_at_column_72_of_a_rewrapped_row_stays_together(q):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import source as SRC

    lead = f"01 F PIC X(90) VALUE {q}"
    lit = "A" * (65 - len(lead) - 1) + q * 2 + "B" * 40  # the pair in columns 72-73 of one long joined line
    lines = _lines(["IDENTIFICATION DIVISION.", "PROGRAM-ID. T.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
                    lead + lit + q + ".", "PROCEDURE DIVISION.", "    GOBACK."])  # fmt: skip
    text, _ = SRC.as_fixed_rows(lines)
    assert all(len(r) <= 72 for r in text.splitlines())
    assert L.parse(lines)[0].values[0][1] == lit.replace(q * 2, q)


def test_a_doubled_quotation_mark_is_one_literal_in_a_value_and_a_statement():
    # the grammar had split VALUE "IT""S" into two values ("IT", "S") and refused MOVE "IT""S"
    pytest.importorskip("tree_sitter_language_pack")
    value, body = _value_and_move(['01 F PIC X(4) VALUE "IT""S".'], ['    MOVE "IT""S" TO A.'])
    assert value == 'IT"S' and body[0].data["from"] == E.Lit('IT"S')


def test_the_doubled_quotation_mark_stand_in_is_refused_by_name_in_the_source():
    from gitgalaxy.tools.cobol_to_java.det import source as SRC

    assert "U+001E" in SRC.unmodelled(_lines([f"    MOVE 'A{SRC.QQ}B' TO A."]))


def test_an_exec_sql_line_keeps_its_apostrophes_when_rewrapped():
    from gitgalaxy.tools.cobol_to_java.det import source as SRC

    sql = "    EXEC SQL SELECT A INTO :A FROM T WHERE B = '" + "X" * 60 + "' END-EXEC."
    text, _ = SRC.as_fixed_rows(_lines([sql, "    DISPLAY '" + "Y" * 70 + "'."]))
    joined = SRC.unwrap(text).splitlines()
    assert joined[0][7:] == sql and joined[1][7:] == '    DISPLAY "' + "Y" * 70 + '".'


def test_a_hex_literal_on_a_rewrapped_line_keeps_its_value():
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import layout as L

    def value(v: str):
        return L.parse(_lines(["IDENTIFICATION DIVISION.", "PROGRAM-ID. T.", "DATA DIVISION.",
                               "WORKING-STORAGE SECTION.", f"01 F PIC X(2) VALUE {v}.", "PROCEDURE DIVISION.",
                               "    GOBACK."]))[0].values  # fmt: skip

    # past column 72 (the line is re-wrapped, its apostrophe literals written in quotation marks)
    assert value("X'C1C2'" + " " * 60 + "") == value("X'C1C2'") == [("hex", b"\xc1\xc2")]


# ---- #4462: PROGRAM-ID without its period (estate-crucible LOAN LNCALC) ------------------------------------------
@pytest.mark.parametrize("header", ["PROGRAM-ID LNCALC.", "PROGRAM-ID   LNCALC IS INITIAL.", "PROGRAM-ID. LNCALC."])
def test_program_id_without_its_period_parses(header):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import source as SRC

    raw = _fixed_rows(["IDENTIFICATION DIVISION.", header, "AUTHOR.       LOAN SYSTEMS.", "DATA DIVISION.",
                  "WORKING-STORAGE SECTION.", "01  WS-RATE PIC S9(3)V9(8) COMP-3.", "PROCEDURE DIVISION.",
                  "    GOBACK."])  # fmt: skip
    lines = SRC.logical_lines(raw, "t")
    assert lines[1].text.startswith("PROGRAM-ID.") and lines[1].text.split()[1].rstrip(".") == "LNCALC"
    assert [r.name for r in L.parse(lines)] == ["WS-RATE"]


def test_missing_language_pack_names_the_translator_extra(monkeypatch):
    # tree-sitter-language-pack is the optional `translator` extra: without it both parsers say how to install it
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det.source import Line

    monkeypatch.setitem(sys.modules, "tree_sitter_language_pack", None)  # import raises ImportError
    monkeypatch.setattr(S, "_PARSER", None)
    for call in (L._parser, lambda: S.parse([Line("PROCEDURE DIVISION.", "x", 1)])):
        with pytest.raises(ImportError, match=r"pip install gitgalaxy\[translator\]"):
            call()
