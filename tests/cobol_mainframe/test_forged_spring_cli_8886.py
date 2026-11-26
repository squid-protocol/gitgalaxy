"""#8886 slice 23: the one-command Spring mode (`equivalence_forged_spring.py --spec ... --report|--run-chain`).

The Spring run itself is covered by test_forged_spring_nightly_8886.py; here `scan_and_run` is stubbed, so this checks
the command's wiring: the chain's exported directories reach the run, the exit code follows `differs`, and a missing
JDK is exit 2, not a pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "tools"))
import equivalence_forged_spring as efs  # noqa: E402

SPEC = REPO / "tests/equivalence/jobs/carddemo-nightly.forged.json"


def _row(status):
    md = {"status": status, "issues": []}
    return {"case": "s1", "job": "J", "jcl_steps": ["A"], "modes": {"strict": md, "skip": md}}


def _ds(status):
    md = {"status": status, "issue": None}
    return {"dataset": "D", "job": "J", "case": "s1", "modes": {"strict": md, "skip": md}}


def _run(tmp_path, monkeypatch, res, capsys, **report):
    seen = {}

    def fake(spec, case, rep, corpus, rcs, chain=None, outputs=None):
        seen.update(chain=chain, outputs=outputs)
        return res

    monkeypatch.setattr(efs, "scan_and_run", fake)
    rp = tmp_path / "report.json"
    rp.write_text(json.dumps({"case": "carddemo-nightly", "steps": [], **report}), encoding="utf-8")
    out_json = tmp_path / "out.json"
    code = efs.main(["--spec", str(SPEC), "--report", str(rp), "--corpus", str(tmp_path), "--json", str(out_json)])
    return code, seen, capsys.readouterr().out, out_json


def test_all_equal_exits_zero_and_hands_the_chains_directories_to_the_run(tmp_path, monkeypatch, capsys):
    res = {"rows": [_row("equal")], "datasets": [_ds("equal")], "jobs": {}}
    code, seen, out, out_json = _run(
        tmp_path, monkeypatch, res, capsys, generations_dir=str(tmp_path / "g"), outputs_dir=str(tmp_path / "o")
    )
    assert code == 0
    assert seen == {"chain": tmp_path / "g", "outputs": tmp_path / "o"}
    assert "0 step/dataset results differ" in out
    assert json.loads(out_json.read_text())["rows"][0]["case"] == "s1"


def test_a_differing_dataset_or_step_exits_one_and_is_named(tmp_path, monkeypatch, capsys):
    res = {"rows": [_row("equal")], "datasets": [_ds("differs")], "jobs": {}}
    code, seen, out, _ = _run(tmp_path, monkeypatch, res, capsys)
    assert code == 1
    assert seen == {"chain": None, "outputs": None}
    assert "dataset D [J] strict" in out
    res = {"rows": [_row("differs")], "datasets": [], "jobs": {}}
    assert _run(tmp_path, monkeypatch, res, capsys)[0] == 1


def test_no_spring_run_is_exit_two_not_a_pass(tmp_path, monkeypatch, capsys):
    assert _run(tmp_path, monkeypatch, None, capsys)[0] == 2


def test_run_chain_keeps_the_chain_and_fails_without_a_report(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(efs.subprocess, "run", lambda cmd, check: calls.append(cmd))
    with pytest.raises(SystemExit, match="no report.json"):
        efs.run_chain("carddemo-nightly", tmp_path)
    assert calls[0][-3:] == ["carddemo-nightly", "--keep", str(tmp_path)]
    (tmp_path / "report.json").write_text("{}", encoding="utf-8")
    assert efs.run_chain("carddemo-nightly", tmp_path) == tmp_path / "report.json"
