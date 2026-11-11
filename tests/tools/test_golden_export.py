"""#4052 slice 1: golden export of a case's COBOL outputs, and the byte-exact check of a Java run against it."""

import json
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


JDK = pytest.mark.skipif(not shutil.which("javac") or not shutil.which("java"), reason="needs a JDK")


def _java_agrees(golden, tmp_path, cases):
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


def test_one_jvm_reaches_the_java_runs_and_a_mutant_reuses_the_first_projects_estate(tmp_path, monkeypatch):
    """#4052 slice 11: `--one-jvm` reaches the harness for every port (off by default), and every port after the first
    is run with the first's work dir as its --reuse source (not regenerated), cleared afterwards."""
    import equivalence
    import equivalence_java as ej
    import mainframe_corpus as mc

    common = equivalence.equivalence_common
    case = {**CASE, "corpus": "c", "datasets": {}}
    seen, bounds = [], []

    def fake_java(case, corpus, work, *a, **k):
        work.mkdir(parents=True)
        seen.append((work.name, k.get("one_jvm"), common.reused(work)))
        bounds.append(ej.JAVA_DIRECT_TIMEOUT)
        return {}

    monkeypatch.setattr(equivalence, "load_case", lambda n: case)
    monkeypatch.setattr(equivalence, "build_image", lambda: None)
    monkeypatch.setattr(equivalence, "selected_faults", lambda c, f: [])
    monkeypatch.setattr(equivalence, "run_cobol", lambda *a, **k: dict(MAIN_RUN))
    monkeypatch.setattr(mc, "select", lambda names: [object()])
    monkeypatch.setattr(mc, "require_clone", lambda e: tmp_path)
    monkeypatch.setattr(ej, "run_java_environments", fake_java)
    for flag in (False, True):
        w = tmp_path / str(flag)
        g._run_ports("demo", "none", {"a": None, "b": None}, w, tmp_path / f"g{flag}", flag)
        assert common._REUSE is None
        assert seen[-2:] == [("a", flag, None), ("b", flag, (w / "java" / "a").resolve())]

    before = ej.JAVA_DIRECT_TIMEOUT
    bounds.clear()
    g._run_ports("demo", "none", {"a": None, "b": None, "c": None}, tmp_path / "t", tmp_path / "gt", False, 7)
    assert bounds == [before, 7, 7] and ej.JAVA_DIRECT_TIMEOUT == before


def test_the_project_and_prove_mutant_golden_carries_the_record_layouts(tmp_path, monkeypatch):
    """#4052: `_run_ports` (behind `project` and `prove-mutant`) exports the golden with the case's field layouts, as
    `export` does; without them a FILLER-only dataset (posttran TCATBALF) was judged byte-exact there."""
    import equivalence
    import equivalence_java as ej
    import mainframe_corpus as mc

    case = {**CASE, "corpus": "c", "datasets": {"OUT": {"compare": True, "copybook": "x.cpy", "reclen": 4}}}
    fields = [{"name": "A", "offset": 0, "length": 4}]
    monkeypatch.setattr(equivalence, "load_case", lambda n: case)
    monkeypatch.setattr(equivalence, "build_image", lambda: None)
    monkeypatch.setattr(equivalence, "selected_faults", lambda c, f: [])
    monkeypatch.setattr(equivalence, "run_cobol", lambda *a, **k: dict(MAIN_RUN))
    monkeypatch.setattr(mc, "select", lambda names: [object()])
    monkeypatch.setattr(mc, "require_clone", lambda e: tmp_path)
    monkeypatch.setattr(ej, "run_java_environments", lambda case, corpus, work, *a, **k: work.mkdir(parents=True) or {})
    monkeypatch.setattr(equivalence.equivalence_common, "layout_fields", lambda *a, **k: fields)
    g._run_ports("demo", "none", {"a": None}, tmp_path / "w", tmp_path / "g")
    manifest = json.loads((tmp_path / "g" / g.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["records"] == {"OUT": {"reclen": 4, "fields": fields}}


def test_a_mutant_whose_java_run_hangs_is_a_failing_run_not_an_abort(tmp_path, monkeypatch):
    """#4052 slice 11: the harness raises when a run times out or crashes; for a mutant that is a kill with a reason
    (a hung `fault-sortin-eof` run aborted a whole prove-mutant after 1200 s, no verdict); the first port still raises."""
    import equivalence
    import equivalence_java as ej
    import mainframe_corpus as mc

    case = {**CASE, "corpus": "c", "datasets": {}}

    def fake_java(case, corpus, work, *a, **k):
        work.mkdir(parents=True)
        if work.name != "a":
            raise RuntimeError(f"Java side failed (see {work}/maven.log):\nx\njava EquivalenceMain timed out after 7s")
        return {"default": {}}

    monkeypatch.setattr(equivalence, "load_case", lambda n: case)
    monkeypatch.setattr(equivalence, "build_image", lambda: None)
    monkeypatch.setattr(equivalence, "selected_faults", lambda c, f: [])
    monkeypatch.setattr(equivalence, "run_cobol", lambda *a, **k: dict(MAIN_RUN))
    monkeypatch.setattr(mc, "select", lambda names: [object()])
    monkeypatch.setattr(mc, "require_clone", lambda e: tmp_path)
    monkeypatch.setattr(ej, "run_java_environments", fake_java)
    got = g._run_ports("demo", "none", {"a": None, "b": None}, tmp_path / "w", tmp_path / "g")
    assert got["a"] == {"default": {}} and got["b"] == "java EquivalenceMain timed out after 7s"
    with pytest.raises(RuntimeError, match="timed out"):
        g._run_ports("demo", "none", {"b": None, "a": None}, tmp_path / "w2", tmp_path / "g2")


@JDK
def test_the_generated_java_check_agrees_with_the_python_check(golden, tmp_path):
    """The same messages, in the same order, for a run that differs in every way `check` can name."""
    bad = dict(MAIN_RUN, OUT=MAIN_RUN["OUT"][:7] + b"Z" + MAIN_RUN["OUT"][8:])
    cases = {
        "same": {"main": MAIN_RUN, "fault-x": {"ABEND": b"U0016\n", "FAULTS": b"x"}},
        "byte": {"main": bad, "fault-x": {"ABEND": b"U0016\n"}},
        "rc": {"main": {"RETURN-CODE": b"8\n", "EXTRA": b"x"}, "fault-x": {"RETURN-CODE": b"0\n", "OUT": b""}},
        "norun": {"main": MAIN_RUN},
        "abended-junk": {"main": MAIN_RUN, "fault-x": {"ABEND": b"U0016\n", "OUT": b"junk"}},
    }
    _java_agrees(golden, tmp_path, cases)


@pytest.fixture
def signed_golden(tmp_path):
    case = dict(CASE, zoned_sign_equivalent=["OUT"])
    d = tmp_path / "golden-signed"
    g.export(case, {"main": {"OUT": b"00001234", "RETURN-CODE": b"0\n"}}, d, "cp037")
    return d


def test_export_carries_a_declared_sign_difference_only_when_declared(golden, signed_golden):
    assert "zoned_sign_equivalent" not in g.json.loads((golden / "golden.json").read_text())
    assert g.json.loads((signed_golden / "golden.json").read_text())["zoned_sign_equivalent"] == ["OUT"]


def test_a_declared_dataset_accepts_the_positive_overpunch_and_says_so(signed_golden, tmp_path):
    java = _java(tmp_path / "j", {"main": {"OUT": b"{0001234", "RETURN-CODE": b"0\n"}})
    notes: list[str] = []
    # golden 0x30 vs 0x7B (`{`) in Java: the same positive zero
    assert g.check(signed_golden, java, notes) == []
    assert notes == ["main/OUT: 1 byte(s) accepted as C10 sign-equivalent (declared by the case)"]


def test_a_declared_dataset_still_fails_a_real_difference_or_a_length_change(signed_golden, tmp_path):
    for label, out in (("value", b"00001239"), ("negative", b"0000}234"), ("short", b"{0001234x")):
        java = _java(tmp_path / label, {"main": {"OUT": out, "RETURN-CODE": b"0\n"}})
        assert g.check(signed_golden, java), label


def test_an_undeclared_dataset_stays_byte_exact(golden, tmp_path):
    bad = dict(MAIN_RUN, OUT=b"AB\x00{\n" * 3)
    java = _java(tmp_path / "j", {"main": bad, "fault-x": {"ABEND": b"U0016\n"}})
    assert g.check(golden, java)


@JDK
def test_the_generated_java_check_applies_the_declared_sign_difference_too(signed_golden, tmp_path):
    cases = {
        "overpunch": {"main": {"OUT": b"0000A234", "RETURN-CODE": b"0\n"}},
        "zero-sign": {"main": {"OUT": b"{0001234", "RETURN-CODE": b"0\n"}},
        "value": {"main": {"OUT": b"00001239", "RETURN-CODE": b"0\n"}},
        "short": {"main": {"OUT": b"0000123", "RETURN-CODE": b"0\n"}},
    }
    _java_agrees(signed_golden, tmp_path, cases)


LOG = b"HELLO\nWORLD  \nlibcob: src/EQDRIVER.cbl:7: warning: implicit CLOSE of OUT-FILE ('OUTFILE')\n"


def _log_golden(tmp_path, log=LOG, encoding="latin-1"):
    d = tmp_path / "golden-log"
    g.export(CASE, {"main": {"SYSOUT": log, "RETURN-CODE": b"0\n"}}, d, encoding)
    return d


SYSOUT_CASES = {
    "no-libcob": b"HELLO\nWORLD\n",
    "padded": b"HELLO   \r\nWORLD",
    "identical": LOG,
    "java-libcob": b"HELLO\nWORLD\nlibcob: not the port's\n",
    "other-line": b"HELLO\nWORLD!\n",
    "missing-line": b"HELLO\n",
    "blank-line-inside": b"HELLO\n\nWORLD\n",
}


def test_sysout_is_compared_by_lines_as_the_harness_does(tmp_path):
    golden = _log_golden(tmp_path)
    got = {}
    for label, out in SYSOUT_CASES.items():
        java = _java(tmp_path / label, {"main": {"SYSOUT": out, "RETURN-CODE": b"0\n"}})
        got[label] = g.check(golden, java) == []
    # libcob lines are the golden side's own noise (a Java one is not); trailing blanks are padding; a real line difference still fails
    assert got == {
        "no-libcob": True,
        "padded": True,
        "identical": True,
        "java-libcob": False,
        "other-line": False,
        "missing-line": False,
        "blank-line-inside": False,
    }


def test_sysout_stays_byte_exact_for_a_non_ascii_code_page_and_for_an_unmodelled_operand(tmp_path):
    java = _java(tmp_path / "j", {"main": {"SYSOUT": b"HELLO\nWORLD\n", "RETURN-CODE": b"0\n"}})
    assert g.check(_log_golden(tmp_path, encoding="cp037"), java)
    unmodelled = _log_golden(tmp_path / "u", b"HELLO\nGGDISPLAY-NOT-MODELLED\n")
    java = _java(tmp_path / "k", {"main": {"SYSOUT": b"HELLO\nGGDISPLAY-NOT-MODELLED", "RETURN-CODE": b"0\n"}})
    assert g.check(unmodelled, java)


@JDK
def test_the_generated_java_check_compares_sysout_by_lines_too(tmp_path):
    golden = _log_golden(tmp_path)
    cases = {k: {"main": {"SYSOUT": v, "RETURN-CODE": b"0\n"}} for k, v in SYSOUT_CASES.items()}
    _java_agrees(golden, tmp_path, cases)


# --- #4052 slice 15: record-level (field layout) comparison -----------------------------------------------------

_F = [
    {"name": "ID", "offset": 0, "bytes": 2, "pic": "99", "usage": "DISPLAY"},
    {"name": "FILLER", "offset": 2, "bytes": 2, "pic": "XX", "usage": "DISPLAY"},
    {"name": "NAME", "offset": 4, "bytes": 2, "pic": "XX", "usage": "DISPLAY"},
]
_REC = {"OUT": {"reclen": 6, "fields": _F}}
_GOLD = b"01..AB02..CD"


@pytest.fixture
def rec_golden(tmp_path):
    d = tmp_path / "golden-rec"
    g.export(CASE, {"main": {"OUT": _GOLD, "RETURN-CODE": b"0\n"}}, d, "latin-1", _REC)
    return d


def _run(tmp_path, label, out):
    return _java(tmp_path / label, {"main": {"OUT": out, "RETURN-CODE": b"0\n"}})


def test_export_carries_layouts_only_when_given(golden, rec_golden):
    assert "records" not in g.json.loads((golden / "golden.json").read_text())
    assert g.json.loads((rec_golden / "golden.json").read_text())["records"] == _REC


def test_a_filler_only_difference_is_accepted_and_counted(rec_golden, tmp_path):
    notes: list[str] = []
    assert g.check(rec_golden, _run(tmp_path, "j", b"01xx" + b"AB" + b"02yyCD"), notes) == []
    assert notes == [
        "main/OUT: 2/2 records equal field by field; FILLER differs in 2 record(s) (accepted as the harness compares records)"
    ]


def test_a_field_difference_or_a_missing_record_still_fails(rec_golden, tmp_path):
    for label, out in (("field", b"01..AB02..CX"), ("short", b"01..AB"), ("long", _GOLD + b"03..EF")):
        assert g.check(rec_golden, _run(tmp_path, label, out)), label


def test_a_dataset_without_a_layout_stays_byte_exact(golden, tmp_path):
    bad = dict(MAIN_RUN, OUT=b"AB\x00\xc2\n" * 3)
    assert g.check(golden, _java(tmp_path / "j", {"main": bad, "fault-x": {"ABEND": b"U0016\n"}}))


_FILLER_ONLY = [
    {"name": "FILLER", "offset": 0, "bytes": 3, "pic": "XXX", "usage": "DISPLAY"},
    {"name": "REDEF", "offset": 2, "bytes": 1, "pic": "X", "usage": "DISPLAY"},  # covers the last FILLER byte too
]


@pytest.mark.skipif(not shutil.which("javac") or not shutil.which("java"), reason="needs a JDK")
def test_the_generated_java_check_compares_records_like_the_python_check(tmp_path):
    """#4052 slice 16: the Java mirror of diff_records. A FILLER-only difference passes in both; a field, a byte outside
    the layout, a FILLER byte a named field also covers, a missing or extra record and a partial record fail in both."""
    recs = {"OUT": {"reclen": 6, "fields": _F}, "FIL": {"reclen": 4, "fields": _FILLER_ONLY}}
    base = {"RETURN-CODE": b"0\n"}
    gold = tmp_path / "golden"
    g.export(CASE, {"main": dict(base, OUT=_GOLD, FIL=b"abcdWXYZ")}, gold, "latin-1", recs)
    runs = {
        "same": (_GOLD, b"abcdWXYZ"),
        "filler": (b"01xxAB02yyCD", b"zzcdWXYZ"),  # only FILLER bytes differ
        "field": (b"01..AB02..CX", b"abcdWXYZ"),
        "redef": (_GOLD, b"abXdWXYZ"),  # byte 2 is also a named field
        "outside": (_GOLD, b"abcXWXYZ"),  # byte 3 is no field, no FILLER
        "short": (_GOLD[:6], b"abcdWXYZ"),
        "long": (_GOLD + b"03..EF", b"abcdWXYZ"),
        "partial": (_GOLD[:-1], b"abcdWXY"),
    }
    dirs = {k: _java(tmp_path / k, {"main": dict(base, OUT=o, FIL=f)}) for k, (o, f) in runs.items()}
    want = {k: g.check(gold, d) for k, d in dirs.items()}
    assert [k for k, v in want.items() if not v] == ["same", "filler"]
    assert g.java_problems(gold, list(dirs.values()), tmp_path / "scratch") == list(want.values())
