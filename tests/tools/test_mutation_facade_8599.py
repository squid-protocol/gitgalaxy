"""#8599: the in-process CICS mutant path judges the java-facade side too, as the baseline proof does (run_case
facades): a mutant in facade-only code (handleLink, lastLinkBytes) survived in process where a separate run killed it
(ABNDPROC 661ba858a8)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import equivalence_cics as ec  # noqa: E402
import mutation as mu  # noqa: E402


def _ctx(tmp_path: Path, facade: bool) -> mu._DirectContext:
    return mu._DirectContext(
        kind="cics", case={"program": "P", "scenarios": [{"name": "s1"}, {"name": "s2"}]}, corpus=tmp_path,
        project=tmp_path, base_classes=tmp_path, env_default={}, base_jvm_flags="-Dx=1", shell={}, inputs=tmp_path,
        cics_in=tmp_path / "in", cics_cobol_work=tmp_path / "cobol", cics_cobol={"s1": {}, "s2": {}},
        cics_facade=facade,
    )  # fmt: skip


def _run(tmp_path: Path, monkeypatch, facade: bool, judged: dict | None = None, codes: tuple[int, ...] = (0, 0),
         runtask_ok: bool = True):  # fmt: skip
    runs: list[tuple[str, str | None]] = []

    def run(argline, timeout, epoch=None, cp=None):
        runs.append((argline, epoch))
        return SimpleNamespace(returncode=codes[len(runs) - 1], stderr="", stdout="boom")

    session = SimpleNamespace(run=run)
    worker = SimpleNamespace(swap_and_restore=lambda c: [], rollback=lambda rb: None, reset=lambda: None,
                             _ensure=lambda: session, cp="cp", classes_dir=tmp_path / "w" / "classes")  # fmt: skip
    seen: dict = {}

    def judge_facade(case, corpus, files, cobol, fc, refused, cobol_work, quiet=False):
        seen.update(facade=fc, quiet=quiet, refused=refused)
        return judged

    monkeypatch.setattr(ec, "_java_events", lambda *a: {})
    monkeypatch.setattr(ec, "evaluate_cics_outputs", lambda *a, **k: (runtask_ok, {}))
    monkeypatch.setattr(ec, "judge_facade", judge_facade)
    mw = tmp_path / "mw"
    (mw / "classes").mkdir(parents=True)
    m = mu.Mutant(id="m1", file="service/P.java", line=1, op="COR", before="a", after="b")
    res = _ctx(tmp_path, facade).run_mutant(worker, m, mw, 60.0, False, {})
    return res, runs, seen


def test_no_facade_side_when_the_baseline_had_none(tmp_path, monkeypatch):
    res, runs, _ = _run(tmp_path, monkeypatch, facade=False)
    assert res["verdict"] == "survived" and len(runs) == 1
    assert "facades" not in runs[0][0]


def test_a_mutant_the_facade_side_sees_is_killed(tmp_path, monkeypatch):
    judged = {"proven": False, "outputs": {"s1": {"pass": True}, "s2": {"pass": False}}}
    res, runs, seen = _run(tmp_path, monkeypatch, facade=True, judged=judged)
    assert res["verdict"] == "killed" and res["killed_by"] == ["s2 [java-facade]"]
    assert len(runs) == 2
    assert "-Dequivalence.facades=true" in runs[1][0] and "-Dx=1" in runs[1][0]
    assert runs[0][1] == "m1" and runs[1][1] == "m1:facade"  # its own epoch: a fresh class loader
    out = tmp_path / "mw" / "proof" / "facade" / "out"
    assert f"-Dequivalence.out={out}" in runs[1][0]
    assert seen["quiet"] is True and seen["refused"] == {} and seen["facade"]["out"] == out
    assert set(seen["facade"]["entries"]) == {"s1", "s2"}


def test_a_mutant_both_sides_pass_survives(tmp_path, monkeypatch):
    res, runs, _ = _run(tmp_path, monkeypatch, facade=True, judged={"proven": True, "outputs": {}})
    assert res["verdict"] == "survived" and len(runs) == 2


def test_a_facade_run_that_fails_is_judged_as_the_baseline_judges_it(tmp_path, monkeypatch):
    res, _, seen = _run(tmp_path, monkeypatch, facade=True, codes=(0, 1),
                        judged={"proven": False, "error": "boom", "outputs": {}})  # fmt: skip
    assert seen["facade"] == {"error": "boom"}
    assert res["verdict"] == "killed" and res["killed_by"] == ["java-facade"]


@pytest.mark.parametrize(("code", "want"), [(124, "timeout")])
def test_a_facade_run_past_the_limit_is_a_timeout(tmp_path, monkeypatch, code, want):
    res, _, _ = _run(tmp_path, monkeypatch, facade=True, codes=(0, code))
    assert res["verdict"] == want


def test_a_runtask_kill_skips_the_facade_side(tmp_path, monkeypatch):
    monkeypatch.setattr(mu, "killers", lambda r: ["s1"])
    res, runs, _ = _run(tmp_path, monkeypatch, facade=True, runtask_ok=False)
    assert res["verdict"] == "killed" and res["killed_by"] == ["s1"] and len(runs) == 1


def test_killers_names_the_facade_scenarios_of_a_separate_run():
    report = {"kind": "cics", "outputs": {"s1": {"equal": 2, "records": 2}},
              "facade": {"proven": False, "outputs": {"s1": {"pass": False}}}}  # fmt: skip
    assert mu.killers(report) == ["s1 [java-facade]"]
    assert mu.killers({**report, "facade": {"proven": True, "outputs": {}}}) == []


def test_judge_facade_quiet_prints_nothing(tmp_path, capsys):
    ec.judge_facade({"program": "P", "scenarios": []}, tmp_path, [], {}, {"error": "x\ny"}, {}, tmp_path, quiet=True)
    assert capsys.readouterr().out == ""
    ec.judge_facade({"program": "P", "scenarios": []}, tmp_path, [], {}, {"error": "x\ny"}, {}, tmp_path)
    assert "the run failed -- x" in capsys.readouterr().out
