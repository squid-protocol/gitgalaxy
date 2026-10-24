"""The Che4z referee over LSP (#4438): framing, the client loop against an in-process fake server, and the
documentSymbol-to-facts mapping. No JVM and no Che4z jar: the real server is an external tool that runs on demand.
"""

from __future__ import annotations

import io
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "referees"))

import che4z_adapter as C
import facts as F


def sym(name: str, kind: int, start: int, end: int, children: list | None = None) -> dict:
    """A DocumentSymbol; lines are 0-based like LSP's."""
    rng = {"start": {"line": start, "character": 7}, "end": {"line": end, "character": 20}}
    return {"name": name, "kind": kind, "range": rng, "selectionRange": rng, "detail": "", "children": children or []}


# 1-based lines: the source the symbols below describe
SOURCE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROGA.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY CPYONE.
       01  WS-GROUP.
           05  WS-A          PIC X.
           05  WS-B          PIC 9.
       77  WS-SOLO           PIC X.
       PROCEDURE DIVISION.
           PERFORM P1.
      * a comment between the statements and the section
       MAIN-SEC SECTION.
       P1.
           CALL 'SUBX'.
           GO TO P2.
      * trailing comment
       P2.
           STOP RUN.
"""


def tree() -> list[dict]:
    return [
        sym("PROGRAM: PROGA", 5, 0, 18, [
            sym("IDENTIFICATION DIVISION", 6, 0, 1, [sym("PROGRAM-ID PROGA", 6, 1, 1)]),
            sym("DATA DIVISION", 6, 2, 8, [
                sym("WORKING-STORAGE SECTION", 19, 3, 8, [
                    sym("COPY CPYONE", 1, 4, 4),
                    sym("WS-GROUP", C.SYMBOL_STRUCT, 5, 7, [sym("WS-A", 13, 6, 6), sym("WS-B", 13, 7, 7)]),
                    sym("WS-SOLO", 13, 8, 8),
                ]),
            ]),
            sym("PROCEDURE DIVISION", 6, 9, 18, [
                sym("MAIN-SEC", 6, 12, 18, [sym("P1", 6, 13, 15), sym("P2", 6, 16, 18)]),
            ]),
        ])
    ]  # fmt: skip


def test_symbol_facts_map_every_channel_the_symbols_carry():
    f = C.symbol_facts(tree(), SOURCE.splitlines())
    assert f["program_ids"] == {"PROGA"}
    assert f["copybooks"] == {"CPYONE"}
    assert f["units"] == {"MAIN-SEC", "P1", "P2"}
    assert f["data_items"] == {"L6 01 WS-GROUP", "L7 05 WS-A", "L8 05 WS-B", "L9 77 WS-SOLO"}


def test_extents_stop_before_trailing_comments_and_at_the_first_paragraph():
    f = C.symbol_facts(tree(), SOURCE.splitlines())
    # P2's range ends on line 19 (0-based 18) which is code; P1's own range ends on line 16
    assert "P1 L14-16" in f["unit_extents"]
    assert "P2 L17-19" in f["unit_extents"]
    # a section's own extent ends where its first paragraph starts, minus comments / blanks (its header line only)
    assert "MAIN-SEC L13-13" in f["unit_extents"]
    # the main line is the division header plus the statement before the first section; the comment is not its own
    assert f"{F.MAIN_LINE} L10-11" in f["unit_extents"]
    assert F.MAIN_LINE not in f["units"]


def test_main_line_without_statements_has_no_extent():
    src = ["       PROCEDURE DIVISION.", "       P1.", "           STOP RUN."]
    f = C.symbol_facts([sym("PROGRAM: X", 5, 0, 2, [sym("PROCEDURE DIVISION", 6, 0, 2, [sym("P1", 6, 1, 2)])])], src)
    assert f["unit_extents"] == {"P1 L2-3"}


def test_second_program_units_are_prefixed():
    src = [
        "       PROGRAM-ID. A.",
        "       P1.",
        "           STOP RUN.",
        "       PROGRAM-ID. B.",
        "       P1.",
        "           STOP RUN.",
    ]
    tops = [
        sym("PROGRAM: A", 5, 0, 2, [sym("PROCEDURE DIVISION", 6, 1, 2, [sym("P1", 6, 1, 2)])]),
        sym("PROGRAM: B", 5, 3, 5, [sym("PROCEDURE DIVISION", 6, 4, 5, [sym("P1", 6, 4, 5)])]),
    ]
    f = C.symbol_facts(tops, src)
    assert f["units"] == {"P1", "B:P1"}


def test_an_item_whose_level_cannot_be_read_is_skipped_not_guessed():
    f = C.symbol_facts([sym("PROGRAM: X", 5, 0, 0, [sym("DATA DIVISION", 6, 0, 0, [sym("WS-X", 13, 40, 40)])])], ["x"])
    assert f["data_items"] == set()


@pytest.mark.parametrize("line", ["000100 01  WS-A PIC X.", "       01  WS-A PIC X.", "01 WS-A PIC X."])
def test_level_is_read_from_fixed_sequenced_and_free_lines(line):
    assert C._symbol_level([line], 0) == 1


def test_framing_round_trips_and_ends_at_eof():
    buf = io.BytesIO()
    C.write_message(buf, {"jsonrpc": "2.0", "id": 1, "result": ["é"]})
    C.write_message(buf, {"jsonrpc": "2.0", "method": "x"})
    buf.seek(0)
    assert C.read_message(buf) == {"jsonrpc": "2.0", "id": 1, "result": ["é"]}
    assert C.read_message(buf) == {"jsonrpc": "2.0", "method": "x"}
    assert C.read_message(buf) is None


class FakeServer:
    """Speaks just enough of the Che4z server over two OS-less pipes: asks for config and a copybook first."""

    def __init__(self, tmp_path: Path, symbols: list[dict]) -> None:
        self.symbols, self.seen, self.answers = symbols, [], {}
        self.cpy = tmp_path / "CPYONE.cpy"
        self.cpy.write_text("       01 X PIC X.\n", encoding="utf-8")
        self.c2s_r, self.c2s_w = _pipe()
        self.s2c_r, self.s2c_w = _pipe()
        threading.Thread(target=self.run, daemon=True).start()

    def send(self, msg: dict) -> None:
        C.write_message(self.s2c_w, {"jsonrpc": "2.0", **msg})

    def run(self) -> None:
        while (m := C.read_message(self.c2s_r)) is not None:
            self.seen.append(m.get("method") or "response")
            if "result" in m and "method" not in m:
                self.answers[m["id"]] = m["result"]
            method = m.get("method")
            if method == "initialize":
                self.send({"id": m["id"], "result": {"capabilities": {}}})
            elif method == "textDocument/didOpen":
                uri = m["params"]["textDocument"]["uri"]
                self.send(
                    {
                        "id": "c1",
                        "method": "workspace/configuration",
                        "params": {"items": [{"section": "a"}, {"section": "b"}]},
                    }
                )
                self.send({"id": "c2", "method": "copybook/resolve", "params": [uri, "cpyone", "COBOL"]})
                self.send({"id": "c3", "method": "copybook/resolve", "params": [uri, "MISSING", "COBOL"]})
                self.send({"id": "c4", "method": "file/content", "params": self.cpy.as_uri()})
                self.send({"method": "textDocument/publishDiagnostics", "params": {"uri": "file:///elsewhere", "diagnostics": [{"severity": 1}]}})  # fmt: skip
                self.send({"method": "textDocument/publishDiagnostics", "params": {"uri": uri, "diagnostics": [{"severity": 2, "message": "w"}]}})  # fmt: skip
            elif method == "textDocument/documentSymbol":
                self.send({"id": m["id"], "result": self.symbols})
            elif method == "shutdown":
                self.send({"id": m["id"], "result": None})


def _pipe() -> tuple[io.BufferedReader, io.BufferedWriter]:
    import os

    r, w = os.pipe()
    return os.fdopen(r, "rb"), os.fdopen(w, "wb")


def test_session_answers_the_servers_requests_and_returns_symbols(tmp_path):
    fake = FakeServer(tmp_path, tree())
    session = C.LspSession(fake.s2c_r, fake.c2s_w, C.copybook_resolver(tmp_path))
    session.start()
    src = tmp_path / "a.cbl"
    src.write_text(SOURCE, encoding="utf-8")
    symbols, diags = session.open_and_analyse(src, SOURCE, timeout=10)
    session.stop()
    assert symbols == tree()
    assert diags == [{"severity": 2, "message": "w"}]  # the other file's diagnostics are not this member's
    assert fake.answers["c1"] == [None, None]
    assert fake.answers["c2"] == (tmp_path / "CPYONE.cpy").resolve().as_uri()  # case-insensitive name
    assert fake.answers["c3"] is None
    assert fake.answers["c4"] == "       01 X PIC X.\n"


def test_session_reports_a_closed_pipe_and_a_silent_server(tmp_path):
    r, w = _pipe()
    w.close()  # EOF at once
    session = C.LspSession(r, io.BytesIO(), lambda n: None)
    with pytest.raises(EOFError):
        session.wait(lambda m: True, timeout=5)
    r2, w2 = _pipe()
    silent = C.LspSession(r2, io.BytesIO(), lambda n: None)
    with pytest.raises(TimeoutError):
        silent.wait(lambda m: True, timeout=0.2)
    w2.close()


def test_a_server_error_response_becomes_a_runtime_error(tmp_path):
    r, w = _pipe()
    C.write_message(w, {"jsonrpc": "2.0", "id": 1, "error": {"code": -32800, "message": "cancelled"}})
    session = C.LspSession(r, io.BytesIO(), lambda n: None)
    with pytest.raises(RuntimeError, match="cancelled"):
        session.request("textDocument/documentSymbol", {}, timeout=5)


def test_copybook_resolver_indexes_every_copy_extension(tmp_path):
    for n in ("a.cpy", "B.CPY", "c.cbl", "d.txt"):
        (tmp_path / n).write_text("x", encoding="utf-8")
    r = C.copybook_resolver(tmp_path)
    assert r("A") and r("b") and r("C")
    assert r("D") is None


def test_read_uri_reads_a_file_uri_with_spaces_and_escapes(tmp_path):
    cpy = tmp_path / "my dir" / "a%b.cpy"
    cpy.parent.mkdir()
    cpy.write_text("       01 X PIC X.\n", encoding="utf-8")
    assert C._read_uri(cpy.resolve().as_uri()) == "       01 X PIC X.\n"
    assert C._read_uri("http://example/x.cpy") is None


def test_read_uri_converts_a_windows_drive_uri_through_url2pathname(monkeypatch):
    seen = []
    monkeypatch.setattr("urllib.request.url2pathname", lambda p: seen.append(p) or str(Path("/nonexistent/x")))
    assert C._read_uri("file:///C:/a%20b/x.cpy") is None
    assert seen == ["/C:/a%20b/x.cpy"]
