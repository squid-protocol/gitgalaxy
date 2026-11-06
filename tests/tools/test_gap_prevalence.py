"""gap_prevalence (#5865): per-gap estate / program counts by era over synthetic survey rows and inventories."""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gap_prevalence as gp

A, B = "zecs", "cics-genapp"  # burned estates


def inv(root: Path, corpus: str, eras: dict[str, int | None]) -> None:
    progs = {p: {"era": e, "earliest": e, "mixed": False, "tells": []} for p, e in eras.items()}
    (root / f"{corpus}.json").write_text(json.dumps({"eras": {"programs": progs}}), encoding="utf-8")


def row(*holes: str) -> dict:
    return {"statements": 3, "holes": list(holes)}


@pytest.fixture
def rows_and_inv(tmp_path):
    inv(tmp_path, A, {"a1.cbl": 1, "a2.cbl": 4, "a3.cbl": None, "a4.cbl": 2, "a5.cbl": 2})
    inv(tmp_path, B, {"b1.cbl": 2})
    rows = {
        (A, "a1.cbl"): row("line 3: EXEC CICS: GETMAIN not modelled"),
        (A, "a2.cbl"): row(
            "line 3: EXEC CICS: GETMAIN not modelled", "line 9: EXEC EXEC SQL: DECLARE CURSOR WITH HOLD"
        ),
        (A, "a3.cbl"): row(),
        (A, "a4.cbl"): {"error": "CopyNotFound: COPY BAQRI not found"},
        (A, "a5.cbl"): {"error": "NotSupported: m.cbl:4: CICS Assembler not supported"},
        (B, "b1.cbl"): row("line 5: EXEC CICS: GETMAIN not modelled"),
        (B, "b2.cbl"): row("line 7: HOLE does not parse"),  # no inventory era for it
    }
    return rows, tmp_path


def test_counts_estates_programs_and_eras(rows_and_inv):
    rows, d = rows_and_inv
    res = gp.measure(rows, d, top=(1, 2))
    by = {g["gap"]: g for g in res["gaps"]}
    g = by["EXEC CICS GETMAIN"]
    assert (g["estates"], g["programs"]) == (2, 3)
    assert g["by_era"] == {"0": 0, "1": 1, "2": 1, "3": 0, "4": 1, "none": 0}
    assert g["estates_by_era"]["2"] == 1 and g["estates_by_era"]["1"] == 1
    assert res["gaps"][0]["gap"] == "EXEC CICS GETMAIN"  # estates first
    assert by["missing copybook BAQRI"]["status"] == "unknown"
    assert by["refused: CICS Assembler"]["status"] == "refused by name"
    assert by["refused: CICS Assembler"]["owner"] == "#5121"
    assert by["EXEC CICS GETMAIN"]["status"] == "not modelled"
    assert by["EXEC SQL: DECLARE CURSOR WITH HOLD"]["owner"].startswith("#4098")
    assert by["grammar: does not parse"]["owner"] == "#4462"
    assert by["grammar: does not parse"]["by_era"]["none"] == 1  # program absent from the inventory


def test_program_with_no_era_tell_counts_under_none(rows_and_inv):
    rows, d = rows_and_inv
    res = gp.measure(rows, d)
    assert res["by_era_programs"] == {"0": 0, "1": 1, "2": 3, "3": 0, "4": 1, "none": 1 + 1}


def test_coverage_if_closed(rows_and_inv):
    rows, d = rows_and_inv
    res = gp.measure(rows, d, top=(1, 2, 99))
    assert res["programs"] == 7 and res["whole_now"] == 1
    cov = {c["top"]: c for c in res["coverage_if_closed"]}
    assert cov[1]["whole"] == 1 + 2  # a3 whole already; a1 and b1 once GETMAIN is closed
    assert not cov[1]["upper_bound"]
    assert 99 not in cov  # fewer gaps than N: not reported
    assert max(cov) == 2


def test_refusal_in_top_makes_coverage_an_upper_bound(tmp_path):
    inv(tmp_path, A, {"x.cbl": 1})
    rows = {(A, "x.cbl"): {"error": "NotSupported: m.cbl:4: macro-level CICS not supported"}}
    res = gp.measure(rows, tmp_path, top=(1,))
    assert res["coverage_if_closed"][0]["upper_bound"] is True
    assert res["coverage_if_closed"][0]["whole"] == 1


def test_close_next_is_greedy_by_programs_gained(rows_and_inv):
    rows, d = rows_and_inv
    res = gp.measure(rows, d)
    steps = res["close_next"]
    assert steps[0]["gap"] == "EXEC CICS GETMAIN"  # a1 and b1 turn whole
    first = steps[0]
    assert first["gained"] == 2 and first["whole"] == res["whole_now"] + 2
    assert first["gained_by_era"] == {"0": 0, "1": 1, "2": 1, "3": 0, "4": 0, "none": 0}
    assert sum(s["gained"] for s in steps) + res["whole_now"] == steps[-1]["whole"]
    assert all(a["whole"] < b["whole"] for a, b in zip(steps, steps[1:], strict=False))
    assert steps[-1]["whole"] <= res["programs"]
    assert any(s["upper_bound"] for s in steps)  # a refusal gap is among the single-gap programs


def test_close_next_breaks_ties_by_estates_then_name_and_stops_when_nothing_is_gained():
    progs = [("e1", "2", {"b gap"}), ("e1", "2", {"a gap"}), ("e2", "2", {"b gap"}), ("e1", "3", {"x", "y"})]
    gaps = gp.rank(progs, "t")["gaps"]
    steps = gp.close_next(progs, gaps)
    assert [s["gap"] for s in steps] == ["b gap", "a gap"]  # b: 2 programs; then a
    assert steps[-1]["whole"] == 3  # the x+y program only helps in combination: not listed
    assert "close_next" in gp.rank(progs, "t")
    assert "close_next" not in gp.rank([("e1", "2", set())], "t")  # added only when non-empty


def test_needs_together_groups_programs_the_greedy_order_leaves_out():
    progs = [
        ("e1", "2", {"b gap"}),
        ("e1", "3", {"x", "y"}),
        ("e2", "3", {"x", "y"}),
        ("e1", "4", {"refused: z", "q"}),
        ("e1", "none", {"m", "n", "o"}),
        ("e1", "1", set()),
    ]
    res = gp.rank(progs, "t")
    tail = res["needs_together"]
    assert [t["gaps"] for t in tail] == [["x", "y"], ["q", "refused: z"], ["m", "n", "o"]]
    assert tail[0]["programs"] == 2 and tail[0]["estates"] == 2 and tail[0]["by_era"]["3"] == 2
    assert [t["upper_bound"] for t in tail] == [False, True, False]
    # whole today + greedy gains + the tail account for every program
    assert res["whole_now"] + sum(s["gained"] for s in res["close_next"]) + sum(t["programs"] for t in tail) == 6
    page = gp.render(res)
    assert "Needs several gaps together (4 programs the order" in page and "| `x`; `y` | 2 | 2 |" in page


def test_needs_together_is_added_only_when_non_empty():
    assert "needs_together" not in gp.rank([("e1", "2", {"a"}), ("e1", "2", set())], "t")
    assert "needs_together" not in gp.rank([("e1", "2", set())], "t")
    assert gp.needs_together([("e1", "2", {"a", "b"})], {"a", "b"}) == []


def test_committed_summaries_account_for_every_program():
    for path in (gp.SUMMARY, gp.CENSUS_SUMMARY):
        d = json.loads(path.read_text(encoding="utf-8"))
        tail = sum(t["programs"] for t in d.get("needs_together", []))
        gained = sum(s["gained"] for s in d.get("close_next", []))
        if "close_next" in d or "needs_together" in d:
            assert d["whole_now"] + gained + tail == d["programs"], path.name


def test_committed_census_summary_orders_the_closing_and_names_the_tail():
    """#5865: the census half carries the same close-next order and tail as the burned half, name-free."""
    c = json.loads(gp.CENSUS_SUMMARY.read_text(encoding="utf-8"))
    assert c["close_next"] and c["whole_now"] + sum(s["gained"] for s in c["close_next"]) <= c["programs"]
    shares = [s["share"] for s in c["close_next"]]
    assert shares == sorted(shares) and all(s["whole"] <= c["programs"] for s in c["close_next"])
    known = {g["gap"] for g in c["gaps"]}
    for s in c["close_next"]:
        assert s["gap"] in known
    for t in c.get("needs_together", []):
        assert len(t["gaps"]) >= 2 and set(t["gaps"]) <= known  # a single gap would have gained alone


def test_close_next_is_rendered(rows_and_inv):
    rows, d = rows_and_inv
    page = gp.render(gp.measure(rows, d))
    assert "Close-next order" in page and "| 1 | `EXEC CICS GETMAIN` | 2 |" in page


def test_non_burned_corpus_is_refused(tmp_path):
    with pytest.raises(ValueError, match="not burned"):
        gp.measure({("some-census-repo", "p.cbl"): row("line 1: EXEC SQL: X")}, tmp_path)


def test_missing_inventory_and_deterministic_render(rows_and_inv):
    rows, d = rows_and_inv
    first, second = gp.render(gp.measure(rows, d)), gp.render(gp.measure(dict(reversed(rows.items())), d))
    assert first == second
    assert "| `EXEC CICS GETMAIN` | 2 | 3 |" in first
    assert gp.eras_of("no-such-corpus", d) == {}


@pytest.mark.parametrize("service", ["CEEHDLR", "CEEHDLU", "CEEMGET", "CEESGL", "CEENCOD", "CEEMRCE", "CEE3SRP"])
def test_every_le_condition_service_gap_is_owned_by_5106(service):
    assert gp.owner_of(f"{service}: an LE condition service is not modelled") == "#5106 (le-condition-handling)"
    assert gp.owner_of("CEEIGZCT: x") == "unowned"  # the stand-in copybook is not a condition service


# ---- census half: aggregates under opaque labels, no names -------------------------------------------------------
CENSUS = ("some-census-repo", "other-census-repo")


@pytest.mark.parametrize(
    ("gap", "kept"),
    [
        ("EXEC CICS GETMAIN", "EXEC CICS GETMAIN"),
        ("EXEC CICS ASSIGN APPLID", "EXEC CICS ASSIGN APPLID"),
        ("EXEC SQL: DECLARE CURSOR WITH HOLD", "EXEC SQL: DECLARE CURSOR WITH HOLD"),
        ("EXEC SQL: SELECT FROM PAYROLL", "EXEC SQL: other"),  # a table name could name the repo
        ("EXEC SQL: <name> host variable", "EXEC SQL: other"),
        ("EXEC DLI: GU SEGMENT PAYSEG", "EXEC DLI"),
        ("missing copybook PAYREC (ambiguous)", "missing copybook: clone defect (not in the clone)"),
        ("missing copybook PAYREC", "missing copybook: clone defect (not in the clone)"),
        ("missing copybook DFHAID", "missing copybook: CICS system"),
        ("missing copybook SQLCA", "missing copybook: Db2 system"),
        ("missing copybook CMQV", "missing copybook: MQ system"),
        ("missing copybook AIBLK", "missing copybook: IMS system"),
        ("missing copybook CEEIGZCT", "missing copybook: LE system"),
        ("missing copybook CSQCHLL", "missing copybook: MQ system"),
        ("missing copybook DFSMSG", "missing copybook: IMS system"),
        ("missing copybook ISPFREC", "missing copybook: ISPF product"),
        ("missing copybook EZASMREC", "missing copybook: Sockets product"),
        ("missing copybook ICETOOL", "missing copybook: DFSORT product"),
        ("missing copybook IGYCRCTL", "missing copybook: COBOL compiler product"),
        ("missing copybook BAQRINFO", "missing copybook: z/OS Connect product"),
        ("missing copybook BAQRINFO (ambiguous)", "missing copybook: z/OS Connect product"),
        ("missing copybook HWTJICOB", "missing copybook: z/OS client web toolkit product"),
        ("missing copybook MYBAQREC", "missing copybook: clone defect (not in the clone)"),
        ("missing copybook ICEBERG", "missing copybook: DFSORT product"),  # prefix match is by design, documented
        (
            "missing copybook MYDFHREC",
            "missing copybook: clone defect (not in the clone)",
        ),  # a prefix inside the name is not a prefix
        ("refused: CICS Assembler", "refused: CICS Assembler"),
        ("refused: ExprError: PAYROLL thing", "refused: ExprError"),
        ("grammar: does not parse", "grammar: does not parse"),
        ("<name>: no such item", "<name>: no such item"),
        ("CALL CEEHDLR", "CALL CEEHDLR"),
        ("CALL MQPUT1", "CALL MQPUT1"),
        ("CALL PAYCALC", "CALL other"),
        ("SET TO ENTRY: procedure pointers are not modelled", "SET TO ENTRY: procedure pointers are not modelled"),
        (
            "COMPUTE exponentiation in a floating-point expression",
            "COMPUTE exponentiation in a floating-point expression",
        ),
        ("ZUIDSTCK: an assembler wrapper", "other"),
        ("SET PAYFLAG-X TO ENTRY", "SET: other"),
    ],
)
def test_scrub_key_keeps_the_vocabulary_and_collapses_names(gap, kept):
    assert gp.scrub_key(gap) == kept


def test_census_counts_carry_no_corpus_or_program_name():
    a, b = CENSUS
    rows = {
        (a, "payroll01.cbl"): row(
            "line 3: EXEC CICS: GETMAIN not modelled", "line 4: EXEC EXEC SQL: SELECT FROM PAYROLL"
        ),
        (a, "payroll02.cbl"): row("line 3: EXEC CICS: GETMAIN not modelled"),
        (b, "inv01.cbl"): row("line 3: EXEC CICS: GETMAIN not modelled"),
        (b, "inv02.cbl"): row(),
    }
    eras = {a: {"payroll01.cbl": "1", "payroll02.cbl": "2"}, b: {"inv01.cbl": "2"}}
    res = gp.measure_census(rows, eras, top=(1,))
    blob = json.dumps(res)
    for leak in (*CENSUS, "payroll", "inv01", "PAYROLL"):
        assert leak not in blob
    assert res["estates"] == sorted(gp.census_label(c) for c in CENSUS)
    g = res["gaps"][0]
    assert (g["gap"], g["estates"], g["programs"]) == ("EXEC CICS GETMAIN", 2, 3)
    assert g["by_era"] == {"0": 0, "1": 1, "2": 2, "3": 0, "4": 0, "none": 0}
    assert res["programs"] == 4 and res["whole_now"] == 1
    assert res["coverage_if_closed"][0]["whole"] == 3  # inv02 and payroll02 and inv01; payroll01 keeps its SQL gap
    assert res["gaps"][1]["gap"] == "EXEC SQL: other"


def test_census_and_burned_entry_points_refuse_each_other(tmp_path):
    with pytest.raises(ValueError, match="burned"):
        gp.measure_census({(A, "x.cbl"): row()}, {})
    with pytest.raises(ValueError, match="not burned"):
        gp.measure({(CENSUS[0], "x.cbl"): row()}, tmp_path)


def test_census_program_without_an_era_counts_under_none():
    res = gp.measure_census({(CENSUS[0], "p.cbl"): row("line 1: EXEC CICS: SYNCPOINT not modelled")}, {})
    assert res["gaps"][0]["by_era"]["none"] == 1


def test_render_adds_the_census_section(rows_and_inv):
    rows, d = rows_and_inv
    census = gp.measure_census({(CENSUS[0], "p.cbl"): row("line 1: EXEC CICS: SYNCPOINT not modelled")}, {})
    page = gp.render(gp.measure(rows, d), census)
    assert "## Census estates (1 estates, 1 programs, 0 translate whole today)" in page
    assert CENSUS[0] not in page
    assert "## Census estates" not in gp.render(gp.measure(rows, d))


@pytest.mark.parametrize(
    ("gap", "key"),
    [
        ("WRITE AFTER without ADVANCING", "WRITE: AFTER without ADVANCING"),
        (
            "WRITE AFTER ADVANCING identifier / mnemonic-name: carriage control is not modelled",
            "WRITE: carriage control (mnemonic-name) not modelled",
        ),
        (
            "PAYFILE: variable-length records without RECORD VARYING ... DEPENDING ON",
            "FD: variable-length records without RECORD VARYING",
        ),
        (
            "PAYSUB: no program of that name with a CALL entry in the estate",
            "CALL: target without a CALL entry in the estate",
        ),
        ("CALL <name>", "CALL: other non-IBM target"),
        ("JSON PARSE (…): not modelled", "JSON PARSE: not modelled"),
        ("JSON GENERATE (…): not modelled", "JSON GENERATE: not modelled"),
        # #7847: the det hole's first word is the statement class, so the gap key reads `JSONPARSE JSON PARSE: ...`
        ("JSONPARSE JSON PARSE: <name> is PACKED NUMERIC", "JSON PARSE: not modelled"),
        ("JSONPARSE JSON PARSE: <name> is COMP-1 FLOAT", "JSON PARSE: not modelled"),
        ("JSONGEN JSON GENERATE: <name> is COMP-1 FLOAT", "JSON GENERATE: not modelled"),
        (
            "MOVE an alphanumeric literal holds a character beyond the single-byte code page (…)",
            "MOVE: literal beyond the single-byte code page",
        ),
        (
            "STRING an alphanumeric literal holds a character beyond the single-byte code page (…)",
            "STRING: literal beyond the single-byte code page",
        ),
        (
            "STRING sender <name>, PIC <name>(…)<name>: a numeric item with a P or a decimal place is a compile error",
            "STRING: numeric sender with P or a decimal place",
        ),
        (
            "STRING sender <name>: a numeric literal is a compile error in Enterprise COBOL (…)",
            "STRING: numeric literal sender",
        ),
        ("<name>: its bytes hold <name> <name>", "<name>: bytes overlap another item"),
        ("ACCEPT from SYSIN / console", "ACCEPT: from SYSIN / console"),
        ("PERFORM <name>: undeclared paragraph", "PERFORM: undeclared paragraph"),
        ("SQLCA: undeclared item", "<name>: undeclared item"),
        ("PAYMAPI: undeclared item", "<name>: undeclared item"),
        ("PAYIN: no FD record", "FD: no record description"),
        ("EXEC CICS map <name>: no PAYFLDA", "EXEC CICS map: no <name> field"),
        ("STOP literal", "STOP: literal"),
        ("EXHIBIT NAMED of <name> IN <name>: only plain names", "EXHIBIT NAMED: only plain names and literals"),
        ("MOVE CORRESPONDING", "MOVE CORRESPONDING"),
    ],
)
def test_scrub_key_itemises_the_other_buckets_without_names(gap, key):
    assert gp.scrub_key(gap) == key
    assert not re.search(r"PAY[A-Z]*", key)  # the key is the table's string, never a slice of the source


def test_copybook_family_owner_and_status():
    assert gp.owner_of("missing copybook: MQ system") == "#4892"
    assert gp.owner_of("missing copybook: IMS system") == "#4893"
    assert gp.owner_of("missing copybook: CICS system") == "#4270 (cics-command-slice)"
    assert "source defect" in gp.owner_of("missing copybook: clone defect (not in the clone)")
    assert gp.status_of("missing copybook: clone defect (not in the clone)") == "named source defect"
    for fam in ("ISPF", "Sockets", "DFSORT", "COBOL compiler", "z/OS Connect", "z/OS client web toolkit"):
        assert gp.owner_of(f"missing copybook: {fam} product").startswith("#7709 (product copybook frontier")
        assert gp.status_of(f"missing copybook: {fam} product") == "unknown"
    assert gp.owner_of("missing copybook: LE system") == "unowned (copybook family)"
    assert gp.status_of("missing copybook: LE system") == "unknown"


def test_copybook_family_keys_never_carry_the_member_name():
    for member in ("PAYREC", "DFHPAYX", "SQLCAPAY", "CMQPAY", "AIBPAY", "CEEPAY", "BAQPAY", "HWTPAY"):
        key = gp.scrub_key(f"missing copybook {member} (ambiguous)")
        assert "PAY" not in key and key.startswith("missing copybook: ")


@pytest.mark.parametrize(
    ("gap", "key"),
    [
        ("refused: LayoutError: VALUE (…) not modelled", "refused: LayoutError: VALUE not modelled"),
        ("refused: LayoutError: <name> COMP-3 VALUE 'x': not a number", "refused: LayoutError: VALUE not a number"),
        (
            "refused: LayoutError: 01 <name> REDEFINES <name>, no 01 of that name before it",
            "refused: LayoutError: REDEFINES target not found",
        ),
        (
            "refused: LayoutError: <name> REDEFINES <name>, not a sibling before it",
            "refused: LayoutError: REDEFINES target not a sibling",
        ),
        (
            "refused: LayoutError: level N <name> has no 01 above it",
            "refused: LayoutError: level without an 01 above it",
        ),
        (
            "refused: LayoutError: DATA DIVISION does not parse near expanded line(s) (…)",
            "refused: LayoutError: DATA DIVISION does not parse",
        ),
        (
            "refused: LayoutDisagrees: PAYREC: the engine's fields (N) do not pair with the record's (N)",
            "refused: LayoutDisagrees: fields do not pair with the record's",
        ),
        (
            "refused: LayoutDisagrees: PAYREC: the engine does not know the record's width",
            "refused: LayoutDisagrees: record width unknown to the engine",
        ),
        (
            "refused: UnitRefused: text after END PROGRAM <name>, outside (…)",
            "refused: UnitRefused: text after END PROGRAM",
        ),
        (
            "refused: UnitRefused: END PROGRAM <name> closes no open program of (…)",
            "refused: UnitRefused: END PROGRAM closes no open program",
        ),
        (
            "refused: UnitRefused: p.cbl: no PROGRAM-ID: a member to be copied, not a program",
            "refused: UnitRefused: no PROGRAM-ID (a member to be copied)",
        ),
        (
            "refused: UnitRefused: <name> is nested in <name>, which declares (…)",
            "refused: UnitRefused: nested program",
        ),
        (
            "refused: UnitRefused: no program <name> in the source (…)",
            "refused: UnitRefused: requested program not in the source",
        ),
        ("refused: ExprError: reference modification not closed", "refused: ExprError: reference modification form"),
        (
            "refused: ExprError: NULL: only compared (…) with a pointer",
            "refused: ExprError: NULL compared with a non-pointer",
        ),
        ("refused: ExprError: ADDRESS OF", "refused: ExprError: ADDRESS OF"),
        (
            "refused: ExprError: DFHRESP(…) is not a documented condition",
            "refused: ExprError: DFHRESP condition not documented",
        ),
        (
            "refused: ExprError: DFHVALUE(…) is not a documented CVDA",
            "refused: ExprError: DFHVALUE CVDA not documented",
        ),
        ("refused: ExprError: unbalanced parenthesis in condition", "refused: ExprError: unbalanced parenthesis"),
        ("refused: ExprError: left over in condition: <name> X", "refused: ExprError: expression does not parse"),
        ("refused: ExprError: not a relation: '…'", "refused: ExprError: not a condition / relation"),
        ("refused: ExprError: not a data name: <name>", "refused: ExprError: not a data name"),
        ("refused: ExprError: ALL '…'", "refused: ExprError: ALL form"),
        (
            "refused: LayoutError: f.cbl:N: source defect: source text past column 72 (`e.'`) cuts a literal open: fixed-form COBOL reads columns 8-72 only",
            "refused: LayoutError: source defect: text past column 72",
        ),
        (
            "refused: LayoutError: f.cbl:N: source defect: source text past column 72 (`,`) truncates `X`: fixed-form COBOL reads columns 8-72 only",
            "refused: LayoutError: source defect: text past column 72",
        ),
        (
            "refused: LayoutError: source defect: data entry 03 NAME (f.cpy:N) has no period before the next level number",
            "refused: LayoutError: source defect: data entry without a period",
        ),
        ("refused: LayoutError: something new", "refused: LayoutError"),  # unknown message: the bare class
        (  # #7645: the estate-level row, through error_key as the census feeds it
            "refused: generation failed: not a COBOL program: ISPF editor screen (X.cbl: menu bar)",
            "refused: generation: ISPF editor screen, not a COBOL program",
        ),
        ("refused: generation failed: SystemExit: 0", "refused: generation"),  # any other exception: the bare class
    ],
)
def test_scrub_key_itemises_the_translator_refusals(gap, key):
    assert gp.scrub_key(gap) == key
    assert not re.search(r"PAY[A-Z]*", key)


def test_every_refusal_pattern_anchors_on_a_text_the_translator_raises():
    root = Path(gp.REPO) / "gitgalaxy" / "tools" / "cobol_to_java" / "det"
    src = "".join(p.read_text(encoding="utf-8") for p in root.glob("*.py"))
    for anchor in ("has no 01 above it", "DATA DIVISION does not parse", "do not pair with the record", "no PROGRAM-ID",
                   "is nested in", "reference modification not closed", "is not a documented CVDA", "unbalanced parenthesis",
                   "left over in condition", "not a relation", "not a data name", "closes no open program", "not a sibling before it",
                   "not a number", "no 01 of that name", "source defect: source text past column", "has no period", "does not know the record's width"):  # fmt: skip
        assert anchor in src, anchor


def test_owner_pointers_for_bll_picture_n_and_procedure_pointers_and_reowner():
    bll = "X: no service of its own, its translation is refused: OS/VS COBOL BLL addressing: SERVICE LABEL (…): not modelled"
    assert gp.owner_of(bll) == "#5119"
    assert gp.owner_of("X: refused: f.cbl:N: the PICTURE N (…) is not modelled (…)") == "#4272"
    assert gp.owner_of("SET TO ENTRY: procedure / function pointers are not modelled") == "#5106"
    for verb in ("GENERATE", "PARSE"):
        assert gp.owner_of(f"JSON {verb}: not modelled") == "#7524"  # the census breadth issue owns both rows
    # #7845 owns the census bytes-overlap row (COMP-5 in CICS containers); an unrelated overlap-like key stays unowned
    assert gp.owner_of("<name>: bytes overlap another item").startswith("#7845")
    assert gp.owner_of("<name>: its bytes hold <name>") == "unowned"
    assert gp.owner_of("<name>: <name> is not defined in a record of file <name>") == "#5866"
    assert gp.owner_of("<name> ADDRESS OF <name>: not an item of <name> or LINKAGE") == "#5042"
    for verb in ("RECEIVE NOTRUNCATE", "CONVERSE", "WRITE HTTPHEADER", "SEND", "PARSE URL", "OPEN", "CLOSE"):
        assert gp.owner_of(f"EXEC CICS WEB {verb}") == "#7525"  # before the generic CICS row; #4767 is closed
    assert gp.owner_of("EXEC CICS GETMAIN without INITIMG").startswith("#4270")
    for key in (
        "refused: LayoutError: source defect: text past column 72",
        "refused: LayoutError: source defect: data entry without a period",
    ):
        assert gp.owner_of(key).startswith("none (a source defect")
    for still in ("XML PARSE: not modelled", "refused: LayoutError"):
        assert gp.owner_of(still) == "unowned"
    res = {"gaps": [{"gap": "SET TO ENTRY: procedure / function pointers are not modelled", "owner": "unowned"}]}
    assert gp.reowner(res)["gaps"][0]["owner"] == "#5106"
    assert gp.reowner(res) == res


# ---- the committed census aggregate (#5865): readable by name-free invariants, whatever the census run counted ----
def test_committed_census_summary_is_name_free_and_consistent():
    c = json.loads(gp.CENSUS_SUMMARY.read_text(encoding="utf-8"))
    assert c["format"] == gp.FORMAT
    assert c["estates"] and all(re.fullmatch(r"census-[0-9a-f]{6}", e) for e in c["estates"])
    assert sum(c["by_era_programs"].values()) == c["programs"]
    for g in c["gaps"]:
        assert re.fullmatch(r"[A-Za-z0-9 :<>/(),.+-]{1,90}", g["gap"]), g["gap"]  # no path, quote or long literal
        assert sum(g["by_era"].values()) == g["programs"] and g["estates"] <= len(c["estates"])
        assert g["owner"] and g["status"]
    ranks = [(-g["estates"], -g["programs"]) for g in c["gaps"]]
    assert ranks == sorted(ranks)  # highest estate coverage first
    assert all(x["whole"] <= c["programs"] for x in c["coverage_if_closed"])


def test_committed_census_summary_itemises_every_layout_error():
    # #7644: the census regenerated after the source-defect keys landed; no LayoutError may collapse to the bare class,
    # and a source-defect key carries the "not an engine gap" owner line
    c = json.loads(gp.CENSUS_SUMMARY.read_text(encoding="utf-8"))
    layout = [g for g in c["gaps"] if g["gap"].startswith("refused: LayoutError")]
    assert all(g["gap"] != "refused: LayoutError" for g in layout)
    for g in layout:
        if ": source defect" in g["gap"]:
            assert g["owner"].startswith("none (a source defect"), g


def test_layout_disagrees_owner_and_combined_ranking(rows_and_inv):
    rows, d = rows_and_inv
    assert gp.owner_of("refused: LayoutDisagrees") == "#6926"
    burned = gp.measure(rows, d)
    census = gp.measure_census({(CENSUS[0], "p.cbl"): row("line 1: EXEC CICS: GETMAIN not modelled")}, {})
    both = gp.combine(burned, census)
    getmain = next(g for g in both if g["scope"] == "B+C")
    assert getmain["estates"] == next(g for g in burned["gaps"] if g["gap"] == getmain["gap"])["estates"] + 1
    assert all(sum(g["by_era"].values()) == g["programs"] for g in both)
    ranks = [(-g["estates"], -g["programs"]) for g in both]
    assert ranks == sorted(ranks)
    page = gp.render(burned, census)
    assert page.index("## All estates") < page.index("## Burned estates")
    assert CENSUS[0] not in page
    assert "## All estates" not in gp.render(burned)


def test_committed_combined_table_adds_the_two_summaries():
    b = json.loads(gp.SUMMARY.read_text(encoding="utf-8"))
    c = json.loads(gp.CENSUS_SUMMARY.read_text(encoding="utf-8"))
    both = gp.combine(b, c)
    assert sum(g["programs"] for g in both) == sum(g["programs"] for g in b["gaps"] + c["gaps"])
    assert {g["gap"] for g in both} == {g["gap"] for g in b["gaps"] + c["gaps"]}


def test_headline_states_the_coverage_if_closed_per_scope_and_its_bound():
    """#5865: each scope opens with the top-N whole-program share; a refusing gap in the top N says upper bound."""
    lines = gp.headline({"programs": 4, "whole_now": 1, "coverage_if_closed": [
        {"top": 1, "whole": 2, "share": 0.5, "upper_bound": False},
        {"top": 3, "whole": 3, "share": 0.75, "upper_bound": True}]})  # fmt: skip
    assert "top 1: 2 / 4 (50.0%)" in lines[0] and "top 3: 3 / 4 (75.0%, upper bound)" in lines[0]
    assert "from 1 today" in lines[0]
    assert gp.headline({"programs": 0, "whole_now": 0, "coverage_if_closed": []}) == []


def test_render_opens_each_scope_with_the_headline(rows_and_inv):
    rows, d = rows_and_inv
    burned = gp.measure(rows, d)
    census = gp.measure_census({(CENSUS[0], "p.cbl"): row("line 1: EXEC CICS: GETMAIN not modelled")}, {})
    page = gp.render(burned, census)
    assert page.count("Coverage if closed, programs that translate whole") == 3  # all estates, burned, census
    assert page.index("Coverage if closed, programs") < page.index("| top N gaps closed |")


def test_shapes_account_for_every_program_with_a_gap(rows_and_inv):
    rows, d = rows_and_inv
    res = gp.measure(rows, d)
    assert sum(s["programs"] for s in res["shapes"]) == res["programs"] - res["whole_now"]
    assert all(sum(s["by_era"].values()) == s["programs"] and s["gaps"] == sorted(s["gaps"]) for s in res["shapes"])
    clean = gp.rank([(A, "1", set())], "burned estates")
    assert "shapes" not in clean  # added only when non-empty


def test_combined_coverage_is_the_per_scope_wholes_added_for_one_closed_set():
    b = gp.rank([(A, "1", {"x"}), (A, "2", {"x", "y"}), (A, "1", set())], "b")
    c = gp.rank(
        [("census-1", "2", {"x"}), ("census-2", "none", {"refused: LayoutError"}), ("census-2", "3", set())], "c"
    )
    both = gp.combined_coverage(b, c, top=(1, 2))
    assert (both["programs"], both["whole_now"]) == (6, 2)
    ranked = [g["gap"] for g in gp.combine(b, c)]
    for step in both["coverage_if_closed"]:
        picked = set(ranked[: step["top"]])
        expect = sum(
            r["whole_now"] + sum(s["programs"] for s in r.get("shapes", []) if set(s["gaps"]) <= picked) for r in (b, c)
        )
        assert step["whole"] == expect
    assert both["coverage_if_closed"][0]["top"] == 1
    assert both["close_next"][0]["gap"] == "x" and both["close_next"][0]["gained"] == 1 + 1


def test_committed_combined_coverage_adds_the_two_scopes_and_is_rendered():
    b = json.loads(gp.SUMMARY.read_text(encoding="utf-8"))
    c = json.loads(gp.CENSUS_SUMMARY.read_text(encoding="utf-8"))
    both = gp.combined_coverage(b, c)
    assert both["programs"] == b["programs"] + c["programs"]
    assert both["whole_now"] == b["whole_now"] + c["whole_now"]
    for scope in (b, c):  # one gap closed for everyone can only make as many whole as the scopes' own sums allow
        assert sum(s["programs"] for s in scope["shapes"]) == scope["programs"] - scope["whole_now"]
    shares = [s["whole"] for s in both["coverage_if_closed"]]
    assert shares == sorted(shares)
    page = gp.render(b, c)
    assert page.count("Coverage if closed, programs that translate whole") == 3
    assert (
        gp.render(b, {k: v for k, v in c.items() if k != "shapes"}).count(
            "Coverage if closed, programs that translate whole"
        )
        == 2
    )


def test_undeclared_name_rows_are_source_defects_owned_by_7647():
    """#7647: a name or paragraph no member, clone or COPY declares is the source's defect, not an engine gap."""
    assert gp.owner_of("<name>: undeclared item").startswith("#7647 (source defect")
    assert gp.owner_of("PERFORM: undeclared paragraph").startswith("#7647 (source defect")
    assert gp.owner_of("<name>: no such item") == "unowned"  # supplied interface names stay a translator gap


def test_numeric_string_sender_rows_are_source_defects_owned_by_7523():
    """#7523: IBM rejects a STRING sender that is a numeric item with a P or a decimal place, or a numeric literal."""
    for key in ("STRING: numeric sender with P or a decimal place", "STRING: numeric literal sender"):
        assert gp.owner_of(key).startswith("#7523 (source defect")


def test_wide_literal_rows_are_source_defects_owned_by_7526():
    """#7526: a literal holding a character no single-byte EBCDIC page holds is the source's transfer defect (D4)."""
    for verb in ("MOVE", "STRING", "UNSTRING", "INSPECT"):
        key = f"{verb}: literal beyond the single-byte code page"
        assert gp.owner_of(key).startswith("#7526 (source defect")
        assert gp.status_of(key) == "named source defect"
    raw = "UNSTRING an alphanumeric literal holds a character beyond the single-byte code page (…)"
    assert gp.scrub_key(raw) == "UNSTRING: literal beyond the single-byte code page"


def test_named_source_defect_status_and_accounted_count():
    """#7709: a source-defect row reads as named, and a program with only such gaps counts as accounted."""
    for key in (
        "STRING: numeric sender with P or a decimal place",
        "STRING: numeric literal sender",
        "<name>: undeclared item",
    ):
        assert gp.status_of(key) == "named source defect"
    assert gp.status_of("refused: LayoutError: source defect: text past column 72") == "refused by name"
    progs = [
        ("c", "none", set()),
        ("c", "none", {"STRING: numeric sender with P or a decimal place"}),
        ("c", "none", {"STRING: numeric sender with P or a decimal place", "JSON PARSE: not modelled"}),
    ]
    res = gp.rank(progs, "census")
    assert (res["whole_now"], res["accounted_now"]) == (1, 2)
    assert "Accounted today" in "\n".join(gp.headline(res))
    assert "accounted_now" not in gp.rank(progs[:1] + progs[2:], "census")


def test_cics_map_field_row_is_a_source_defect_owned_by_7647():
    """#7844: the BMS source is in the clone, but the program never COPYs the symbolic map (no FROM / INTO): the estate's defect."""
    key = "EXEC CICS map: no <name> field"
    assert gp.owner_of(key).startswith("#7647 (source defect")
    assert gp.status_of(key) == "named source defect"
    assert gp.is_named_defect(key)
    # the cause is named: no FROM / INTO and no COPY of the symbolic area, though the BMS source is in the clone
    assert "no FROM / INTO" in gp.owner_of(key) and "never COPYs or declares" in gp.owner_of(key)
    assert gp.owner_of("EXEC CICS SEND MAP: other") == "#4270 (cics-command-slice)"
    assert gp.owner_of("EXEC CICS WEB SEND").startswith("#7525")


def test_cics_map_rows_are_census_only_and_the_undeclared_sibling_shares_the_owner():
    """#7844: no burned program hits the map gap or its `<map>I` sibling; both rows are source defects of one owner."""
    burned = {g["gap"] for g in json.loads(gp.SUMMARY.read_text(encoding="utf-8"))["gaps"]}
    census = {g["gap"]: g for g in json.loads(gp.CENSUS_SUMMARY.read_text(encoding="utf-8"))["gaps"]}
    row, sibling = "EXEC CICS map: no <name> field", "<name>: undeclared item"
    assert row not in burned and sibling not in burned
    assert row in census and sibling in census
    assert census[row]["owner"].startswith("#7647 (source defect") and census[sibling]["owner"].startswith("#7647")


def test_expr_and_unit_refusals_have_census_owners_7847():
    """#7847: the two whole-program refusals the census left unowned. The scrubbed texts the census sees, not the raw ones."""
    expr = "refused: ExprError: PROCEDURE DIVISION does not parse"
    assert gp.scrub_key("refused: ExprError: the PROCEDURE DIVISION does not parse") == expr
    unit_raw = "refused: UnitRefused: <class>.<property>: no <name>: a member to be copied, not a program"
    unit = "refused: UnitRefused: no PROGRAM-ID (a member to be copied)"
    assert gp.scrub_key(unit_raw) == unit
    assert gp.scrub_key("refused: UnitRefused: p.cbl: no PROGRAM-ID: a member to be copied, not a program") == unit
    assert gp.owner_of(expr).startswith("#7709 (source defect") and gp.is_named_defect(expr)
    assert gp.status_of(expr) == "refused by name"  # a refusal keeps its status; the owner column names the defect
    assert gp.owner_of(unit).startswith("#7709 (not a program")
    assert not gp.is_named_defect(unit)  # a copybook the inventory counted is no defect of the estate's source
    # a different ExprError still falls to its own row; the bare class is not owned
    assert gp.owner_of("refused: ExprError") == "unowned"


def test_committed_census_summary_has_no_unowned_refusal_7847():
    c = json.loads(gp.CENSUS_SUMMARY.read_text(encoding="utf-8"))
    whole = [g["gap"] for g in c["gaps"] if g.get("refuses_program") and g["gap"].startswith("refused")]
    assert whole
    assert [g for g in whole if gp.owner_of(g) == "unowned"] == []


def test_unowned_rows_flags_every_fallback_owner_7847():
    gaps = [
        "refused: ExprError",
        "missing copybook: something unclassified",
        "EXEC CICS ASSIGN",
        "refused: ExprError: PROCEDURE DIVISION does not parse",
    ]
    assert gp.unowned_rows({"gaps": [{"gap": g} for g in gaps]}) == gaps[:2]
    assert gp.unowned_rows({"gaps": [{"gap": g} for g in gaps[2:]]}) == []
    assert gp.unowned_rows({}) == []


@pytest.mark.parametrize("path", [gp.CENSUS_SUMMARY, gp.SUMMARY], ids=["census", "burned"])
def test_committed_summary_has_no_unowned_row_beyond_the_named_exemptions_7847(path):
    """The census half (and the burned half) show no `unowned` row but the named ones; a new one fails here."""
    found = gp.unowned_rows(json.loads(path.read_text(encoding="utf-8")))
    allowed = gp.KNOWN_UNOWNED if path == gp.CENSUS_SUMMARY else {}
    assert sorted(set(found) - set(allowed)) == [], "give the new row an owner in gap_prevalence.OWNERS"
    assert sorted(set(allowed) - set(found)) == [], "an exemption is owned or gone: drop it from KNOWN_UNOWNED"


def test_cics_map_rows_are_accounted_in_the_census_and_do_not_refuse_the_program():
    """#7844 (T7 re-survey): the map row and its `<map>I` sibling are named source defects, so they count as accounted
    and never as an open translator gap; their programs are not whole, and no row of that class is a refusal."""
    census = json.loads(gp.CENSUS_SUMMARY.read_text(encoding="utf-8"))
    rows = {g["gap"]: g for g in census["gaps"]}
    for key in ("EXEC CICS map: no <name> field", "<name>: undeclared item"):
        assert rows[key]["status"] == "named source defect"
        assert rows[key]["refuses_program"] is False
        assert gp.is_named_defect(key)
    # the map programs are a subset of the sibling's programs (both census rows also read `undeclared item`)
    assert rows["EXEC CICS map: no <name> field"]["programs"] <= rows["<name>: undeclared item"]["programs"]
    assert census["whole_now"] <= census["accounted_now"] <= census["programs"]


def test_cics_map_programs_are_accounted_through_their_shapes_not_a_translator_gap():
    """#7709 [c:26cc02df]: both map programs are accounted. Every shape holding the map row holds only rows that are
    named source defects, so neither program is open on a translator gap, and the 2 map programs are in the census total."""
    census = json.loads(gp.CENSUS_SUMMARY.read_text(encoding="utf-8"))
    rows = {g["gap"]: g for g in census["gaps"]}
    map_row = "EXEC CICS map: no <name> field"
    assert rows[map_row]["programs"] == sum(s["programs"] for s in census["shapes"] if map_row in s["gaps"])
    for shape in census["shapes"]:
        if map_row in shape["gaps"]:
            assert all(rows[g]["status"] == "named source defect" for g in shape["gaps"])


def test_headline_basis_note_reports_the_copy_member_from_the_counts_7847():
    """#7847: a copybook the inventory counted shrinks the basis; the note derives its numbers, and is absent without the row."""
    res = {"programs": 40, "whole_now": 11, "accounted_now": 37, "gaps": [{"gap": gp.COPY_MEMBER_GAP, "programs": 1}],
           "coverage_if_closed": [{"top": 1, "whole": 12, "share": 0.3, "upper_bound": False}]}  # fmt: skip
    note = [x for x in gp.headline(res) if x.startswith("Basis note")]
    assert len(note) == 1
    assert "40 surveyed, 1 copy member" in note[0] and "so 39 real programs" in note[0]
    assert "37 / 40" in note[0] and "37 / 39" in note[0]
    res["gaps"] = []
    assert not [x for x in gp.headline(res) if x.startswith("Basis note")]


def test_json_item_usage_refusals_are_owned_not_other_7847():
    """#7847: `JSONPARSE JSON PARSE: <item> is PACKED NUMERIC (...)` collapsed to `other`, unowned. Every statement-class
    spelling of the JSON refusals reaches the #7524 row; an unrelated key still falls to `other`."""
    for cls, verb in (("JSONPARSE", "PARSE"), ("JSONGEN", "GENERATE"), ("", "PARSE"), ("", "GENERATE")):
        raw = f"{cls} JSON {verb}: SCORE is PACKED NUMERIC".strip()
        key = gp.scrub_key(raw)
        assert key == f"JSON {verb}: not modelled", raw
        assert gp.owner_of(key) == "#7524"
    assert gp.scrub_key("JSONPARSEX something else") == "other"
    census = json.loads(gp.CENSUS_SUMMARY.read_text(encoding="utf-8"))
    assert "other" not in {g["gap"] for g in census["gaps"]}


# ---- #7901: the census basis is the programs alone; a summary that counted the copy member is corrected ---------------
def _progs(with_copy: bool, era: str) -> list:
    g, s = "EXEC CICS GETMAIN", "EXEC CICS SYNCPOINT"
    progs = [("c-a", "1", {g}), ("c-a", "2", {g, s}), ("c-b", "2", {s}), ("c-b", "none", set())]
    return [*progs, ("c-b", era, {gp.COPY_MEMBER_GAP})] if with_copy else progs


@pytest.mark.parametrize("era", ["1", "none"])
def test_dropping_the_copy_member_equals_a_survey_without_it(era):
    got = gp.drop_copy_member_gap(gp.rank(_progs(True, era), "x"))
    want = gp.rank(_progs(False, era), "x")
    assert got.pop("copy_members") == 1
    for key in ("programs", "by_era_programs", "gaps", "coverage_if_closed", "close_next", "shapes", "estates"):
        assert got[key] == want[key], key
    assert got.get("accounted_now") == want.get("accounted_now")


def test_drop_copy_member_gap_is_a_noop_without_it_and_idempotent():
    clean = gp.rank(_progs(False, "1"), "x")
    assert gp.drop_copy_member_gap(json.loads(json.dumps(clean))) == clean
    dirty = gp.rank(_progs(True, "1"), "x")
    once = gp.drop_copy_member_gap(dirty)
    assert gp.drop_copy_member_gap(json.loads(json.dumps(once))) == once


def test_committed_census_basis_is_39_programs_with_the_copy_member_listed():
    c = json.loads(gp.CENSUS_SUMMARY.read_text(encoding="utf-8"))
    assert c["programs"] == 39 and c["copy_members"] == 1
    assert gp.COPY_MEMBER_GAP not in {g["gap"] for g in c["gaps"]}
    page = gp.PAGE.read_text(encoding="utf-8")
    assert "9 estates, 39 programs" in page and "40-program" not in page
