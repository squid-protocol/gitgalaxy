"""#7956: a program that issues a tokenless file WRITE / DELETE records them (and its plain READ INTO) as SPEC 6.2 events.

hc-file-delete's det port otherwise logged no READ, WRITE or DELETE (`task.write` / `task.delete` / `task.deleteHeld` /
`task.read` record none), so every java-ported cell failed at the first file event ("DELETE expected, got WRITEQ-TS").
The gate is the program's own commands; a program with none keeps the event-free calls (its port is unchanged)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from gitgalaxy.tools.cobol_to_java.det import cics_filecontrol as FC  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det.cics_filecontrol import FileControlCommands as FileControl  # noqa: E402


class _G:
    class p:  # noqa: N801
        class proc:  # noqa: N801
            execs: dict = {}

    n = 0

    @classmethod
    def tmpname(cls, base):
        cls.n += 1
        return f"{base}{cls.n}"


def _fc(*execs):
    _G.p.proc.execs = dict(enumerate(execs, 1))
    fc = FileControl.__new__(FileControl)
    fc.g = _G
    fc.store = lambda opts: "store(F)"
    fc.file_name = lambda t: '"F"'
    fc.field = lambda t: t
    fc.outcome = lambda *a: []
    fc._keylength = lambda *a: None
    fc.record_from = lambda opts: "REC"
    return fc


def test_the_gate_is_off_unless_a_crucible_builder_turns_it_on():
    fc = _fc("WRITE FILE('F') FROM(R) RIDFLD(K)")
    assert fc._records_file_events() is False
    assert "task.write(" in "\n".join(fc.file_update("WRITE", {"FILE": "'F'", "RIDFLD": "K", "FROM": "R"}, ""))
    assert FC.RECORD_FILE_UPDATES is False


def test_the_gate_is_a_tokenless_file_write_or_delete(monkeypatch):
    monkeypatch.setattr(FC, "RECORD_FILE_UPDATES", True)
    assert _fc("WRITE FILE('F') FROM(R) RIDFLD(K)")._records_file_events() is True
    assert _fc("DELETE FILE('F') RIDFLD(K)")._records_file_events() is True
    assert _fc("DELETE FILE('F')")._records_file_events() is True
    for other in ("WRITEQ TS QUEUE('Q') FROM(R)", "DELETE CONTAINER('C')", "DELETE FILE('F') TOKEN(T)",
                  "DELETE FILE('F') RIDFLD(K) GENERIC", "READ FILE('F') INTO(R) RIDFLD(K)"):  # fmt: skip
        assert _fc(other)._records_file_events() is False, other


def test_the_recorded_forms_are_the_event_calls(monkeypatch):
    monkeypatch.setattr(FC, "RECORD_FILE_UPDATES", True)
    fc = _fc("WRITE FILE('F') FROM(R) RIDFLD(K)")
    text = "\n".join(fc.file_update("WRITE", {"FILE": "'F'", "RIDFLD": "K", "FROM": "R"}, ""))
    assert "task.writeEvent(" in text and "task.write(" not in text
    text = "\n".join(fc.file_update("DELETE", {"FILE": "'F'", "RIDFLD": "K"}, ""))
    assert "task.deleteEvent(" in text and "task.delete(" not in text
    text = "\n".join(fc.file_update("DELETE", {"FILE": "'F'"}, ""))
    assert "task.deleteHeldEvent(" in text and "task.deleteHeld(" not in text


def test_a_program_without_one_keeps_the_event_free_calls(monkeypatch):
    monkeypatch.setattr(FC, "RECORD_FILE_UPDATES", True)
    fc = _fc("READ FILE('F') INTO(R) RIDFLD(K)")
    text = "\n".join(fc.file_update("DELETE", {"FILE": "'F'", "RIDFLD": "K"}, ""))
    assert "task.delete(" in text and "deleteEvent" not in text
