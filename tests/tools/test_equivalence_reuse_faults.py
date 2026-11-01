"""#4047: the COBOL fault log (work/FAULTS) is appended to by the instrument; --reuse must not carry a doubled one."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence
import equivalence_common as common

FIRED = "DALYTRAN OPEN 1 35\n"


@pytest.fixture(autouse=True)
def _no_reuse(monkeypatch):
    monkeypatch.setattr(common, "_REUSE", None)


def _work(tmp_path: Path, log: str) -> Path:
    work = tmp_path / "cobol"
    work.mkdir(parents=True)
    (work / "run.sh").write_text("true\n")
    (work / "FAULTS").write_text(log)
    return work


@pytest.mark.parametrize("log", [FIRED, FIRED * 2, ""])
def test_a_fault_run_starts_with_no_log(tmp_path, log):
    work = _work(tmp_path, log)
    equivalence.fresh_fault_log(work, {"name": "open-dalytran"})
    assert not (work / "FAULTS").exists()


def test_the_main_run_has_no_fault_log_to_clear(tmp_path):
    work = _work(tmp_path, FIRED)
    equivalence.fresh_fault_log(work, None)
    assert (work / "FAULTS").read_text() == FIRED


def test_a_reused_step_keeps_the_earlier_log(tmp_path):
    earlier = tmp_path / "earlier"
    _work(earlier, FIRED)
    (earlier / "report.json").write_text("{}")
    mine = tmp_path / "mine"
    work = _work(mine, FIRED)
    common.reuse(mine, earlier)
    equivalence.fresh_fault_log(work, {"name": "open-dalytran"})
    assert (work / "FAULTS").read_text() == FIRED


def test_a_second_pass_over_the_work_dir_logs_once(tmp_path):
    work = _work(tmp_path, "")
    for _ in range(2):  # the instrument appends, as ggfault.c does
        equivalence.fresh_fault_log(work, {"name": "open-dalytran"})
        with (work / "FAULTS").open("a") as f:
            f.write(FIRED)
    assert (work / "FAULTS").read_text() == FIRED


def test_the_java_driver_clears_a_scenarios_fired_fault_log_before_running_it():
    """The Java side appends to out/<scenario>.faults too: a --reuse copy of the baseline's out dir logged every
    fault twice, so a mutant looked killed by "faults fired differ" (#5862)."""
    src = (Path(__file__).resolve().parent / "equivalence_cics.py").read_text(encoding="utf-8")
    clear = src.index('Files.deleteIfExists(out.resolve(sc.get("name").asText() + ".faults"))')
    assert clear < src.index("task.withFaults(faults,")
    assert clear < src.index("dliReset(in.resolve")
