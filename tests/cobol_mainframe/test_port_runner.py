"""#3753: the porting loop -- bring-your-own LLM, a person approves, the harness proves.

The loop is exercised end to end on a generated project with a porting ticket (#3752), with
a stand-in `command` backend (a Python one-liner that prints a fenced Java answer) and a
stand-in proof command: the prompt carries the ticket's rules, the service, the imported
generated classes and the listings; the answer's Java lands as an overlay (the generated
sources untouched); every event is logged; a person's review is required; and `status`
counts, per model, what was proposed, proven and approved.
"""

import json
import shlex
import shutil
import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_java import port_runner as pr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_port_tickets import JOB, POSTIT, TRANREC, _pipeline  # noqa: E402


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    base = tmp_path_factory.mktemp("port_loop")
    repo = base / "src_estate"
    for rel, text in {"cbl/POSTIT.cbl": POSTIT, "cpy/TRANREC.cpy": TRANREC, "jcl/NIGHTLY.jcl": JOB}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    out = base / "run"
    out.mkdir()
    return _pipeline(repo, out)


ANSWER = "Here it is.\n```java\npackage com.gitgalaxy.modernized.service;\n// ported\n```\n```notes\nnone\n```\n"


def _fake_backend(tmp_path: Path) -> str:
    script = tmp_path / "backend.py"
    script.write_text(f"import sys\nassert open(sys.argv[1]).read().startswith('You port')\nprint({ANSWER!r})\n")
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(script))} {{prompt_file}}"


def test_the_prompt_carries_the_ticket(project):
    system, user = pr.build_prompt(project, pr.load_ticket(project, "POSTIT"))
    assert "COMPUTE / ADD / SUBTRACT" in system and "```java fenced block" in system
    assert "public int runBatch(List<Dd> dds, String parm)" in user
    assert "## Generated class it may use: src/main/java/com/gitgalaxy/modernized/batch/Dd.java" in user
    assert "   14 |        PROCEDURE DIVISION." in user and "TR-AMT" in user


def test_extract_java_takes_the_last_java_block_and_the_notes():
    assert pr.extract_java(ANSWER) == ("package com.gitgalaxy.modernized.service;\n// ported\n", "none")
    assert pr.extract_java("no code here") == (None, "")


def test_the_loop_proposes_proves_and_needs_a_person(project, tmp_path):
    proj = tmp_path / "proj"
    shutil.copytree(project, proj)
    generated = (proj / "src/main/java/com/gitgalaxy/modernized/service/PostitService.java").read_text()
    assert pr.main(["run", str(proj), "--ticket", "POSTIT", "--backend", "command", "--model", "stand-in",
                    "--command", _fake_backend(tmp_path)]) == 0  # fmt: skip
    port = proj / "ai_agent_jobs/ports/POSTIT/overlay/service/PostitService.java"
    assert port.read_text().endswith("// ported\n")
    assert (proj / "src/main/java/com/gitgalaxy/modernized/service/PostitService.java").read_text() == generated
    assert pr.status(proj)["tickets"]["POSTIT"]["state"] == "proposed"

    proof = tmp_path / "proof.py"
    proof.write_text("import json, pathlib, sys\nd = pathlib.Path(sys.argv[2]); d.mkdir(parents=True)\n"
                     "(d / 'report.json').write_text(json.dumps({'outputs': {'OUT': {'equal': 3, 'records': 3}}}))\n"
                     "assert pathlib.Path(sys.argv[1], 'service', 'PostitService.java').is_file()\n")  # fmt: skip
    cmd = f"{shlex.quote(sys.executable)} {shlex.quote(str(proof))} {{port_dir}} {{report_dir}}"
    assert pr.main(["prove", str(proj), "--ticket", "POSTIT", "--command", cmd]) == 0
    st = pr.status(proj)["tickets"]["POSTIT"]
    assert (st["state"], st["summary"]) == ("proven", {"OUT": "3/3"})

    assert pr.main(["review", str(proj), "--ticket", "POSTIT", "--approve", "--by", "reviewer"]) == 0
    s = pr.status(proj)
    assert s["tickets"]["POSTIT"]["state"] == "approved"
    assert s["models"]["stand-in"] == {"proposed": 1, "proven": 1, "approved": 1, "rejected": 0}
    log = [json.loads(line) for line in (proj / "ai_agent_jobs/ports/port_log.jsonl").read_text().splitlines()]
    assert [e["event"] for e in log] == ["proposed", "proven", "approved"] and log[2]["by"] == "reviewer"


def test_a_person_can_submit_a_port_and_reject_one(project, tmp_path):
    proj = tmp_path / "proj"
    shutil.copytree(project, proj)
    mine = tmp_path / "PostitService.java"
    mine.write_text("package com.gitgalaxy.modernized.service;\n")
    assert pr.main(["submit", str(proj), "--ticket", "POSTIT", "--file", str(mine), "--by", "dev"]) == 0
    assert pr.main(["review", str(proj), "--ticket", "POSTIT", "--reject", "--by", "lead", "--note", "no"]) == 0
    s = pr.status(proj)
    assert s["tickets"]["POSTIT"]["state"] == "rejected" and s["models"]["person:dev"]["rejected"] == 1


def test_a_missing_api_key_stops_before_any_request(project, monkeypatch):
    monkeypatch.delenv("NO_SUCH_KEY_VAR", raising=False)
    with pytest.raises(SystemExit, match="NO_SUCH_KEY_VAR is not set"):
        pr.main(["run", str(project), "--ticket", "POSTIT", "--backend", "anthropic", "--model", "m",
                 "--api-key-env", "NO_SUCH_KEY_VAR"])  # fmt: skip


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://models.example.com/v1", "ftp://x/y"])
def test_a_key_never_leaves_unencrypted_or_to_a_file(url):
    with pytest.raises(SystemExit, match="must be https"):
        pr._post(url, {}, {"Authorization": "Bearer k"}, 5)


def test_https_and_a_local_model_are_accepted():
    for url in ("https://api.example.com/v1", "http://localhost:11434/v1", "http://127.0.0.1:8000/v1"):
        assert pr.check_url(url) == url


def test_a_redirect_is_refused_so_the_key_is_not_forwarded():
    import http.server
    import threading

    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            seen.append(self.path)
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/steal")
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    try:
        with pytest.raises(pr.urllib.error.HTTPError, match="refused"):
            pr._post(f"http://127.0.0.1:{srv.server_port}/v1", {}, {"Authorization": "Bearer k"}, 5)
    finally:
        srv.server_close()
    assert seen == ["/v1"]
