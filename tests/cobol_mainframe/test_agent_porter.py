"""The agent porter's sandbox (agent_porter): what the workspace holds, the one command the agent may run, and what
is taken back from it. The agent itself (Claude Code) is exercised by the porting loop, not here."""

import json
from pathlib import Path

from gitgalaxy.tools.cobol_to_java import agent_porter as ap


def _project(tmp_path: Path) -> tuple[Path, dict]:
    project = tmp_path / "project"
    svc = project / "src/main/java/com/x/service/PgmService.java"
    svc.parent.mkdir(parents=True)
    svc.write_text("class PgmService {}\n")
    (project / "src/main/java/com/x/entity").mkdir(parents=True)
    (project / "src/main/java/com/x/entity/Rec.java").write_text("class Rec {}\n")
    (project / "ai_agent_jobs/sources").mkdir(parents=True)
    (project / "ai_agent_jobs/sources/PGM.cbl.lst").write_text("    1 |       IDENTIFICATION DIVISION.\n")
    ticket = {
        "ticket": "PGM", "program": {"key": "PGM", "language": "cobol", "file": "PGM.cbl"},
        "target": {"service": "PgmService", "file": "src/main/java/com/x/service/PgmService.java",
                   "methods_to_port": ["runTask"], "config": {}},
        "deliverable": {"return": "the service"}, "facts": {"program": {}}, "worklist": [],
        "paragraphs": [{"name": "0000-MAIN", "start_line": 1, "lines": 9}],
        "source": {"program": {"file": "PGM.cbl", "listing": "sources/PGM.cbl.lst"}, "copybooks": []},
    }  # fmt: skip
    return project, ticket


def test_the_workspace_holds_the_ticket_the_sources_and_one_port_file(tmp_path):
    project, ticket = _project(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    port = ap.build_workspace(project, ticket, "1. a rule", work, "prove {port_dir} {report_dir}", None, "")
    ws = port.parent.parent
    try:
        assert not str(ws).startswith(str(Path.home() / ".claude"))  # Claude Code refuses writes there
        assert port.name == "PgmService.java" and port.read_text() == "class PgmService {}\n"
        assert (ws / "cobol/PGM.cbl.lst").is_file() and (ws / "java/com/x/entity/Rec.java").is_file()
        md = (ws / "TICKET.md").read_text()
        assert "1. a rule" in md and "| 0000-MAIN | 1 | 9 |" in md and "run exactly `./prove.sh`" in md
        assert json.loads((ws / "facts.json").read_text()) == {"program": {}}
        assert not (ws / "FEEDBACK.md").exists()
        script = (ws / "prove.sh").read_text()
        assert 'prove "$PWD/.overlay" "$PWD/.proofs/$n"' in script and "port/PgmService.java" in script
    finally:
        port.write_text("class PgmService { int ported; }\n")
        (port.parent / "NOTES.md").write_text("a defect kept")
        taken = ap.collect(ws, work)
    assert (taken / "PgmService.java").read_text() == "class PgmService { int ported; }\n"
    assert (taken / "NOTES.md").read_text() == "a defect kept" and not ws.exists()


def test_a_later_attempt_starts_from_the_failed_port_with_what_its_proof_found(tmp_path):
    project, ticket = _project(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    last = tmp_path / "001_PgmService.java"
    last.write_text("class PgmService { /* attempt 1 */ }\n")
    port = ap.build_workspace(project, ticket, "", work, "prove", last, "## Your previous attempt (1) was not proven")
    try:
        assert "attempt 1" in port.read_text()
        assert "was not proven" in (port.parent.parent / "FEEDBACK.md").read_text()
    finally:
        ap.collect(port.parent.parent, work)


def test_the_agent_may_run_only_the_proof():
    argv = ap.AGENT_ARGV
    allowed = argv[argv.index("--allowedTools") + 1 : argv.index("--output-format")]
    assert allowed == ["Read", "Glob", "Grep", "Bash(./prove.sh)"]
    assert "--restricted" in argv and "--strict-mcp-config" in argv and "--no-session-persistence" in argv
