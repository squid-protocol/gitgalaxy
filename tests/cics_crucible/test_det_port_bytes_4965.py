"""#4965: a committed crucible scenario that RETURNs TRANSID with a COMMAREA through the byte-carrying
handleTransaction. The model ports RETURN DTO-only (`returnedBytes()` null), so only the deterministic port of PCWIZ
makes the java-facade side compare real `lastAnswerBytes()`; deleting the facade's assignment must fail the scenarios."""

import os
import re
import shutil
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import cics_crucible as runner  # noqa: E402
import cics_crucible_det as det  # noqa: E402

SERVICE = det.DET_PORTS / "pc-wizard" / "PCWIZ" / "overlay" / "service"
ASSIGN = "lastAnswerBytes = task.returnedBytes();"


def test_the_committed_det_port_returns_its_commarea_through_the_byte_form():
    text = (SERVICE / "PcwizService.java").read_text(encoding="utf-8")
    assert ASSIGN in text
    assert re.search(r"task\.returnTransid\(\"PC02\"[^;]*\.bytes\);", text)  # the byte-carrying RETURN (#4817)
    assert ASSIGN in (SERVICE / "PcconfService.java").read_text(encoding="utf-8")


def test_the_ports_dir_adds_the_runtime_and_keeps_the_services(tmp_path):
    out = det.ports_dir("pc-wizard", tmp_path)
    overlay = out / "PCWIZ" / "overlay"
    assert (overlay / "service" / "PcwizService.java").is_file() and (overlay / "cobolrt" / "Cobol.java").is_file()
    assert runner.case_overlays(out) == {"PCWIZ": overlay}


def test_the_det_ports_stay_out_of_the_model_port_records():
    assert not (det.DET_PORTS / "pc-wizard" / "PCWIZ" / "provenance.json").exists()
    assert det.DET_PORTS.parent / "ports" != det.DET_PORTS


E2E = os.environ.get("EQUIVALENCE_E2E") == "1" and bool(os.environ.get(runner.PATH_ENV))


@pytest.mark.slow(reason="two Maven builds of the generated project (the det port, then its mutant)")
@pytest.mark.e2e
@pytest.mark.skipif(not E2E, reason="needs EQUIVALENCE_E2E=1, a JDK + Maven and a cics-crucible checkout")
def test_the_crucible_proves_the_byte_overload_and_kills_its_assignment(tmp_path):
    crucible = Path(os.environ[runner.PATH_ENV])
    offline = os.environ.get("MAVEN_OFFLINE") == "1"

    def facade(name, root):
        res = runner.measure(crucible, {"pc-wizard"}, {"java-facade"}, tmp_path / name, offline,
                             runner.PortOptions(ports=det.ports_dir("pc-wizard", tmp_path / f"ports-{name}", root)))  # fmt: skip
        return {c["scenario"]: c for c in res["cells"].values() if c["side"] == "java-facade"}

    base = facade("base", det.DET_PORTS)
    assert base and {c["status"] for c in base.values()} == {"pass"}
    mutant = tmp_path / "mutant"
    shutil.copytree(det.DET_PORTS, mutant)
    svc = mutant / "pc-wizard" / "PCWIZ" / "overlay" / "service" / "PcwizService.java"
    svc.write_text(svc.read_text(encoding="utf-8").replace(ASSIGN, ""), encoding="utf-8")
    killed = facade("mutant", mutant)
    assert {c["status"] for c in killed.values()} == {"fail"}
    assert all("is not the bytes its RETURN passes on" in c["reason"] for c in killed.values())
