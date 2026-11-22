"""#7155 part 2: the canary catalog is safe and names real gates, and the opener refuses anything but a canary/ branch."""

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import canary_control as cc  # noqa: E402
import gate_controls as gc  # noqa: E402

WORKFLOW = TOOLS.parents[1] / ".github" / "workflows" / "canary-control.yml"


def test_the_shipped_catalog_is_safe_and_names_real_gates():
    assert cc.problems() == []


def test_each_unsafe_shape_is_named():
    bad = (
        cc.Defect("wf", ".github/workflows/x.yml", "", ("mypy-audit",), "w"),
        cc.Defect("up", "../outside.py", "", ("mypy-audit",), "w"),
        cc.Defect("exists", "tests/tools/canary_control.py", "", ("mypy-audit",), "w"),
        cc.Defect("ghost", "gitgalaxy/new_canary_x.py", "", ("no-such-gate",), "w"),
        cc.Defect("none", "gitgalaxy/new_canary_y.py", "", (), "w"),
        cc.Defect("pub", "tools/publish.yml", "", ("mypy-audit",), "w"),
    )
    out = cc.problems(bad)
    for key, word in (
        ("wf:", "workflow"),
        ("up:", "leaves"),
        ("exists:", "already exists"),
        ("ghost:", "no gate named"),
        ("none:", "no gate to go red"),
        ("pub:", "workflow"),
    ):
        assert any(p.startswith(key) and word in p for p in out), (key, out)
    twice = (cc.DEFECTS[0], cc.DEFECTS[0])
    assert any("planted twice" in p for p in cc.problems(twice))


def test_the_plan_lists_every_gate_that_must_go_red_once():
    p = cc.plan()
    assert p["must_go_red"] == sorted(set(p["must_go_red"]))
    assert {g for d in cc.DEFECTS for g in d.red} == set(p["must_go_red"])
    assert {g.name for g in gc.GATES} >= set(p["must_go_red"])


def test_the_pr_body_carries_a_parseable_expectation_and_a_do_not_merge_note():
    body = cc.pr_body()
    m = re.search(rf"<!-- {cc.MARKER} (\{{.*\}}) -->", body)
    assert m and json.loads(m.group(1)) == cc.plan()
    assert "do not merge" in body


def test_a_non_canary_branch_is_refused_and_a_dry_run_changes_nothing(capsys, monkeypatch):
    monkeypatch.setattr(cc.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran a command")))
    assert cc.open_pr("feature/x") == 2
    assert cc.open_pr("main", dry_run=True) == 2
    assert cc.open_pr("canary/20261122T0000Z", dry_run=True) == 0
    assert "must_go_red" in capsys.readouterr().out


def test_branch_names_are_canary_prefixed():
    assert cc.branch_name(datetime(2026, 11, 22, 3, 17, tzinfo=UTC)) == "canary/20261122T0317Z"


def test_plant_writes_only_the_catalog_files(tmp_path):
    paths = cc.plant(tmp_path)
    assert paths == [d.path for d in cc.DEFECTS]
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*") if p.is_file()) == sorted(paths)


def test_the_workflow_only_opens_a_pr_never_merges_and_has_no_pr_trigger():
    text = WORKFLOW.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    on = doc.get(True) or doc.get("on")
    assert set(on) == {"schedule", "workflow_dispatch"}
    assert "merge" not in re.sub(r"#.*", "", text).lower().replace("never merge", "")
    assert "shepherd:" not in text
    assert doc["permissions"] == {"contents": "read"}
