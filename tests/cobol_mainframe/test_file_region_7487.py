"""#7487: a template-named CICS file (`ZC@ID@FILE`) is reached only by a name the region defines.

`fileKey` maps a run-time name onto the template store by its shape (`ZC.+FILE`), so ZECS003 started as ZC02, in a
region that installs only instance 01, reached ZC01's store and deleted its records where the COBOL gets FILENOTFOUND
(RESP 12, RESP2 1). The harness states the region's files (`withRegionFiles`, the names the stub's files.cfg carries);
`CicsTask.fileFault` and the port's `store()` answer FILENOTFOUND for any other name, whatever its shape.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from gitgalaxy.tools.cobol_to_java.cics_task_faults import FAULTS_JAVA  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_filecontrol as FC  # noqa: E402

CASE = Path(__file__).resolve().parents[1] / "equivalence" / "zecs-zecs003" / "case.json"


def test_the_runtime_answers_filenotfound_for_a_name_the_region_does_not_define():
    assert "public CicsTask withRegionFiles(java.util.Set<String> names)" in FAULTS_JAVA
    # one choke point for every file verb, after a planned (injected) condition and before the store is reached
    fault = FAULTS_JAVA.split("private int[] fileFault(")[1].split("\n    }\n")[0]
    assert "injected(cmd, file)" in fault and "undefinedInRegion(file)" in fault
    assert "return new int[] {12, 1};" in fault
    # not stated: every definable name stays the project's to decide (a case without the harness's set is unchanged)
    check = FAULTS_JAVA.split("public boolean undefinedInRegion(")[1].split("\n    }\n")[0]
    assert "defined != null" in check and "stripTrailing()" in check


def test_the_ports_store_never_hands_out_an_undefined_names_store():
    from gitgalaxy.tools.cobol_to_java.det import program

    src = Path(program.__file__).read_text(encoding="utf-8")
    assert "task.undefinedInRegion(name)" in src
    # the template switch is still only the shape of the DEFINED names
    java = "\n".join(FC.file_key_method(["ZC@ID@FILE"]))
    assert 'if (t.matches("ZC.+FILE")) return "ZC@ID@FILE";' in java


def _case() -> dict:
    return json.loads(CASE.read_text(encoding="utf-8"))


def test_the_harness_states_the_region_as_the_one_installed_instance():
    import equivalence_cics as eq

    case = _case()
    files = [{"file": "ZC@ID@FILE"}, {"file": "ZC@ID@KEY"}]
    names = [eq._cfg_file_name(case, f) for f in files]
    assert names == ["ZC01FILE", "ZC01KEY"]  # ZC02FILE is in no definition of the region
    assert eq.jstr_java("ZC01FILE") == '"ZC01FILE"'


def test_the_zc02_scenario_reads_a_file_the_region_does_not_install():
    case = _case()
    sc = next(s for s in case["scenarios"] if s["name"] == "transid-zc02")
    assert sc["transid"] == "ZC02"
    assert set(sc["datasets"]) == {"ZECS.ZC01FILE.TEST", "ZECS.ZC01KEY.TEST"}  # only instance 01 holds records


def test_a_task_reaching_two_instances_of_a_template_is_a_hole_not_one_shared_store():
    java = "\n".join(FC.file_key_method(["ZC@ID@FILE", "ZC@ID@KEY"]))
    claim = java.split("private void claimInstance(String name) {")[1]
    assert "putIfAbsent(k, t)" in claim and "!first.equals(t)" in claim
    assert "throw new Hole(" in claim and "per-instance data not modelled" in claim
    # a name that is a store's own key is never judged here
    assert "k.equals(t)) return;" in claim
    assert FC.file_key_method(["CUSTOMER"]) == []  # a program with no template store emits nothing


def test_the_port_claims_an_instance_only_where_a_template_store_exists():
    from gitgalaxy.tools.cobol_to_java.det import program

    src = Path(program.__file__).read_text(encoding="utf-8")
    assert "FC.has_template(cx.stores) else []" in src and "claimInstance(name);" in src


def test_a_read_that_answers_differently_is_a_difference_in_the_event_comparison():
    import equivalence_cics_compare as cmp

    cobol = [{"event": "READ", "file": "ZC02FILE", "resp": "FILENOTFOUND", "resp2": 1}]
    java = [{"event": "READ", "file": "ZC02FILE", "resp": "NORMAL"}]
    got = cmp.compare_events(cobol, java)
    assert got["equal"] == 0
    assert {f["field"] for f in got["diffs"][0]["fields"]} == {"resp", "resp2"}
    assert cmp.compare_events(cobol, [dict(cobol[0])])["equal"] == 1
