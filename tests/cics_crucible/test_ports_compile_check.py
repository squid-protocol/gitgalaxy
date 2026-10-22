"""#4423: tests/tools/ports_compile_check.py finds every committed port and names the broken ones."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ports_compile_check as pcc  # noqa: E402


def test_the_compiler_naming_a_ports_file_names_that_port_else_all_of_them():
    files = {"PCWIZ": [Path("o/service/PcwizService.java")], "PCCONF": [Path("o/service/PcconfService.java")]}
    assert pcc.culprits(files, "[ERROR] /x/service/PcwizService.java:[12,5] cannot find symbol") == ["PCWIZ"]
    assert pcc.culprits(files, "[ERROR] /x/dto/Other.java:[1,1] error") == ["PCWIZ", "PCCONF"]


def test_every_committed_equivalence_port_is_checked_with_the_ports_it_uses():
    ports = {c["_name"]: c for c in pcc.equivalence_ports(None)}
    committed = {p.parent.name for p in pcc.EQUIVALENCE.glob("*/port") if any(p.rglob("*.java"))}
    assert set(ports) == committed and "carddemo-signon" in ports
    report = pcc.port_files(ports["carddemo-report"])  # uses_ports: carddemo-dateutil's CSUTLDTC first
    assert list(report) == ["service/CsutldtcService.java", "service/Corpt00cService.java"]
    assert report["service/CsutldtcService.java"].parts[-4] == "carddemo-dateutil"


def test_crucible_ports_are_the_overlays_under_the_ledger():
    assert pcc.cx.case_overlays(pcc.cx.PORTS_DIR / "pc-wizard").keys() == {"PCCONF", "PCWIZ"}


def test_pc_return_immediate_has_a_det_port_of_each_program():
    """#5053: the case's four programs are committed det ports (no model), so its java-ported cells have a port."""
    ports = pcc.cx.case_overlays(pcc.cx.PORTS_DIR / "pc-return-immediate")
    assert ports.keys() == {"PCIMMA", "PCIMMB", "PCIMML", "PCIMMS"}


def test_pcconf_is_a_det_port_that_applies_the_justify_of_its_map():
    """#5082: PCCONF's RECEIVE MAP puts AMT (JUSTIFY=(RIGHT,ZERO)) through DetJustify; the det port carries the runtime."""
    import json

    ports = pcc.cx.PORTS_DIR / "pc-wizard"
    prov = json.loads((ports / "PCCONF" / "provenance.json").read_text(encoding="utf-8"))
    assert prov["backend"] == "det" and prov["model"] is None
    service = (ports / "PCCONF" / "overlay" / "service" / "PcconfService.java").read_text(encoding="utf-8")
    assert "DetJustify.place(" in service and '"RIGHT,ZERO"' in service
    assert (ports / "PCCONF" / "overlay" / "cobolrt" / "cics" / "DetJustify.java").is_file()
