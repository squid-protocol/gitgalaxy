"""
#3497: JCICS -- Java on CICS (core/jcics.py) through `extract_boundary("java")`:
Program.link as a LINK call site, KSDS / TSQ operations with names from literals,
constants and prefixes, channels and containers, and Java with no JCICS.
"""

from gitgalaxy.core.mainframe_boundary import extract_boundary

SRC = """\
import com.ibm.cics.server.KSDS;
import com.ibm.cics.server.Program;
import com.ibm.cics.server.TSQ;
import com.ibm.cics.server.Task;
public class Bank {
    private static final String FILENAME = "CUSTOMER";
    private KSDS customerFile;
    void go(byte[] data, String sc) throws Exception {
        Program getCompy = new Program();
        getCompy.setName("GETCOMPY");
        getCompy.link(data);
        customerFile = new KSDS();
        customerFile.setName(FILENAME);
        customerFile.readForUpdate(key, holder);
        customerFile.rewrite(data);
        TSQ q = new TSQ();
        q.setName("HBNK" + sc);
        q.writeItem(data);
        // q.delete();
        Channel ch = Task.getTask().createChannel("CIPCHAN");
        Container c = ch
                .createContainer("CIPA");
    }
}
"""


def _rows(src):
    b = extract_boundary("java", src)
    return (
        [(c["line"], c["verb"], c["target"]) for c in b["calls"]],
        [(o["line"], o["kind"], o["verb"], o["name"], o["resolution"], o["qualifier"]) for o in b["cics_resources"]],
    )


def test_jcics_links_files_queues_channels_containers():
    calls, ops = _rows(SRC)
    assert calls == [(11, "LINK", "GETCOMPY")]
    assert ops == [
        (14, "FILE", "readForUpdate", "CUSTOMER", "constant", None),
        (15, "FILE", "rewrite", "CUSTOMER", "constant", None),
        (18, "QUEUE", "writeItem", "HBNK*", "prefix", "TS"),  # the commented-out delete draws nothing
        (20, "CHANNEL", "createChannel", "CIPCHAN", "literal", None),
        (22, "CONTAINER", "createContainer", "CIPA", "literal", "CIPCHAN"),  # the method's line, below its object
    ]


def test_java_without_jcics_draws_nothing():
    assert _rows("public class A { void f() { Program p = new Program(); p.link(); } }") == ([], [])
