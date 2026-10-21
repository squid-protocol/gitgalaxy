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


def test_retriage_replaces_a_verdict_and_recounts_the_totals_and_operators():
    p = ms.port_entry(_run(), {"x-case/PROG:c": {"verdict": "case_gap", "reason": ms.PLACEHOLDER}}, "abc")
    assert ms.placeholders({"ports": [p]}) == {"x-case/PROG": 1}
    n = ms.retriage_port(p, {"x-case/PROG:c": {"verdict": "equivalent", "reason": "never reached"}})
    assert n == 1 and ms.placeholders({"ports": [p]}) == {}
    assert p["total"]["equivalent"] == 1 and p["total"]["case_gap"] == 0
    assert p["ops"]["ROR"].get("equivalent") == 1 and "case_gap" not in p["ops"]["ROR"]
    assert ms.scores(p["total"]) == (2, 5, 4)
