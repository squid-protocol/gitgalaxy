"""#7525 (register X35): EXEC CICS WEB CONVERSE with IBM's bare method keyword (DELETE, GET, HEAD, OPTIONS, POST, PUT, TRACE)
in place of METHOD(cvda). IBM (EXEC CICS WEB CONVERSE): the method is given by one of those keywords or by METHOD. Both
translators (the det port and the GnuCOBOL oracle's) resolve the keyword to its CVDA at translation time, so the runtime and
the stub see the same number as METHOD(DFHVALUE(x)); two methods, or none, are refused by the spec group. The end-to-end
proof reuses the URIMAP program of test_web_converse_urimap_e2e_7525.py with each METHOD(DFHVALUE(x)) written as the keyword."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.cics.commands.web import METHOD_FLAGS, WEB_CONVERSE
from gitgalaxy.tools.cobol_to_java.det.cics_web import METHOD_WORDS
from gitgalaxy.tools.cobol_to_java.det.cvda import CVDA

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[0] / "tools"
sys.path.insert(0, str(HERE))
import test_det_translate as t  # noqa: E402

TAIL = " INTO(AREA) MAXLENGTH(R2) NOHANDLE"
BODY = " FROM(AREA) FROMLENGTH(R) MEDIATYPE(REC)"


def _det(method: str, extra: str = "") -> str:
    return " ".join(t._ChanCics().command(f"WEB CONVERSE SESSTOKEN(KEY) {method}{extra}{TAIL}", ""))


def test_the_spec_names_the_seven_keywords_as_flags_of_the_method():
    assert METHOD_FLAGS == ("DELETE", "GET", "HEAD", "OPTIONS", "POST", "PUT", "TRACE")
    assert METHOD_WORDS == METHOD_FLAGS
    for f in METHOD_FLAGS:
        assert WEB_CONVERSE.options[f].kind == "flag"
        assert f not in WEB_CONVERSE.refused


@pytest.mark.parametrize("word", METHOD_FLAGS)
def test_det_bare_keyword_is_the_same_java_as_the_value_form(word):
    assert _det(word) == _det("METHOD(R)").replace("INT(R)", str(CVDA[word]), 1)
    assert f", {CVDA[word]}, " in _det(word)


def test_det_bare_keyword_with_a_body_and_with_a_path():
    assert _det("POST", BODY) == _det("METHOD(R)", BODY).replace("INT(R)", "636", 1)
    assert ", 748, " in _det("GET", " PATH(REC) PATHLENGTH(R)")


@pytest.mark.parametrize(
    ("cmd", "why"),
    [
        ("WEB CONVERSE SESSTOKEN(KEY)" + TAIL, "without METHOD"),
        ("WEB CONVERSE SESSTOKEN(KEY) GET POST" + TAIL, "or with more than one"),
        ("WEB CONVERSE SESSTOKEN(KEY) METHOD(R) GET" + TAIL, "or with more than one"),
        ("WEB CONVERSE SESSTOKEN(KEY) GET MAXLENGTH(R2)", "without INTO"),
    ],
)
def test_det_refuses_no_method_and_two_methods(cmd, why):
    with pytest.raises(t.C.CicsError, match=why):
        t._ChanCics().command(cmd, "")


def test_oracle_translator_moves_the_cvda_and_refuses_as_the_det_port_does():
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(TOOLS))
    import equivalence_cics as ec

    base = "WEB CONVERSE SESSTOKEN(WS-TOK) {} INTO(WS-IN) MAXLENGTH(WS-MAX)"
    for word in METHOD_FLAGS:
        bare = ec.translate_command(base.format(word))
        assert f"MOVE {CVDA[word]} TO GG-NUM" in bare
        assert any("GGCWCNV" in line for line in bare)
        assert bare == ec.translate_command(base.format(f"METHOD({CVDA[word]})"))
    for bad in ("", "GET POST", "METHOD(WS-M) PUT"):
        with pytest.raises(ec.Unsupported, match="METHOD"):
            ec.translate_command(base.format(bad))


def test_trace_and_options_stay_refused_by_name_by_the_runtime():
    # the keywords resolve to the numbers the runtime refuses (cics_task_web.java: 760 TRACE, 759 OPTIONS)
    assert (CVDA["TRACE"], CVDA["OPTIONS"]) == (760, 759)
    assert "WEB CONVERSE METHOD TRACE / OPTIONS" in (
        Path(__file__).resolve().parents[2] / "gitgalaxy/tools/cobol_to_java/cics_task_web.py"
    ).read_text(encoding="utf-8")


@pytest.mark.slow(reason="a Maven build of the generated project and a GnuCOBOL container run")
@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
def test_a_bare_keyword_program_is_proven_against_gnucobol(tmp_path, monkeypatch):
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(TOOLS))
    import det_port
    import test_web_converse_urimap_e2e_7525 as e

    from gitgalaxy.tools.cobol_to_java.det import program as P

    program = e.PROGRAM
    for w in ("POST", "PUT", "GET", "DELETE"):
        program = program.replace(f"METHOD(DFHVALUE({w}))", w)
    assert "DFHVALUE(PATCH)" in program and "DFHVALUE(POST)" not in program
    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    (estate / "csd").mkdir()
    (estate / "cbl" / "WCUDEMO.cbl").write_text(program, encoding="ascii")
    (estate / "csd" / "WCU.csd").write_text(e.CSD, encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    (tmp_path / "case.json").write_text(json.dumps(e._case()), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "WcudemoService.java").read_text("utf-8")
    r = P.translate(
        estate / "cbl" / "WCUDEMO.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project), project
    )
    assert r.stats["holes"] == [], r.stats["holes"]
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "wcu-7525b", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    events = report["outputs"]["converse"]["cobol"]
    assert [x["text"].rstrip() for x in events if x.get("event") == "SEND-TEXT"] == e.SENT
