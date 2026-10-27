"""#5005 slice 2: the Java runner hands a `RETURN TRANSID CHANNEL` to the next terminal task. A channel program has no
task facade, so the proof is the deterministic port on the java-ported side; dropping `t.withChannel(carried)` from the
generated test must fail the carry and modify scenarios."""

import os
import shutil
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as compare  # noqa: E402
import cics_crucible_det as det  # noqa: E402

CASE = "pc-return-channel"
SERVICE = det.DET_PORTS / CASE / "PCRC" / "overlay" / "service"
CARRY = "t.withChannel(carried);"


def test_the_committed_det_ports_cover_each_program_and_return_the_channel():
    assert det.PROGRAMS[CASE][1] == ("PCRCA", "PCRCB", "PCRCL")
    services = sorted(p.name for p in SERVICE.glob("*Service.java"))
    assert services == ["PcrcaService.java", "PcrcbService.java", "PcrclService.java"]
    assert "task.returnChannel(" in (SERVICE / "PcrcaService.java").read_text(encoding="utf-8")


def test_the_ports_dir_adds_the_runtime_and_keeps_the_services(tmp_path):
    out = det.ports_dir(CASE, tmp_path)
    overlay = out / "PCRC" / "overlay"
    assert (overlay / "service" / "PcrcaService.java").is_file() and (overlay / "cobolrt" / "Cobol.java").is_file()
    assert runner.case_overlays(out) == {"PCRC": overlay}


def test_the_generated_test_carries_the_channel_only_to_the_named_transaction():
    src = runner._JAVA_TEST
    assert "pendingChannel = abended || transid == null ? null : outChannel;" in src
    assert "inChannel = transid.equals(pending) ? pendingChannel : null;" in src
    assert "outChannel = t.returnedChannel();" in src
    assert CARRY in src


def test_both_legs_declare_and_compare_the_channel():
    assert "channel" in runner.JAVA_CAPS.events["RETURN"]
    assert "channel" in runner.COBOL_CAPS.events["RETURN"]
    assert "channel" in compare.EVENT_KEYS["RETURN"]


def _ret(**kw):
    raw = {"tasks": [{"transid": "PCRA", "program": "PCRCA", "end": "return", "events": [dict(event="RETURN", **kw)]}]}
    return runner.java_actual(None, raw, Path("."))["tasks"][0]["events"][0]


def test_a_returned_channel_is_logged_and_a_failed_return_is_not_immediate():
    assert _ret(level=1, transid="PCRB", channel="CH1")["channel"] == "CH1"
    failed = _ret(level=2, transid="PCRB", channel="CH1", resp=16, resp2=2)
    assert failed["channel"] == "CH1" and "immediate" not in failed
    immediate = _ret(level=1, transid="PCRB", resp=16, resp2=2)
    assert immediate["immediate"] is True and "channel" not in immediate


E2E = os.environ.get("EQUIVALENCE_E2E") == "1" and bool(os.environ.get(runner.PATH_ENV))


@pytest.mark.slow(reason="two Maven builds of the generated project (the det port, then the no-carry mutant)")
@pytest.mark.e2e
@pytest.mark.skipif(not E2E, reason="needs EQUIVALENCE_E2E=1, a JDK + Maven and a cics-crucible checkout")
def test_the_crucible_proves_the_carry_and_kills_its_removal(tmp_path, monkeypatch):
    crucible = Path(os.environ[runner.PATH_ENV])
    offline = os.environ.get("MAVEN_OFFLINE") == "1"

    def ported(name):
        res = runner.measure(crucible, {CASE}, {"java-ported"}, tmp_path / name, offline,
                             runner.PortOptions(ports=det.ports_dir(CASE, tmp_path / f"ports-{name}")))  # fmt: skip
        return {c["scenario"]: c["status"] for c in res["cells"].values() if c["side"] == "java-ported"}

    base = ported("base")
    assert set(base) == {"carry", "modify", "link-level2"} and set(base.values()) == {"pass"}
    monkeypatch.setattr(runner, "_JAVA_TEST", runner._JAVA_TEST.replace(CARRY, ""))
    mutant = ported("mutant")
    assert mutant["carry"] != "pass" and mutant["modify"] != "pass"
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_the_stub_logs_a_returned_channel(tmp_path):
    (tmp_path / "events.txt").write_text(
        "001 RETURN pgm=PCRCA level=1 transid=PC62 len=0 channel=PCCHAN\n"
        "002 RETURN pgm=PCRCL level=2 transid=PC62 channel=PCCHAN resp=16 resp2=2\n"
        "003 RETURN pgm=PCRCB level=1 transid= len=0\n"
    )
    ok, failed, plain = runner._cobol_events(tmp_path, "PCRCA")
    assert ok["channel"] == "PCCHAN" and ok["transid"] == "PC62"
    assert failed["channel"] == "PCCHAN" and failed["resp"] == "INVREQ" and failed["resp2"] == 2
    assert "immediate" not in failed and "channel" not in plain
