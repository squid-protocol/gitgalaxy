"""Unit tests for L0-L4 proof speedups: persistent CobolSession + binary sharing, --one-jvm --record, and evidence.py --jobs."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT))

import equivalence as eq  # noqa: E402
import equivalence_common as common  # noqa: E402
import evidence as ev  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_reuse(monkeypatch):
    monkeypatch.setattr(common, "_REUSE", None)


def test_cobol_session_reuses_one_container_and_handles_timeout(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def fake_run(cmd, *a, **kw):
        calls.append(cmd)
        if cmd[:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="cid-123\n", stderr="")
        if cmd[:2] == ["docker", "exec"]:
            if "hang" in cmd[-2]:
                raise subprocess.TimeoutExpired(cmd, timeout=10)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    step1 = tmp_path / "cobol"
    step2 = tmp_path / "faults" / "f1" / "cobol"
    step1.mkdir(parents=True)
    step2.mkdir(parents=True)
    (step1 / "run.sh").write_text("true\n", encoding="ascii")
    (step2 / "run.sh").write_text("true\n", encoding="ascii")

    with common.CobolSession(tmp_path) as box:
        assert box.id is None  # lazy until an un-reused step executes
        assert common.run_cobol_step(step1, session=box).returncode == 0
        assert box.id == "cid-123"
        assert common.run_cobol_step(step2, session=box).returncode == 0
        # Only one docker run -d across both steps
        assert sum(1 for c in calls if c[:2] == ["docker", "run"]) == 1
        execs = [c for c in calls if c[:2] == ["docker", "exec"]]
        assert len(execs) == 2
        assert "ln -s /case/cobol /work" in execs[0][-2]
        assert "ln -s /case/faults/f1/cobol /work" in execs[1][-2]

    assert ["docker", "rm", "-f", "cid-123"] in calls

    # Timeout cleans up the container and returns returncode 124
    calls.clear()
    box = common.CobolSession(tmp_path)
    box._start()
    calls.clear()

    def timeout_run(cmd, *a, **kw):
        calls.append(cmd)
        if cmd[:2] == ["docker", "exec"]:
            raise subprocess.TimeoutExpired(cmd, timeout=10)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", timeout_run)
    timed = box.exec_step(step1)
    assert timed.returncode == 124 and "timed out" in timed.stderr
    assert ["docker", "rm", "-f", "cid-123"] in calls
    assert box.id is None


def test_cobol_session_stays_unstarted_when_all_steps_reused(monkeypatch, tmp_path):
    called: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, *a, **k: called.append(cmd) or subprocess.CompletedProcess(cmd, 0))

    earlier = tmp_path / "earlier"
    (earlier / "cobol").mkdir(parents=True)
    (earlier / "cobol" / "run.sh").write_text("echo ok\n", encoding="ascii")
    (earlier / "cobol" / "out.txt").write_text("done\n", encoding="ascii")
    (earlier / "report.json").write_text("{}\n", encoding="utf-8")

    now = tmp_path / "now"
    (now / "cobol").mkdir(parents=True)
    (now / "cobol" / "run.sh").write_text("echo ok\n", encoding="ascii")
    common.reuse(now, earlier)

    with common.CobolSession(now) as box:
        proc = common.run_cobol_step(now / "cobol", session=box)
        assert proc.args[0] == "reuse"
        assert box.id is None
    assert called == []


def test_run_cobol_shares_compiled_binaries_unless_parm_changes(monkeypatch, tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "PROG1.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. PROG1.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n",
        encoding="ascii",
    )
    case = {
        "name": "demo",
        "program": "PROG1",
        "program_source": "PROG1.cbl",
        "corpus": "demo",
        "parm": "BASE",
        "datasets": {"IDXFILE": {"organization": "indexed", "reclen": 10, "keys": [{"offset": 0, "length": 4}]}},
    }

    def fake_step(work: Path, *a, **k):
        if "gcc -shared -fPIC -O2 -o /work/ggfault.so" in (work / "run.sh").read_text():
            (work / "ggfault.so").write_bytes(b"fault-so")
        if "gcc -shared -fPIC -O2 -o /work/ggdisplay.so" in (work / "run.sh").read_text():
            (work / "ggdisplay.so").write_bytes(b"display-so")
        if "-o program " in (work / "run.sh").read_text():
            (work / "program").write_bytes(b"base-program")
        if "-o ldIDXFILE " in (work / "run.sh").read_text():
            (work / "ldIDXFILE").write_bytes(b"ld")
        if "-o ulIDXFILE " in (work / "run.sh").read_text():
            (work / "ulIDXFILE").write_bytes(b"ul")
        (work / "RETURN-CODE").write_text("0\n", encoding="ascii")
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(eq, "run_cobol_step", fake_step)

    base = tmp_path / "cobol"
    eq.run_cobol(case, corpus, base, compile_fault_stub=True)
    base_sh = (base / "run.sh").read_text(encoding="ascii")
    assert "-o program " in base_sh and "/work/ggfault.so" in base_sh

    # Same PARM fault reuses program, ld/ul, ggdisplay.so, ggfault.so -> zero compiles!
    f1 = tmp_path / "f1"
    eq.run_cobol(case, corpus, f1, {"name": "f1", "faults": []}, shared=base)
    f1_sh = (f1 / "run.sh").read_text(encoding="ascii")
    assert "cobc -x" not in f1_sh and "gcc -shared" not in f1_sh
    assert (f1 / "program").read_bytes() == b"base-program"
    assert (f1 / "ggfault.so").read_bytes() == b"fault-so"
    assert (f1 / "ldIDXFILE").read_bytes() == b"ld"

    # Fault overriding PARM changes EQDRIVER.cbl -> recompiles program, still reuses ld/ul + .so stubs
    f2 = tmp_path / "f2"
    eq.run_cobol(case, corpus, f2, {"name": "f2", "parm": "ALT", "faults": []}, shared=base)
    f2_sh = (f2 / "run.sh").read_text(encoding="ascii")
    assert "-o program " in f2_sh
    assert "-o ldIDXFILE " not in f2_sh
    assert "gcc -shared" not in f2_sh


def test_equivalence_allows_record_with_one_jvm(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["equivalence.py", "run", "nonexistent-case", "--record", "--one-jvm"])
    with pytest.raises(FileNotFoundError):
        eq.main()


def test_evidence_prove_forwards_one_jvm_flag(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def fake_run(cmd, *a, **kw):
        calls.append(cmd)
        work = Path(cmd[cmd.index("--keep") + 1])
        work.mkdir(parents=True, exist_ok=True)
        (work / "report.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    t = ev.Target(
        key="demo-case",
        kind="batch",
        case="demo-case",
        program="DEMO",
        record=tmp_path / "evidence.json",
        port_dir=tmp_path / "port",
    )
    t.record.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ev.subprocess, "run", fake_run)
    monkeypatch.setattr(ev, "det_only", lambda target: False)
    monkeypatch.setattr(ev, "load", lambda target: {})
    monkeypatch.setattr(ev, "status", lambda rec, target: {"status": "proven, unapproved", "reasons": []})

    assert ev.prove(t, tmp_path)["key"] == "demo-case"
    assert "--one-jvm" in calls[-1] and "--record" in calls[-1]

    ev.prove(t, tmp_path, one_jvm=False)
    assert "--one-jvm" not in calls[-1]


def test_evidence_jobs_runs_non_db2_concurrently_and_serializes_db2(monkeypatch, tmp_path, capsys):
    targets = [
        ev.Target(key=f"batch-{i}", kind="batch", case=f"batch-{i}", program=f"P{i}", record=tmp_path / f"{i}.json", port_dir=tmp_path, db2=False)
        for i in range(4)
    ] + [
        ev.Target(key=f"db2-{i}", kind="batch", case=f"db2-{i}", program=f"D{i}", record=tmp_path / f"d{i}.json", port_dir=tmp_path, db2=True)
        for i in range(2)
    ]

    lock = threading.Lock()
    active_non_db2 = 0
    max_non_db2 = 0
    active_db2 = 0
    max_db2 = 0

    def fake_prove(t, work, crucible=None, offline=False, one_jvm=True):
        nonlocal active_non_db2, max_non_db2, active_db2, max_db2
        with lock:
            if t.db2:
                active_db2 += 1
                max_db2 = max(max_db2, active_db2)
            else:
                active_non_db2 += 1
                max_non_db2 = max(max_non_db2, active_non_db2)
        time.sleep(0.08)
        with lock:
            if t.db2:
                active_db2 -= 1
            else:
                active_non_db2 -= 1
        return {"key": t.key, "status": {"status": "proven, unapproved", "reasons": []}}

    monkeypatch.setattr(ev, "_selected", lambda args: targets)
    monkeypatch.setattr(ev, "prove", fake_prove)
    monkeypatch.setattr(ev, "load", lambda t: {"proof": {"verdict": "proven"}})
    monkeypatch.setattr(ev, "ledgered_facade_only", lambda k, r: None)
    monkeypatch.setattr(ev, "write_pages", lambda: 0)

    rc = ev.main(["prove", "--work", str(tmp_path / "work"), "--jobs", "4"])
    assert rc == 0
    assert max_non_db2 >= 2
    assert max_db2 == 1

    # Output lines preserve target selection order deterministically
    lines = [ln.split(":", 1)[0] for ln in capsys.readouterr().out.strip().splitlines()]
    assert lines == [t.key for t in targets]


def test_evidence_rejects_nonpositive_jobs():
    with pytest.raises(SystemExit):
        ev.main(["prove", "--jobs", "0"])
