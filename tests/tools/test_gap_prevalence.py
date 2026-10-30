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
        ("missing copybook PAYREC (ambiguous)", "missing copybook: estate-owned"),
        ("missing copybook PAYREC", "missing copybook: estate-owned"),
        ("missing copybook DFHAID", "missing copybook: CICS system"),
        ("missing copybook SQLCA", "missing copybook: Db2 system"),
        ("missing copybook CMQV", "missing copybook: MQ system"),
        ("missing copybook AIBLK", "missing copybook: IMS system"),
        ("missing copybook CEEIGZCT", "missing copybook: LE system"),
        ("missing copybook MYDFHREC", "missing copybook: estate-owned"),  # a prefix inside the name is not a prefix
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
    assert gp.owner_of("missing copybook: estate-owned").startswith("none (the estate's own")
    assert gp.owner_of("missing copybook: LE system") == "unowned (copybook family)"
    assert gp.status_of("missing copybook: LE system") == "unknown"


def test_copybook_family_keys_never_carry_the_member_name():
    for member in ("PAYREC", "DFHPAYX", "SQLCAPAY", "CMQPAY", "AIBPAY", "CEEPAY"):
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
            "refused: LayoutDisagrees: PAYREC: the engine's layout differs from the translator's: (…)",
            "refused: LayoutDisagrees: layout differs from the engine's",
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
        ("refused: LayoutError: something new", "refused: LayoutError"),  # unknown message: the bare class
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
                   "not a number", "no 01 of that name", "does not know the record's width", "layout differs"):  # fmt: skip
        assert anchor in src, anchor


def test_owner_pointers_for_bll_picture_n_and_procedure_pointers_and_reowner():
    bll = "X: no service of its own, its translation is refused: OS/VS COBOL BLL addressing: SERVICE LABEL (…): not modelled"
    assert gp.owner_of(bll) == "#5119"
    assert gp.owner_of("X: refused: f.cbl:N: the PICTURE N (…) is not modelled (…)") == "#4272"
    assert gp.owner_of("SET TO ENTRY: procedure / function pointers are not modelled") == "#5106"
    assert gp.owner_of("JSON GENERATE: not modelled") == "unowned"  # no open issue owns it: none invented
    assert gp.owner_of("<name>: <name> is not defined in a record of file <name>") == "#5866"
    assert gp.owner_of("<name> ADDRESS OF <name>: not an item of <name> or LINKAGE") == "#5042"
    assert gp.owner_of("EXEC CICS WEB RECEIVE NOTRUNCATE") == "#4767"  # before the generic CICS row
    assert gp.owner_of("EXEC CICS GETMAIN without INITIMG").startswith("#4270")
    for still in ("JSON PARSE: not modelled", "refused: LayoutError", "PERFORM: undeclared paragraph"):
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
    assert page.count("Coverage if closed, programs that translate whole") == 2
    assert page.index("Coverage if closed, programs") < page.index("| top N gaps closed |")
