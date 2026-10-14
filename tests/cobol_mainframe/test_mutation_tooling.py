"""#3753 follow-up: mutation testing of the proven ports (tests/tools/mutation.py). The pure parts: which sites are
mutated (never a comment, a log call, an import or an annotation), what each operator writes, the sample, which of
a proof's runs killed a mutant, and the score."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_common as common
import equivalence_java as ej
import mutation as mu
from maven_exe import mvn_executable

JAVA = """package com.gitgalaxy.modernized.service;

import java.math.BigDecimal;

@Service
public class XService {
    private static final Logger log = LoggerFactory.getLogger(XService.class);

    int run(int a, List<String> xs) {
        log.info("never mutated: {} < {}", a, 1);
        // a < b in a comment is not code
        if (a >= 10 && a != 0x09CB) {
            total = total.add(new BigDecimal("1.00")).setScale(2, RoundingMode.HALF_UP);
            count++;
        }
        doIt(a);
        return a * 2;
    }
}
"""


def _by_op(ms):
    out = {}
    for m in ms:
        out.setdefault(m.op, []).append(m.after)
    return out


def test_every_operator_mutates_code_and_nothing_else():
    ms = mu.mutants_of("service/XService.java", JAVA, set(mu.OPERATORS))
    ops = _by_op(ms)
    assert "if (a > 10 && a != 0x09CB) {" in ops["ROR"] and "if (a >= 10 && a == 0x09CB) {" in ops["ROR"]
    assert "if (a >= 10 || a != 0x09CB) {" in ops["COR"]
    assert "if (!(a >= 10 && a != 0x09CB)) {" in ops["NEG"]
    assert "return a / 2;" in ops["AOR"] and "count--;" in ops["AOR"]
    assert any(".subtract(" in x for x in ops["BDM"]) and any("RoundingMode.DOWN" in x for x in ops["BDM"])
    assert "if (a >= 11 && a != 0x09CB) {" in ops["CON"] and "if (a >= 10 && a != 0x09CC) {" in ops["CON"]
    assert any('new BigDecimal("X.00")' in x for x in ops["LIT"])
    assert "/* doIt(a); */" in ops["DEL"] and "/* count++; */" in ops["DEL"]
    lines = {m.line for m in ms}
    assert not lines & {1, 3, 5, 7, 10, 11}  # package, import, annotation, the logger, a log call, a comment
    assert not any("List<" in m.after and m.op == "ROR" for m in ms)  # a generic is not a comparison


def test_a_mutant_is_the_port_with_one_change(tmp_path):
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    (port / "service" / "XService.java").write_text(JAVA, encoding="utf-8")
    (port / "provenance.json").write_text("{}", encoding="utf-8")
    (m,) = [x for x in mu.all_mutants(port, {"AOR"}) if x.after == "return a / 2;"]
    out = mu.write_mutant(port, m, tmp_path / "mutant")
    text = (out / "service" / "XService.java").read_text(encoding="utf-8")
    assert text == JAVA.replace("return a * 2;", "return a / 2;") and not (out / "provenance.json").exists()
    assert (port / "service" / "XService.java").read_text(encoding="utf-8") == JAVA  # the port is untouched


def test_the_sample_spreads_over_the_operators_and_is_repeatable():
    ms = mu.mutants_of("x.java", JAVA, set(mu.OPERATORS))
    picked = mu.sample(ms, 8, seed=3)
    assert len(picked) == 8 and len({m.op for m in picked}) == 8
    assert [m.id for m in picked] == [m.id for m in mu.sample(ms, 8, seed=3)]
    assert mu.sample(ms, None, 0) == ms


def test_the_runs_that_killed_a_mutant_are_named_for_each_kind():
    batch = {"environments": [{"ok": True}], "faults": [{"name": "dup", "ok": False}, {"name": "eof", "ok": True}]}
    assert mu.killers(batch) == ["dup"]  # only a fault run saw it
    assert mu.killers({**batch, "environments": [{"ok": False}]}) == ["main", "dup"]
    cics = {"kind": "cics", "outputs": {"a": {"equal": 3, "records": 3, "diffs": []},
                                        "b": {"equal": 2, "records": 3, "diffs": [{}]},
                                        "c": {"equal": 1, "records": 1, "diffs": [],
                                              "fired": {"cobol": ["x"], "java": []}}}}  # fmt: skip
    assert mu.killers(cics) == ["b", "c"]
    assert mu.killers({"kind": "call", "outputs": {"CALLS": {"diffs": [{"record": 4}]}}}) == ["call 4"]
    assert mu.killers({"java_failed": True}) == ["java"]


def test_the_score_counts_timeouts_as_caught_and_stillborn_as_nothing():
    rs = [{"id": str(i), "op": "ROR", "file": "f", "line": i, "before": "a", "after": "b", "verdict": v,
           "killed_by": k} for i, (v, k) in enumerate([("killed", ["main"]), ("killed", ["dup"]), ("timeout", []),
                                                       ("survived", []), ("stillborn", [])])]  # fmt: skip
    md = mu.mutation_md({"case": "c", "program": "P", "mutants": 9, "chosen": 5, "seed": 0, "seconds": 1,
                         "coverage": "proven on 2 runs", "results": rs})  # fmt: skip
    assert "**Score: 3/4 caught (75%)**" in md and "stillborn (javac) 1" in md
    assert "Killed only by fault runs: 1" in md and "- `3` ROR f:3" in md


# ---- --reuse: an earlier run's COBOL side and generated project (the fast mode) ------------------------------
@pytest.fixture
def earlier(tmp_path):
    """An earlier run's --keep directory: a COBOL step and a generated project with a one-file overlay."""
    e = tmp_path / "earlier"
    (e / "cobol").mkdir(parents=True)
    (e / "cobol" / "run.sh").write_text("cobc ...\n", encoding="ascii")
    (e / "cobol" / "OUT.out").write_bytes(b"RECORD")
    project = e / "java" / "java_h2"
    (project / "target" / "classes").mkdir(parents=True)
    (project / ej.OVERLAY_FILE).write_text('["service/XService.java"]\n', encoding="utf-8")
    (e / "report.json").write_text("{}", encoding="utf-8")
    yield e
    common._REUSE = None


def test_a_reused_cobol_step_must_be_the_same_step_else_it_runs_afresh(tmp_path, earlier, monkeypatch):
    runs = []
    monkeypatch.setattr(common, "_docker_run", lambda work, *a: runs.append(work) or subprocess.CompletedProcess([], 0))
    work = tmp_path / "now"
    common.reuse(work, earlier)
    (work / "cobol").mkdir(parents=True)
    (work / "cobol" / "run.sh").write_text("cobc ...\n", encoding="ascii")
    assert common.run_cobol_step(work / "cobol").returncode == 0
    assert (work / "cobol" / "OUT.out").read_bytes() == b"RECORD"  # the earlier step's output, not a new run
    assert not runs
    (work / "cobol" / "run.sh").write_text("cobc -DOTHER ...\n", encoding="ascii")
    common.run_cobol_step(work / "cobol")  # #4476: not the earlier run's step -- run, not copied, not refused
    assert runs == [work / "cobol"]


def test_a_reused_project_must_be_overlaid_with_the_same_files(tmp_path, earlier):
    work = tmp_path / "now" / "java"
    project = ej._reused_project(earlier / "java", work, ["service/XService.java"])
    assert project == work / "java_h2" and (project / "target" / "classes").is_dir()
    with pytest.raises(RuntimeError, match="not the earlier run's"):
        ej._reused_project(earlier / "java", work, [])  # the generated stub, where the earlier had a port
    with pytest.raises(SystemExit):
        common.reuse(work, tmp_path / "nowhere")  # not a finished run


def test_the_test_runs_without_maven_only_on_a_build_of_this_very_source(tmp_path):
    """--reuse runs EquivalenceRunTest in a plain JVM only when the main classes were compiled from the port and
    the test classes from this test source; anything else goes back to Maven (None)."""
    project = tmp_path / "java_h2"
    (project / ej.TEST_FILE).parent.mkdir(parents=True)
    (project / "target").mkdir()
    (project / ej.TEST_FILE).write_text("class EquivalenceRunTest {}", encoding="utf-8")
    shell = {"JAVA_HOME": "/nonexistent"}
    assert ej._run_direct(project, "", shell) is None  # nothing precompiled
    (project / ej.PRECOMPILED).write_text("", encoding="utf-8")
    (project / ej.TEST_CLASSPATH).write_text("/m2/junit-platform-engine/1.10.2/junit-platform-engine-1.10.2.jar")
    (project / ej.TEST_SOURCE).write_text("class EquivalenceRunTest { /* another test */ }", encoding="utf-8")
    assert ej._run_direct(project, "", shell) is None  # the test classes are another source's build
    (project / ej.TEST_SOURCE).write_text("class EquivalenceRunTest {}", encoding="utf-8")
    assert ej._run_direct(project, "", shell) is None  # the launcher jar is not in the local repository
    assert ej._launcher(["/m2/junit-platform-engine/1.10.2/junit-platform-engine-1.10.2.jar"]) is None
    jar = tmp_path / "m2/junit-platform-launcher/1.10.2/junit-platform-launcher-1.10.2.jar"
    jar.parent.mkdir(parents=True)
    jar.write_bytes(b"")
    engine = (tmp_path / "m2/junit-platform-engine/1.10.2/junit-platform-engine-1.10.2.jar").as_posix()
    assert ej._launcher(["/x/classes", engine]) == jar


def test_the_launcher_is_found_from_a_windows_backslash_classpath(tmp_path):
    """#4934: surefire's classpath on Windows has backslash entries; the direct path must still find the launcher
    (it fell back to Maven on every run there)."""
    jar = tmp_path / "m2/junit-platform-launcher/1.10.2/junit-platform-launcher-1.10.2.jar"
    jar.parent.mkdir(parents=True)
    jar.write_bytes(b"")
    engine = f"{tmp_path}/m2/junit-platform-engine/1.10.2/junit-platform-engine-1.10.2.jar".replace("/", "\\")
    assert ej._launcher([engine]) == jar


def test_runs_after_the_first_maven_run_take_the_direct_path_with_mavens_classpath_and_flags(tmp_path, monkeypatch):
    """#4910: the first run of a project builds it through Maven; every later run (a fault, an environment, an entry,
    the facade side) is a fresh plain JVM on the classpath surefire ran the first on, with the same flags and cwd."""
    import shlex

    project = tmp_path / "java_h2"
    (project / ej.TEST_FILE).parent.mkdir(parents=True)
    (project / ej.TEST_FILE).write_text("class EquivalenceRunTest {}", encoding="utf-8")
    (project / "target" / "classes").mkdir(parents=True)
    (project / "target" / "surefire-reports").mkdir()
    m2 = tmp_path / "m2"
    engine = m2 / "junit-platform-engine/1.10.2/junit-platform-engine-1.10.2.jar"
    launcher = m2 / "junit-platform-launcher/1.10.2/junit-platform-launcher-1.10.2.jar"
    for jar in (engine, launcher):
        jar.parent.mkdir(parents=True)
        jar.write_bytes(b"")
    surefire_cp = os.pathsep.join([str(project / "target/test-classes"), str(project / "target/classes"), str(engine)])
    (project / "target/surefire-reports/TEST-x.xml").write_text(
        f'<testsuite><properties><property name="surefire.test.class.path" value="{surefire_cp}"/>'
        "</properties></testsuite>", encoding="utf-8")  # fmt: skip
    java_home = tmp_path / "jdk"
    runner = tmp_path / "runner"
    monkeypatch.setattr(ej.jtm, "_jdk", lambda _v: str(java_home))
    monkeypatch.setattr(ej, "_runner", lambda *_a: runner)
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(ej.subprocess, "run", fake_run)
    inputs = tmp_path / "in"
    work1 = work2 = tmp_path / "w"  # (the run areas differ only in the paths the harness gives them)
    ej.run_maven(project, work1, inputs, props="-Dgitgalaxy.faults.plan=a")
    ej.run_maven(project, work2, inputs, props="-Dgitgalaxy.faults.plan=b")
    (mvn, mvn_kw), (java, java_kw) = calls
    assert mvn[0] == mvn_executable() and java[0] == str(
        java_home / "bin" / "java"
    )  # the first run builds, the second is direct
    maven_flags = ej.split_argline(next(a for a in mvn if a.startswith("-DargLine="))[len("-DargLine=") :])
    assert maven_flags[-1] == "-Dgitgalaxy.faults.plan=a"
    utf8 = ["-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8"]  # #5128: the direct java names its charset itself
    assert java[1:3] == utf8
    n = len(utf8)
    assert (
        java[1 + n : 1 + n + len(maven_flags) - 1] == maven_flags[:-1]
    )  # the same JVM flags and properties, but the run's
    assert java[n + len(maven_flags)] == "-Dgitgalaxy.faults.plan=b"
    assert java[-3:] == ["-cp", os.pathsep.join([surefire_cp, str(launcher), str(runner)]), "EquivalenceMain"]
    assert java_kw["cwd"] == mvn_kw["cwd"] == project  # the same working directory
    assert java_kw["timeout"] == ej.JAVA_DIRECT_TIMEOUT
