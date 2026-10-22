"""#5856 slice 3: the CardDemo CBSTM03A equivalence case (batch, a CALLed COBOL subprogram, the TIOT walk).

Pure parts (no docker): the case's shape, the harness's `subprograms` and `mvs_step` wiring, and the copybook tab
stops (CUSTREC.cpy's tab-indented lines run past column 72 at GnuCOBOL's stops of 8). The proof itself is
`det_port.py run carddemo-cbstm03a` (gated here on EQUIVALENCE_E2E).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "tools"))

import equivalence_common  # noqa: E402

CASE = REPO / "tests" / "equivalence" / "carddemo-cbstm03a" / "case.json"


def _case() -> dict:
    return json.loads(CASE.read_text(encoding="utf-8"))


def test_the_case_states_the_step_and_the_called_program():
    case = _case()
    assert case["program"] == "CBSTM03A"
    assert case["subprograms"] == ["app/cbl/CBSTM03B.CBL"]
    job, step, _proc, dds = case["mvs_step"].split(";")
    assert (job, step) == ("CREASTMT", "STEP040")
    stated = {d.split(":")[0] for d in dds.split(",")}
    assert {"TRNXFILE", "XREFFILE", "CUSTFILE", "ACCTFILE", "STMTFILE", "HTMLFILE"} <= stated


def test_only_the_statement_outputs_are_compared():
    compared = {dd for dd, spec in _case()["datasets"].items() if spec.get("compare")}
    assert compared == {"STMTFILE", "HTMLFILE"}


def test_the_harness_wires_the_subprogram_and_the_step():
    run = (REPO / "tests" / "tools" / "equivalence.py").read_text(encoding="utf-8")
    java = (REPO / "tests" / "tools" / "equivalence_java.py").read_text(encoding="utf-8")
    assert 'case.get("subprograms", [])' in run and "SUB{Path(rel).stem.upper()}.cbl" in run
    assert "-Dgitgalaxy.mvs.step={case['mvs_step']}" in java and 'case.get("mvs_step") is not None' in java


def test_a_tab_member_that_fits_at_stops_of_8_is_untouched():
    data = b"       01  A.\n\t05  B  PIC X.\n"
    assert equivalence_common._tab_stops(data, "A.cpy") is data


def test_a_tab_member_past_column_72_at_8_is_staged_at_stops_of_4():
    line = b"\t\t     05  CUST-FIRST-NAME" + b" " * 24 + b"PIC X(25).\n"
    assert max(len(ln) for ln in line.expandtabs(8).split(b"\n")) > 72
    out = equivalence_common._tab_stops(line, "CUSTREC.cpy")
    assert out == line.expandtabs(4) and max(len(ln) for ln in out.split(b"\n")) <= 72


def test_a_tab_member_still_past_column_72_is_refused_by_name():
    line = b"\t\t" + b"X" * 70 + b"\n"
    with pytest.raises(RuntimeError, match=r"not runnable faithfully: BIG\.cpy"):
        equivalence_common._tab_stops(line, "BIG.cpy")


@pytest.mark.skipif(
    os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL), a JDK + Maven and the CardDemo corpus"
)
def test_the_port_is_proved_end_to_end(tmp_path):
    import subprocess

    out = subprocess.run(
        [sys.executable, str(REPO / "tests" / "tools" / "det_port.py"), "run", "carddemo-cbstm03a", "--faults", "none", "--work", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )  # fmt: skip
    assert "PROVED" in out.stdout, out.stdout[-2000:]


def _det_runtime():
    import equivalence_java

    return equivalence_java.det_runtime


def test_a_committed_det_port_is_its_services_and_the_runtime_is_laid_at_proof_time(tmp_path):
    port = REPO / "tests" / "equivalence" / "carddemo-cbstm03a" / "port"
    assert sorted(p.name for p in (port / "service").glob("*.java")) == ["Cbstm03aService.java", "Cbstm03bService.java"]
    assert not (port / "cobolrt").exists()
    assert json.loads((port / "provenance.json").read_text(encoding="utf-8"))["translator"] == "det"


def test_the_runtime_is_laid_only_for_a_port_that_names_it_and_does_not_carry_it(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    names = tmp_path / "Names.java"
    names.write_text("import com.gitgalaxy.modernized.cobolrt.Cobol;\n", encoding="utf-8")
    plain = tmp_path / "Plain.java"
    plain.write_text("class Plain {}\n", encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    lay = _det_runtime()
    laid = lay(["service/N.java"], {"service/N.java": names}, project, tmp_path / "w")
    assert "cobolrt/Cobol.java" in laid and all(p.is_file() for p in laid.values())
    assert lay(["service/P.java"], {"service/P.java": plain}, project, tmp_path / "w") == {}
    assert lay(["service/N.java", "cobolrt/Cobol.java"], {"service/N.java": names}, project, tmp_path / "w") == {}
