"""#3651: the migration worklist -- every TODO the generators leave, as one plan.

Pins the join of the two sources (the Java's TODO comments and the #3650 manifest's
TODOs), the categories and their drift guard over the generators' own TODO templates,
owner attribution, and a real scan end to end.
"""

import json
import re
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db
from gitgalaxy.tools.cobol_to_java import cobol_to_java_worklist as wlmod
from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import TraceLog
from gitgalaxy.tools.cobol_to_java.cobol_to_java_worklist import (
    UNCATEGORISED,
    build_worklist,
    classify,
    normalize,
    render_markdown,
)

FORGE_DIR = Path(wlmod.__file__).parent


def _generator_todo_templates() -> list[tuple[str, str]]:
    """(file:line, text) of every `TODO:` a generator writes, placeholders as X, split literals joined."""
    out = []
    for path in sorted(FORGE_DIR.glob("*.py")):
        if path.name == "cobol_to_java_worklist.py":
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if "TODO:" not in line:  # (a `# TODO:` line here is inside a template: YAML the forge writes)
                continue
            text = " ".join(lines[i : i + 3])
            text = text[text.index("TODO:") :]
            text = re.sub(r"\{[^{}]*\}", "X", text)
            text = re.sub(r'"\s*,\s*f?"', " ", text)  # adjacent literals in a list
            text = re.sub(r'\bf"|"|\*|\\n', " ", text)
            out.append((f"{path.name}:{i + 1}", re.sub(r"\s+", " ", text)))
    return out


def test_every_generator_todo_has_a_category():
    """A generator that starts writing a new kind of TODO must give it a category here."""
    templates = _generator_todo_templates()
    assert len(templates) >= 20  # the scan finds them
    unfiled = [(where, text[:80]) for where, text in templates if classify(text) is UNCATEGORISED]
    assert unfiled == []


@pytest.mark.parametrize(
    "text, category",
    [("TODO: this site passes WS-A; ACCTINQ receives DFHCOMMAREA", "commarea-mismatch"),
     ("TODO: no OPEN mode for this DD is known (no JCL step ...)", "open-mode"),
     ("TODO: the RESP of LINK at line 8 (paragraph 000-MAIN) is never tested", "unchecked-resp"),
     ("// TODO: [AI AGENT] split the transaction here", "transaction-split"),
     ("TODO: something new", "uncategorised")],
)  # fmt: skip
def test_classify(text, category):
    assert classify(text).id == category


def test_normalize_strips_the_tag_and_comment_closer():
    assert normalize("    /** CALLed. TODO: [AI AGENT] implement from the program's business rules. */") == (
        "implement from the program's business rules"
    )


def _java(root: Path, rel: str, text: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text, encoding="utf-8")


SVC = "src/main/java/p/service/MenuService.java"
CTL = "src/main/java/p/controller/MenuController.java"
REPO = "src/main/java/p/repository/db2/AccountRepository.java"


def test_the_join_claims_merges_folds_and_attributes(tmp_path):
    _java(tmp_path, SVC, "class MenuService {\n"
                         " * TODO: the RESP of LINK at line 8 (paragraph 000-MAIN) is never tested\n"
                         "    // TODO: port paragraph 100-X's logic\n"
                         "    // TODO: port paragraph 100-X's logic\n}\n")  # fmt: skip
    _java(tmp_path, CTL, "/**\n * TODO: callers also pass WS-A (cbl/B.cbl, 10 bytes)\n *  at cbl/B.cbl:9.\n */\n")
    _java(
        tmp_path, REPO, " * TODO: this SQL is DB2's; the configured database is postgresql -- review each statement.\n"
    )
    fact = {"source": "cbl/MENU.cbl:8", "ledger_field": "call targets", "field_testing": "open (6 public / 0 private)"}
    caller = {"source": "cbl/B.cbl:9", "ledger_field": "entry transactions"}
    todo_mismatch = "TODO: callers also pass WS-A (cbl/B.cbl, 10 bytes) at cbl/B.cbl:9."
    manifest = {"artifacts": [
        {"file": SVC, "symbol": "MenuService", "facts": [fact],
         "todos": ["TODO: the RESP of LINK at line 8 (paragraph 000-MAIN) is never tested"]},
        {"file": SVC, "symbol": "MenuService", "facts": [{**fact, "source": "cbl/MENU.cbl:40"}],
         "todos": ["TODO: the RESP of SEND at line 40 (paragraph 900-SEND) is never tested"]},  # past the cut-off
        {"file": CTL, "symbol": "MenuController#link", "facts": [caller], "todos": [todo_mismatch]},
        {"file": CTL, "symbol": "MenuController#transactionMENU", "facts": [caller], "todos": [todo_mismatch]},
        {"file": REPO, "symbol": "AccountRepository#selectL11Menu", "facts": [{"source": "cbl/MENU.cbl:11"}],
         "todos": ["TODO: DB2 SQL on postgresql -- review the statement"]},
        {"file": REPO, "symbol": "AccountRepository#insertL14Menu", "facts": [{"source": "cbl/MENU.cbl:14"}],
         "todos": ["TODO: DB2 SQL on postgresql -- review the statement"]},
    ]}  # fmt: skip
    wl = build_worklist(tmp_path, manifest, {"clean_room": "x"}, owners={"Menu": "cbl/MENU.cbl"})
    got = [(i["category"], i["file"].rsplit("/", 1)[-1], i["line"], i["symbols"], i["program"]) for i in wl["items"]]
    assert got == [
        # one Java note restated on two endpoints: one item, both symbols; filed under the program, not the caller
        ("commarea-mismatch", "MenuController.java", 2, ["MenuController#link", "MenuController#transactionMENU"],
         "cbl/MENU.cbl"),
        ("unchecked-resp", "MenuService.java", 2, ["MenuService"], "cbl/MENU.cbl"),
        ("unchecked-resp", "MenuService.java", None, ["MenuService"], "cbl/MENU.cbl"),  # manifest-only: kept
        # per statement from the manifest; the repository's one class-level line is their summary, not a 3rd item
        ("db2-dialect", "AccountRepository.java", None, ["AccountRepository#insertL14Menu"], "cbl/MENU.cbl"),
        ("db2-dialect", "AccountRepository.java", None, ["AccountRepository#selectL11Menu"], "cbl/MENU.cbl"),
        # two Java lines with the same text are two items
        ("business-logic", "MenuService.java", 3, [], "cbl/MENU.cbl"),
        ("business-logic", "MenuService.java", 4, [], "cbl/MENU.cbl"),
    ]  # fmt: skip
    assert wl["items"][0]["text"] == "callers also pass WS-A (cbl/B.cbl, 10 bytes) at cbl/B.cbl:9"  # javadoc joined
    assert wl["summary"]["by_nature"] == {"conflict": 1, "fact-gap": 0, "review": 4, "port": 2}
    assert [i["id"] for i in wl["items"]] == [f"WL-{n:04d}" for n in range(1, 8)]
    md = render_markdown(wl)
    assert "| conflict | 1 |" in md and "- [ ] **WL-0002** `src/main/java/p/service/MenuService.java:2`" in md
    assert "  - fact: `cbl/MENU.cbl:8`, call targets (open (6 public / 0 private))" in md


def test_without_a_manifest_every_java_todo_is_an_item(tmp_path):
    _java(tmp_path, SVC, "    // TODO: [AI AGENT] Implement extracted business rules here.\n")
    wl = build_worklist(tmp_path, None)
    assert [(i["category"], i["program"]) for i in wl["items"]] == [("business-logic", "(no COBOL source cited)")]


def test_tracelog_keeps_one_symbol_backed_by_different_lines():
    """#3651 found #3650 dropping all but a service's first unchecked RESP (same file, symbol and kind)."""
    trace = TraceLog()
    for line in (8, 40, 8):
        trace.record(SVC, "Class", "unchecked-response", [{"source": f"cbl/MENU.cbl:{line}"}], [f"TODO: {line}"])
    assert [a["todos"] for a in trace.as_dict({})["artifacts"]] == [["TODO: 8"], ["TODO: 40"]]


MENU = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MENU.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-AREA.
           05 WS-ID           PIC 9(5).
           05 WS-FLAG         PIC X.
       01  WS-RESP            PIC S9(8) COMP.
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS LINK PROGRAM('ACCTINQ') COMMAREA(WS-AREA)
                RESP(WS-RESP) END-EXEC.
           EXEC CICS SEND TEXT FROM(WS-AREA) RESP(WS-RESP) END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""

OTHER = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. OTHER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-OTHER.
           05 WS-CODE         PIC X(4).
           05 WS-AMOUNT       PIC 9(7)V99.
           05 WS-NOTE         PIC X(30).
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS LINK PROGRAM('ACCTINQ') COMMAREA(WS-OTHER) END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""

ACCTINQ = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTINQ.
       DATA DIVISION.
       LINKAGE SECTION.
       01  DFHCOMMAREA.
           05 LK-ACCT-ID      PIC 9(11).
           05 LK-NAME         PIC X(20).
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS RETURN END-EXEC.
"""

CSD = """\
 DEFINE TRANSACTION(MENU) GROUP(APP)
        PROGRAM(MENU)
"""


def test_a_real_run_writes_the_worklist_and_its_audit(tmp_path):
    repo = tmp_path / "estate"
    for rel, text in {
        "cbl/MENU.cbl": MENU,
        "cbl/OTHER.cbl": OTHER,
        "cbl/ACCTINQ.cbl": ACCTINQ,
        "csd/APP.csd": CSD,
    }.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    db = scan_to_db(repo, tmp_path / "scan")
    work = tmp_path / "work" / "estate"
    shutil.copytree(repo, work)
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = (tmp_path / "work").glob("estate_gitgalaxy_clean_*")
    with patch.object(sys, "argv", ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]):
        java_controller.main()
    (java,) = (tmp_path / "work").glob("estate_gitgalaxy_java_spring_*")
    wl = json.loads((java / "migration_worklist.json").read_text(encoding="utf-8"))
    items = {(i["category"], i["program"]) for i in wl["items"]}
    # MENU and OTHER pass ACCTINQ two different records; MENU asks for two RESPs and tests neither
    assert "commarea-mismatch" in {c for c, _ in items}
    resp = [i for i in wl["items"] if i["category"] == "unchecked-resp"]
    assert len(resp) == 2 and all(i["program"] == "cbl/MENU.cbl" and i["facts"] for i in resp)
    assert ("configuration", "(project configuration)") in items  # application.yml's credentials
    assert all(i["program"].startswith("cbl/") for i in wl["items"] if i["category"] != "configuration")
    assert all((java / i["file"]).is_file() for i in wl["items"])
    assert (java / "migration_worklist.md").read_text(encoding="utf-8").startswith("# Migration worklist\n")
    audit = (java / "java_migration_audit.txt").read_text(encoding="utf-8")
    assert f"  • Open items : {wl['summary']['items']} across {wl['summary']['programs']} COBOL sources" in audit
    assert "CICS responses the COBOL never tests" in audit
