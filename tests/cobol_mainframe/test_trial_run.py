"""#8322: `trial.py run` books a first attempt per program, decomposed by what the oracle could judge (Amendment 4)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import trial  # noqa: E402


def _verdict(key: str, event: str, oracle: str | None) -> dict:
    e = {"ticket": key, "event": event}
    if oracle is not None:
        e["oracle"] = oracle
    return e


def test_every_outcome_class_is_booked_once():
    eligible = ["A", "B", "C", "D", "E", "F", "G", "H"]
    events = [
        _verdict("A", "proven", "compiled"),
        _verdict("B", "proof-failed", "compiled"),
        _verdict("C", "proof-failed", "compile-failed"),
        _verdict("D", "proven", "compile-failed"),
        _verdict("E", "proven", None),
        _verdict("F", "proven", "compiled"),
        _verdict("H", "proof-failed", "unknown"),
    ]
    out = trial.summarize_run(events, eligible, flagged=frozenset({"F"}))
    assert {k: r["state"] for k, r in out["programs"].items()} == {
        "A": "proven",
        "B": "not-proven",
        "C": "not-judged",
        "D": "not-judged",
        "E": "unknown-oracle",
        "F": "flagged",
        "G": "no-port",
        "H": "not-judged",
    }
    assert out["programs"]["H"]["reason"] == "no-report"
    assert out["programs"]["C"]["reason"] == "oracle-compile-failed"
    assert out["programs"]["C"]["cause"] == "harness"
    assert sum(out["counts"].values()) == out["eligible"] == len(eligible)


def test_a_compile_failure_is_never_a_port_failure_even_when_flagged():
    out = trial.summarize_run([_verdict("A", "proof-failed", "compile-failed")], ["A"], frozenset({"A"}))
    assert out["programs"]["A"]["state"] == "not-judged"
    assert out["counts"]["not-proven"] == 0


def test_only_the_first_verdict_counts():
    events = [_verdict("A", "proof-failed", "compiled"), _verdict("A", "proven", "compiled")]
    assert trial.summarize_run(events, ["A"])["programs"]["A"]["state"] == "not-proven"


def test_rest_wrappers_are_marked_error_path_only():
    out = trial.summarize_run([], ["HCPRESTW", "HCP1BU01"])
    assert out["programs"]["HCPRESTW"]["scope"] == "error-path-only"
    assert "scope" not in out["programs"]["HCP1BU01"]


def test_holes_are_carried_only_when_present():
    events = [{"ticket": "A", "event": "proposed", "translation": {"holes": 3}}, {"ticket": "B", "event": "proposed"}]
    out = trial.summarize_run(events, ["A", "B"])
    assert out["programs"]["A"]["holes"] == 3
    assert "holes" not in out["programs"]["B"]


def test_case_map_refuses_two_cases_for_one_program(tmp_path):
    for name in ("one", "two"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "case.json").write_text(json.dumps({"corpus": "c", "program": "P"}))
    with pytest.raises(SystemExit, match="two cases"):
        trial.case_map("c", tmp_path)


def test_case_map_selects_by_corpus(tmp_path):
    for name, corpus in (("a", "c"), ("b", "other")):
        (tmp_path / name).mkdir()
        (tmp_path / name / "case.json").write_text(json.dumps({"corpus": corpus, "program": name.upper()}))
    assert trial.case_map("c", tmp_path) == {"A": "a"}


def test_run_record_reports_both_runs_and_names_the_unproven():
    doc = (Path(__file__).resolve().parents[2] / "docs/language_status/blind1_proof_run.md").read_text(encoding="utf-8")
    assert doc.index("Run A, frozen harness") < doc.index("Run B, harness at main")
    for key in ("HCIMDB01", "HCIPDB01", "HCITDB01", "HCIVDB01", "HCMADB02", "det-then-model: not measured"):
        assert key in doc
    assert "5 of 28" in doc and "23 of 28" in doc


def _run_opts(tmp_path, backend):
    import argparse

    return argparse.Namespace(trial="trial-001", ledger=trial.LEDGER, work=tmp_path, estate_path=tmp_path, runs=["A"],
                              repo=tmp_path, backend=backend, api_key_env="GG_TEST_NO_SUCH_KEY")  # fmt: skip


def test_the_model_leg_refuses_without_a_key_before_any_work(tmp_path, monkeypatch):
    monkeypatch.delenv("GG_TEST_NO_SUCH_KEY", raising=False)
    called = []
    monkeypatch.setattr(trial.subprocess, "run", lambda *a, **k: called.append(a))
    with pytest.raises(SystemExit, match="GG_TEST_NO_SUCH_KEY"):
        trial.cmd_run(_run_opts(tmp_path, "anthropic"))
    assert not called and not list(tmp_path.iterdir())


def test_the_model_leg_refuses_a_trial_registered_for_another_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("GG_TEST_NO_SUCH_KEY", "x")
    ledger = trial.load()
    ledger["trials"][0]["system"]["backend"] = "det"
    monkeypatch.setattr(trial, "load", lambda *_a, **_k: ledger)
    with pytest.raises(SystemExit, match="registered with backend"):
        trial.cmd_run(_run_opts(tmp_path, "anthropic"))


def test_run_defaults_to_the_det_backend_and_names_the_model_leg():
    doc = (Path(__file__).resolve().parents[2] / "docs/language_status/blind1_proof_run.md").read_text(encoding="utf-8")
    assert "--backend anthropic" in doc and "run_summary_anthropic.json" in doc
    src = (Path(trial.__file__)).read_text(encoding="utf-8")
    assert 'choices=("det", "anthropic"), default="det"' in src
