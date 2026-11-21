"""#8599: a baseline proof in a `--work` dir is kept for the same port, case inputs and engine, and proven again for
anything else (a moved port byte, a moved case input, an unproven or missing report)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import mutation as mu  # noqa: E402


@pytest.fixture
def stub_inputs(monkeypatch):
    """evidence / equivalence_cache stand-ins: the case digest and the engine hash are set per test."""
    state = {"digest": "d1", "engine": "e1"}
    ev = ModuleType("evidence")
    ev.equivalence_target = lambda case: case
    ev.compute_inputs = lambda t: {"digest": state["digest"]}
    cache = ModuleType("equivalence_cache")
    cache.engine_hash = lambda: state["engine"]
    monkeypatch.setitem(sys.modules, "evidence", ev)
    monkeypatch.setitem(sys.modules, "equivalence_cache", cache)
    return state


@pytest.fixture
def prover(monkeypatch):
    """A `mu.prove` that writes report.json into its work dir and counts its calls."""
    calls = SimpleNamespace(n=0, proven=True)

    def prove(case, port, work, timeout, extra=(), env=None):
        calls.n += 1
        work.mkdir(parents=True, exist_ok=True)
        (work / "report.json").write_text(json.dumps({"proven": calls.proven}), encoding="utf-8")
        return {"verdict": "proven" if calls.proven else "refuted", "seconds": 17, "killed_by": [], "report": {}}

    monkeypatch.setattr(mu, "prove", prove)
    return calls


def _port(tmp_path: Path, text: str = "class A {}") -> Path:
    port = tmp_path / "port"
    port.mkdir(exist_ok=True)
    (port / "A.java").write_text(text, encoding="utf-8")
    return port


def test_the_same_port_and_inputs_keep_the_baseline(tmp_path, stub_inputs, prover):
    port, work = _port(tmp_path), tmp_path / "w" / "baseline"
    first = mu.baseline_proof("c", port, True, work, ())
    again = mu.baseline_proof("c", port, True, work, ())
    assert prover.n == 1
    assert again["verdict"] == "proven" and again["seconds"] == first["seconds"] == 17


@pytest.mark.parametrize("moved", ["port", "digest", "engine", "case_file"])
def test_a_moved_input_proves_the_baseline_again(tmp_path, stub_inputs, prover, moved):
    port, work = _port(tmp_path), tmp_path / "w" / "baseline"
    case_file = tmp_path / "case.json"
    case_file.write_text("{}", encoding="utf-8")
    arg = ("--case-file", str(case_file))
    mu.baseline_proof("c", port, True, work, arg)
    if moved == "port":
        _port(tmp_path, "class A { int x; }")
    elif moved == "case_file":
        case_file.write_text('{"x": 1}', encoding="utf-8")
    else:
        stub_inputs[moved] = "changed"
    mu.baseline_proof("c", port, True, work, arg)
    assert prover.n == 2


def test_a_refuted_baseline_is_never_kept(tmp_path, stub_inputs, prover):
    port, work = _port(tmp_path), tmp_path / "w" / "baseline"
    prover.proven = False
    assert mu.baseline_proof("c", port, True, work, ())["verdict"] == "refuted"
    assert not (tmp_path / "w" / f"baseline.{mu.BASELINE_KEY}").exists()
    prover.proven = True
    mu.baseline_proof("c", port, True, work, ())
    assert prover.n == 2


def test_a_missing_report_or_unreadable_inputs_prove_again(tmp_path, stub_inputs, prover, monkeypatch):
    port, work = _port(tmp_path), tmp_path / "w" / "baseline"
    mu.baseline_proof("c", port, True, work, ())
    (work / "report.json").unlink()
    mu.baseline_proof("c", port, True, work, ())
    assert prover.n == 2
    monkeypatch.setattr(mu, "baseline_key", lambda *a: None)  # inputs that cannot be read: never kept
    mu.baseline_proof("c", port, True, work, ())
    mu.baseline_proof("c", port, True, work, ())
    assert prover.n == 4
