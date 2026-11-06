"""#7525: WEB CONVERSE URIMAP / NOTRUNCATE stay refused by name, each with IBM's wording or silence as the reason; both
translators read the spec entry. Server WEB RECEIVE NOTRUNCATE is translated (the det port keeps the rest of the body for the
next RECEIVE, LENGERR RESP2 36; the sequence is ASSUMED, register X38); the GnuCOBOL oracle stub keeps it the same way (GGCWRCV,
NOTRUNC flag); SET with NOTRUNCATE is refused by both."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.cics.commands.web import WEB_CONVERSE, WEB_RECEIVE

CONVERSE = "WEB CONVERSE SESSTOKEN(KEY) METHOD(R) INTO(AREA) "


def test_the_spec_names_why_each_form_is_refused():
    cases = (
        (WEB_CONVERSE.refused["URIMAP"], ("this request only", "forbids PATH")),
        (WEB_CONVERSE.refused["NOTRUNCATE"], ("RESP2 36", "later WEB CONVERSE")),
    )
    for r, words in cases:
        for w in words:
            assert w in r.why


@pytest.mark.parametrize("opt,match", [("NOTRUNCATE", "RESP2 36"), ("URIMAP(UM)", "this request only")])
def test_det_translator_refuses_the_converse_option_by_name(opt, match):
    pytest.importorskip("tree_sitter_language_pack")
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import equivalence_cics as ec

    with pytest.raises(ec.Unsupported, match=match):
        ec.translate_command(CONVERSE + opt)


def test_server_receive_notruncate_is_a_modelled_flag_and_translates():
    assert "NOTRUNCATE" not in WEB_RECEIVE.refused and "NOTRUNCATE" in WEB_RECEIVE.options
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import equivalence_cics as ec

    t = ec.translate_command("WEB RECEIVE NOTRUNCATE INTO(AREA) LENGTH(LEN) MAXLENGTH(MX)")
    assert t[1] == "MOVE 'NOTRUNC' TO GG-FLAGS" and "IF GG-RESP = 0 OR GG-RESP2 = 57 OR GG-RESP2 = 36" in t
    t = ec.translate_command("WEB RECEIVE NOTRUNCATE INTO(AREA) LENGTH(LEN) MAXLENGTH(MX) MEDIATYPE(MT) NOSRVCONVERT")
    assert t[1] == "MOVE 'MEDIA NOTRUNC RAW' TO GG-FLAGS"
    with pytest.raises(ec.Unsupported, match="SET with NOTRUNCATE"):
        ec.translate_command("WEB RECEIVE NOTRUNCATE SET(PTR) LENGTH(LEN)")


def test_det_translator_passes_notruncate_to_the_runtime():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_det_translate as t

    c = t._ChanCics()
    plain = c.command("WEB RECEIVE INTO(REC) LENGTH(R) MAXLENGTH(R2)", "")[0]
    kept = c.command("WEB RECEIVE INTO(REC) LENGTH(R) MAXLENGTH(R2) NOTRUNCATE", "")[0]
    assert plain.endswith("Integer.MAX_VALUE, 0);") is False and ", true)" not in plain
    assert kept.endswith(", 0, true);")


JAVA_MAIN = """
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withHttpRequest(new CicsTask.HttpRequest("HTTP", "h", 80,
                "PUT", "HTTP/1.1", "/k", "", java.util.List.of(), "text/plain", "hello world!"));
        for (int[] s : new int[][] {{5, 1}, {4, 1}, {50, 1}}) {
            CicsTask.WebReceived r = t.webReceive(s[0], 50, 0, s[1] == 1);
            System.out.println(r.resp() + "/" + r.resp2() + " " + r.body());
        }
        try { t.webReceive(5, 50, 0, true); } catch (UnsupportedOperationException e) { System.out.println("refused"); }
        CicsTask u = new CicsTask("ZC01", "ENTER", null, null).withHttpRequest(new CicsTask.HttpRequest("HTTP", "h", 80,
                "PUT", "HTTP/1.1", "/k", "", java.util.List.of(), "text/plain", "hello world!"));
        System.out.println(u.webReceive(5, 50, 0, true).resp2() + " " + u.webReceive(3, 50, 0, false).resp2());
"""


@pytest.mark.skipif(shutil.which("javac") is None, reason="needs a JDK (javac)")
@pytest.mark.slow(reason="compiles the generated CicsTask runtime with javac (cold ~10-18 s on a loaded runner)")
def test_the_runtime_keeps_the_rest_for_the_next_receive(tmp_path):
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
    # "hello world!": 5 kept -> 4 of the rest " wor" kept -> "ld!" fits; a fourth receive is a second RECEIVE (refused)
    assert run.stdout.decode("utf-8").splitlines() == [
        "22/36 hello",
        "22/36  wor",
        "0/0 ld!",
        "refused",
        "36 57",
    ]
