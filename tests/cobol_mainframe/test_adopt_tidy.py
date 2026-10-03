"""#4179: an adopted port's stale scaffold TODOs are tidied -- comments only, verified."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import porting_loop as pl  # noqa: E402

TODO = pl.SCAFFOLD_TODO
IMPLEMENTED = f"""class S {{
    /** A CICS transaction entered the program.{TODO} */
    public void handleTransaction(String transid) {{
        log.info("S: handleTransaction");
        runTask(task);
    }}
}}"""
STUB = f"""class S {{
    /** Another program LINKed / XCTLed to this one.{TODO} */
    public Dto handleLink(Dto request) {{
        log.info("S: handleLink");
        return request;
    }}
}}"""


def test_the_implement_todo_is_dropped_from_an_implemented_handler():
    new, dropped, retagged = pl.tidy_scaffold(IMPLEMENTED)
    assert TODO not in new and (dropped, retagged) == (1, 0)
    assert "/** A CICS transaction entered the program. */" in new


def test_a_handler_still_the_generated_stub_keeps_its_todo():
    new, dropped, _ = pl.tidy_scaffold(STUB)
    assert new == STUB and dropped == 0


def test_resp_notes_are_retagged_as_facts_about_the_cobol():
    src = "/**\n * TODO: the RESP of LINK at line 8 (paragraph 000-MAIN) is never tested\n */\nclass S { }"
    new, _, retagged = pl.tidy_scaffold(src)
    assert retagged == 1 and "COBOL: the RESP of LINK at line 8" in new and "TODO" not in new


def test_strip_comments_keeps_string_literals():
    assert pl.strip_comments('x = "/* not a comment */"; // gone') == 'x = "/* not a comment */";'


def test_a_code_change_is_refused(monkeypatch):
    monkeypatch.setattr(pl, "RESP_NOTE", "x();")  # a "retag" that would touch code outside a comment
    with pytest.raises(RuntimeError):
        pl.tidy_scaffold("int a; // TODO: the RESP of X at line 1 (paragraph P) is never tested\nint b;\n"
                         .replace("// ", "").replace("\n", " "))


def test_tidy_port_records_the_edit_in_provenance(tmp_path):
    (tmp_path / "service").mkdir()
    (tmp_path / "service" / "S.java").write_text(IMPLEMENTED, encoding="utf-8")
    (tmp_path / "provenance.json").write_text(json.dumps({"program": "S"}), encoding="utf-8")
    assert pl.tidy_port(tmp_path) == {"dropped": 1, "retagged": 0}
    assert "comment_edits" in json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
