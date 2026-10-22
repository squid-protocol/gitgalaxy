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
import mutation_crucible as mc
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
    assert maven_flags[:2] == utf8  # #5161: so does surefire's fork
    assert "text" not in mvn_kw and "-Dfile.encoding=UTF-8" in mvn_kw["env"]["MAVEN_OPTS"]
    maven_flags = maven_flags[2:]
    assert java[1:3] == utf8
    n = len(utf8)
    assert (
        java[1 + n : 1 + n + len(maven_flags) - 1] == maven_flags[:-1]
    )  # the same JVM flags and properties, but the run's
    assert java[n + len(maven_flags)] == "-Dgitgalaxy.faults.plan=b"
    assert java[-3:] == ["-cp", os.pathsep.join([surefire_cp, str(launcher), str(runner)]), "EquivalenceMain"]
    assert java_kw["cwd"] == mvn_kw["cwd"] == project  # the same working directory
    assert java_kw["timeout"] == ej.JAVA_DIRECT_TIMEOUT


# ---- --one-jvm: all the runs of one proof in one JVM -----------------------------------------------------------------
FAKE_JVM = f"""import sys, time
for line in sys.stdin:
    line = line.rstrip("\\n")
    if line == "quit":
        break
    if "die" in line:
        sys.exit(3)
    if "hang" in line:
        time.sleep(60)
    print("props=" + repr(line.split("\\t")), flush=True)
    print("{ej.RUN_DONE} " + ("1" if "fail=1" in line else "0"), flush=True)
"""


@pytest.fixture
def fake_session(tmp_path):
    script = tmp_path / "fake_jvm.py"
    script.write_text(FAKE_JVM, encoding="utf-8")
    made = []

    def start():
        s = ej.JvmSession([sys.executable, str(script)], tmp_path, dict(os.environ))
        made.append(s)
        return s

    yield start
    for s in made:
        s.close()


def test_a_session_jvm_runs_one_proof_run_per_line_with_that_runs_properties(fake_session):
    s = fake_session()
    a = s.run("-Dequivalence.out=/o/1 -Dgitgalaxy.faults.plan=/p", 20)
    b = s.run("-Dequivalence.out=/o/2 -Dfail=1", 20)
    assert (a.returncode, b.returncode) == (0, 1)  # the run's own verdict, not the JVM's
    assert a.stdout.strip() == "props=['equivalence.out=/o/1', 'gitgalaxy.faults.plan=/p']"
    assert "/o/1" not in b.stdout and "equivalence.out=/o/2" in b.stdout  # each run's output is its own


def test_a_session_run_that_hangs_or_kills_the_jvm_is_a_failed_run_not_a_hang(fake_session):
    s = fake_session()
    hung = s.run("-Dx=hang", 1)
    assert hung.returncode == 124 and "timed out" in hung.stderr
    died = fake_session().run("-Dx=die", 20)  # the JVM exits before RUN_DONE
    assert died.returncode == 3 and "ended before the run finished" in died.stderr


def _env_run(monkeypatch, tmp_path, case, envs, one_jvm=True, stop=None):
    sessions, seen = [], []

    class Fake:
        closed = False

        def close(self):
            self.closed = True

    monkeypatch.setattr(ej, "prepare_project", lambda *a, **k: tmp_path)
    monkeypatch.setattr(ej, "equivalence_test", lambda c: "")
    monkeypatch.setattr(ej, "start_session", lambda project, env: sessions.append(Fake()) or sessions[-1])

    def area(case_, project, area_, inputs, env, props="", session=None):
        seen.append((env["name"], props.split()[0] if props else "", session))
        return {"RETURN-CODE": b"0"}

    monkeypatch.setattr(ej, "_run_area", area)
    runs = ej.run_java_environments(
        case,
        tmp_path,
        tmp_path,
        tmp_path,
        envs,
        faults=(("f1", "plan"), ("f2", "plan")),
        entries=("E1",),
        one_jvm=one_jvm,
        stop=stop,
    )
    return runs, sessions, seen


def test_one_jvm_carries_the_first_environments_runs_and_the_other_environments_get_a_jvm_each(monkeypatch, tmp_path):
    envs = [ej.environment("default"), ej.environment("turkish")]
    runs, sessions, seen = _env_run(monkeypatch, tmp_path, {"datasets": {}}, envs)
    assert list(runs) == ["default", "turkish", "fault:f1", "fault:f2", "entry:E1"]
    assert len(sessions) == 1 and sessions[0].closed  # one JVM, closed when the proof ends
    by_run = {(n, p): s for n, p, s in seen}
    assert by_run[("default", "")] is sessions[0] and by_run[("turkish", "")] is None
    assert all(s is sessions[0] for n, p, s in seen if p)  # every fault and entry run is in it


def test_one_jvm_is_off_by_default_and_for_db2_and_ims_cases(monkeypatch, tmp_path):
    envs = [ej.environment("default")]
    for case, one_jvm in (({"datasets": {}}, False), ({"datasets": {}, "db2": {"tables": []}}, True),
                          ({"datasets": {}, "ims": {"compare": []}}, True)):  # fmt: skip
        _, sessions, seen = _env_run(monkeypatch, tmp_path, case, envs, one_jvm)
        assert not sessions and all(s is None for _n, _p, s in seen)


def test_first_difference_ends_a_one_jvm_proof_where_it_ends_a_jvm_per_run_proof(monkeypatch, tmp_path):
    envs = [ej.environment("default")]
    runs, sessions, _ = _env_run(monkeypatch, tmp_path, {"datasets": {}}, envs, stop=lambda n, _o: n == "fault:f1")
    assert list(runs) == ["default", "fault:f1"] and sessions[0].closed


def test_the_session_runner_and_the_test_it_runs_are_made_for_repeated_runs():
    assert "--session" in ej.RUNNER and ej.RUN_DONE in ej.RUNNER and "System.clearProperty" in ej.RUNNER
    case = {"program": "X", "name": "x", "datasets": {}, "clock": "2024/01/02 03:04:05.00"}
    assert "@DirtiesContext" in ej.equivalence_test(case)  # a second run in the JVM never meets the first's context


class _FakeHolder:
    def __init__(self):
        self.closed, self.session = False, object()

    def get(self):
        return self.session

    def close(self):
        self.closed = True


@pytest.mark.parametrize("case,one_jvm,expect", [({}, True, True), ({}, False, False), ({"db2": {"tables": []}}, True, False),
                                                 ({"ims": {"compare": []}}, True, False)])  # fmt: skip
def test_sessions_for_is_the_one_rule_of_who_gets_a_session_jvm(tmp_path, case, one_jvm, expect):
    import equivalence_call as ecall

    assert bool(ecall.sessions_for(case, tmp_path, one_jvm)) is expect


def _recording_maven(monkeypatch):
    seen = []
    monkeypatch.setattr(ej, "run_maven", lambda project, work, inputs, env=None, props="", session=None:
                        seen.append((work.name, props, session)) or work / "out")  # fmt: skip
    return seen


@pytest.mark.parametrize("one_jvm", [True, False])
def test_a_call_proofs_run_goes_through_the_session_only_under_one_jvm(monkeypatch, tmp_path, one_jvm):
    import equivalence_call as ecall

    holders = []
    monkeypatch.setattr(
        ecall, "sessions_for", lambda *a: holders.append(_FakeHolder()) or holders[-1] if a[2] else None
    )
    seen = _recording_maven(monkeypatch)
    out = ecall._run_calls(ej, {"datasets": {}}, tmp_path, tmp_path / "w", tmp_path, one_jvm)
    assert out == tmp_path / "w" / "out" and len(seen) == 1
    assert (seen[0][2] is holders[0].session and holders[0].closed) if one_jvm else (seen[0][2] is None)


def test_a_cics_proofs_task_run_and_facade_run_share_one_session_that_is_closed(monkeypatch, tmp_path):
    import equivalence_cics as ec

    holder = _FakeHolder()
    seen = _recording_maven(monkeypatch)
    monkeypatch.setattr(ec, "_java_events", lambda *a: {})
    facade = {}
    ec._run_facade(ej, tmp_path, tmp_path / "w", tmp_path, "-Dp=1", holder, {"scenarios": []}, None, None, facade)
    assert seen == [("facade", "-Dp=1 -Dequivalence.facades=true", holder.session)] and facade["events"] == {}


def test_a_facade_run_that_fails_is_the_facades_error_not_a_crash(monkeypatch, tmp_path):
    import equivalence_cics as ec

    def boom(*a, **k):
        raise RuntimeError("no go")

    monkeypatch.setattr(ej, "run_maven", boom)
    facade = {}
    ec._run_facade(ej, tmp_path, tmp_path / "w", tmp_path, "", None, {"scenarios": []}, None, None, facade)
    assert facade == {"error": "no go"}


def test_the_call_and_cics_tests_are_made_for_a_second_run_in_the_session_jvm():
    import equivalence_call as ecall
    import equivalence_cics as ec

    case = {"program": "X", "name": "x", "datasets": {}, "using": [], "calls": [], "clock": "2024/01/02 03:04:05.00"}
    assert "@DirtiesContext" in ecall.java_test(case) and "@DirtiesContext" in ecall.java_test_dto(
        case, ["CobolRef<String>"]
    )
    import inspect

    assert "@DirtiesContext" in inspect.getsource(ec.cics_equivalence_test)


def _run(mode, verdicts):
    return {"mode": mode, "results": [{"id": f"m{i}", "op": op, "line": i, "verdict": v, "seconds": s}
                                      for i, (op, v, s) in enumerate(verdicts)]}  # fmt: skip


def test_compare_counts_killed_and_timeout_as_one_and_names_every_difference_by_operator():
    full = _run(
        "full", [("NEG", "killed", 100), ("CMP", "survived", 90), ("CMP", "timeout", 80), ("LIT", "stillborn", 1)]
    )
    fast = _run(
        "fast", [("NEG", "timeout", 10), ("CMP", "survived", 20), ("CMP", "survived", 20), ("LIT", "stillborn", 1)]
    )
    got = mu.compare(full, fast)
    assert got["judged_by_both"] == 4 and got["agree"] == 3
    assert [d["id"] for d in got["differ"]] == ["m2"]
    assert got["by_operator"]["CMP"] == {"judged": 2, "differ": 1} and got["by_operator"]["NEG"]["differ"] == 0
    assert got["survivor_proof_seconds"] == {"full": 170, "fast": 40}  # a survivor in either run


def test_compare_leaves_out_a_mutant_that_is_pending_in_either_run():
    got = mu.compare(
        _run("a", [("NEG", "killed", 1), ("NEG", "pending", 0)]),
        _run("b", [("NEG", "killed", 1), ("NEG", "killed", 1)]),
    )
    assert got["judged_by_both"] == 1 and not got["differ"]


@pytest.mark.parametrize("judged,differ,minimum,ok", [(12, [], None, True), (12, [], 12, True), (11, [], 12, False),
                                                      (12, [{"id": "m1"}], 12, False), (3, [{"id": "m1"}], None, True)])  # fmt: skip
def test_the_agreement_gate_needs_enough_mutants_judged_and_no_difference(judged, differ, minimum, ok):
    assert mu.agreement_gate({"judged_by_both": judged, "differ": differ}, minimum) is ok


@pytest.mark.parametrize("flags,expect", [([], True), (["--one-jvm"], True), (["--no-one-jvm"], False), (["--full"], False),
                                          (["--record"], True)])  # fmt: skip
def test_the_session_jvm_is_the_fast_default_and_off_for_full(monkeypatch, tmp_path, flags, expect):
    seen = {}

    def fake_run(*args, **kw):
        seen.update(kw, full=args[8])
        return {}

    monkeypatch.setattr(mu, "run", fake_run)
    monkeypatch.setattr(mu, "mutation_md", lambda s: "")
    monkeypatch.setitem(sys.modules, "mutation_scores", type("S", (), {"record_run": staticmethod(lambda *a: None)}))
    assert mu.main(["run", "carddemo-intcalc", "--work", str(tmp_path), *flags]) == 0
    assert seen["one_jvm"] is expect and seen["full"] is ("--full" in flags)


def test_one_jvm_with_full_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="fast-mode option"):
        mu.main(["run", "carddemo-intcalc", "--work", str(tmp_path), "--full", "--one-jvm"])


def test_a_reused_project_carries_the_stubs_the_earlier_overlay_replaced(tmp_path, earlier):
    """#4047: a LINKed program is translated from its generated stub; the reused project's file is the earlier run's
    translation, and translating that lost the program's CICS file stores (cbsa-inqacc: ABNDPROC, 9 false kills)."""
    kept = earlier / "java" / ej.GENERATED_KEEP / "service"
    kept.mkdir(parents=True)
    (kept / "XService.java").write_text("// the stub\n", encoding="utf-8")
    work = tmp_path / "now" / "java"
    ej._reused_project(earlier / "java", work, ["service/XService.java"])
    assert (work / ej.GENERATED_KEEP / "service" / "XService.java").read_text(encoding="utf-8") == "// the stub\n"


@pytest.mark.parametrize("reused", [False, True])
def test_a_linked_program_is_translated_from_the_stub_also_on_reuse(tmp_path, monkeypatch, reused):
    P = pytest.importorskip("gitgalaxy.tools.cobol_to_java.det.program")
    project = tmp_path / "java" / "java_h2"
    rel = "service/AbndprocService.java"
    (project / "src/main/java" / ej.PKG_DIR / "service").mkdir(parents=True)
    (project / "src/main/java" / ej.PKG_DIR / rel).write_text("// translated by the earlier run\n" if reused else "// stub\n",
                                                              encoding="utf-8")  # fmt: skip
    if reused:
        (project.parent / ej.GENERATED_KEEP / "service").mkdir(parents=True)
        (project.parent / ej.GENERATED_KEEP / rel).write_text("// stub\n", encoding="utf-8")
    seen = []

    def translate(source, dirs, stub, *a, **kw):
        seen.append(stub)
        return type("R", (), {"java": "// out\n", "extra": []})()

    monkeypatch.setattr(P, "translate", translate)
    monkeypatch.setattr(P, "estate_files", lambda p: {})
    monkeypatch.setattr(P, "runtime_files", lambda *a: {})
    monkeypatch.setattr(P, "has_batch", lambda p: False)
    monkeypatch.setattr(ej, "CASES", tmp_path / "no-cases")
    case = {"programs": [{"program": "ABNDPROC", "program_source": "abndproc.cbl"}]}
    files, origins = ej.linked_programs(case, tmp_path, project, {}, tmp_path / "work")
    assert seen == ["// stub\n"] and rel in files and "det port" in origins["ABNDPROC"]


def test_crucible_prove_command_passes_the_forge_cache_only_in_fast_mode_and_strengthened_by_the_flag(monkeypatch):
    ov, out = Path("ov"), Path("out")
    full = mc.prove_command("pc-wizard", "PCWIZ", ov, out)
    assert "--forge-cache" not in full and "--strengthened" not in full
    assert full[full.index("--sides") + 1 : full.index("--overlay")] == ["java-ported", "java-facade"]
    fast = mc.prove_command("pc-wizard", "PCWIZ", ov, out, Path("cache"))
    assert fast[fast.index("--forge-cache") + 1] == "cache"
    monkeypatch.setattr(mc, "STRENGTHENED", True)
    assert "--strengthened" in mc.prove_command("pc-wizard", "PCWIZ", ov, out)


def test_crucible_verdict_tells_survived_stillborn_killed_and_timeout_apart():
    assert mc.verdict(0, {"proven": True}) == ("survived", [])
    assert mc.verdict(None, None) == ("timeout", [])
    broken = {"cells": {"a/s1": {"kind": mc.NOT_COMPILED, "status": "fail"}}}
    assert mc.verdict(1, broken) == ("stillborn", [])
    hit = {"cells": {"java-ported/s2": {"status": "fail"}, "java-ported/s1": {"status": "pass"}}}
    assert mc.verdict(1, hit) == ("killed", ["s2"])
