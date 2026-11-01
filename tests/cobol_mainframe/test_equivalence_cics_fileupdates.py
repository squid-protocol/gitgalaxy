"""#5274: file updates: WRITE, REWRITE, READ UPDATE and SYNCPOINT. Split out of test_equivalence_cics.py, which every CICS slice appended to."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402


# ---- file updates: WRITE, REWRITE, READ UPDATE, SYNCPOINT (CardDemo's update programs) -----------------------
def test_file_updates_translate_to_stub_calls():
    upd = ec.translate_command("READ DATASET(WS-F) INTO(R) RIDFLD(K) UPDATE RESP(X)")
    assert upd[:4] == ["MOVE WS-F TO GG-NAME1", "MOVE 'UPDATE' TO GG-FLAGS", "MOVE LENGTH OF R TO GG-LEN",
                       "CALL 'GGCREAD' USING GG-CICS"]  # fmt: skip
    w = ec.translate_command("WRITE DATASET(F) FROM(REC) RIDFLD(K) RESP(X)")
    assert w[:2] == ["MOVE F TO GG-NAME1", "CALL 'GGCWRIT' USING GG-CICS"] and "    BY REFERENCE REC" in w
    rw = ec.translate_command("REWRITE FILE(F) FROM(REC) RESP(X) RESP2(Y)")
    assert rw[:3] == [
        "MOVE F TO GG-NAME1",
        "MOVE SPACES TO GG-FLAGS",
        "CALL 'GGCREWR' USING GG-CICS",
    ]  # #5078: flags set
    assert ec.translate_command("SYNCPOINT")[:2] == ["MOVE SPACES TO GG-FLAGS", "CALL 'GGCSYNC' USING GG-CICS"]
    assert ec.translate_command("SYNCPOINT ROLLBACK")[0] == "MOVE 'ROLLBACK' TO GG-FLAGS"
    for bad in ("WRITE FILE(F) FROM(R) RIDFLD(K) MASSINSERT", "REWRITE FILE(F) FROM(R) SYSID(S)"):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(bad)
    sc = {
        "faults": [{"cmd": "REWRITE", "file": "ACCTDAT", "resp": "NOSPACE"}]
    }  # IBM's REWRITE lists no NOTOPEN (#5044)
    assert ec.fault_lines(sc) == ["REWRITE ACCTDAT 1 18 100"]


def test_a_tasks_files_are_compared_in_key_order():
    files = [{"base": "ACCT", "reclen": 6, "key_offset": 0, "key_length": 2}]
    case = {"datasets": {"ACCT": {}}}

    def compare(cobol, java, tmp):
        (tmp / "s.ACCT.out").write_bytes(java)
        return ec.compare_files(case, Path("."), files, {"ACCT": cobol}, tmp, "s")

    import tempfile

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        assert compare(b"02BBBB01AAAA", b"01AAAA02BBBB", tmp) == {}  # the order a store keeps is not data
        diff = compare(b"01AAAA02BBBB", b"01AAAA02BBBX", tmp)
        assert diff["ACCT"]["equal"] == 1 and diff["ACCT"]["records"] == 2
        assert compare(b"01AAAA02BBBB03CCCC", b"01AAAA02BBBB", tmp)["ACCT"]["equal"] == 2  # a WRITE the port missed


def test_a_case_csd_defines_the_programs_and_no_csd_defines_all(tmp_path):
    (tmp_path / "x.csd").write_text(" DEFINE PROGRAM(COMEN01C) GROUP(G)\n DEFINE  PROGRAM(COUSR00C)\n"
                                    " DEFINE TRANSACTION(CM00) PROGRAM(COMEN01C)\n", encoding="ascii")  # fmt: skip
    assert ec.csd_programs(tmp_path, {"csd": "x.csd"}) == ["COMEN01C", "COUSR00C"]
    assert ec.csd_programs(tmp_path, {}) is None
    # the Java side (CicsTask.withPrograms) is proven by carddemo-adminmenu: options 5 and 6 are PGMIDERR on both


def test_formattime_resp_asktime_nohandle_readq_length_of_and_receive_map_asis():
    """#4737 (X28): FORMATTIME is INVREQ RESP2 1 below zero, then RESP / the handlers; ASKTIME NOHANDLE with no ABSTIME
    changes nothing; READQ TS LENGTH(LENGTH OF x) is not set back; RECEIVE MAP ASIS is accepted."""
    fmt = ec.translate_command("FORMATTIME ABSTIME(T) DDMMYYYY(D) RESP(R)")
    assert fmt[:6] == ["MOVE 0 TO GG-RESP", "MOVE 0 TO GG-RESP2", "IF T < 0", "    MOVE 16 TO GG-RESP",
                       "    MOVE 1 TO GG-RESP2", "ELSE"]  # fmt: skip
    assert "MOVE GG-RESP TO R" in fmt and not any("GGCCOND" in x for x in fmt)
    plain = ec.translate_command("FORMATTIME ABSTIME(T) TIME(D)")  # no RESP: an ABSTIME below zero is refused
    assert plain[:2] == ["IF T < 0", "    DISPLAY 'FORMATTIME ABSTIME < 0 NO RESP: not modelled'"]
    assert not any("GG-RESP" in x for x in plain)
    assert ec.translate_command("ASKTIME NOHANDLE") == ["CONTINUE"]
    out = ec.translate_command("READQ TS QUEUE(Q) INTO(A) LENGTH(LENGTH OF A) RESP(R)")
    assert "MOVE LENGTH OF A TO GG-LEN" in out and not any(x.endswith("TO LENGTH OF A") for x in out)
    assert "    MOVE GG-LEN TO L" in ec.translate_command("READQ TS QUEUE(Q) INTO(A) LENGTH(L) RESP(R)")
    assert "CALL 'GGCRECV' USING GG-CICS" in ec.translate_command(
        "RECEIVE MAP('MAP') MAPSET('MS') INTO(MAPI) ASIS RESP(R)"
    )


def test_browse_delete_and_time_commands_translate():
    assert ec.translate_command("STARTBR DATASET(F) RIDFLD(K) EQUAL RESP(R)")[:3] == [
        "MOVE F TO GG-NAME1",
        "MOVE 'EQUAL' TO GG-FLAGS",
        "CALL 'GGCSTBR' USING GG-CICS",
    ]
    assert ec.translate_command("READPREV DATASET(F) INTO(REC) RIDFLD(K) RESP(R)")[2] == "CALL 'GGCRDPV' USING GG-CICS"
    assert ec.translate_command("DELETE FILE(F) RESP(R)")[1] == "MOVE 'HELD' TO GG-FLAGS"  # the READ UPDATE's record
    for bad in (
        "STARTBR FILE(F) RIDFLD(K) GENERIC KEYLENGTH(2)",
        "READNEXT FILE(F) INTO(R) RIDFLD(K) REQID(1)",
        "FORMATTIME ABSTIME(T) DATE(D)",  # #4415 slice 3 (X46): the installation's DATFORM, not stated
        "FORMATTIME ABSTIME(T) DATESTRING(D) STRINGFORMAT(DFHVALUE(RFC1123))",
    ):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(bad)
    long_names = "FORMATTIME ABSTIME(WS-ABS-TIME) YYYYMMDD(WS-CUR-DATE-X10) DATESEP('-') TIME(WS-T) TIMESEP"
    for cmd in ("ASKTIME ABSTIME(WS-ABS-TIME)", long_names):  # each statement fits area B (col 12-72)
        assert all(len(s) <= 61 for s in ec.translate_command(cmd))


def test_an_alphanumeric_commarea_field_reaches_the_port_as_text():
    """CardDemo's CDEMO-CT01-TRN-SELECTED (PIC X(16)) '0000000000683580' reached the port as the number 683580."""
    fields = [{"name": "SEL", "pic": "X(16)"}, {"name": "PAGE", "pic": "9(08)"}, {"name": "AMT", "pic": "S9(5)V99"}]
    shape = {"sel": "SEL", "page": "PAGE", "amt": "AMT"}
    got = ec.to_java({"SEL": "0000000000683580", "PAGE": "00000002", "AMT": "12.50"}, shape, ec.alphanumeric(fields))
    assert got == {"sel": "0000000000683580", "page": 2, "amt": 12.5}


def test_a_repeat_count_with_a_nine_is_not_a_digit_position():
    """COACTUPC's ACUP-OLD-CUST-SSN-X (PIC X(09)) '017590544' reached the port as the number 17590544: the 9 of the
    repetition count read as a numeric PICTURE symbol -- the port then saw another record than COBOL's."""
    fields = [{"name": "SSN", "pic": "X(09)"}, {"name": "ID", "pic": "X(19)"}, {"name": "N", "pic": "9(09)"}]
    assert ec.alphanumeric(fields) == frozenset({"SSN", "ID"})
    got = ec.to_java({"SSN": "017590544", "N": "000000042"}, {"ssn": "SSN", "n": "N"}, ec.alphanumeric(fields))
    assert got == {"ssn": "017590544", "n": 42}


def test_assign_applid_sysid_and_writeq_td_translate():
    got = ec.translate_command("ASSIGN APPLID(A) SYSID(S)")
    assert got[:3] == ["MOVE 'APPLID' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "MOVE GG-NAME1(1:8) TO A(1:8)"]
    assert got[3:6] == ["MOVE 'SYSID' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "MOVE GG-NAME1(1:4) TO S(1:4)"]
    td = ec.translate_command("WRITEQ TD QUEUE('JOBS') FROM(REC) RESP(R)")
    assert td[:4] == ["MOVE 'JOBS' TO GG-QNAME", "MOVE LENGTH OF REC TO GG-LEN", "CALL 'GGCWRTD' USING GG-CICS",
                      "    BY REFERENCE REC"]  # fmt: skip
    # X6 (ASSUMED): TD with a LENGTH past FROM pads through GG-PADQ as TS does; LENGTH within FROM or a literal FROM does not
    pad = ec.translate_command("WRITEQ TD QUEUE('JOBS') FROM(REC) LENGTH(WS-L) RESP(R)")
    assert pad[1:3] == ["MOVE WS-L TO GG-LEN", "IF GG-LEN > LENGTH OF REC"]
    assert "    MOVE REC TO GG-PADQ(1:LENGTH OF REC)" in pad and "        BY REFERENCE GG-PADQ" in pad
    assert pad.count("    CALL 'GGCWRTD' USING GG-CICS") == 2 and "        BY REFERENCE REC" in pad
    assert "GG-PADQ" not in " ".join(ec.translate_command("WRITEQ TD QUEUE('JOBS') FROM('X') LENGTH(1) RESP(R)"))
    assert "GG-PADQ" in ec._PADQ
    with pytest.raises(ec.Unsupported):
        ec.translate_command("ASSIGN OPID(U)")


@pytest.mark.parametrize("opt,width", [("APPLID", 8), ("SYSID", 4), ("ABCODE", 4), ("PROGRAM", 8), ("INVOKINGPROG", 8),
                                       ("STARTCODE", 2), ("USERID", 8)])  # fmt: skip
def test_assign_writes_exactly_the_option_width(opt, width):
    """#4049: IBM ASSIGN writes `width` bytes and leaves a wider data area's tail as it was; a plain MOVE would space it
    (CardDemo SYSIDO is 8 bytes, SYSID 4). The target is reference-modified to the width, whatever its qualification,
    and an already reference-modified target is refused by name."""
    for target in ("WS-X", "SYSIDO OF COSGN0AO", "WS-T(IDX)"):
        assert f"MOVE GG-NAME1(1:{width}) TO {target}(1:{width})" in ec.translate_command(f"ASSIGN {opt}({target})")
    with pytest.raises(ec.Unsupported, match="reference-modified"):
        ec.translate_command(f"ASSIGN {opt}(WS-X(1:2))")


def test_send_text_terminal_translates_as_send_text():
    """#4270 slice 4: TERMINAL, the default output disposition, changes nothing in the stub's call; the logical-message,
    printer and partition options are refused by name (register X20)."""
    plain = ec.translate_command("SEND TEXT FROM(L) WAIT FREEKB ERASE")
    assert ec.translate_command("SEND TEXT FROM(L) TERMINAL WAIT FREEKB ERASE") == plain
    assert plain[0] == "MOVE 'TEXT WAIT FREEKB ERASE' TO GG-FLAGS"
    for opt in ("ACCUM", "PAGING", "HEADER(H)", "JUSTIFY(5)", "L80", "SET(P)"):
        with pytest.raises(ec.Unsupported) as e:
            ec.translate_command(f"SEND TEXT FROM(L) TERMINAL {opt}")
        assert e.value.features == [f"SEND TEXT {opt.split('(')[0]}"]


def test_a_tasks_userid_and_screen_are_stated_only_when_given():
    """#5126 (X19): "userid" (1 to 8 characters) and "screen" ([rows, columns], of a stated termid) -- the scenario's,
    else the case's; absent from the result unless stated, malformed refused."""
    case = {"termid": "T001", "userid": "CICSUSER", "screen": [24, 80]}
    got = ec.terminal_facts(case, {"name": "s"})
    assert (got["userid"], got["screen"]) == ("CICSUSER", [24, 80])
    got = ec.terminal_facts(case, {"name": "s", "userid": "BOB", "screen": [43, 80]})
    assert (got["userid"], got["screen"]) == ("BOB", [43, 80])
    assert "userid" not in ec.terminal_facts({"termid": "T001"}, {"name": "s"})
    assert "screen" not in ec.terminal_facts({}, {"name": "s"})
    for bad in ({"userid": ""}, {"userid": "NINECHARS"}, {"userid": "A B"}, {"userid": "A,B"}, {"userid": 7},
                {"termid": "T001", "screen": [24]}, {"termid": "T001", "screen": [24, 0]},
                {"termid": "T001", "screen": [24, "80"]}, {"termid": "T001", "screen": "24 80"},
                {"screen": [24, 80]}):  # fmt: skip
        with pytest.raises(ec.Unsupported):
            ec.terminal_facts({}, {"name": "s", **bad})


def test_a_terminal_device_is_stated_only_when_given_and_reaches_both_sides():
    """#7434 (X15): "device" ("3270" or "LUTYPE2") -- the scenario's, else the case's; absent unless stated, anything
    else refused by name; LUTYPE2 sets the stub's GGCICS_LU2 and the port's withEndOfChain."""
    assert "device" not in ec.terminal_facts({}, {"name": "s"})
    for dev in ("3270", "LUTYPE2"):
        assert ec.terminal_facts({"device": dev}, {"name": "s"})["device"] == dev
    assert ec.terminal_facts({"device": "3270"}, {"name": "s", "device": "LUTYPE2"})["device"] == "LUTYPE2"
    for bad in ("LUTYPE6", "", "lutype2", 2):
        with pytest.raises(ec.Unsupported):
            ec.terminal_facts({}, {"name": "s", "device": bad})
    src = Path(ec.__file__).read_text(encoding="utf-8")
    assert ec._cobol_read("RECEIVE", {"resp": "6"}, b"AB", "ascii")["data"] == "AB"  # EOC delivers its data
    assert 'GGCICS_LU2=1 " if term.get("device") == "LUTYPE2"' in src
    assert '.withEndOfChain("LUTYPE2".equals(sc.path("device").asText()))' in src


def test_assign_startcode_userid_and_the_terminal_facts_translate():
    """#4270 slice 3: STARTCODE / USERID through GGCASGN; FACILITY / SCRNHT / SCRNWD behind TERMCHK (INVREQ RESP2 5 for
    a task with no terminal, then no data area written), with the condition's handling."""
    got = ec.translate_command("ASSIGN STARTCODE(SC) USERID(U)")
    assert got[:6] == ["MOVE 'STARTCOD' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "MOVE GG-NAME1(1:2) TO SC(1:2)",
                       "MOVE 'USERID' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "MOVE GG-NAME1(1:8) TO U(1:8)"]  # fmt: skip
    got = ec.translate_command("ASSIGN FACILITY(F) SCRNHT(H) RESP(R)")
    assert got[:4] == ["MOVE 'TERMCHK' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "IF GG-RESP = 0",
                       "    MOVE 'FACILITY' TO GG-NAME2"]  # fmt: skip
    assert "    MOVE GG-NUM TO H" in got and "MOVE GG-RESP TO R" in got
    assert "    CALL 'GGCCOND' USING GG-CICS" in ec.translate_command("ASSIGN SCRNWD(W)")


def test_an_esds_browse_by_rba_translates_and_the_rest_of_rba_is_refused():
    """#4213 (IBM DBB EPSMLIST): STARTBR / READNEXT / READPREV ... RBA reach the stub with 'RBA' in GG-FLAGS.
    IBM, EXEC CICS STARTBR: EQUAL "is the default for a direct ESDS browse" and GTEQ "is not valid for directly
    browsing an ESDS", so an RBA browse is EQUAL and GTEQ with RBA is refused; READ / WRITE / DELETE by RBA, XRBA,
    RRN and KEYLENGTH with RBA are not modelled (refused by name)."""
    assert ec.translate_command("STARTBR DATASET('EPSMORTF') RIDFLD(RID-LENGTH) RBA EQUAL RESP(R)")[:3] == [
        "MOVE 'EPSMORTF' TO GG-NAME1",
        "MOVE 'EQUAL RBA' TO GG-FLAGS",
        "CALL 'GGCSTBR' USING GG-CICS",
    ]
    assert ec.translate_command("STARTBR FILE(F) RIDFLD(K) RBA RESP(R)")[1] == "MOVE 'EQUAL RBA' TO GG-FLAGS"
    for verb, stub in (("READNEXT", "GGCRDNX"), ("READPREV", "GGCRDPV")):
        assert ec.translate_command(f"{verb} FILE(F) INTO(REC) RIDFLD(K) RBA RESP(R)")[:3] == [
            "MOVE F TO GG-NAME1",
            "MOVE 'RBA' TO GG-FLAGS",
            f"CALL '{stub}' USING GG-CICS",
        ]
        # a keyed READNEXT says so too: GG-FLAGS is not left as the last command set it
        assert ec.translate_command(f"{verb} FILE(F) INTO(REC) RIDFLD(K) RESP(R)")[1] == "MOVE SPACES TO GG-FLAGS"
    for bad in (
        "STARTBR FILE(F) RIDFLD(K) RBA GTEQ",
        "STARTBR FILE(F) RIDFLD(K) RBA KEYLENGTH(4)",
        "STARTBR FILE(F) RIDFLD(K) XRBA",
        "STARTBR FILE(F) RIDFLD(K) RRN",
        "READNEXT FILE(F) INTO(R) RIDFLD(K) XRBA",
        "READPREV FILE(F) INTO(R) RIDFLD(K) RRN",
        "READNEXT FILE(F) INTO(R) RIDFLD(K) RBA KEYLENGTH(4)",
        "READ FILE(F) INTO(R) RIDFLD(K) RBA",
        "WRITE FILE(F) FROM(R) RIDFLD(K) RBA",
        "DELETE FILE(F) RIDFLD(K) RBA",
    ):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(bad)


class _NoDefineIR:
    """An estate whose CICS file has no CSD DEFINE FILE (IBM DBB MortgageApplication's EPSMORTF)."""

    files: dict = {}

    @staticmethod
    def cics_file_lineage():
        return [{"program": "p.cbl", "name": "EPSMORTF", "definitions": []}]


def test_a_case_states_an_esds_the_estate_does_not_define():
    """#4213: with no CSD DEFINE FILE nor IDCAMS DEFINE in the estate, the case's dataset may state the file
    (`csd`: organization ESDS, reclen, why) -- a deployment fact, as `recovery` is. Anything else stays refused."""
    csd = {"organization": "ESDS", "reclen": 56, "why": "stated"}
    assert ec.stub_files(_NoDefineIR(), "p.cbl", {"EPSMORTF": {"csd": csd}}) == [
        {
            "file": "EPSMORTF",
            "dsname": "EPSMORTF",
            "base": "EPSMORTF",
            "key_offset": 0,
            "key_length": 0,
            "reclen": 56,
            "via": ["the case's csd"],
            "organization": "ESDS",
        }  # fmt: skip
    ]
    with pytest.raises(ec.Unsupported):
        ec.stub_files(_NoDefineIR(), "p.cbl", {})
    for wrong in ({"organization": "KSDS", "reclen": 56, "why": "x"}, {"organization": "ESDS", "why": "x"},
                  {"organization": "ESDS", "reclen": 56}):  # fmt: skip
        with pytest.raises(ec.Unsupported):
            ec.stub_files(_NoDefineIR(), "p.cbl", {"EPSMORTF": {"csd": wrong}})


class _SymbolicIR:
    """An estate whose CSD names a file with install symbols and whose IDCAMS job the engine does not read as a define
    (zECS: ZCEXPIRE.idcams is not JCL), as `record_format` says."""

    files: dict = {}

    def __init__(self, dsname="@ECS_HLQ@.ZCEXPIRE.@ENVIRONMENT@", record_format="V"):
        self.dsname, self.record_format = dsname, record_format

    @staticmethod
    def vsam_stores():
        return []

    def cics_file_lineage(self):
        return [{"program": "p.cbl", "name": "ZCEXPIRE", "definitions": [
            {"file": "ZCEXPIRE", "dsname": self.dsname, "record_format": self.record_format}]}]  # fmt: skip


_SYMBOLS = {"values": {"ECS_HLQ": "ZECS", "ENVIRONMENT": "TEST"}, "why": "this install"}
_VSAM = {"key_offset": 0, "key_length": 4, "reclen": 70, "variable": True, "why": "ZCEXPIRE.idcams KEYS(4 0)"}


def test_install_symbols_are_stated_by_the_case_never_guessed():
    """#5089: `@NAME@` placeholders in a dataset name resolve only to what the case's install_symbols state (names are
    not case-sensitive); the stated file keeps the resolved name; anything unstated or malformed is refused."""
    symbols = ec.install_symbols(_SYMBOLS)
    assert symbols == {"ECS_HLQ": "ZECS", "ENVIRONMENT": "TEST"}
    assert ec.install_symbols(None) == {}
    assert ec.substitute_install_symbols("@ecs_hlq@.ZCEXPIRE.@environment@", symbols) == "ZECS.ZCEXPIRE.TEST"
    assert ec.substitute_install_symbols("@ECS_HLQ@.@OTHER@", symbols) == "ZECS.@OTHER@"  # left: refused by the caller
    assert ec.substitute_install_symbols("PLAIN.NAME", symbols) == "PLAIN.NAME"
    assert ec.substitute_install_symbols("@A@.@A@", {"A": "X"}) == "X.X"  # every occurrence
    assert ec.stub_files(_SymbolicIR(), "p.cbl", {"ZECS.ZCEXPIRE.TEST": {"vsam": _VSAM}}, symbols) == [
        {
            "file": "ZCEXPIRE",
            "dsname": "ZECS.ZCEXPIRE.TEST",
            "base": "ZECS.ZCEXPIRE.TEST",
            "key_offset": 0,
            "key_length": 4,
            "reclen": 70,
            "via": ["the case's install_symbols", "the case's vsam"],
        }  # fmt: skip
    ]


@pytest.mark.parametrize(
    "bad",
    [
        {"values": {"ECS_HLQ": "ZECS"}},  # no why
        {"values": {"ECS_HLQ": "ZECS"}, "why": ""},
        {"values": {}, "why": "x"},
        {"values": {"ECS_HLQ": "zecs"}, "why": "x"},  # not upper case
        {"values": {"ECS_HLQ": 3}, "why": "x"},
        {"values": {"ECS HLQ": "ZECS"}, "why": "x"},
        {"values": {"A": "X", "a": "Y"}, "why": "x"},  # twice
        {"values": {"A": "X"}, "why": "x", "extra": 1},
        ["ECS_HLQ"],
        {"ECS_HLQ": "ZECS"},  # the values are one level down
    ],
)
def test_malformed_install_symbols_are_refused(bad):
    with pytest.raises(ec.Unsupported):
        ec.install_symbols(bad)


def test_an_unstated_install_symbol_or_a_missing_vsam_is_refused():
    """#5089: a symbol the case does not state, no stated KEYS / RECORDSIZE, a V file not acknowledged as stood in for
    by a fixed record length -- each stops the case by name; a stale key (a symbol no name uses) is not an error."""
    only_hlq = ec.install_symbols({"values": {"ECS_HLQ": "ZECS"}, "why": "x"})
    with pytest.raises(ec.Unsupported, match="install symbol the case does not state"):
        ec.stub_files(_SymbolicIR(), "p.cbl", {"ZECS.ZCEXPIRE.TEST": {"vsam": _VSAM}}, only_hlq)
    symbols = ec.install_symbols(_SYMBOLS)
    for datasets in ({}, {"ZECS.ZCEXPIRE.TEST": {}}, {"ZECS.ZCEXPIRE.TEST": {"vsam": {**_VSAM, "why": ""}}},
                     {"ZECS.ZCEXPIRE.TEST": {"vsam": {**_VSAM, "reclen": "70"}}},
                     {"ZECS.ZCEXPIRE.TEST": {"vsam": {k: v for k, v in _VSAM.items() if k != "key_length"}}}):  # fmt: skip
        with pytest.raises(ec.Unsupported, match="no IDCAMS DEFINE"):
            ec.stub_files(_SymbolicIR(), "p.cbl", datasets, symbols)
    with pytest.raises(ec.Unsupported, match="variable-length"):
        ec.stub_files(_SymbolicIR(), "p.cbl", {"ZECS.ZCEXPIRE.TEST": {"vsam": {**_VSAM, "variable": False}}}, symbols)
    fixed = ec.stub_files(_SymbolicIR(record_format="F"), "p.cbl",
                          {"ZECS.ZCEXPIRE.TEST": {"vsam": {**_VSAM, "variable": False}}}, symbols)  # fmt: skip
    assert fixed[0]["reclen"] == 70
    # no symbols stated: the name stays symbolic and is refused as before (the engine's candidate join is separate)
    with pytest.raises(ec.Unsupported, match="no IDCAMS DEFINE"):
        ec.stub_files(_SymbolicIR(), "p.cbl", {"ZECS.ZCEXPIRE.TEST": {"vsam": _VSAM}})
    # a name with no symbols at all is not touched by the stated ones
    with pytest.raises(ec.Unsupported, match="no IDCAMS DEFINE"):
        ec.stub_files(_SymbolicIR(dsname="PLAIN.ZCEXPIRE"), "p.cbl", {"PLAIN.ZCEXPIRE": {"vsam": _VSAM}}, symbols)


def test_a_retrieve_is_compared_as_the_task_records_it():
    """#5089: RETRIEVE's resp, length and data (INTO) and the RTRANSID / RTERMID / QUEUE it returned, from the stub's
    log and from CicsTask's event -- ENDDATA, a NORMAL record, a LENGERR truncation and a RETRIEVE with no INTO."""
    import base64

    assert ec._cobol_retrieve({"resp": "29", "len": "-1", "copied": "0", "into": "1"}, b"", "cp037") == {
        "resp": "ENDDATA", "length": None, "data": None}  # fmt: skip
    got = ec._cobol_retrieve({"resp": "0", "len": "3", "copied": "3", "into": "1", "rtransid": "5a583031"}, b"abc",
                             "ascii")  # fmt: skip
    assert got == {"resp": "NORMAL", "length": 3, "data": "abc", "rtransid": "ZX01"}
    assert ec._cobol_retrieve({"resp": "22", "len": "9", "copied": "2", "into": "1"}, b"ab", "ascii")["length"] == 9
    assert ec._cobol_retrieve({"resp": "0", "len": "0", "copied": "0", "into": "0"}, b"", "ascii")["length"] is None
    java = {"event": "RETRIEVE", "resp": "NORMAL", "length": 3, "data": base64.b64encode(b"\xc1\xc2\xc3").decode()}
    assert ec.java_retrieve_as_compared(java)["data"] == "ABC"  # the region's EBCDIC page
    assert ec.java_retrieve_as_compared({"resp": "ENDDATA", "data": None})["data"] is None


def test_an_esds_is_compared_in_arrival_order():
    """#4213: an ESDS has no key -- its records' order is their RBAs, so it is data and is compared as it is."""
    files = [{"base": "LOG", "reclen": 2, "key_offset": 0, "key_length": 0, "organization": "ESDS"}]
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "s.LOG.out").write_bytes(b"BBAA")
        diff = ec.compare_files({"datasets": {"LOG": {}}}, Path("."), files, {"LOG": b"AABB"}, tmp, "s")
        assert diff["LOG"]["equal"] == 0 and diff["LOG"]["records"] == 2
