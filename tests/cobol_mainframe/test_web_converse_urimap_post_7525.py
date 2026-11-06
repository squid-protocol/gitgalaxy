"""#7525: WEB CONVERSE URIMAP with a request body (POST / PUT / PATCH) and without (GET / DELETE), the whole class on the
det port's runtime. IBM (EXEC CICS WEB CONVERSE): URIMAP gives this request's path (PATH is not given with it); a body
method needs FROM (INVREQ RESP2 34), a bodyless method refuses FROM (33), a body needs MEDIATYPE (76), FROMLENGTH not
greater than zero is LENGERR 50, a response over MAXLENGTH is LENGERR 57 with the first MAXLENGTH bytes. Which exchange
answers is chosen by method, path and query only (the body is the program's; the run does not state it)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

MAIN = """
        CicsTask.HttpPeer p = new CicsTask.HttpPeer("HTTP", "h1", 80, "UM1", "/p/one", java.util.List.of(
                new CicsTask.HttpExchange("POST", "/p/one", "", 201, "Created", "text/plain", "created-body"),
                new CicsTask.HttpExchange("PUT", "/p/one", "", 200, "OK", "text/plain", "put-body"),
                new CicsTask.HttpExchange("PATCH", "/p/one", "", 200, "OK", "text/plain", "patch-body"),
                new CicsTask.HttpExchange("POST", "/p/one", "", 200, "OK", "text/plain", "0123456789"),
                new CicsTask.HttpExchange("GET", "/p/one", "a=1", 200, "OK", "text/plain", "got")));
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withHttpPeers(java.util.List.of(p));
        String tok = t.webOpenUrimap("UM1").sesstoken();
        java.nio.charset.Charset cs = java.nio.charset.StandardCharsets.UTF_8;
        // {method, hasBody, fromLength, maxLength}; 636 POST, 749 PUT, 1220 PATCH, 748 GET
        int[][] ok = {{636, 1, 4, 50}, {749, 1, 1, 50}, {1220, 1, 2, 50}};
        for (int[] c : ok) {
            CicsTask.WebResponse r = t.webConverse(tok, "UM1", c[0], null, 0, null, 0, "data", c[2], "text/plain", c[3], -1, cs);
            System.out.println(c[0] + " " + r.resp() + "/" + r.resp2() + " " + r.status() + " " + new String(r.body()));
        }
        // POST again: the first POST exchange is answered, the second (10 bytes) is cut at MAXLENGTH 4: LENGERR 57
        CicsTask.WebResponse cut = t.webConverse(tok, "UM1", 636, null, 0, null, 0, "d", 1, "text/plain", 4, -1, cs);
        System.out.println("cut " + cut.resp() + "/" + cut.resp2() + " " + new String(cut.body()));
        CicsTask.WebResponse g = t.webConverse(tok, "UM1", 748, null, 0, "a=1", 3, null, 0, null, 50, -1, cs);
        System.out.println("get " + g.resp() + "/" + g.resp2() + " " + new String(g.body()));
        // the conditions, each alone, on a body method or a bodyless one
        Object[][] bad = {
            {636, null, 0, null},          // POST without FROM: INVREQ 34
            {748, "x", 1, "text/plain"},   // GET with FROM: INVREQ 33
            {636, "x", 1, null},           // body without MEDIATYPE: INVREQ 76
            {636, "x", 0, "text/plain"},   // FROMLENGTH 0: LENGERR 50
            {636, "x", -1, "text/plain"},  // FROMLENGTH negative: LENGERR 50
            {9999, null, 0, null},         // a method that is not one: INVREQ 54
        };
        for (Object[] b : bad) {
            CicsTask.WebResponse r = t.webConverse(tok, "UM1", (Integer) b[0], null, 0, null, 0, (String) b[1], (Integer) b[2],
                    (String) b[3], 50, -1, cs);
            System.out.println("bad " + b[0] + " " + r.resp() + "/" + r.resp2());
        }
        // refused by name, never answered: PATH with URIMAP, a body with a blank MEDIATYPE, a body longer than its area
        Object[][] refused = {{636, "x", 1, "text/plain", "/p/one"}, {636, "x", 1, "  ", null}, {636, "xy", 5, "text/plain", null}};
        for (Object[] b : refused) {
            try {
                t.webConverse(tok, "UM1", (Integer) b[0], (String) b[4], b[4] == null ? 0 : 6, null, 0, (String) b[1],
                        (Integer) b[2], (String) b[3], 50, -1, cs);
                System.out.println("accepted");
            } catch (UnsupportedOperationException e) { System.out.println("refused"); }
        }
"""

EXPECTED = [
    "636 0/0 201 created-body",
    "749 0/0 200 put-body",
    "1220 0/0 200 patch-body",
    "cut 22/57 0123",
    "get 0/0 got",
    "bad 636 16/34",
    "bad 748 16/33",
    "bad 636 16/76",
    "bad 636 22/50",
    "bad 636 22/50",
    "bad 9999 16/54",
    "refused",
    "refused",
    "refused",
]


def _javac_run(tmp_path: Path, main: str) -> list[str]:
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    pkg = tmp_path / "src" / "t" / "cics"
    pkg.mkdir(parents=True)
    (pkg / "CicsTask.java").write_text(
        CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"), encoding="utf-8"
    )
    (pkg / "CicsSpec.java").write_text(CICS_SPEC_JAVA.replace("__PACKAGE__", "t"), encoding="utf-8")
    (pkg / "Main.java").write_text(
        "package t.cics;\npublic class Main {\n    public static void main(String[] a) {\n" + main + "\n    }\n}\n",
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
    return run.stdout.decode("utf-8").splitlines()


@pytest.mark.skipif(shutil.which("javac") is None, reason="needs a JDK (javac)")
@pytest.mark.slow(reason="compiles the generated CicsTask runtime with javac (cold ~10-18 s on a loaded runner)")
def test_converse_urimap_body_and_bodyless_forms_answer_as_ibm_states(tmp_path):
    assert _javac_run(tmp_path, MAIN) == EXPECTED


@pytest.mark.parametrize(
    ("body", "args"),
    [
        ("METHOD(R) FROM(AREA) FROMLENGTH(R) MEDIATYPE(REC) ", "Cobol.text(f_AREA, CS), "),
        ("METHOD(R) FROM(AREA) FROMLENGTH(R) ", "Cobol.text(f_AREA, CS), "),
        ("METHOD(R) ", "null, "),
    ],
)
def test_the_det_translation_gives_urimap_then_the_body_to_the_runtime(body, args):
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_det_translate as t

    v = t._ChanCics().command(f"WEB CONVERSE SESSTOKEN(KEY) URIMAP(UMN) {body}INTO(AREA) NOHANDLE", "")[0]
    assert ".webConverse(Cobol.text(f_KEY, CS), Cobol.text(f_UMN, CS), INT(R), null, 0, null, 0, " + args in v, v
