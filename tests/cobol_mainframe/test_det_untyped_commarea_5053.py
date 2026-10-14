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
