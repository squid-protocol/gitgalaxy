"""#8121: a re-entry scenario (`commarea_hex`, EIBCALEN > 0) on a program with no DFHCOMMAREA (the health screen front
ends keep COMM-AREA in WORKING-STORAGE, a layout_only case). The det service has no handleTransaction that takes bytes,
so the java-facade leg used to refuse "cannot take the COMMAREA ([B)". The region now runs such a task through runTask
(and `entries` says so); a typed COMMAREA no overload takes still refuses. The end-to-end proof is
`det_port.py run health-hcp1pl01 health-hcv1pl01 health-hct1pl01`; these pin the generated text and the input class."""

import json
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import equivalence_cics as ec  # noqa: E402

_JAVA = ec.FACADE_JAVA
REPO = Path(__file__).resolve().parents[2]
HEALTH = ("hcp1pl01", "hcv1pl01", "hct1pl01")


def test_raw_bytes_no_overload_takes_run_through_runtask_with_a_named_entry():
    assert "} else if (commarea instanceof byte[]) {" in _JAVA
    assert 'entry(program, "runTask (raw bytes: no handleTransaction of " + program + " takes them, #8121)");' in _JAVA


def test_the_branch_sits_after_every_typed_and_byte_overload_and_before_the_refusal():
    typed = _JAVA.index("two.getParameterTypes()[1].isInstance(commarea)")
    bytes_overload = _JAVA.index("commarea instanceof byte[] && twoB != null")
    branch = _JAVA.index("} else if (commarea instanceof byte[]) {")
    refusal = _JAVA.index("cannot take the COMMAREA (")
    assert typed < bytes_overload < branch < refusal


def test_a_non_byte_commarea_still_refuses():
    assert 'throw new FacadeRefused("handleTransaction of " + program + " cannot take the COMMAREA ("' in _JAVA
    # the new branch is the byte[] case only, ahead of the one `else` that refuses
    tail = _JAVA[_JAVA.index("} else if (commarea instanceof byte[]) {") :]
    assert tail.index("} else {") < tail.index("cannot take the COMMAREA (")


@pytest.mark.parametrize("hexs", ["40", "C1C2C3C4C5C6C7C8", "C1C2C3", "F0" * 50])
def test_every_length_of_raw_bytes_is_the_ports_commarea_and_eibcalen(hexs):
    """One byte, even and odd lengths, a long area: the port is given those bytes and EIBCALEN is their count."""
    case = {"corpus": "x", "commarea": {"segments": [], "layout_only": True}}
    sc = {"name": "s", "commarea": None, "commarea_hex": hexs}
    out = ec._java_untyped_commarea(case, sc, [])
    assert out["untyped_length"] == len(hexs) // 2
    assert out["commarea_hex"] and out["area"] == hexs


@pytest.mark.parametrize("bad", ["", "4", "ZZ", "40 41", 5])
def test_an_empty_odd_or_non_hex_area_is_still_refused_by_name(bad):
    case = {"commarea": {"segments": [], "layout_only": True}}
    with pytest.raises(ec.Unsupported, match="commarea_hex"):
        ec.untyped_commarea(case, {"name": "s", "commarea": None, "commarea_hex": bad}, [])


@pytest.mark.parametrize("name", HEALTH)
def test_each_health_front_end_drives_its_reentry_arm_with_bytes(name):
    case = json.loads((REPO / f"tests/equivalence/health-{name}/case.json").read_text(encoding="utf-8"))
    assert ec.layout_only(case)
    arm = [s for s in case["scenarios"] if s.get("commarea_hex")]
    assert {s["name"] for s in arm} == {"reentry-short-area", "reentry-long-area"}
    assert len({len(s["commarea_hex"]) for s in arm}) == 2  # a short and a long area
    for s in arm:
        assert s["commarea"] is None and s.get("why") and not s.get("link_bytes")
    assert "Not driven" not in case["notes"]
