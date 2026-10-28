"""det-port translator pieces that need no corpus: COBOL conditions and expressions (det/expr.py), statement parsing
(det/stmt.py) and EXEC CICS options (det/cics.py). Each case is a COBOL rule the proofs of the det ports depend on;
the ports themselves are proven by tests/tools/det_port.py against GnuCOBOL."""

from __future__ import annotations

import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_conditions as CN  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_faults as CFL  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_containers as CC  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_filecontrol as CF  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_taskcontrol as CT  # noqa: E402
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


def test_perform_test_after_varying_runs_the_body_before_the_test():
    """#5945: PERFORM WITH TEST AFTER VARYING ... UNTIL tests after the body (the step only while the test is false)."""
    for text, after in (("PERFORM TEST AFTER VARYING I FROM 1 BY 1 UNTIL I > 3", True),
                        ("PERFORM P1 VARYING I FROM 1 BY 1 UNTIL I > 3", False)):  # fmt: skip
        s = S._statement(text, 1)
        assert s.data["test_after"] is after and s.data["varying"] is not None


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

    # #4270: a COMMAREA program that also reads a channel (GenApp's LGASTAT1) has a handleChannel its controller
    # calls: kept (the port compiles), stopping by name; the COMMAREA facade still runs the program
    both = stub.replace("}\n", "    public void handleChannel(Lgastat1ChannelIn request) {\n    }\n}\n", 1)
    java = "\n".join(P.facades(both))
    assert (
        "    public void handleChannel(Lgastat1ChannelIn request) {\n        throw new UnsupportedOperationException("
        in java
    )
    assert 'region.run(task, "COMEN01C", this::runTask);' in java


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

    def file_name(self, text):
        return f"{text}.stripTrailing()"

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
        "int resp1 = task.startbrRba('EPSMORTF'.stripTrailing(), CicsTask.rba(DetCics.bytes(f_RID, 4)));",
        "OUTCOME(resp1, task.resp2());",
    ]
    assert c.command("READNEXT FILE('EPSMORTF') INTO(REC) RIDFLD(RID) RBA RESP(R)", "") == [
        "CicsTask.BrowsedRba read2 = task.readnextRba('EPSMORTF'.stripTrailing(), CicsTask.rba(DetCics.bytes(f_RID, 4)), 56);",
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


def test_handle_abend_program_is_refused_by_name_with_its_reason():
    """#4270 (X67): PROGRAM is refused by the spec's reason, not by a bare option name."""
    with pytest.raises(C.CicsError, match=r"HANDLE ABEND PROGRAM: option not modelled \(PROGRAM: an abend exit"):
        _KeyCics().command("HANDLE ABEND PROGRAM('P')", "")


@pytest.mark.parametrize(
    "text",
    [
        "RETURN IMMEDIATE",  # #4270 (X27): IMMEDIATE without TRANSID: IBM does not say what it attaches
        "READNEXT FILE('KSDS') INTO(REC) RIDFLD(KEY) UPDATE TOKEN(R)",  # #5078: READ TOKEN honoured, a browse for update (RLS) not
        "STARTBR FILE('KSDS') RIDFLD(KEY) GENERIC KEYLENGTH(6)",
        "STARTBR FILE('KSDS') RIDFLD(KEY) REQID(2)",
        "READNEXT FILE('KSDS') INTO(REC) RIDFLD(KEY) REQID(2)",
        "ENDBR FILE('KSDS') REQID(2)",
        "LINK PROGRAM('P') COMMAREA(REC) DATALENGTH(KEY)",
        "ASSIGN OPID(REC)",
        "ASSIGN NETNAME(REC) APPLID(REC)",
        "FORMATTIME ABSTIME(REC) YYYYMMDD(REC) DATE(KEY)",  # #4415 slice 3 (X46): the DATFORM order is the installation's
        "ASKTIME ABSTIME(REC) RESP(R)",
        "WRITEQ QUEUE('Q') FROM(REC) TD",  # a TD option after the verb is not TS
        "SEND TEXT FROM(REC) CURSOR(KEY)",
        "HANDLE ABEND LABEL(X) RESP(R)",
        "HANDLE ABEND PROGRAM('P')",
        "INQUIRE PROGRAM('P') CEDFSTATUS(REC)",  # #4768: STATUS honoured (X34), every other attribute refused
    ],
)
def test_an_option_the_translation_would_ignore_is_refused_by_name(text):
    with pytest.raises(C.CicsError, match="not modelled"):
        _KeyCics().command(text, "")


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(VARLEN)", "not a known length on a known file"),
        ("READ FILE(WS-FILE) INTO(REC) RIDFLD(KEY) KEYLENGTH(6)", "not a known length on a known file"),
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

    def long_(self, text):
        return f"LONG({text})"


def test_read_length_is_modelled_in_and_out():
    """#4436 (GenApp LGUCVS01 / LGUPVS01: LENGTH(WS-Commarea-Len), set from EIBCALEN): IBM, EXEC CICS READ -- LENGTH
    is "the length ... of the data area where the record is to be put. On completion ... the actual length of the
    record"; a longer record is truncated, LENGERR RESP2 11. DetCics.readInto moves the record and answers NORMAL or
    LENGERR; LENGTH is then set to the record's length. Refused at #4411 because it was accepted and ignored."""
    out = _LenCics().command("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) LENGTH(VARLEN) KEYLENGTH(10) RESP(R) UPDATE", "")
    assert out == [
        "byte[] rec2 = DetCics.bytes(f_KEY);",
        "CicsTask.FileRead<byte[]> read1 = task.readForUpdate('KSDS'.stripTrailing(), () -> store(F).find(rec2));",
        "int resp3 = read1.resp();",
        "int resp24 = read1.resp2();",
        "if (read1.record() != null) {",
        "    resp3 = DetCics.readInto(f_REC, read1.record(), INT(VARLEN), true);",
        "    resp24 = resp3 == 22 ? 11 : 0;",
        "    heldKey.put('KSDS'.stripTrailing(), rec2);",
        "    STORE(VARLEN, BigDecimal.valueOf(read1.record().length));",
        "}",
        "OUTCOME(resp3, resp24);",
    ]


# ---- #4270: READ GTEQ / GENERIC (GenApp LGICVS01, LGIPVS01; oracle_assumptions.md X22) ------------------------
def test_read_gteq_searches_the_first_key_not_below_ridfld():
    """IBM, EXEC CICS READ: GTEQ -- "if the search for a record that has the same key (complete or generic) as that
    specified in the RIDFLD option is unsuccessful, the first record that has a greater key is retrieved"; NOTFND
    RESP2 80 when none is (CicsTask.readSearch). RIDFLD is not updated (IBM says so for READNEXT / READPREV only)."""
    out = _LenCics().command("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(10) GTEQ RESP(R)", "")
    assert out == [
        "byte[] rec2 = DetCics.bytes(f_KEY);",
        "CicsTask.FileRead<byte[]> read1 = task.readSearch('KSDS'.stripTrailing(), false, () -> store(F).search(rec2, 10, true));",
        "if (read1.record() != null) {",
        "    DetCics.put(f_REC, read1.record());",
        "}",
        "OUTCOME(read1.resp(), read1.resp2());",
    ]


def test_read_generic_gteq_update_holds_the_record_found():
    """GENERIC: "the search key is a generic key whose length is specified in the KEYLENGTH option" (6 of the 10-byte
    key); READ UPDATE holds the record the search found, not RIDFLD's key."""
    out = _LenCics().command(
        "READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(6) GENERIC GTEQ LENGTH(VARLEN) UPDATE RESP(R)", ""
    )
    assert (
        "CicsTask.FileRead<byte[]> read1 = task.readSearch('KSDS'.stripTrailing(), true, () -> store(F).search(rec2, 6, true));"
        in out
    )
    assert "    heldKey.put('KSDS'.stripTrailing(), store(F).keyOf(read1.record()));" in out
    assert "    resp3 = DetCics.readInto(f_REC, read1.record(), INT(VARLEN), true);" in out
    plain = _LenCics().command("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(6) GENERIC RESP(R)", "")
    assert "() -> store(F).search(rec2, 6, false));" in plain[1]  # GENERIC alone: EQUAL on the generic key


def test_read_gteq_on_a_file_named_at_run_time_takes_that_files_key():
    """#4771 zECS (FILE(ZF-FCT): ZC##FILE, the table's own file, named at run time): GTEQ on the full key searches with
    the key length of the store the name picks then; a name the project stores no file for is a Hole then, and a
    RIDFLD shorter than that key is refused then (X6) -- as for a file named by a literal, only later."""
    out = _LenCics().command("READ FILE(WS-FILE) INTO(REC) RIDFLD(KEY) GTEQ LENGTH(VARLEN) RESP(R)", "")
    assert out[1] == (
        "CicsTask.FileRead<byte[]> read1 = task.readSearch(WS-FILE.stripTrailing(), false, () -> { int keylen5 = switch "
        '(WS-FILE.stripTrailing()) { case "KSDS" -> 10; default -> throw new Hole("CICS file " + WS-FILE.stripTrailing() + ": no store '
        'in the generated project"); }; if (rec2.length < keylen5) throw new DetCics.PastFrom("READ RIDFLD(KEY) shorter '
        'than the key searched: not modelled"); return store(F).search(rec2, keylen5, true); });'
    )
    upd = _LenCics().command("READ FILE(WS-FILE) INTO(REC) RIDFLD(KEY) GTEQ UPDATE RESP(R)", "")
    assert any("heldKey.put(" in x and ".keyOf(read1.record())" in x for x in upd)
    with pytest.raises(C.CicsError, match="not a known file"):  # a literal the project maps to no file
        _LenCics().command("READ FILE('NOPE') INTO(REC) RIDFLD(KEY) GTEQ RESP(R)", "")
    bare = _LenCics()
    bare.gp.files = {}  # (ZECS003: the generated project stores no file -- a Hole at run time, as store() makes it)
    none = bare.command("READ FILE(WS-FILE) INTO(REC) RIDFLD(KEY) GTEQ RESP(R)", "")
    assert none[1].endswith(
        '() -> { throw new Hole("CICS file " + WS-FILE.stripTrailing() + ": the program names no file the '
        'generated project stores"); });'
    )


def test_delete_generic_deletes_every_record_with_the_generic_key():
    """#4771 zECS (ZECS003 3100-DELETE; IBM, EXEC CICS DELETE, register X22): GENERIC deletes every record whose key
    starts with RIDFLD's first KEYLENGTH bytes (CicsTask.delete: NOTFND RESP2 80 when none); on a file named at run time
    a KEYLENGTH not shorter than that file's key is INVREQ 25 then (#5092: 25 / 42 are answered, CicsTask.deleteInvalid;
    22 for a non-KSDS and 26 for a KEYLENGTH without GENERIC likewise). Zero and an unknown KEYLENGTH are refused."""
    out = _LenCics().command("DELETE FILE('KSDS') RIDFLD(KEY) KEYLENGTH(6) GENERIC RESP(R)", "")
    assert out[0] == "byte[] generic2 = DetCics.bytes(f_KEY);"
    assert (
        out[1]
        == "int resp1 = task.deleteGeneric('KSDS'.stripTrailing(), store(F).search(generic2, 6, false).isPresent(), () -> {"
    )
    assert out[3] == ("    while ((found3 = store(F).search(generic2, 6, false)).isPresent()) "
                      "store(F).remove(store(F).keyOf(found3.get()));")  # fmt: skip
    assert "OUTCOME(resp1, task.resp2());" in out
    rt = _LenCics().command("DELETE FILE(WS-FILE) RIDFLD(KEY) KEYLENGTH(8) GENERIC NOHANDLE", "")
    assert rt[1] == "int resp1;"
    assert rt[2].startswith('if (8 >= switch (WS-FILE.stripTrailing()) { case "KSDS" -> 10; default -> throw new Hole(')
    assert rt[2].endswith("resp1 = task.deleteInvalid(WS-FILE.stripTrailing(), true, 25);")
    assert rt[3].startswith("else resp1 = task.deleteGeneric(WS-FILE.stripTrailing(), ")
    for text, want in (
        ("KEYLENGTH(10) GENERIC", "task.deleteInvalid('KSDS'.stripTrailing(), true, 25);"),  # the key is 10
        ("KEYLENGTH(11) GENERIC", "task.deleteInvalid('KSDS'.stripTrailing(), true, 25);"),
        ("KEYLENGTH(-1) GENERIC", "task.deleteInvalid('KSDS'.stripTrailing(), true, 42);"),
        ("KEYLENGTH(- 5) GENERIC", "task.deleteInvalid('KSDS'.stripTrailing(), true, 42);"),
    ):
        got = _LenCics().command(f"DELETE FILE('KSDS') RIDFLD(KEY) {text} RESP(R)", "")
        assert got[0].endswith(want) and "OUTCOME(" in got[1], got
    for text, resp2 in (
        ("KEYLENGTH(6)", 26),
        ("KEYLENGTH(11)", 26),
        ("KEYLENGTH(0)", 26),
    ):  # not GENERIC, not the key's 10
        got = _LenCics().command(f"DELETE FILE('KSDS') RIDFLD(KEY) {text} RESP(R)", "")
        assert got[0].endswith(f"task.deleteInvalid('KSDS'.stripTrailing(), false, {resp2});"), got
    assert (
        "task.delete('KSDS'.stripTrailing(),"
        in _LenCics().command("DELETE FILE('KSDS') RIDFLD(KEY) KEYLENGTH(10) RESP(R)", "")[0]
    )
    for bad, why in (("DELETE FILE('KSDS') RIDFLD(KEY) GENERIC", "GENERIC without KEYLENGTH"),
                     ("DELETE FILE('KSDS') KEYLENGTH(6) GENERIC", "GENERIC without RIDFLD"),
                     ("DELETE FILE('KSDS') RIDFLD(KEY) KEYLENGTH(0) GENERIC", "not above zero"),
                     ("DELETE FILE('KSDS') RIDFLD(KEY) KEYLENGTH(VARLEN) GENERIC", "not a known length"),
                     ("DELETE FILE('KSDS') RIDFLD(SHORTKEY) KEYLENGTH(8) GENERIC", "shorter than the 8-byte"),
                     ("DELETE FILE('NOPE') RIDFLD(KEY) KEYLENGTH(6) GENERIC", "no file the project stores"),
                     ("DELETE FILE('KSDS') RIDFLD(KEY) KEYLENGTH(6) GENERIC NUMREC(R)", "not modelled")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            _LenCics().command(bad, "")


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) GTEQ EQUAL", "EQUAL and GTEQ together"),
        ("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) GENERIC", "GENERIC without KEYLENGTH"),
        ("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(0) GENERIC GTEQ", "not above zero"),
        ("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(VARLEN) GENERIC", "not a known length"),
        ("READ FILE('KSDS') INTO(REC) RIDFLD(SHORTKEY) GTEQ", "shorter than the 10 bytes searched"),
    ],
)
def test_read_gteq_generic_refusals_by_name(text, why):
    with pytest.raises(C.CicsError, match=why):
        _LenCics().command(text, "")


@pytest.mark.parametrize(
    ("opts", "resp2"),
    [
        ("KEYLENGTH(6)", 26),  # no GENERIC, not the key's length (10)
        ("KEYLENGTH(LENGTH OF SHORTKEY)", 26),
        ("KEYLENGTH(6) GTEQ", 26),
        ("KEYLENGTH(11)", 26),
        ("KEYLENGTH(10) GENERIC", 25),  # GENERIC, not shorter than the key
        ("KEYLENGTH(11) GENERIC GTEQ", 25),
        ("KEYLENGTH(-1) GENERIC", 42),  # GENERIC, below zero
        ("KEYLENGTH(-3) GENERIC GTEQ UPDATE", 42),
    ],
)
def test_read_keylength_invreq_is_a_result_with_ibms_resp2(opts, resp2):
    """#5092 (X52), IBM, EXEC CICS READ: INVREQ RESP2 25 / 26 / 42 for a KEYLENGTH that is not the key's length (no
    GENERIC), or for a GENERIC one not shorter than the key / below zero; the read is not done (CicsTask.readInvalid)."""
    out = _LenCics().command(f"READ FILE('KSDS') INTO(REC) RIDFLD(KEY) {opts} RESP(R)", "")
    assert out[0].endswith(
        f"task.readInvalid('KSDS'.stripTrailing(), {'true' if 'UPDATE' in opts else 'false'}, {resp2});"
    )
    assert not any("find(" in line or "search(" in line for line in out)


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
    "ASSIGN": "ABCODE APPLID INVOKINGPROG PROGRAM SYSID USERID NETNAME OPID TERMCODE STARTCODE TWALENG CWALENG "
    "CHANNEL FACILITY FCI SCRNHT SCRNWD DEFSCRNHT DEFSCRNWD ALTSCRNHT ALTSCRNWD TCTUALENG TASKPRIORITY RETURNPROG "
    "PRINSYSID OPCLASS OPSECURITY USERNAME QNAME OPERKEYS",
    "ABEND": "ABCODE CANCEL NODUMP NOHANDLE",
    "FORMATTIME": "ABSTIME DATE FULLDATE DATEFORM DATESEP DAYCOUNT DAYOFMONTH DAYOFWEEK DDMMYY DDMMYYYY MILLISECONDS "
    "MMDDYY MMDDYYYY MONTHOFYEAR STRINGFORMAT TIME TIMESEP YEAR YYDDD YYDDMM YYMMDD YYYYDDD YYYYDDMM YYYYMMDD",
    "SEND MAP": "MAP MAPSET FROM DATAONLY MAPONLY LENGTH CURSOR FORMFIELD ERASE ERASEAUP PRINT FREEKB ALARM FRSET "
    "MSR OUTPARTN ACTPARTN LDC FMHPARMS NLEOM REQID SET PAGING TERMINAL WAIT LAST HONEOM L40 L64 L80 ACCUM",
    "RECEIVE MAP": "MAP MAPSET INTO SET FROMLENGTH FROM TERMINAL ASIS INPARTN",
    # #4413: terminal control (SEND CONTROL; RECEIVE (3270 logical), (LUTYPE2/LUTYPE3), z/OS Communications Server)
    "SEND CONTROL": "CURSOR FORMFEED ERASE DEFAULT ALTERNATE ERASEAUP PRINT FREEKB ALARM FRSET MSR OUTPARTN "
    "ACTPARTN LDC ACCUM TERMINAL SET PAGING WAIT LAST REQID HONEOM L40 L64 L80",
    "RECEIVE": "INTO SET LENGTH FLENGTH MAXLENGTH MAXFLENGTH NOTRUNCATE ASIS BUFFER CONVID SESSION PARTN LDC",
    # #4270: channels and containers (PUT / GET / DELETE CONTAINER (CHANNEL))
    "PUT CONTAINER": "CONTAINER CHANNEL FROM FLENGTH BIT CHAR DATATYPE FROMCCSID FROMCODEPAGE APPEND PREPEND",
    "GET CONTAINER": "CONTAINER CHANNEL INTO SET NODATA FLENGTH BYTEOFFSET INTOCCSID INTOCODEPAGE CONVERTST CCSID",
    "DELETE CONTAINER": "CONTAINER CHANNEL",
    # #4951: MOVE CONTAINER and the container browse
    "MOVE CONTAINER": "CONTAINER AS CHANNEL TOCHANNEL",
    "STARTBROWSE CONTAINER": "CHANNEL BROWSETOKEN",
    "GETNEXT CONTAINER": "CONTAINER BROWSETOKEN",
    "ENDBROWSE CONTAINER": "BROWSETOKEN",
    # #5005: DELETE CHANNEL and QUERY CHANNEL
    "DELETE CHANNEL": "CHANNEL",
    "QUERY CHANNEL": "CHANNEL CONTAINERCNT",
    # #4270 slice 2: interval control (START, RETRIEVE, CANCEL)
    "START": "TRANSID INTERVAL TIME AFTER AT HOURS MINUTES SECONDS FROM LENGTH FLENGTH FMH TERMID USERID SYSID "
    "RTRANSID RTERMID QUEUE REQID NOCHECK PROTECT ATTACH BREXIT CHANNEL",
    "RETRIEVE": "INTO SET LENGTH RTRANSID RTERMID QUEUE WAIT",
    "CANCEL": "ACTIVITY ACQACTIVITY ACQPROCESS REQID SYSID TRANSID",
    "RUN": "TRANSID CHANNEL CHILD",
    # #4270 slice 4: SEND TEXT (minimum, standard and full BMS)
    "SEND TEXT": "FROM LENGTH CURSOR FORMFEED ERASE DEFAULT ALTERNATE PRINT FREEKB ALARM NLEOM FMHPARM OUTPARTN "
    "ACTPARTN LDC MSR TERMINAL SET PAGING WAIT LAST REQID HEADER TRAILER JUSTIFY JUSFIRST JUSLAST ACCUM HONEOM L40 "
    "L64 L80",
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
    for family in (CC, CF, CT, CN, CFL):  # #5274: the command families split out of det/cics.py
        code += Path(family.__file__).read_text(encoding="utf-8")
    stated = {"NODUMP", "MAIN", "AUXILIARY", "NOSUSPEND", "EQUAL", "GTEQ", "TASK", "UOW", "MAXLIFETIME", "RESOURCE",
              "FOR", "INTERVAL", "TIME", "HOURS", "MINUTES", "SECONDS", "MILLISECS", "TS",
              "TERMINAL", "BELOW", "EXECUTABLE", "NAME", "EVENTUAL"}  # (#5079 X63: WAIT EVENT NAME only labels the task)  # (#5859 X32: WRITE OPERATOR EVENTUAL only says when the operator acts)  # (#4771 X47: GETMAIN's placement flags change no byte the program sees)  # fmt: skip
    flags = {*C.MAP_OPTIONS, *C.TEXT_OPTIONS, *C._FORMS}
    for key, allowed in C.OPTIONS.items():
        for opt in allowed or ():
            read = f'"{opt}"' in code or f"'{opt}'" in code
            assert opt in stated | flags or read, f"{key} {opt}: accepted but never read"


# ---- #4468 (after #4467, ownership per #4273): the translator takes each COPY's member from the engine --------------
from gitgalaxy.tools.cobol_to_java.det import source as SRC  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile


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


def _engine(prog, root, deps, gaps=(), collisions=(), strict=False):
    """deps: importer -> its resolved files (a list, or file -> library-names); members are (importer, member)."""
    return SRC.EngineCopies.of(prog, root, deps, gaps, collisions, strict=strict)


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


@pytest.mark.parametrize("strict", [False, True])
def test_a_member_the_engine_reports_as_a_gap_is_refused_in_both_modes(tmp_path, strict):
    """#4486: a gap (no library of the search order holds the member) has no answer to take: refused by name."""
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY AREC."], {"cpy/AREC.cpy": _MEMBER})
    eng = _engine(prog, root, {"cbl/PROG.cbl": []}, gaps=[("cbl/PROG.cbl", "AREC")], strict=strict)
    with pytest.raises(SRC.CopyUnresolved, match="COPY AREC: the engine records a gap"):
        SRC.program_lines(prog, [root / "cpy"], eng)


# #4486 (estate-crucible H-0052 ORDREC / ADDRREC, H-0034 DATEWS): the member is in two libraries of the program's
# SYSLIB order; the engine took the first library's, as the compiler does
_COLLISION = [("cbl/PROG.cbl", "AREC", "ORDRCPY", ["SHRCPY"])]
_TWO_LIBS = {"ord/AREC.cpy": _MEMBER, "shared/AREC.cpy": _fixed("05 S-FIELD PIC X(4).")}


def test_a_syslib_collision_takes_the_first_librarys_member_with_a_warning(tmp_path):
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY AREC."], _TWO_LIBS)
    eng = _engine(prog, root, {"cbl/PROG.cbl": {"ord/AREC.cpy": [""]}}, collisions=_COLLISION)
    lines = SRC.program_lines(prog, [root / "shared", root / "ord"], eng)
    assert _from(lines, "A-FIELD") == {"ord/AREC.cpy"} and not _from(lines, "S-FIELD")
    assert eng.warnings == ["COPY AREC in cbl/PROG.cbl: SYSLIB collision -- took ord/AREC.cpy from library ORDRCPY "
                            "(first in search order); also in SHRCPY"]  # fmt: skip


@pytest.mark.parametrize("strict", [False, True])
def test_a_copy_in_a_library_is_no_collision(tmp_path, strict):
    """#4486 (estate-crucible PAYMAIN: `COPY DATEWS.` and `COPY DATEWS IN SHRCPY.`): the IN form searches that one
    library, so only the unqualified COPY is the collision -- warned (or refused in strict mode) once."""
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY AREC IN SHRCPY."], _TWO_LIBS)
    eng = _engine(prog, root, {"cbl/PROG.cbl": {"shared/AREC.cpy": ["SHRCPY"]}}, collisions=_COLLISION, strict=strict)
    assert _from(SRC.program_lines(prog, [], eng), "S-FIELD") == {"shared/AREC.cpy"} and eng.warnings == []


def test_a_syslib_collision_is_refused_in_strict_mode(tmp_path):
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY AREC."], _TWO_LIBS)
    eng = _engine(prog, root, {"cbl/PROG.cbl": {"ord/AREC.cpy": [""]}}, collisions=_COLLISION, strict=True)
    with pytest.raises(SRC.CopyUnresolved, match="COPY AREC: the engine records a collision"):
        SRC.program_lines(prog, [root / "ord"], eng)
    assert eng.warnings == []


def test_a_collision_the_engine_resolved_no_member_for_is_refused(tmp_path):
    """The first library holds several files of the member: the engine chose none, so neither does the translator."""
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY AREC."], _TWO_LIBS)
    eng = _engine(prog, root, {"cbl/PROG.cbl": []}, collisions=[("cbl/PROG.cbl", "AREC")])
    with pytest.raises(SRC.CopyUnresolved, match="COPY AREC: the engine records a collision and resolved no member"):
        SRC.program_lines(prog, [root / "ord"], eng)


@pytest.mark.parametrize("strict", [False, True])
def test_a_member_in_a_single_library_is_unchanged_by_the_collision_policy(tmp_path, strict):
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY AREC."], _TWO_LIBS)
    eng = _engine(prog, root, {"cbl/PROG.cbl": {"shared/AREC.cpy": [""]}}, strict=strict)
    lines = SRC.program_lines(prog, [root / "ord"], eng)
    assert _from(lines, "S-FIELD") == {"shared/AREC.cpy"} and eng.warnings == []


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


def test_an_i_o_control_apply_hint_is_read_past(tmp_path):
    """#4486 (estate-crucible PAYMAIN, unblocked by the collision policy, refused next by its I-O-CONTROL): `APPLY
    WRITE-ONLY ON f` is a buffering hint with no storage; the grammar does not read it, the layout skips it."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import layout as L

    prog = tmp_path / "P.cbl"
    prog.write_text(_fixed("IDENTIFICATION DIVISION.", "PROGRAM-ID. P.", "ENVIRONMENT DIVISION.",
                           "INPUT-OUTPUT SECTION.", "FILE-CONTROL.", "    SELECT F ASSIGN TO FOUT.", "I-O-CONTROL.",
                           "    APPLY WRITE-ONLY", "        ON F.", "DATA DIVISION.", "FILE SECTION.", "FD  F.",
                           "01  R PIC X(80).", "WORKING-STORAGE SECTION.", "01  W PIC X(2).", "PROCEDURE DIVISION.",
                           "    GOBACK."), encoding="utf-8")  # fmt: skip
    recs = {r.name: r for r in L.parse(SRC.program_lines(prog, []))}
    assert recs["R"].fd == "F" and recs["R"].size == 80 and recs["W"].size == 2


@pytest.mark.parametrize("strict", [False, True])
def test_the_port_tickets_collisions_carry_their_libraries_and_the_strict_mode(tmp_path, strict):
    """#4486: the skeleton's copy_collisions rows name the library chosen and the others; strict comes from the
    translator option (det.program.translate strict_copy, port_runner --strict-copy, a case's `strict_copy`)."""
    prog, root = _estate(tmp_path, ["01 WS-A.", "COPY AREC."], _TWO_LIBS)
    jobs = tmp_path / "project" / "ai_agent_jobs"
    jobs.mkdir(parents=True)
    ticket = {"source": {"program": {"file": "cbl/PROG.cbl"}},
              "facts": {"program": {"copy_edges": {"cbl/PROG.cbl": {"ord/AREC.cpy": [""]}, "ord/AREC.cpy": {}},
                                    "copy_gaps": [], "copy_collisions": [list(_COLLISION[0])]}}}  # fmt: skip
    (jobs / "PROG_port_ticket.json").write_text(json.dumps(ticket), encoding="utf-8")
    eng = SRC.engine_copies_from_ticket(tmp_path / "project", prog, strict=strict)
    assert eng.strict is strict and eng.collision_libraries == {("cbl/PROG.cbl", "AREC"): ("ORDRCPY", ("SHRCPY",))}
    if strict:
        with pytest.raises(SRC.CopyUnresolved, match="collision"):
            SRC.program_lines(prog, [], eng)
    else:
        assert _from(SRC.program_lines(prog, [], eng), "A-FIELD") == {"ord/AREC.cpy"} and len(eng.warnings) == 1


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
    # #4486: a collision carries the library chosen and the others holding the member, in search order
    ir.copy_member_collisions = [{"importer": "cbl/P.cbl", "member": "a", "resolved": "cpy/A.cpy", "library": "LIB",
                                  "shadowed": [{"library": "SHR", "paths": ["shr/A.cpy"]},
                                               {"library": "OLD", "paths": ["old/A.cpy"]}]},
                                 {"importer": "cbl/Q.cbl", "member": "C", "library": "X", "shadowed": []}]  # fmt: skip
    assert GalaxyIR.copy_resolution(ir, "cbl/P.cbl")["collisions"] == [["cbl/P.cbl", "A", "LIB", ["SHR", "OLD"]]]


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

    def int_(self, text):
        return f"INT({text})"


@pytest.mark.parametrize(
    ("text", "cmd", "call"),
    [
        ("SYNCPOINT ROLLBACK RESP(R) RESP2(R2)", "ROLLBACK", "task.rollback();"),  # CBSA DBCRFUN 564, INQACC 682
        ("SYNCPOINT ROLLBACK NOHANDLE RESP(R) RESP2(R2)", "ROLLBACK", "task.rollback();"),
        ("SYNCPOINT RESP(R) RESP2(R2)", "SYNCPOINT", "task.syncpoint();"),  # XFRFUN 407
        ("SYNCPOINT", "SYNCPOINT", "task.syncpoint();"),
    ],
)  # fmt: skip
def test_syncpoint_writes_the_planned_outcome_into_eibresp_resp_and_resp2(text, cmd, call):
    """#4437 (left by #4411): RESP / RESP2 on SYNCPOINT [ROLLBACK] were accepted and never written. #6271 (X71): the
    outcome is the one the scenario plans for the command (NORMAL with no plan), the command runs only when none is
    planned, and the outcome is written as CICS writes it (a condition with no RESP coded raises HANDLE CONDITION)."""
    c = _RespCics()
    assert c.command(text, "") == [
        f'int[] planned1 = task.planned("{cmd}", "-");',
        f"if (planned1[0] == 0) {call}",
        "OUTCOME(planned1[0], planned1[1]);",
    ]
    (opts,) = c.outcomes
    assert ("RESP" in opts) == ("RESP(" in text) and ("RESP2" in opts) == ("RESP2(" in text)


def test_syncpoint_resp2_alone_is_written_too():
    assert _RespCics().command("SYNCPOINT ROLLBACK RESP2(R2)", "") == [
        'int[] planned1 = task.planned("ROLLBACK", "-");',
        "if (planned1[0] == 0) task.rollback();",
        "OUTCOME(planned1[0], planned1[1]);",
        "STORE(R2, BigDecimal.valueOf(planned1[1]));",
    ]


# A sample of each modelled command that accepts RESP; the commands this double cannot translate say why their RESP
# is written (or need not be).
_RESP_SAMPLES = {
    "FETCH ANY": "FETCH ANY(REC) NOSUSPEND", "FETCH CHILD": "FETCH CHILD(REC) NOSUSPEND",
    "FORMATTIME": "FORMATTIME ABSTIME(REC) DDMMYYYY(KEY)", "ENQ": "ENQ RESOURCE(REC) LENGTH(10)", "DEQ": "DEQ RESOURCE(REC) LENGTH(10)", "DELAY": "DELAY FOR SECONDS(1)",
    "SEND TEXT": "SEND TEXT FROM(REC)", "XCTL": "XCTL PROGRAM('P')", "ASSIGN": "ASSIGN APPLID(REC)",
    "READ": "READ FILE('KSDS') INTO(REC) RIDFLD(KEY)", "READNEXT": "READNEXT FILE('KSDS') INTO(REC) RIDFLD(KEY)",
    "READPREV": "READPREV FILE('KSDS') INTO(REC) RIDFLD(KEY)", "STARTBR": "STARTBR FILE('KSDS') RIDFLD(KEY)",
    "ENDBR": "ENDBR FILE('KSDS')", "WRITE": "WRITE FILE('KSDS') FROM(REC) RIDFLD(KEY)",
    "REWRITE": "REWRITE FILE('KSDS') FROM(REC)", "DELETE": "DELETE FILE('KSDS') RIDFLD(KEY)",
    "INQUIRE PROGRAM": "INQUIRE PROGRAM('P')", "WRITEQ TD": "WRITEQ TD QUEUE('Q') FROM(REC)",
    "READQ TD": "READQ TD QUEUE('Q') INTO(REC)", "DELETEQ TD": "DELETEQ TD QUEUE('Q')",
    "WRITEQ TS": "WRITEQ TS QUEUE('Q') FROM(REC)", "READQ TS": "READQ TS QUEUE('Q') INTO(REC)",
    "GET COUNTER": "GET COUNTER(KEY) VALUE(REC)", "SYNCPOINT": "SYNCPOINT", "SYNCPOINT ROLLBACK": "SYNCPOINT ROLLBACK",
    "SEND CONTROL": "SEND CONTROL ERASE", "RECEIVE": "RECEIVE INTO(REC)",
    "PUSH HANDLE": "PUSH HANDLE", "POP HANDLE": "POP HANDLE",
    "PUT CONTAINER": "PUT CONTAINER('C') FROM(REC)", "GET CONTAINER": "GET CONTAINER('C') INTO(REC)",
    "PUT64 CONTAINER": "PUT64 CONTAINER('C') FROM(REC)", "GET64 CONTAINER": "GET64 CONTAINER('C') INTO(REC)",
    "DELETE CONTAINER": "DELETE CONTAINER('C')",
    "MOVE CONTAINER": "MOVE CONTAINER('C') AS('D')", "STARTBROWSE CONTAINER": "STARTBROWSE CONTAINER BROWSETOKEN(REC)",
    "GETNEXT CONTAINER": "GETNEXT CONTAINER(REC) BROWSETOKEN(REC)",
    "ENDBROWSE CONTAINER": "ENDBROWSE CONTAINER BROWSETOKEN(REC)",
    "DELETE CHANNEL": "DELETE CHANNEL('C')", "QUERY CHANNEL": "QUERY CHANNEL('C') CONTAINERCNT(REC)",
    "START": "START TRANSID('T')", "RETRIEVE": "RETRIEVE INTO(REC)", "CANCEL": "CANCEL REQID('R')",
    "RUN": "RUN TRANSID('T') CHILD(REC)", "BIF DEEDIT": "BIF DEEDIT FIELD(REC)", "FREE CHILD": "FREE CHILD(REC)",
    "INQUIRE TERMINAL": "INQUIRE TERMINAL(KEY) UCTRANST(REC)",
    "INQUIRE TDQUEUE": "INQUIRE TDQUEUE(KEY) TYPE(REC)",
    "DELETEQ TS": "DELETEQ TS QUEUE('Q')", "QUERY COUNTER": "QUERY COUNTER(KEY) VALUE(REC)", "INQUIRE ASSOCIATION": "INQUIRE ASSOCIATION(EIBTASKN) ODAPPLID(REC)", "INQUIRE URIMAP": "INQUIRE URIMAP(REC) NEXT", "WRITE OPERATOR": "WRITE OPERATOR TEXT(REC)", "VERIFY PASSWORD": "VERIFY PASSWORD(REC) USERID(KEY)",
    "DEFINE COUNTER": "DEFINE COUNTER(KEY)", "DELETE COUNTER": "DELETE COUNTER(KEY)",
    "REWIND COUNTER": "REWIND COUNTER(KEY)", "UPDATE COUNTER": "UPDATE COUNTER(KEY) VALUE(7)",
    "DOCUMENT CREATE": "DOCUMENT CREATE DOCTOKEN(REC)",
    "DOCUMENT RETRIEVE": "DOCUMENT RETRIEVE DOCTOKEN(KEY) INTO(REC) MAXLENGTH(10) DATAONLY",
    "WEB OPEN": "WEB OPEN SESSTOKEN(KEY) URIMAP(REC)", "WEB CLOSE": "WEB CLOSE SESSTOKEN(KEY)",
    "WEB CONVERSE": "WEB CONVERSE SESSTOKEN(KEY) METHOD(10) INTO(REC) MAXLENGTH(10)",
    "WEB PARSE URL": "WEB PARSE URL(REC) URLLENGTH(R) HOST(REC) HOSTLENGTH(R2)",
    "WEB SEND": "WEB SEND FROM(REC) FROMLENGTH(R) ACTION(R2)",
    "WEB EXTRACT": "WEB EXTRACT HOST(REC) HOSTLENGTH(R)", "EXTRACT WEB": "EXTRACT WEB HOST(REC) HOSTLENGTH(R)",
    "EXTRACT TCPIP": "EXTRACT TCPIP CLIENTADDR(REC) CADDRLENGTH(R)", "WEB RECEIVE": "WEB RECEIVE INTO(REC) MAXLENGTH(R)",
    "WEB READ HTTPHEADER": "WEB READ HTTPHEADER(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2)",
    "WEB WRITE HTTPHEADER": "WEB WRITE HTTPHEADER(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2)",
    "WEB RETRIEVE": "WEB RETRIEVE DOCTOKEN(REC)",
    "UNLOCK": "UNLOCK FILE('KSDS') TOKEN(R)",
    "WEB READ FORMFIELD": "WEB READ FORMFIELD(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2)",
    "WEB READ QUERYPARM": "WEB READ QUERYPARM(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2)",
    **{f"WEB {f} {k}": f"WEB {f} {k}" + ("(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2)" if f == "READNEXT" else "")
       for f in ("STARTBROWSE", "READNEXT", "ENDBROWSE") for k in ("HTTPHEADER", "FORMFIELD", "QUERYPARM")},
}  # fmt: skip
_RESP_ELSEWHERE = {
    "RETURN": "control never comes back from a RETURN (OPTIONS)",
    "SEND MAP": "Cics.send_map ends in outcome() (screens: covered by the det ports' CICS proofs)",
    "RECEIVE MAP": "Cics.receive_map ends in outcome() (covered by the det ports' CICS proofs)",
    "LINK": "Cics.link ends in outcome() (covered by the CBSA / GenApp LINK proofs)",
    "GETMAIN": "Cics.storage ends in outcome() (test_getmain_and_freemain_work_on_task_storage_through_a_pointer)",
    "FREEMAIN": "Cics.storage ends in outcome() (test_getmain_and_freemain_work_on_task_storage_through_a_pointer)",
    "ADDRESS": "Cics.address ends in outcome(); needs the generator's pointer items, which this double lacks: test_address_5079.py::test_a_program_addressing_the_eib_and_the_commarea_translates_whole",
    **dict.fromkeys(
        ("POST", "WAIT EVENT", "CONVERSE"),
        "Cics.post / wait_event / converse end in outcome() and need the generator's pointer items and fields, which this "
        "double lacks: test_post_wait_converse_5079.py::test_post_raises_its_conditions_through_resp_and_handle_condition",
    ),
    "SET TERMINAL": "needs the generator's int_expr, which this double lacks: test_bif_deedit_and_the_terminal_uctranst_cvdas",
    "SET TDQUEUE": "needs the generator's int_expr, which this double lacks: test_td_openstatus_translate_5168.py",
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
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA

    # DetCics.condition / resp delegate to the generated CicsSpec (#4270 spec PR 4)
    rt = (Path(C.__file__).parent / "cobolrt/cics/DetCics.java").read_text(encoding="utf-8") + CICS_SPEC_JAVA
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


# ---- #4270: channels and containers -------------------------------------------------------------------------------
class _ChanCics(_TermCics):
    SIZES = {**_TermCics.SIZES, "AREA": 20}

    def __init__(self):
        super().__init__()
        self.g.jump = lambda target: f"JUMP({target});"
        self.g.p = type("P", (), {"name": "PROG"})()


def test_put_container_is_the_programs_bytes_on_the_task_channel():
    """IBM, PUT CONTAINER (CHANNEL): FROM's first FLENGTH bytes (FLENGTH omitted: FROM's length), into the named
    channel -- created when it does not exist -- or, with no CHANNEL, the current one; BIT / CHAR /
    DATATYPE(DFHVALUE(..)), APPEND. CicsTask answers NORMAL / INVREQ / LENGERR with their RESP2."""
    out = _ChanCics().command("PUT CONTAINER('REQ') CHANNEL(CH) FROM(REC) CHAR RESP(R) RESP2(R2)", "")
    assert out == ["int flen2 = 56;",
                   "CicsTask.ContainerResult cont1 = task.putContainer(CH.strip(), 'REQ'.strip(), "
                   'DetCics.containerData(f_REC, flen2), flen2, "CHAR", false);',
                   "OUTCOME(DetCics.resp(cont1.resp()), cont1.resp2());"]  # fmt: skip
    out = _ChanCics().command("PUT CONTAINER(CN) FROM(REC) FLENGTH(N) DATATYPE(DFHVALUE(BIT)) APPEND", "")
    assert out[0] == "int flen2 = INT(N);" and out[1].endswith('flen2, "BIT", true);') and "(null, " in out[1]
    assert ", null, false);" in _ChanCics().command("PUT CONTAINER(CN) FROM(REC)", "")[1]


_GET_FORMS = (
    "CONTAINER(CN) INTO(AREA) FLENGTH(FL) RESP(R) RESP2(R2)",
    "CONTAINER(CN) CHANNEL(CH) INTO(AREA)",
    "CONTAINER(CN) CHANNEL(CH) NODATA FLENGTH(FL)",
    "CONTAINER(CN) INTO(AREA) FLENGTH(FL) BYTEOFFSET(OFF)",
    "CONTAINER(CN) INTO(AREA) INTOCCSID(1208) CHANNEL(CH)",
    "CONTAINER(CN) INTO(AREA) CONVERTST(DFHVALUE(NOCONVERT)) CCSID(CS)",
)
_PUT_FORMS = (
    "CONTAINER('REQ') CHANNEL(CH) FROM(REC) CHAR RESP(R) RESP2(R2)",
    "CONTAINER(CN) FROM(REC) FLENGTH(N) DATATYPE(DFHVALUE(BIT)) APPEND",
    "CONTAINER(CN) FROM(REC) BIT PREPEND",
    "CONTAINER(CN) CHANNEL(CH) FROM(REC) FROMCCSID(1208)",
)


@pytest.mark.parametrize("verb, form", [("GET", f) for f in _GET_FORMS] + [("PUT", f) for f in _PUT_FORMS])
def test_get64_and_put64_container_translate_as_the_32_bit_commands(verb, form):
    """#5005 (X17), IBM GET64 / PUT64 CONTAINER: the same options, conditions and RESP2 as GET / PUT CONTAINER, with 64-bit
    INTO / FROM. A COBOL item has no address above the bar, so INTO / FROM are the item: every form of the base command is
    generated byte for byte as the 64-bit command, and the 64-bit key's spec holds the base's options but SET."""
    from gitgalaxy.standards.cics.commands import COMMANDS

    assert _ChanCics().command(f"{verb}64 {form}", "") == _ChanCics().command(f"{verb} {form}", "")
    base, wide = COMMANDS[f"{verb} CONTAINER"], COMMANDS[f"{verb}64 CONTAINER"]
    assert wide.status == "modelled" and wide.register == "X17" and wide.impl == base.impl
    assert set(wide.options) == set(base.options) - {"SET"}
    assert [(o.condition, o.resp2) for o in wide.outcomes] == [(o.condition, o.resp2) for o in base.outcomes]


def test_get64_container_set_is_refused_by_name_and_the_code_page_names_stay_refused():
    """#5005 (X17): SET returns a 64-bit pointer reference, which the pointer lane (31-bit-style blocks, X47) does not hold;
    INTOCODEPAGE / FROMCODEPAGE are refused as on the base commands; GET64 still needs INTO or NODATA, PUT64 FROM."""
    for text, why in (
        ("GET64 CONTAINER(CN) SET(PTR) FLENGTH(FL)", "64-bit pointer"),
        ("GET64 CONTAINER(CN) CHANNEL(CH) SET(PTR)", "64-bit pointer"),
        ("GET64 CONTAINER(CN) INTO(AREA) INTOCODEPAGE('IBM-037')", "IANA code-page names"),
        ("PUT64 CONTAINER(CN) FROM(REC) FROMCODEPAGE('IBM-037')", "IANA code-page names"),
        ("GET64 CONTAINER(CN)", "needs one of INTO / NODATA"),
        ("PUT64 CONTAINER(CN)", "needs an argument"),
        ("PUT64 CONTAINER(CN) FROM(REC) SET(PTR)", "SET"),
    ):
        with pytest.raises(C.CicsError, match=why):
            _ChanCics().command(text, "")


def test_byteoffset_and_prepend_pass_to_the_task():  # noqa: E302
    """#5005 (X17), IBM GET CONTAINER BYTEOFFSET and PUT CONTAINER PREPEND: BYTEOFFSET (a data value) calls getContainerAt with the
    most INTO takes; FLENGTH is set back from the length returned. PREPEND is the task's last argument, after the FROMCCSID (-1:
    none); a command without either is generated as before."""
    out = _ChanCics().command("GET CONTAINER(CN) CHANNEL(CH) INTO(AREA) FLENGTH(FL) BYTEOFFSET(OFF) RESP(R)", "")
    assert out == ["CicsTask.ContainerResult cont1 = task.getContainerAt(CH.strip(), CN.strip(), "
                   "DetCics.containerLimit(f_AREA, INT(FL)), INT(OFF));",
                   "if (cont1.data() != null) DetCics.put(f_AREA, cont1.data());",
                   "if (cont1.length() >= 0) STORE(FL, BigDecimal.valueOf(cont1.length()));",
                   "OUTCOME(DetCics.resp(cont1.resp()), cont1.resp2());"]  # fmt: skip
    assert (
        "getContainerAt(null, CN.strip(), DetCics.containerLimit(f_AREA, 20), INT(4));"
        in _ChanCics().command("GET CONTAINER(CN) INTO(AREA) BYTEOFFSET(4)", "")[0]
    )
    out = _ChanCics().command("PUT CONTAINER(CN) FROM(REC) BIT PREPEND", "")
    assert out[1].endswith('flen2, "BIT", false, -1, true);')
    out = _ChanCics().command("PUT CONTAINER(CN) FROM(REC) PREPEND", "")
    assert out[1].endswith("flen2, null, false, -1, true);")


def test_get_container_flength_is_in_out_and_nodata_reads_the_length():
    """IBM, GET CONTAINER (CHANNEL): FLENGTH in -- the most INTO takes (else INTO's length) -- and out, "the length
    of the data in the container", set back on NORMAL and LENGERR (CicsTask's length is -1 otherwise); NODATA moves
    nothing. The data goes into INTO's first bytes."""
    out = _ChanCics().command("GET CONTAINER(CN) CHANNEL(CH) INTO(AREA) FLENGTH(FL) RESP(R)", "")
    assert out == ["CicsTask.ContainerResult cont1 = task.getContainer(CH.strip(), CN.strip(), "
                   "DetCics.containerLimit(f_AREA, INT(FL)));",
                   "if (cont1.data() != null) DetCics.put(f_AREA, cont1.data());",
                   "if (cont1.length() >= 0) STORE(FL, BigDecimal.valueOf(cont1.length()));",
                   "OUTCOME(DetCics.resp(cont1.resp()), cont1.resp2());"]  # fmt: skip
    out = _ChanCics().command("GET CONTAINER(CN) INTO(AREA)", "")
    assert "DetCics.containerLimit(f_AREA, 20)" in out[0] and not any("STORE" in x for x in out)
    out = _ChanCics().command("GET CONTAINER(CN) NODATA FLENGTH(FL)", "")
    assert out[0].endswith("task.getContainer(null, CN.strip(), -1);") and "STORE(FL" in out[1]
    out = _ChanCics().command("DELETE CONTAINER(CN) RESP(R)", "")
    assert out[0] == "CicsTask.ContainerResult cont1 = task.deleteContainer(null, CN.strip());"


def test_container_ccsid_options_pass_the_ccsid_to_the_task():
    """#4270 (X17), IBM PUT CONTAINER FROMCCSID and GET CONTAINER INTOCCSID / CONVERTST / CCSID: the CCSID (a data value) is the
    task's last argument; a command without one calls the
    short form, so every port that names no CCSID is generated as before. CONVERTST(NOCONVERT) reads the container's own
    CCSID; CCSID(area) is stored with FLENGTH, on NORMAL and LENGERR."""
    out = _ChanCics().command("PUT CONTAINER(CN) FROM(REC) FROMCCSID(1140)", "")
    assert out[1].endswith("flen2, null, false, INT(1140));")
    out = _ChanCics().command("PUT CONTAINER(CN) FROM(REC) FROMCCSID(WS-CS) APPEND", "")
    assert out[1].endswith("flen2, null, true, INT(WS-CS));")
    out = _ChanCics().command("GET CONTAINER(CN) INTO(AREA) INTOCCSID(1140)", "")
    assert out[0].endswith("DetCics.containerLimit(f_AREA, 20), INT(1140), false);")
    out = _ChanCics().command("GET CONTAINER(CN) NODATA FLENGTH(FL) INTOCCSID(WS-CS)", "")
    assert out[0].endswith("task.getContainer(null, CN.strip(), -1, INT(WS-CS), false);")
    out = _ChanCics().command("GET CONTAINER(CN) INTO(AREA) CONVERTST(DFHVALUE(NOCONVERT)) CCSID(CS)", "")
    assert out[0].endswith("DetCics.containerLimit(f_AREA, 20), -1, true);")
    assert "if (cont1.length() >= 0) STORE(CS, BigDecimal.valueOf(task.containerCcsid()));" in out
    assert ", -1" not in _ChanCics().command("GET CONTAINER(CN) INTO(AREA)", "")[0]


def test_container_ccsid_options_refuse_a_region_page_other_than_037():
    """The conversion tables read a program's bytes as CCSID 037, the port's default region page (#4528): an estate that
    declares another EBCDIC page (cp273 ...) cannot use them."""
    c = _ChanCics()
    c.region = "IBM273"
    with pytest.raises(C.CicsError, match="CCSID 037, not IBM273"):
        c.command("GET CONTAINER(CN) INTO(AREA) INTOCCSID(1140)", "")
    out = c.command("GET CONTAINER(CN) INTO(AREA)", "")  # no CCSID option: as before
    assert out[0].endswith("DetCics.containerLimit(f_AREA, 20));")


def test_move_container_is_a_rename_across_channels():
    """IBM, MOVE CONTAINER (CHANNEL): CONTAINER and AS, CHANNEL and TOCHANNEL (omitted: the current channel); the
    answer is CicsTask's, with RESP2 (INVREQ 4, CHANNELERR 2, CONTAINERERR 10), through RESP / HANDLE CONDITION."""
    out = _ChanCics().command("MOVE CONTAINER('A') AS('B') CHANNEL(CH) TOCHANNEL(TC) RESP(R)", "")
    assert out == ["CicsTask.ContainerResult cont1 = task.moveContainer(CH.strip(), 'A'.strip(), 'B'.strip(), TC.strip());",
                   "OUTCOME(DetCics.resp(cont1.resp()), cont1.resp2());"]  # fmt: skip
    out = _ChanCics().command("MOVE CONTAINER(CN) AS(NEW)", "")
    assert out[0] == "CicsTask.ContainerResult cont1 = task.moveContainer(null, CN.strip(), NEW.strip(), null);"
    for bad in ("MOVE CONTAINER(CN)", "MOVE CONTAINER AS(NEW)", "MOVE CONTAINER(CN) AS"):
        with pytest.raises(C.CicsError):
            _ChanCics().command(bad, "")


def test_the_container_browse_stores_the_token_and_the_name():
    """IBM, STARTBROWSE / GETNEXT / ENDBROWSE CONTAINER (CHANNEL): the token (a fullword) is stored by STARTBROWSE
    on NORMAL only; GETNEXT's 16-character name is stored on NORMAL only; END, TOKENERR, ILLOGIC and CHANNELERR come
    back with their RESP2 through RESP / HANDLE CONDITION."""
    c = _ChanCics()
    out = c.command("STARTBROWSE CONTAINER CHANNEL(CH) BROWSETOKEN(REC) RESP(R)", "")
    assert out[0] == "CicsTask.ContainerResult cont1 = task.startBrowseContainer(CH.strip());"
    assert out[1].startswith("if (cont1.length() >= 0) STORE(REC, BigDecimal.valueOf(cont1.length()))")
    assert out[-1] == "OUTCOME(DetCics.resp(cont1.resp()), cont1.resp2());"
    assert "task.startBrowseContainer(null);" in _ChanCics().command("STARTBROWSE CONTAINER BROWSETOKEN(REC)", "")[0]
    out = _ChanCics().command("GETNEXT CONTAINER(AREA) BROWSETOKEN(TK) RESP(R)", "")
    assert out[0] == "CicsTask.ContainerResult cont1 = task.getNextContainer(INT(TK));"
    assert out[1] == "if (cont1.name() != null) DetCics.putText(f_AREA, cont1.name(), CS);"
    out = _ChanCics().command("ENDBROWSE CONTAINER BROWSETOKEN(TK) NOHANDLE", "")
    assert out[0] == "CicsTask.ContainerResult cont1 = task.endBrowseContainer(INT(TK));"
    for bad in ("STARTBROWSE CONTAINER CHANNEL(CH)", "GETNEXT CONTAINER(AREA)", "GETNEXT BROWSETOKEN(TK)",
                "ENDBROWSE CONTAINER"):  # fmt: skip
        with pytest.raises(C.CicsError):
            _ChanCics().command(bad, "")


def test_delete_and_query_channel_answer_with_channelerr_and_the_count():
    """IBM, DELETE CHANNEL (the channel and its containers go) and QUERY CHANNEL (CONTAINERCNT, a fullword, the number of
    containers): CHANNEL is required, CHANNELERR RESP2 2 comes back through RESP / HANDLE CONDITION, and the count is
    stored on NORMAL only."""
    out = _ChanCics().command("DELETE CHANNEL(CH) RESP(R)", "")
    assert out == ["CicsTask.ContainerResult chan1 = task.deleteChannel(CH.strip());",
                   "OUTCOME(DetCics.resp(chan1.resp()), chan1.resp2());"]  # fmt: skip
    assert "task.deleteChannel('X'.strip());" in _ChanCics().command("DELETE CHANNEL('X') NOHANDLE", "")[0]
    out = _ChanCics().command("QUERY CHANNEL(CH) CONTAINERCNT(REC) RESP(R)", "")
    assert out[0] == "CicsTask.ContainerResult chan1 = task.queryChannel(CH.strip());"
    assert out[1].startswith("if (chan1.length() >= 0) STORE(REC, BigDecimal.valueOf(chan1.length()))")
    assert out[-1] == "OUTCOME(DetCics.resp(chan1.resp()), chan1.resp2());"
    for bad in ("DELETE CHANNEL", "DELETE CHANNEL(CH) CONTAINER(CN) CHANNELX(Q)", "QUERY CHANNEL(CH)",
                "QUERY CHANNEL CONTAINERCNT(REC)", "QUERY CHANNEL(CH) CONTAINERCNT"):  # fmt: skip
        with pytest.raises(C.CicsError):
            _ChanCics().command(bad, "")
    with pytest.raises(C.CicsError, match="CONTAINERTYPE"):
        _ChanCics().command("DELETE CHANNEL(CH) CONTAINERTYPE(X)", "")


def test_inquire_container_is_refused_by_name_whatever_its_options():
    """#5005 / X44: IBM documents INQUIRE CONTAINER only for a BTS data-container, so a channel form (CHANNEL,
    BROWSETOKEN, START / NEXT / END) and the BTS options alike are refused at translation, with the reason."""
    for opts in ("", "(CN)", "(CN) CHANNEL(CH)", "(CN) BROWSETOKEN(TK)", " START CHANNEL(CH) BROWSETOKEN(TK)",
                 " NEXT BROWSETOKEN(TK)", " END BROWSETOKEN(TK)", "(CN) DATALENGTH(FL)", "(CN) SET(PTR)",
                 "(CN) ACTIVITYID(ID) DATALENGTH(FL)", "(CN) PROCESS(PN) PROCESSTYPE(PT) SET(PTR) RESP(R)",
                 "(CN) CHANNEL(CH) NOHANDLE"):  # fmt: skip
        with pytest.raises(C.CicsError, match="INQUIRE CONTAINER.*only for a BTS data-container.*no channel form"):
            _ChanCics().command(f"INQUIRE CONTAINER{opts}", "")


def test_link_and_xctl_pass_a_channel_and_assign_reads_it():
    """IBM, LINK / XCTL CHANNEL: the channel is "made available to the called program" as its current channel;
    ASSIGN CHANNEL returns its name (blanks without one). CHANNEL beside COMMAREA is refused."""
    c = _ChanCics()
    link = c.command("LINK PROGRAM('SUB') CHANNEL(CH) RESP(R)", "")
    assert link[0] == "String lr1 = task.linkChannel('SUB'.strip(), CH.strip());" and "task.abendExit();" in link[1]
    xctl = c.command("XCTL PROGRAM('XB') CHANNEL(CH)", "")
    assert xctl[:2] == ["String xr4 = task.xctlChannel('XB'.strip(), CH.strip());",
                        'if ("NORMAL".equals(xr4)) throw new Goback();']  # fmt: skip
    assert c.command("ASSIGN CHANNEL(REC)", "") == ["DetCics.putText(f_REC, task.assignChannel(), CS);"]
    for bad in ("LINK PROGRAM('P') CHANNEL(CH) COMMAREA(REC)", "XCTL PROGRAM('P') CHANNEL(CH) COMMAREA(REC)"):
        with pytest.raises(C.CicsError, match="one or the other"):
            c.command(bad, "")


def test_return_channel_hands_the_next_task_a_channel():
    """#5005, IBM EXEC CICS RETURN: CHANNEL is "made available to the next program"; below the highest level the
    command fails (INVREQ RESP2 2) and returns to the program. COMMAREA, LENGTH, IMMEDIATE and a missing TRANSID are
    refused by name."""
    c = _ChanCics()
    out = c.command("RETURN TRANSID('NEXT') CHANNEL(CH) RESP(R)", "")
    assert out[0] == "int[] rr1 = task.returnChannel('NEXT'.strip(), CH.strip());"
    assert out[1] == "if (rr1[0] == 0) { caBack.run(); throw new Goback(); }"
    for bad in (
        "RETURN TRANSID('NEXT') CHANNEL(CH) COMMAREA(REC)",
        "RETURN TRANSID('NEXT') CHANNEL(CH) LENGTH(4)",
        "RETURN TRANSID('NEXT') CHANNEL(CH) IMMEDIATE",
        "RETURN CHANNEL(CH)",
    ):
        with pytest.raises(C.CicsError, match="RETURN CHANNEL with COMMAREA"):
            c.command(bad, "")


def test_send_text_terminal_is_the_default_disposition():
    """#4270 slice 4, IBM "Output disposition options: TERMINAL, SET, and PAGING": TERMINAL "is the default value that
    you get if you do not specify another disposition" and "sends the output to the principal facility of your task".
    SEND TEXT TERMINAL translates as SEND TEXT does (census: SEQPNT, ASYNCPNT, WEBHOME), its other options recorded
    as before; the logical-message, printer and partition options are refused with a reason (register X20)."""
    plain = _RespCics().command("SEND TEXT FROM(REC) WAIT FREEKB ERASE RESP(R)", "")
    terminal = _RespCics().command("SEND TEXT FROM(REC) TERMINAL WAIT FREEKB ERASE RESP(R)", "")
    assert terminal == plain
    assert 'int[] planned2 = task.planned("SEND-TEXT", "-");' in plain  # #6271 (X71): a planned fault sends nothing
    assert (
        'if (planned2[0] == 0) task.sendText(text1.substring(0, Math.min(text1.length(), 56)), 56, "ERASE", "FREEKB",'
        ' "WAIT");'
    ) in plain
    for opt, why in (("ACCUM", "logical message"), ("PAGING", "terminal paging"), ("SET(PTR)", "RETPAGE"),
                     ("HEADER(REC)", "page headers"), ("JUSTIFY(KEY)", "page"), ("L80", "printer"),
                     ("NLEOM", "printer"), ("OUTPARTN(KEY)", "unpartitioned"), ("ALTERNATE", "screen size"),
                     ("MSR(KEY)", "magnetic")):  # fmt: skip
        name = opt.split("(")[0]
        with pytest.raises(C.CicsError, match=f"SEND TEXT {name}: option not modelled .*{why}"):
            _RespCics().command(f"SEND TEXT FROM(REC) TERMINAL ERASE {opt}", "")


def test_send_text_length_past_from_sends_what_follows_it_in_its_record():
    """#4270 (GenApp LGICVS01: SEND TEXT FROM(WRITE-MSG-H) LENGTH(24), WRITE-MSG-H X(14) followed by WRITE-MSG-HIGH in
    WRITE-MSG): CICS sends LENGTH bytes from FROM's first byte, so the port takes them from FROM's record
    (DetCics.withinRecord; past the record, refused: X6). Before, the text was cut at FROM's end."""
    past = _LenCics().command("SEND TEXT FROM(REC) LENGTH(60) ERASE", "")
    assert past[0] == 'String text1 = new String(DetCics.withinRecord(f_REC, INT(60), "SEND TEXT"), CS);'
    within = _LenCics().command("SEND TEXT FROM(REC) LENGTH(56) ERASE", "")
    assert within[0] == "String text1 = Cobol.text(f_REC, CS);"  # as before: LENGTH within FROM


def test_assign_startcode_userid_and_the_terminal_facts():
    """#4270 slice 3, IBM EXEC CICS ASSIGN: STARTCODE / USERID from what the harness states; FACILITY / SCRNHT / SCRNWD
    INVREQ RESP2 5 for a task with no terminal, and then no data area written (register X19). Other options are
    refused with a reason."""
    c = _ChanCics()
    assert c.command("ASSIGN STARTCODE(REC) USERID(REC)", "") == [
        "DetCics.putText(f_REC, task.assignStartcode(), CS);",
        "DetCics.putText(f_REC, task.assignUserid(), CS);",
    ]
    out = c.command("ASSIGN FACILITY(REC) SCRNHT(KEY) RESP(R) RESP2(R)", "")
    assert out[:2] == ["int assign1 = task.assignTerminalResp();", "if (assign1 == 0) {"]
    assert out[2] == "    DetCics.putText(f_REC, task.assignFacility(), CS);"
    assert "task.assignScreen(false)" in out[3] and out[4] == "}"
    assert any("(assign1 == 0 ? 0 : 5)" in x for x in out[5:])
    unhandled = _ChanCics().command("ASSIGN SCRNWD(KEY)", "")  # (OUTCOME: the condition's handling, no RESP)
    assert "task.assignScreen(true)" in unhandled[2] and unhandled[-1] == "OUTCOME(assign1, (assign1 == 0 ? 0 : 5));"
    for opt, why in (("OPID", "no security"), ("NETNAME", "network name"), ("TERMCODE", "device"),
                     ("TWALENG", "transaction work area"), ("MAPCOLUMN", "no corpus program")):  # fmt: skip
        with pytest.raises(C.CicsError, match=f"ASSIGN {opt}: option not modelled .*{why}"):
            c.command(f"ASSIGN {opt}(REC)", "")


def test_bif_deedit_and_the_terminal_uctranst_cvdas():
    """#4415 slice 1 (register X26), IBM EXEC CICS BIF DEEDIT / INQUIRE TERMINAL / SET TERMINAL: DEEDIT edits FIELD in
    place (LENGTH its length, LENGERR below 1, no RESP2); INQUIRE TERMINAL UCTRANST returns the CVDA (UCTRAN 450,
    NOUCTRAN 451, TRANIDONLY 452); SET TERMINAL UCTRANST takes DFHVALUE(..) or a data area, TERMIDERR RESP2 23 /
    INVREQ RESP2 43 from the runtime. Other options are refused by name."""
    c = _ChanCics()
    out = c.command("BIF DEEDIT FIELD(REC) RESP(R)", "")
    assert out[0] == "int resp1 = CicsTask.deeditResp(f_REC.length());"
    assert out[1] == "if (resp1 == 0) DetCics.deedit(f_REC, f_REC.length(), CS, REGION);"
    sized = c.command("BIF DEEDIT FIELD(REC) LENGTH(4) NOHANDLE", "")
    assert sized[0].endswith("deeditResp(INT(4));") and sized[1].endswith("DetCics.deedit(f_REC, INT(4), CS, REGION);")
    assert c.region_used
    inq = c.command("INQUIRE TERMINAL(KEY) UCTRANST(REC) RESP(R) RESP2(R)", "")
    assert inq[0].startswith("int[] term") and ".inquireUctranst(" in inq[0] and inq[1].startswith("if (term")
    st = c.command("SET TERMINAL(KEY) UCTRANST(DFHVALUE(NOUCTRAN)) RESP(R)", "")
    assert (
        ".setUctranst(" in st[0] and "NOUCTRAN" in st[0]
    )  # (the double prints its operand; DFHVALUE -> 451 is test_dfhvalue_is_its_cvda)
    for bad, why in (("INQUIRE TERMINAL(KEY) NETNAME(REC)", "only the terminal's translation state"),
                     ("SET TERMINAL(KEY) UCTRANST(X) PURGE", "only the terminal's translation state")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")
    with pytest.raises(C.CicsError, match="without UCTRANST"):
        c.command("SET TERMINAL(KEY)", "")


def test_deleteq_ts_and_inquire_association_and_the_receive_map_terminal_option():
    """#4415 slice 2 (register X29), IBM EXEC CICS DELETEQ TS / INQUIRE ASSOCIATION / RECEIVE MAP: DELETEQ TS deletes the
    whole queue (QIDERR for one that is not there, RESP2 0); INQUIRE ASSOCIATION(EIBTASKN) takes the origin data the run
    states (none: refused); RECEIVE MAP's TERMINAL is the task's terminal, which it reads anyway."""
    c = _ChanCics()
    assert c.command("DELETEQ TS QUEUE('Q') RESP(R) RESP2(R)", "") == ["int ts1 = task.deleteqTs('Q'.strip());",
                                                                       "OUTCOME(ts1, 0);"]  # fmt: skip
    assert c.command("DELETEQ QUEUE('Q') NOHANDLE", "")[0].startswith("int ts")  # (TS is the default)
    for bad, why in (("DELETEQ TS", "without QUEUE / QNAME"), ("DELETEQ TS QUEUE('Q') SYSID('A')", "SYSID")):
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")
    a = c.command("INQUIRE ASSOCIATION(EIBTASKN) ODAPPLID(REC) ODUSERID(REC) ODFACILNAME(REC) ODNETWORKID(REC) "
                  "ODFACILTYPE(KEY) RESP(R)", "")  # fmt: skip
    assert a[0].startswith("CicsTask.Origin assoc") and a[0].endswith("= task.inquireAssociation();")
    assert sum("putText" in x for x in a) == 4 and any(".faciltype()" in x for x in a)
    with pytest.raises(C.CicsError, match="without an origin option"):
        c.command("INQUIRE ASSOCIATION(EIBTASKN) RESP(R) RESP2(R)", "")
    q = c.command("QUERY COUNTER(KEY) POOL('GENAPOOL') VALUE(REC) RESP(R)", "")
    assert (
        q[0].startswith("int[] counter") and ".queryCounter(" in q[0] and q[1].endswith("[0] == 22) {")
    )  # (#4770: LENGERR writes VALUE)
    assert q[2].startswith("    STORE(REC, BigDecimal.valueOf(counter") and q[-1].startswith("OUTCOME(counter")
    assert _LenCics().command("QUERY COUNTER(KEY) VALUE(REC) NOSUSPEND", "") == _LenCics().command(
        "QUERY COUNTER(KEY) VALUE(REC)", ""
    )  # #5039, X53
    g = c.command("GET COUNTER(KEY) VALUE(REC) RESP(R) RESP2(R2)", "")  # X30: INVREQ RESP2 201, not NOTFND
    assert (
        g[0].startswith("long[] counter")
        and ".getCounter(" in g[0]
        and "task.fullwordGet(" in g[1]
        and g[2].endswith("[0] == 22) {")
    )  # (#4770: LENGERR writes VALUE)
    assert any("OUTCOME((int) counter" in x for x in g) and not any("NOTFND" in x or " 13" in x for x in g)
    d = c.command("DEFINE COUNTER(KEY) POOL('GENAPOOL') VALUE(REC) RESP(R)", "")
    assert d[0].startswith("int[] counter") and ".defineCounter(" in d[0] and "INT(REC)" in d[0]
    assert any(x.startswith("OUTCOME(counter") for x in d)
    assert (
        ", 0, 0, 2147483647);" in c.command("DEFINE COUNTER(KEY) RESP(R)", "")[0]
    )  # VALUE omitted: IBM's initial zero
    x = c.command("DELETE COUNTER(KEY) POOL('GENAPOOL') RESP(R)", "")
    assert x[0].startswith("int[] counter") and ".deleteCounter(" in x[0]
    for bad, why in (("DEFINE COUNTER(KEY) MINIMUM(0)", "MINIMUM without VALUE"),
                     ("DEFINE DCOUNTER(KEY) MINIMUM(0)", "MINIMUM without VALUE"),
                     ("DEFINE DCOUNTER(KEY) COUNTER(KEY)", "one of COUNTER and DCOUNTER"),
                     ("DELETE COUNTER(KEY) VALUE(REC)", "only the counter's name and pool")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")
    for bad, why in (("INQUIRE ASSOCIATION(KEY) ODAPPLID(REC)", "only the task's own number, EIBTASKN"),
                     ("INQUIRE ASSOCIATION(EIBTASKN) ODTASKID(REC)", "only the origin data"),
                     ("INQUIRE ASSOCIATION ODAPPLID(REC)", "needs an argument")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")


def test_inquire_urimap_browse_and_write_operator():
    """#4270 zECS (register X32), IBM INQUIRE URIMAP ("Browsing resource definitions") / WRITE OPERATOR: START, NEXT and END
    are the CicsTask browse (ILLOGIC RESP2 1, END RESP2 2 through RESP / HANDLE CONDITION); NEXT hands the definition's name,
    PATH and TRANSACTION to the areas only on NORMAL; WRITE OPERATOR sends the text area. Everything IBM leaves open is
    refused by name."""
    c = _ChanCics()
    s = c.command("INQUIRE URIMAP START NOHANDLE", "")
    assert s[0].startswith("int[] urimap") and s[0].endswith("= task.inquireUrimapStart();")
    n = c.command("INQUIRE URIMAP(REC) PATH(REC) TRANSACTION(KEY) NEXT RESP(R)", "")
    assert n[0].endswith("= task.inquireUrimapNext();") and n[1].endswith("[0] == 0) {")
    assert sum("DetCics.putText(" in x for x in n) == 3 and "task.urimapPath()" in " ".join(n)
    assert any("OUTCOME(urimap" in x for x in n)
    e = c.command("INQUIRE URIMAP END NOHANDLE", "")
    assert e[0].endswith("= task.inquireUrimapEnd();")
    w = c.command("WRITE OPERATOR TEXT(REC) NOHANDLE", "")
    assert w[0].startswith("int wto") and ".writeOperator(Cobol.text(" in w[0]
    for bad, why in (("INQUIRE URIMAP(REC) NEXT START", "more than one of START, NEXT and END"),
                     ("INQUIRE URIMAP START PATH(REC)", "returns no definition"),
                     ("INQUIRE URIMAP(REC) HOST(REC) NEXT", "only the URIMAP's name, PATH and TRANSACTION"),
                     ("WRITE OPERATOR", "without TEXT"),
                     ("WRITE OPERATOR TEXT(REC) ROUTECODES(REC)", "ROUTECODES and NUMROUTES go together"),
                     ("WRITE OPERATOR TEXT(REC) NUMROUTES(N)", "ROUTECODES and NUMROUTES go together"),
                     ("WRITE OPERATOR TEXT(REC) CONSNAME(REC)", "only the plain message to the console"),
                     ("WRITE OPERATOR TEXT(REC) REPLY(REC)", "only the plain message to the console")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")
    # #5859 (ZECSNC): TEXTLENGTH, ROUTECODES + NUMROUTES, EVENTUAL answer through RESP / RESP2 like the plain form
    r = c.command("WRITE OPERATOR TEXT(REC) TEXTLENGTH(N) ROUTECODES(REC) NUMROUTES(N) EVENTUAL NOHANDLE", "")
    assert r[0].startswith("int[] wto") and ".writeOperator(Cobol.text(" in r[0] and "Integer.valueOf(" in r[0]
    assert r[0].count("Integer.valueOf(") == 2 and "null" not in r[0]
    t = c.command("WRITE OPERATOR TEXT(REC) TEXTLENGTH(7) EVENTUAL", "")[0]
    assert t.endswith("Integer.valueOf(INT(7)), null, null);")  # (a length alone: no routes)
    assert c.command("WRITE OPERATOR TEXT(REC) EVENTUAL", "")[0].startswith(
        "int wto"
    )  # (EVENTUAL alone: the plain form)


def test_verify_password_asks_the_stated_verdict_and_refuses_what_it_cannot_model():
    """#5859 (ZECS002, register X32), IBM VERIFY PASSWORD(pw) USERID(id): the region has no security manager, so the port asks
    CicsTask for the verdict a scenario states for the USERID and answers through RESP / RESP2 like any command; the
    password is not compared. A missing operand or an option outside the plain form is refused by name."""
    c = _ChanCics()
    v = c.command("VERIFY PASSWORD(REC) USERID(KEY) NOHANDLE", "")
    assert v[0].startswith("int[] ver") and ".verifyPassword(Cobol.text(" in v[0]
    assert "[0]" in " ".join(v[1:]) and "[1]" in " ".join(v[1:])
    for bad, why in (("VERIFY PASSWORD(REC)", "without USERID"),
                     ("VERIFY USERID(KEY)", "not modelled"),
                     ("VERIFY PASSWORD(REC) USERID(KEY) NEWPASSWORD(REC)", "only USERID and PASSWORD")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")


def test_write_operator_routing_options_lower_to_the_stub_call():
    """#5859 (ZECSNC): TEXTLENGTH / ROUTECODES + NUMROUTES reach the stub's GGCWTO through GG-LEN, GG-NUM and the flags;
    one of ROUTECODES / NUMROUTES alone is refused by name, never dropped."""
    import equivalence_cics as ec  # noqa: PLC0415 (tests/tools is on sys.path above)

    plain = " ".join(ec.translate_command("WRITE OPERATOR TEXT(WS-MSG) EVENTUAL"))
    assert "GGCWTO" in plain and "TEXTLENGTH" not in plain and "ROUTES" not in plain
    out = " ".join(
        ec.translate_command("WRITE OPERATOR TEXT(WS-MSG) TEXTLENGTH(WS-N) ROUTECODES(WS-RC) NUMROUTES(WS-NR) EVENTUAL")
    )
    assert "GGCWTO" in out and "TEXTLENGTH ROUTES" in out and "TO GG-LEN" in out and "TO GG-NUM" in out
    assert "WS-RC" in out and "WS-NR" in out
    for opt in ("ROUTECODES(WS-RC)", "NUMROUTES(WS-NR)"):
        with pytest.raises(ec.Unsupported, match="go together"):
            ec.translate_command(f"WRITE OPERATOR TEXT(WS-MSG) {opt} EVENTUAL")


def test_abend_nohandle_is_the_plain_abend():
    """#5859 (ZECSNC): IBM's ABEND page lists no condition, so NOHANDLE suppresses nothing: the same lines as without."""
    assert _HandleCics().command("ABEND ABCODE('HCX1') NOHANDLE", "") == _HandleCics().command(
        "ABEND ABCODE('HCX1')", ""
    )
    assert _HandleCics().command("ABEND NOHANDLE", "") == _HandleCics().command("ABEND", "")


def test_web_send_is_the_response_to_the_stated_request():
    """#4767 zECS (register X37), IBM WEB SEND (server): CicsTask.webSend takes FROM's text and FROMLENGTH, MEDIATYPE's text
    (null when absent), ACTION's value (0 absent), STATUSCODE (-1), STATUSTEXT's text and STATUSLEN (-1: the whole area) and
    the conversion flag (0 / 1 SRVCONVERT / 2 NOSRVCONVERT); every condition through RESP / HANDLE CONDITION. What IBM leaves
    open, or zECS does not use, is refused by name."""
    c = _ChanCics()
    w = c.command(
        "WEB SEND FROM(REC) FROMLENGTH(R) MEDIATYPE(REC) ACTION(R2) STATUSCODE(R) STATUSTEXT(REC) SRVCONVERT NOHANDLE",
        "",
    )
    assert w[0].startswith("int[] web") and ".webSend(Cobol.text(" in w[0] and w[0].endswith(", -1, 1);")
    assert any("OUTCOME(web" in x for x in w)
    n = c.command("WEB SEND FROM(REC) FROMLENGTH(R) NOSRVCONVERT STATUSTEXT(REC) STATUSLEN(R2) NOHANDLE", "")
    assert ", null, 0, -1, Cobol.text(" in n[0] and n[0].endswith(", 2);")
    d = c.command("WEB SEND DOCTOKEN(KEY) MEDIATYPE(REC) ACTION(R2) STATUSCODE(R) SRVCONVERT NOHANDLE", "")
    assert ".webSendDocument(Cobol.text(" in d[0] and d[0].endswith(
        ", 1, 0, CS);"
    )  # (#4767: the document the token names; #4941: DOCSTATUS 0 when not given)
    ct = c.command("WEB SEND CONTAINER(KEY) CHANNEL(REC) MEDIATYPE(REC) ACTION(R2) SRVCONVERT NOHANDLE", "")
    assert ".webSendContainer(REC.strip(), KEY.strip(), Cobol.text(" in ct[0] and ct[0].endswith(
        ", 1, CS);"
    )  # (#5037 X37: a container's data)
    cc = c.command("WEB SEND CONTAINER(KEY) ACTION(R2) NOHANDLE", "")
    assert ".webSendContainer(null, " in cc[0]  # (no CHANNEL: the current channel)
    ds = c.command("WEB SEND DOCTOKEN(KEY) ACTION(R2) DOCSTATUS(R) NOHANDLE", "")
    assert ds[0].endswith(", 0, INT(R), CS);")  # (#4941 X37: DOCSTATUS's CVDA, DOCDELETE / NODOCDELETE)
    for bad, why in (("WEB SEND FROMLENGTH(R)", "needs exactly one of FROM"),
                     ("WEB SEND FROM(REC) FROMLENGTH(R) DOCTOKEN(KEY)", "needs exactly one of FROM"),
                     ("WEB SEND DOCTOKEN(KEY) FROMLENGTH(R)", "FROMLENGTH without FROM"),
                     ("WEB SEND DOCTOKEN(KEY) SRVCONVERT NOSRVCONVERT", "both SRVCONVERT and NOSRVCONVERT"),
                     ("WEB SEND FROM(REC) FROMLENGTH(R) DOCSTATUS(R)", "DOCSTATUS without DOCTOKEN"),
                     ("WEB SEND FROM(REC)", "FROM without FROMLENGTH"),
                     ("WEB SEND FROM(REC) FROMLENGTH(R) SRVCONVERT NOSRVCONVERT", "both SRVCONVERT and NOSRVCONVERT"),
                     ("WEB SEND FROM(REC) FROMLENGTH(R) STATUSLEN(R)", "STATUSLEN without STATUSTEXT"),
                     ("WEB SEND FROM(REC) FROMLENGTH(R) CHUNKING(R)", "chunked response"),
                     ("WEB SEND FROM(REC) FROMLENGTH(R) CHARACTERSET(REC)", "code-page conversion"),
                     ("WEB SEND FROM(REC) FROMLENGTH(R) CLOSESTATUS(R)", "closing the connection"),
                     ("WEB SEND CONTAINER(KEY) FROM(REC) FROMLENGTH(R)", "needs exactly one of FROM"),
                     ("WEB SEND CONTAINER(KEY) DOCTOKEN(KEY)", "needs exactly one of FROM"),
                     ("WEB SEND CHANNEL(KEY) FROM(REC) FROMLENGTH(R)", "CHANNEL without CONTAINER"),
                     ("WEB SEND CONTAINER(KEY) CHUNKING(R)", "chunked response"),
                     ("WEB SEND CONTAINER(KEY) HOSTCODEPAGE(REC)", "code-page conversion"),
                     ("WEB SEND CONTAINER(KEY) CHARACTERSET(REC)", "code-page conversion"),
                     ("WEB SEND CONTAINER(KEY) CLNTCODEPAGE(REC)", "code-page conversion"),
                     ("WEB SEND CONTAINER(KEY) CLOSESTATUS(R)", "closing the connection"),
                     ("WEB SEND CONTAINER(KEY) LENGTH(R)", "LENGTH is kept for upgrade only")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")


def test_web_extract_reads_the_stated_request():
    """#4767 zECS (register X38), IBM WEB EXTRACT (server): CicsTask.webExtract takes each piece's length option (null when the
    piece is not asked for) and its area's size; on NORMAL only the pieces' bytes, their lengths, PORTNUMBER, SCHEME's CVDA and
    REQUESTTYPE's HTTPYES (1033) are written. The client form and what the request does not state are refused by name."""
    c = _ChanCics()
    w = c.command(
        "WEB EXTRACT SCHEME(R) HOST(REC) HOSTLENGTH(R2) PATH(REC) PATHLENGTH(R) PORTNUMBER(R) REQUESTTYPE(R2) NOHANDLE",
        "",
    )
    assert w[0].startswith("CicsTask.WebExtracted web") and ".webExtract(Integer.valueOf(" in w[0]
    assert ", null, 0, null, 0, Integer.valueOf(" in w[0] and w[0].endswith(
        ", null, 0);"
    )  # (no METHOD / VERSION / QUERY)
    body = " ".join(w)
    assert ".resp() == 0) {" in body and ".host().getBytes(CS)" in body and ".path().length()" in body
    assert ".port()" in body and ".scheme()" in body and "valueOf(1033)" in body
    for ok in ("WEB EXTRACT HTTPMETHOD(REC) METHODLENGTH(R)", "WEB EXTRACT HTTPVERSION(REC) VERSIONLEN(R)",
               "WEB EXTRACT QUERYSTRING(REC) QUERYSTRLEN(R) NOHANDLE"):  # fmt: skip
        assert c.command(ok, "")[0].startswith("CicsTask.WebExtracted web")
    for bad, why in (("WEB EXTRACT HOST(REC)", "HOST without HOSTLENGTH"),
                     ("WEB EXTRACT HOSTLENGTH(R)", "HOST without HOSTLENGTH"),
                     ("WEB EXTRACT HTTPMETHOD(REC)", "HTTPMETHOD without METHODLENGTH"),
                     ("WEB EXTRACT HTTPVERSION(REC)", "HTTPVERSION without VERSIONLEN"),
                     ("WEB EXTRACT PATH(REC)", "PATH without PATHLENGTH"),
                     ("WEB EXTRACT QUERYSTRING(REC)", "QUERYSTRING without QUERYSTRLEN"),
                     ("WEB EXTRACT SESSTOKEN(KEY) HOST(REC) HOSTLENGTH(R)", "client form"),
                     ("WEB EXTRACT HOSTTYPE(R)", "address format of the host"),
                     ("WEB EXTRACT URIMAP(REC)", "URIMAP the request matched"),
                     ("WEB EXTRACT REALM(REC)", "client form"),
                     ("WEB EXTRACT REALMLEN(R)", "client form")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")


def test_web_receive_reads_the_body_of_the_stated_request():
    """#4767 zECS (register X38), IBM WEB RECEIVE (server): CicsTask.webReceive takes MAXLENGTH and INTO's size; the body goes
    to INTO's start, LENGTH is the bytes returned, MEDIATYPE is blank-padded to its 56 bytes. SET (the pointer lane), NOTRUNCATE,
    the containers and every code-page option are refused by name, as is INTO without MAXLENGTH (IBM: INVREQ RESP2 16)."""
    c = _ChanCics()
    w = c.command("WEB RECEIVE INTO(REC) LENGTH(R) MAXLENGTH(R2) MEDIATYPE(REC) NOSRVCONVERT NOHANDLE", "")
    assert w[0].startswith("CicsTask.WebReceived web") and ".webReceive(" in w[0]
    body = " ".join(w)
    assert ".body() != null) {" in body and ".body().getBytes(CS)" in body and ".body().length()" in body
    assert '"%-56s"' in body and ".mediaType()" in body
    assert c.command("WEB RECEIVE INTO(REC) MAXLENGTH(R2) SRVCONVERT", "")[0].startswith("CicsTask.WebReceived web")
    for bad, why in (("WEB RECEIVE", "one of INTO / SET"),
                     ("WEB RECEIVE INTO(REC)", "INTO without MAXLENGTH"),
                     ("WEB RECEIVE INTO(REC) MAXLENGTH(R) SRVCONVERT NOSRVCONVERT", "both SRVCONVERT and NOSRVCONVERT"),
                     ("WEB RECEIVE SET(PTR) MAXLENGTH(R)", "SET without LENGTH"),
                     ("WEB RECEIVE INTO(REC) SET(PTR) MAXLENGTH(R) LENGTH(R)", "one of INTO / SET"),
                     ("WEB RECEIVE INTO(REC) MAXLENGTH(R) NOTRUNCATE", "NOTRUNCATE"),
                     ("WEB RECEIVE TOCONTAINER('C')", "container"),
                     ("WEB RECEIVE INTO(REC) MAXLENGTH(R) TOCHANNEL('C')", "container"),
                     ("WEB RECEIVE INTO(REC) MAXLENGTH(R) CHARACTERSET(REC)", "code-page conversion"),
                     ("WEB RECEIVE INTO(REC) MAXLENGTH(R) HOSTCODEPAGE(REC)", "code-page conversion"),
                     ("WEB RECEIVE INTO(REC) MAXLENGTH(R) CLNTCODEPAGE(REC)", "code-page conversion"),
                     ("WEB RECEIVE INTO(REC) MAXLENGTH(R) SERVERCONV(R)", "SERVERCONV"),
                     ("WEB RECEIVE INTO(REC) MAXLENGTH(R) BODYCHARSET(REC)", "character set"),
                     ("WEB RECEIVE INTO(REC) MAXLENGTH(R) TYPE(R)", "TYPE")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")


class _PtrCics(_ChanCics):
    """#4771 (X47): PTR a USAGE POINTER, OVER-PTR one a REDEFINES overlays, TBL-PTR one in a table, REC an alphanumeric."""

    SIZES = {**_ChanCics.SIZES, "INIT": 1, "TWO": 2}

    def __init__(self):
        super().__init__()
        import types

        from gitgalaxy.tools.cobol_to_java.det import layout as L
        from gitgalaxy.tools.cobol_to_java.det.gen import Gen

        items = {"PTR": L.Item(1, "PTR", "WORKING-STORAGE", usage="POINTER"),
                 "OVER-PTR": L.Item(1, "OVER-PTR", "WORKING-STORAGE", usage="POINTER"),
                 "TBL-PTR": L.Item(5, "TBL-PTR", "WORKING-STORAGE", usage="POINTER", occurs=3),
                 "REC": L.Item(1, "REC", "WORKING-STORAGE"), "INIT": L.Item(1, "INIT", "WORKING-STORAGE"),
                 "TWO": L.Item(1, "TWO", "WORKING-STORAGE")}  # fmt: skip
        self.g.resolve = lambda ref: items[ref.name]
        self.g.field_expr = lambda ref: f"f_{ref.name}"
        self.g.overlaid_pointers = {"OVER-PTR"}
        self.g.pointer_item = types.MethodType(Gen.pointer_item, self.g)


def test_getmain_and_freemain_work_on_task_storage_through_a_pointer():
    """#4771 (register X47), IBM GETMAIN / FREEMAIN: GETMAIN SET FLENGTH INITIMG puts the new block's handle in the pointer
    (LENGERR 1 sets it to zero); FREEMAIN DATAPOINTER releases it (INVREQ 1 for an address GETMAIN did not return). The
    pointer is a plain USAGE POINTER, INITIMG a one-byte data area; IBM's "no default initialization" makes INITIMG required."""
    out = _PtrCics().command("GETMAIN SET(PTR) FLENGTH(N) INITIMG(INIT) NOHANDLE", "")
    assert out[0] == "int[] storage1 = DetCics.getmain(task, f_PTR, INT(N), false, f_INIT);"
    assert out[1] == "OUTCOME(storage1[0], storage1[1]);"
    out = _PtrCics().command("GETMAIN SET(PTR) LENGTH(100) INITIMG(INIT) USERDATAKEY BELOW", "")
    assert out[0] == "int[] storage1 = DetCics.getmain(task, f_PTR, INT(100), true, f_INIT);"
    out = _PtrCics().command("FREEMAIN DATAPOINTER(PTR) RESP(R)", "")
    assert out == ["int[] storage1 = task.freemain(DetCics.pointerValue(f_PTR));", "OUTCOME(storage1[0], storage1[1]);"]
    for bad, why in (
        ("GETMAIN FLENGTH(N) INITIMG(INIT)", "without SET"),
        ("GETMAIN SET(PTR) INITIMG(INIT)", "one of FLENGTH / LENGTH"),
        ("GETMAIN SET(PTR) FLENGTH(N) LENGTH(N) INITIMG(INIT)", "one of FLENGTH / LENGTH"),
        ("GETMAIN SET(PTR) FLENGTH(N)", "without INITIMG"),
        ("GETMAIN SET(PTR) FLENGTH(N) INITIMG(X'00')", "INITIMG as a literal"),
        ("GETMAIN SET(PTR) FLENGTH(N) INITIMG(TWO)", "INITIMG is not one byte"),
        ("GETMAIN SET(PTR) FLENGTH(N) INITIMG(INIT) USERDATAKEY CICSDATAKEY", "both USERDATAKEY and CICSDATAKEY"),
        ("GETMAIN SET(PTR) FLENGTH(N) INITIMG(INIT) SHARED", "SHARED: SHARED storage"),
        ("GETMAIN SET(PTR) FLENGTH(N) INITIMG(INIT) NOSUSPEND", "NOSUSPEND: storage unavailable"),
        ("GETMAIN SET(REC) FLENGTH(N) INITIMG(INIT)", "not a plain USAGE POINTER"),
        ("GETMAIN SET(TBL-PTR) FLENGTH(N) INITIMG(INIT)", "not a plain USAGE POINTER"),
        ("GETMAIN SET(OVER-PTR) FLENGTH(N) INITIMG(INIT)", "REDEFINES overlays"),
        ("FREEMAIN", "without DATAPOINTER"),
        ("FREEMAIN DATA(REC)", "DATA: "),
        ("FREEMAIN DATAPOINTER(OVER-PTR)", "REDEFINES overlays"),
    ):
        with pytest.raises(C.CicsError, match=why):
            _PtrCics().command(bad, "")


def test_web_receive_set_puts_the_body_in_a_block_the_pointer_addresses():
    """#4771 (X47), IBM WEB RECEIVE (server) SET: the body goes into storage CICS hands the program (the pointer), LENGTH is
    the bytes returned and must be given; MAXLENGTH is optional with SET (all the remaining data)."""
    w = _PtrCics().command("WEB RECEIVE SET(PTR) LENGTH(R) MAXLENGTH(R2) MEDIATYPE(REC) NOSRVCONVERT NOHANDLE", "")
    assert w[0] == "CicsTask.WebReceived web1 = task.webReceive(INT(R2), Integer.MAX_VALUE);"
    assert "DetCics.receivedBlock(task, f_PTR, web1.body(), CS);" in " ".join(w) and "STORE(R, " in " ".join(w)
    w = _PtrCics().command("WEB RECEIVE SET(PTR) LENGTH(R)", "")
    assert w[0] == "CicsTask.WebReceived web1 = task.webReceive(Integer.MAX_VALUE, Integer.MAX_VALUE);"
    for bad, why in (("WEB RECEIVE SET(PTR) MAXLENGTH(R)", "SET without LENGTH"),
                     ("WEB RECEIVE SET(REC) LENGTH(R)", "not a plain USAGE POINTER"),
                     ("WEB RECEIVE SET(OVER-PTR) LENGTH(R)", "REDEFINES overlays"),
                     ("WEB RECEIVE INTO(REC) SET(PTR) LENGTH(R) MAXLENGTH(R)", "one of INTO / SET"),
                     ("WEB RECEIVE SET(PTR) LENGTH(R) NOTRUNCATE", "NOTRUNCATE")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            _PtrCics().command(bad, "")


def test_web_read_and_write_httpheader_are_the_servers_headers():
    """#4767 zECS (register X38), IBM WEB READ HTTPHEADER / WEB WRITE HTTPHEADER (server): READ takes the name area's text, its
    NAMELENGTH, VALUELENGTH and VALUE's size, writes VALUE and VALUELENGTH on NORMAL only; WRITE takes the name and value texts
    with both lengths and records the header (WEB-HEADER). The client form (SESSTOKEN) and a missing option are refused."""
    c = _ChanCics()
    r = c.command("WEB READ HTTPHEADER(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2) NOHANDLE", "")
    assert r[0].startswith("CicsTask.WebHeader web") and ".webReadHeader(Cobol.text(" in r[0]
    assert (
        ".resp() == 0) {" in " ".join(r)
        and ".value().getBytes(CS)" in " ".join(r)
        and ".value().length()" in " ".join(r)
    )
    w = c.command("WEB WRITE HTTPHEADER(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2) NOHANDLE", "")
    assert w[0].startswith("int[] web") and ".webWriteHeader(Cobol.text(" in w[0]
    for form in ("READ", "WRITE"):
        full = ["HTTPHEADER(REC)", "NAMELENGTH(R)", "VALUE(REC)", "VALUELENGTH(R2)"]
        for i, missing in enumerate(("header name", "NAMELENGTH", "VALUE", "VALUELENGTH")):
            # (no HTTPHEADER: the command is no longer this form, a WEB READ of no modelled kind)
            with pytest.raises(C.CicsError, match=f"WEB {form} not modelled" if i == 0 else f"without {missing}"):
                c.command(f"WEB {form} " + " ".join(full[:i] + full[i + 1 :]), "")
        with pytest.raises(C.CicsError, match="client form"):
            c.command(f"WEB {form} HTTPHEADER(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2) SESSTOKEN(KEY)", "")


def test_web_read_formfield_and_queryparm_are_the_requests_pairs():
    """#4940 (register X38), IBM WEB READ FORMFIELD / QUERYPARM (server): CicsTask.webReadParam takes the kind, the name area's
    text, NAMELENGTH, VALUELENGTH and VALUE's size; VALUE (cut to VALUELENGTH) and VALUELENGTH (the real length) are written
    when a value came back (NORMAL, LENGERR RESP2 5). SET, the code-page options and a missing option are refused by name."""
    c = _ChanCics()
    for kind in ("FORMFIELD", "QUERYPARM"):
        r = c.command(f"WEB READ {kind}(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2) NOHANDLE", "")
        text = " ".join(r)
        assert r[0].startswith("CicsTask.WebParam web") and f'.webReadParam("{kind}", Cobol.text(' in r[0]
        assert ".value() != null) {" in text and ".value().getBytes(CS)" in text and ".length()" in text
        full = [f"{kind}(REC)", "NAMELENGTH(R)", "VALUE(REC)", "VALUELENGTH(R2)"]
        for i, missing in enumerate(("the name", "NAMELENGTH", "VALUE", "VALUELENGTH")):
            with pytest.raises(C.CicsError, match=f"WEB READ not modelled" if i == 0 else f"without {missing}"):
                c.command("WEB READ " + " ".join(full[:i] + full[i + 1 :]), "")
        for bad, why in (("SET(REC)", "pointer lane"), ("HOSTCODEPAGE(R)", "code-page"), ("CHARACTERSET(R)", "code-page"),
                         ("CLNTCODEPAGE(R)", "code-page"), ("SESSTOKEN(KEY)", "only")):  # fmt: skip
            with pytest.raises(C.CicsError, match=why):
                c.command(f"WEB READ {kind}(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2) {bad}", "")


def test_web_browse_forms_are_the_requests_pairs():
    """#4940 (register X38), IBM WEB STARTBROWSE / READNEXT / ENDBROWSE HTTPHEADER, FORMFIELD, QUERYPARM (server): STARTBROWSE
    takes the kind and, for FORMFIELD / QUERYPARM, a start name with its NAMELENGTH (null for none); READNEXT takes both
    lengths and the areas' sizes and writes the pair's name, value and whole lengths; ENDBROWSE takes nothing. The client form
    (SESSTOKEN), a start name on HTTPHEADER, NAMELENGTH without a name, a name without NAMELENGTH, the code-page options and a
    missing READNEXT option are refused by name."""
    c = _ChanCics()
    for kind in ("HTTPHEADER", "FORMFIELD", "QUERYPARM"):
        s = c.command(f"WEB STARTBROWSE {kind} NOHANDLE", "")
        assert s[0].startswith("int[] web") and f'.webStartBrowse("{kind}", null, null)' in s[0]
        e = c.command(f"WEB ENDBROWSE {kind} NOHANDLE", "")
        assert e[0].startswith("int[] web") and f'.webEndBrowse("{kind}")' in e[0]
        n = c.command(f"WEB READNEXT {kind}(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2) NOHANDLE", "")
        text = " ".join(n)
        assert n[0].startswith("CicsTask.WebNext web") and f'.webReadNext("{kind}", ' in n[0]
        assert ".name() != null) {" in text and ".nameLength()" in text and ".valueLength()" in text
        full = [f"{kind}(REC)", "NAMELENGTH(R)", "VALUE(REC)", "VALUELENGTH(R2)"]
        for i, missing in enumerate((kind, "NAMELENGTH", "VALUE", "VALUELENGTH")):
            rest = [kind] if i == 0 else [full[0]]  # (the form word stays, bare when its own argument is missing)
            rest += [x for j, x in enumerate(full) if j not in (0, i)]
            with pytest.raises(C.CicsError, match=f"WEB READNEXT {kind} without {missing}"):
                c.command("WEB READNEXT " + " ".join(rest), "")
        with pytest.raises(C.CicsError, match="SESSTOKEN"):
            c.command(f"WEB READNEXT {kind}(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2) SESSTOKEN(KEY)", "")
        with pytest.raises(C.CicsError, match="SESSTOKEN|only|takes no option"):
            c.command(f"WEB ENDBROWSE {kind} SESSTOKEN(KEY)", "")
    named = c.command("WEB STARTBROWSE FORMFIELD(REC) NAMELENGTH(R) NOHANDLE", "")
    assert '.webStartBrowse("FORMFIELD", Cobol.text(' in named[0] and "Integer.valueOf(" in named[0]
    for bad, why in (("WEB STARTBROWSE HTTPHEADER(REC)", "not documented"),
                     ("WEB STARTBROWSE FORMFIELD(REC)", "without NAMELENGTH"),
                     ("WEB STARTBROWSE QUERYPARM NAMELENGTH(R)", "NAMELENGTH without a name"),
                     ("WEB STARTBROWSE HTTPHEADER SESSTOKEN(KEY)", "client form"),
                     ("WEB STARTBROWSE FORMFIELD HOSTCODEPAGE(R)", "code-page"),
                     ("WEB STARTBROWSE QUERYPARM CHARACTERSET(R)", "code-page"),
                     ("WEB STARTBROWSE QUERYPARM FORMFIELD", "option not modelled")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")


def test_define_query_delete_dcounter_pass_the_doubleword_limits():
    """#4770 zECS (register X45), IBM DEFINE / QUERY / DELETE DCOUNTER: CicsTask.defineDcounter(pool, name, value, min, max) --
    the unsigned doublewords as longs, IBM's defaults for what the command omits (VALUE 0, MINIMUM 0, MAXIMUM a doubleword of
    X'FF', which is -1L); queryDcounter writes VALUE / MINIMUM / MAXIMUM unsigned, on NORMAL only; DELETE DCOUNTER is
    DELETE COUNTER's call."""
    c = _ChanCics()
    assert c.command("DEFINE DCOUNTER(KEY) POOL('P') VALUE(R) MINIMUM(R) MAXIMUM(R) NOHANDLE", "")[0].endswith(
        "task.defineDcounter('P'.strip(), KEY.strip(), LONG(R), LONG(R), LONG(R));"
    )
    assert c.command("DEFINE DCOUNTER(KEY) NOHANDLE", "")[0].endswith('defineDcounter("", KEY.strip(), 0L, 0L, -1L);')
    assert c.command("DEFINE DCOUNTER(KEY) VALUE(R) NOHANDLE", "")[0].endswith("KEY.strip(), LONG(R), 0L, -1L);")
    q = c.command("QUERY DCOUNTER(KEY) VALUE(REC) MINIMUM(REC) MAXIMUM(REC) NOHANDLE", "")
    assert q[0].startswith("long[] counter") and q[0].endswith('queryDcounter("", KEY.strip(), true);')
    assert sum("Long.toUnsignedString" in x for x in q) == 3 and q[-1].startswith("OUTCOME((int) counter")
    assert c.command("QUERY DCOUNTER(KEY) VALUE(REC) NOHANDLE", "")[0].endswith(", false);")  # (no limits asked for)
    assert ".deleteCounter(" in c.command("DELETE DCOUNTER(KEY) NOHANDLE", "")[0]


def test_define_query_counter_pass_the_fullword_limits():
    """#5039 (register X50), IBM DEFINE / QUERY COUNTER: CicsTask.defineCounter(pool, name, value, min, max) --
    the signed fullwords, IBM's defaults for what the command omits (VALUE 0, MINIMUM 0, MAXIMUM X'7FFFFFFF', which
    is 2147483647); queryCounter writes VALUE / MINIMUM / MAXIMUM on NORMAL only; GET COUNTER takes INCREMENT and WRAP."""
    c = _ChanCics()
    assert c.command("DEFINE COUNTER(KEY) POOL('P') VALUE(R) MINIMUM(R) MAXIMUM(R) NOHANDLE", "")[0].endswith(
        "task.defineCounter('P'.strip(), KEY.strip(), INT(R), INT(R), INT(R));"
    )
    assert c.command("DEFINE COUNTER(KEY) NOHANDLE", "")[0].endswith(
        'defineCounter("", KEY.strip(), 0, 0, 2147483647);'
    )
    assert c.command("DEFINE COUNTER(KEY) VALUE(R) NOHANDLE", "")[0].endswith("KEY.strip(), INT(R), 0, 2147483647);")
    q = c.command("QUERY COUNTER(KEY) VALUE(REC) MINIMUM(REC) MAXIMUM(REC) NOHANDLE", "")
    assert q[0].startswith("int[] counter") and q[0].endswith('queryCounter("", KEY.strip(), true);')
    assert sum("BigDecimal.valueOf(counter" in x for x in q) == 3 and q[-1].startswith("OUTCOME(counter")
    assert c.command("QUERY COUNTER(KEY) VALUE(REC) NOHANDLE", "")[0].endswith(", false);")  # (no limits asked for)
    w = c.command("GET COUNTER(KEY) VALUE(REC) INCREMENT(R) WRAP NOHANDLE", "")
    assert w[0].startswith("long[] counter") and w[0].endswith("LONG(R), true);")


def test_get_dcounter_takes_an_increment_and_refuses_what_it_does_not_model():
    """#4767 zECS (register X30), IBM GET DCOUNTER: CicsTask.getCounter(pool, name[, increment]) -- VALUE written on NORMAL
    only, the increment read from its data area (omitted: the one-argument form, IBM's default 1); WRAP is accepted (it acts at a
    maximum the run does not state). REDUCE, COMPAREMIN / COMPAREMAX and NOSUSPEND are refused by name."""
    c = _ChanCics()
    w = c.command("GET DCOUNTER(KEY) VALUE(REC) INCREMENT(R) WRAP NOHANDLE", "")
    assert (w[0].startswith("long[] counter") and '.getCounter("", ' in w[0] and w[0].count(",") == 3) and w[
        0
    ].endswith(
        "LONG(R), true);"
    )  # (pool, name, increment, wrap) -- #4770 (X45): WRAP acts at DEFINE DCOUNTER's maximum
    assert (
        c.command("GET DCOUNTER(KEY) VALUE(REC) INCREMENT(R) NOHANDLE", "")[0].count(",") == 2
    )  # (pool, name, increment)
    assert c.command("GET DCOUNTER(KEY) VALUE(REC) WRAP NOHANDLE", "")[0].endswith(
        ", 1L, true);"
    )  # (the default increment)
    assert "Long.toUnsignedString" in "".join(w)  # the doubleword VALUE is unsigned
    plain = c.command("GET DCOUNTER(KEY) VALUE(REC) NOHANDLE", "")
    assert plain[0].count(",") == 1  # (pool, name: the default increment)
    assert c.command("GET COUNTER(KEY) VALUE(REC)", "")[0].count(",") == 1  # (the fullword form as before)
    for bad, why in (
        ("GET DCOUNTER(KEY) INCREMENT(R)", "without VALUE"),
        ("GET DCOUNTER(KEY) COUNTER(KEY) VALUE(REC)", "one of COUNTER and DCOUNTER"),
    ):  # fmt: skip (REDUCE / COMPARE / NOSUSPEND: #5039, X53)
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")


def test_web_parse_url_is_a_pure_task_call():
    """#4767 zECS (register X36), IBM WEB PARSE URL: CicsTask.webParse takes the URL area's text and URLLENGTH apart, with
    HOSTLENGTH / PATHLENGTH / QUERYSTRLEN read first (null when not given) and the areas' sizes; on NORMAL only the scheme
    (SCHEMENAME), the pieces, their lengths and PORTNUMBER are written; every condition through RESP / HANDLE CONDITION."""
    c = _ChanCics()
    p = c.command(
        "WEB PARSE URL(REC) URLLENGTH(R) SCHEMENAME(AREA) HOST(REC) HOSTLENGTH(R2) PORTNUMBER(R) NOHANDLE", ""
    )
    assert p[0].startswith("CicsTask.WebParsed web") and ".webParse(Cobol.text(" in p[0]
    assert ", null, 0, null, 0);" in p[0] and "Integer.valueOf(" in p[0]  # (no PATH, no QUERYSTRING)
    body = " ".join(p)
    assert ".resp() == 0) {" in body and ".scheme(), CS)" in body and ".host(), CS)" in body
    assert ".host().length()" in body and ".port()" in body and any("OUTCOME(web" in x for x in p)
    q = c.command(
        "WEB PARSE URL(REC) URLLENGTH(R) PATH(REC) PATHLENGTH(R) QUERYSTRING(REC) QUERYSTRLEN(R) NOHANDLE", ""
    )
    assert ".path(), CS)" in " ".join(q) and ".query(), CS)" in " ".join(q)
    for bad, why in (("WEB PARSE URL(REC)", "without URLLENGTH"),
                     ("WEB PARSE URL(REC) URLLENGTH(R) HOST(REC)", "HOST without HOSTLENGTH"),
                     ("WEB PARSE URL(REC) URLLENGTH(R) PATHLENGTH(R)", "PATH without PATHLENGTH"),
                     ("WEB PARSE URL(REC) URLLENGTH(R) QUERYSTRING(REC)", "QUERYSTRING without QUERYSTRLEN"),
                     ("WEB PARSE URL(REC) URLLENGTH(R) HOSTTYPE(R)", "IPv6 host is refused")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")


def test_web_open_converse_close_are_the_tasks_http_client():
    """#4767 zECS (register X35), IBM WEB OPEN / WEB CONVERSE / WEB CLOSE: OPEN by URIMAP or HOST / HOSTLENGTH /
    PORTNUMBER / SCHEME (CicsTask.webOpenUrimap / webOpenHost), the SESSTOKEN written on NORMAL only; CONVERSE hands
    each area's text and length to CicsTask.webConverse (MAXLENGTH defaulting to INTO's length) and writes INTO,
    TOLENGTH, STATUSCODE, STATUSTEXT and MEDIATYPE only when a response came back; CLOSE: CicsTask.webClose. Every
    condition through RESP / HANDLE CONDITION. What IBM leaves open, or zECS does not use, is refused by name."""
    c = _ChanCics()
    u = c.command("WEB OPEN SESSTOKEN(KEY) URIMAP(REC) NOHANDLE", "")
    assert u[0].startswith("CicsTask.WebOpened web") and ".webOpenUrimap(" in u[0]
    assert ".resp() == 0) DetCics.putText(" in u[1] and any("OUTCOME(web" in x for x in u)
    h = c.command("WEB OPEN HOST(REC) HOSTLENGTH(R) PORTNUMBER(R2) SCHEME(R) SESSTOKEN(KEY) NOHANDLE", "")
    assert ".webOpenHost(Cobol.text(" in h[0] and ", true, " in h[0]
    h2 = c.command("WEB OPEN HOST(REC) HOSTLENGTH(R) SCHEME(R) SESSTOKEN(KEY) NOHANDLE", "")
    assert ", 0, false, " in h2[0]
    v = c.command(
        "WEB CONVERSE SESSTOKEN(KEY) METHOD(R) PATH(REC) PATHLENGTH(R) FROM(AREA) FROMLENGTH(R) "
        "MEDIATYPE(REC) INTO(AREA) TOLENGTH(R2) STATUSCODE(R) STATUSLEN(R2) STATUSTEXT(REC) NOHANDLE",
        "",
    )
    assert v[0].startswith("CicsTask.WebResponse web") and ".webConverse(Cobol.text(" in v[0]
    assert ", 20, " in v[0] and v[0].endswith(", CS);")  # (no MAXLENGTH: INTO's 20 bytes)
    assert v[1].endswith(".body() != null) {") and "throw new DetCics.PastFrom(" in v[2] and "WEB CONVERSE INTO" in v[2]
    assert "DetCics.put(f_AREA, web" in v[2]
    body = " ".join(v)
    assert ".toLength()" in body and ".status()" in body and ".statusText().getBytes(CS)" in body
    assert ".mediaType(), CS)" in body and any("OUTCOME(web" in x for x in v)
    q = c.command(
        "WEB CONVERSE SESSTOKEN(KEY) METHOD(R) PATH(REC) PATHLENGTH(R) QUERYSTRING(REC) QUERYSTRLEN(R) "
        "INTO(AREA) MAXLENGTH(R2) TOLENGTH(R2) NOOUTCONVERT NOHANDLE",
        "",
    )
    assert "null, 0, null, " in q[0]  # (no FROM, no MEDIATYPE)
    k = c.command("WEB CLOSE SESSTOKEN(KEY) NOHANDLE", "")
    assert k[0].startswith("int[] web") and ".webClose(Cobol.text(" in k[0]
    for bad, why in (("WEB OPEN URIMAP(REC)", "without SESSTOKEN"),
                     ("WEB OPEN SESSTOKEN(KEY)", "one of URIMAP and HOST"),
                     ("WEB OPEN SESSTOKEN(KEY) URIMAP(REC) HOST(REC) HOSTLENGTH(R) SCHEME(R)", "one of URIMAP and HOST"),
                     ("WEB OPEN SESSTOKEN(KEY) HOST(REC) SCHEME(R)", "HOST without HOSTLENGTH"),
                     ("WEB OPEN SESSTOKEN(KEY) HOST(REC) HOSTLENGTH(R)", "IBM states no default scheme"),
                     ("WEB OPEN SESSTOKEN(KEY) URIMAP(REC) PORTNUMBER(R)", "PORTNUMBER without HOST"),
                     ("WEB OPEN SESSTOKEN(KEY) URIMAP(REC) CERTIFICATE(REC)", "TLS client certificates"),
                     ("WEB CONVERSE SESSTOKEN(KEY) INTO(AREA)", "without METHOD"),
                     ("WEB CONVERSE SESSTOKEN(KEY) METHOD(R)", "without INTO"),
                     ("WEB CONVERSE SESSTOKEN(KEY) METHOD(R) INTO(AREA) PATH(REC)", "PATH without PATHLENGTH"),
                     ("WEB CONVERSE SESSTOKEN(KEY) METHOD(R) INTO(AREA) FROMLENGTH(R)", "FROM without FROMLENGTH"),
                     ("WEB CONVERSE SESSTOKEN(KEY) METHOD(R) INTO(AREA) NOOUTCONVERT NOCLICONVERT",
                      "more than one conversion option"),
                     ("WEB CONVERSE SESSTOKEN(KEY) METHOD(R) INTO(AREA) CHARACTERSET(REC)", "code-page conversion"),
                     ("WEB CONVERSE SESSTOKEN(KEY) METHOD(R) INTO(AREA) NOTRUNCATE", "kept for later RECEIVEs"),
                     ("WEB CONVERSE SESSTOKEN(KEY) METHOD(R) SET(PTR)", "held in CICS storage"),
                     ("WEB CONVERSE SESSTOKEN(KEY) URIMAP(REC) POST INTO(AREA)", "request URIMAP"),
                     ("WEB CLOSE", "without SESSTOKEN")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")


def test_inquire_urimap_direct_form_and_inquire_program_status():
    """#4768 zECS (register X34). IBM INQUIRE URIMAP, the direct form: URIMAP(name) with no browse option reads that
    definition among the stated installed ones (CicsTask.inquireUrimap), PATH / TRANSACTION written only on NORMAL,
    NOTFND RESP2 3 through RESP / HANDLE CONDITION. IBM INQUIRE PROGRAM STATUS: the definition's CVDA (CicsTask.programStatus),
    written only on NORMAL."""
    c = _ChanCics()
    d = c.command("INQUIRE URIMAP(REC) PATH(REC) TRANSACTION(KEY) NOHANDLE", "")
    assert d[0].startswith("int[] urimap") and ".inquireUrimap(" in d[0] and d[1].endswith("[0] == 0) {")
    assert sum("DetCics.putText(" in x for x in d) == 2 and "task.urimapPath()" in " ".join(d)
    assert "task.urimapName()" not in " ".join(d)  # (the direct form's URIMAP is the name it reads)
    assert any("OUTCOME(urimap" in x for x in d)
    p = c.command("INQUIRE PROGRAM('P') STATUS(REC) RESP(R) NOHANDLE", "")
    assert p[0].startswith("int resp") and ".inquireProgram(" in p[0]
    assert any(".programStatus(" in x and "if (resp" in x for x in p)
    assert any("OUTCOME(resp" in x for x in p)
    for bad, why in (("INQUIRE URIMAP PATH(REC)", "without URIMAP, START, NEXT or END"),
                     ("INQUIRE URIMAP NOHANDLE", "without URIMAP, START, NEXT or END"),
                     ("INQUIRE URIMAP(REC) HOST(REC)", "only the URIMAP's name, PATH and TRANSACTION")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(bad, "")


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("GET CONTAINER(CN) INTO(AREA) INTOCODEPAGE('UTF-8')", "IANA code-page names"),
        ("PUT CONTAINER(CN) FROM(REC) FROMCODEPAGE('ISO-8859-1')", "IANA code-page names"),
        ("GET CONTAINER(CN) INTO(AREA) INTOCCSID(1140) CONVERTST(DFHVALUE(NOCONVERT))", "one target code page"),
        ("GET CONTAINER(CN) INTO(AREA) CONVERTST(DFHVALUE(CONVERT))", "only DFHVALUE"),
        ("GET CONTAINER(CN) INTO(AREA) CCSID(WS-CCSID)", "CCSID without CONVERTST"),
        ("GET CONTAINER(CN) NODATA BYTEOFFSET(4)", "BYTEOFFSET needs INTO"),  # #5005 (X17)
        ("GET CONTAINER(CN) SET(PTR) FLENGTH(FL) BYTEOFFSET(4)", "BYTEOFFSET needs INTO"),
        ("GET CONTAINER(CN) INTO(AREA) BYTEOFFSET(4) INTOCCSID(500)", "BYTEOFFSET with INTOCCSID"),
        ("GET CONTAINER(CN) INTO(AREA) BYTEOFFSET(4) CONVERTST(DFHVALUE(NOCONVERT))", "BYTEOFFSET with CONVERTST"),
        (
            "GET CONTAINER(CN) INTO(AREA) BYTEOFFSET(4) CONVERTST(DFHVALUE(NOCONVERT)) CCSID(WS-CCSID)",
            "BYTEOFFSET with CONVERTST",
        ),
        ("PUT CONTAINER(CN) FROM(REC) PREPEND APPEND", "APPEND and PREPEND together"),
        ("PUT CONTAINER(CN) FROM(REC) APPEND PREPEND", "APPEND and PREPEND together"),
        ("GET CONTAINER(CN) FLENGTH(FL)", "one of INTO / NODATA"),
        ("PUT CONTAINER(CN) FROM(REC) BIT CHAR", "one data type"),
        ("PUT CONTAINER(CN) FROM(REC) DATATYPE(WS-TYPE)", "DFHVALUE"),
        ("MOVE CONTAINER(A) AS(B) CONTAINERTYPE(X)", "CONTAINERTYPE"),
    ],
)
def test_what_the_container_commands_do_not_model_is_refused_by_name(text, why):
    """#4270: CHAR conversion (FROMCCSID / INTOCCSID / code pages / CONVERTST), SET, BYTEOFFSET, PREPEND,
    MOVE CONTAINER and the container browse are refused with their reason, never accepted and ignored."""
    with pytest.raises(C.CicsError, match=why):
        _ChanCics().command(text, "")


def test_the_container_conditions_are_known_by_resp_and_abend_code():
    """IBM: CONTAINERERR is RESP 110 (abend AEZJ, "CONTAINERERR condition not handled"), CHANNELERR 122 (AEZV)."""
    assert C.DFHRESP["CONTAINERERR"] == 110 and C.DFHRESP["CHANNELERR"] == 122
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA

    # DetCics.condition / resp delegate to the generated CicsSpec (#4270 spec PR 4)
    rt = (Path(C.__file__).parent / "cobolrt/cics/DetCics.java").read_text(encoding="utf-8") + CICS_SPEC_JAVA
    assert 'case 110 -> "CONTAINERERR";' in rt and 'case "CHANNELERR" -> 122;' in rt
    assert 'case "CONTAINERERR" -> "AEZJ";' in CICS_SPEC_JAVA and 'case "CHANNELERR" -> "AEZV";' in CICS_SPEC_JAVA


# ---- #4270 slice 2: interval control -----------------------------------------------------------------------------
def test_start_builds_its_request_and_takes_its_outcome():
    """IBM, EXEC CICS START: TRANSID, INTERVAL / TIME (a literal's leading zeros dropped: no octal), AFTER / AT HOURS
    MINUTES SECONDS (null: not given), TERMID, REQID, the data options, PROTECT; FROM's first LENGTH bytes in the
    region's page; INVREQ's RESP2 4 / 5 / 6 through the outcome."""
    out = _ChanCics().command("START TRANSID('GT02') INTERVAL(0) FROM(REC) LENGTH(20) RESP(R)", "")
    assert out == ["CicsTask.StartResult start1 = task.startRequest('GT02'.strip()).interval(0)"
                   ".from(DetCics.toRegion(DetCics.startData(f_REC, INT(20)), CS, REGION)).issue();",
                   "OUTCOME(DetCics.resp(start1.resp()), start1.resp2());"]  # fmt: skip
    out = _ChanCics().command("START TRANSID(TR) TIME(093000) TERMID(TM) REQID(RQ) PROTECT RTRANSID('GT03') "
                              "RTERMID(TM) QUEUE(Q) NOHANDLE", "")  # fmt: skip
    assert out[0] == ("CicsTask.StartResult start1 = task.startRequest(TR.strip()).time(93000).termid(TM.strip())"
                      ".reqid(RQ.strip()).rtransid('GT03'.strip()).rtermid(TM.strip()).queue(Q.strip()).protect(true)"
                      ".issue();")  # fmt: skip
    assert ".after(null, 1, null).issue();" in _ChanCics().command("START TRANSID('S') AFTER MINUTES(1)", "")[0]
    assert ".at(INT(H), null, 30).issue();" in _ChanCics().command("START TRANSID('S') AT HOURS(H) SECONDS(30)", "")[0]
    assert _ChanCics().command("START TRANSID('S')", "")[0].endswith("task.startRequest('S'.strip()).issue();")


def test_retrieve_moves_the_data_its_length_and_the_values_asked_for():
    """IBM, EXEC CICS RETRIEVE: INTO takes at most LENGTH's value (else INTO's length), back in the storage's page;
    LENGTH is set to the data's length on NORMAL / LENGERR; RTRANSID / QUEUE padded into their areas; CANCEL REQID."""
    out = _ChanCics().command("RETRIEVE INTO(AREA) LENGTH(LN) RESP(R) RESP2(R2)", "")
    assert out == ["CicsTask.RetrieveResult retrieved1 = task.retrieve(INT(LN), false, false, false);",
                   "if (retrieved1.data() != null) DetCics.put(f_AREA, DetCics.fromRegion(retrieved1.data(), REGION, CS));",
                   "if (retrieved1.length() >= 0) STORE(LN, BigDecimal.valueOf(retrieved1.length()));",
                   "OUTCOME(DetCics.resp(retrieved1.resp()), 0);"]  # fmt: skip
    assert (
        _ChanCics().command("RETRIEVE INTO(AREA) NOHANDLE", "")[0].endswith("task.retrieve(20, false, false, false);")
    )
    out = _ChanCics().command("RETRIEVE RTRANSID(REC) QUEUE(AREA)", "")
    assert out[:3] == ["CicsTask.RetrieveResult retrieved1 = task.retrieve(null, true, false, true);",
                       "if (retrieved1.rtransid() != null) DetCics.putPadded(f_REC, retrieved1.rtransid(), CS);",
                       "if (retrieved1.queue() != null) DetCics.putPadded(f_AREA, retrieved1.queue(), CS);"]  # fmt: skip
    assert _ChanCics().command("CANCEL REQID('R1') RESP(R)", "") == [
        "int cancelled1 = DetCics.resp(task.cancel('R1'.strip()));",
        "OUTCOME(cancelled1, 0);",
    ]


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("START TRANSID('T') CHANNEL(CH) FROM(AREA)", "START CHANNEL with FROM"),
        ("START TRANSID('T') CHANNEL(CH) INTERVAL(5)", "START CHANNEL with INTERVAL"),
        ("START TRANSID('T') CHANNEL(CH) REQID('R')", "START CHANNEL with REQID"),
        ("START TRANSID('T') USERID(U)", "surrogate security"),
        ("START TRANSID('T') SYSID(S)", "remote system"),
        ("START TRANSID('T') NOCHECK", "NOCHECK"),
        ("START TRANSID('T') INTERVAL(1) TIME(1)", "one expiry option"),
        ("START TRANSID('T') HOURS(1)", "go with AFTER / AT"),
        ("START TRANSID('T') AFTER", "go with AFTER / AT"),
        ("START INTERVAL(0)", "without TRANSID"),
        ("START TRANSID('T') LENGTH(4)", "LENGTH without FROM"),
        ("RETRIEVE INTO(AREA) WAIT", "WAIT"),
        ("RETRIEVE LENGTH(LN)", "without INTO"),
        ("CANCEL TRANSID('T')", "only CANCEL REQID"),
        ("CANCEL", "only CANCEL REQID"),
        ("FETCH CHILD(REC) NOSUSPEND TIMEOUT(5)", "FETCH NOSUSPEND and TIMEOUT together"),
        ("FETCH ANY", "FETCH ANY without ANY"),
        ("FREE CHILD", "FREE CHILD without CHILD"),
    ],
)
def test_what_interval_control_does_not_model_is_refused_by_name(text, why):
    """#4270 slice 2: START CHANNEL / USERID / SYSID / NOCHECK / ATTACH, RETRIEVE SET / WAIT and CANCEL of anything
    but a REQID are refused with their reason."""
    with pytest.raises(C.CicsError, match=why):
        _ChanCics().command(text, "")


def test_run_transid_puts_the_child_token_and_takes_its_outcome():
    """#4270 slice 2, IBM RUN TRANSID: CHILD's area gets the child token on NORMAL; TRANSIDERR's RESP2 through the
    outcome."""
    out = _ChanCics().command("RUN TRANSID('GT24') CHILD(REC) RESP(R) RESP2(R2)", "")
    assert out == ["CicsTask.RunResult run1 = task.runTransid('GT24'.strip());",
                   "if (run1.child() != null) DetCics.putPadded(f_REC, run1.child(), CS);",
                   "OUTCOME(DetCics.resp(run1.resp()), run1.resp2());"]  # fmt: skip


def test_fetch_waits_times_out_or_not_and_writes_what_the_child_left():
    """#4950: FETCH ANY / CHILD on CicsTask.fetch -- NOSUSPEND, TIMEOUT or neither (it waits) -- and on NORMAL the token
    (ANY), the reply channel's name (CHANNEL), the abend code (ABCODE, an abended child only) and COMPSTATUS's CVDA."""
    out = _ChanCics().command("FETCH ANY(REC) CHANNEL(CH) COMPSTATUS(C) ABCODE(AB) NOSUSPEND RESP(R)", "")
    assert out[0] == 'CicsTask.FetchResult fetch1 = task.fetch(null, "NOSUSPEND", 0, true);'
    assert out[1:7] == ["if (fetch1.child() != null) {", "    DetCics.putPadded(f_REC, fetch1.child(), CS);",
                        "    DetCics.putPadded(f_CH, fetch1.channel(), CS);",
                        "    if (fetch1.abcode() != null) DetCics.putPadded(f_AB, fetch1.abcode(), CS);",
                        out[5], "}"]  # fmt: skip
    assert "fetch1.compstatus()" in out[5] and out[-1] == "OUTCOME(DetCics.resp(fetch1.resp()), fetch1.resp2());"
    assert (
        _ChanCics().command("FETCH CHILD(REC)", "")[0]
        == ('CicsTask.FetchResult fetch1 = task.fetch(DetCics.str(f_REC, CS), "WAIT", 0, false);')
        or "task.fetch(" in _ChanCics().command("FETCH CHILD(REC)", "")[0]
    )
    timed = _ChanCics().command("FETCH CHILD(REC) TIMEOUT(250)", "")[0]
    assert '"TIMEOUT", 250, false);' in timed and "WAIT" not in timed


def test_free_child_delay_and_start_channel():
    """#4950: FREE CHILD on CicsTask.freeChild; DELAY on CicsTask.delay (INTERVAL / FOR as milliseconds, TIME refused at
    run time in a task with children); START CHANNEL hands the channel's name to the request."""
    assert (
        _ChanCics()
        .command("FREE CHILD(REC) RESP(R)", "")[0]
        .startswith("CicsTask.FetchResult freed1 = task.freeChild(")
    )

    # #6271 (X72): line 0 reads the scenario's planned fault, line 1 performs the delay when none is planned
    def delay(cmd: str) -> str:
        out = _ChanCics().command(cmd, "")
        assert out[0] == 'int[] planned1 = task.planned("DELAY", "-");'
        return out[1].removeprefix("if (planned1[0] == 0) ")

    assert delay("DELAY FOR SECONDS(3)") == (
        'task.delay(CicsTask.delayMillis(null, null, null, Long.valueOf(3), null), "DELAY out of range");'
    )
    assert delay("DELAY INTERVAL(000105)") == (
        'task.delay(CicsTask.delayMillis(Long.valueOf(105), null, null, null, null), "DELAY out of range");'
    )
    assert delay("DELAY TIME(120000)") == 'task.delay(-1L, "DELAY TIME (a time of day)");'
    assert delay("DELAY") == 'task.delay(0L, "DELAY");'
    start = _ChanCics().command("START TRANSID('T') CHANNEL('CIPCHAN')", "")[0]
    assert ".channel('CIPCHAN'.strip())" in start or ".channel(" in start


def test_the_interval_conditions_are_known_by_resp():
    """IBM RESP values: TERMIDERR 11, IOERR 17, TRANSIDERR 28, ENDDATA 29, ENVDEFERR 56 -- both ways in DetCics."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA

    # DetCics.condition / resp delegate to the generated CicsSpec (#4270 spec PR 4)
    rt = (Path(C.__file__).parent / "cobolrt/cics/DetCics.java").read_text(encoding="utf-8") + CICS_SPEC_JAVA
    for name in ("TERMIDERR", "TRANSIDERR", "ENDDATA", "ENVDEFERR"):
        assert f'case {C.DFHRESP[name]} -> "{name}";' in rt and f'case "{name}" -> {C.DFHRESP[name]};' in rt
    assert 'case "IOERR" -> 17;' in rt


def test_a_channel_program_translates_whole(tmp_path):
    """#4270: a program that PUTs and GETs containers, LINKs with a channel and reads its current channel's name
    translates with no hole (the census's GET / PUT CONTAINER programs were refused whole)."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "T2.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. T2.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n       01  WS-CH                 PIC X(16) VALUE 'CH1'.\n"
        "       01  WS-AREA               PIC X(10) VALUE 'ABCDEFGHIJ'.\n"
        "       01  WS-LEN                PIC S9(8) COMP VALUE 10.\n"
        "       01  WS-RESP               PIC S9(8) COMP.\n       PROCEDURE DIVISION.\n"
        "           EXEC CICS PUT CONTAINER('IN') CHANNEL(WS-CH)\n"
        "                     FROM(WS-AREA) CHAR END-EXEC\n"
        "           EXEC CICS LINK PROGRAM('T3') CHANNEL(WS-CH) END-EXEC\n"
        "           EXEC CICS GET CONTAINER('OUT') CHANNEL(WS-CH)\n"
        "                     INTO(WS-AREA) FLENGTH(WS-LEN) RESP(WS-RESP)\n"
        "           END-EXEC\n"
        "           EXEC CICS DELETE CONTAINER('IN') CHANNEL(WS-CH)\n           END-EXEC\n"
        "           EXEC CICS ASSIGN CHANNEL(WS-CH) END-EXEC\n           EXEC CICS RETURN END-EXEC.\n",
        encoding="utf-8",
    )
    vsam = tmp_path / "proj/src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class T2Service {\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    r = P.translate(tmp_path / "T2.cbl", [], stub, "com.x", {}, tmp_path / "proj")
    assert (r.stats["statements"], r.stats["translated"], r.stats["holes"]) == (6, 6, [])
    for call in (
        "task.putContainer(",
        "task.linkChannel(",
        "task.getContainer(",
        "task.deleteContainer(",
        "task.assignChannel()",
    ):
        assert call in r.java, call


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
        ["    PERFORM P2 THRU.", "    GOBACK.", "P2.", "    EXIT."],  # GOBACK and P2 were dropped
        ["    CALL 'X' USING BY REFERENCE.", "    GOBACK."],
        ["    SET A TO.", "    GOBACK."],
    ],
)
def test_a_parse_error_outside_the_procedure_node_refuses_the_program(body):
    pytest.importorskip("tree_sitter_language_pack")
    with pytest.raises(E.ExprError, match="does not parse at line"):
        _proc(body)


@pytest.mark.parametrize(
    "cond",
    [
        ["    IF A NOT", "        = 'B'"],  # #4674: NOT at the end of a line, its operator on the next
        ["    IF A NOT", "        EQUAL TO 'B'"],
        ["    IF A", "        NOT", "        = 'B'"],
        ["    IF A = 'B' OR NOT", "        < 'C'"],
        ["    IF A = 'B' AND", "        NOT < 'C'"],  # an AND at a line end, the NOT (and operator) after it
        ["    IF A = 'B' AND", "        NOT", "        < 'C'"],
        ["    IF NOT", "        A = 'B'"],
        ["    IF (ZERO + 3) / 12 NOT > 1"],  # #4656: ZERO is a number inside arithmetic, not a class word
        ["    IF (ZERO / 12) * 2 > 1"],
        ["    IF (3 + ZERO) > 1"],
    ],
)
def test_a_relation_split_across_lines_or_with_zero_in_arithmetic_parses(cond):
    pytest.importorskip("tree_sitter_language_pack")
    proc = _proc([*cond, "        DISPLAY 'Y'", "    END-IF.", "    DISPLAY 'AFTER'.", "    GOBACK."])
    stmts = [s for p in proc.paragraphs for s in S.walk(p.body)]
    cond_ = stmts[0].data["cond"]
    assert stmts[0].kind == "IF" and not (isinstance(cond_, tuple) and cond_[0] == "UNPARSED"), cond_
    assert [s.kind for s in stmts if s.kind != "IF"] == ["DISPLAY", "DISPLAY", "GOBACK"]
    # the break moved with the NOT, not the statements: AFTER keeps its own line (head is 7 lines, then cond)
    assert stmts[-2].line == 7 + len(cond) + 3


# #4682: NOT and its relational operator split by line breaks anywhere, before every operator form: the program
# translates (the break is whitespace) and the relation is the right one, however many lines the operator takes
_NOT_OPS = [
    (["<"], "<"), ([">"], ">"), (["="], "="), (["<="], "<="), ([">="], ">="),
    (["LESS", "THAN"], "<"), (["GREATER", "THAN"], ">"), (["EQUAL", "TO"], "="), (["EQUAL"], "="),
    (["LESS", "THAN", "OR", "EQUAL", "TO"], "<="), (["LESS", "OR", "EQUAL"], "<="),
    (["GREATER", "THAN", "OR", "EQUAL", "TO"], ">="), (["GREATER", "OR", "EQUAL"], ">="),
    (["IS", "LESS", "THAN"], "<"), (["IS", "EQUAL", "TO"], "="), (["IS", "GREATER", "THAN", "OR", "EQUAL"], ">="),
]  # fmt: skip


def _breaks(words: list[str], head: str) -> list[list[str]]:
    """The condition `head NOT <words> 3` with a line break after every word boundary at once, and at each one alone
    (no break at all is the control)."""
    full = [head, "NOT", *words, "3"]
    shapes = [[" ".join(full)], [*full[:-1], full[-1]]]
    shapes += [[" ".join(full[:k]), " ".join(full[k:])] for k in range(1, len(full))]
    return shapes


def _expect_negated(cond, op: str) -> bool:
    """`A NOT op B` is the relation's opposite (or its Not): evaluate the AST's shape, not Java."""
    inverse = {"<": ">=", ">": "<=", "=": "<>", "<=": ">", ">=": "<"}
    rel = cond.cond if type(cond).__name__ == "Not" else cond
    return type(rel).__name__ == "Rel" and (
        (type(cond).__name__ == "Not" and rel.op == op) or (type(cond).__name__ == "Rel" and rel.op == inverse[op])
    )


@pytest.mark.parametrize(("words", "op"), _NOT_OPS, ids=[" ".join(w) for w, _ in _NOT_OPS])
def test_not_and_its_operator_split_at_any_word_boundary_translate(words, op):
    pytest.importorskip("tree_sitter_language_pack")
    for shape in _breaks(words, "D0"):
        proc = _proc([f"    IF {shape[0]}", *[f"        {x}" for x in shape[1:]], "        DISPLAY 'Y'", "    END-IF.",
                      "    GOBACK."])  # fmt: skip
        stmts = [s for p in proc.paragraphs for s in S.walk(p.body)]
        cond = stmts[0].data["cond"]
        assert stmts[0].kind == "IF" and not (isinstance(cond, tuple) and cond[0] == "UNPARSED"), (shape, cond)
        assert [s.kind for s in stmts] == ["IF", "DISPLAY", "GOBACK"], shape
        assert _expect_negated(cond, op), (shape, cond)
        assert stmts[-1].line == 7 + len(shape) + 3, shape  # the break moved, the statements kept their lines


@pytest.mark.parametrize(
    "pred", ["NUMERIC", "ALPHABETIC", "ALPHABETIC-LOWER", "ALPHABETIC-UPPER", "POSITIVE", "NEGATIVE", "ZERO"]
)
def test_not_at_a_line_end_before_a_class_or_sign_condition_translates(pred):
    pytest.importorskip("tree_sitter_language_pack")
    for cond in (["D0 NOT", pred], ["D0 IS NOT", pred], ["D0 IS", f"NOT {pred}"], ["D0", "NOT", pred]):
        proc = _proc(
            [
                f"    IF {cond[0]}",
                *[f"        {x}" for x in cond[1:]],
                "        DISPLAY 'Y'",
                "    END-IF.",
                "    GOBACK.",
            ]
        )
        stmts = [s for p in proc.paragraphs for s in S.walk(p.body)]
        c = stmts[0].data["cond"]
        assert not (isinstance(c, tuple) and c[0] == "UNPARSED"), (cond, c)
        assert [s.kind for s in stmts] == ["IF", "DISPLAY", "GOBACK"], cond


@pytest.mark.parametrize(
    "lead",
    [["D0 > 1 AND NOT"], ["D0 > 1 OR NOT"], ["D0 > 1 AND", "NOT"], ["D0 NOT = 1 AND NOT"]],
)
@pytest.mark.parametrize(
    "rest", [["< 5"], ["EQUAL TO 5"], ["GREATER", "THAN 5"], ["<=", "5"], ["LESS THAN OR", "EQUAL 5"], ["5"]]
)
def test_an_abbreviated_combined_condition_with_not_before_a_line_break_translates(lead, rest):
    pytest.importorskip("tree_sitter_language_pack")
    cond = [*lead, *rest]
    if cond[-1].endswith("5") and rest == ["5"] and not lead[0].endswith("= 1 AND NOT"):
        return  # `AND NOT 5` has no relation to abbreviate
    proc = _proc(
        [f"    IF {cond[0]}", *[f"        {x}" for x in cond[1:]], "        DISPLAY 'Y'", "    END-IF.", "    GOBACK."]
    )
    stmts = [s for p in proc.paragraphs for s in S.walk(p.body)]
    c = stmts[0].data["cond"]
    assert not (isinstance(c, tuple) and c[0] == "UNPARSED"), (cond, c)
    assert [s.kind for s in stmts] == ["IF", "DISPLAY", "GOBACK"], cond


@pytest.mark.parametrize(
    "head",
    [
        ["    EVALUATE TRUE", "        WHEN D0 NOT", "            < 3", "            DISPLAY 'Y'", "    END-EVALUATE."],
        [
            "    EVALUATE TRUE",
            "        WHEN D0 NOT",
            "            GREATER",
            "            THAN 3",
            "            DISPLAY 'Y'",
            "    END-EVALUATE.",
        ],
        [
            "    EVALUATE TRUE",
            "        WHEN D0 NOT",
            "            <= 3",
            "            DISPLAY 'Y'",
            "    END-EVALUATE.",
        ],
        [
            "    EVALUATE TRUE",
            "        WHEN D0 > 1 AND NOT",
            "            EQUAL TO 3",
            "            DISPLAY 'Y'",
            "    END-EVALUATE.",
        ],
        ["    PERFORM UNTIL D0 NOT", "        < 3", "        ADD 1 TO D0", "    END-PERFORM."],
        ["    PERFORM UNTIL D0 NOT", "        LESS THAN OR EQUAL TO 3", "        ADD 1 TO D0", "    END-PERFORM."],
        ["    PERFORM UNTIL D0 > 1 OR NOT", "        EQUAL TO 3", "        ADD 1 TO D0", "    END-PERFORM."],
    ],
)
def test_not_before_a_line_break_in_an_evaluate_when_or_perform_until_translates(head):
    pytest.importorskip("tree_sitter_language_pack")
    proc = _proc([*head, "    GOBACK."])
    stmts = [s for p in proc.paragraphs for s in S.walk(p.body)]
    assert not any(s.kind == "HOLE" for s in stmts), [(s.kind, s.data) for s in stmts]
    assert stmts[-1].kind == "GOBACK" and stmts[-1].line == 7 + len(head) + 1


@pytest.mark.parametrize(
    "cond",
    [["D0 > 1 AND", "> 5"], ["D0 > 1 OR", "EQUAL TO 5"], ["D0 > 1 AND", "GREATER", "THAN 5"],
     ["D0 > 1 AND GREATER THAN OR EQUAL TO 5"], ["D0 > 1 AND", "LESS OR", "EQUAL 5"]],
)  # fmt: skip
def test_an_omitted_subject_relation_after_an_and_or_or_translates_across_lines(cond):
    pytest.importorskip("tree_sitter_language_pack")
    proc = _proc(
        [f"    IF {cond[0]}", *[f"        {x}" for x in cond[1:]], "        DISPLAY 'Y'", "    END-IF.", "    GOBACK."]
    )
    stmts = [s for p in proc.paragraphs for s in S.walk(p.body)]
    c = stmts[0].data["cond"]
    assert not (isinstance(c, tuple) and c[0] == "UNPARSED"), (cond, c)
    assert [s.kind for s in stmts] == ["IF", "DISPLAY", "GOBACK"], cond


def test_a_not_inside_a_literal_is_not_rewritten():
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    text = "           IF A = 'X NOT <= Y' AND D0 NOT\n               <= 3\n"
    out = ST._join_not_breaks(text)
    assert "'X NOT <= Y'" in out and out.count("\n") == text.count("\n") and "D0 >" in out


def test_a_when_with_zero_in_arithmetic_is_a_condition():
    pytest.importorskip("tree_sitter_language_pack")
    proc = _proc(["    EVALUATE TRUE", "        WHEN 1 + ZERO > 0 DISPLAY 'Y'", "    END-EVALUATE.", "    GOBACK."])
    ev = next(s for p in proc.paragraphs for s in S.walk(p.body) if s.kind == "EVALUATE")
    assert ev.whens[0][0][0][0][0] == "COND", ev.whens


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
        try:  # #4462: a source of several programs (IC2244 ...: a CALLed one after it; IC4014: a nested one), each
            procs = []
            for unit in SRC.program_units(SRC.program_lines(p, [_CCVS85])):
                L.parse(unit.lines)
                procs.append(S.parse(unit.lines))
        except Exception:  # noqa: BLE001 -- a refusal is a program that does not count
            continue
        ok += not any(s.kind == "HOLE" and s.data.get("why") == "does not parse"
                      for proc in procs for para in proc.paragraphs for s in S.walk(para.body))  # fmt: skip
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


# ---- #4528: TS items in the region's code page; DTO copybooks in their declared page --------------------------------
class _TsCics(_RespCics):
    def int_(self, text):
        return f"INT({text})"


def test_ts_items_move_between_the_storage_page_and_the_regions():
    """#4528: a TS item is "the bytes the program wrote, in the region's code page" (CicsTask), as the COBOL side's
    region keeps it (cics-crucible SPEC 2: CCSID 037). The port's storage is in CS (CobolRecords.charset()): WRITEQ
    hands the region the item in REGION's page, READQ moves it back into CS. hc-perform-range: WS-ONE VALUE 'W' was
    written as X'57' ('ï' in CCSID 037), and an item 'A' read back as X'C1' ('Á' in Latin-1)."""
    c = _TsCics()
    assert not c.region_used and c.region == "IBM037"
    out = c.command("WRITEQ TS QUEUE('Q') FROM(REC) LENGTH(10)", "")
    assert (
        out[0] == "CicsTask.TsResult ts1 = task.writeqTs('Q'.strip(), DetCics.toRegion("
        'DetCics.padded(f_REC, INT(10), "WRITEQ TS", CS), CS, REGION));'
    )  # (X6: a LENGTH past FROM is padded with spaces)
    out = c.command("WRITEQ TS QUEUE('Q') FROM(REC) ITEM(3) REWRITE", "")
    assert "DetCics.toRegion(DetCics.bytes(f_REC, f_REC.length()), CS, REGION)" in out[0]
    out = c.command("READQ TS QUEUE('Q') INTO(REC) LENGTH(VARLEN) ITEM(2)", "")
    assert "if (ts3.data() != null) DetCics.put(f_REC, DetCics.fromRegion(ts3.data(), REGION, CS));" in out
    assert c.region_used


@pytest.mark.parametrize(
    ("declared", "page"),
    [(None, "IBM037"), ("cp037", "IBM037"), ("cp273", "IBM273"), ("cp277", "IBM277"), ("cp1047", "IBM1047"),
     ("cp1140", "IBM01140"), ("latin-1", "IBM037"), ("utf-8", "IBM037"), ("no-such-page", "IBM037")],
)  # fmt: skip
def test_the_region_page_is_the_estates_declared_ebcdic_page_else_ccsid_037(declared, page):
    """#4528: the estate's declared code page for the program (EngineCopies.page, #4462) names the region's when it
    is an EBCDIC page; an ASCII-family declaration says how the source was transferred, not which page the region
    runs, so CICS's default CCSID 037 stands."""
    assert C.region_page(declared) == page


def test_a_dto_copybook_is_read_in_its_declared_page(tmp_path):
    """#4528 (left by #4462): Cics.declared read a DTO's copybook as Latin-1 while the engine and the source reader
    take the estate's declared page; an EBCDIC copybook was garbage. It is now read the way the program is."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det.source import EngineCopies

    member = "       05  CA-AMT  PIC S9(5) SIGN LEADING SEPARATE.\n       05  CA-NAME PIC X(10).\n"
    (tmp_path / "CACOPY.cpy").write_bytes(member.encode("cp037"))
    c = _TsCics()
    c.g.copy_dirs = [tmp_path]
    c.g.engine = EngineCopies(tmp_path / "P.cbl", tmp_path, {}, frozenset(), frozenset(), {"CACOPY.cpy": "cp037"})
    leaf = C.Leaf("caAmt", "BigDecimal", "CA-AMT", "S9(5)", "DISPLAY", 0, 6, "CACOPY.cpy")
    it = c.declared(leaf)
    assert (it.name, it.size, it.sign_leading, it.sign_separate) == ("CA-AMT", 6, True, True)


def _javac() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_det_cics_moves_ts_bytes_between_pages_strictly(tmp_path):
    """#4528: DetCics.toRegion / fromRegion: Latin-1 storage <-> CCSID 037, every byte both ways (each page holds the
    other's 256 characters), NL (X'15') as NEL -- the COBOL side's cp037, not the JDK's LF; the same page is the bytes
    as they are; a byte one page cannot carry, or part of a multi-byte character, stops the run by name -- never a
    substituted '?'. gitgalaxy.cics.charset names another region page."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import java.nio.charset.Charset;
import t.cobolrt.cics.DetCics;
public class Main {
    static String hex(byte[] b) { StringBuilder s = new StringBuilder(); for (byte x : b) s.append(String.format("%02X", x)); return s.toString(); }
    public static void main(String[] a) {
        Charset l1 = Charset.forName("ISO-8859-1"), region = DetCics.region("IBM037");
        System.out.println(region + " " + hex(DetCics.toRegion("W A".getBytes(l1), l1, region)));
        byte[] all = new byte[256];
        for (int i = 0; i < 256; i++) all[i] = (byte) i;
        System.out.println(java.util.Arrays.equals(all, DetCics.fromRegion(DetCics.toRegion(all, l1, region), region, l1)));
        System.out.println(hex(DetCics.fromRegion(new byte[] {(byte) 0xC1, 0x40}, region, l1)));
        System.out.println(DetCics.toRegion(all, region, region) == all);
        System.out.println(hex(DetCics.fromRegion(new byte[] {0x15, 0x25}, region, l1)));
        System.out.println(hex(DetCics.toRegion(all, l1, region)));
        try { DetCics.toRegion(new byte[] {(byte) 0xC3, (byte) 0xA9}, Charset.forName("UTF-8"), region); }
        catch (UnsupportedOperationException e) { System.out.println("refused: " + e.getMessage()); }
        try { DetCics.toRegion(new byte[] {(byte) 0x80}, Charset.forName("windows-1252"), region); }
        catch (UnsupportedOperationException e) { System.out.println("refused"); }
        System.setProperty("gitgalaxy.cics.charset", "IBM273");
        System.out.println(DetCics.region("IBM037"));
    }
}
"""
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _javac()
    import subprocess

    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                            *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"], capture_output=True,  # noqa: S603
                         text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out[:5] == ["IBM037 E640C1", "true", "4120", "true", "850A"]  # NL is NEL, as Python's cp037 has it
    assert out[5] == bytes(range(256)).decode("latin-1").encode("cp037").hex().upper()  # the stub's own table
    assert out[6] == "refused: byte C3 is no character of UTF-8 on its own: not modelled"
    assert out[7:] == ["refused", "IBM273"]


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_det_cics_deedit_follows_ibms_text(tmp_path):
    """#4415 slice 1 (register X26), IBM EXEC CICS BIF DEEDIT: non-digits removed, digits right-aligned and zero
    padded in the same field ("14-6704/B" -> "00146704B", "$25.68" in 9 bytes -> "000002568": IBM's two examples); a
    trailing minus sign or CR puts the negative zone X'D' in the rightmost byte (123- -> 012L, X'D3'); a rightmost
    byte with a zone of A-F is returned unaltered; a 1-byte field is; LENGTH edits that many bytes. A field with no
    digit left, a character beyond 7-bit ASCII and a LENGTH past the field are refused by name."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import java.nio.charset.Charset;
import t.cobolrt.Field;
import t.cobolrt.Storage;
import t.cobolrt.cics.DetCics;
public class Main {
    static void run(String text, int length) {
        Charset l1 = Charset.forName("ISO-8859-1"), region = DetCics.region("IBM037");
        Storage st = new Storage(text.length());
        System.arraycopy(text.getBytes(l1), 0, st.bytes, 0, text.length());
        try {
            DetCics.deedit(Field.alphanumeric(st, 0, text.length(), false), length, l1, region);
            System.out.println("[" + text + "] -> [" + new String(st.bytes, l1) + "]");
        } catch (RuntimeException e) {
            System.out.println("[" + text + "] refused: " + e.getMessage());
        }
    }
    public static void main(String[] a) {
        run("14-6704/B", 9);
        run("$25.68   ", 9);
        run("123-", 4);
        run("1.5CR", 5);
        run("5-", 2);
        run("12}", 3);
        run("A", 1);
        run("ab12cd34", 8);
        run("ab12cd34", 4);
        run("abc", 3);
        run("\u00e91", 2);
        run("12345", 6);
    }
}
"""
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _javac()
    import subprocess

    built = javac_run([str(jdk / "javac"), "-nowarn", "-encoding", "UTF-8", "-d", str(tmp_path / "classes"),  # noqa: S603
                            *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"], capture_output=True,  # noqa: S603
                         text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out[:9] == ["[14-6704/B] -> [00146704B]", "[$25.68   ] -> [000002568]", "[123-] -> [012L]",
                       "[1.5CR] -> [0001N]", "[5-] -> [0N]", "[12}] -> [12}]", "[A] -> [A]",
                       "[ab12cd34] -> [00001234]", "[ab12cd34] -> [0012cd34]"]  # fmt: skip
    assert out[9] == "[abc] -> [000]"
    assert "beyond 7-bit ASCII" in out[10] and "LENGTH 6 > FIELD's 5 bytes" in out[11]


# ---- #4534: a LINKed program's COMMAREA writes survive its abend --------------------------------------------------
def test_an_abend_ending_the_program_throws_through_abended():
    """#4534: ABEND with no exit at this level, and a LINK an abend below unwound past this level, end the program
    through abended() -- which hands a LINKed program's COMMAREA back to its caller first -- not a bare Goback."""
    c = _HandleCics()
    assert c.command("ABEND ABCODE('HCX1')", "") == [
        "String exit1 = task.abend('HCX1'.strip());", "if (exit1 == null) throw abended();", "if (true) GOTO(paragraph(exit1));"]  # fmt: skip
    out = c.command("LINK PROGRAM('SUB')", "")
    assert "if (task.ended()) throw abended();" in out and not any("new Goback()" in x for x in out)


def test_a_linked_programs_commarea_goes_back_to_its_caller_when_an_abend_ends_it(tmp_path):
    """#4534 (cics-crucible hc-abend-link sub-unhandled): IBM, COMMAREA in LINK and XCTL commands -- "the address of
    the area is passed", so HCSUB's MOVE 's' TO CA-TRAIL before its QIDERR abend is in HCMAIN's storage when HCMAIN's
    abend exit runs. caBack (the write-back RETURN runs) also runs when an abend ends the program at a LINK level
    (level > 1): ABEND, an unhandled condition's default abend, an abend below unwound past it. Level 1 (a transaction,
    a DPL mirror task) keeps nothing, as before: no local caller shares its COMMAREA."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "T3.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. T3.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n       01  WS-J                  PIC X(8)  VALUE SPACES.\n"
        "       LINKAGE SECTION.\n       01  DFHCOMMAREA.\n           05  CA-TRAIL          PIC X(9).\n"
        "       PROCEDURE DIVISION.\n       MAIN-PARA.\n           MOVE 's' TO CA-TRAIL(1:1)\n"
        "           EXEC CICS READQ TS QUEUE('NONE') INTO(WS-J) ITEM(1) END-EXEC\n"
        "           EXEC CICS ABEND ABCODE('HCX1') END-EXEC\n           EXEC CICS RETURN END-EXEC.\n",
        encoding="utf-8",
    )
    (tmp_path / "proj/src/main/java/com/x").mkdir(parents=True)
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class T3Service {\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    r = P.translate(tmp_path / "T3.cbl", [], stub, "com.x", {}, tmp_path / "proj")
    assert r.stats["holes"] == []
    body = r.java[r.java.index("private Goback abended()") :]
    body = body[: body.index("\n    }\n")]
    assert "if (task.level() > 1) {" in body and "caBack.run();" in body and "return new Goback();" in body
    cond = r.java[r.java.index("private int condition(String cond)") :]
    assert "if (label == null) {\n            throw abended();" in cond[: cond.index("\n    }\n")]
    assert "throw abended();" in r.java[r.java.index("task.abend(") :]


# ---- #4272 / #4462: a character beyond the single-byte code page in a PROCEDURE DIVISION literal ----------------
_WIDE_WHY = "an alphanumeric literal holds a character beyond the single-byte code page"


def _wide_program(tmp_path, proc: list[str], data: tuple[str, ...] = ()) -> Path:
    (tmp_path / "TW.cbl").write_text(
        "".join(
            f"       {t}\n"
            for t in (
                "IDENTIFICATION DIVISION.",
                "PROGRAM-ID. TW.",
                "DATA DIVISION.",
                "WORKING-STORAGE SECTION.",
                "01  WS-MSG                PIC X(40) VALUE SPACES.",
                "01  WS-F                  PIC X VALUE 'Y'.",
                *data,
                "PROCEDURE DIVISION.",
                "MAIN-PARA.",
                *proc,
            )
        ),
        encoding="utf-8",
    )
    (tmp_path / "proj/src/main/java/com/x").mkdir(parents=True, exist_ok=True)
    return tmp_path / "TW.cbl"


def _tw_stub() -> str:
    return "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class TWService {\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip


def test_an_em_dash_in_a_procedure_literal_is_a_hole_by_name_not_a_refused_program(tmp_path):
    """A UTF-8 em dash (U+2014) in `MOVE '... \u2014 ...' TO WS-MSG` (a census estate's CICS messages): no single-byte code
    page holds it, so the literal's bytes and length are what the source's transfer to the compiler made of it
    (a substitute byte, or its three UTF-8 bytes), not what COBOL says. The statement is a hole naming why; the rest of
    the program translates (it had refused the whole program before the parser). The literal never reaches Java."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    prog = _wide_program(tmp_path, [
        "    IF WS-F = 'Y'", "        MOVE 'Conto bloccato \u2014 operazione negata' TO WS-MSG",
        "    END-IF", "    EVALUATE WS-MSG", "        WHEN 'A \u2014 B'", "            MOVE 'N' TO WS-F",
        "        WHEN OTHER", "            MOVE 'Y' TO WS-F", "    END-EVALUATE",
        "    MOVE 'plain' TO WS-MSG", "    EXEC CICS RETURN END-EXEC."])  # fmt: skip
    r = P.translate(prog, [], _tw_stub(), "com.x", {}, tmp_path / "proj")
    holes = r.stats["holes"]
    assert len(holes) == 2 and all(_WIDE_WHY in h for h in holes), holes
    assert holes[0].startswith("line 10: MOVE ") and holes[1].startswith("line 12: EVALUATE ")
    # IF, MOVE (hole), EVALUATE (hole: a WHEN holds the literal), MOVE 'plain', EXEC CICS RETURN
    assert (r.stats["statements"], r.stats["translated"]) == (5, 3)
    assert "\\u001d" not in r.java and "\x1d" not in r.java and "\\u2014" not in r.java


@pytest.mark.parametrize(
    "data, proc, why",
    [
        # a VALUE lays the record out: its bytes are the program's storage
        (("01  WS-T PIC X(8) VALUE 'A \u2014 B'.",), ["    GOBACK."], "national / DBCS text"),
        # a national / DBCS literal stays refused by name (#4272): national data is not modelled
        ((), ["    MOVE N'\u6f22\u5b57' TO WS-MSG", "    GOBACK."], "national / DBCS text"),
        ((), ["    MOVE G'\u6f22\u5b57' TO WS-MSG", "    GOBACK."], "national / DBCS text"),
        # outside a literal: a name
        ((), ["    MOVE 'A' TO WS-\u6f22", "    GOBACK."], "national / DBCS text"),
    ],
)  # fmt: skip
def test_wide_text_outside_a_procedure_alphanumeric_literal_is_still_refused_whole(tmp_path, data, proc, why):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P
    from gitgalaxy.tools.cobol_to_java.det.source import logical_lines, unmodelled

    prog = _wide_program(tmp_path, proc, data)
    assert why in (unmodelled(logical_lines(prog.read_text(encoding="utf-8").splitlines(), str(prog))) or "")
    with pytest.raises(Exception, match=why):
        P.translate(prog, [], _tw_stub(), "com.x", {}, tmp_path / "proj")


def test_an_em_dash_in_an_inline_comment_is_read(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    # (a fixed-format `*>` comment in the PROCEDURE DIVISION is a hole of its own, wide or not: the statement grammar)
    prog = _wide_program(tmp_path, ["    MOVE 'A' TO WS-F", "    EXEC CICS RETURN END-EXEC."],
                         ("01  WS-T PIC X(8) VALUE 'AB'.  *> s\u00ec \u2014 note",))  # fmt: skip
    r = P.translate(prog, [], _tw_stub(), "com.x", {}, tmp_path / "proj")
    assert (r.stats["statements"], r.stats["translated"], r.stats["holes"]) == (2, 2, [])


def test_the_wide_literal_stand_in_is_refused_by_name_in_the_source():
    from gitgalaxy.tools.cobol_to_java.det import source as SRC

    assert "U+001D" in SRC.unmodelled(_lines([f"    MOVE 'A{SRC.WIDE}B' TO A."]))


# ---- FUNCTION RANDOM: the oracle's generator, stated (oracle_assumptions.md C12) ------------------------------------
_RANDOM_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. RND.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-SEED                PIC S9(15) COMP VALUE 7.
       01  WS-DELAY               PIC S9(8) COMP.
       01  WS-SCORE               PIC 999.
       PROCEDURE DIVISION.
           COMPUTE WS-DELAY = ((3 - 1) * FUNCTION RANDOM(WS-SEED)) + 1
           COMPUTE WS-SCORE = ((999 - 1) * FUNCTION RANDOM) + 1
           GOBACK.
"""


def test_function_random_seeded_and_unseeded_translate_onto_the_run_units_sequence(tmp_path):
    """CBSA's CRDTAGY1-5 / INQCUST and GenApp's LGICVS01: RANDOM(seed), then RANDOM with no argument continuing the
    sequence. Both translate onto one Funcs.Random per program, reset by every entry point (a run unit starts as a
    first reference with no seed finds it: seed zero, IBM)."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "RND.cbl").write_text(_RANDOM_PROGRAM, encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    r = P.translate(tmp_path / "RND.cbl", [], "public class RndService {\n}\n", "com.x", None, project)
    assert (r.stats["statements"], r.stats["translated"], r.stats["holes"]) == (3, 3, [])
    assert "private final Funcs.Random funcRandom = new Funcs.Random();" in r.java
    assert "funcRandom.next(" in r.java and "funcRandom.next()" in r.java
    init = r.java.split("private void initialState() {", 1)[1].split("\n    }", 1)[0]
    assert "funcRandom.reset();" in init


def test_a_program_without_function_random_carries_no_sequence(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "RND.cbl").write_text(_RANDOM_PROGRAM.replace("FUNCTION RANDOM(WS-SEED)", "WS-SEED")
                                      .replace("FUNCTION RANDOM", "WS-SEED"), encoding="utf-8")  # fmt: skip
    project = tmp_path / "proj"
    project.mkdir()
    r = P.translate(tmp_path / "RND.cbl", [], "public class RndService {\n}\n", "com.x", None, project)
    assert r.stats["holes"] == [] and "funcRandom" not in r.java


def test_a_writeq_length_past_from_is_padded_by_the_det_port_as_by_the_stub_x6():
    """X6 (ASSUMED, owner 2026-10-21): a WRITEQ TS / TD LENGTH past its FROM item (GenApp LGSTSQ: 104 bytes from 95)
    writes FROM's bytes then spaces to LENGTH, the fill the stub uses (IBM reads the storage that follows: undefined).
    Without LENGTH nothing is padded; only a LENGTH over the longest record (32767) is refused (PastFrom)."""
    ts = _ChanCics().command("WRITEQ TS QUEUE('Q') FROM(REC) LENGTH(20) RESP(R)", "")
    assert ts[0] == ("CicsTask.TsResult ts1 = task.writeqTs('Q'.strip(), DetCics.toRegion("
                     'DetCics.padded(f_REC, INT(20), "WRITEQ TS", CS), CS, REGION));')  # fmt: skip
    td = _ChanCics().command("WRITEQ TD QUEUE('Q') FROM(REC) LENGTH(20) RESP(R)", "")
    assert td[0] == ("int resp1 = task.writeqTd('Q'.strip(), "
                     'new String(DetCics.padded(f_REC, INT(20), "WRITEQ TD", CS), CS));')  # fmt: skip
    assert "padded" not in _ChanCics().command("WRITEQ TS QUEUE('Q') FROM(REC) RESP(R)", "")[0]
    td_plain = _ChanCics().command("WRITEQ TD QUEUE('Q') FROM(REC) RESP(R)", "")[0]
    assert "padded" not in td_plain and "Cobol.text(f_REC, CS)" in td_plain
    rt = (Path(C.__file__).parent / "cobolrt/cics/DetCics.java").read_text(encoding="utf-8")
    assert "public static final class PastFrom extends UnsupportedOperationException" in rt
    assert "public static byte[] padded(Field f, int n, String what, Charset cs)" in rt
    assert "public static int within(Field f, int n, String what)" in rt  # DOCUMENT CREATE still refuses


def test_readq_td_and_deleteq_td_call_the_task_and_move_the_record_into():
    """#5079 (register X57): READQ TD INTO [LENGTH] -> CicsTask.readqTd (the most INTO takes: LENGTH, else INTO's own
    size), the record's text moved INTO by DetCics.readTd (a record past INTO refused), a data area LENGTH set to the
    record's length when one was read; DELETEQ TD -> CicsTask.deleteqTd; SET / SYSID / NOSUSPEND refused by name."""
    out = _ChanCics().command("READQ TD QUEUE('Q') INTO(REC) LENGTH(WS-N) RESP(R)", "")
    assert out[0].startswith("CicsTask.TdResult td1 = task.readqTd('Q'.strip(), ") and "WS-N" in out[0]
    assert out[1] == "if (td1.data() != null) DetCics.readTd(f_REC, td1.data().getBytes(CS));"
    assert "td1.length() >= 0" in out[2] and "BigDecimal.valueOf(td1.length())" in out[2]
    plain = _ChanCics().command("READQ TD QUEUE('Q') INTO(REC) RESP(R)", "")
    assert "f_REC.length()" in plain[0] and not any("td1.length()" in line for line in plain)
    literal = _ChanCics().command("READQ TD QUEUE('Q') INTO(REC) LENGTH(8) RESP(R)", "")
    assert not any("td1.length()" in line for line in literal)
    assert _ChanCics().command("DELETEQ TD QUEUE('Q') RESP(R)", "")[0] == "int resp1 = task.deleteqTd('Q'.strip());"
    for body in ("READQ TD QUEUE('Q') SET(P)", "READQ TD QUEUE('Q') INTO(REC) SYSID('S')",
                 "DELETEQ TD QUEUE('Q') SYSID('S')"):  # fmt: skip
        with pytest.raises(Exception, match="not modelled|refused|SYSID|SET|NOSUSPEND"):
            _ChanCics().command(body, "")
    rt = (Path(C.__file__).parent / "cobolrt/cics/DetCics.java").read_text(encoding="utf-8")
    assert "public static void readTd(Field into, byte[] record)" in rt


def test_readq_td_set_puts_the_record_in_a_block_and_nosuspend_changes_nothing_5168():
    """#5168 (register X61): READQ TD SET(ptr) LENGTH(area) -> the record in a block valid to the next READQ TD
    (DetCics.setBlock, key "READQ TD"), its length to the area; NOSUSPEND is accepted with no effect (no second task holds a queue);
    INTO with SET, SET without a LENGTH area or with a literal one are refused."""
    out = _PtrCics().command("READQ TD QUEUE('Q') SET(PTR) LENGTH(WS-N) NOSUSPEND RESP(R)", "")
    assert out[0] == "CicsTask.TdResult td1 = task.readqTd('Q'.strip(), Integer.MAX_VALUE, true);"
    assert (
        out[1].startswith("if (td1.data() != null) DetCics.setBlock(task, ") and '"READQ TD", td1.data(), CS' in out[1]
    )
    assert "td1.length() >= 0" in out[2] and "WS-N" in out[2]
    nos = _PtrCics().command("READQ TD QUEUE('Q') INTO(REC) NOSUSPEND RESP(R)", "")
    assert nos[0].startswith("CicsTask.TdResult td1 = task.readqTd(")
    for body in ("READQ TD QUEUE('Q') INTO(REC) SET(PTR) LENGTH(WS-N)", "READQ TD QUEUE('Q') SET(PTR)",
                 "READQ TD QUEUE('Q') SET(PTR) LENGTH(8)"):  # fmt: skip
        with pytest.raises(Exception, match="SET|INTO|LENGTH"):
            _PtrCics().command(body, "")


def test_a_commarea_of_a_stated_length_is_all_dfhcommarea_holds(tmp_path):
    """#4270 (oracle_assumptions.md X23): a level-1 task whose runner states the COMMAREA is exactly EIBCALEN bytes
    (CicsTask.withExactCommarea: a scenario's `commarea_length`, shorter than the record) runs with DFHCOMMAREA's
    storage cut to those bytes, so a reference past them fails and is refused as DetCics.PastFrom -- the stub's guard
    page stops the COBOL side at the same statement. The record comes back whole before the COMMAREA is written back
    to the task's object (caBack), and after the task whatever ended it."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "T4.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. T4.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n       01  WS-J                  PIC X(8)  VALUE SPACES.\n"
        "       LINKAGE SECTION.\n       01  DFHCOMMAREA.\n           05  CA-CODE           PIC XX.\n"
        "           05  CA-REST           PIC X(98).\n"
        "       PROCEDURE DIVISION.\n       MAIN-PARA.\n           IF EIBCALEN < 100\n"
        "               MOVE '98' TO CA-CODE\n           END-IF\n           EXEC CICS RETURN END-EXEC.\n",
        encoding="utf-8",
    )
    (tmp_path / "proj/src/main/java/com/x").mkdir(parents=True)
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class T4Service {\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    r = P.translate(tmp_path / "T4.cbl", [], stub, "com.x", {}, tmp_path / "proj")
    assert r.stats["holes"] == []
    run = r.java[r.java.index("public void runTask(CicsTask task)") :]
    run = " ".join(run[: run.index("\n    }\n")].split())  # (the body is indented under the TRUNC wrapper)
    assert "if (task.exactCommarea() && calen < " in run and ".bytes = java.util.Arrays.copyOf(caWhole, calen);" in run
    assert "caBack = () -> { caWhole(whole); typed.run(); };" in run
    assert "} catch (IndexOutOfBoundsException e) { if (caWhole == null) { throw e; }" in run
    assert 'throw new DetCics.PastFrom("COMMAREA past EIBCALEN (" + calen + " bytes): not modelled");' in run
    assert "} finally { if (caWhole != null) { caWhole(caWhole); } }" in run
    assert "private void caWhole(byte[] whole) {" in r.java


# ---- #4501: an XCTL COMMAREA whose LENGTH is past the target's DTO ----------------------------------------
class _OverCics(_ChanCics):
    """A target whose DTO is 80 bytes; WS-BIGLEN a never-written COMP-5 VALUE 32767, WS-N a data item the program sets."""

    SIZES = {**_ChanCics.SIZES, "WS-BIG": 32767, "WS-V1": 10}

    def __init__(self):
        super().__init__()
        self.gp.dto = lambda cls: type("D", (), {"size": 80, "extent": 80})()  # the 80-byte DTO, on the inherited stub
        self.dto_for = lambda area, size, program=None: "Dto"
        self.codec = lambda cls: cls
        self.g.reading = lambda: __import__("contextlib").nullcontext()
        self.g.field_expr = lambda ref: f"f_{ref.name}"
        self.constant_int = lambda t: {"WS-BIGLEN": 32767, "80": 80, "10": 10}.get(t.strip())


def test_xctl_commarea_length_past_the_dto_passes_that_many_bytes():
    """IBM, EXEC CICS XCTL: LENGTH is the COMMAREA's length and the target's EIBCALEN is that length; ca-xctl-versions
    CAXA passes LENGTH(WS-BIGLEN)=32767 over a PIC X(32767) the 80-byte DTO cannot hold. The bytes travel
    (DetCics.commareaOut); a length within the DTO, known at translation, keeps the plain DTO. RESP2 follows the
    condition (LENGERR 11, PGMIDERR 1)."""
    c = _OverCics()
    out = c.command("XCTL PROGRAM('XB') COMMAREA(WS-BIG) LENGTH(WS-BIGLEN) RESP(R) RESP2(R2)", "")
    assert out[0] == (
        "String xr1 = task.xctl('XB'.strip(), DetCics.commareaOut(out_Dto(f_WS-BIG.storage(), "
        "f_WS-BIG.offset()), f_WS-BIG, INT(WS-BIGLEN), 80, CS), INT(WS-BIGLEN));"
    )
    assert any("task.transferResp2()" in x for x in out)
    within = c.command("XCTL PROGRAM('XB') COMMAREA(WS-V1) LENGTH(80)", "")
    # #4806: a DTO's XCTL passes the bytes it spans too: a det target's DFHCOMMAREA is them, not the DTO's reading
    assert "commareaOut" not in within[0] and within[0].endswith(", INT(80), Cobol.commarea(f_WS-V1, 80).bytes);")
    unknown = c.command("XCTL PROGRAM('XB') COMMAREA(WS-V1) LENGTH(WS-N)", "")
    assert "commareaOut" in unknown[0]  # a length only known at run time is decided there
    assert unknown[1] == (
        "String xr4 = task.xctl('XB'.strip(), xc3, INT(WS-N), "
        "(xc3 instanceof byte[] ? null : Cobol.commarea(f_WS-V1, 80).bytes));"
    )  # (the DTO: its bytes)
    ret = c.command("RETURN TRANSID('TRN1') COMMAREA(WS-BIG) LENGTH(WS-BIGLEN)", "")
    assert any("commareaOut" in x for x in ret)  # #4679: a RETURN's too (below)
    # #4817: RETURN passes the bytes beside the DTO
    ret_within = c.command("RETURN TRANSID('T1') COMMAREA(WS-V1) LENGTH(80)", "")
    assert "commareaOut" not in ret_within[0] and ret_within[1].endswith(
        ", INT(80), Cobol.commarea(f_WS-V1, 80).bytes);"
    )
    ret_unknown = c.command("RETURN TRANSID('T1') COMMAREA(WS-V1) LENGTH(WS-N)", "")
    assert "commareaOut" in ret_unknown[0]
    assert ret_unknown[2] == (
        "task.returnTransid('T1'.strip(), xc5, INT(WS-N), "
        "(xc5 instanceof byte[] ? null : Cobol.commarea(f_WS-V1, 80).bytes));"
    )
    imm = c.command("RETURN TRANSID('T1') IMMEDIATE COMMAREA(WS-V1) LENGTH(80)", "")
    assert "commareaOut" not in imm[0] and imm[0].endswith(", INT(80), Cobol.commarea(f_WS-V1, 80).bytes);")


# ---- #4679: LINK RESP2; RETURN / LINK COMMAREA LENGTH past the DTO; opaque bytes passed on ------------------------
def test_link_resp2_follows_its_condition():
    """IBM, EXEC CICS LINK conditions: LENGERR RESP2 11 (COMMAREA length below 0 or above 32763), PGMIDERR RESP2 1 (no
    installed definition, autoinstall off) -- what CicsTask.link and the stub's GGCLINK raise. A failed LINK stored
    RESP2 0; it is task.transferResp2() now (#4986: the event's RESP2, a planned fault's too), as XCTL's."""
    c = _OverCics()
    out = c.command("LINK PROGRAM('XB') COMMAREA(WS-V1) RESP(R) RESP2(R2)", "")
    assert out[-1] == "OUTCOME(DetCics.resp(lr1), task.transferResp2());"
    out = c.command("LINK PROGRAM('XB')", "")
    assert out[-1].endswith(", task.transferResp2());")


def test_return_and_link_commarea_length_past_the_dto():
    """IBM, EXEC CICS RETURN: COMMAREA / LENGTH is the data passed to the next program of the conversation, and its
    EIBCALEN is that LENGTH; LINK: LENGTH is the COMMAREA's length, passed by reference (the target's EIBCALEN).
    CardDemo's COCRDLIC RETURNs WS-COMMAREA LENGTH 2000 over its 414-byte DTO: the bytes travel (DetCics.commareaOut).
    A LINK past the DTO lays that many bytes over the caller's storage (Cobol.commarea, capped at 32763: past it the
    LINK is LENGERR); a LENGTH within the DTO known at translation keeps the DTO's span."""
    c = _OverCics()
    ret = c.command("RETURN TRANSID('TRN1') COMMAREA(WS-BIG) LENGTH(WS-BIGLEN)", "")
    assert ret[1] == ("task.returnTransid('TRN1'.strip(), DetCics.commareaOut(out_Dto(f_WS-BIG.storage(), "
                      "f_WS-BIG.offset()), f_WS-BIG, INT(WS-BIGLEN), 80, CS), INT(WS-BIGLEN));")  # fmt: skip
    within = c.command("RETURN TRANSID('TRN1') COMMAREA(WS-V1) LENGTH(80)", "")
    assert "commareaOut" not in within[1]
    link = _OverCics().command("LINK PROGRAM('XB') COMMAREA(WS-BIG) LENGTH(WS-BIGLEN)", "")
    assert link[0] == "Storage cw3 = Cobol.commarea(f_WS-BIG, Math.max(80, Math.min(INT(WS-BIGLEN), 32763)));"
    assert link[2] == "String lr1 = task.link('XB'.strip(), ca2, INT(WS-BIGLEN), cw3.bytes);"
    assert c.command("LINK PROGRAM('XB') COMMAREA(WS-V1) LENGTH(10)", "")[0].endswith("Cobol.commarea(f_WS-V1, 80);")
    assert c.command("LINK PROGRAM('XB') COMMAREA(WS-V1)", "")[0].endswith("Cobol.commarea(f_WS-V1, 80);")


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_det_runtime_passes_opaque_commarea_bytes_on(tmp_path):
    """#4679 (c): a receiver whose DFHCOMMAREA is shorter than the COMMAREA it was passed keeps the bytes past its
    record (Storage.beyond) -- CICS passed LENGTH bytes, the record only addresses its own. A further RETURN / XCTL
    (DetCics.commareaOut) or LINK (Cobol.commarea) of that area with the LENGTH passes them on, and a LINK target's
    writes there come back (Cobol.commareaBack: by reference). Past them: LOW-VALUES, as before (X10)."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import java.nio.charset.Charset;
import t.cobolrt.*;
import t.cobolrt.cics.DetCics;
public class Main {
    public static void main(String[] a) {
        Charset l1 = Charset.forName("ISO-8859-1");
        Storage ca = Storage.of("ABCD".getBytes(l1));
        ca.beyond = "EFG".getBytes(l1);
        Field f = Field.group(ca, 0, 4);
        byte[] out = (byte[]) DetCics.commareaOut("dto", f, 9, 4, l1);
        System.out.println(new String(DetCics.commareaIn(out, l1), l1).replace('\0', '.'));
        System.out.println(DetCics.commareaOut("dto", f, 4, 4, l1));
        Field tail = Field.group(ca, 2, 2);
        Storage w = Cobol.commarea(tail, 6);
        System.out.println(new String(w.bytes, l1).replace('\0', '.'));
        w.bytes[3] = 'x';
        w.bytes[0] = 'y';
        Cobol.commareaBack(w, tail);
        System.out.println(new String(ca.bytes, l1) + "|" + new String(ca.beyond, l1));
    }
}
"""
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _javac()
    import subprocess

    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                            *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"], capture_output=True,  # noqa: S603
                         text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out == ["ABCDEFG..", "dto", "CDEFG.", "AByD|ExG"]


def test_link_to_a_target_no_dto_types_passes_the_bytes():
    """#4679 (cics-crucible ca-link-lengths undefined-program): CALINK LINKs CAGONE, which no CSD defines, with
    COMMAREA(WS-CA100) LENGTH(100) RESP2: no generated DTO types it, so the COMMAREA travels as its LENGTH bytes
    (DetCics.commareaBytes, by reference) rather than the LINK being a hole -- and its PGMIDERR is RESP2 1."""
    c = _OverCics()

    def no_dto(area, size, program=None):
        raise C.CicsError(f"no generated DTO for COMMAREA {area.name}")

    c.dto_for = no_dto
    out = c.command("LINK PROGRAM('CAGONE') COMMAREA(WS-V1) LENGTH(100) RESP(R) RESP2(R2)", "")
    assert out[:3] == ["Storage cw3 = Cobol.commarea(f_WS-V1, Math.max(0, Math.min(INT(100), 32763)));",
                       "String lr1 = task.link('CAGONE'.strip(), DetCics.commareaBytes(cw3.bytes, CS), INT(100), cw3.bytes);",
                       'if ("NORMAL".equals(lr1)) Cobol.commareaBack(cw3, f_WS-V1);']  # fmt: skip
    assert out[-1] == "OUTCOME(DetCics.resp(lr1), task.transferResp2());"


def test_an_integer_literal_against_an_alphanumeric_item_keeps_its_leading_zeros(tmp_path):
    """#4270 (GenApp LGTESTP4: `ENP4CNOO Not = 0000000000` on a map field of ten digits): compared with an
    alphanumeric item, an integer literal is the nonnumeric literal of its digits as written (IBM, "Comparison of
    numeric and alphanumeric operands"). As a value it is 0, whose text "0" made '0000000000' unequal to it."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "T5.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. T5.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n       01  REC.\n           05  WS-A              PIC X(10).\n"
        "           05  WS-B              PIC X(2).\n       01  WS-N                  PIC 9(3) VALUE 7.\n"
        "       PROCEDURE DIVISION.\n       MAIN-PARA.\n           MOVE SPACES TO REC\n"
        "           IF WS-A NOT = 0000000000 AND WS-A NOT = 0\n               MOVE 'Y' TO WS-B\n           END-IF\n"
        "           IF WS-N = 007\n               MOVE 'N' TO WS-B\n           END-IF\n"
        "           EXEC CICS RETURN END-EXEC.\n",
        encoding="utf-8",
    )
    (tmp_path / "proj/src/main/java/com/x").mkdir(parents=True)
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class T5Service {\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    r = P.translate(tmp_path / "T5.cbl", [], stub, "com.x", {}, tmp_path / "proj")
    assert r.stats["holes"] == []
    assert '_WS_A, "0000000000", CS) == 0' in r.java and '_WS_A, "0", CS) == 0' in r.java
    assert '"007"' not in r.java  # a numeric item against it: by value, as before


def test_return_immediate_and_link_synconreturn():
    """#4270 (X27), IBM EXEC CICS RETURN / LINK: RETURN TRANSID IMMEDIATE attaches the task at once with the COMMAREA, and
    can fail (INVREQ RESP2 1 / 2, LENGERR RESP2 11: the program then goes on, so RESP is read); without TRANSID IBM does
    not say what it attaches, refused. SYNCONRETURN is "ignored if the link is local" (every LINK here is): the
    translation is the same as without it."""
    out = _ChanCics().command("RETURN TRANSID('PC52') IMMEDIATE RESP(R) RESP2(R2)", "")
    assert out == ["int[] rr1 = task.returnImmediate('PC52'.strip(), null, null);",
                   "if (rr1[0] == 0) { caBack.run(); throw new Goback(); }",
                   "OUTCOME(rr1[0], rr1[1]);"]  # fmt: skip
    with pytest.raises(C.CicsError, match="not modelled"):
        _ChanCics().command("RETURN IMMEDIATE", "")
    plain = _ChanCics().command("LINK PROGRAM('P') RESP(R)", "")
    assert _ChanCics().command("LINK PROGRAM('P') SYNCONRETURN RESP(R)", "") == plain


def test_asktime_nohandle_formattime_resp_and_readq_length_of():
    """#4737 (register X28): ASKTIME NOHANDLE (the option is no verb word; ABSTIME optional), FORMATTIME RESP (INVREQ
    RESP2 1 for ABSTIME below zero, nothing written), READQ TS LENGTH(LENGTH OF x) (the most INTO takes, no store back)."""
    c = _ChanCics()
    assert C.parse_exec("EXEC CICS ASKTIME NOHANDLE ABSTIME(A) NOHANDLE END-EXEC")[0] == ["ASKTIME"]
    assert c.command("ASKTIME NOHANDLE", "") == ["task.asktime();"]
    assert "task.asktime()" in c.command("ASKTIME ABSTIME(REC) NOHANDLE", "")[0]
    out = c.command("FORMATTIME ABSTIME(REC) DDMMYYYY(KEY) DATESEP RESP(R)", "")
    assert out[0].startswith("int[] fmt") and out[0].endswith(".longValue());") and out[1].endswith("[0] == 0) {")
    assert out[2].lstrip().startswith("Cobol.move(CicsTask.formatDate(") and out[3] == "}"
    assert out[4].startswith("OUTCOME(fmt") and "[0]" in out[4] and "[1]" in out[4]
    plain = c.command("FORMATTIME ABSTIME(REC) TIME(KEY) NOHANDLE", "")  # (no RESP: unchanged; the runtime refuses < 0)
    assert len(plain) == 1 and plain[0].startswith("Cobol.move(CicsTask.formatTime(")
    out = c.command("READQ TS QUEUE('Q') INTO(REC) LENGTH(LENGTH OF REC) RESP(R)", "")
    assert not any("Cobol.store" in x and "length()" in x for x in out)
    assert any("readqTsNext" in x for x in out)
    stored = c.command("READQ TS QUEUE('Q') INTO(REC) LENGTH(KEY) RESP(R)", "")
    assert any("Cobol.store" in x and "length()" in x for x in stored)


_FMT_TEXT = ("YYDDD", "YYYYDDD", "YYDDMM", "YYYYDDMM", "YYYYMMDD", "DDMMYY")
_FMT_BIN = ("DAYCOUNT", "DAYOFMONTH", "DAYOFWEEK", "MONTHOFYEAR", "YEAR", "MILLISECONDS")
_FMT_REFUSED = ("DATE", "DATEFORM", "FULLDATE", "DATESTRING", "STRINGFORMAT", "STRINGZONE")


@pytest.mark.parametrize("form", _FMT_TEXT)
def test_formattime_each_text_date_form_is_formatted_with_its_separator(form):
    """#4415 slice 3 (X46): every date form (the day-of-year ones included) is CicsTask.formatDate of the form, with
    '/' for a DATESEP with no value, or no separator at all (a DATESEP value is a literal, tested in the runtime)."""
    c = _LenCics()
    for sep_opt, sep in (("", '""'), (" DATESEP", '"/"')):
        out = c.command(f"FORMATTIME ABSTIME(REC) {form}(KEY){sep_opt} NOHANDLE", "")
        assert len(out) == 1 and f"CicsTask.formatDate(" in out[0] and f'"{form}", {sep})' in out[0]


@pytest.mark.parametrize("form", _FMT_BIN)
def test_formattime_each_binary_form_is_stored_by_the_areas_declared_usage(form):
    c = _LenCics()
    out = c.command(f"FORMATTIME ABSTIME(REC) {form}(KEY) NOHANDLE", "")
    assert len(out) == 1 and out[0].startswith("STORE(KEY, BigDecimal.valueOf(CicsTask.formatNumber(")
    assert f'"{form}"))' in out[0]
    with_resp = c.command(f"FORMATTIME ABSTIME(REC) {form}(KEY) RESP(R)", "")  # INVREQ RESP2 1 guards every form
    assert (
        with_resp[0].startswith("int[] fmt") and with_resp[1].endswith("[0] == 0) {") and "formatNumber" in with_resp[2]
    )


@pytest.mark.parametrize("form", _FMT_REFUSED)
def test_formattime_options_ibm_leaves_to_the_installation_or_the_zone_are_refused_by_name(form):
    with pytest.raises(C.CicsError, match=form):
        _LenCics().command(f"FORMATTIME ABSTIME(REC) {form}(KEY) NOHANDLE", "")


@pytest.mark.parametrize(
    "text",
    [
        "DUMP TRANSACTION DUMPCODE('ABCD')",
        "DUMP DUMPCODE('ABCD')",
        "DUMP TRANSACTION DUMPCODE('ABCD') FROM(REC) LENGTH(10) NOHANDLE",
        "DUMP TRANSACTION COMPLETE",
    ],
)
def test_dump_is_refused_by_name_in_both_forms(text):
    """#4415 slice 3 (X46): IBM's DUMP TRANSACTION outcome is the region's dump setup, which the run does not state."""
    with pytest.raises(C.CicsError, match=r"DUMP.*(not modelled|X46)"):
        _LenCics().command(text, "")


def test_document_create_each_source_and_retrieve_as_cicstask_answers():
    """#4769 (register X33), IBM DOCUMENT CREATE / DOCUMENT RETRIEVE: CREATE builds an empty document, one of TEXT /
    BINARY (LENGTH bytes of the area, unchanged) or a TEMPLATE (the installed DOCTEMPLATE's text, in the program's page);
    its DOCTOKEN is written on NORMAL only, and LENGERR RESP2 1 / NOTFND RESP2 3 reach RESP / RESP2 / HANDLE CONDITION.
    RETRIEVE copies the document INTO, at most MAXLENGTH bytes, and sets LENGTH only when CicsTask returns one (NORMAL, and
    the truncating LENGERR RESP2 2); MAXLENGTH is read before LENGTH is written (zECS gives both the same area)."""
    c = _ChanCics()
    t = c.command("DOCUMENT CREATE DOCTOKEN(T) TEMPLATE(M) RESP(R) RESP2(R2)", "")
    assert t == ["CicsTask.DocumentCreated doc1 = task.documentCreateTemplate(M.strip(), CS);",
                 "if (doc1.resp() == 0) DetCics.putText(f_T, doc1.doctoken(), CS);",
                 "OUTCOME(doc1.resp(), doc1.resp2());"]  # fmt: skip
    assert c.command("DOCUMENT CREATE DOCTOKEN(T) NOHANDLE", "")[0].endswith("= task.documentCreateEmpty();")
    for src in ("TEXT", "BINARY"):
        d = c.command(f"DOCUMENT CREATE DOCTOKEN(T) {src}(A) LENGTH(L) NOHANDLE", "")
        assert d[0].startswith("CicsTask.DocumentCreated doc") and d[0].endswith(
            " = task.documentCreateData(DetCics.documentBytes(f_A, INT(L)), INT(L));"
        )
    r = c.command("DOCUMENT RETRIEVE DOCTOKEN(T) INTO(A) LENGTH(L) MAXLENGTH(L) DATAONLY NOHANDLE", "")
    n = re.search(r"doc(\d+)", r[0]).group(1)
    assert r == [f"CicsTask.DocumentData doc{n} = task.documentRetrieve(Cobol.text(f_T, CS), INT(L));",
                 f"if (doc{n}.data() != null) DetCics.putDocument(f_A, doc{n}.data());",
                 f"if (doc{n}.length() >= 0) STORE(L, BigDecimal.valueOf(doc{n}.length()));",
                 f"OUTCOME(doc{n}.resp(), doc{n}.resp2());"]  # fmt: skip
    r = c.command("DOCUMENT RETRIEVE DOCTOKEN(T) INTO(A) MAXLENGTH(9) DATAONLY RESP(R)", "")
    assert not any("STORE(" in x for x in r)  # no LENGTH asked for
    rt = (Path(C.__file__).parent / "cobolrt/cics/DetCics.java").read_text(encoding="utf-8")
    assert "public static byte[] documentBytes(Field f, int n)" in rt and "public static void putDocument(" in rt
    assert 'bytes(f, within(f, n, "DOCUMENT CREATE"))' in rt  # a LENGTH past the area is refused, as a WRITEQ's is


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("DOCUMENT CREATE DOCTOKEN(T) FROM(A) LENGTH(5)", "FROM takes a template or a RETRIEVEd document"),
        ("DOCUMENT CREATE DOCTOKEN(T) FROMDOC(A)", "copying a document"),
        ("DOCUMENT CREATE DOCTOKEN(T) TEMPLATE(M) SYMBOLLIST(A) LISTLENGTH(9)", "symbol table is not modelled"),
        ("DOCUMENT CREATE DOCTOKEN(T) TEMPLATE(M) DELIMITER('|')", "symbol table is not modelled"),
        ("DOCUMENT CREATE DOCTOKEN(T) TEMPLATE(M) UNESCAPED", "symbol table is not modelled"),
        ("DOCUMENT CREATE DOCTOKEN(T) TEMPLATE(M) DOCSIZE(L)", "DOCSIZE"),
        ("DOCUMENT CREATE DOCTOKEN(T) TEXT(A) LENGTH(3) HOSTCODEPAGE('037')", "code-page conversion"),
        ("DOCUMENT CREATE TEMPLATE(M)", "without DOCTOKEN"),
        ("DOCUMENT CREATE DOCTOKEN(T) TEXT(A)", "without LENGTH"),
        ("DOCUMENT CREATE DOCTOKEN(T) BINARY(A)", "without LENGTH"),
        ("DOCUMENT CREATE DOCTOKEN(T) LENGTH(4)", "LENGTH without TEXT or BINARY"),
        ("DOCUMENT CREATE DOCTOKEN(T) TEMPLATE(M) LENGTH(4)", "LENGTH without TEXT or BINARY"),
        ("DOCUMENT CREATE DOCTOKEN(T) TEXT(A) TEMPLATE(M) LENGTH(3)", "one source of the document"),
        ("DOCUMENT CREATE DOCTOKEN(T) TEXT(A) BINARY(A) LENGTH(3)", "one source of the document"),
        ("DOCUMENT RETRIEVE INTO(A) MAXLENGTH(9) DATAONLY", "without DOCTOKEN"),
        ("DOCUMENT RETRIEVE DOCTOKEN(T) MAXLENGTH(9) DATAONLY", "without INTO"),
        ("DOCUMENT RETRIEVE DOCTOKEN(T) INTO(A) DATAONLY", "without MAXLENGTH"),
        ("DOCUMENT RETRIEVE DOCTOKEN(T) INTO(A) MAXLENGTH(9)", "without DATAONLY"),
        ("DOCUMENT RETRIEVE DOCTOKEN(T) INTO(A) MAXLENGTH(9) DATAONLY CHARACTERSET(CS)", "code-page conversion"),
        ("DOCUMENT RETRIEVE DOCTOKEN(T) INTO(A) MAXLENGTH(9) DATAONLY CLNTCODEPAGE(CS)", "code-page conversion"),
        ("DOCUMENT INSERT DOCTOKEN(T) TEXT(A) LENGTH(3)", "DOCUMENT INSERT / SET / DELETE"),
        ("DOCUMENT INSERT DOCTOKEN(T) TEMPLATE(M)", "DOCUMENT INSERT / SET / DELETE"),
        ("DOCUMENT SET DOCTOKEN(T) SYMBOLLIST(A) LENGTH(3)", "DOCUMENT INSERT / SET / DELETE"),
        ("DOCUMENT DELETE DOCTOKEN(T)", "DOCUMENT INSERT / SET / DELETE"),
    ],
)
def test_document_options_ibm_leaves_open_are_refused_by_name(text, why):
    """#4769 (X33): FROM / FROMDOC, the symbol table, DOCSIZE, code pages, a RETRIEVE without DATAONLY or MAXLENGTH, a CREATE
    of TEXT / BINARY without LENGTH, and INSERT / SET / DELETE are refused with their cause -- never translated as
    something else."""
    with pytest.raises(C.CicsError, match=re.escape(why)):
        _ChanCics().command(text, "")


def test_a_program_with_zecs_shaped_document_commands_translates_with_no_hole(tmp_path):
    """#4769: zECS's shapes -- CREATE DOCTOKEN TEMPLATE(group) NOHANDLE, RETRIEVE DOCTOKEN INTO LENGTH MAXLENGTH DATAONLY
    NOHANDLE with one length area for LENGTH and MAXLENGTH, CREATE with RESP, and a CREATE with no source -- go through the
    whole program translator: no hole, the CicsTask calls in the Java."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    prog = tmp_path / "ZDOC.cbl"
    prog.write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. ZDOC.\n"
        "       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
        "       01  DC-TOKEN               PIC  X(16) VALUE SPACES.\n"
        "       01  DC-LENGTH              PIC S9(08) COMP  VALUE ZEROES.\n"
        "       01  SD-RESP                PIC S9(08) COMP.\n"
        "       01  ZECS-DC.\n"
        "           02  DC-TRANID          PIC  X(04) VALUE 'ZC01'.\n"
        "           02  FILLER             PIC  X(02) VALUE 'DC'.\n"
        "           02  FILLER             PIC  X(42) VALUE SPACES.\n"
        "       01  DC-CONTROL.\n"
        "           02  FILLER             PIC  X(06).\n"
        "           02  DC-TYPE            PIC  X(02) VALUE SPACES.\n"
        "           02  THE-OTHER-DC       PIC X(160) VALUE SPACES.\n"
        "       01  WS-TEXT                PIC  X(20) VALUE 'HELLO'.\n"
        "       PROCEDURE DIVISION.\n"
        "           EXEC CICS DOCUMENT CREATE DOCTOKEN(DC-TOKEN)\n"
        "                TEMPLATE(ZECS-DC)\n"
        "                NOHANDLE\n"
        "           END-EXEC.\n"
        "           MOVE LENGTH OF DC-CONTROL TO DC-LENGTH.\n"
        "           IF  EIBRESP EQUAL DFHRESP(NORMAL)\n"
        "               EXEC CICS DOCUMENT RETRIEVE DOCTOKEN(DC-TOKEN)\n"
        "                    INTO     (DC-CONTROL)\n"
        "                    LENGTH   (DC-LENGTH)\n"
        "                    MAXLENGTH(DC-LENGTH)\n"
        "                    DATAONLY\n"
        "                    NOHANDLE\n"
        "               END-EXEC.\n"
        "           EXEC CICS DOCUMENT CREATE DOCTOKEN(DC-TOKEN)\n"
        "                TEMPLATE(ZECS-DC) RESP(SD-RESP)\n"
        "                NOHANDLE\n"
        "           END-EXEC.\n"
        "           EXEC CICS DOCUMENT CREATE DOCTOKEN(DC-TOKEN)\n"
        "                TEXT(WS-TEXT) LENGTH(5) NOHANDLE\n"
        "           END-EXEC.\n"
        "           EXEC CICS DOCUMENT CREATE DOCTOKEN(DC-TOKEN)\n"
        "                NOHANDLE\n"
        "           END-EXEC.\n"
        "           EXEC CICS RETURN END-EXEC.\n",
        encoding="utf-8",
    )
    vsam = tmp_path / "proj/src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    stub = ("package com.x.service;\nimport com.x.cics.CicsTask;\npublic class ZdocService {\n"
            "    public void runTask(CicsTask task) {}\n}\n")  # fmt: skip
    r = P.translate(prog, [], stub, "com.x", {}, tmp_path / "proj")
    assert r.stats["holes"] == []
    for call in ("task.documentCreateTemplate(", "task.documentCreateData(", "task.documentCreateEmpty(",
                 "task.documentRetrieve(", "DetCics.putDocument("):  # fmt: skip
        assert call in r.java, call


def test_xctl_marks_only_an_operand_inside_the_linkage_dfhcommarea():
    """#4816: an XCTL COMMAREA with no item of its own to resolve (an operand commarea_out handles) is never marked, and
    never raises; one inside a LINKAGE 01 record -- the record or a field of it -- is marked."""
    c = _OverCics()
    assert not any("xctlOfLinkage" in x for x in c.command("XCTL PROGRAM('XB') COMMAREA(WS-BIG) LENGTH(WS-BIGLEN)", ""))
    root = type("I", (), {"name": "DFHCOMMAREA", "section": "LINKAGE", "parent": None})()
    field = type("I", (), {"name": "CA-NUM", "section": "LINKAGE", "parent": root})()
    ws = type("I", (), {"name": "WS-CA", "section": "WORKING-STORAGE", "parent": None})()
    other = type("I", (), {"name": "SUB-AREA", "section": "LINKAGE", "parent": None})()  # #4957: any LINKAGE 01 record
    items = {"DFHCOMMAREA": root, "CA-NUM": field, "WS-CA": ws, "SUB-AREA": other}
    c.SIZES = {**c.SIZES, "DFHCOMMAREA": 12, "CA-NUM": 6, "WS-CA": 12, "SUB-AREA": 12}
    c.g.resolve = lambda ref: items[ref.name]
    for operand, marked in (("DFHCOMMAREA", True), ("CA-NUM", True), ("SUB-AREA", True), ("WS-CA", False)):
        out = c.command(f"XCTL PROGRAM('XB') COMMAREA({operand}) LENGTH(80)", "")
        assert any("task.xctlOfLinkage();" in x for x in out) is marked, (operand, out)


def test_web_retrieve_asks_the_task_and_refuses_every_other_option():
    """#4941 zECS (register X41), IBM WEB RETRIEVE: DOCTOKEN is the only option and is required; the outcome is CicsTask's
    (INVREQ RESP2 2 / NOTFND RESP2 1), the area written with the token on NORMAL only; every other option and the literal
    form are refused."""
    c = _ChanCics()
    r = c.command("WEB RETRIEVE DOCTOKEN(REC) NOHANDLE", "")
    assert r[0].startswith("CicsTask.DocumentCreated web") and ".webRetrieve();" in r[0]
    assert "if (web" in r[1] and ".resp() == 0) DetCics.putText(" in r[1] and ".doctoken(), CS);" in r[1]
    r2 = c.command("WEB RETRIEVE DOCTOKEN(REC) RESP(R) RESP2(R2)", "")
    assert ".webRetrieve();" in r2[0] and len(r2) > 1
    with pytest.raises(C.CicsError, match="without DOCTOKEN"):
        c.command("WEB RETRIEVE NOHANDLE", "")
    for extra in ("SESSTOKEN(KEY)", "FROM(REC)", "ACTION(R)", "DOCSTATUS(R)", "INTO(REC)", "MEDIATYPE(REC)"):
        with pytest.raises(C.CicsError):
            c.command(f"WEB RETRIEVE DOCTOKEN(REC) {extra}", "")


def test_extract_web_is_web_extract():
    """#4972 (register X38): IBM's EXTRACT WEB is "a synonym of WEB EXTRACT" -- the same options, the same CicsTask.webExtract
    call and writes, the same refusals (the messages name the form the program wrote)."""
    c = _ChanCics()
    opts = ("SCHEME(R) HOST(REC) HOSTLENGTH(R2) HTTPMETHOD(REC) METHODLENGTH(R) HTTPVERSION(REC) VERSIONLEN(R) PATH(REC) "
            "PATHLENGTH(R) PORTNUMBER(R) QUERYSTRING(REC) QUERYSTRLEN(R) REQUESTTYPE(R2) NOHANDLE")  # fmt: skip
    old = c.command(f"WEB EXTRACT {opts}", "")
    new = c.command(f"EXTRACT WEB {opts}", "")
    assert [re.sub(r"web\d+", "web", ln) for ln in new] == [re.sub(r"web\d+", "web", ln) for ln in old]
    for form in ("HOST(REC)", "HTTPMETHOD(REC)", "HTTPVERSION(REC)", "PATH(REC)", "QUERYSTRING(REC)", "HOSTLENGTH(R)",
                 "SESSTOKEN(KEY)", "HOSTTYPE(R)", "URIMAP(REC)", "REALM(REC)", "REALMLEN(R)"):  # fmt: skip
        with pytest.raises(C.CicsError) as want:
            c.command(f"WEB EXTRACT {form}", "")
        with pytest.raises(C.CicsError) as got:
            c.command(f"EXTRACT WEB {form}", "")
        assert str(got.value).replace("EXTRACT WEB", "WEB EXTRACT") == str(want.value), form


def test_extract_tcpip_reads_the_stated_connection():
    """#4972 (register X38), IBM EXTRACT TCPIP: CicsTask.extractTcpip takes each address / name area's length option (0 when the
    area is given without its length option: LENGERR RESP2 1) and its area's size, then which numbers are asked for; on NORMAL
    only the bytes, the lengths, the address numbers, the IPv4 family (300), the port and the SSL type's CVDA are written. The
    character port, the IPv6 forms and the TCPIPSERVICE's own settings are refused by name."""
    c = _ChanCics()
    w = c.command(
        "EXTRACT TCPIP CLIENTADDR(REC) CADDRLENGTH(R) CLIENTADDRNU(R2) PORTNUMNU(R2) SSLTYPE(R2) CLNTIPFAMILY(R) NOHANDLE",
        "",
    )
    assert w[0].startswith("CicsTask.TcpipExtracted tcp") and ".extractTcpip(Integer.valueOf(" in w[0]
    assert (
        ", 56, null, 0, null, 0, null, 0, true, false, true, false);" in w[0]
    )  # (the client address number and family)
    body = " ".join(w)
    assert ".resp() == 0) {" in body and ".clientAddr().getBytes(CS)" in body and ".clientAddr().length()" in body
    assert ".clientNu()" in body and ".port()" in body and ".ssl()" in body and "valueOf(300)" in body
    missing = c.command("EXTRACT TCPIP SERVERNAME(REC) NOHANDLE", "")
    assert ".extractTcpip(null, 0, null, 0, null, 0, Integer.valueOf(0), 56, false, false, false, false);" in missing[0]
    for ok in ("CLIENTNAME(REC) CNAMELENGTH(R)", "SERVERADDR(REC) SADDRLENGTH(R) SERVERADDRNU(R2) SRVRIPFAMILY(R2)",
               "SERVERNAME(REC) SNAMELENGTH(R)", "PORTNUMNU(R)", "SSLTYPE(R)", "NOHANDLE"):  # fmt: skip
        assert c.command(f"EXTRACT TCPIP {ok}", "")[0].startswith("CicsTask.TcpipExtracted tcp")
    for bad, why in (("CADDRLENGTH(R)", "CADDRLENGTH without CLIENTADDR"),
                     ("CNAMELENGTH(R)", "CNAMELENGTH without CLIENTNAME"),
                     ("SADDRLENGTH(R)", "SADDRLENGTH without SERVERADDR"),
                     ("SNAMELENGTH(R)", "SNAMELENGTH without SERVERNAME"),
                     ("PORTNUMBER(REC)", "5 characters are padded"),
                     ("CLNTADDR6NU(REC)", "IPv6"),
                     ("SRVRADDR6NU(REC)", "IPv6"),
                     ("AUTHENTICATE(R)", "authentication"),
                     ("TCPIPSERVICE(REC)", "TCPIPSERVICE definition"),
                     ("PRIVACY(R)", "TCPIPSERVICE definition"),
                     ("MAXDATALEN(R)", "TCPIPSERVICE definition"),
                     ("TERMINAL(REC)", "only CLIENTADDR")):  # fmt: skip
        with pytest.raises(C.CicsError, match=why):
            c.command(f"EXTRACT TCPIP {bad}", "")


class _DatasetNameCics(_KeyCics):
    """#5278 (CardDemo COPAUA0C): the file is named by a data item (VALUE 'ACCTDAT ' -> KSDS here), the key by an
    alias item of the key's size (a REDEFINES of a numeric key as X(n)), and KEYLENGTH is LENGTH OF that alias."""

    SIZES = {**_KeyCics.SIZES, "WS-KEY-X": 10, "WS-SHORT-X": 6, "WS-LONG-X": 11}

    def constant(self, text):
        return "KSDS" if text and text.strip() == "WS-FILE" else super().constant(text)


@pytest.mark.parametrize("verb_opts", ["READ", "READ UPDATE"])
def test_read_dataset_name_keylength_length_of_the_key_alias_translates_as_without(verb_opts):
    """#5278: COPAUA0C's three READ ... DATASET(WS-xxx-FILE) RIDFLD(alias) KEYLENGTH(LENGTH OF alias) are the full key
    through a named dataset: the port is the one without KEYLENGTH (no hole once the file is mapped)."""
    plain = _DatasetNameCics().command(f"{verb_opts} DATASET(WS-FILE) INTO(REC) RIDFLD(WS-KEY-X) RESP(R)", "")
    got = _DatasetNameCics().command(
        f"{verb_opts} DATASET(WS-FILE) INTO(REC) RIDFLD(WS-KEY-X) KEYLENGTH(LENGTH OF WS-KEY-X) LENGTH(LENGTH OF REC) RESP(R)",
        "",
    )
    assert got == plain


@pytest.mark.parametrize(("alias", "resp2"), [("WS-SHORT-X", 26), ("WS-LONG-X", 26)])
def test_read_dataset_name_keylength_of_an_alias_not_the_key_size_is_invreq(alias, resp2):
    out = _DatasetNameCics().command(
        f"READ DATASET(WS-FILE) INTO(REC) RIDFLD({alias}) KEYLENGTH(LENGTH OF {alias}) RESP(R)", ""
    )
    assert out[0].endswith(f"{resp2});") and "readInvalid" in out[0]
