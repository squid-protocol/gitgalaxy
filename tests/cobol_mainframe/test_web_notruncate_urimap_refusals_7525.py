"""#7525: WEB CONVERSE NOTRUNCATE stays refused by name, with IBM's silence as the reason; both translators read the spec
entry. WEB CONVERSE URIMAP(name) is translated by the det port (the stated peer's URIMAP path stands for PATH; PATH with it is
refused; another peer's or an unstated URIMAP is refused by the runtime, register X35); the GnuCOBOL stub does not model it yet,
so the oracle translator refuses it by name. Server WEB RECEIVE NOTRUNCATE is translated (the det port keeps the rest of the body for the
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
    cases = ((WEB_CONVERSE.refused["NOTRUNCATE"], ("RESP2 36", "later WEB CONVERSE")),)
    for r, words in cases:
        for w in words:
            assert w in r.why


@pytest.mark.parametrize("opt,match", [("NOTRUNCATE", "RESP2 36")])
def test_det_translator_refuses_the_converse_option_by_name(opt, match):
    pytest.importorskip("tree_sitter_language_pack")
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import equivalence_cics as ec

    with pytest.raises(ec.Unsupported, match=match):
        ec.translate_command(CONVERSE + opt)


def test_converse_urimap_is_modelled_and_translates_for_every_method():
    pytest.importorskip("tree_sitter_language_pack")
    assert "URIMAP" not in WEB_CONVERSE.refused and "URIMAP" in WEB_CONVERSE.options
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_det_translate as t

    c = t._ChanCics()
    for meth, body in (
        ("GET", ""),
        ("POST", "FROM(AREA) FROMLENGTH(R) MEDIATYPE(REC) "),
        ("PUT", "FROM(AREA) FROMLENGTH(R) "),
    ):
        v = c.command(f"WEB CONVERSE SESSTOKEN(KEY) URIMAP(UMN) METHOD(R) {body}INTO(AREA) NOHANDLE", "")
        assert ".webConverse(Cobol.text(f_KEY, CS), Cobol.text(f_UMN, CS), " in v[0], (meth, v[0])
    plain = c.command("WEB CONVERSE SESSTOKEN(KEY) METHOD(R) PATH(REC) PATHLENGTH(R) INTO(AREA) NOHANDLE", "")[0]
    assert "f_KEY, CS), null, INT(R)" in plain  # no URIMAP: null


def test_converse_urimap_with_path_is_refused_by_the_spec_group():
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_det_translate as t

    c = t._ChanCics()
    for extra in ("PATH(REC) PATHLENGTH(R)", "PATH(REC)", "PATHLENGTH(R)"):
        with pytest.raises(Exception, match="PATH"):
            c.command(f"WEB CONVERSE SESSTOKEN(KEY) URIMAP(UMN) METHOD(R) {extra} INTO(AREA)", "")


def test_oracle_translator_refuses_urimap_until_the_stub_models_it():
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import equivalence_cics as ec

    with pytest.raises(ec.Unsupported, match="URIMAP: not modelled by the stub"):
        ec.translate_command(CONVERSE + "URIMAP(UM)")


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


URIMAP_MAIN = """
        java.util.function.BiFunction<String, String, CicsTask.HttpExchange> ex = (m, q) ->
                new CicsTask.HttpExchange(m, "/p/one", q, 201, "Created", "text/plain", "ok-" + m);
        CicsTask.HttpPeer pa = new CicsTask.HttpPeer("HTTP", "h1", 80, "UM1", "/p/one",
                java.util.List.of(ex.apply("POST", ""), ex.apply("GET", "a=1"), ex.apply("PUT", ""), ex.apply("PATCH", "")));
        CicsTask.HttpPeer pb = new CicsTask.HttpPeer("HTTP", "h2", 80, "UM2", "/p/two", java.util.List.of(
                new CicsTask.HttpExchange("POST", "/p/two", "", 200, "OK", "text/plain", "two")));
        CicsTask.HttpPeer pn = new CicsTask.HttpPeer("HTTP", "h3", 80, "UM3", null, java.util.List.of());
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withHttpPeers(java.util.List.of(pa, pb, pn));
        String tok = t.webOpenUrimap("UM1").sesstoken();
        int[] meth = {636, 748, 749, 1220};
        String[] q = {null, "a=1", null, null};
        String[] body = {"x", null, "y", "z"};
        for (int i = 0; i < 4; i++) {
            CicsTask.WebResponse r = t.webConverse(tok, i == 0 ? "UM1     " : "UM1", meth[i], null, 0, q[i],
                    q[i] == null ? 0 : q[i].length(), body[i], body[i] == null ? 0 : 1, body[i] == null ? null : "text/plain",
                    50, -1, java.nio.charset.StandardCharsets.UTF_8);
            System.out.println(r.resp() + "/" + r.resp2() + " " + r.status() + " " + new String(r.body()));
        }
        String[][] bad = {{"UM2", null}, {"ZZ", null}, {"UM1", "/p/one"}};
        for (String[] u : bad) {
            try {
                t.webConverse(tok, u[0], 748, u[1], u[1] == null ? 0 : 6, null, 0, null, 0, null, 50, -1,
                        java.nio.charset.StandardCharsets.UTF_8);
                System.out.println("accepted " + u[0]);
            } catch (UnsupportedOperationException e) { System.out.println("refused " + u[0]); }
        }
        CicsTask t3 = new CicsTask("ZC01", "ENTER", null, null).withHttpPeers(java.util.List.of(pa, pb, pn));
        String tk3 = t3.webOpenUrimap("UM3").sesstoken();
        try {
            t3.webConverse(tk3, "UM3", 748, null, 0, null, 0, null, 0, null, 50, -1, java.nio.charset.StandardCharsets.UTF_8);
            System.out.println("accepted UM3");
        } catch (UnsupportedOperationException e) { System.out.println("refused UM3"); }
        System.out.println(t.webConverse("NOSUCH  ", "UM1", 748, null, 0, null, 0, null, 0, null, 50, -1,
                java.nio.charset.StandardCharsets.UTF_8).resp2());
"""


@pytest.mark.skipif(shutil.which("javac") is None, reason="needs a JDK (javac)")
@pytest.mark.slow(reason="compiles the generated CicsTask runtime with javac (cold ~10-18 s on a loaded runner)")
def test_the_runtime_takes_the_path_from_the_session_peers_urimap(tmp_path):
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    pkg = tmp_path / "src" / "t" / "cics"
    pkg.mkdir(parents=True)
    (pkg / "CicsTask.java").write_text(
        CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"), encoding="utf-8"
    )
    (pkg / "CicsSpec.java").write_text(CICS_SPEC_JAVA.replace("__PACKAGE__", "t"), encoding="utf-8")
    (pkg / "Main.java").write_text(
        "package t.cics;\npublic class Main {\n    public static void main(String[] a) {\n"
        + URIMAP_MAIN
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
    assert run.stdout.decode("utf-8").splitlines() == [
        "0/0 201 ok-POST",
        "0/0 201 ok-GET",
        "0/0 201 ok-PUT",
        "0/0 201 ok-PATCH",
        "refused UM2",
        "refused ZZ",
        "refused UM1",
        "refused UM3",
        "27",
    ]
