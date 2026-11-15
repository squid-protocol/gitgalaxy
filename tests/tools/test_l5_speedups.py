"""Unit tests for the L5 mutation & survivor-attack speedups (#l5-speedups)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))


def test_baseline_classpath_reads_surefire_without_mvn(tmp_path: Path, monkeypatch):
    import mutation as mu

    baseline = tmp_path / "baseline"
    project = baseline / "java" / "demo"
    (project / "target" / "classes").mkdir(parents=True)
    (project / "target" / "test-classes").mkdir(parents=True)
    (project / "pom.xml").write_text("<project/>", encoding="utf-8")
    jar = tmp_path / "lib.jar"
    jar.write_bytes(b"")
    reports = project / "target" / "surefire-reports"
    reports.mkdir(parents=True)
    old_root = project
    cp = os.pathsep.join([
        str(old_root / "target" / "test-classes"),
        str(old_root / "target" / "classes"),
        str(jar),
    ])
    (reports / "TEST-Run.xml").write_text(
        f'<testsuite><properties><property name="surefire.test.class.path" value="{cp}"/></properties></testsuite>',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        mu,
        "run_decoded",
        lambda *a, **k: pytest.fail("mvn compile should not run when surefire XML exists"),
    )
    got = mu.baseline_classpath(baseline, tmp_path / "work")
    assert got == os.pathsep.join([str(project / "target" / "classes"), str(jar)])


def test_baseline_classpath_reads_recorded_file_without_mvn(tmp_path: Path, monkeypatch):
    import equivalence_java as ej
    import mutation as mu

    baseline = tmp_path / "baseline"
    project = baseline / "java" / "demo"
    (project / "target" / "classes").mkdir(parents=True)
    (project / "pom.xml").write_text("<project/>", encoding="utf-8")
    jar = tmp_path / "lib.jar"
    jar.write_bytes(b"")
    (project / ej.TEST_CLASSPATH).write_text(
        os.pathsep.join([
            str(project / "target" / "test-classes"),
            str(project / "target" / "classes"),
            str(jar),
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(mu, "run_decoded", lambda *a, **k: pytest.fail("mvn should not run"))
    got = mu.baseline_classpath(baseline, tmp_path / "work")
    assert got == os.pathsep.join([str(project / "target" / "classes"), str(jar)])


def test_javac_session_compiles_live_and_rejects_stillborn(tmp_path: Path):
    import equivalence_java as ej
    import mutation as mu

    env = mu._java_env()
    bin_dir = mu._javac_session_bin(env)
    assert bin_dir is not None
    sess = mu.JavacSession(bin_dir, env)
    try:
        live_src = tmp_path / "live" / "service"
        live_src.mkdir(parents=True)
        src_file = live_src / "Demo.java"
        src_file.write_text("package service; public class Demo { public int f() { return 7; } }\n", encoding="utf-8")
        out_live = tmp_path / "out_live"
        res = sess.compile(tmp_path / "live", "", out_live)
        assert res is not None and res[0] is True
        assert (out_live / "service" / "Demo.class").is_file()
        manifest = json.loads((out_live / ej.PRECOMPILED_MANIFEST).read_text(encoding="utf-8"))
        assert manifest["javac_options"] == ej.JAVAC_OPTIONS
        assert manifest["sources"]["service/Demo.java"] == hashlib.sha256(src_file.read_bytes()).hexdigest()

        bad_src = tmp_path / "bad" / "service"
        bad_src.mkdir(parents=True)
        (bad_src / "Demo.java").write_text("package service; public class Demo { broken( }\n", encoding="utf-8")
        res2 = sess.compile(tmp_path / "bad", "", tmp_path / "out_bad")
        assert res2 is not None and res2[0] is False and res2[1]
    finally:
        sess.close()


def test_adopt_precompiled_overlay_copies_classes_and_cleans_stale_inners(tmp_path: Path, monkeypatch):
    import equivalence_java as ej

    earlier = tmp_path / "earlier"
    e_proj = earlier / "app"
    e_src = e_proj / "src/main/java" / ej.PKG_DIR / "cobolrt"
    e_src.mkdir(parents=True)
    (e_src / "Rt.java").write_text("class Rt {}", encoding="utf-8")

    project = tmp_path / "cur" / "app"
    classes = project / "target" / "classes"
    pkg_cls = classes / ej.PKG_DIR / "service"
    pkg_cls.mkdir(parents=True)
    (pkg_cls / "Svc.class").write_bytes(b"OLD")
    (pkg_cls / "Svc$OldInner.class").write_bytes(b"STALE_INNER")
    c_src = project / "src/main/java" / ej.PKG_DIR
    (c_src / "service").mkdir(parents=True)
    (c_src / "cobolrt").mkdir(parents=True)
    mut_java = c_src / "service" / "Svc.java"
    mut_bytes = b"package x; class Svc { int v() { return 1; } }"
    mut_java.write_bytes(mut_bytes)
    (c_src / "cobolrt" / "Rt.java").write_text("class Rt {}", encoding="utf-8")

    pre = tmp_path / "precompiled"
    (pre / ej.PKG_DIR / "service").mkdir(parents=True)
    (pre / ej.PKG_DIR / "service" / "Svc.class").write_bytes(b"NEW_MUTANT")
    (pre / ej.PRECOMPILED_MANIFEST).write_text(
        json.dumps({
            "javac_options": ej.JAVAC_OPTIONS,
            "sources": {"service/Svc.java": hashlib.sha256(mut_bytes).hexdigest()},
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv(ej.PRECOMPILED_OVERLAY_ENV, str(pre))

    assert ej._adopt_precompiled_overlay(project, earlier, ["service/Svc.java", "cobolrt/Rt.java"], classes) is True
    assert (pkg_cls / "Svc.class").read_bytes() == b"NEW_MUTANT"
    assert not (pkg_cls / "Svc$OldInner.class").exists()

    # Mismatch in source sha refuses adoption cleanly
    mut_java.write_bytes(b"changed!")
    assert ej._adopt_precompiled_overlay(project, earlier, ["service/Svc.java", "cobolrt/Rt.java"], classes) is False


def test_mutant_worker_swap_and_rollback(tmp_path: Path):
    import mutation as mu

    base = tmp_path / "base_cls"
    (base / "p").mkdir(parents=True)
    (base / "p" / "A.class").write_bytes(b"BASE_A")
    (base / "p" / "A$1.class").write_bytes(b"BASE_A1")
    (base / "p" / "Keep.class").write_bytes(b"KEEP")

    mut1 = tmp_path / "mut1_cls"
    (mut1 / "p").mkdir(parents=True)
    (mut1 / "p" / "A.class").write_bytes(b"MUT_A")
    (mut1 / "p" / "A$2.class").write_bytes(b"MUT_A2")

    ctx = SimpleNamespace(base_classes=base)
    w = mu._MutantWorker(0, tmp_path / "work", ctx)
    w.session = SimpleNamespace(close=lambda: None)
    w.classes_dir.mkdir(parents=True)
    import shutil

    shutil.copytree(base, w.classes_dir, dirs_exist_ok=True)
    rb = w.swap_and_restore(mut1)
    assert (w.classes_dir / "p" / "A.class").read_bytes() == b"MUT_A"
    assert (w.classes_dir / "p" / "A$2.class").read_bytes() == b"MUT_A2"
    assert not (w.classes_dir / "p" / "A$1.class").exists()
    assert (w.classes_dir / "p" / "Keep.class").read_bytes() == b"KEEP"

    w.rollback(rb)
    assert (w.classes_dir / "p" / "A.class").read_bytes() == b"BASE_A"
    assert (w.classes_dir / "p" / "A$1.class").read_bytes() == b"BASE_A1"
    assert not (w.classes_dir / "p" / "A$2.class").exists()
    assert (w.classes_dir / "p" / "Keep.class").read_bytes() == b"KEEP"


def test_det_mutation_forwards_one_jvm_and_jobs(tmp_path: Path, monkeypatch):
    import det_mutation as dm
    import mutation as mu

    port = tmp_path / "det" / "c1" / "port" / "service"
    port.mkdir(parents=True)
    (port / "S.java").write_text("class S {}", encoding="utf-8")
    monkeypatch.setattr(dm, "_run_translate", lambda cases, work, jobs: tmp_path / "det")
    seen: list[dict] = []

    def fake_mu_run(case, work, jobs, *a, **kw):
        seen.append({"case": case, "jobs": jobs, **kw})
        return {"coverage": None, "results": []}

    monkeypatch.setattr(mu, "run", fake_mu_run)
    monkeypatch.setattr(dm, "case_kind", lambda c: "batch")
    monkeypatch.setattr(dm, "record", lambda c, w, p: 0)

    dm.run(["c1"], tmp_path, 10, 0, 6, False, case_jobs=1)
    assert seen[-1]["one_jvm"] is True and seen[-1]["jobs"] == 6

    dm.run(["c1"], tmp_path, 10, 0, 6, True, case_jobs=1)
    assert seen[-1]["one_jvm"] is False and seen[-1]["jobs"] == 6


def test_survivor_attack_defaults_to_one_jvm(tmp_path: Path, monkeypatch):
    import equivalence as eq
    import mainframe_corpus as mc
    import mutation as mu
    import strengthen as st
    import survivor_attack as sa

    case = {
        "name": "b", "program": "P", "corpus": "x",
        "datasets": {"IN": {"input": "in.txt", "reclen": 10}, "OUT": {"organization": "sequential", "reclen": 10, "compare": True}},
        "faults": [],
    }
    (tmp_path / "in.txt").write_text("00001ALICE\n", encoding="latin-1")
    monkeypatch.setattr(eq, "load_case", lambda n: {**case})
    monkeypatch.setattr(st, "input_layout", lambda *a: None)
    monkeypatch.setattr(mc, "select", lambda names: [object()])
    monkeypatch.setattr(mc, "require_clone", lambda entry: tmp_path)
    monkeypatch.setattr(sa, "det_port", lambda c, w: tmp_path / "port")
    monkeypatch.setattr(sa, "find_mutants", lambda c, p, ids: {
        "m1": SimpleNamespace(id="m1", op="ROR", file="S.java", line=1, before="a", after="b")
    })
    monkeypatch.setattr(mu, "baseline_classpath", lambda *a: "")
    monkeypatch.setattr(mu, "write_mutant", lambda p, m, d: d)
    monkeypatch.setattr(mu, "compiles", lambda *a, **kw: (True, ""))
    prove_calls = []

    def fake_prove(c, port, d, t, flags):
        prove_calls.append(flags)
        if "--reuse" not in flags:
            return {"verdict": "proven", "report": {"program": "P"}}
        return {"verdict": "refuted", "killed_by": ["main"]}

    monkeypatch.setattr(mu, "prove", fake_prove)
    inp = tmp_path / "inputs.json"
    inp.write_text(json.dumps([{"name": "s1", "sysin": "X"}]), encoding="utf-8")
    res = sa.attack("b", ["m1"], inp, tmp_path / "w", 30, jobs=2)
    assert res["m1"]["result"] == "killed"
    assert "--one-jvm" in prove_calls[-1]
    assert sa._default_jobs() >= 1


def test_det_mutation_refresh_case_jobs_and_jobs(tmp_path: Path, monkeypatch):
    import det_mutation as dm
    import mutation as mu

    ledger_dir = tmp_path / "ledger"
    ports = tmp_path / "det"
    for c in ("c1", "c2"):
        p = ports / c / "port" / "service"
        p.mkdir(parents=True)
        (p / "S.java").write_text("class S {}", encoding="utf-8")
    fp = {"case": "a1", "corpus": "b1", "survivors": "c1", "generator": "d1", "harness": "e1", "oracle": "f1"}
    entries = {
        c: {
            "format": dm.FORMAT, "case": c, "date": "2026-11-01", "commit": "abc", "mode": "fast+one-jvm",
            "seed": 0, "mutants": 2, "chosen": 2,
            "counts": {"killed": 1, "timeout": 0, "survived": 1, "stillborn": 0, "error": 0, "pending": 0},
            "killed": ["m0"], "stillborn": [], "survived": [{"id": "m1", "op": "ROR", "line": 1, "before": "a", "after": "b"}],
            "every": "m0 m1",
            "inputs": {**{k: v for k, v in fp.items()}, "port": dm.port_sha(ports / c / "port"), "runtime": ""},
        }
        for c in ("c1", "c2")
    }
    monkeypatch.setattr(dm, "load", lambda path=dm.LEDGER: entries)
    monkeypatch.setattr(dm, "fingerprints", lambda c: {k: {"sha256": ("a2" if k == "case" else v)} for k, v in fp.items()})
    monkeypatch.setattr(dm, "_run_translate", lambda cases, work, jobs: ports)
    monkeypatch.setattr(dm, "case_kind", lambda c: "batch")
    monkeypatch.setattr(dm, "stated", lambda c, s=None: {})
    written: dict[str, dict] = {}
    monkeypatch.setattr(dm, "write", lambda c, e, path=dm.LEDGER: written.__setitem__(c, e))
    seen: list[tuple[str, int, bool | None]] = []

    def fake_mu_run(case, work, jobs, *a, **kw):
        seen.append((case, jobs, kw.get("one_jvm")))
        return {"coverage": None, "results": [{"id": "m1", "verdict": "killed", "before": "a", "after": "b"}]}

    monkeypatch.setattr(mu, "run", fake_mu_run)
    for c in ("c1", "c2"):
        fake_case_dir = tmp_path / "cases" / c
        fake_case_dir.mkdir(parents=True)
        (fake_case_dir / "case.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(dm, "CASES", tmp_path / "cases")

    rc = dm.refresh(["c1", "c2"], tmp_path / "work", jobs=5, case_jobs=2)
    assert rc == 0
    assert sorted(written) == ["c1", "c2"]
    assert all(j == 5 and oj is True for _, j, oj in seen)


def test_equivalence_main_mutant_session_isolates_epochs(tmp_path: Path):
    import equivalence_java as ej
    import mutation as mu

    m2 = Path.home() / ".m2" / "repository"
    jars = []
    for pat in (
        "org/junit/platform/junit-platform-launcher/1.10.*/*.jar",
        "org/junit/platform/junit-platform-engine/1.10.*/*.jar",
        "org/junit/platform/junit-platform-commons/1.10.*/*.jar",
        "org/junit/jupiter/junit-jupiter-api/5.10.*/*.jar",
        "org/junit/jupiter/junit-jupiter-engine/5.10.*/*.jar",
        "org/opentest4j/opentest4j/1.3.*/*.jar",
        "org/apiguardian/apiguardian-api/*/*.jar",
    ):
        found = sorted(m2.glob(pat))
        if not found:
            pytest.skip(f"missing jar matching {pat}")
        jars.append(str(found[-1]))

    shell = mu._java_env()
    javac = str(Path(shell["JAVA_HOME"]) / "bin" / "javac")
    java = str(Path(shell["JAVA_HOME"]) / "bin" / "java")
    if not Path(javac).is_file():
        pytest.skip("javac unavailable")

    fw_cp = os.pathsep.join(jars)
    runner_dir = tmp_path / "runner"
    runner_dir.mkdir()
    (runner_dir / "EquivalenceMain.java").write_text(ej.RUNNER, encoding="utf-8")
    subprocess.run([javac, "-encoding", "UTF-8", "-d", str(runner_dir), "-cp", fw_cp, str(runner_dir / "EquivalenceMain.java")], check=True, env=shell)

    ep1 = tmp_path / "ep1"
    ep2 = tmp_path / "ep2"
    for ep, body in ((ep1, "return;"), (ep2, 'throw new AssertionError("killed");')):
        pkg = ep / ej.PKG_DIR
        pkg.mkdir(parents=True)
        (pkg / "EquivalenceRunTest.java").write_text(
            f"package {ej.PKG}; import org.junit.jupiter.api.Test;\n"
            f"public class EquivalenceRunTest {{ @Test void run() {{ {body} }} }}\n",
            encoding="utf-8",
        )
        subprocess.run([javac, "-encoding", "UTF-8", "-d", str(ep), "-cp", fw_cp, str(pkg / "EquivalenceRunTest.java")], check=True, env=shell)

    sess = ej.JvmSession(
        [java, "-cp", f"{fw_cp}{os.pathsep}{runner_dir}", "EquivalenceMain", "--mutant-session"],
        tmp_path,
        shell,
    )
    try:
        r1 = sess.run("-Dtest.prop=one", 30, epoch="m1", cp=str(ep1))
        r2 = sess.run("-Dtest.prop=two", 30, epoch="m2", cp=str(ep2))
        assert r1.returncode == 0
        assert r2.returncode == 1
    finally:
        sess.close()

