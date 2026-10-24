"""#4767: the default cics_crucible.py run lays a case's committed deterministic port (det-ports/) when the case has no
model port, so a det-port-only case is measured on java-ported / java-facade without a --ports argument."""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import cics_crucible as runner  # noqa: E402
import cics_crucible_det as det  # noqa: E402


def test_every_committed_det_port_is_a_registered_case():
    on_disk = {d.name for d in runner.DET_PORTS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")}
    assert on_disk == set(det.PROGRAMS)


def test_the_default_run_reads_the_det_ports_beside_the_model_ports():
    assert runner.DET_PORTS_DIR == det.DET_PORTS
    assert runner.PortOptions().det_root == runner.DET_PORTS_DIR


def test_a_det_port_only_case_gets_its_overlays_with_the_runtime(tmp_path):
    out = runner.det_port_overlays("gt-web-parse-url", tmp_path)
    assert set(out) == {"GTWPARS"}
    assert (out["GTWPARS"] / "service" / "GtwparsService.java").is_file()
    assert (out["GTWPARS"] / "cobolrt" / "Cobol.java").is_file()


def test_a_case_with_a_model_port_is_not_a_det_port_only_case():
    model = {d.name for d in runner.PORTS_DIR.iterdir() if d.is_dir()}
    both = model & set(det.PROGRAMS)
    # the model port wins there; the fallback is for the cases that have none
    assert both == {"pc-wizard"}
