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
    assert ch.replaced == ["handleTransaction(String,XWsCa)"]
    assert ch.removed == [
        "executeX()",
        "submitXm(XmScreen,String)",
    ]  # not written by the generator, and runTask does not call them
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
    assert ch.replaced == ["handleTransaction(String,XWsCa)"] and ch.imports_added == [
        "p.dto.XWsCa"
    ]  # the request still names it
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
    assert prov["history"][-1]["event"] == "resurfaced" and prov["history"][-1]["replaced"] == [
        "handleTransaction(String,XWsCa)"
    ]
    assert ps.equivalence(tmp_path / "work", None, check=True) == 0


def test_a_det_port_is_left_to_the_translator(tmp_path, monkeypatch):
    """#5983: a det port's facades are the translator's own (no log line, its own answer); --check passes it by."""
    import json

    import ports_compile_check as pcc

    cases = tmp_path / "equivalence"
    port = cases / "c1" / "port" / "service" / "XService.java"
    port.parent.mkdir(parents=True)
    port.write_text(GENERATED, encoding="utf-8")
    (cases / "c1" / "case.json").write_text(json.dumps({"name": "c1", "corpus": "k"}), encoding="utf-8")
    (cases / "c1" / "port" / "provenance.json").write_text(json.dumps({"translator": "det"}), encoding="utf-8")

    def generate(*_args):
        raise AssertionError("no generation for a det port")

    monkeypatch.setattr(pcc, "EQUIVALENCE", cases)
    monkeypatch.setattr(pcc, "generate", generate)
    assert ps.equivalence(tmp_path / "work", None, check=True) == 0
    assert port.read_text(encoding="utf-8") == GENERATED


OVERLOADED = GENERATED.replace(
    "    /** TODO: port it. */",
    """    /** Same transaction, with the COMMAREA's bytes (#4870). */
    public XWsCa handleTransaction(String transid, XWsCa request, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request, area);
        region.run(task, "X", this::runTask);
        lastAnswerBytes = task.returnedBytes();
        return task.returned(XWsCa.class);
    }

    // @facade-helper: the bytes the last overload call answered
    private byte[] lastAnswerBytes;

    /**
     * The last answer's bytes.
     * @facade-helper
     */
    public byte[] lastAnswerBytes() {
        return lastAnswerBytes;
    }

    /** TODO: port it. */""",
)

LOGIC = """    /** The PROCEDURE DIVISION. */
    public void runTask(CicsTask task) {
        int ported = 1;
    }
"""


def _pair(tmp_path, port_text, gen_text):
    port, gen = tmp_path / "port" / "XService.java", tmp_path / "gen" / "XService.java"
    for f, text in ((port, port_text), (gen, gen_text)):
        f.parent.mkdir(exist_ok=True)
        f.write_text(text, encoding="utf-8")
    return port, gen


def _ported(text):
    """GENERATED / OVERLOADED with runTask replaced by ported logic."""
    return text[: text.index("    /** TODO: port it. */")] + LOGIC + "}\n"


def test_overloads_are_matched_by_signature(tmp_path):
    """#4870: the port has the one-argument-pair handleTransaction only; the generator writes both overloads."""
    port, gen = _pair(tmp_path, _ported(GENERATED), OVERLOADED)
    text, ch = ps.resurface(port, gen)
    assert ch.replaced == [] and ch.removed == []  # the existing overload is equal: untouched
    assert ch.added == ["lastAnswerBytes (field)", "handleTransaction(String,XWsCa,byte[])", "lastAnswerBytes()"]
    assert text.count("handleTransaction(String transid, XWsCa request)") == 1
    assert "region.transaction(transid, request, area)" in text
    assert text.index("private byte[] lastAnswerBytes;") < text.index(
        "public XWsCa handleTransaction(String transid, XWsCa request, byte[]"
    )
    assert "int ported = 1;" in text  # the logic is the port's
    port.write_text(text, encoding="utf-8")
    again, ch2 = ps.resurface(port, gen)
    assert ch2.empty() and again == text


def test_each_overload_is_replaced_or_removed_on_its_own(tmp_path):
    old_port = _ported(OVERLOADED).replace("task.returnedBytes()", "null")
    port, gen = _pair(tmp_path, old_port, OVERLOADED)
    text, ch = ps.resurface(port, gen)
    assert ch.replaced == ["handleTransaction(String,XWsCa,byte[])"] and ch.added == [] and ch.removed == []
    assert "lastAnswerBytes = task.returnedBytes();" in text
    # the generator drops the overload and its helpers: the port loses exactly those, the other overload stays
    port, gen = _pair(tmp_path, _ported(OVERLOADED), _ported(GENERATED))
    text, ch = ps.resurface(port, gen)
    assert sorted(ch.removed) == [
        "handleTransaction(String,XWsCa,byte[])",
        "lastAnswerBytes (field)",
        "lastAnswerBytes()",
    ]
    assert ch.replaced == [] and "public XWsCa handleTransaction(String transid, XWsCa request) {" in text
    assert "lastAnswerBytes" not in text and "byte[]" not in text


def test_an_untagged_member_is_never_surface(tmp_path):
    """#4870: no @facade-helper, no surface: the model's own field / method is neither copied nor removed."""
    plain = OVERLOADED.replace("@facade-helper", "helper")
    port, gen = _pair(
        tmp_path,
        _ported(GENERATED).replace("    /** The PROCEDURE", "    private int mine;\n\n    /** The PROCEDURE"),
        plain,
    )
    text, ch = ps.resurface(port, gen)
    assert ch.added == ["handleTransaction(String,XWsCa,byte[])"]  # the FACADE-named method only
    assert "lastAnswerBytes" not in text.replace("lastAnswerBytes = task.returnedBytes();", "")
    assert "private int mine;" in text


def test_check_reports_a_helper_only_difference(tmp_path):
    """--check: a port equal in every facade but missing the tagged field + accessor differs and is not written."""
    body = OVERLOADED.replace("        lastAnswerBytes = task.returnedBytes();\n", "")
    gen_text = OVERLOADED
    start = body.index("    // @facade-helper")
    port_text = _ported(body[:start] + body[body.index("    /** TODO: port it. */") :])
    port, gen = _pair(tmp_path, port_text, gen_text)
    before = port.read_text(encoding="utf-8")
    assert ps.main(["apply", "--port", str(port), "--generated", str(gen), "--check"]) == 1
    assert port.read_text(encoding="utf-8") == before
    assert ps.main(["apply", "--port", str(port), "--generated", str(gen)]) == 0
    assert ps.main(["apply", "--port", str(port), "--generated", str(gen), "--check"]) == 0
    assert "private byte[] lastAnswerBytes;" in port.read_text(encoding="utf-8")
