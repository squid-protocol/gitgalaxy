"""#4052 slice 1: golden export of a case's COBOL outputs, and the byte-exact check of a Java run against it."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import golden_export as g

CASE = {"name": "demo", "program": "DEMO"}
MAIN_RUN = {"OUT": b"AB\x00\xc1\n" * 3, "RETURN-CODE": b"0\n", "SYSOUT": b"hi\n"}
FAULT_RUN = {"OUT": b"", "ABEND": b"U0016\n", "FAULTS": b"OUT READ 1\n"}


def _java(tmp: Path, runs: dict) -> Path:
    for name, files in runs.items():
        (tmp / name).mkdir(parents=True)
        for k, v in files.items():
            (tmp / name / k).write_bytes(v)
    return tmp


@pytest.fixture
def golden(tmp_path):
    d = tmp_path / "golden"
    g.export(CASE, {"main": MAIN_RUN, "fault-x": FAULT_RUN}, d, "cp037")
    return d


def test_export_writes_bytes_hashes_and_status(golden):
    m = g.json.loads((golden / "golden.json").read_text())
    assert m["data_encoding"] == "cp037"
    assert m["runs"]["main"]["return_code"] == "0"
    assert m["runs"]["main"]["outputs"]["OUT"]["bytes"] == 15
    assert m["runs"]["fault-x"]["abend"] == "U0016"
    assert (golden / "main" / "OUT").read_bytes() == MAIN_RUN["OUT"]
    assert "RETURN-CODE" not in m["runs"]["main"]["outputs"]


def test_a_byte_identical_java_run_passes(golden, tmp_path):
    java = _java(tmp_path / "j", {"main": MAIN_RUN, "fault-x": {"ABEND": b"U0016\n", "FAULTS": b"x"}})
    assert g.check(golden, java) == []


def test_one_changed_byte_is_named_with_its_offset(golden, tmp_path):
    bad = dict(MAIN_RUN, OUT=MAIN_RUN["OUT"][:7] + b"Z" + MAIN_RUN["OUT"][8:])
    java = _java(tmp_path / "j", {"main": bad, "fault-x": {"ABEND": b"U0016\n"}})
    assert g.check(golden, java) == ["main/OUT: differs at byte 7 (Java 15 bytes, golden 15)"]


def test_return_code_abend_missing_and_extra_outputs_all_fail(golden, tmp_path):
    java = _java(
        tmp_path / "j", {"main": {"RETURN-CODE": b"8\n", "EXTRA": b"x"}, "fault-x": {"RETURN-CODE": b"0\n", "OUT": b""}}
    )
    got = g.check(golden, java)
    assert "main: return code '8', golden '0'" in got
    assert "main/OUT: missing from the Java run" in got
    assert "main/EXTRA: a Java output the golden run does not have" in got
    assert "fault-x: abend None, golden 'U0016'" in got


def test_a_run_missing_from_java_and_a_tampered_golden_file_fail(golden, tmp_path):
    (golden / "main" / "OUT").write_bytes(b"tampered")
    java = _java(tmp_path / "j", {"main": MAIN_RUN})
    got = g.check(golden, java)
    assert "main/OUT: the golden file no longer matches its manifest hash" in got
    assert "fault-x: the Java run has no outputs" in got


def test_an_abended_run_does_not_compare_its_datasets(golden, tmp_path):
    java = _java(tmp_path / "j", {"main": MAIN_RUN, "fault-x": {"ABEND": b"U0016\n", "OUT": b"junk"}})
    assert g.check(golden, java) == []


def test_export_needs_the_main_run_and_a_plain_dd_name(tmp_path):
    with pytest.raises(ValueError):
        g.export(CASE, {"fault-x": FAULT_RUN}, tmp_path / "a")
    with pytest.raises(ValueError):
        g.export(CASE, {"main": {"../X": b""}}, tmp_path / "b")


def test_cli_check_exit_codes(golden, tmp_path, capsys):
    java = _java(tmp_path / "j", {"main": MAIN_RUN, "fault-x": {"ABEND": b"U0016\n"}})
    assert g.main(["check", str(golden), "--java", str(java)]) == 0
    (java / "main" / "OUT").write_bytes(b"")
    assert g.main(["check", str(golden), "--java", str(java)]) == 1
    assert "DIFFERS" in capsys.readouterr().out


def test_junit_writes_index_and_both_classes(golden, tmp_path):
    written = g.write_junit(golden, tmp_path / "src", "com.acme.golden")
    names = {p.name for p in written}
    assert names == {"golden.index", "GoldenCheck.java", "GoldenRegressionTest.java"}
    index = (golden / "golden.index").read_text().splitlines()
    assert index[0] == "R\tfault-x\tU0016\t"
    assert any(line.startswith("O\tmain\tOUT\t") for line in index)
    test_src = (tmp_path / "src/com/acme/golden/GoldenRegressionTest.java").read_text()
    assert "package com.acme.golden;" in test_src and "demo" in test_src and "__" not in test_src
    assert "__" not in (tmp_path / "src/com/acme/golden/GoldenCheck.java").read_text()
    with pytest.raises(ValueError):
        g.write_junit(golden, tmp_path / "x", "a-b")


@pytest.mark.skipif(not shutil.which("javac") or not shutil.which("java"), reason="needs a JDK")
def test_the_generated_java_check_agrees_with_the_python_check(golden, tmp_path):
    """The same messages, in the same order, for a run that differs in every way `check` can name."""
    g.write_junit(golden, tmp_path / "src", "golden")
    classes = tmp_path / "classes"
    classes.mkdir()
    done = subprocess.run(
        ["javac", "-encoding", "UTF-8", "-d", str(classes), str(tmp_path / "src/golden/GoldenCheck.java")],
        capture_output=True,
        encoding="utf-8",
    )
    assert done.returncode == 0, done.stderr
    (tmp_path / "Run.java").write_text(
        "import java.nio.file.Path;\n"
        "public class Run { public static void main(String[] a) throws Exception {\n"
        "  for (String p : golden.GoldenCheck.problems(Path.of(a[0]), Path.of(a[1]))) System.out.println(p);\n"
        "} }\n"
    )
    javac = subprocess.run(
        ["javac", "-encoding", "UTF-8", "-cp", str(classes), "-d", str(classes), str(tmp_path / "Run.java")],
        capture_output=True,
        encoding="utf-8",
    )
    assert javac.returncode == 0, javac.stderr
    bad = dict(MAIN_RUN, OUT=MAIN_RUN["OUT"][:7] + b"Z" + MAIN_RUN["OUT"][8:])
    cases = {
        "same": {"main": MAIN_RUN, "fault-x": {"ABEND": b"U0016\n", "FAULTS": b"x"}},
        "byte": {"main": bad, "fault-x": {"ABEND": b"U0016\n"}},
        "rc": {"main": {"RETURN-CODE": b"8\n", "EXTRA": b"x"}, "fault-x": {"RETURN-CODE": b"0\n", "OUT": b""}},
        "norun": {"main": MAIN_RUN},
        "abended-junk": {"main": MAIN_RUN, "fault-x": {"ABEND": b"U0016\n", "OUT": b"junk"}},
    }
    for label, runs in cases.items():
        java = _java(tmp_path / label, runs)
        out = subprocess.run(
            [
                "java",
                "-Dfile.encoding=UTF-8",
                "-Dstdout.encoding=UTF-8",
                "-cp",
                str(classes),
                "Run",
                str(golden),
                str(java),
            ],
            capture_output=True,
        )
        assert out.returncode == 0, out.stderr.decode("utf-8")
        assert out.stdout.decode("utf-8").splitlines() == g.check(golden, java), label


def test_java_run_names_map_to_golden_runs():
    assert g.java_run_name("default") == "main"
    assert g.java_run_name("fault:OUT-READ") == "fault-OUT-READ"
    assert g.java_run_name("entry:run") is None and g.java_run_name("env-x") is None


def test_write_java_out_lays_runs_out_as_check_reads_them(golden, tmp_path):
    runs = {"default": MAIN_RUN, "fault:x": {"ABEND": b"U0016\n", "FAULTS": b"x"}, "entry:run": {"OUT": b"no"}}
    out = tmp_path / "target" / "golden-java-out"
    assert g.write_java_out(runs, out) == ["main", "fault-x"]
    assert not (out / "entry:run").exists()
    assert g.check(golden, out) == []
    (out / "main" / "OUT").write_bytes(b"mutant")
    assert g.check(golden, out) != []


def test_install_project_copies_golden_files_and_writes_the_classes(golden, tmp_path):
    project = tmp_path / "proj"
    written = g.install_project(golden, project, "com.acme.golden")
    res = project / "src/test/resources/golden/demo"
    assert (res / "golden.json").is_file() and (res / "main" / "OUT").read_bytes() == MAIN_RUN["OUT"]
    assert (res / "golden.index").is_file()
    assert (project / "src/test/java/com/acme/golden/GoldenRegressionTest.java") in written
    stale = res / "stale"
    stale.write_text("x")
    g.install_project(golden, project, "com.acme.golden")
    assert not stale.exists()


def test_killed_ids_reads_the_committed_ledger_and_is_empty_for_an_unknown_case():
    assert g.killed_ids("no-such-case") == set()
    assert g.killed_ids("carddemo-readcust")  # the ledger the prove-mutant command trusts


def test_find_mutants_names_the_missing_id(tmp_path):
    (tmp_path / "service").mkdir()
    (tmp_path / "service" / "A.java").write_text("class A { boolean f(int x) { return x == 0; } }\n")
    import mutation

    (m,) = [m for m in mutation.mutants_of("service/A.java", (tmp_path / "service/A.java").read_text(), {"ROR"})][:1]
    assert g.find_mutants(tmp_path, [m.id])[m.id].file == "service/A.java"
    with pytest.raises(SystemExit, match="no mutant ffffffffff"):
        g.find_mutants(tmp_path, ["ffffffffff"])


def test_prove_mutant_refuses_a_mutant_the_proof_does_not_kill(tmp_path):
    with pytest.raises(SystemExit, match="not recorded as killed"):
        g._prove_mutants("carddemo-readcust", tmp_path, ["0000000000"], "none", tmp_path / "out")


@pytest.mark.skipif(not shutil.which("javac") or not shutil.which("java"), reason="needs a JDK")
def test_the_generated_java_check_fails_a_mutated_run_like_the_python_check(golden, tmp_path):
    good = _java(tmp_path / "good", {"main": MAIN_RUN, "fault-x": {"ABEND": b"U0016\n"}})
    mutant = _java(tmp_path / "mut", {"main": dict(MAIN_RUN, OUT=b"x"), "fault-x": {"ABEND": b"U0016\n"}})
    ok, bad = g.java_problems(golden, [good, mutant], tmp_path / "scratch_java")
    assert ok == [] and bad == g.check(golden, mutant) != []


@pytest.mark.skipif(not shutil.which("javac") or not shutil.which("java"), reason="needs a JDK")
def test_an_abended_run_still_compares_its_job_log(tmp_path):
    """#4052 slice 4: the proof compares SYSOUT after an abend too (dc6a5c3575 differed only there), so does the check,
    in Python and in the generated Java; the datasets of an abended run stay uncompared."""
    fault = dict(FAULT_RUN, SYSOUT=b"FILE STATUS IS: 30\n")
    gold = tmp_path / "golden"
    g.export(CASE, {"main": MAIN_RUN, "fault-x": fault}, gold, "cp037")
    runs = {
        "same": {"main": MAIN_RUN, "fault-x": dict(fault, OUT=b"junk")},
        "log": {"main": MAIN_RUN, "fault-x": dict(fault, SYSOUT=b"FILE STATUS IS: 32\n")},
        "nolog": {"main": MAIN_RUN, "fault-x": {"ABEND": b"U0016\n"}},
    }
    dirs = {label: _java(tmp_path / label, r) for label, r in runs.items()}
    want = {label: g.check(gold, d) for label, d in dirs.items()}
    assert want["same"] == []
    assert any("fault-x/SYSOUT" in p for p in want["log"]) and any("fault-x/SYSOUT" in p for p in want["nolog"])
    assert g.java_problems(gold, list(dirs.values()), tmp_path / "scratch") == list(want.values())
