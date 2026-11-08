"""#7954 slice 6: a scenario states the files its region does not install (`undefined_files`).

ABNDPROC's `store()` answers FILENOTFOUND for `undefinableFile(name) || task.undefinedInRegion(name)`; ABNDFILE is a
definable name, so only the region check can refuse it, and the harness used to state every case file as installed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

CASE = Path(__file__).resolve().parents[1] / "equivalence" / "cbsa-abndproc" / "case.json"
FILES = [{"file": "ABNDFILE"}, {"file": "OTHER"}]


def _eq():
    import equivalence_cics as eq

    return eq


def test_an_absent_key_states_nothing():
    assert _eq().undefined_files({}, {"name": "s"}, FILES) == []


def test_the_named_files_are_returned_once_and_sorted():
    sc = {"name": "s", "undefined_files": ["OTHER", "ABNDFILE", "OTHER"]}
    assert _eq().undefined_files({}, sc, FILES) == ["ABNDFILE", "OTHER"]


def test_install_symbols_resolve_the_name_as_files_cfg_states_it():
    case = {"install_symbols": {"values": {"ID": "01"}, "why": "x"}}
    files = [{"file": "ZC@ID@FILE"}]
    assert _eq().undefined_files(case, {"name": "s", "undefined_files": ["ZC01FILE"]}, files) == ["ZC01FILE"]


@pytest.mark.parametrize("bad", [[], "ABNDFILE", ["NOFILE"], ["ABNDFILE", 3], {"ABNDFILE": 1}])
def test_a_shape_the_case_cannot_mean_is_refused_by_name(bad):
    eq = _eq()
    with pytest.raises(eq.Unsupported, match="undefined_files"):
        eq.undefined_files({}, {"name": "s", "undefined_files": bad}, FILES)


def test_the_harness_drops_the_file_from_files_cfg_and_the_port_region_set():
    src = (TOOLS / "equivalence_cics.py").read_text(encoding="utf-8")
    assert "if _cfg_file_name(case, f) not in undefined_files(case, sc, files)" in src  # the stub's files.cfg
    assert 'sc.hasNonNull("undefined_files")' in src and "installed.remove(u.asText())" in src  # the port's set
    assert "task.withRegionFiles(installed);" in src
    # emitted into the scenario JSON only when stated (an always-present empty key breaks exact-equality tests)
    assert '**({"undefined_files": undefined_files(case, sc, files)} if sc.get("undefined_files") else {})' in src


def test_abndproc_states_the_region_without_abndfile_on_both_entry_shapes():
    case = json.loads(CASE.read_text(encoding="utf-8"))
    by = {s["name"]: s for s in case["scenarios"]}
    typed, raw = by["abndfile-not-in-region"], by["abndfile-not-in-region-link-bytes"]
    assert typed["undefined_files"] == raw["undefined_files"] == ["ABNDFILE"]
    assert raw["link_bytes"] is True and not typed.get("link_bytes")
    assert "faults" not in typed and "faults" not in raw  # FILENOTFOUND comes from the region, not an injected RESP
    # ABNDFILE is a definable name (1-8 characters, no blank): the region check alone refuses it
    import equivalence_cics as eq

    assert not any(c.isspace() for c in "ABNDFILE") and eq.undefined_files(case, typed, [{"file": "ABNDFILE"}])
