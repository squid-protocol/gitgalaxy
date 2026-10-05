"""#4343: tests/tools/port_surface.py brings a port's facades to the generator's and leaves its ported logic alone."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import port_surface as ps  # noqa: E402

GENERATED = """package p.service;

import p.cics.CicsTask;
import p.dto.XWsCa;

public class XService {

    /** A CICS transaction entered the program (#4343). */
    public XWsCa handleTransaction(String transid, XWsCa request) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "X", this::runTask);
        return task.returned(XWsCa.class);
    }

    /** TODO: port it. */
    public void runTask(CicsTask task) {
    }
}
"""

PORT = """package p.service;

import p.cics.CicsTask;
import java.util.Map;

public class XService {

    public void executeX() {
        log.info("X is CICS only");
    }

    /** Runs a task of its own. */
    public XWsCa handleTransaction(String transid, XWsCa request) {
        CicsTask task = new CicsTask(transid, "ENTER", request, Map.of());
        runTask(task);
        return returnedOf(task);
    }

    /** The PROCEDURE DIVISION. */
    public void runTask(CicsTask task) {
        task.sendMap(renderXm(null));
    }

    /** SEND MAP: what runTask sends. */
    public XmScreen renderXm(XmScreen s) {
        return new XmScreen();
    }

    /** RECEIVE MAP outside the task. */
    public Object submitXm(XmScreen in, String aid) {
        return in;
    }

    private static XWsCa returnedOf(CicsTask task) {
        return task.returned(XWsCa.class);
    }
}
"""


def test_facades_come_from_the_generator_and_the_ported_logic_stays(tmp_path):
    port, gen = tmp_path / "port" / "XService.java", tmp_path / "gen" / "XService.java"
    for f, text in ((port, PORT), (gen, GENERATED)):
        f.parent.mkdir()
        f.write_text(text, encoding="utf-8")
    text, ch = ps.resurface(port, gen)
    assert ch.replaced == ["handleTransaction"]
    assert ch.removed == ["executeX", "submitXm"]  # not written by the generator, and runTask does not call them
    assert ch.helpers_removed == ["returnedOf"]  # only the old facade used it
    assert ch.imports_added == ["p.dto.XWsCa"]
    assert "region.transaction(transid, request)" in text and "new CicsTask(transid" not in text
    assert "public XmScreen renderXm" in text  # runTask calls it: ported behaviour, kept
    assert "task.sendMap(renderXm(null));" in text
    port.write_text(text, encoding="utf-8")
    again, ch2 = ps.resurface(port, gen)
    assert ch2.empty() and again == text


CROSSING = (
    GENERATED.replace("public XWsCa handleTransaction", "public Object handleTransaction")
    .replace("task.returned(XWsCa.class)", "task.returned(Object.class)")
    .replace("import p.dto.XWsCa;", "import p.dto.XWsCa;\nimport java.util.List;")
)


def test_only_the_imports_the_written_facades_use_are_added(tmp_path):
    """#4441: an import of the generated file that no written facade uses is the model's choice, never surface."""
    port, gen = tmp_path / "port" / "XService.java", tmp_path / "gen" / "XService.java"
    for f, text in ((port, GENERATED.replace("import p.dto.XWsCa;\n", "")), (gen, CROSSING)):
        f.parent.mkdir()
        f.write_text(text, encoding="utf-8")
    text, ch = ps.resurface(port, gen)
    assert ch.replaced == ["handleTransaction"] and ch.imports_added == ["p.dto.XWsCa"]  # the request still names it
    assert "import java.util.List;" not in text and "public Object handleTransaction" in text
    port.write_text(GENERATED.replace("import p.dto.XWsCa;\n", "").replace("XWsCa", "Object"), encoding="utf-8")
    gen.write_text(CROSSING.replace("XWsCa", "Object"), encoding="utf-8")
    assert ps.resurface(port, gen)[1].empty()  # facades equal: List is not added on its own


def test_equivalence_resurfaces_each_case_port_and_records_it(tmp_path, monkeypatch):
    """#4441: the equivalence ports are resurfaced against their corpus's generation; provenance gets the event."""
    import json

    import ports_compile_check as pcc

    cases = tmp_path / "equivalence"
    port = cases / "c1" / "port" / "service" / "XService.java"
    port.parent.mkdir(parents=True)
    port.write_text(GENERATED, encoding="utf-8")
    (cases / "c1" / "case.json").write_text(json.dumps({"name": "c1", "corpus": "k"}), encoding="utf-8")
    (cases / "c1" / "port" / "provenance.json").write_text(json.dumps({"edited_after": "none"}), encoding="utf-8")

    def generate(corpus, culture, work):
        root = work / "proj"
        gen = root / "src" / "main" / "java" / "com" / "gitgalaxy" / "modernized" / "service" / "XService.java"
        gen.parent.mkdir(parents=True)
        gen.write_text(CROSSING, encoding="utf-8")
        return root

    monkeypatch.setattr(pcc, "EQUIVALENCE", cases)
    monkeypatch.setattr(pcc, "generate", generate)
    assert ps.equivalence(tmp_path / "work", None, check=True) == 1
    assert "public XWsCa handleTransaction" in port.read_text(encoding="utf-8")  # --check writes nothing
    assert ps.equivalence(tmp_path / "work", None, check=False) == 0
    assert "public Object handleTransaction" in port.read_text(encoding="utf-8")
    prov = json.loads((cases / "c1" / "port" / "provenance.json").read_text(encoding="utf-8"))
    assert prov["history"][-1]["event"] == "resurfaced" and prov["history"][-1]["replaced"] == ["handleTransaction"]
    assert ps.equivalence(tmp_path / "work", None, check=True) == 0
