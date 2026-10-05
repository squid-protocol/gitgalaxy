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
