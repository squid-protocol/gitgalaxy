"""#4449 (X8): the COBOL oracle stops on a subscript / reference modification past its item, by name."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_common as common

PROGRAM = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. T.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 TB.
          05 E PIC X OCCURS 3.
       01 N PIC 9(3) VALUE {n}.
       01 S PIC X(5) VALUE "ABCDE".
       01 L PIC 9(2) VALUE {length}.
       PROCEDURE DIVISION.
           MOVE "X" TO E(N)
           MOVE "Z" TO S(1:L)
           DISPLAY "done"
           STOP RUN.
"""


def test_every_compile_carries_the_bound_checks():
    case = {"program": "T", "datasets": {}}
    _src, flags = common.compile_options(case, PROGRAM.format(n=1, length=1))
    assert set(common.BOUND_FLAGS) <= set(flags)
    assert flags[-2:] == common.BOUND_FLAGS


@pytest.mark.parametrize(
    "said, expected",
    [
        (
            b"libcob: t.cbl:13: error: subscript of 'E' out of bounds: 7\nnote: maximum subscript for 'E': 3\n",
            "subscript of 'E'",
        ),
        (b"in\nlibcob: t.cbl:15: error: length of 'S' out of bounds: 9, maximum: 5\n", "length of 'S'"),
        (b"libcob: t.cbl:15: error: offset of 'S' out of bounds: 9\n", "offset of 'S'"),
        ("libcob: x.cbl:1: error: subscript of 'E' out of bounds: 7", "subscript of 'E'"),
    ],
)
def test_bound_violation_names_the_item(said, expected):
    assert expected in (common.bound_violation(said) or "")


@pytest.mark.parametrize(
    "said",
    [
        b"",
        b"done\n",
        b"libcob: error: module 'X' not found\n",
        b"a subscript of 'E' out of bounds (the program's own text)\n",
    ],
)
def test_other_output_is_no_violation(said):
    assert common.bound_violation(said) is None


def _oracle(tmp_path, n, length, case=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    if shutil.which("docker") is None:
        pytest.skip("no docker")
    if subprocess.run(["docker", "image", "inspect", common.IMAGE], capture_output=True).returncode != 0:
        pytest.skip(f"no {common.IMAGE} image")
    case = {"program": "T", "datasets": {}, **(case or {})}
    src, flags = common.compile_options(case, PROGRAM.format(n=n, length=length))
    (tmp_path / "t.cbl").write_text(src)
    (tmp_path / "src").mkdir()
    common.stage_zero_length_conf(case, tmp_path / "src")
    flags = [f.replace("/work/src", "/w/src") for f in flags]  # the harness mounts the run at /work
    cmd = f"cobc -x -std=ibm {' '.join(flags)} -o t t.cbl && ./t"
    p = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", common.IMAGE, "sh", "-c", cmd + " 2>&1"],
        capture_output=True,
        timeout=300,
    )
    return p.stdout


@pytest.mark.parametrize(
    "n, length, hit", [(7, 1, "subscript of 'E'"), (1, 9, "length of 'S'"), (1, 0, "length of 'S'")]
)
def test_oracle_stops_past_the_item(tmp_path, n, length, hit):
    assert hit in (common.bound_violation(_oracle(tmp_path, n, length)) or "")


def test_oracle_runs_in_range(tmp_path):
    said = _oracle(tmp_path, 3, 5)
    assert common.bound_violation(said) is None and b"done" in said


ZLEN = {"zero_length_refmod": "the program moves a blank message by reference modification of length 0"}


def test_zero_length_refmod_is_off_unless_the_case_says_so():
    _src, flags = common.compile_options({"program": "T", "datasets": {}}, PROGRAM.format(n=1, length=1))
    assert not any(f.startswith("-conf=") for f in flags)
    _src, flags = common.compile_options({"program": "T", "datasets": {}, **ZLEN}, PROGRAM.format(n=1, length=1))
    assert flags[-3:] == [f"-conf=/work/src/{common.ZERO_LENGTH_CONF}", *common.BOUND_FLAGS]


def test_zero_length_refmod_needs_a_reason():
    with pytest.raises(common.UnsupportedOption):
        common.zero_length_refmod({"zero_length_refmod": "yes"})


def test_zero_length_refmod_is_an_empty_item_and_nothing_else_is_let_through(tmp_path):
    ok = _oracle(tmp_path / "a", 1, 0, ZLEN)
    assert common.bound_violation(ok) is None and b"done" in ok  # `MOVE "Z" TO S(1:0)` changes nothing
    assert "length of 'S'" in (common.bound_violation(_oracle(tmp_path / "b", 1, 9, ZLEN)) or "")  # still past the item
    assert "subscript of 'E'" in (common.bound_violation(_oracle(tmp_path / "c", 7, 0, ZLEN)) or "")  # still refused


BOUNDS_CASES = ["carddemo-cardlist", "carddemo-menu", "cbsa-bnk1cac", "cbsa-bnk1uac"]


@pytest.mark.parametrize("name", BOUNDS_CASES)
def test_bounds_refused_names_real_scenarios_with_a_reason(name):
    import json

    case = json.loads((Path(__file__).resolve().parents[1] / "equivalence" / name / "case.json").read_text())
    scenarios = {sc["name"] for sc in case["scenarios"]}
    refused = case["bounds_refused"]
    assert refused and set(refused) <= scenarios
    assert all(len(why) > 20 for why in refused.values())
