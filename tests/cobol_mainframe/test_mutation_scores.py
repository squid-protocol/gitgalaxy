"""#4047: the crucible ports' mutation verdicts (tests/tools/mutation_crucible.py) and the committed scores table
(tests/tools/mutation_scores.py): what counts as caught, what counts for nothing, and the two scores."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import mutation_crucible as mc
import mutation_scores as ms

REPO = Path(__file__).resolve().parents[2]


def test_a_crucible_mutant_is_killed_by_the_scenarios_that_failed_and_stillborn_when_it_does_not_compile():
    passed = {"proven": True, "cells": {"c/a/java-ported": {"status": "pass"}}}
    assert mc.verdict(0, passed) == ("survived", [])
    failed = {"proven": False, "cells": {"c/a/java-ported": {"status": "pass"}, "c/b/java-ported": {"status": "fail"}}}
    assert mc.verdict(1, failed) == ("killed", ["b"])
    broken = {"proven": False, "cells": {"c/a/java-ported": {"status": "fail", "kind": mc.NOT_COMPILED}}}
    assert mc.verdict(1, broken) == ("stillborn", [])
    assert mc.verdict(None, None) == ("timeout", [])
    assert mc.verdict(1, None) == ("killed", ["runner"])  # the runner died before its report


def test_every_committed_crucible_port_is_found():
    found = mc.ports(None)
    assert len(found) == len(list((REPO / "tests" / "cics_crucible" / "ports").glob("*/*/provenance.json")))
    assert [p[1] for p in mc.ports(["CASUB"])] == ["CASUB"]


def _run():
    res = [("a", "ROR", "killed"), ("b", "ROR", "timeout"), ("c", "ROR", "survived"), ("d", "DEL", "survived"),
           ("e", "DEL", "stillborn"), ("f", "LIT", "survived")]  # fmt: skip
    return {"case": "x-case", "program": "PROG", "mutants": 10, "chosen": 6, "seed": 0,
            "results": [{"id": i, "op": op, "file": "S.java", "line": n, "before": "b", "after": "a", "verdict": v}
                        for n, (i, op, v) in enumerate(res)]}  # fmt: skip


def test_the_scores_drop_equivalent_and_unreachable_survivors_only_from_the_adjusted_score(tmp_path):
    triage = {"x-case/PROG:c": {"verdict": "equivalent", "reason": "r"},
              "x-case/PROG:d": {"verdict": "case_gap", "reason": "r"}}  # fmt: skip
    p = ms.port_entry(_run(), triage, "abc")
    assert p["total"]["killed"] == 2 and p["total"]["survived"] == 3 and p["total"]["stillborn"] == 1
    assert p["total"]["equivalent"] == 1 and p["total"]["case_gap"] == 1 and p["total"]["untriaged"] == 1
    assert ms.scores(p["total"]) == (2, 5, 4)
    assert p["ops"]["DEL"] == {"survived": 1, "stillborn": 1, "case_gap": 1}
    doc = tmp_path / "d.md"
    doc.write_text(f"intro\n{ms.BEGIN}\nold\n{ms.END}\nafter\n", encoding="utf-8")
    ms.render({"ports": [p]}, doc)
    text = doc.read_text(encoding="utf-8")
    assert "old" not in text and text.startswith("intro\n") and text.endswith(f"{ms.END}\nafter\n")
    assert "| PROG (x-case) | equivalence | 6/10 | 2/5 (40%) | 2/4 (50%) | 1 / 0 / 1 / 0 / 1 |" in text


def test_the_committed_table_is_the_committed_results():
    if not ms.RESULTS.exists():
        return
    results = json.loads(ms.RESULTS.read_text(encoding="utf-8"))
    assert ms.table(results) in ms.DOC.read_text(encoding="utf-8")


def test_a_crucible_port_is_mutated_in_its_own_files_not_the_shared_runtime():
    overlay = REPO / "tests" / "cics_crucible" / "ports" / "pc-return-immediate" / "PCIMMA" / "overlay"
    assert (overlay / "cobolrt").is_dir()  # this port ships the runtime
    every = mc.mu.all_mutants(overlay, set(mc.mu.OPERATORS))
    own = [m for m in every if not m.file.startswith(mc.SHARED_RUNTIME)]
    assert own and len(own) < len(every)
    assert {m.file for m in own} == {"service/PcimmaService.java"}


# ---- #4048: a mutation run updates the port's evidence record itself --------------------------------------------------
def _committed_stand_in(tmp_path, monkeypatch):
    """RESULTS and DOC point into tmp_path; a stub `evidence` module records the refresh the build must trigger."""
    import types

    calls: list[str] = []
    stub = types.SimpleNamespace(refresh_mutation=lambda: calls.append("refresh") or ["k"],
                                 write_pages=lambda: calls.append("pages") or 0)  # fmt: skip
    monkeypatch.setitem(sys.modules, "evidence", stub)
    results, doc = tmp_path / "scores.json", tmp_path / "doc.md"
    doc.write_text(f"{ms.BEGIN}\nold\n{ms.END}\n", encoding="utf-8")
    monkeypatch.setattr(ms, "RESULTS", results)
    monkeypatch.setattr(ms, "DOC", doc)
    run_dir = tmp_path / "work"
    run_dir.mkdir()
    (run_dir / "mutation.json").write_text(json.dumps(_run()), encoding="utf-8")
    return calls, results, doc, run_dir


def test_recording_a_run_refreshes_the_records_and_keeps_the_committed_triage(tmp_path, monkeypatch):
    calls, results, doc, run_dir = _committed_stand_in(tmp_path, monkeypatch)
    ms.build_scores([run_dir], {"x-case/PROG:c": {"verdict": "equivalent", "reason": "r"}}, "abc", results)
    assert calls == ["refresh", "pages"]
    ms.record_run(run_dir)  # no triage given: the committed file's verdict for "c" carries over
    entry = next(p for p in json.loads(results.read_text(encoding="utf-8"))["ports"] if p["program"] == "PROG")
    assert entry["total"]["equivalent"] == 1 and entry["total"]["untriaged"] == 2
    assert calls == ["refresh", "pages", "refresh", "pages"]
    assert "old" not in doc.read_text(encoding="utf-8")


def test_a_build_into_another_file_leaves_the_records_alone(tmp_path, monkeypatch):
    calls, _, _, run_dir = _committed_stand_in(tmp_path, monkeypatch)
    ms.build_scores([run_dir], {}, "abc", tmp_path / "other.json")
    assert calls == []


def test_mutation_run_record_chains_the_scoring_and_refuses_overrides(tmp_path, monkeypatch):
    import mutation as mu

    seen: list[tuple[Path, list[Path]]] = []
    monkeypatch.setattr(ms, "record_run", lambda work, triage=None: seen.append((work, triage)))
    monkeypatch.setattr(mu, "run", lambda *a, **k: {"results": []})
    monkeypatch.setattr(mu, "mutation_md", lambda s: "")
    work = tmp_path / "w"
    assert mu.main(["run", "carddemo-x", "--work", str(work), "--sample", "3", "--record"]) == 0
    assert seen == [(work, [])]
    for extra in (["--case-file", "c.json"], ["--only", "d"], ["--port", "p"], ["--files", "service/*.java"]):
        with pytest.raises(SystemExit):
            mu.main(["run", "carddemo-x", "--work", str(work), "--record", *extra])
    assert len(seen) == 1
    assert mu.main(["run", "carddemo-x", "--work", str(work)]) == 0  # without --record nothing is scored
    assert len(seen) == 1


def test_crucible_run_record_chains_per_port_and_refuses_case_gaps(tmp_path, monkeypatch):
    monkeypatch.setenv("CICS_CRUCIBLE_PATH", str(tmp_path))
    seen: list[Path] = []
    monkeypatch.setattr(ms, "record_run", lambda work, triage=None: seen.append(work))
    monkeypatch.setattr(mc, "ports", lambda only: [("case-a", "PROGA", tmp_path), ("case-b", "PROGB", tmp_path)])
    monkeypatch.setattr(mc, "run_port", lambda case, prog, overlay, work, args: {"results": [], "seconds": 0})
    work = tmp_path / "w"
    assert mc.main(["run", "--work", str(work), "--record"]) == 0
    assert seen == [work / "case-a" / "PROGA", work / "case-b" / "PROGB"]
    with pytest.raises(SystemExit):
        mc.main(["run", "--work", str(work), "--record", "--case-gaps"])
    assert mc.main(["run", "--work", str(work)]) == 0 and len(seen) == 2


def test_the_operator_matrix_gives_each_port_its_caught_over_judged_per_operator():
    p = ms.port_entry(_run(), {}, "abc")
    lines = ms.operator_matrix({"ports": [p]}).splitlines()
    assert lines[0] == "| port | DEL | LIT | ROR |"
    assert lines[2] == "| PROG (x-case) | 0/1 | 0/1 | 2/3 |"  # stillborn DEL counts for nothing, timeout is caught
    assert (
        ms.operator_matrix({"ports": [{**p, "ops": {"ROR": {"killed": 1}}}, p]})
        .splitlines()[2]
        .endswith("| - | - | 1/1 |")
    )


# #4047: ports whose survivors still carry the default placeholder verdict instead of a read triage. This set only
# shrinks: triage a port (`mutation_scores.py retriage`) and delete its line.
UNREAD_PLACEHOLDERS: set[str] = set()  # the three GenApp ports were read and triaged (#4047)


def test_placeholder_verdicts_only_shrink_and_every_triaged_survivor_has_a_reason():
    results = json.loads(ms.RESULTS.read_text(encoding="utf-8"))
    assert set(ms.placeholders(results)) <= UNREAD_PLACEHOLDERS
    for port in results["ports"]:
        for s in port["survivors"]:
            assert s["verdict"] != "untriaged" and s["reason"].strip()


def test_the_generated_acctview_case_is_scored_and_states_the_card_numbers_that_kill_the_parser_mutants():
    """#4506: a generated xref card number is random text, so alnumToUnsigned always returned 0 and hid its mutants."""
    results = json.loads(ms.RESULTS.read_text(encoding="utf-8"))
    port = next(p for p in results["ports"] if p["case"] == "carddemo-acctview-generated")
    assert port["total"]["untriaged"] == 0 and port["total"]["killed"] > 100
    case = json.loads((REPO / "tests/equivalence/carddemo-acctview-generated/case.json").read_text(encoding="utf-8"))
    xref = case["datasets"]["AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS"]["generate"]["fields"]["XREF-CARD-NUM"]
    assert len(set(xref["values"])) == len(xref["values"]) and all(len(v) == 16 for v in xref["values"])
    card = [s for s in case["scenarios"] if s["name"].startswith("card-number-")]
    assert len(card) == 7 and all("#4506" in s["why"] for s in card)


def test_the_generated_signon_case_is_scored_and_states_the_credentials_that_kill_the_survivors():
    """#4506: COSGN00C's generated variant is scored; its survivors were stated inputs the random draw missed."""
    results = json.loads(ms.RESULTS.read_text(encoding="utf-8"))
    ports = {p["case"]: p for p in results["ports"]}
    for name in ("carddemo-signon-generated", "carddemo-acctview-generated"):
        total = ports[name]["total"]
        assert total["untriaged"] == 0 and total["case_gap"] == 0 and total["killed"] > 90
        for s in ports[name]["survivors"]:
            assert s["reason"].strip() and s["verdict"] != "untriaged"
    case = json.loads((REPO / "tests/equivalence/carddemo-signon-generated/case.json").read_text(encoding="utf-8"))
    ids = case["datasets"]["AWS.M2.CARDDEMO.USRSEC.VSAM.KSDS"]["generate"]["fields"]["SEC-USR-ID"]["values"]
    named = {s["name"]: s for s in case["scenarios"]}
    for n in (
        "lowercase-z-credentials",
        "uppercase-z-credentials",
        "user-not-on-file",
        "userid-not-sent",
        "passwd-not-sent",
    ):
        assert "#4506" in named[n]["why"]
    z = named["lowercase-z-credentials"]["receive"]["COSGN0A"]["USERIDI"]
    assert "z" in z and z.upper() in ids
    assert named["user-not-on-file"]["receive"]["COSGN0A"]["USERIDI"] not in ids
    assert "USERIDI" not in named["userid-not-sent"]["receive"]["COSGN0A"]
    assert "PASSWDI" not in named["passwd-not-sent"]["receive"]["COSGN0A"]


def test_the_generated_billpay_case_is_scored_and_states_the_inputs_that_kill_the_survivors():
    """#4506: COBIL00C's generated variant is scored; its survivors were stated inputs the random draw missed."""
    results = json.loads(ms.RESULTS.read_text(encoding="utf-8"))
    ports = {p["case"]: p for p in results["ports"]}
    total = ports["carddemo-billpay-generated"]["total"]
    assert total["untriaged"] == 0 and total["case_gap"] == 0 and total["killed"] > 100
    for s in ports["carddemo-billpay-generated"]["survivors"]:
        assert s["reason"].strip() and s["verdict"] != "untriaged"
    case = json.loads((REPO / "tests/equivalence/carddemo-billpay-generated/case.json").read_text(encoding="utf-8"))
    ids = case["datasets"]["AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS"]["generate"]["fields"]["TRAN-ID"]["values"]
    # the oracle sorts ASCII, the port cp037: a key mixing letters and digits would order differently
    assert ids and all(v.isdigit() for v in ids)
    named = {s["name"]: s for s in case["scenarios"]}
    for n in (
        "pay-lowercase-y",
        "zero-balance-confirm",
        "pay-large-balance",
        "pay-near-maximum-balance",
        "account-id-one-digit-padded",
        "account-id-embedded-blank",
        "account-id-with-letter",
        "endbr-invalid-request",
        "pf3-blank-from-program",
    ):
        assert "#4506" in named[n]["why"]
    assert [f["cmd"] for f in named["endbr-invalid-request"]["faults"]] == ["ENDBR"]
    assert named["pf3-blank-from-program"]["commarea"]["CDEMO-FROM-PROGRAM"] == ""


def test_the_generated_transaction_view_case_is_scored_and_states_the_mapfail_input():
    """#4506: COTRN01C's generated variant is scored on 150 mutants; its one case gap was an input the draw missed."""
    results = json.loads(ms.RESULTS.read_text(encoding="utf-8"))
    ports = {p["case"]: p for p in results["ports"]}
    port = ports["carddemo-tranview-generated"]
    total = port["total"]
    assert port["chosen"] == 150
    assert total["untriaged"] == 0 and total["case_gap"] == 0 and total["killed"] > 80
    for s in port["survivors"]:
        assert s["reason"].strip() and s["verdict"] != "untriaged"
    case = json.loads((REPO / "tests/equivalence/carddemo-tranview-generated/case.json").read_text(encoding="utf-8"))
    named = {s["name"]: s for s in case["scenarios"]}
    scenario = named["enter-no-map-received"]
    assert "#4506" in scenario["why"]
    # a MAPFAIL: the screen is never received, so the port's cleared screen is what the oracle compares
    assert "receive" not in scenario
    # #4506: the cursor of the found-record screen is set on the ENTER branch; only a received id the file holds
    # reaches it, so the case receives the first key of the generated TRANSACT file (seed 4506)
    found = named["enter-existing-transaction-id"]
    assert "#4506" in found["why"]
    assert found["aid"] == "DFHENTER" and "faults" not in found
    assert found["receive"]["COTRN1A"]["TRNIDINI"] == "A1GB0BH0JI5U9KUG"
    assert total["harness_gap"] == 0


def test_the_generated_menu_case_is_scored_and_states_the_scenarios_its_survivors_needed():
    """#4506: COMEN01C's generated variant is scored on 150 mutants; its case gaps were the twin's scenarios."""
    results = json.loads(ms.RESULTS.read_text(encoding="utf-8"))
    ports = {p["case"]: p for p in results["ports"]}
    port = ports["carddemo-menu-generated"]
    total = port["total"]
    assert port["chosen"] == 150
    assert total["untriaged"] == 0 and total["case_gap"] == 0 and total["killed"] > 80
    for s in port["survivors"]:
        assert s["reason"].strip() and s["verdict"] != "untriaged"
    case = json.loads((REPO / "tests/equivalence/carddemo-menu-generated/case.json").read_text(encoding="utf-8"))
    named = {s["name"]: s for s in case["scenarios"]}
    for name in ("option-11-installed", "option-past-the-table", "carried-commarea-fields"):
        assert "#4506" in named[name]["why"]
    # a non-digit option is refused by the oracle (register X8), so it is a limit, not a scenario
    assert "option-non-numeric" not in named


def test_the_re_run_menu_and_account_view_cases_are_current_and_state_the_scenarios_their_survivors_needed():
    """#4443: carddemo-menu and carddemo-acctview were re-run on their current ports (seed 0, 150 mutants); the
    survivors showed two committed-case gaps, closed with stated scenarios, and the record is current again."""
    results = json.loads(ms.RESULTS.read_text(encoding="utf-8"))
    ports = {p["case"]: p for p in results["ports"]}
    for name in ("carddemo-menu", "carddemo-acctview"):
        port = ports[name]
        assert port["chosen"] == 150 and port["total"]["untriaged"] == 0 and port["total"]["harness_gap"] == 0
        for s in port["survivors"]:
            assert s["reason"].strip() and s["verdict"] != "untriaged"
        evidence = json.loads((REPO / "tests/equivalence" / name / "evidence.json").read_text(encoding="utf-8"))
        assert evidence["mutation"]["inputs"]["port"]["sha256"] == evidence["inputs"]["port"]["sha256"]
    assert ports["carddemo-menu"]["total"]["case_gap"] == 0
    # the account view's alnumToUnsigned parser mutants are killed by stated card-number records (xref accounts 52-62)
    assert ports["carddemo-acctview"]["total"]["case_gap"] == 0
    for name, scenarios in (
        ("carddemo-menu", ("carried-customer-and-card-fields",)),
        ("carddemo-acctview", ("pf15-back-to-menu", "carried-middle-name-and-ids")),
    ):
        case = json.loads((REPO / "tests/equivalence" / name / "case.json").read_text(encoding="utf-8"))
        named = {s["name"]: s for s in case["scenarios"]}
        for scenario in scenarios:
            assert "#4443" in named[scenario]["why"]
    case = json.loads((REPO / "tests/equivalence/carddemo-acctview/case.json").read_text(encoding="utf-8"))
    card = [s for s in case["scenarios"] if s["name"].startswith("card-number-")]
    assert len(card) == 11 and all("#4443" in s["why"] for s in card)
    xref = (REPO / "tests/equivalence/carddemo-acctview/cardxref-4049.txt").read_text(encoding="utf-8").splitlines()
    assert len(xref) == 1 + len(card) and all(len(r) == 36 for r in xref)
    assert len({r[:16] for r in xref}) == len(xref)
    acct = (REPO / "tests/equivalence/carddemo-acctview/acctdata-4049.txt").read_text(encoding="utf-8").splitlines()
    assert [r[:11] for r in acct] == [r[25:36] for r in xref]
    assert {s["receive"]["CACTVWA"]["ACCTSIDI"] for s in card} == {r[25:36] for r in xref[1:]}


def test_the_generated_admin_menu_case_is_scored_and_states_the_scenarios_its_survivors_needed():
    """#4506: COADM01C's generated variant is scored on 150 mutants; its case gaps became three stated scenarios."""
    results = json.loads(ms.RESULTS.read_text(encoding="utf-8"))
    ports = {p["case"]: p for p in results["ports"]}
    port = ports["carddemo-adminmenu-generated"]
    total = port["total"]
    assert port["chosen"] == 150
    assert total["untriaged"] == 0 and total["case_gap"] == 0 and total["killed"] > 90
    for s in port["survivors"]:
        assert s["reason"].strip() and s["verdict"] != "untriaged"
    case = json.loads((REPO / "tests/equivalence/carddemo-adminmenu-generated/case.json").read_text(encoding="utf-8"))
    named = {s["name"]: s for s in case["scenarios"]}
    for name in ("option-9", "option-11", "option-5-pgmiderr"):
        assert "#4506" in named[name]["why"]
        assert "faults" not in named[name]


def test_retriage_replaces_a_verdict_and_recounts_the_totals_and_operators():
    p = ms.port_entry(_run(), {"x-case/PROG:c": {"verdict": "case_gap", "reason": ms.PLACEHOLDER}}, "abc")
    assert ms.placeholders({"ports": [p]}) == {"x-case/PROG": 1}
    n = ms.retriage_port(p, {"x-case/PROG:c": {"verdict": "equivalent", "reason": "never reached"}})
    assert n == 1 and ms.placeholders({"ports": [p]}) == {}
    assert p["total"]["equivalent"] == 1 and p["total"]["case_gap"] == 0
    assert p["ops"]["ROR"].get("equivalent") == 1 and "case_gap" not in p["ops"]["ROR"]
    assert ms.scores(p["total"]) == (2, 5, 4)


DECLARED = {"verdict": "declared_difference", "class": "float-store-rounding", "register": "C6", "reason": "r"}


def test_a_declared_difference_is_counted_but_not_subtracted_from_the_adjusted_score():
    # #5401: unlike `equivalent`, a declared difference is a real IBM difference and stays among the judged survivors
    p = ms.port_entry(_run(), {"x-case/PROG:c": DECLARED, "x-case/PROG:d": {"verdict": "equivalent", "reason": "r"}}, "abc")
    assert p["total"]["declared_difference"] == 1 and p["total"]["equivalent"] == 1
    assert ms.scores(p["total"]) == (2, 5, 4)
    (s,) = [s for s in p["survivors"] if s["id"] == "c"]
    assert (s["verdict"], s["class"], s["register"]) == ("declared_difference", "float-store-rounding", "C6")
    assert "+ 1 declared |" in ms.table({"ports": [p]})
    again = ms.port_entry(_run(), {"x-case/PROG:c": {"verdict": "case_gap", "reason": "r"}}, "abc")
    assert "declared_difference" not in again["total"]  # the key exists only where non-zero
    assert ms.retriage_port(again, {"x-case/PROG:c": DECLARED}) == 1
    assert again["total"]["declared_difference"] == 1 and again["total"]["case_gap"] == 0
    assert ms.retriage_port(again, {"x-case/PROG:c": {"verdict": "case_gap", "reason": "r"}}) == 1
    assert "declared_difference" not in again["total"] and "class" not in again["survivors"][0]


@pytest.mark.parametrize("bad", [{}, {"class": "float-store-rounding"}, {"register": "C6"},
                                 {"class": "float-store-rounding", "register": "C2"}, {"class": "other", "register": "C6"}])
def test_a_declared_difference_without_its_class_and_register_entry_is_refused(bad):
    triage = {"x-case/PROG:c": {"verdict": "declared_difference", "reason": "r", **bad}}
    with pytest.raises(SystemExit, match="declared_difference"):
        ms.port_entry(_run(), triage, "abc")


def test_corpt00c_d2fca7d77a_is_the_committed_float_store_declared_difference():
    results = json.loads(ms.RESULTS.read_text(encoding="utf-8"))
    (port,) = [p for p in results["ports"] if (p["case"], p["program"]) == ("carddemo-report", "CORPT00C")]
    (s,) = [s for s in port["survivors"] if s["id"] == "d2fca7d77a"]
    assert (s["verdict"], s["class"], s["register"]) == ("declared_difference", "float-store-rounding", "C6")
    assert port["total"]["declared_difference"] == 1
    assert sum(p["total"].get("declared_difference", 0) for p in results["ports"]) == 1


# ---- #4047: the crucible runner's fast mode (a generated project copied per mutant) -----------------------------


def test_the_proof_command_carries_the_forge_cache_only_in_fast_mode(tmp_path):
    fast = mc.prove_command("c", "P", tmp_path / "o", tmp_path / "out", tmp_path / "cache")
    full = mc.prove_command("c", "P", tmp_path / "o", tmp_path / "out")
    assert fast[fast.index("--forge-cache") + 1] == str(tmp_path / "cache") and "--forge-cache" not in full
    assert fast[: fast.index("--forge-cache")] == full  # both sides, the overlay and the program are the same
    assert fast[fast.index("--sides") + 1 : fast.index("--sides") + 3] == ["java-ported", "java-facade"]


def _fake_forge(monkeypatch, tmp_path):
    """cics_crucible.forge with the generator and Maven replaced: the generator writes one file and counts its runs."""
    import types

    import cics_crucible as cx

    runs: list[Path] = []

    def generate(clean, name, config, work, header=None):
        runs.append(work)
        project = work / "java_h2"
        (project / "src/main/java").mkdir(parents=True)
        (project / "src/main/java/Gen.java").write_text("generated", encoding="utf-8")
        (project / "target").mkdir()
        (project / "target/stale.class").write_text("x", encoding="utf-8")
        return project

    fake = types.SimpleNamespace(refactor=lambda corpus, work, scan=False: work, generate=generate, MATRIX={"h2": {}})
    monkeypatch.setitem(sys.modules, "java_target_matrix", fake)
    monkeypatch.setattr(cx, "maven", lambda project, args, offline, log: (True, ""))
    monkeypatch.setattr(cx, "lay_overlay", lambda overlay, project: (project / "laid.txt").write_text(overlay.name))
    return cx, runs, types.SimpleNamespace(dir=tmp_path)


def test_a_forge_cache_is_generated_once_and_each_copy_has_the_overlay_but_no_build_output(monkeypatch, tmp_path):
    cx, runs, case = _fake_forge(monkeypatch, tmp_path)
    cache = tmp_path / "cache"
    for n in range(3):  # the baseline fills the cache, two mutants copy it
        verdict, project = cx.forge(case, tmp_path / f"w{n}", False, [tmp_path / f"overlay{n}"], cache)
        assert verdict.status == "pass"
        assert (project / "src/main/java/Gen.java").read_text(encoding="utf-8") == "generated"
        assert (project / "laid.txt").read_text(encoding="utf-8") == f"overlay{n}"  # this mutant's, not the first's
        assert n == 0 or not (project / "target").exists()  # a copy never carries the baseline's build output
    assert len(runs) == 1  # generated once
    assert not (cache / "project" / "laid.txt").exists() and not (cache / "project" / "target").exists()
    cx.forge(case, tmp_path / "w9", False, [tmp_path / "o"], None)  # no cache: --full generates every time
    assert len(runs) == 2


def test_compare_gates_two_crucible_runs_of_one_port(tmp_path):
    def run(mode, verdicts):
        d = tmp_path / mode
        d.mkdir()
        res = [{"id": f"m{n}", "op": "ROR", "line": n, "verdict": v, "seconds": 1} for n, v in enumerate(verdicts)]
        (d / "mutation.json").write_text(json.dumps({"mode": mode, "results": res}), encoding="utf-8")
        return str(d)

    same = ["killed", "survived", "stillborn", "timeout"]
    a, b = run("full", same), run("fast", ["timeout", "survived", "stillborn", "killed"])  # timeout and killed: caught
    assert mc.main(["compare", a, b, "--require-agree", "4"]) == 0
    assert mc.main(["compare", a, b, "--require-agree", "5"]) == 1  # too few judged
    c = run("other", ["survived", "survived", "stillborn", "killed"])
    assert mc.main(["compare", a, c, "--require-agree", "1"]) == 1  # one mutant judged differently
