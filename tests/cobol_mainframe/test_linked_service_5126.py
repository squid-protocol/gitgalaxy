"""#5126: a LINKed program the forge writes no service for (HLASM ZECS002) is named before the Java test fails to compile."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "tools"))
import equivalence_cics as ec  # noqa: E402


def _project(tmp_path, services):
    src = tmp_path / "src/main/java/com/x/service"
    src.mkdir(parents=True)
    for name in services:
        (src / f"{name}.java").write_text("class X {}", encoding="utf-8")
    return tmp_path / "src/main/java"


def test_no_programs_means_nothing_missing(tmp_path):
    assert ec.no_service_programs({"program": "A"}, _project(tmp_path, [])) == []


def test_a_linked_program_without_a_service_is_named(tmp_path):
    case = {"programs": [{"program": "zecs002"}, {"program": "LGSTSQ"}]}
    assert ec.no_service_programs(case, _project(tmp_path, ["LgstsqService"])) == ["ZECS002"]


def test_every_linked_program_with_a_service_is_not_named(tmp_path):
    case = {"programs": [{"program": "ZECS002"}, {"program": "LGSTSQ"}]}
    assert ec.no_service_programs(case, _project(tmp_path, ["Zecs002Service", "LgstsqService"])) == []
