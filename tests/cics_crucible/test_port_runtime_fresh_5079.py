"""#5079: the det runtime copies inside two committed crucible ports are FROZEN on purpose (docs/cobolrt_api_contract.md,
"Frozen runtime copies"): they predate `addressCommarea` and the pointer lane, and a refresh is not free -- the copies'
calls into the live CicsTask become public API (`frozen-overlay` evidence in cobolrt_api.json) and the ports' mutation
scores (test_proof_reach) and evidence records are tied to them. So the answer to "the copies are stale" is this pin,
not a copy: only these two overlays carry a runtime, and a program that needs ADDRESS is ported on the live runtime."""

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FROZEN = {
    "tests/cics_crucible/ports/pc-wizard/PCCONF/overlay",
    "tests/cics_crucible/ports/pc-return-immediate/PCIMMA/overlay",
}
LIVE_DETCICS = REPO / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt" / "cics" / "DetCics.java"


def _overlays_with_a_runtime():
    files = subprocess.run(  # noqa: S603
        ["git", "ls-files", "tests/cics_crucible/ports"],  # noqa: S607
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.splitlines()  # fmt: skip
    return {f.split("/cobolrt/", 1)[0] for f in files if "/overlay/cobolrt/" in f}


def test_only_the_two_documented_ports_carry_a_frozen_runtime():
    assert _overlays_with_a_runtime() == FROZEN


def test_the_frozen_copies_lack_what_the_live_runtime_models_for_address():
    live = LIVE_DETCICS.read_text(encoding="utf-8")
    assert "addressCommarea" in live and "addressTwa" in live and "addressCwa" in live
    for overlay in FROZEN:
        copy = (REPO / overlay / "cobolrt" / "cics" / "DetCics.java").read_text(encoding="utf-8")
        assert "addressCommarea" not in copy, f"{overlay}: refreshed? then update docs/cobolrt_api_contract.md and X59"
