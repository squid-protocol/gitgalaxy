"""#3237: porting tickets in port order -- the programs the most other code depends on first.

A small estate through a real scan, the refractor and cobol-to-java: RATES is CALLed by
POSTIT and by BILLIT, and a JCL step runs POSTIT. With #3237 the CALLs are dependency-graph
edges, so RATES has the most callers and the largest blast radius: its ticket is first,
port_order.json / .md say so, the worklist lists it first, and the porting loop's `status`
offers it as the next ticket to take.
"""

import json
import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_java import port_runner

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_port_tickets import _pipeline  # noqa: E402


def _program(name: str, calls: str = "") -> str:
    call = f"           CALL 'RATES' USING WS-AMT.\n" if calls else ""
    return (
        "       IDENTIFICATION DIVISION.\n"
        f"       PROGRAM-ID. {name}.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-AMT            PIC S9(7)V99 VALUE 0.\n"
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           ADD 1 TO WS-AMT.\n"
        f"{call}"
        "           GOBACK.\n"
    )


ESTATE = {
    "cbl/POSTIT.cbl": _program("POSTIT", calls="RATES"),
    "cbl/BILLIT.cbl": _program("BILLIT", calls="RATES"),
    "cbl/RATES.cbl": _program("RATES"),
    "jcl/NIGHTLY.jcl": "//NIGHTLY  JOB (ACCT),'POST'\n//RUN      EXEC PGM=POSTIT\n",
}


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    base = tmp_path_factory.mktemp("port_order")
    repo = base / "src_estate"
    for rel, text in ESTATE.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    out = base / "run"
    out.mkdir()
    return _pipeline(repo, out)


def test_the_most_depended_on_program_is_ported_first(project):
    order = json.loads((project / "ai_agent_jobs/port_order.json").read_text())
    assert [o["key"] for o in order][0] == "RATES"
    rates = order[0]
    assert rates["callers"] == 2 and rates["file"] == "cbl/RATES.cbl"
    assert [o["rank"] for o in order] == list(range(1, len(order) + 1))
    keys = [(-o["callers"], -o["blast_radius"]) for o in order]
    assert keys == sorted(keys)  # callers first, blast radius breaks ties
    ticket = json.loads((project / "ai_agent_jobs/RATES_port_ticket.json").read_text())
    assert ticket["priority"]["rank"] == 1 and ticket["priority"]["of"] == len(order)
    assert "**Port order 1 of" in (project / "ai_agent_jobs/RATES_port_ticket.md").read_text()
    assert "| 1 | `cbl/RATES.cbl` | 2 |" in (project / "ai_agent_jobs/port_order.md").read_text()


def test_the_worklist_and_the_loop_follow_the_port_order(project):
    md = (project / "migration_worklist.md").read_text()
    table = md.split("## By program source", 1)[1]
    assert table.index("1. `cbl/RATES.cbl`") < table.index("`cbl/POSTIT.cbl`")
    st = port_runner.status(project)
    assert list(st["tickets"])[0] == "RATES" and st["next"] == "RATES"
