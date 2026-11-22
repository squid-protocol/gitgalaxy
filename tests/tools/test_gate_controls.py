"""#7155: every gate is listed, a named failure proof exists, and the first controls prove gates can go red."""

import functools
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent))
import gate_controls as gc
import mypy_audit
import ruff_audit

REPO = TOOLS.parents[1]
WORKFLOWS = REPO / ".github" / "workflows"


def _triggers(path: Path) -> set[str]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    on = doc.get(True) or doc.get("on") or {}  # YAML reads a bare `on:` key as True
    return set(on if isinstance(on, (dict, list)) else [on])


@functools.lru_cache(maxsize=1)  # called once per gate: parsing every workflow each time took 25 s on CI
def _pr_workflows() -> frozenset[str]:
    return frozenset(p.name for p in WORKFLOWS.glob("*.yml") if {"pull_request", "pull_request_target"} & _triggers(p))


def test_every_workflow_is_a_listed_gate_or_says_why_not():
    """Not only the PR ones: a nightly or release check that can fail is a gate too (#7155)."""
    listed = {g.workflow for g in gc.GATES} | set(gc.NOT_GATES)
    every = {p.name for p in WORKFLOWS.glob("*.yml")}
    assert not every - listed, "add it to gate_controls.GATES, or NOT_GATES with the reason"
    assert not {w for w in listed if not (WORKFLOWS / w).exists()}, "a listed workflow is gone"
    assert not {g.workflow for g in gc.GATES} & set(gc.NOT_GATES), "a workflow is both a gate and not one"


def test_a_named_job_exists_and_the_trigger_matches_the_workflow():
    docs: dict[str, dict] = {}  # parse each workflow once: many gates share one (25 s on CI otherwise)
    for g in gc.GATES:
        assert g.trigger in {"pr", "main", "nightly", "release"}, g.name
        if g.workflow not in docs:
            docs[g.workflow] = yaml.safe_load((WORKFLOWS / g.workflow).read_text(encoding="utf-8"))
        doc = docs[g.workflow]
        assert not g.job or g.job in doc["jobs"], f"{g.name}: job {g.job} is not in {g.workflow}"
        if g.trigger == "pr":
            assert g.workflow in _pr_workflows(), f"{g.name}: marked pr but {g.workflow} has no PR trigger"
        else:
            # an off-PR gate may share a workflow with a PR gate only through its own job
            assert g.job or g.workflow not in _pr_workflows(), f"{g.name}: {g.workflow} runs on PRs"


def test_every_required_check_is_listed():
    import shepherd_gh

    names = {g.name.split(" (")[0] for g in gc.GATES if g.required}
    assert set(shepherd_gh.REQUIRED_CHECKS) <= names


def test_every_named_proof_is_a_real_test():
    for g in gc.GATES:
        if g.proof:
            path, _, name = g.proof.partition("::")
            assert f"def {name}(" in (REPO / path).read_text(encoding="utf-8"), f"{g.name}: {g.proof} is gone"


def test_every_gate_says_what_it_claims_to_catch():
    """A placeholder claim is a gate nobody has read: every entry names what it catches (#7155)."""
    placeholders = ("not audited", "todo", "tbd", "unknown")
    bad = [g.name for g in gc.GATES if len(g.claims.split()) < 3 or any(w in g.claims.lower() for w in placeholders)]
    assert not bad, f"write a real claim for: {bad}"


def test_a_notice_cannot_also_claim_a_proof():
    assert not [g.name for g in gc.GATES if g.notice and g.proof]


def test_the_unproven_count_only_goes_down():
    n = len(gc.unproven())
    assert n <= gc.MAX_UNPROVEN, f"{n} gates have no failure proof, the limit is {gc.MAX_UNPROVEN}: add a control"
    assert n == gc.MAX_UNPROVEN, f"good news: {n} unproven now, so lower MAX_UNPROVEN to {n}"


def _audit_at(tmp_path, monkeypatch, module, baseline=None):
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline or {}), encoding="utf-8")
    monkeypatch.setattr(module, "BASELINE_PATH", path)


@pytest.mark.skipif(shutil.which("ruff") is None, reason="needs ruff")
def test_ruff_audit_fails_on_a_planted_finding_with_real_ruff(tmp_path, monkeypatch, capsys):
    """The negative control: real ruff over a planted file, so a broken runner or parser can't pass unnoticed."""
    (tmp_path / "planted.py").write_text("import os\n", encoding="utf-8")
    real = ruff_audit.run_ruff_findings
    _audit_at(tmp_path, monkeypatch, ruff_audit)
    monkeypatch.setattr(ruff_audit, "run_ruff_findings", lambda: real(tmp_path, tmp_path))
    monkeypatch.setattr(ruff_audit, "run_ruff_format_check", lambda: True)
    monkeypatch.setattr(ruff_audit, "run_syntax_check", lambda: [])  # #7667: no real ruff
    assert ruff_audit.run_ci_check() == 1
    assert "F401" in capsys.readouterr().out


def test_ruff_audit_fails_on_format_alone(tmp_path, monkeypatch, capsys):
    _audit_at(tmp_path, monkeypatch, ruff_audit)
    monkeypatch.setattr(ruff_audit, "run_ruff_findings", lambda: {})
    monkeypatch.setattr(ruff_audit, "run_ruff_format_check", lambda: False)
    monkeypatch.setattr(ruff_audit, "run_syntax_check", lambda: [])  # #7667: no real ruff
    assert ruff_audit.run_ci_check() == 1  # no lint findings at all: format is zero-tolerance on its own
    assert "ruff format" in capsys.readouterr().out


def test_mypy_audit_fails_on_a_new_error(tmp_path, monkeypatch, capsys):
    (tmp_path / "planted.py").write_text("x: int = 'a'\n", encoding="utf-8")
    stdout = "planted.py:1: error: Incompatible types in assignment  [assignment]\n"
    found = mypy_audit.parse_mypy_output(stdout, tmp_path)
    assert found, "the parser lost a real mypy line, so the audit would pass on anything"
    _audit_at(tmp_path, monkeypatch, mypy_audit)
    monkeypatch.setattr(mypy_audit, "run_mypy_findings", lambda: found)
    assert mypy_audit.run_ci_check() == 1
    assert "1 NEW type error" in capsys.readouterr().out
    _audit_at(tmp_path, monkeypatch, mypy_audit, {k: "known" for k in found})
    assert mypy_audit.run_ci_check() == 0  # the same error, baselined, passes: the ratchet, not a blanket failure


def test_ast_accuracy_audit_fails_on_a_regression_drift_or_missing_baseline(tmp_path, monkeypatch, capsys):
    """The negative control: the real --ci path over the committed baseline, with one metric made worse."""
    import ast_accuracy_audit as aaa

    base = json.loads(aaa.BASELINE_PATH.read_text(encoding="utf-8"))
    monkeypatch.setattr(aaa, "measure", lambda verbose=False: dict(base))
    assert aaa.run_ci_check() == 0  # the committed numbers pass: the gate is not a blanket failure
    monkeypatch.setattr(aaa, "measure", lambda verbose=False: {**base, "found_functions": base["found_functions"] - 1})
    assert aaa.run_ci_check() == 1
    assert "found_functions" in capsys.readouterr().out
    monkeypatch.setattr(aaa, "measure", lambda verbose=False: {**base, "real_functions": base["real_functions"] + 1})
    assert aaa.run_ci_check() == 1  # ground truth drifted from the pinned corpus
    monkeypatch.setattr(aaa, "measure", lambda verbose=False: dict(base))
    monkeypatch.setattr(aaa, "BASELINE_PATH", tmp_path / "absent.json")
    assert aaa.run_ci_check() == 1  # no baseline: fails closed


def test_detection_accuracy_audit_fails_on_a_regression(monkeypatch, capsys):
    import detection_accuracy_audit as daa

    base = json.loads(daa.BASELINE_PATH.read_text(encoding="utf-8"))
    monkeypatch.setattr(sys, "argv", ["detection_accuracy_audit.py", "--ci"])
    monkeypatch.setattr(daa, "measure", lambda: dict(base))
    assert daa.main() == 0
    worse = {**base, "determinable_accuracy": base["determinable_accuracy"] - 0.05}
    monkeypatch.setattr(daa, "measure", lambda: worse)
    assert daa.main() == 1
    assert "determinable_accuracy" in capsys.readouterr().out
    monkeypatch.setattr(daa, "measure", lambda: {**base, "tier_5_conflicts": base["tier_5_conflicts"] + 1})
    assert daa.main() == 1


def test_call_graph_accuracy_audit_fails_on_a_regression(tmp_path, monkeypatch, capsys):
    import call_graph_accuracy as cga

    (tmp_path / "data").mkdir()
    monkeypatch.setattr(cga, "CRUCIBLE", tmp_path)
    monkeypatch.setattr(cga, "render", lambda results: "")
    base = json.loads(cga.BASELINE.read_text(encoding="utf-8"))
    monkeypatch.setattr(cga, "measure", lambda *a, **k: json.loads(json.dumps(base)))
    assert cga.main(["--ci"]) == 0
    lang = sorted(base)[0]
    worse = json.loads(json.dumps(base))
    worse[lang]["precision_pct"] = base[lang]["precision_pct"] - cga.TOLERANCE_PP - 1
    monkeypatch.setattr(cga, "measure", lambda *a, **k: worse)
    assert cga.main(["--ci"]) == 1
    assert lang in capsys.readouterr().out
    dropped = {k: v for k, v in base.items() if k != lang}
    monkeypatch.setattr(cga, "measure", lambda *a, **k: dropped)
    assert cga.main(["--ci"]) == 1  # a language that is no longer measured is a regression too
