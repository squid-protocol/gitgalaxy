"""#4308: every committed CICS crucible port's provenance names the crucible version it is proven at, and that is
the pinned one (tests/_cics_crucible_pin.py PINNED_REF) -- or the record says, explicitly, that it is stale.

A pin bump used to leave all 17 records saying "v0.1.0" while the runner measured v0.2.0, and nothing noticed. Now
the bump fails here until each port is re-proven at the new pin (tests/tools/crucible_port_provenance.py reprove,
which runs the proof and appends a `reproven` entry) or marked stale against it with a reason.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import crucible_port_provenance as cpp  # noqa: E402


def test_every_port_provenance_is_at_the_pinned_crucible():
    assert cpp.records(), "no committed crucible port provenance found"
    assert cpp.problems() == []


def test_a_re_proof_names_the_port_it_proved():
    """A `reproven` entry is a claim about one port tree: the committed overlay must still be that tree."""
    for path in cpp.records():
        again = (json.loads(path.read_text(encoding="utf-8")).get("proof") or {}).get("reproven") or []
        if again:
            assert again[-1]["port_sha256"] == cpp.tree_sha256(path.parent / "overlay"), (
                f"{path.relative_to(cpp.PORTS)}: the port changed since its last re-proof; run "
                "tests/tools/crucible_port_provenance.py reprove"
            )


def _write(tmp_path, proof):
    path = tmp_path / "case-x" / "PROG" / "provenance.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"format": "cics-crucible-port/1", "proof": proof}), encoding="utf-8")
    return tmp_path


OLD = {"crucible_ref": "v0.1.0 (0c942cb8)", "summary": {"s": "1/1"}}


@pytest.mark.parametrize(("proof", "ok"), [
    (OLD, False),  # the loop's proof at an older crucible, nothing said: the #4308 bug
    ({**OLD, "crucible_ref": "v0.2.0 (94f2afcb)"}, True),
    ({**OLD, "reproven": [{"crucible_ref": "v0.2.0 (94f2afcb)"}]}, True),
    ({**OLD, "reproven": [{"crucible_ref": "v0.2.0 (94f2afcb)"}, {"crucible_ref": "v0.1.5 (aaaaaaaa)"}]}, False),
    ({**OLD, "stale": {"against": "v0.2.0", "reason": "the re-proof failed: {'s': '0/1'}"}}, True),
    ({**OLD, "stale": {"against": "v0.1.5", "reason": "stale against an older pin"}}, False),  # the next bump
    ({**OLD, "stale": {"against": "v0.2.0"}}, False),  # a stale mark must say why
])  # fmt: skip
def test_the_pinned_ref_or_an_explicit_stale_mark(tmp_path, proof, ok):
    assert (cpp.problems(_write(tmp_path, proof), "v0.2.0") == []) is ok


def test_ref_tag():
    assert cpp.ref_tag("v0.2.0 (94f2afcb)") == "v0.2.0"
    assert cpp.ref_tag("94f2afcbe6adfb88") == "94f2afcbe6adfb88"
    assert cpp.ref_tag(None) is None
