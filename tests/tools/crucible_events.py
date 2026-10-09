"""Constructors for HAND-TRACED cics-crucible expected logs (its SPEC.md, section 6; format `cics-crucible/1`).

The crucible's rule (its AGENTS.md, rules 2 and 3): an expected log is derived by hand from IBM's documentation,
never by running an implementation -- not the stub runtime, not a port, not an emulator. A script that writes the
logs only FORMATS values a person traced: so it imports nothing but the standard library and this module, which is
itself standard-library only and imports nothing from gitgalaxy or a runtime. `crucible_case.py check-hand-derived
SCRIPT` enforces that on the script.

    import sys; sys.path.insert(0, "<gitgalaxy>/tests/tools")
    import crucible_events as ev

    clock = ev.Clock("2026-03-02T10:00:00")
    log = ev.expected("gt-x", "happy", [
        ev.task(1, "GT31", "GTX", clock.at(0), ev.terminal(0), [
            ev.receive("GTX", "NORMAL", 6, ev.text_area("GT31 T", 6)),
            ev.writeq_ts("GTX", "GTLOG", ev.text_area("LOGGED", 6), "NORMAL", item=1),
            ev.return_("GTX")], termid="T001", eibaid="ENTER")],
        final_ts={"GTLOG": ["LOGGED"]})
    ev.write_case(case_dir, case_doc, {"happy": log})

Every event constructor checks its keys against EVENTS (SPEC 6.2's table, as schema/expected.schema.json states it):
a missing required key or an unknown one raises ValueError, so a typo fails in the script, not in validate.py.
Python spells the key `from` as `from_`; everything else is the JSON key.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

FORMAT_CASE = "cics-crucible/case/1"
FORMAT_EXPECTED = "cics-crucible/expected/1"
TRAPS = ("condition-handling", "hex-attributes", "commarea-mismatch", "ghost-tasks", "pseudo-conversational")

# event -> (required keys, optional keys), besides `event`, `program` and `note`
EVENTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "SEND-MAP": (("map", "mapset", "options", "fields"), ("cursor",)),
    "SEND-TEXT": (("text", "length", "options"), ()),
    "SEND-CONTROL": (("options",), ("cursor",)),
    "RECEIVE-MAP": (("map", "mapset", "resp"), ()),
    "RECEIVE": (("resp", "length", "data"), ()),
    "LINK": (("target", "length", "commarea", "resp"), ("resp2",)),
    "XCTL": (("target", "length", "commarea", "resp"), ("resp2",)),
    "RETURN": (("level",), ("transid", "commarea", "caller_commarea", "immediate", "resp", "resp2")),  # #4270 (X27)
    "START": (
        ("transid", "termid", "from", "protect", "resp", "expires"),
        ("interval", "time", "reqid", "rtransid", "rtermid", "queue", "resp2"),
    ),
    "RETRIEVE": (("resp", "data"), ("length", "rtransid", "rtermid", "queue")),
    "CANCEL": (("reqid", "resp"), ()),
    "RUN": (("transid", "resp"), ("resp2",)),
    "READQ-TS": (("queue", "item", "resp", "data"), ("length",)),
    "WRITEQ-TS": (("queue", "data", "resp", "item"), ()),
    "READ": (("file", "ridfld", "resp"), ()),
    "ABEND": (("abcode", "cause", "outcome"), ("condition", "exit")),
}
# Keys the crucible's main has (cics-crucible, #4270 X27) but no release yet: the pin's schema lacks them, so the table
# check (tests/tools/test_crucible_case.py) leaves them out until the pin moves
UNRELEASED: dict[str, tuple[str, ...]] = {"RETURN": ("immediate", "resp", "resp2")}
ABEND_FOR = {
    "NOTFND": "AEIM",
    "LENGERR": "AEIV",
    "ITEMERR": "AEIZ",
    "QIDERR": "AEYH",
    "MAPFAIL": "AEI9",
    "ENDDATA": "AEI2",
    "PGMIDERR": "AEI0",
    "INVREQ": "AEIP",
}  # SPEC 6.2 (IBM's AEIx / AEYx codes)


# ---- values (SPEC 6.1) ------------------------------------------------------------------------------------------
def text_area(text: str, length: int) -> dict[str, Any]:
    """An area given as text: trailing blanks are optional (it is blank-padded to `length` for comparison)."""
    if len(text.rstrip()) > length:
        raise ValueError(f"text {text!r} is longer than its area ({length})")
    return {"length": length, "text": text.rstrip()}


def hex_area(hexstr: str, length: int) -> dict[str, Any]:
    h = hexstr.upper()
    if len(h) % 2 or any(c not in "0123456789ABCDEF" for c in h) or len(h) // 2 > length:
        raise ValueError(f"bad hex area {hexstr!r} for length {length}")
    return {"length": length, "hex": h}


def layout_area(length: int, layout: str, fields: dict[str, Any]) -> dict[str, Any]:
    return {"length": length, "layout": layout, "fields": dict(fields)}


def hex_value(hexstr: str) -> dict[str, str]:
    return {"hex": hexstr.upper()}


class Clock:
    """Virtual time: `Clock("2026-03-02T10:00:00").at(10)` is ten seconds after the case's clock."""

    def __init__(self, base: str):
        self.base = _dt.datetime.strptime(base, "%Y-%m-%dT%H:%M:%S")  # noqa: DTZ007 -- a virtual, zoneless clock

    def at(self, seconds: int) -> str:
        return (self.base + _dt.timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%S")

    def __str__(self) -> str:
        return self.at(0)


# ---- events (SPEC 6.2) ------------------------------------------------------------------------------------------
def event(kind: str, program: str, note: str | None = None, **keys: Any) -> dict[str, Any]:
    """One event, its keys checked against EVENTS. `from_` is the JSON key `from`."""
    if kind not in EVENTS:
        raise ValueError(f"unknown event {kind!r} (SPEC 6.2: {', '.join(EVENTS)})")
    keys = {("from" if k == "from_" else k): v for k, v in keys.items()}
    required, optional = EVENTS[kind]
    missing = [k for k in required if k not in keys]
    unknown = [k for k in keys if k not in required and k not in optional]
    if missing or unknown:
        raise ValueError(f"{kind}: " + "; ".join(([f"missing {missing}"] if missing else []) +
                                                 ([f"unknown {unknown}"] if unknown else [])))  # fmt: skip
    out: dict[str, Any] = {"event": kind, "program": program}
    out.update((k, keys[k]) for k in required)
    out.update((k, keys[k]) for k in optional if k in keys)
    if note is not None:
        out["note"] = note
    return out


def send_text(program: str, text: Any, length: int, options: list[str] | None = None, **kw: Any) -> dict[str, Any]:
    return event("SEND-TEXT", program, text=text, length=length, options=sorted(options or []), **kw)


def send_control(program: str, options: list[str], **kw: Any) -> dict[str, Any]:
    return event("SEND-CONTROL", program, options=sorted(options), **kw)


def send_map(program: str, map_: str, mapset: str, fields: dict[str, Any], options: list[str] | None = None,
             **kw: Any) -> dict[str, Any]:  # fmt: skip
    return event("SEND-MAP", program, map=map_, mapset=mapset, options=sorted(options or []), fields=fields, **kw)


def receive_map(program: str, map_: str, mapset: str, resp: str = "NORMAL", **kw: Any) -> dict[str, Any]:
    return event("RECEIVE-MAP", program, map=map_, mapset=mapset, resp=resp, **kw)


def receive(program: str, resp: str, length: int, data: dict[str, Any] | None, **kw: Any) -> dict[str, Any]:
    return event("RECEIVE", program, resp=resp, length=length, data=data, **kw)


def link(program: str, target: str, length: int = 0, commarea: dict[str, Any] | None = None, resp: str = "NORMAL",
         **kw: Any) -> dict[str, Any]:  # fmt: skip
    return event("LINK", program, target=target, length=length, commarea=commarea, resp=resp, **kw)


def xctl(program: str, target: str, length: int = 0, commarea: dict[str, Any] | None = None, resp: str = "NORMAL",
         **kw: Any) -> dict[str, Any]:  # fmt: skip
    return event("XCTL", program, target=target, length=length, commarea=commarea, resp=resp, **kw)


def return_(program: str, level: int = 1, transid: str | None = None, commarea: dict[str, Any] | None = None,
            **kw: Any) -> dict[str, Any]:  # fmt: skip
    """RETURN. At level 1 `transid` / `commarea` are always written (null when none); a LINKed program's RETURN
    (level > 1) carries `caller_commarea` instead."""
    if "resp" in kw:  # #4270 (X27): a RETURN IMMEDIATE that failed went on in the program: no area of its own
        return event("RETURN", program, level=level, transid=transid, **kw)
    if level == 1:
        return event("RETURN", program, level=1, transid=transid, commarea=commarea, **kw)
    return event("RETURN", program, level=level, **kw)


def start(program: str, transid: str, expires: str | None, termid: str | None = None, from_: Any = None,
          protect: bool = False, resp: str = "NORMAL", **kw: Any) -> dict[str, Any]:  # fmt: skip
    """START. Give `interval="hhmmss"` or `time="hhmmss"`, and reqid / rtransid / rtermid / queue only when the
    program names them. `expires` is null unless resp is NORMAL."""
    return event("START", program, transid=transid, termid=termid, from_=from_, protect=protect, resp=resp,
                 expires=expires, **kw)  # fmt: skip


def retrieve(program: str, resp: str, data: Any, **kw: Any) -> dict[str, Any]:
    return event("RETRIEVE", program, resp=resp, data=data, **kw)


def cancel(program: str, reqid: str, resp: str = "NORMAL", **kw: Any) -> dict[str, Any]:
    return event("CANCEL", program, reqid=reqid, resp=resp, **kw)


def run(program: str, transid: str, resp: str = "NORMAL", **kw: Any) -> dict[str, Any]:
    return event("RUN", program, transid=transid, resp=resp, **kw)


def readq_ts(program: str, queue: str, item: Any, resp: str, data: Any, **kw: Any) -> dict[str, Any]:
    return event("READQ-TS", program, queue=queue, item=item, resp=resp, data=data, **kw)


def writeq_ts(program: str, queue: str, data: dict[str, Any], resp: str = "NORMAL", item: int = 1,
              **kw: Any) -> dict[str, Any]:  # fmt: skip
    return event("WRITEQ-TS", program, queue=queue, data=data, resp=resp, item=item, **kw)


def read(program: str, file: str, ridfld: Any, resp: str = "NORMAL", **kw: Any) -> dict[str, Any]:
    return event("READ", program, file=file, ridfld=ridfld, resp=resp, **kw)


def abend(program: str, abcode: str, cause: str = "command", outcome: str = "terminated", **kw: Any) -> dict[str, Any]:
    """EXEC CICS ABEND (cause `command`), or an unhandled condition: `abend_for("GTX", "INVREQ")`."""
    return event("ABEND", program, abcode=abcode, cause=cause, outcome=outcome, **kw)


def abend_for(program: str, condition: str, **kw: Any) -> dict[str, Any]:
    """The default action of an unhandled condition: abend with IBM's code for it (ABEND_FOR, SPEC 6.2)."""
    return abend(program, ABEND_FOR[condition], cause="condition", condition=condition, **kw)


# ---- tasks, scenarios, documents (SPEC 4-6) ---------------------------------------------------------------------
def terminal(step: int) -> dict[str, Any]:
    return {"kind": "terminal", "step": step}


def started(task: int, event_index: int) -> dict[str, Any]:
    """A task a START (event `event_index` of task `task`) started."""
    return {"kind": "start", "task": task, "event": event_index}


def run_child(task: int, event_index: int) -> dict[str, Any]:
    return {"kind": "run", "task": task, "event": event_index}


def immediate(task: int, event_index: int) -> dict[str, Any]:
    """#4270 (X27): a task a RETURN IMMEDIATE (event `event_index` of task `task`) attached at once."""
    return {"kind": "immediate", "task": task, "event": event_index}


def task(seq: int, transid: str, program: str, at: str, trigger: dict[str, Any], events: list[dict[str, Any]],
         termid: str | None = None, eibaid: str | None = None, eibcalen: int = 0,
         commarea: dict[str, Any] | None = None, end: str = "normal", note: str | None = None) -> dict[str, Any]:  # fmt: skip
    if not events:
        raise ValueError(f"task {seq}: a task has at least one event")
    if end not in ("normal", "abend"):
        raise ValueError(f"task {seq}: end is normal or abend, not {end!r}")
    out = {"seq": seq, "transid": transid, "program": program, "termid": termid, "at": at, "trigger": trigger,
           "eibaid": eibaid, "eibcalen": eibcalen, "commarea": commarea, "events": list(events), "end": end}  # fmt: skip
    if note is not None:
        out["note"] = note
    return out


def step(at: int, aid: str = "ENTER", text: str | None = None, map_: str | None = None,
         fields: dict[str, str] | None = None, cursor: str | None = None, note: str | None = None) -> dict[str, Any]:  # fmt: skip
    out: dict[str, Any] = {"at": at, "aid": aid}
    given = (("text", text), ("map", map_), ("fields", fields), ("cursor", cursor), ("note", note))
    out.update({k: v for k, v in given if v is not None})
    return out


def scenario(id_: str, path: str, summary: str, steps: list[dict[str, Any]], until: int = 60,
             initial_ts: dict[str, list[str]] | None = None) -> dict[str, Any]:  # fmt: skip
    if path not in ("happy", "trap"):
        raise ValueError(f"scenario {id_}: path is happy or trap, not {path!r}")
    out: dict[str, Any] = {"id": id_, "path": path, "summary": summary}
    if initial_ts is not None:
        out["initial"] = {"ts_queues": initial_ts}
    out.update({"steps": steps, "until": until})
    return out


def expected(case: str, scenario_id: str, tasks: list[dict[str, Any]],
             final_ts: dict[str, list[str]] | None = None) -> dict[str, Any]:  # fmt: skip
    seqs = [t["seq"] for t in tasks]
    if seqs != list(range(1, len(tasks) + 1)):
        raise ValueError(f"{case}/{scenario_id}: task seq must be 1..n in dispatch order, got {seqs}")
    doc: dict[str, Any] = {"format": FORMAT_EXPECTED, "case": case, "scenario": scenario_id, "tasks": tasks}
    if final_ts is not None:
        doc["final"] = {"ts_queues": final_ts}
    return doc


def write_case(case_dir: Path, case_doc: dict[str, Any] | None, logs: dict[str, dict[str, Any]],
               indent: int = 1) -> list[Path]:  # fmt: skip
    """Write case.json (when given; indent 2, as the crucible's cases are) and expected/<scenario>.json."""
    case_dir = Path(case_dir)
    written = []
    if case_doc is not None:
        if case_doc.get("format") != FORMAT_CASE:
            raise ValueError(f"case.json format must be {FORMAT_CASE}")
        ids = [s["id"] for s in case_doc.get("scenarios", [])]
        if sorted(ids) != sorted(logs):
            raise ValueError(f"scenarios {sorted(ids)} and logs {sorted(logs)} differ: one expected log per scenario")
        p = case_dir / "case.json"
        p.write_text(json.dumps(case_doc, indent=2) + "\n", encoding="utf-8")
        written.append(p)
    (case_dir / "expected").mkdir(parents=True, exist_ok=True)
    for sid, doc in logs.items():
        if doc.get("scenario") != sid:
            raise ValueError(f"log for {sid} says scenario {doc.get('scenario')!r}")
        p = case_dir / "expected" / f"{sid}.json"
        p.write_text(json.dumps(doc, indent=indent) + "\n", encoding="utf-8")
        written.append(p)
    return written
