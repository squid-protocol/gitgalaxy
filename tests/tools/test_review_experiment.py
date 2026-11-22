"""#7155 part 3: the review experiment's prompt is blind, its scorer is right on every shape of answer, and `run` is owner-gated."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import review_controls as rc  # noqa: E402
import review_experiment as ex  # noqa: E402

DEFECTIVE = [c for c in rc.CONTROLS if c.cls]
TWINS = [c for c in rc.CONTROLS if not c.cls]


def _review(verdict, *findings):
    return json.dumps({"verdict": verdict, "findings": list(findings)})


def _on_target(c):
    key = rc.answer_key(c)
    return {"file": key["file"], "line_text": key["where"], "summary": "something is wrong here"}


@pytest.mark.parametrize("c", rc.CONTROLS, ids=lambda c: c.key)
def test_the_prompt_is_blind(c):
    text = ex.prompt_for(c)
    assert not rc.LEAKY.search(text)
    assert not c.cls or (c.what not in text and c.cls not in text)
    assert c.title in text and c.body.strip() in text and rc.diff(c) in text


@pytest.mark.parametrize("c", DEFECTIVE, ids=lambda c: c.key)
def test_a_review_that_quotes_the_defect_line_is_caught(c):
    s = ex.score_review(c, _review("request_changes", _on_target(c)))
    assert s["caught"] is True and s["stray"] == 0 and not s["false_alarm"] and not s["malformed"]


@pytest.mark.parametrize("c", DEFECTIVE, ids=lambda c: c.key)
def test_a_fenced_answer_with_chatter_still_parses(c):
    raw = "Here you go:\n```json\n" + _review("request_changes", _on_target(c)) + "\n```\n"
    assert ex.score_review(c, raw)["caught"] is True


@pytest.mark.parametrize("c", DEFECTIVE, ids=lambda c: c.key)
def test_each_way_to_miss_is_a_miss(c):
    on = _on_target(c)
    wrong_file = {**on, "file": "tests/tools/other.py"}
    wrong_line = {**on, "line_text": "return 1"}
    no_quote = {**on, "line_text": ""}
    for findings, stray in (([wrong_file], 1), ([wrong_line], 1), ([no_quote], 1), ([], 0)):
        s = ex.score_review(c, _review("approve", *findings))
        assert s["caught"] is False and s["stray"] == stray and s["false_alarm"] is bool(stray)


@pytest.mark.parametrize("raw", ["", "no json here", "{not json}", '{"verdict": "maybe", "findings": []}',
                                 '{"verdict": "approve", "findings": ["x"]}', "[1, 2]"])  # fmt: skip
def test_an_unusable_answer_is_malformed_and_counts_as_a_miss(raw):
    d, t = ex.score_review(DEFECTIVE[0], raw), ex.score_review(TWINS[0], raw)
    assert d["malformed"] and d["caught"] is False
    assert t["malformed"] and t["caught"] is None and not t["false_alarm"]


@pytest.mark.parametrize("c", TWINS, ids=lambda c: c.key)
def test_a_clean_twin_approved_is_no_false_alarm_and_any_objection_is(c):
    ok = ex.score_review(c, _review("approve"))
    assert ok["caught"] is None and not ok["false_alarm"]
    blocked = ex.score_review(c, _review("request_changes"))
    assert blocked["false_alarm"] and blocked["blocked"]
    nit = ex.score_review(c, _review("approve", {"file": c.module, "line_text": "x", "summary": "nit"}))
    assert nit["false_alarm"] and nit["stray"] == 1


def test_the_report_compares_two_models_on_the_same_set():
    rows = []
    for c in rc.CONTROLS:
        caught = _review("request_changes", _on_target(c)) if c.cls else _review("approve")
        rows.append({"model": "strong", "key": c.key, "raw": caught})
        missed = _review("approve") if c.cls else _review("request_changes")
        rows.append({"model": "weak", "key": c.key, "raw": missed if c.key != "swallow" else caught})
    out = ex.report(rows)
    assert out["models"]["strong"]["catch_rate"] == [3, 3]
    assert out["models"]["strong"]["twin_false_alarms"] == [0, 3]
    assert out["models"]["weak"]["catch_rate"] == [1, 3]
    assert out["models"]["weak"]["twin_false_alarms"] == [3, 3]
    assert out["models"]["strong"]["catch"] == {c.cls: [1, 1] for c in DEFECTIVE}
    assert out["delta"]["catch_rate"] == [[3, 3], [1, 3]]
    assert "no verdict" in out["note"]


def test_run_without_owner_ok_calls_no_model(monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("a model was called")

    monkeypatch.setattr(subprocess, "run", boom)
    assert ex.main(["run", "--models", "sonnet,opus", "--repeats", "2"]) == 0
    head = json.loads(capsys.readouterr().out.splitlines()[0])
    assert head["dry_run"] is True and head["reviews"] == len(rc.CONTROLS) * 2 * 2 and head["input_tokens"] > 0


def test_run_with_owner_ok_pipes_the_blind_prompt_to_a_text_only_model(monkeypatch, tmp_path):
    calls = []

    def fake(cmd, **kw):
        calls.append((cmd, kw["input"]))
        return subprocess.CompletedProcess(cmd, 0, stdout=_review("approve"), stderr="")

    monkeypatch.setattr(subprocess, "run", fake)
    out = tmp_path / "r.json"
    assert ex.main(["run", "--models", "sonnet", "--owner-ok", "--out", str(out)]) == 0
    assert len(calls) == len(rc.CONTROLS)
    cmd, sent = calls[0]
    assert cmd[0] == "claude" and "--model" in cmd and cmd[cmd.index("--tools") + 1] == ""
    assert not rc.LEAKY.search(sent)
    rows = json.loads(out.read_text(encoding="utf-8"))
    assert {r["key"] for r in rows} == set(rc.BY_KEY) and ex.report(rows)["models"]["sonnet"]["catch_rate"] == [0, 3]


def test_prompt_and_report_commands(tmp_path, capsys):
    assert ex.main(["prompt", "swallow"]) == 0
    assert "Title: Read the retry budget" in capsys.readouterr().out
    res = tmp_path / "r.json"
    res.write_text(json.dumps([{"model": "m", "key": "swallow", "raw": _review("approve")}]), encoding="utf-8")
    assert ex.main(["report", str(res)]) == 0
    assert json.loads(capsys.readouterr().out)["models"]["m"]["catch_rate"] == [0, 1]
