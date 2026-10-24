"""harness_report (#4493): coverage, run status, input generation and blockers-as-fixes, from proof_blockers' result.
Fixture cases / corpora under tmp_path; no corpus, translator or sweep needed."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness_report as hr
import proof_blockers as pb
import test_proof_blockers as tpb


def burned(res):
    """The fixture corpus is not a burned name: mark its programs burned, as proof_blockers does for a real one."""
    for p in res["programs"] + res.get("untranslated", []):
        p["burned"] = True
    return res


def fixture(tmp_path):
    cases, corpora, cru, det_baseline, rows = tpb.setup(tmp_path)
    for c, n in (("c-known", 4), ("c-cov", 2), ("c-taskn", 5), ("c-assign", 3), ("c-proven", 6)):
        f = cases / c / "case.json"
        d = json.loads(f.read_text())
        d["scenarios"] = [{"name": f"s{i}"} for i in range(n)]
        f.write_text(json.dumps(d))
    tpb.evidence(cases, "c-known", 1, 1)  # so that leaving the baseline proves it, as in a real fix
    return cases, corpora, cru, det_baseline, rows


def proof(cases, corpora, cru, det_baseline, rows):
    return burned(pb.proof_blockers(rows, [corpora], cases_dir=cases, crucible_dir=cru, det_baseline=det_baseline))


def test_coverage_and_status_counts(tmp_path):
    cases, *rest = fixture(tmp_path)
    rep = hr.build(proof(cases, *rest), "x", cases)
    c = rep["coverage"]
    assert (c["programs"], c["proven"]) == (9, 1)
    assert c["with_case"] == 8 and c["with_case_pct"] == 88.9  # NOCASE has none
    assert sum(rep["status_counts"].values()) == 9
    by = {Path(r["program"]).stem: r for r in rep["programs"]}
    assert by["PROVEN"]["status"] == "proven" and by["NOCASE"]["status"] == hr.NOT_ATTEMPTED
    assert by["KNOWN"]["status"] == hr.COULDNT_RUN and by["COV"]["status"] == hr.COVERAGE_OPEN
    assert c["paragraphs"]["live"] > 0 and c["cases_measured"] >= 1


def test_each_non_proven_program_is_under_exactly_one_blocker(tmp_path):
    cases, *rest = fixture(tmp_path)
    rep = hr.build(proof(cases, *rest), "x", cases)
    listed = [p for b in rep["blockers"] for p in b["programs"]]
    assert len(listed) == len(set(listed))
    assert sorted(listed) == sorted(r["program"] for r in rep["programs"] if r["gaps"])
    top = rep["blockers"][0]
    assert top["tests_unlocked"] == max(b["tests_unlocked"] for b in rep["blockers"])
    assert all(b["fix"] and b["programs"] for b in rep["blockers"])


def test_unlock_prediction_matches_a_rerun_after_the_fix(tmp_path):
    cases, corpora, cru, det_baseline, rows = fixture(tmp_path)
    before = hr.build(proof(cases, corpora, cru, det_baseline, rows), "x", cases)
    known = next(b for b in before["blockers"] if b["gap"].startswith("known unproven"))
    assert known["tests_unlocked"] == 4 and known["programs_unlocked"] == 1

    def proven_tests(rep):
        return sum(r["tests"] for r in rep["programs"] if r["status"] == hr.PROVEN)

    # fix the blocker: the case leaves det_sweep_baseline.json
    after = hr.build(proof(cases, corpora, cru, {}, rows), "x", cases)
    gained = proven_tests(after) - proven_tests(before)
    assert gained >= known["tests_unlocked"]
    newly = {r["program"] for r in after["programs"] if r["status"] == hr.PROVEN} - {
        r["program"] for r in before["programs"] if r["status"] == hr.PROVEN
    }
    assert newly == set(known["programs"]) and gained == known["tests_unlocked"]
    assert all(b["gap"] != known["gap"] for b in after["blockers"])


def test_a_program_with_two_gaps_unlocks_nothing_until_both_go(tmp_path):
    cases, *rest = fixture(tmp_path)
    rep = hr.build(proof(cases, *rest), "x", cases)
    assign = next(r for r in rep["programs"] if r["program"].endswith("ASSIGN.cbl"))
    assert len(assign["gaps"]) == 2
    mine = next(b for b in rep["blockers"] if assign["program"] in b["programs"])
    assert mine["tests_unlocked"] == 0 and mine["programs_unlocked"] == 0
    assert mine["then_needs"][assign["program"]] == [g for g in assign["gaps"] if g != mine["gap"]]
    assert "also needs" in hr.markdown(rep)


def test_input_generation_classes():
    case = {"datasets": {"A": {"input": "@generate", "generate": {"copybook": "a.cpy", "record": "R", "records": 5}},
                         "B": {"input": "data/b.dat"}, "C": {}},
            "scenario_generate": {"count": 24}}  # fmt: skip
    i = hr.input_generation(case)
    assert [g["dataset"] for g in i["generated"]] == ["A"] and i["shipped"] == ["B"] and i["skipped"] == ["C"]
    assert i["scenarios_generated"] and hr.scenario_count(case) == 24
    assert hr.input_generation({}) == {"generated": [], "shipped": [], "skipped": [], "scenarios_generated": False}


def test_non_burned_programs_are_counted_never_named(tmp_path):
    cases, *rest = fixture(tmp_path)
    res = proof(cases, *rest)
    for p in res["programs"][:2]:
        p["burned"] = False
    names = [p["program"] for p in res["programs"][:2]]
    rep = hr.build(res, "x", cases)
    assert rep["not_listed"]["non_burned_programs"] == 2
    text = json.dumps(rep) + hr.markdown(rep)
    assert not any(n in text for n in names)


def test_empty_estate_and_write(tmp_path):
    rep = hr.build({"programs": [], "gaps": []}, "none", tmp_path)
    assert rep["coverage"]["programs"] == 0 and rep["coverage"]["proven_pct"] is None
    assert "None: every program is proven." in hr.markdown(rep)
    cases, *rest = fixture(tmp_path / "f")
    paths = hr.write_report(proof(cases, *rest), tmp_path / "out", "est", cases)
    assert json.loads(paths["json"].read_text())["schema_version"] == hr.SCHEMA_VERSION
    assert "## Blockers (highest value first)" in paths["md"].read_text()


def layout_case(tmp_path, copybooks):
    """A case whose generated datasets read `copybooks` ({name: text}) from a fixture corpus."""
    corpora = tmp_path / "corpora"
    ds = {}
    for name, text in copybooks.items():
        tpb.write(corpora / "estate" / f"{name}.cpy", text)
        ds[name.upper()] = {"input": "@generate", "reclen": 20,
                            "generate": {"copybook": f"{name}.cpy", "record": "REC", "records": 3}}  # fmt: skip
    return corpora, {"corpus": "estate", "datasets": ds}


def cpy(*lines):
    return "\n".join(f"       {ln}" for ln in lines) + "\n"


def test_record_layout_limits_each_land_under_one_cause(tmp_path):
    corpora, case = layout_case(tmp_path, {
        "ok": cpy("01 REC.", "   05 A PIC X(5)."),
        "redef": cpy("01 REC.", "   05 T PIC X.", "      88 T-A VALUE 'A'.", "   05 A.", "      10 X1 PIC X(4).",
                     "   05 B REDEFINES A.", "      10 N1 PIC 9(4)."),
        "ren": cpy("01 REC.", "   05 A PIC X(5).", "   05 C PIC X(2).", "   66 AC RENAMES A THRU C."),
        "syn": cpy("01 REC.", "   05 A PIC S9(4) COMP SYNC."),
        "cop": cpy("01 REC.", "   COPY NOWHERE.", "   05 A PIC X."),
    })  # fmt: skip
    got = {dd: hr.record_cause([corpora], case, dd) for dd in case["datasets"]}
    assert got == {"OK": "", "REDEF": "redefines", "REN": "renames", "SYN": "sync", "COP": "unresolved copy"}
    assert hr.record_limit([corpora], case, "REDEF") == ("redefines", "A -> B (selector T)")
    assert hr.record_cause([], case, "OK") == "not read"  # no corpus: stated, not an error


def test_redefines_only_when_another_field_chooses(tmp_path):
    corpora, case = layout_case(tmp_path, {
        "view": cpy("01 REC.", "   05 A PIC X(8).", "   05 B REDEFINES A PIC 9(8)."),
        "filler": cpy("01 REC.", "   05 A PIC X(8).", "   05 FILLER REDEFINES A PIC X(8)."),
        "two": cpy("01 REC.", "   05 KIND PIC X(2).", "   05 A PIC X(4).", "   05 B REDEFINES A PIC 9(4).",
                   "   05 C REDEFINES A PIC S9(4) COMP."),
        "code": cpy("01 REC.", "   05 REC-CODE PIC X(2).", "   05 A.", "      10 X1 PIC X(4).",
                    "   05 B REDEFINES A.", "      10 N1 PIC 9(4)."),
        "none": cpy("01 REC.", "   05 A.", "      10 X1 PIC X(4).", "   05 B REDEFINES A.", "      10 N1 PIC 9(4)."),
    })  # fmt: skip
    got = {dd: hr.record_limit([corpora], case, dd) for dd in case["datasets"]}
    assert got["VIEW"] == got["FILLER"] == ("", "")  # the first alternative already holds a same-bytes view
    assert got["TWO"] == ("redefines", "A -> B/C (selector KIND)")
    assert got["CODE"] == ("redefines", "A -> B (selector REC-CODE)")
    assert got["NONE"] == ("redefines", "A -> B (selector not found)")
    ruled = {"corpus": "estate", "datasets": {"CODE": {"input": "@generate", "generate": {
        "copybook": "code.cpy", "record": "REC", "records": 1, "fields": {"REC-CODE": {"values": ["AA"]}}}}}}  # fmt: skip
    assert hr.record_cause([corpora], ruled, "CODE") == ""  # stated rules have chosen what to fill


def test_redefines_symbols_reach_the_page(tmp_path):
    cases, *rest = fixture(tmp_path)
    corpora, lc = layout_case(tmp_path / "l", {"r": cpy("01 REC.", "   05 T PIC X.", "   88 T-A VALUE 'A'.",
                                                        "   05 A.", "      10 X1 PIC X.", "   05 B REDEFINES A.",
                                                        "      10 N1 PIC 9.")})  # fmt: skip
    f = cases / "c-known" / "case.json"
    f.write_text(json.dumps(json.loads(f.read_text()) | lc))
    rep = hr.build(proof(cases, *rest), "x", cases, [corpora])
    assert rep["inputs"]["c-known"]["records"][0]["symbols"] == "A -> B (selector T)"
    blocker = next(b for b in rep["input_blockers"] if b["cause"] == "redefines")
    assert "A -> B (selector T)" in blocker["items"][0]
    assert "A -> B (selector T)" in hr.markdown(rep)


def test_input_blockers_are_stated_as_fixes_and_sorted(tmp_path):
    cases, *rest = fixture(tmp_path)
    corpora, lc = layout_case(tmp_path / "l", {"ren": cpy("01 REC.", "   05 A PIC X.", "   66 R RENAMES A.")})
    lc["mq"] = {}
    lc["datasets"]["REN"]["record_format"] = "VB"
    f = cases / "c-known" / "case.json"
    f.write_text(json.dumps(json.loads(f.read_text()) | lc))
    rep = hr.build(proof(cases, *rest), "x", cases, [corpora])
    kinds = {b["cause"]: b for b in rep["input_blockers"]}
    assert set(kinds) == {"renames", "mq", "recfm v", "db2"}  # (c-db2 of the fixture is a Db2 case)
    assert kinds["renames"]["cases"] == ["c-known"] and kinds["renames"]["tests_held"] == 4
    assert "RENAMES" in kinds["renames"]["fix"] and "(#4266)" in kinds["renames"]["fix"]
    assert [b["tests_held"] for b in rep["input_blockers"]] == sorted(
        (b["tests_held"] for b in rep["input_blockers"]), reverse=True
    )
    assert rep["inputs"]["c-known"]["records"][0]["cause"] == "renames"
    assert "### Input-generation blockers" in hr.markdown(rep)


def test_input_keys_only_when_something_limits_an_input(tmp_path):
    cases, *rest = fixture(tmp_path)
    rep = hr.build(proof(cases, *rest), "x", cases)
    assert [b["cause"] for b in rep["input_blockers"]] == ["db2"]  # the fixture's only limited input
    assert all("records" not in i for i in rep["inputs"].values())
    assert hr.build({"programs": [], "gaps": []}, "none", tmp_path).get("input_blockers") is None


# ---- #4493 issue classes 1 and 3: unclassified because no burned program needs them ------------------------------
EQUIVALENCE = Path(__file__).resolve().parents[1] / "equivalence"
STATED_RULES = {"values", "every", "from", "miss", "digits", "date", "hex"}  # hex: one field's raw bytes (#6072)


def generated_datasets():
    for f in sorted(EQUIVALENCE.glob("*/case.json")):
        case = json.loads(f.read_text(encoding="utf-8"))
        for dd, spec in (case.get("datasets") or {}).items():
            if spec.get("input") == "@generate":
                yield f.parent.name, case, dd, spec


def test_burned_generated_rules_are_stated_single_field_joins():
    """Class 3: no case needs a rule across records (a sum, a transition); `from` joins one field of one dataset."""
    seen = 0
    for name, _case, dd, spec in generated_datasets():
        for field, rule in ((spec.get("generate") or {}).get("fields") or {}).items():
            seen += 1
            assert set(rule) <= STATED_RULES, f"{name}/{dd}.{field}: a rule beyond the stated ones: {sorted(rule)}"
            if "from" in rule:
                assert isinstance(rule["from"], str) and rule["from"].count(".") >= 1, (name, dd, field)
    assert seen  # the committed cases do state rules


def test_burned_generated_inputs_need_no_class_1_or_3_cause():
    """Class 1: no burned generated record repeats a field name (a qualified name would be needed to tell them apart).
    Needs the corpora checkout; without it there is nothing to read."""
    import os

    import equivalence_common as common

    roots = [Path(p) for p in os.environ.get("GITGALAXY_MAINFRAME_CORPORA", "").split(os.pathsep) if p]
    checked = 0
    for name, case, dd, spec in generated_datasets():
        base = next((r / case.get("corpus", "") for r in roots if (r / case.get("corpus", "")).is_dir()), None)
        gen = spec.get("generate") or {}
        cpy = gen.get("copybook") or spec.get("copybook", "")
        if base is None or not (base / cpy).is_file():
            continue
        fields = common.layout_fields(
            base, cpy, gen.get("record") or spec.get("record") or None, copy_dirs=hr.copy_dirs(base, case, cpy)
        )
        names = [f["name"] for f in fields if not f["name"].startswith("FILLER")]
        dup = sorted({n for n in names if names.count(n) > 1})
        assert not dup, f"{name}/{dd}: qualified names needed for {dup}: add a cause to record_cause / FIX_LAYOUT"
        checked += 1
    if not checked:
        pytest.skip("no burned corpus checkout")


def test_burned_generated_records_have_no_redefines_chosen_by_a_field():
    """No burned `@generate` record carries a chosen REDEFINES (checked 2026-10-18); when one does, state its `fields`
    rules or accept the "redefines" blocker. Needs the corpora checkout."""
    import os

    roots = [Path(p) for p in os.environ.get("GITGALAXY_MAINFRAME_CORPORA", "").split(os.pathsep) if p]
    checked = 0
    for name, case, dd, _spec in generated_datasets():
        cause, symbols = hr.record_limit(roots, case, dd)
        if cause == "not read":
            continue
        assert cause != "redefines", f"{name}/{dd}: {symbols}"
        checked += 1
    if not checked:
        pytest.skip("no burned corpus checkout")


def test_untranslated_programs_land_under_one_cause_each(tmp_path):
    """Classes 4 and 5: a program the translator refused or left holes in has no case, so it is listed by cause."""
    cases, corpora, cru, det_baseline, rows = fixture(tmp_path)
    for name in ("LINK1", "LINK2", "STUB", "REFUSED", "NOTCICS"):
        tpb.write(corpora / "estate" / "a" / f"{name}.cbl", tpb.BATCH if name == "NOTCICS" else tpb.CICS)
    err = "CopyNotFound: a/{n}.cbl:3: COPY {c}: not found"
    rows[("estate", "a/LINK1.cbl")] = {"program": "a/LINK1.cbl", "error": err.format(n="LINK1", c="CUSTREC")}
    rows[("estate", "a/LINK2.cbl")] = {"program": "a/LINK2.cbl", "error": err.format(n="LINK2", c="ACCTREC")}
    rows[("estate", "a/STUB.cbl")] = {"program": "a/STUB.cbl", "statements": 5, "translated": 4,
                                      "holes": ["line 12: EXEC EXEC CICS: EXEC CICS GETMAIN not modelled"]}  # fmt: skip
    rows[("estate", "a/REFUSED.cbl")] = {"program": "a/REFUSED.cbl", "error": "ExprError: a/REFUSED.cbl:9: bad"}
    rows[("estate", "a/NOTCICS.cbl")] = {"program": "a/NOTCICS.cbl", "error": "ExprError: x"}
    res = burned(pb.proof_blockers(rows, [corpora], cases_dir=cases, crucible_dir=cru, det_baseline=det_baseline))
    rep = hr.build(res, "x", cases)
    by = {b["cause"]: b for b in rep["untranslated"]}
    link = by["unresolved link"]
    assert [Path(p).stem for p in link["programs"]] == ["LINK1", "LINK2"]
    assert "COPY member" in link["fix"] and any("missing copybook CUSTREC" in i for i in link["items"])
    assert [Path(p).stem for p in by["no stub"]["programs"]] == ["STUB"]
    assert [Path(p).stem for p in by["refused"]["programs"]] == ["REFUSED"]
    listed = [p for b in rep["untranslated"] for p in b["programs"]]
    assert len(listed) == len(set(listed)) and not any("NOTCICS" in p for p in listed)  # not a CICS program
    assert "## Programs with no translation yet" in hr.markdown(rep)
    # the proven / blocker counts are untouched: these programs have no proof subject
    assert rep["coverage"]["programs"] == 9


def test_every_copy_refusal_kind_is_an_unresolved_link_naming_the_member(tmp_path):
    """#4493 class 4: CopyNotFound, CopyAmbiguous and CopyUnresolved (#4468) all state as one fix naming the member;
    a refusal that is no COPY problem stays `refused`."""
    cases, corpora, cru, det_baseline, rows = fixture(tmp_path)
    errs = {
        "NF": "CopyNotFound: a/NF.cbl:3: COPY NFREC: not found",
        "AMB": "CopyAmbiguous: a/AMB.cbl:3: COPY AMBREC: found in lib1, lib2",
        "UNR": "CopyUnresolved: a/UNR.cbl: COPY UNRREC: the engine resolved several files: lib1/UNRREC.cpy, lib2/UNRREC.cpy",
        "UNR2": "CopyUnresolved: a/UNR2.cbl: COPY NONEREC: the engine resolved nothing; the estate holds x/NONEREC.cpy",
        "EXPR": "ExprError: a/EXPR.cbl:9: bad",
    }
    for n, err in errs.items():
        tpb.write(corpora / "estate" / "a" / f"{n}.cbl", tpb.CICS)
        rows[("estate", f"a/{n}.cbl")] = {"program": f"a/{n}.cbl", "error": err}
    res = burned(pb.proof_blockers(rows, [corpora], cases_dir=cases, crucible_dir=cru, det_baseline=det_baseline))
    rep = hr.build(res, "x", cases)
    by = {b["cause"]: b for b in rep["untranslated"]}
    assert [Path(p).stem for p in by["unresolved link"]["programs"]] == ["AMB", "NF", "UNR", "UNR2"]
    assert [Path(p).stem for p in by["refused"]["programs"]] == ["EXPR"]
    items = " | ".join(by["unresolved link"]["items"])
    assert (
        "COPY UNRREC: the engine resolved several files" in items
        and "[COPY NONEREC: the engine resolved nothing" in items
    )
    assert "COPY EXPR" not in " | ".join(by["refused"]["items"]) and "[COPY" not in " | ".join(by["refused"]["items"])
    listed = [p for b in rep["untranslated"] for p in b["programs"]]
    assert len(listed) == len(set(listed))


def test_untranslated_row_carries_the_error_only_for_a_copy_refusal(tmp_path):
    cases, corpora, cru, det_baseline, rows = fixture(tmp_path)
    for n in ("U", "E"):
        tpb.write(corpora / "estate" / "a" / f"{n}.cbl", tpb.CICS)
    rows[("estate", "a/U.cbl")] = {"program": "a/U.cbl", "error": "CopyUnresolved: a/U.cbl: COPY X: gap"}
    rows[("estate", "a/E.cbl")] = {"program": "a/E.cbl", "error": "ExprError: a/E.cbl:9: bad"}
    res = pb.proof_blockers(rows, [corpora], cases_dir=cases, crucible_dir=cru, det_baseline=det_baseline)
    by = {Path(p["program"]).stem: p for p in res["untranslated"]}
    assert "COPY X" in by["U"]["error"] and "error" not in by["E"]


def test_untranslated_key_only_when_something_is_refused(tmp_path):
    cases, *rest = fixture(tmp_path)
    res = proof(cases, *rest)
    assert [p["program"] for p in res["untranslated"]] == ["a/HOLEY.cbl"]  # the fixture's holey program
    del res["untranslated"]
    rep = hr.build(res, "x", cases)
    assert "untranslated" not in rep and "## Programs with no translation yet" not in hr.markdown(rep)
    res["untranslated"] = [
        {"corpus": "estate", "program": "a/N.cbl", "burned": False, "classes": ["missing copybook X"]}
    ]
    assert "untranslated" not in hr.build(res, "x", cases)  # a non-burned program is never named


def test_copy_inside_a_record_resolves_in_the_cases_copy_dirs(tmp_path):
    """#5233: the generator finds a nested COPY in the case's `copy_dirs`; the report must not call it unresolved."""
    corpora, case = layout_case(tmp_path, {"top": cpy("01 REC.", "   COPY INNER.", "   05 A PIC X.")})
    assert hr.record_cause([corpora], case, "TOP") == "unresolved copy"
    tpb.write(corpora / "estate" / "cpy" / "INNER.cpy", cpy("   05 B PIC X(2)."))
    case["copy_dirs"] = ["cpy"]
    assert hr.record_cause([corpora], case, "TOP") == ""


def test_cli_writes_the_page_from_a_proof_blockers_file_deterministically(tmp_path, monkeypatch):
    """#4493: the nightly CI step is this command; a run writes the page (md + json) and a re-run is byte-identical."""
    cases, *rest = fixture(tmp_path)
    src = tmp_path / "proof_blockers.json"
    src.write_text(json.dumps(proof(cases, *rest)), encoding="utf-8")
    monkeypatch.setenv("GITGALAXY_MAINFRAME_CORPORA", str(tmp_path / "no-corpora"))
    pages = []
    for n in ("a", "b"):
        assert hr.main([str(src), "--out", str(tmp_path / n), "--estate", "est", "--cases-dir", str(cases)]) == 0
        pages.append((tmp_path / n / "harness_report.md", tmp_path / n / "harness_report.json"))
    assert pages[0][0].read_text(encoding="utf-8").startswith("# Equivalence harness report -- est")
    assert json.loads(pages[0][1].read_text(encoding="utf-8"))["estate"] == "est"
    assert [p.read_bytes() for p in pages[0]] == [p.read_bytes() for p in pages[1]]
