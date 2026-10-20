"""#4726 `gitgalaxy assess --jcl`: the compile options the estate's own JCL sets, read as an estate options file."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")  # the det parser; the ground-truth CI job has no translator extra

from gitgalaxy.core.estate_options import effective_options, validate
from gitgalaxy.tools.readiness.jcl_options import options_from_jcl

REPO = Path(__file__).resolve().parents[2]
OPTIONS = REPO / "tests" / "equivalence" / "estate_options"
CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", REPO / ".mainframe_corpora"))


def _step(parm: str | None, name: str = "COBOL") -> str:
    tail = "" if parm is None else f",PARM={parm}"
    return f"//{name:<8} EXEC PGM=IGYCRCTL{tail}\n//SYSIN DD DSN=A.B,DISP=SHR\n"


def _jcl(tmp_path: Path, *steps: str, name: str = "BUILD.jcl") -> Path:
    path = tmp_path / name
    path.write_text("//J JOB (A)\n" + "".join(steps))
    return path


def _parm(doc: dict) -> dict[str, str]:
    return {e["option"]: e["value"] for e in doc["parm"]["default"]}


@pytest.mark.parametrize(
    "parm, expected",
    [
        ("'LIST,MAP,NODYN'", {"LIST": "", "MAP": "", "NODYNAM": ""}),
        ("(RENT,TRUNC(OPT),'AMODE(31)')", {"RENT": "", "TRUNC": "OPT", "AMODE": "31"}),
        (
            "'NODYNAM,OPT,''APOST,TRUNC(BIN),CICS'''",
            {"NODYNAM": "", "OPTIMIZE": "", "APOST": "", "TRUNC": "BIN", "CICS": ""},
        ),
    ],
)
def test_the_parm_forms(tmp_path, parm, expected):
    doc, notices = options_from_jcl(_jcl(tmp_path, _step(parm)))
    assert validate(doc) == [] and notices == []
    assert _parm(doc) == expected
    assert {e["source"] for e in doc["parm"]["default"]} == {"BUILD.jcl:2"}


def test_a_continued_parm(tmp_path):
    step = "//COBOL EXEC PGM=IGYCRCTL,REGION=0M,\n//   PARM=(NODYNAM,LIB,RENT,\n//   'TRUNC(OPT)')\n"
    doc, _ = options_from_jcl(_jcl(tmp_path, step))
    assert _parm(doc) == {"NODYNAM": "", "LIB": "", "RENT": "", "TRUNC": "OPT"}


def test_the_resolver_sees_the_jcl_options(tmp_path):
    doc, _ = options_from_jcl(_jcl(tmp_path, _step("'TRUNC(OPT)'")))
    assert effective_options(None, doc, "PROG").values()["TRUNC"] == "OPT"


def test_optfile_is_named_not_ignored(tmp_path):
    doc, notices = options_from_jcl(_jcl(tmp_path, _step("'OPTFILE'")))
    assert any("OPTFILE" in n for n in notices) and validate(doc) == []
    assert _parm(doc) == {}


def test_no_parm_and_no_compile_step_are_defaults(tmp_path):
    doc, notices = options_from_jcl(_jcl(tmp_path, _step(None)))
    assert _parm(doc) == {} and notices == []
    doc, notices = options_from_jcl(_jcl(tmp_path, "//S EXEC PGM=IEBGENER\n"))
    assert _parm(doc) == {} and any("no compile step" in n for n in notices) and validate(doc) == []


def test_steps_that_differ_keep_only_what_they_agree_on(tmp_path):
    jcl = _jcl(tmp_path, _step("'RENT,TRUNC(OPT),CICS'", "A"), _step("'RENT,TRUNC(OPT),NOCICS'", "B"))
    doc, notices = options_from_jcl(jcl)
    assert _parm(doc) == {"RENT": "", "TRUNC": "OPT"}
    assert len(notices) == 1 and "CICS" in notices[0] and "NOCICS" in notices[0]
    jcl = _jcl(tmp_path, _step("'RENT,TRUNC(OPT)'", "A"), _step("'RENT,TRUNC(STD)'", "B"), name="TWO.jcl")
    assert _parm(options_from_jcl(jcl)[0]) == {"RENT": ""}
    assert _parm(options_from_jcl(_jcl(tmp_path, _step("RENT", "A"), _step(None, "B"), name="N.jcl"))[0]) == {}


def test_a_directory_reads_jcl_members_only(tmp_path):
    sub = tmp_path / "jcl"
    sub.mkdir()
    _jcl(sub, _step("'RENT'"), name="A.jcl")
    (sub / "notes.txt").write_text(_step("'NORENT'"))
    doc, _ = options_from_jcl(sub)
    assert _parm(doc) == {"RENT": ""}


def _assess(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=str(REPO), GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER")
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "gitgalaxy.cli", "assess", *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=600,
    )


def test_jcl_text_never_reaches_the_report(tmp_path):
    estate = tmp_path / "estate"
    estate.mkdir()
    (estate / "HELLO.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. HELLO.\n       PROCEDURE DIVISION.\n           GOBACK.\n"
    )
    jcl = tmp_path / "jcl"
    jcl.mkdir()
    (jcl / "BUILD.jcl").write_text(
        "//SECRETJOB JOB (A)\n//* MARKER-COMMENT-9f3\n"
        + _step("'RENT,TRUNC(OPT)'")
        + "//DD1 DD DSN=MARKER.DSN.7c1,DISP=SHR\n"
    )
    out = tmp_path / "report.json"
    res = _assess(str(estate), "--jcl", str(jcl), "--no-translate", "--out", str(out))
    assert res.returncode == 0, res.stderr[-3000:]
    text = out.read_text()
    assert json.loads(text)["totals"]
    assert "MARKER" not in text and "SECRETJOB" not in text and "BUILD" not in text


def test_jcl_and_options_are_refused_together(tmp_path):
    res = _assess(str(tmp_path), "--jcl", str(tmp_path), "--options", str(tmp_path / "o.json"))
    assert res.returncode == 2 and "pass one" in res.stderr
    res = _assess(str(tmp_path), "--jcl", str(tmp_path / "missing"))
    assert res.returncode == 2 and "does not exist" in res.stderr


# --- the burned estates' own JCL ---------------------------------------------------------------------------------------


def test_cbsa_jcl_matches_the_committed_estate_parm():
    jcl = CORPORA / "cics-banking-sample-application-cbsa" / "etc" / "install" / "base" / "buildjcl"
    if not jcl.is_dir():
        pytest.skip("no mainframe corpora (mainframe_corpus.py fetch)")
    doc, notices = options_from_jcl(jcl)
    assert validate(doc) == []
    committed = json.loads((OPTIONS / "cics-banking-sample-application-cbsa.json").read_text())
    want = {(e["option"], e["value"]) for e in committed["parm"]["default"]} - {("CICS", ""), ("NOCICS", "")}
    got = set(_parm(doc).items())
    assert want >= got and ("TRUNC", "OPT") in got and "CICS" in " ".join(notices)


def test_genapp_jcl_names_its_optfile():
    jcl = CORPORA / "cics-genapp" / "base" / "cntl" / "cobol.jcl"
    if not jcl.is_file():
        pytest.skip("no mainframe corpora (mainframe_corpus.py fetch)")
    doc, notices = options_from_jcl(jcl)
    assert validate(doc) == [] and any("OPTFILE" in n for n in notices)
