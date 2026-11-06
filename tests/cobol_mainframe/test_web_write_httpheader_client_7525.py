"""#7525: WEB WRITE HTTPHEADER SESSTOKEN (the client form) translates on an ASSUMED sequence (register X38; IBM does not say
which request the header goes on or whether it persists): it goes on every later WEB CONVERSE on that session until WEB
CLOSE. The det port runs it and the GnuCOBOL stub keeps the session headers the same way (GGCWWRT;
the cics_crucible runtime tests compare the two). The server form (no SESSTOKEN) is unchanged."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.cics.commands.web import WEB_WRITE_HTTPHEADER

CLIENT = "WEB WRITE HTTPHEADER(WS-N) NAMELENGTH(WS-NL) VALUE(WS-V) VALUELENGTH(WS-VL) SESSTOKEN(WS-TOK)"


def test_the_spec_models_sesstoken_as_a_session_token_area():
    assert "SESSTOKEN" not in WEB_WRITE_HTTPHEADER.refused
    assert WEB_WRITE_HTTPHEADER.options["SESSTOKEN"].width == 8


def test_equivalence_translator_translates_the_client_write_to_the_session_entry():
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import equivalence_cics as ec

    w = ec.translate_command(CLIENT)
    assert w[:3] == ["MOVE WS-NL TO GG-LEN", "MOVE WS-VL TO GG-NUM", "CALL 'GGCWWRT' USING GG-CICS"]
    assert w[3] == "    BY REFERENCE WS-TOK" and w[4] == "    BY REFERENCE WS-N"  # the token is the first argument
    assert "GGCWWRT" not in "".join(ec.translate_command(CLIENT.replace(" SESSTOKEN(WS-TOK)", "")))  # server: GGCWWRH
    with pytest.raises(ec.Unsupported, match="client form"):  # the client READ stays refused
        ec.translate_command(CLIENT.replace("WRITE", "READ"))
    with pytest.raises(ec.Unsupported, match="as a literal"):
        ec.translate_command(CLIENT.replace("SESSTOKEN(WS-TOK)", "SESSTOKEN('ABCDEFGH')"))


def test_det_translator_passes_the_token_for_the_client_form_only():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_det_translate as t

    c = t._ChanCics()
    server = c.command("WEB WRITE HTTPHEADER(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2) NOHANDLE", "")[0]
    client = c.command(
        "WEB WRITE HTTPHEADER(REC) NAMELENGTH(R) VALUE(REC) VALUELENGTH(R2) SESSTOKEN(KEY) NOHANDLE", ""
    )[0]
    assert ".webWriteHeader(Cobol.text(" in server
    assert client.count("Cobol.text(") == server.count("Cobol.text(") + 1
    assert "KEY" in client.split(".webWriteHeader(")[1].split(",")[0]


JAVA_MAIN = """
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withHttpPeers(java.util.List.of(
                new CicsTask.HttpPeer("HTTP", "h", 80, "UM", "/p", java.util.List.of(
                        new CicsTask.HttpExchange("GET", "/p", "", 200, "OK", "text/plain", "a"),
                        new CicsTask.HttpExchange("GET", "/p", "", 200, "OK", "text/plain", "b")))));
        java.nio.charset.Charset cs = java.nio.charset.StandardCharsets.ISO_8859_1;
        String tok = t.webOpenUrimap("UM").sesstoken();
        String n = "X-A" + " ".repeat(5), v = "one" + " ".repeat(5);
        System.out.println(t.webWriteHeader("NOSUCHTK", n, 3, v, 3)[1]);
        System.out.println(t.webWriteHeader(tok, n, 0, v, 3)[1]);
        System.out.println(t.webWriteHeader(tok, n, 3, v, 0)[1]);
        System.out.println(t.webWriteHeader(tok, n, 3, v, 3)[0]);
        System.out.println(t.webWriteHeader(tok, "X-B     ", 3, "two     ", 3)[0]);
        for (int i = 0; i < 2; i++) {
            t.webConverse(tok, 748, null, 0, null, 0, null, 0, null, 10, -1, cs);
        }
        t.webClose(tok);
        for (java.util.Map<String, Object> e : t.events()) {
            if (e.get("headers") != null) System.out.println("conv " + e.get("headers").toString().replace("\\n", "|"));
            else if (e.containsKey("sesstoken")) System.out.println("hdr " + e.get("name") + "=" + e.get("value"));
        }
        System.out.println(t.webWriteHeader(tok, n, 3, v, 3)[1]);
"""


@pytest.mark.skipif(shutil.which("javac") is None, reason="needs a JDK (javac)")
@pytest.mark.slow(reason="compiles the generated CicsTask runtime with javac (cold ~10-18 s on a loaded runner)")
def test_the_runtime_sends_the_session_headers_on_each_later_converse(tmp_path):
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    pkg = tmp_path / "src" / "t" / "cics"
    pkg.mkdir(parents=True)
    (pkg / "CicsTask.java").write_text(
        CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"), encoding="utf-8"
    )
    (pkg / "CicsSpec.java").write_text(CICS_SPEC_JAVA.replace("__PACKAGE__", "t"), encoding="utf-8")
    (pkg / "Main.java").write_text(
        "package t.cics;\npublic class Main {\n    public static void main(String[] a) {\n"
        + JAVA_MAIN
        + "\n    }\n}\n",
        encoding="utf-8",
    )
    classes = tmp_path / "classes"
    built = subprocess.run(  # noqa: S603, S607
        ["javac", "-encoding", "UTF-8", "-d", str(classes), *map(str, pkg.glob("*.java"))],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )  # fmt: skip
    assert built.returncode == 0, built.stderr
    run = subprocess.run(  # noqa: S603, S607
        ["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(classes), "t.cics.Main"],
        capture_output=True, check=True,
    )  # fmt: skip
    out = run.stdout.decode("utf-8").splitlines()
    # NOTOPEN 27, LENGERR 35, LENGERR 55, then two headers written; the two converses each carry both; after CLOSE: NOTOPEN
    assert out[:5] == ["27", "35", "55", "0", "0"]
    assert out.count("conv X-A: one|X-B: two") == 2
    assert "hdr X-A=one" in out and "hdr X-B=two" in out
    assert out[-1] == "27"
