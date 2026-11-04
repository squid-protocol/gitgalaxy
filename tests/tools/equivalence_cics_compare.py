"""#5274: the event comparison of the CICS harness, split out of equivalence_cics.py: the COBOL task's events
(`cobol_events`), the end-state / LINK filters (`linked_result`, `executed_commands`) and the pairing of both sides'
events (`compare_events`, with `_same` / `_same_commarea`). A new event kind's comparison goes in `compare_events`, so a
slice leaves equivalence_cics.py alone. It reaches the shared helpers through the module at call time (a family module
imports its host), and equivalence_cics resolves these names on first use, so `ec.compare_events` still works."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

import equivalence_cics as ec
import equivalence_cics_filecontrol as cics_filecontrol
import equivalence_mq


def cobol_events(res: dict[str, Any]) -> list[dict[str, Any]]:
    """The COBOL task's outputs as the event list CicsTask records."""
    out: list[dict[str, Any]] = []
    screens, texts, records = iter(res["screens"]), iter(res["text"]), iter(res.get("td", []))
    text_options = iter(res.get("text_options", []))
    text_lengths = iter(res.get("text_lengths", []))
    queued = iter(res.get("ts", []))
    operator = iter(res.get("operator", []))
    reads = iter(res.get("reads", []))  # #4270: READQ TS / terminal RECEIVE
    starts = iter(res.get("starts", []))  # #4270: START
    retrieves = iter(res.get("retrieves", []))  # #5089: RETRIEVE
    mq_calls = iter(res.get("mq", []))  # #4892: MQI calls
    webs = iter(res.get("web", []))  # #4767 (X35): WEB CONVERSE
    webopens = iter(res.get("webopen", []))  # #4767 (X35): WEB OPEN
    webcloses = iter(res.get("webclose", []))  # #4767 (X35): WEB CLOSE
    websends = iter(res.get("websend", []))  # #4767 (X37): WEB SEND
    webheaders = iter(res.get("webheader", []))  # #4767 (X38): WEB WRITE HTTPHEADER
    webreceives = iter(res.get("webreceive", []))  # #4767 (X38): WEB RECEIVE
    children = iter(res.get("children", []))  # #4950: RUN TRANSID children
    fileevents = iter(res.get("fileevents", []))  # #7434: READ / REWRITE / UNLOCK
    for line in res["events"]:
        verb, _, args = line.partition(" ")
        if verb == "SEND-MAP":
            s = next(screens)
            out.append({"event": "SEND-MAP", "map": s["map"], **({"mapset": s["mapset"]} if "mapset" in s else {}), "screen": s["fields"], "subfields": s["subfields"],
                        "options": s["options"], "cursor": s["cursor"]})  # fmt: skip
        elif verb == "SEND-TEXT":  # #5401: its options too, as CicsTask.sendText records them
            sent = {"event": "SEND-TEXT", "text": next(texts), "options": next(text_options, [])}
            if (n := next(text_lengths, None)) is not None:  # #5862: its LENGTH too, both ways
                sent["length"] = n
            out.append(sent)
        elif verb == "SEND-CONTROL":  # #4270: CicsTask.sendControl records it -- its options and CURSOR's offset
            cur = int((re.search(r"\bcursor=(-?\d+)", args) or [None, "-1"])[1])
            out.append({"event": "SEND-CONTROL", "options": args.partition("opts=")[2].split(),
                        "cursor": cur if cur >= 0 else None})  # fmt: skip
        elif verb in ("SYNCPOINT", "SYNCPOINT-ROLLBACK"):  # file updates: CicsTask.syncpoint / rollback record them
            out.append({"event": verb})
        elif verb == "WRITEQ-TD":  # CicsTask.writeqTd records the queue and the record's text
            queue = re.search(r"\bqueue=(\S*)", args).group(1)
            resp = re.search(r"\bresp=(\S*)", args).group(1)
            out.append({"event": "WRITEQ-TD", "queue": queue, "text": next(records) if resp == "0" else None})
        # #5859 (X32): as CicsTask.verifyPassword records it -- the USERID and the verdict
        elif verb == "VERIFY-PASSWORD":
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            out.append(
                {
                    "event": "VERIFY-PASSWORD",
                    "userid": kv["userid"],
                    "resp": ec.RESP_NAMES.get(int(kv["resp"]), kv["resp"]),
                }
            )
        elif verb == "WRITE-OPERATOR":  # #4270 zECS (X32): CicsTask.writeOperator records the text
            out.append({"event": "WRITE-OPERATOR", "text": next(operator)})
        elif verb == "WEB-CONVERSE":  # #4767 (X35): CicsTask.webConverse records the request sent
            out.append({"event": "WEB-CONVERSE", **next(webs)})
        elif verb == "WEB-OPEN":  # #4767 (X35): CicsTask.webOpenHost / webOpenUrimap record the connection
            out.append({"event": "WEB-OPEN", **next(webopens)})
        elif verb == "WEB-CLOSE":  # #4767 (X35): CicsTask.webClose records the session closed
            out.append({"event": "WEB-CLOSE", **next(webcloses)})
        elif verb == "WEB-SEND":  # #4767 (X37): CicsTask.webSend records the response sent
            out.append({"event": "WEB-SEND", **next(websends)})
        elif verb == "WEB-HEADER":  # #4767 (X38): CicsTask.webWriteHeader records the header written
            out.append({"event": "WEB-HEADER", **next(webheaders)})
        elif verb == "WEB-RECEIVE":  # #4767 (X38): CicsTask.webReceive records the body read
            out.append({"event": "WEB-RECEIVE", **next(webreceives)})
        elif verb == "WRITEQ-TS":  # #4607: CicsTask.writeqTs records it (queue, data, resp, item)
            out.append({"event": "WRITEQ-TS", **next(queued)})
        elif verb in ("READQ-TS", "READQ-TD", "RECEIVE"):  # #4270: CicsTask records them (queue, item, resp, data)
            out.append(next(reads))
        elif verb == "START":  # #4270 (GenApp LGWEBST5): CicsTask.start records it
            out.append({"event": "START", **next(starts)})
        elif verb == "RETRIEVE":  # #5089: CicsTask.retrieve records it
            out.append({"event": "RETRIEVE", **next(retrieves)})
        elif verb in cics_filecontrol.FILE_EVENT_VERBS:  # #7434
            out.append(next(fileevents))
        elif verb in equivalence_mq.EVENTS:  # #4892
            out.append(next(mq_calls))
        elif verb == "RECEIVE-MAP":  # #4009: CicsTask.receive records it too
            mapset = re.search(r"\bmapset=(\S*)", args)  # #5862: the mapset too, as CicsTask.receive records it
            out.append({"event": "RECEIVE-MAP", "map": re.search(r"\bmap=(\S*)", args).group(1),
                        **({"mapset": mapset.group(1)} if mapset else {})})  # fmt: skip
        elif verb == "RETURN":
            lvl = re.search(r"\blevel=(\d+)", args)
            if "resp=" in args:  # #4270: a RETURN IMMEDIATE that failed (INVREQ / LENGERR): CicsTask.returnImmediate
                kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
                out.append(
                    {
                        "event": "RETURN",
                        "level": int(kv["level"]),
                        "immediate": True,
                        "transid": kv["transid"],
                        "resp": ec.RESP_NAMES.get(int(kv["resp"]), kv["resp"]),
                        "resp2": int(kv["resp2"]),
                    }
                )
            elif lvl and int(lvl.group(1)) > 1:  # a LINKed program's RETURN: back to its caller, no COMMAREA of its own
                out.append({"event": "RETURN", "transid": None, "commarea": None})
            else:
                out.append({"event": "RETURN", "transid": res["return"]["transid"] or None,
                            "commarea": res["return"]["commarea"]})  # fmt: skip
        elif verb == "XCTL":
            out.append({"event": "XCTL", "program": res["xctl"]["program"], "commarea": res["xctl"]["commarea"]})
        elif verb == "LINK":  # a LINK the case runs (its "programs"): compared by its target (what the target did is
            # compared through its own events, the files, tables and the COMMAREA it leaves)
            out.append({"event": "LINK", "program": re.search(r"\btarget=(\S*)", args).group(1)})
        elif verb == "ABEND":
            m = re.search(r"\babcode=(\S*)", args)
            out.append({"event": "ABEND", "abcode": m.group(1) if m else ""})
        elif (
            verb == "ENQ"
        ):  # #5089 (X60): an ENQ the scenario planned busy: CicsTask.enq records it (the others record none)
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            e = {"event": "ENQ", "resource": kv["resource"], "resp": ec.RESP_NAMES.get(int(kv["resp"]), kv["resp"])}
            if "resp2" in kv:  # X60: LENGERR 1 / INVREQ 2 from the operands (a planned ENQBUSY states none)
                e["resp2"] = int(kv["resp2"])
            out.append(e)
        elif verb == "CANCEL":  # #5079 (X63): as CicsTask.cancel records it -- the REQID and the condition
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            out.append({"event": "CANCEL", "reqid": kv.get("reqid", ""),
                        "resp": ec.RESP_NAMES.get(int(kv.get("resp", "0")), kv.get("resp", ""))})  # fmt: skip
        elif verb == "RUN":  # #4270: RUN TRANSID CHILD, as CicsTask.runTransid records it (the child is not run here)
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            resp = ec.RESP_NAMES.get(int(kv.get("resp", "0")), kv.get("resp", ""))
            out.append({"event": "RUN", "transid": kv.get("transid", ""), "resp": resp})
        elif verb == "FETCH":  # #4884, #4950: as CicsTask.fetch records it (on NORMAL: the child and what it left)
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            e = {"event": "FETCH", "resp": ec.RESP_NAMES.get(int(kv["resp"]), kv["resp"]), "resp2": int(kv["resp2"])}
            if "child" in kv:
                e.update({"child": kv["child"], "compstatus": kv["compstatus"],
                          "abcode": None if kv["abcode"] == "-" else kv["abcode"],
                          "channel": None if kv["channel"] == "-" else kv["channel"]})  # fmt: skip
            out.append(e)
        elif verb == "FREE-CHILD":  # #4950: as CicsTask.freeChild records it
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            out.append({"event": "FREE-CHILD", "resp": ec.RESP_NAMES.get(int(kv["resp"]), kv["resp"]),
                        "resp2": int(kv["resp2"])})  # fmt: skip
        elif verb == "CHILD":  # #4950: a RUN TRANSID child the task's wait dispatched, its events as a whole
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            out.append({"event": "CHILD", "child": kv["child"], "transid": kv["transid"],
                        "events": cobol_events(next(children))})  # fmt: skip
    if res.get("containers") is not None:  # #4270 (X24): the containers the task leaves on its current channel
        out.append({"event": "CONTAINERS", **res["containers"]})
    if res.get("mq_queues") is not None:  # #4892: the queues the task leaves (its normal end commits it)
        out.append({"event": "MQ-QUEUES", "queues": res["mq_queues"]})
    if res.get("dli") is not None:  # #5278: the databases the task leaves, each in hierarchic sequence
        out.append({"event": "DLI-DBS", "dbs": {k: v.hex().upper() for k, v in res["dli"].items()}})
    if res.get("linked_commarea") is not None:
        out.append({"event": "COMMAREA", "commarea": res["linked_commarea"]})
    return out


def _link_as_compared(e: dict[str, Any]) -> dict[str, Any]:
    """A LINK event as both sides compare it: its target (the Java side's also carries its COMMAREA and RESP)."""
    if e.get("event") == "LINK":
        return {"event": "LINK", "program": e.get("program") or e.get("target")}
    return e


_STATE_EVENTS = frozenset({"COMMAREA", "CONTAINERS", "DLI-DBS", "MQ-QUEUES"})  # end-state snapshots, not commands


def executed_commands(events: list[dict[str, Any]]) -> list[str]:
    """#5229: the distinct stub verbs the COBOL task executed (the oracle side, before any judging mask), sorted."""
    return sorted({e["event"] for e in events if e.get("event") and e["event"] not in _STATE_EVENTS})


def linked_result(case: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A LINKed program's events (`"linked": true` in the case): its result is the COMMAREA it leaves in its caller's
    storage, compared as a last COMMAREA event -- unless the task abended (no caller sees it then). Any other
    program's final COMMAREA storage is not observable (a terminal task's RETURN COMMAREA is), so it is dropped."""
    abended = any(e.get("event") == "ABEND" for e in events)
    keep = case.get("linked") and not abended
    # #4270 (X24): the containers left on the task's current channel are its result to whoever passed the channel
    # (a LINK CHANNEL caller, a FETCH CHILD parent) -- unless the task abended, as the COMMAREA
    return [_link_as_compared(e) for e in events
            if (e.get("event") != "COMMAREA" or keep) and (e.get("event") != "CONTAINERS" or not abended)]  # fmt: skip


def _same(a: Any, b: Any) -> bool:
    """Equal as the task means it: decimals exactly, text ignoring trailing blanks, absent == empty."""
    if a is None or b is None:
        return str(a or "").rstrip() == str(b or "").rstrip()
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except ArithmeticError:
        return str(a).rstrip(" \x00") == str(b).rstrip(" \x00")


def _same_commarea(a: Any, b: Any) -> bool:
    """#4635: a COMMAREA field as the next program reads it -- like `_same`, except that LOW-VALUES are not blanks:
    only trailing spaces are dropped, so X'00' bytes and spaces differ."""
    if a is None or b is None or isinstance(a, (int, float)) or isinstance(b, (int, float)):
        return _same(a, b)
    if isinstance(a, ec.AlnumText) or isinstance(
        b, ec.AlnumText
    ):  # #7486: PIC X is compared by its bytes, not as a number
        return str(a).rstrip(" ") == str(b).rstrip(" ")
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except ArithmeticError:
        return str(a).rstrip(" ") == str(b).rstrip(" ")


def compare_events(cobol: list[dict[str, Any]], java: list[dict[str, Any]]) -> dict[str, Any]:
    """Events paired in order; per pair, every differing field. {events, equal, diffs}, and #4778 `not_compared`:
    a COMMAREA's FILLER bytes (decode_record `unnamed`) when the Java side gave back a DTO, which has no property for
    them -- listed with that reason, never counted equal."""
    diffs, equal, not_compared = [], 0, {}
    cobol = cics_filecontrol.recorded_file_events(cobol, java)  # #7434: a verb the port never records is not paired
    for n in range(max(len(cobol), len(java))):
        c = cobol[n] if n < len(cobol) else None
        j = java[n] if n < len(java) else None
        if c is None or j is None or c["event"] != j["event"]:
            diffs.append({"event": n + 1, "cobol": c and c["event"], "java": j and j["event"]})
            continue
        bad = []
        for key in ("map", "transid", "program", "text", "abcode", "queue", "data", "resp", "item", "resource"):
            if key in c and not _same(c[key], j.get(key)):
                bad.append({"field": key, "cobol": c[key], "java": j.get(key)})
        if "mapset" in c and c["mapset"] != j.get("mapset"):  # #5862: the MAPSET of a SEND / RECEIVE MAP
            bad.append({"field": "mapset", "cobol": c["mapset"], "java": j.get("mapset")})
        if c["event"] == "START":  # #4270: what CicsTask.start records besides the transid and RESP, both ways
            for key in ("termid", "interval", "time", "reqid", "protect", "resp2", "expires", "from",
                        "rtransid", "rtermid", "queue", "channel"):  # fmt: skip
                if (key in c or key in j) and not _same(c.get(key), j.get(key)):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] in cics_filecontrol.FILE_EVENT_VERBS:  # #7434: file, UPDATE, RESP2, LENGTH, both ways
            browse = c["event"] in cics_filecontrol.BROWSE_EVENT_VERBS  # the key on entry, STARTBR's mode, the SET form
            for key in (*cics_filecontrol.FILE_EVENT_KEYS, *(cics_filecontrol.BROWSE_EVENT_KEYS if browse else ())):
                if (key in c or key in j) and c.get(key) != j.get(key) and not any(b["field"] == key for b in bad):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] == "WEB-CONVERSE":  # #4767 (X35): the request each side sent, both ways
            for key in ("host", "method", "path", "query", "mediatype", "body", "resp2"):  # (exactly: blanks are sent)
                if (key in c or key in j) and c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] == "WEB-OPEN":  # #4767 (X35): the connection each side opened, both ways
            for key in ("host", "scheme", "resp2"):
                if (key in c or key in j) and c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] == "WEB-CLOSE" and c.get("resp2") != j.get("resp2"):  # #4767 (X35): NOTOPEN 27 or normal
            bad.append({"field": "resp2", "cobol": c.get("resp2"), "java": j.get("resp2")})
        if c["event"] == "WEB-HEADER":  # #4767 (X38): the response header each side wrote, both ways
            for key in ("name", "value", "resp2"):
                if (key in c or key in j) and c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] == "WEB-RECEIVE":  # #4767 (X38): the body each side read and its media type, both ways
            for key in ("mediatype", "body", "resp", "resp2"):
                if (key in c or key in j) and c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] == "WEB-SEND":  # #4767 (X37): the response each side sent, both ways
            for key in ("status", "statustext", "mediatype", "body", "action", "resp2"):  # (exactly: blanks are sent)
                if (key in c or key in j) and c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] in (*equivalence_mq.EVENTS, "MQ-QUEUES"):  # #4892: the MQI call's outcome, the queues left
            bad += equivalence_mq.compare(c, j)
        if c["event"] == "CONTAINERS":  # #4270 (X24): the channel's name and every container's bytes, both ways
            if c.get("channel") != j.get("channel"):
                bad.append({"field": "channel", "cobol": c.get("channel"), "java": j.get("channel")})
            cc, jc = c.get("containers") or {}, j.get("containers") or {}
            for name in sorted(set(cc) | set(jc)):
                if cc.get(name) != jc.get(name):
                    bad.append({"field": f"containers.{name}", "cobol": cc.get(name), "java": jc.get(name)})
        for part in ("screen", "commarea"):
            cv, jv = c.get(part) or {}, j.get(part) or {}
            same = _same_commarea if part == "commarea" else _same
            for name in cv:
                if part == "commarea" and name.startswith("FILLER@") and j.get("commarea_dto"):
                    not_compared[f"commarea.{name}"] = UNNAMED_IN_A_DTO
                    continue
                if not same(cv[name], jv.get(name)):
                    bad.append({"field": f"{part}.{name}", "cobol": cv[name], "java": jv.get(name)})
        for name, value in (j.get("dto") or {}).items():  # #5863: a LINKed port's DTO too, beside the bytes it left
            if name in (c.get("commarea") or {}) and not _same_commarea(c["commarea"][name], value):
                bad.append({"field": f"commarea.dto.{name}", "cobol": c["commarea"][name], "java": value})
        if c["event"] == "SEND-TEXT" and "options" in c:  # #5401: the options the translation forwards, both ways
            java_options = sorted(o for o in j.get("options") or [] if o in ec.TEXT_OPTIONS_FORWARDED)
            if c["options"] != java_options:
                bad.append({"field": "options", "cobol": c["options"], "java": java_options})
        if c["event"] == "SEND-TEXT" and "length" in c and c["length"] != j.get("length"):  # #5862
            bad.append({"field": "length", "cobol": c["length"], "java": j.get("length")})
        if c["event"] == "SEND-CONTROL":  # #4270: ERASE / FREEKB / ALARM ... and the cursor, as the crucible compares
            if sorted(c.get("options") or []) != sorted(j.get("options") or []):
                bad.append({"field": "options", "cobol": c.get("options"), "java": j.get("options")})
            if c.get("cursor") != j.get("cursor"):
                bad.append({"field": "cursor", "cobol": c.get("cursor"), "java": j.get("cursor")})
        if c["event"] == "SEND-MAP" and "subfields" in c:  # #4053: attributes, colour, highlight, cursor, options
            cs, js = c["subfields"], ec.java_subfields(j.get("subfields"))
            for name in sorted(set(cs) | set(js)):
                if cs.get(name, {}) != js.get(name, {}):
                    bad.append({"field": f"subfields.{name}", "cobol": cs.get(name, {}), "java": js.get(name, {})})
            if sorted(c.get("options") or []) != sorted(j.get("options") or []):
                bad.append({"field": "options", "cobol": c.get("options"), "java": j.get("options")})
            if c.get("cursor") != j.get("cursor"):
                bad.append({"field": "cursor", "cobol": c.get("cursor"), "java": j.get("cursor")})
        if c["event"] in ("FETCH", "FREE-CHILD"):  # #4950: the child fetched and what it left, both ways
            for key in ("resp2", "child", "compstatus", "abcode", "channel"):
                if (key in c or key in j) and c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] == "CHILD":  # #4950: a RUN TRANSID child's own events, compared as a task's
            for key in ("child", "transid"):
                if c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
            sub = compare_events(c.get("events") or [], [_link_as_compared(x) for x in j.get("events") or []])  # #6967
            if sub["diffs"]:
                bad.append({"field": "events", "cobol": sub["diffs"], "java": None})
        if bad:
            diffs.append({"event": n + 1, "kind": c["event"], "fields": bad})
        else:
            equal += 1
    out = {"events": max(len(cobol), len(java)), "equal": equal, "diffs": diffs}
    if not_compared:
        out["not_compared"] = not_compared
    return out


UNNAMED_IN_A_DTO = ("a FILLER: the Java side gave back the COMMAREA as a DTO, which has no property for it (a port "
                    "that gives back the bytes -- a det port LINKed with them, or a COMMAREA past its DTO -- has it "
                    "compared)")  # fmt: skip
