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


# ---- #7487 slice 5: the region's file set, read where the port claims an instance ----------------------------------------


def test_the_claim_reads_the_region_set_from_the_root_task_and_fails_closed():
    java = "\n".join(FC.file_key_method(["ZC@ID@FILE", "ZC@ID@KEY"]))
    reader = java.split("private static java.util.Set<String> regionFiles(CicsTask t) {")[1].split("\n    }\n")[0]
    assert 'getDeclaredField("parent")' in reader and 'getDeclaredField("regionFiles")' in reader
    assert 'throw new Hole("CICS file region set unreadable' in reader
    claim = java.split("private void claimInstance(String name) {")[1]
    assert "if (defined != null)" in claim and "same.size() > 1" in claim
    # the private fields it reads exist under those names in the runtime
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_TASK_JAVA

    assert "private final CicsTask parent;" in CICS_TASK_JAVA
    assert "private java.util.Set<String> regionFiles;" in FAULTS_JAVA


_HARNESS = """\
import java.util.*;
class Hole extends RuntimeException { Hole(String m) { super(m); } }
class CicsTask {
    private final CicsTask parent;
    private Set<String> regionFiles;
    CicsTask(CicsTask parent, Set<String> files) { this.parent = parent; this.regionFiles = files; }
}
class Svc {
    CicsTask task;
%s
    String claim(String... names) {
        try { for (String n : names) claimInstance(n); return "ok"; } catch (Hole h) { return h.getMessage(); }
    }
    public static void main(String[] a) {
        Svc s = new Svc();
        Set<String> one = Set.of("ZC01FILE", "ZC01KEY"), two = Set.of("ZC01FILE", "ZC02FILE", "ZC01KEY");
        s.task = new CicsTask(null, null);
        System.out.println("unstated:" + s.claim("ZC02FILE"));
        s.task = new CicsTask(null, one);
        System.out.println("one:" + s.claim("ZC01FILE"));
        s.task = new CicsTask(null, two);
        System.out.println("two-only-02:" + s.claim("ZC02FILE"));
        s.task = new CicsTask(null, two);
        System.out.println("one-key:" + s.claim("ZC01KEY"));
        s.task = new CicsTask(null, Set.of("ZC01KEY", "ZC02KEY"));
        System.out.println("two-key:" + s.claim("ZC02KEY"));
        s.task = new CicsTask(new CicsTask(null, two), null);
        System.out.println("two-child:" + s.claim("ZC01FILE"));
        s.task = new CicsTask(null, two);
        System.out.println("own-key:" + s.claim("ZC@ID@FILE"));
        s.task = new CicsTask(null, Set.of("ZC01FILE", "ZC02FILE", "ZC03FILE"));
        System.out.println("three:" + s.claim("ZC03FILE"));
    }
}
"""


def test_the_emitted_claim_refuses_a_task_reaching_one_instance_while_the_region_defines_several(tmp_path):
    import shutil
    import subprocess

    import pytest

    if not shutil.which("javac") or not shutil.which("java"):
        pytest.skip("javac / java not on PATH")
    body = "\n".join(FC.file_key_method(["ZC@ID@FILE", "ZC@ID@KEY"]))
    (tmp_path / "Svc.java").write_text(_HARNESS % body, encoding="utf-8")
    flags = ["-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8"]
    done = subprocess.run(["javac", "-encoding", "UTF-8", "Svc.java"], cwd=tmp_path, capture_output=True, check=False)
    assert done.returncode == 0, done.stderr.decode("utf-8")
    run = subprocess.run(["java", *flags, "Svc"], cwd=tmp_path, capture_output=True, check=True)
    got = dict(line.split(":", 1) for line in run.stdout.decode("utf-8").splitlines())
    assert got["unstated"] == "ok"  # no region set stated: every definable name stays the project's to decide
    assert got["one"] == "ok"  # one defined instance: the store is that instance's
    assert got["one-key"] == "ok"  # the count is per template: two FILE instances do not condemn the one KEY instance
    for case in ("two-only-02", "two-key", "two-child"):  # reaching ONE instance of several defined is a Hole
        assert got[case].startswith("CICS file ") and "share the one generated store of ZC@ID@" in got[case], case
    assert "[ZC01FILE, ZC02FILE]" in got["two-only-02"] and "ZC01KEY" not in got["two-only-02"]
    assert "[ZC01KEY, ZC02KEY]" in got["two-key"]
    assert got["own-key"] == "ok"  # a store's own key is never judged
    assert "[ZC01FILE, ZC02FILE, ZC03FILE]" in got["three"]
