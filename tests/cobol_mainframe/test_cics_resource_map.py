"""
#5120: CICS macro tables and the CSD merged into one resource map.

Two hand-written estates (tests/fixtures/cics_macro_estate): `tables_only`
(DFHFCT / DFHPCT / DFHPPT / DFHDCT / DFHTST, no CSD) and `tables_and_csd` (three of
the tables plus REGION.csd, built so some resources agree, some disagree and some
sit in one source only). A REAL scan, so the hlasm dialect's `csd_resources` key is
proven to reach csd_resource_data through the config pipeline.
"""

import shutil
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from scan_server import scan_to_db

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cics_macro_estate"


def _ir(tmp_path_factory, estate):
    base = tmp_path_factory.mktemp(f"macro_{estate}")
    repo = base / "region"
    shutil.copytree(FIXTURES / estate, repo)
    return load_galaxy_ir(scan_to_db(repo, base / "scan"))


@pytest.fixture(scope="module")
def tables_only(tmp_path_factory):
    return _ir(tmp_path_factory, "tables_only")


@pytest.fixture(scope="module")
def both(tmp_path_factory):
    return _ir(tmp_path_factory, "tables_and_csd")


def _entry(ir, rtype, name):
    return next(e for e in ir.resource_map() if (e["resource_type"], e["name"]) == (rtype, name))


def test_tables_only_estate_produces_every_resource_type_with_provenance(tables_only):
    entries = {(e["resource_type"], e["name"]): e for e in tables_only.resource_map()}
    assert {t for t, _ in entries} == {
        "FILE",
        "TRANSACTION",
        "PROGRAM",
        "MAPSET",
        "PARTITIONSET",
        "TDQUEUE",
        "TSMODEL",
        "SIT",
        "SRT",
        "JOURNAL",
        "TERMINAL",
        "CONNECTION",
        "MONITORPOINT",
        "PLT",
        "DB2CONN",
        "DB2ENTRY",
    }
    acct = entries[("FILE", "ACCTDAT")]
    assert acct["sources"] == ["MACRO"]
    (d,) = acct["definitions"]
    assert (d["macro_table"], d["defined_in"], d["line"]) == ("DFHFCT01", "DFHFCT.asm", 5)
    assert acct["merged"]["dsname"] == "BANK.ACCT.DAM" and acct["merged"]["key_length"] == 11
    audt = entries[("TDQUEUE", "AUDT")]["merged"]
    assert (audt["ddname"], audt["dsname"], audt["queue_type"]) == ("AUDITDD", None, "EXTRA")  # SDSCI has no DSNAME
    assert entries[("TDQUEUE", "CSSL")]["merged"]["transid"] == "CSML"
    assert ("FILE", "RMTFIL") in entries and ("MAPSET", "BANKMAP") in entries and ("MAPSET", "BANKM2") in entries
    assert {n for t, n in entries if t == "PARTITIONSET"} == {"BANKPS", "BANKP2"}
    assert entries[("TRANSACTION", "BA01")]["merged"]["program"] == "BANKINQ"
    pct_res = {r.name: r for r in tables_only.files["DFHPCT.asm"].csd_resources}
    assert "PRIORITY(100) INDOUBT(WAIT)" in pct_res["BA01"].attributes
    assert [(t.transid, t.program, t.group) for t in tables_only.files["DFHPCT.asm"].transactions] == [
        ("BA01", "BANKINQ", "DFHPCT01"),
        ("BA02", "BANKUPD", "DFHPCT01"),
    ]
    assert {n for t, n in entries if t == "TSMODEL"} == {"BANK", "AUDT", "RCV", "SEC", "RMT"}


def test_sibling_tables_carry_their_provenance_through_a_real_scan(tables_only):
    entries = {(e["resource_type"], e["name"]): e for e in tables_only.resource_map()}
    assert {n for t, n in entries if t == "SRT"} == {"S0C1", "S0C4", "U1234"}  # S0C7 is RECOVER=NO: a removal
    assert {n for t, n in entries if t == "JOURNAL"} == {"SYSTEM", "03"}
    assert {n for t, n in entries if t == "TERMINAL"} == {"T001", "T002", "SEQ1", "R001"}
    tct_res = {r.name: r for r in tables_only.files["DFHTCT.asm"].csd_resources}
    assert "REMOTESYSTEM(SYSB)" in tct_res["T002"].attributes
    assert "REMOTESYSTEM" not in tct_res["SEQ1"].attributes
    assert {n for t, n in entries if t == "MONITORPOINT"} == {"USER.202", "BANK.180"}
    (d,) = entries[("SIT", "DFHSIT")]["definitions"]
    assert (d["macro_table"], d["defined_in"], d["line"]) == ("DFHSIT", "DFHSIT.asm", 4)
    (d,) = entries[("CONNECTION", "SYSB")]["definitions"]
    assert (d["macro_table"], d["defined_in"]) == ("DFHTCT01", "DFHTCT.asm")
    assert {n for t, n in entries if t == "PLT"} == {"BANKPLT1", "BANKPLT2", "BANKPLT3"}
    plt_res = {r.name: r for r in tables_only.files["DFHPLT.asm"].csd_resources}
    assert "STAGE(1)" in plt_res["BANKPLT2"].attributes and "STAGE(2)" in plt_res["BANKPLT3"].attributes
    assert entries[("DB2CONN", "DFHRCT01")]["merged"]["plan"] == "BANKPLN"
    assert {n for t, n in entries if t == "DB2ENTRY"} == {"BA01", "BA02", "BA03"}
    assert entries[("DB2ENTRY", "BA01")]["merged"]["plan"] == "BANKINQP"
    assert entries[("DB2ENTRY", "BA02")]["merged"]["plan"] == "BANKPLN"
    plans = {p["transid"]: p for p in tables_only.transaction_db2_plans()}
    assert (plans["BA01"]["plan"], plans["BA01"]["programs"]) == ("BANKINQP", ["BANKINQ"])
    assert (plans["BA02"]["plan"], plans["BA02"]["programs"]) == ("BANKPLN", ["BANKUPD"])


def test_tables_assembled_inside_jcl_reach_the_resource_map(tmp_path_factory):
    ir = _ir(tmp_path_factory, "jcl_assembled")
    entries = {(e["resource_type"], e["name"]): e for e in ir.resource_map()}
    assert set(entries) == {("FILE", "ACCTDAT"), ("SRT", "U4321"), ("TERMINAL", "T002")}  # NOASM.jcl reads nothing
    (d,) = entries[("FILE", "ACCTDAT")]["definitions"]
    assert (d["source"], d["macro_table"], d["defined_in"], d["line"]) == ("MACRO", "DFHFCT01", "ASMTABLE.jcl", 7)
    assert entries[("FILE", "ACCTDAT")]["merged"]["dsname"] == "BANK.ACCT.DAM"


def test_tables_only_estate_has_no_conflicts(tables_only):
    assert tables_only.resource_conflicts() == []


def test_a_macro_file_joins_dataset_lineage_like_a_csd_file(tables_only):
    files = {f["file"]: f for f in tables_only.cics_file_datasets()}
    assert files["ACCTDAT"]["dsname"] == "BANK.ACCT.DAM"
    assert files["ACCTDAT"]["defined_in"] == "DFHFCT.asm"


def test_macro_and_csd_definitions_merge_into_one_entry(both):
    acct = _entry(both, "FILE", "ACCTDAT")
    assert acct["sources"] == ["CSD", "MACRO"]
    assert sorted(d["source"] for d in acct["definitions"]) == ["CSD", "MACRO"]
    assert acct["merged"]["dsname"] == "BANK.ACCT.DAM"  # they agree
    assert _entry(both, "MAPSET", "BANKMAP")["sources"] == ["CSD", "MACRO"]
    assert {d["defined_in"] for d in acct["definitions"]} == {"DFHFCT.asm", "REGION.csd"}
    # TDQUEUE AUDT: the macro EXTRA+SDSCI and the CSD DEFINE state the same ddname, format and size.
    audt = _entry(both, "TDQUEUE", "AUDT")["merged"]
    assert (audt["ddname"], audt["record_format"]) == ("AUDITDD", "VARIABLE")


def test_conflicts_are_named_with_both_sides_and_their_provenance(both):
    attr = {
        (c["resource_type"], c["name"], c["field"]): c for c in both.resource_conflicts() if c["kind"] == "attribute"
    }
    assert set(attr) == {
        ("FILE", "CUSTDAT", "dsname"),
        ("TRANSACTION", "BA02", "program"),
        ("TDQUEUE", "CSSL", "transid"),
    }
    c = attr[("FILE", "CUSTDAT", "dsname")]
    seen = {(v["value"], v["defined"][0]["source"], v["defined"][0]["defined_in"]) for v in c["values"]}
    assert seen == {("BANK.CUST.DAM", "MACRO", "DFHFCT.asm"), ("BANK.CUST.OTHER", "CSD", "REGION.csd")}
    assert {v["value"] for v in attr[("TDQUEUE", "CSSL", "transid")]["values"]} == {"CSML", "CSMT"}
    assert _entry(both, "FILE", "CUSTDAT")["merged"]["dsname"] is None  # no silent winner
    assert {v["value"] for v in attr[("TRANSACTION", "BA02", "program")]["values"]} == {"BANKUPD", "BANKXFR"}


def test_a_field_one_source_omits_is_not_a_conflict(both):
    # The macro CUSTDAT states no RECSIZE and the CSD states none either; ACCTDAT's
    # macro and CSD both state RECORDSIZE. A one-sided value merges, never conflicts.
    assert not [
        c for c in both.resource_conflicts() if c["kind"] == "attribute" and c["field"] in ("record_size", "key_length")
    ]
    assert _entry(both, "FILE", "CUSTDAT")["merged"]["key_length"] == 16


def test_single_source_resources_are_named_only_in_when_both_sources_exist(both):
    only = {(c["resource_type"], c["name"]): c["only_in"] for c in both.resource_conflicts() if c["kind"] == "only_in"}
    assert only[("FILE", "MACONLY")] == "MACRO"
    assert only[("FILE", "CSDONLY")] == "CSD"
    assert ("FILE", "ACCTDAT") not in only


def test_an_assembler_step_with_a_sysin_member_joins_that_members_tables(tmp_path_factory):
    """#5154: `//SYSIN DD DSN=lib(MEMBER)` names the member whose tables the step assembles."""
    ir = _ir(tmp_path_factory, "jcl_member")
    got = {r["step"]: r for r in ir.job_macro_tables()}
    assert set(got) == {"ASM1", "ASM2", "ASM3"}  # ASM4 has no member, COMP is not an assembler
    asm1 = got["ASM1"]
    assert (asm1["file"], asm1["job"], asm1["member"], asm1["member_file"]) == (
        "ASMJOB.jcl",
        "ASMJOB",
        "DFHFCT01",
        "DFHFCT01.asm",
    )
    assert [(r["resource_type"], r["name"], r["macro_table"], r["defined_in"]) for r in asm1["resources"]] == [
        ("FILE", "ACCTDAT", "DFHFCT01", "DFHFCT01.asm")
    ]
    assert got["ASM2"]["member_file"] is None and got["ASM2"]["resources"] == []  # named, not found: a finding
    assert [r["name"] for r in got["ASM3"]["resources"]] == ["U4321"]  # member name matched case-blind
    assert ("FILE", "ACCTDAT") in {
        (e["resource_type"], e["name"]) for e in ir.resource_map()
    }  # counted once, in the file
    (d,) = next(e for e in ir.resource_map() if e["name"] == "ACCTDAT")["definitions"]
    assert d["defined_in"] == "DFHFCT01.asm"


def test_sysin_member_join_covers_every_shape_and_member_state(tmp_path_factory):
    """#5154 (#5218): SYSIN shape x member state, each with its `status`."""
    ir = _ir(tmp_path_factory, "jcl_sysin_shapes")
    got = [(r["step"], r["member"], r["status"], r["member_file"]) for r in ir.job_macro_tables()]
    assert got == [
        ("DIRECT", "TBL01", "joined", "lib/TBL01.asm"),
        ("EMPTY", "EMPTY01", "no_tables", "lib/EMPTY01.asm"),  # found and read: nothing to join
        ("MISSING", "NOSUCH", "not_found", None),
        ("TWOFILES", "DUP01", "ambiguous", None),  # two files of that name: a finding, not a guess
        ("CONCAT", "TBL01", "joined", "lib/TBL01.asm"),  # concatenated, unnamed DDs: each its own entry
        ("CONCAT", "EMPTY01", "no_tables", "lib/EMPTY01.asm"),
        ("CONCAT", "NOSUCH", "not_found", None),
        ("AUPLE", "TBL01", "joined", "lib/TBL01.asm"),  # DFHAUPLE, //ASSEM.SYSIN override
    ]
    # not read: MYASM (an unknown wrapper proc), PSTEP.ASM.SYSIN (a qualified name we do not
    # resolve), a DSN with no member, in-stream SYSIN (the job's own rows), a non-assembler step
    by = {(r["step"], r["member"]): r for r in ir.job_macro_tables()}
    assert [(x["resource_type"], x["name"], x["defined_in"]) for x in by["DIRECT", "TBL01"]["resources"]] == [
        ("FILE", "ACCTDAT", "lib/TBL01.asm")
    ]
    for key in (("EMPTY", "EMPTY01"), ("MISSING", "NOSUCH"), ("TWOFILES", "DUP01")):
        assert by[key]["resources"] == []


def test_resolved_wrapper_proc_joins_its_assembler_step_sysin(tmp_path):
    """#5218: a procedure in the repository whose inner step runs an assembler joins its SYSIN (override or proc DD),
    while a non-assembler inner step's SYSIN and an unresolvable proc name stay ignored."""
    base = tmp_path / "wrap"
    repo = base / "region"
    shutil.copytree(FIXTURES / "jcl_sysin_shapes", repo)
    (repo / "procs").mkdir()
    (repo / "procs" / "BANKASM.prc").write_text(
        "//BANKASM  PROC\n"
        "//PRE      EXEC PGM=IEFBR14\n"
        "//ASMSTEP  EXEC PGM=ASMA90\n"
        "//SYSIN    DD DSN=BANK.SRCLIB(EMPTY01),DISP=SHR\n",
        encoding="utf-8",
    )
    (repo / "WRAPJOB.jcl").write_text(
        "//WRAPJOB  JOB (ACCT),'WRAP',CLASS=A\n"
        "//OVR      EXEC BANKASM\n"
        "//ASMSTEP.SYSIN DD DSN=BANK.SRCLIB(TBL01),DISP=SHR\n"
        "//DEF      EXEC BANKASM\n"
        "//NOTASM   EXEC BANKASM\n"
        "//PRE.SYSIN DD DSN=BANK.SRCLIB(TBL01),DISP=SHR\n"
        "//         DD DSN=BANK.SRCLIB(TBL01),DISP=SHR\n"  # #5218: PRE's concatenation, not ASMSTEP's override
        "//CONCAT   EXEC BANKASM\n"
        "//ASMSTEP.SYSIN DD DSN=BANK.SRCLIB(EMPTY01),DISP=SHR\n"
        "//         DD DSN=BANK.SRCLIB(TBL01),DISP=SHR\n"
        "//UNKNOWN  EXEC MYASM\n"
        "//ASMSTEP.SYSIN DD DSN=BANK.SRCLIB(TBL01),DISP=SHR\n",
        encoding="utf-8",
    )
    ir = load_galaxy_ir(scan_to_db(repo, base / "scan"))
    got = [(r["step"], r["member"], r["status"]) for r in ir.job_macro_tables() if r["file"] == "WRAPJOB.jcl"]
    assert got == [
        ("OVR", "TBL01", "joined"),  # //ASMSTEP.SYSIN override wins over the proc's own SYSIN
        ("DEF", "EMPTY01", "no_tables"),  # no override: the proc's own ASMSTEP SYSIN
        ("NOTASM", "EMPTY01", "no_tables"),  # //PRE.SYSIN (and its concatenation) is IEFBR14's, not ASMSTEP's
        ("CONCAT", "EMPTY01", "no_tables"),  # an override concatenation: every DD is joined
        ("CONCAT", "TBL01", "joined"),
    ]


def test_assembler_proc_call_forms_join_only_the_override_sysin_they_state(tmp_path):
    """#5218: DFHAUPLE keyword form, no override, symbolic assembler program, temp SYSIN, nested and doubly qualified
    override DDs, and step-name case: each either joins its member or is not read (refused by name, never guessed)."""
    base = tmp_path / "forms"
    repo = base / "region"
    shutil.copytree(FIXTURES / "jcl_sysin_shapes", repo)
    (repo / "FORMS.jcl").write_text(
        "//FORMS    JOB (ACCT),'FORMS',CLASS=A\n"
        "//KEYWORD  EXEC PROC=DFHAUPLE,TABLE=X\n"
        "//ASSEM.SYSIN DD DSN=BANK.SRCLIB(TBL01),DISP=SHR\n"
        "//BARE     EXEC DFHAUPLE\n"
        "//SYMBOLIC EXEC PGM=&ASMBLR\n"
        "//SYSIN    DD DSN=&&TEMPM,DISP=(OLD,PASS)\n"
        "//lower    EXEC pgm=asma90\n"
        "//sysin    DD DSN=BANK.SRCLIB(TBL01),DISP=SHR\n"
        "//QUAL     EXEC DFHAUPLE\n"
        "//QUAL.ASSEM.SYSIN DD DSN=BANK.SRCLIB(TBL01),DISP=SHR\n",
        encoding="utf-8",
    )
    ir = load_galaxy_ir(scan_to_db(repo, base / "scan"))
    got = [(r["step"], r["member"], r["status"]) for r in ir.job_macro_tables() if r["file"] == "FORMS.jcl"]
    assert got == [
        ("KEYWORD", "TBL01", "joined"),
        ("LOWER", "TBL01", "joined"),  # the parser upper-cases step names
    ]
