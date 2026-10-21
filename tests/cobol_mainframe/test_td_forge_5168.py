"""#5168 round 4 (X61): the messaging forge's RoutingTransientData answers by the queue's CSD definition.

The forge is built from synthetic CSD facts (every TYPE / TYPEFILE / OPENTIME / INDIRECTNAME combination, each
with a READQ, a WRITEQ and a DELETEQ site); the plan is checked, and the generated Java is compiled against tiny
slf4j / Spring stubs and run, so the conditions are what the generated class does, not what its text says.
"""

import shutil
import subprocess

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_messaging_forge import MessagingForge
from gitgalaxy.tools.cobol_to_java.java_target import target_from_dict
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

# queue -> (CSD TYPE, the rest of the operand text); a queue missing here is not defined in the CSD
DEFS = {
    "INQ": ("EXTRA", "TYPEFILE(INPUT) DDNAME(INDD)"),
    "INCLOSED": ("EXTRA", "TYPEFILE(INPUT) OPENTIME(DEFERRED) DDNAME(INDD2)"),
    "OUTQ": ("EXTRA", "TYPEFILE(OUTPUT) OPENTIME(INITIAL) DDNAME(OUTDD)"),
    "OUTCLOSED": ("EXTRA", "TYPEFILE(OUTPUT) OPENTIME(DEFERRED) DDNAME(OUTDD2)"),
    "NOTYPEFILE": ("EXTRA", "DDNAME(NTDD)"),
    "RDBACKQ": ("EXTRA", "TYPEFILE(RDBACK) DDNAME(RBDD)"),
    "INTRAQ": ("INTRA", "RECOVSTATUS(NO)"),
    "IND1": ("INDIRECT", "INDIRECTNAME(INQ)"),
    "IND2": ("INDIRECT", "INDIRECTNAME(IND1)"),
    "INDOUT": ("INDIRECT", "INDIRECTNAME(OUTQ)"),
    "INDINTRA": ("INDIRECT", "INDIRECTNAME(INTRAQ)"),
    "LOOP1": ("INDIRECT", "INDIRECTNAME(LOOP2)"),
    "LOOP2": ("INDIRECT", "INDIRECTNAME(LOOP1)"),
    "NOTARGET": ("INDIRECT", "INDIRECTNAME(MISSING)"),
    "NONAME": ("INDIRECT", ""),
    "REMQ": ("REMOTE", "REMOTENAME(OTHER) REMOTESYSTEM(SYS2)"),
    "SYSIDQ": ("INTRA", "SYSID(SYS2)"),
}
VERBS = ("READQ", "WRITEQ", "DELETEQ")
ESTATE_QUEUES = [*DEFS, "CSSL", "UNDEFINED"]  # a log destination, and a queue the CSD does not define


def _forge():
    facts = [
        {"verb": v, "kind": "QUEUE", "qualifier": "TD", "name": q, "line": 10 + i * 3 + j, "attributes": ""}
        for i, q in enumerate(ESTATE_QUEUES)
        for j, v in enumerate(VERBS)
    ]
    skeleton = {"program": {"file": "cbl/P.cbl"}, "sections": {"cics_resources": {"facts": facts}}}
    csd = [
        {"resource_type": "TDQUEUE", "name": q, "queue_type": t, "attributes": f"TYPE({t}) {rest}"}
        for q, (t, rest) in DEFS.items()
    ]
    extra = [
        {
            "queue": q,
            "ddname": a.split("DDNAME(")[1].split(")")[0],
            "dsname": None,
            "record_format": "F",
            "record_size": 80,
        }  # fmt: skip
        for q, (t, a) in DEFS.items()
        if t == "EXTRA"
    ]
    estate = {"sections": {"csd_resources": {"facts": csd}, "tdqueue_datasets": {"facts": extra}}}
    return MessagingForge({"P": skeleton}, estate, "app", target_from_dict(None))


def test_routes_follow_the_definition():
    r = _forge().routes
    assert (r["INQ"].kind, r["INQ"].mode, r["INQ"].closed) == ("dataset", "INPUT", False)
    assert (r["INCLOSED"].mode, r["INCLOSED"].closed) == ("INPUT", True)
    assert (r["OUTQ"].mode, r["OUTQ"].closed) == ("OUTPUT", False)
    assert (r["OUTCLOSED"].mode, r["OUTCLOSED"].closed) == ("OUTPUT", True)
    assert r["NOTYPEFILE"].mode == "" and r["RDBACKQ"].mode == ""
    assert r["INTRAQ"].kind == "queue" and r["CSSL"].kind == "log" and r["UNDEFINED"].kind == "queue"
    # an INDIRECT queue is its target's route, however long the chain
    assert (r["IND1"].target, r["IND1"].kind, r["IND1"].mode) == ("INQ", "dataset", "INPUT")
    assert (r["IND2"].target, r["IND2"].mode) == ("INQ", "INPUT")
    assert (r["INDOUT"].target, r["INDOUT"].mode) == ("OUTQ", "OUTPUT")
    assert (r["INDINTRA"].target, r["INDINTRA"].kind) == ("INTRAQ", "queue")
    assert all(not r[q].refusal for q in ("INQ", "OUTQ", "INTRAQ", "IND1", "IND2", "INDOUT", "INDINTRA", "CSSL"))
    # refused by name
    assert "loops" in r["LOOP1"].refusal and "loops" in r["LOOP2"].refusal
    assert "does not define" in r["NOTARGET"].refusal
    assert "without INDIRECTNAME" in r["NONAME"].refusal
    assert "REMOTE" in r["REMQ"].refusal and "REMOTE" in r["SYSIDQ"].refusal


JAVA_STUBS = {
    "org/slf4j/Logger.java": "package org.slf4j; public interface Logger { void info(String m); void warn(String f, Object a); }",
    "org/slf4j/LoggerFactory.java": (
        "package org.slf4j; public class LoggerFactory {"
        " public static Logger getLogger(String n) { return new L(n); }"
        " public static Logger getLogger(Class<?> c) { return new L(c.getName()); }"
        " static class L implements Logger { final String n; L(String n) { this.n = n; }"
        '  public void info(String m) { System.out.println("LOG " + n + " " + m); }'
        "  public void warn(String f, Object a) { } } }"
    ),
    "org/springframework/beans/factory/annotation/Value.java": (
        "package org.springframework.beans.factory.annotation; public @interface Value { String value(); }"
    ),
    "org/springframework/stereotype/Component.java": "package org.springframework.stereotype; public @interface Component {}",
}

DRIVER = """package app.messaging;

import java.nio.file.*;
import java.util.*;

public class Driver {
    static String run(java.util.function.Supplier<Object> s) {
        try { Object o = s.get(); return String.valueOf(o); }
        catch (RoutingTransientData.TdCondition e) { return e.condition; }
        catch (UnsupportedOperationException e) { return "REFUSED " + e.getMessage(); }
    }

    public static void main(String[] a) throws Exception {
        Path dir = Path.of(a[0]);
        RoutingTransientData td = new RoutingTransientData(new InMemoryMessageQueue(), a[0]);
        for (String q : a[1].split(",")) {
            System.out.println(q + " READ " + run(() -> td.read(q)));
            System.out.println(q + " READ " + run(() -> td.read(q)));
            System.out.println(q + " READ " + run(() -> td.read(q)));
            System.out.println(q + " WRITE " + run(() -> { td.write(q, "rec-" + q); return "ok"; }));
            System.out.println(q + " DELETE " + run(() -> { td.delete(q); return "ok"; }));
        }
    }
}
"""


@pytest.fixture(scope="module")
def ran(tmp_path_factory):
    javac, java = shutil.which("javac"), shutil.which("java")
    if not (javac and java):
        pytest.skip("javac / java not on PATH")
    work = tmp_path_factory.mktemp("td5168")
    src, data, out = work / "src", work / "data", work / "classes"
    for rel, text in JAVA_STUBS.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    forge = _forge()
    files = next(iter(forge.sources().values()))
    for name in ("MessageQueue", "InMemoryMessageQueue", "TransientData", "RoutingTransientData"):
        (src / "app/messaging").mkdir(parents=True, exist_ok=True)
        (src / "app/messaging" / f"{name}.java").write_text(files[name], encoding="utf-8")
    (src / "app/messaging/Driver.java").write_text(DRIVER, encoding="utf-8")
    data.mkdir()
    (data / "INQ.txt").write_text("first\nsecond\n", encoding="utf-8")  # the input data set's records
    (data / "INCLOSED.txt").write_text("hidden\n", encoding="utf-8")
    sources = [str(p) for p in src.rglob("*.java")]
    out.mkdir()
    javac_run(
        [javac, "-encoding", "UTF-8", "--release", "17", "-d", str(out), *sources],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    done = subprocess.run(
        [
            java,
            "-Dfile.encoding=UTF-8",
            "-Dstdout.encoding=UTF-8",
            "-cp",
            str(out),
            "app.messaging.Driver",
            str(data),
            ",".join(ESTATE_QUEUES),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    results: dict[tuple[str, str], list[str]] = {}
    for line in done.stdout.splitlines():
        if line.startswith("LOG "):
            continue
        q, verb, rest = line.split(" ", 2)
        results.setdefault((q, verb), []).append(rest)
    return results, data


def _read(ran, q):
    return ran[0][(q, "READ")]


def _one(ran, q, verb):
    (res,) = ran[0][(q, verb)]
    return res


def test_input_queue_reads_in_order_then_qzero_and_refuses_writes(ran):
    assert _read(ran, "INQ") == ["Optional[first]", "Optional[second]", "Optional.empty"]
    assert _one(ran, "INQ", "WRITE") == "INVREQ"
    assert _one(ran, "INQ", "DELETE") == "INVREQ"  # DELETEQ TD of an extrapartition queue


def test_closed_queue_is_notopen_for_every_verb_but_delete(ran):
    assert _read(ran, "INCLOSED") == ["NOTOPEN"] * 3
    assert _one(ran, "INCLOSED", "WRITE") == "NOTOPEN"
    assert _read(ran, "OUTCLOSED") == ["NOTOPEN"] * 3
    assert _one(ran, "OUTCLOSED", "WRITE") == "NOTOPEN"
    assert _one(ran, "OUTCLOSED", "DELETE") == "INVREQ"


def test_output_queue_is_written_and_not_read(ran):
    assert _read(ran, "OUTQ") == ["INVREQ"] * 3
    assert _one(ran, "OUTQ", "WRITE") == "ok"
    assert (ran[1] / "OUTQ.txt").read_text(encoding="utf-8").startswith("rec-OUTQ\n")
    assert _one(ran, "OUTQ", "DELETE") == "INVREQ"


def test_no_typefile_or_rdback_read_is_refused_and_a_write_is_taken_as_output(ran):
    for q in ("NOTYPEFILE", "RDBACKQ"):
        assert all("REFUSED" in r and "no TYPEFILE INPUT / OUTPUT" in r for r in _read(ran, q))
        assert _one(ran, q, "WRITE") == "ok"  # ASSUMED: open for output, as before X61


def test_indirect_queues_answer_as_their_target(ran):
    # INQ's records were read through INQ (the driver goes in DEFS order): the cursor is the target's, not the alias's
    assert _read(ran, "IND1") == ["Optional.empty"] * 3 and _read(ran, "IND2") == ["Optional.empty"] * 3
    assert _one(ran, "IND1", "WRITE") == "INVREQ" and _one(ran, "IND2", "WRITE") == "INVREQ"
    assert _read(ran, "INDOUT") == ["INVREQ"] * 3
    assert _one(ran, "INDOUT", "WRITE") == "ok"
    assert (ran[1] / "OUTQ.txt").read_text(encoding="utf-8").count("rec-INDOUT") == 1  # the target's data set
    assert not (ran[1] / "INDOUT.txt").exists()


def test_intrapartition_and_indirect_to_intrapartition_use_the_message_port(ran):
    for q in ("INTRAQ", "INDINTRA", "UNDEFINED"):
        assert _one(ran, q, "WRITE") == "ok"
    assert _read(ran, "INTRAQ") == ["Optional.empty"] * 3 and _read(ran, "INDINTRA") == ["Optional.empty"] * 3
    assert _one(ran, "INDINTRA", "DELETE") == "ok"


def test_refused_queues_are_refused_for_every_verb(ran):
    for q, why in (
        ("LOOP1", "loops"), ("LOOP2", "loops"), ("NOTARGET", "does not define"),
        ("NONAME", "without INDIRECTNAME"), ("REMQ", "REMOTE"), ("SYSIDQ", "REMOTE"),
    ):  # fmt: skip
        for verb in ("READ", "WRITE", "DELETE"):
            for res in ran[0][(q, verb)]:
                assert res.startswith("REFUSED") and why in res and res.endswith(": not modelled")


def test_the_log_destination_is_unchanged(ran):
    assert _one(ran, "CSSL", "WRITE") == "ok"
    assert all("written, not read" in r for r in _read(ran, "CSSL"))
