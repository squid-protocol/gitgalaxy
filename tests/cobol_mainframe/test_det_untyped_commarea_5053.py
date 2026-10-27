"""#5053: a COMMAREA no generated DTO types (a DFHCOMMAREA that is no record, PIC X(30): the stub says `Object
request`) is not a class of the project. It read as a missing dto/contract class `Object`, so PCCONF's
`RETURN TRANSID('PC03') COMMAREA(WS-STATE)` was a hole; and a det program entered with a COMMAREA of another
program's DTO ignored it."""

from __future__ import annotations

import pytest

pytest.importorskip("tree_sitter_language_pack")

from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import program as P  # noqa: E402

TYPED = "WsState"


def _stub(request: str) -> str:
    return (
        f"public X handleTransaction(String transid, {request} request) {{ }}\n"
        f"public X handleLink({request} request) {{ }}\n"
        f"public X linkOther({request} request) {{ }}\n"
        f"public X xctlOther({request} request) {{ }}\n"
    )


def test_an_object_request_types_nothing(tmp_path):
    g = C.Generated(tmp_path, _stub("Object"))
    assert g.contract is None
    assert g.links == {} and g.xctl == {}


def test_a_generated_dto_still_types_every_boundary(tmp_path):
    g = C.Generated(tmp_path, _stub(TYPED))
    assert g.contract == TYPED
    assert g.links == {"OTHER": TYPED} and g.xctl == {"OTHER": TYPED}


@pytest.mark.parametrize(
    "sig", ["public X handleLink(Object request)", "public X handleTransaction(String transid, Object request)"]
)
def test_a_target_taking_object_has_no_contract(tmp_path, sig):
    svc = tmp_path / "src/main/java/p/service"
    svc.mkdir(parents=True)
    (svc / "TargetService.java").write_text(f"class TargetService {{ {sig} {{ }} }}", encoding="utf-8")
    g = C.Generated(tmp_path, "")
    assert g.target_contract("TARGET") is None
    (svc / "TargetService.java").write_text(sig.replace("Object", TYPED) + " { }", encoding="utf-8")
    assert g.target_contract("TARGET") == TYPED


def test_a_foreign_dto_commarea_is_read_through_its_layout():
    """The entry reads a COMMAREA that is no DTO of this program through its layout (toCommarea, #4449)."""
    from pathlib import Path

    rt = (Path(P.__file__).parent / "cobolrt/cics/DetCics.java").read_text(encoding="utf-8")
    assert "public static byte[] layoutBytes(Object dto)" in rt and '"toCommarea"' in rt
    assert "DetCics.layoutBytes(ca)" in Path(P.__file__).read_text(encoding="utf-8")


def test_the_committed_pcconf_det_port_translates_whole():
    """PCCONF's `RETURN TRANSID COMMAREA(WS-STATE)` were two holes before the untyped COMMAREA; the committed port
    says every statement is translated, and no statement throws Hole."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "tests/cics_crucible/ports/pc-wizard"
    java = (root / "PCCONF/overlay/service/PcconfService.java").read_text(encoding="utf-8")
    assert "Statements: 47, translated 47, holes 0." in java
    # the one Hole left is the runtime's file-store guard, not a translated statement
    assert java.count("throw new Hole(") == java.count('throw new Hole("CICS file ')


def test_the_committed_pc_return_immediate_det_ports_translate_whole_and_no_port_cell_is_ledgered():
    """The `pc-return-immediate` box said "no committed port, java-ported cells fail 4/4". The four programs are
    committed det ports (every statement translated, no hole), and the crucible baseline ledgers no java-ported or
    java-facade cell of the case: only the `java` side, the generated stub whose PROCEDURE DIVISION is not ported."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "tests/cics_crucible"
    statements = {"PCIMMA": 34, "PCIMMB": 12, "PCIMML": 7, "PCIMMS": 5}
    for program in statements:
        svc = next((root / "ports/pc-return-immediate" / program / "overlay/service").glob("*Service.java"))
        java = svc.read_text(encoding="utf-8")
        n = statements[program]
        assert f"Statements: {n}, translated {n}, holes 0." in java, program
        assert "throw new Hole(" not in java.replace('throw new Hole("CICS file ', ""), program
        prov = json.loads((root / "ports/pc-return-immediate" / program / "provenance.json").read_text("utf-8"))
        assert prov["backend"] == "det" and prov["model"] is None, program

    ledger = json.loads((root / "baseline.json").read_text(encoding="utf-8"))["cells"]
    cells = {k: v for k, v in ledger.items() if k.startswith("pc-return-immediate/")}
    assert cells, "the java side of the case is ledgered"
    assert {k.rsplit("/", 1)[1] for k in cells} == {"java"}


def test_the_pc_return_immediate_java_cells_fail_as_every_unported_stub_does_and_the_ports_have_coverage():
    """The `java` cell is the generated stub with no ported PROCEDURE DIVISION: it stops before its first event, the
    way every ledgered `java` cell of a ported case does. The four ports carry scenario coverage in coverage.json."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "tests/cics_crucible"
    cells = json.loads((root / "baseline.json").read_text(encoding="utf-8"))["cells"]
    mine = {k: v for k, v in cells.items() if k.startswith("pc-return-immediate/")}
    assert len(mine) == 4
    for key, cell in mine.items():
        assert cell["status"] == "fail", key
        assert cell["reason"].endswith("expected, the side recorded no further event"), key
    programs = json.loads((root / "coverage.json").read_text(encoding="utf-8"))["programs"]
    for program in ("PCIMMA", "PCIMMB", "PCIMML", "PCIMMS"):
        assert programs[f"pc-return-immediate/{program}"], program
