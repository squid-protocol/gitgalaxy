"""#4047: the crucible ports' mutation verdicts (tests/tools/mutation_crucible.py) and the committed scores table
(tests/tools/mutation_scores.py): what counts as caught, what counts for nothing, and the two scores."""

import json
import sys
from pathlib import Path

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
