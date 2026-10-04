"""#4188: a port proven with the programs its task LINKs to runs them as Java -- the port's own service, a committed
model port, or (tested end to end by the harness) a deterministic translation -- and names each one's origin."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_java as ej  # noqa: E402


def _case(cases: Path, name: str, program: str, port_service: str | None = None) -> None:
    (cases / name).mkdir(parents=True)
    (cases / name / "case.json").write_text(json.dumps({"name": name, "program": program}), encoding="utf-8")
    if port_service:
        svc = cases / name / "port" / "service"
        svc.mkdir(parents=True)
        (svc / port_service).write_text("// model port\n", encoding="utf-8")


def test_a_linked_program_with_a_committed_model_port_runs_that_port(tmp_path, monkeypatch):
    cases = tmp_path / "cases"
    _case(cases, "estate-callee", "CALLEE", "CalleeService.java")
    monkeypatch.setattr(ej, "CASES", cases)
    case = {"programs": [{"program": "CALLEE", "program_source": "src/CALLEE.cbl"}]}
    files, origins = ej.linked_programs(case, tmp_path, tmp_path, {}, tmp_path / "work")
    assert files == {"service/CalleeService.java": cases / "estate-callee/port/service/CalleeService.java"}
    assert origins == {"CALLEE": "committed model port (estate-callee)"}


def test_a_linked_program_the_port_already_carries_is_the_ports_own(tmp_path, monkeypatch):
    monkeypatch.setattr(ej, "CASES", tmp_path / "cases")
    case = {"programs": [{"program": "CALLEE", "program_source": "src/CALLEE.cbl"}]}
    files, origins = ej.linked_programs(case, tmp_path, tmp_path, {"service/CalleeService.java": tmp_path / "x"},
                                        tmp_path / "work")  # fmt: skip
    assert files == {} and origins == {"CALLEE": "the port under proof"}
