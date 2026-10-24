"""#5694: on the burned programs that COPY or INCLUDE a system member (CardDemo COCRDUPC, COUSR01C, COTRN02C; CBSA
UPDACC), the engine has no entry for DFHAID / DFHBMSCA / SQLCA / DFHEIBLK, so those records keep the translator's own
layout and every estate record takes the engine's. Pins, per program and in both modes: nothing refuses, the system
members are exactly the records the translator lays out alone, and their arithmetic is IBM's (test_det_system_member_layout)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from scan_server import scan_to_db
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from gitgalaxy.tools.cobol_to_java.det import layout as L
from gitgalaxy.tools.cobol_to_java.det.cics import COPY
from gitgalaxy.tools.cobol_to_java.det.engine_layout import EngineLayouts
from gitgalaxy.tools.cobol_to_java.det.source import program_lines

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

CORPORA = Path(
    os.environ.get("GITGALAXY_MAINFRAME_CORPORA", Path(__file__).resolve().parents[2] / ".mainframe_corpora")
)
CARDDEMO = CORPORA / "aws-mainframe-modernization-carddemo" / "app"
CBSA = CORPORA / "cics-banking-sample-application-cbsa" / "src" / "base"

# program -> (source, copybook dirs)
CASES = {
    "COCRDUPC": (CARDDEMO / "cbl" / "COCRDUPC.cbl", [CARDDEMO / "cpy", CARDDEMO / "cpy-bms"]),
    "COUSR01C": (CARDDEMO / "cbl" / "COUSR01C.cbl", [CARDDEMO / "cpy", CARDDEMO / "cpy-bms"]),
    "COTRN02C": (CARDDEMO / "cbl" / "COTRN02C.cbl", [CARDDEMO / "cpy", CARDDEMO / "cpy-bms"]),
    "UPDACC": (CBSA / "cobol_src" / "UPDACC.cbl", [CBSA / "cobol_copy"]),
}
# the records the translator lays out alone: DFHAID / DFHBMSCA for the CardDemo screens, SQLCA for CBSA's Db2 INCLUDE
OWN = {
    "COCRDUPC": ["DFHAID", "DFHBMSCA"],
    "COUSR01C": ["DFHAID", "DFHBMSCA"],
    "COTRN02C": ["DFHAID", "DFHBMSCA"],
    "UPDACC": ["SQLCA"],
}
SIZES = {"SQLCA": 136}  # IBM's documented SQLCA (test_det_system_member_layout)


@pytest.fixture(scope="module", params=sorted(CASES))
def burned(request, tmp_path_factory):
    pytest.importorskip("tree_sitter_language_pack")
    src, dirs = CASES[request.param]
    if not src.is_file():
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    base = tmp_path_factory.mktemp(f"system_member_burned_{request.param}")
    repo = base / "repo"
    repo.mkdir()
    shutil.copy(src, repo / src.name)
    for d in dirs:
        shutil.copytree(d, repo / d.name)
    ir = load_galaxy_ir(scan_to_db(repo, base / "scan"))
    return request.param, repo, [repo / d.name for d in dirs], ir


@pytest.mark.parametrize("mode", ["engine", "check"])
def test_the_system_members_keep_the_translators_layout_and_the_rest_the_engines(burned, mode):
    name, repo, dirs, ir = burned
    lines = program_lines(repo / f"{name}.cbl", [repo, *dirs, COPY], None)
    recs = L.parse(lines)
    lay = EngineLayouts.from_ir(ir, f"{name}.cbl", repo, mode=mode)
    lay.apply(recs, lines)  # LayoutDisagrees / a refusal here is the finding
    assert sorted(lay.own) == OWN[name]  # the system members, and nothing the engine could have laid out
    assert not set(lay.own) & set(lay.consumed)
    assert sorted(lay.own + lay.consumed) == sorted(r.name for r in recs)  # every record is one or the other
    assert lay.consumed, "the program's own records take the engine's layout"
    for r in recs:
        if r.name in SIZES:
            assert r.size == SIZES[r.name], r.name
