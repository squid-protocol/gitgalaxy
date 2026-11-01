"""#4892: the IBM MQ side of a CICS equivalence case -- the queue manager a task's MQI calls reach, stated by the case,
given alike to the oracle's model (tests/equivalence/mq/ggmq.c, as $GGCICS_DIR/mq.cfg) and the port's
(det/cobolrt/mq/QueueManager.java, the same file); the start data a triggered task RETRIEVEs (an MQTM); and what each
side's MQI calls and left queues look like when compared. The register's W family says what is stated and assumed.

A case's (or a scenario's own) "mq":
    {"qmgr": "CSQ1", "ccsid": 37,
     "queues": {"NAME": {"priority": 0, "persistence": 0, "messages": [MESSAGE, ...]}, ...}}
a scenario's "mq_messages": {"NAME": [MESSAGE, ...]} replaces those queues' messages only. A MESSAGE:
    {"data": "text" | "hex": "C1C2", "format": "MQSTR", "msgid": "...", "correlid": "...", "replytoq": "...",
     "replytoqmgr": "...", "msgtype": 8, "priority": n, "persistence": n, "ccsid": n, "encoding": 785}
Every MQMD field not stated is IBM's initial value (det/copy/CMQMDV.cpy), with the queue's defaults and the queue
manager's CCSID resolved as a put resolves them; a MsgId not stated is GGMQSTATED and the message's number (W4).

A scenario's (or the case's) "start_data": [RECORD, ...] -- the START data the task was started with, in RETRIEVE
order: {"text": ...}, {"hex": ...}, or {"mqtm": {"qname": ..., "processname": ..., "triggerdata": ..., "appltype": 1,
"applid": ..., "envdata": ..., "userdata": ...}} (a trigger message, MQTM_LENGTH_1: the CKTI trigger monitor's START).

A scenario's "mq_faults": [{"call": "MQCLOSE", "nth": 1, "reason": 2009}, ...] plans MQI calls to fail: the nth call
of that verb (every call of it counts) is not performed and answers the IBM reason (FAULT_REASONS), CompCode MQCC_FAILED,
the stated queues untouched. Both models read it as `FAULT VERB NTH REASON` lines of mq.cfg; the failed call's event
carries the reason, so the proof compares it on both sides.
"""

from __future__ import annotations

import copy
import re
import struct
from pathlib import Path
from typing import Any

from gitgalaxy.standards.mq import STAND_INS  # noqa: F401 -- the harness stages these (equivalence_cics)

MDLEN = 324
MODEL = Path(__file__).resolve().parents[1] / "equivalence" / "mq" / "ggmq.c"
MQ_CALL = re.compile(r"(?i)\bCALL\s+['\"]MQ")
EVENTS = ("MQOPEN", "MQCLOSE", "MQGET", "MQPUT", "MQPUT1")
# IBM MQ reason codes a call may fail with whatever the queues hold (a planned fault's reasons), and the verbs each fits
FAULT_REASONS = {
    2009: ("MQRC_CONNECTION_BROKEN", EVENTS),
    2035: ("MQRC_NOT_AUTHORIZED", ("MQOPEN", "MQPUT1")),
    2016: ("MQRC_GET_INHIBITED", ("MQGET",)),
    2051: ("MQRC_PUT_INHIBITED", ("MQPUT", "MQPUT1")),
    2161: ("MQRC_Q_MGR_QUIESCING", EVENTS),
    2162: ("MQRC_Q_MGR_STOPPING", EVENTS),
}
COMPARED = ("cc", "rc", "len", "options", "hobj", "msgid")


def _l(v: int) -> bytes:
    return struct.pack(">i", v)


def _c(text: str | None, n: int, enc: str, fill: bytes = b" ") -> bytes:
    raw = (text or "").encode(enc)
    if len(raw) > n:
        raise ValueError(f"{text!r}: longer than {n} bytes")
    return raw + fill * (n - len(raw))


def state(case: dict[str, Any], sc: dict[str, Any]) -> dict[str, Any] | None:
    """The queue manager the scenario's task runs with, or None: the case states none."""
    st = copy.deepcopy(sc["mq"] if "mq" in sc else case.get("mq"))
    if st is None:
        if sc.get("mq_faults"):
            raise ValueError(f'scenario {sc.get("name")}: "mq_faults" in a case with no "mq" section')
        return None
    if sc.get("mq_faults"):
        st["faults"] = fault_plan(sc["mq_faults"], sc.get("name"))
    for q, msgs in (sc.get("mq_messages") or {}).items():
        if q not in st["queues"]:
            raise ValueError(f'scenario {sc.get("name")}: "mq_messages" names {q}, a queue the "mq" section has not')
        st["queues"][q]["messages"] = msgs
    return st


def fault_plan(plan: list[dict[str, Any]], name: str | None) -> list[dict[str, Any]]:
    """A scenario's `mq_faults`, checked: a modelled verb, a positive nth, a reason IBM gives that verb."""
    out = []
    for f in plan:
        verb, nth, reason = f.get("call"), f.get("nth", 1), f.get("reason")
        if verb not in EVENTS:
            raise ValueError(f"scenario {name}: mq_faults call {verb!r} is not one of {EVENTS}")
        if not isinstance(nth, int) or nth < 1:
            raise ValueError(f"scenario {name}: mq_faults nth {nth!r} is not a call number from 1")
        if reason not in FAULT_REASONS or verb not in FAULT_REASONS[reason][1]:
            raise ValueError(f"scenario {name}: mq_faults reason {reason!r} is not one IBM gives {verb} "
                             f"({sorted(r for r, v in FAULT_REASONS.items() if verb in v[1])})")  # fmt: skip
        out.append({"call": verb, "nth": nth, "reason": reason})
    return out


def md_image(msg: dict[str, Any], queue: dict[str, Any], st: dict[str, Any], n: int, enc: str) -> bytes:
    """A stated message's MQMD (version 1): IBM's initial values, the stated fields, the queue's defaults."""
    replytoq = msg.get("replytoq", "")
    image = b"".join([
        _c("MD", 4, enc), _l(1), _l(0), _l(msg.get("msgtype", 8)), _l(-1), _l(0), _l(msg.get("encoding", 785)),
        _l(msg.get("ccsid", st.get("ccsid", 37))), _c(msg.get("format", ""), 8, enc),
        _l(msg.get("priority", queue.get("priority", 0))), _l(msg.get("persistence", queue.get("persistence", 0))),
        _c(msg.get("msgid", f"GGMQSTATED{n:014d}"), 24, enc, b"\0"), _c(msg.get("correlid"), 24, enc, b"\0"), _l(0),
        _c(replytoq, 48, enc), _c(msg.get("replytoqmgr", st["qmgr"] if replytoq else ""), 48, enc),
        _c("", 12, enc), b"\0" * 32, _c("", 32, enc), _l(0), _c("", 28, enc), _c("", 8, enc), _c("", 8, enc),
        _c("", 4, enc),
    ])  # fmt: skip
    assert len(image) == MDLEN
    return image


def _data(msg: dict[str, Any], enc: str) -> bytes:
    return bytes.fromhex(msg["hex"]) if "hex" in msg else str(msg.get("data", "")).encode(enc)


def cfg(st: dict[str, Any], enc: str) -> str:
    """mq.cfg, as both models read it."""
    lines = [f"QMGR {st['qmgr']} {st.get('ccsid', 37)}"]
    n = 0
    for name, q in st["queues"].items():
        if not re.fullmatch(r"[A-Za-z0-9._/%]{1,48}", name):
            raise ValueError(f"{name!r}: not a queue name (IBM: 1-48 of A-Z a-z 0-9 . / _ %)")
        lines.append(f"Q {name} {q.get('priority', 0)} {q.get('persistence', 0)}")
    lines += [f"FAULT {f['call']} {f['nth']} {f['reason']}" for f in st.get("faults", [])]
    for name, q in st["queues"].items():
        for msg in q.get("messages", []):
            n += 1
            data = _data(msg, enc)
            lines.append(f"M {name} {md_image(msg, q, st, n, enc).hex().upper()} {data.hex().upper() or '-'}")
    return "\n".join(lines) + "\n"


def mqtm(spec: dict[str, Any], enc: str) -> bytes:
    """A trigger message (MQTM, version 1, 684 bytes: det/copy/CMQTML.cpy), its fields stated or blank."""
    rec = b"".join([
        _c("TM", 4, enc), _l(1), _c(spec.get("qname"), 48, enc), _c(spec.get("processname"), 48, enc),
        _c(spec.get("triggerdata"), 64, enc), _l(spec.get("appltype", 1)), _c(spec.get("applid"), 256, enc),
        _c(spec.get("envdata"), 128, enc), _c(spec.get("userdata"), 128, enc),
    ])  # fmt: skip
    assert len(rec) == 684
    return rec


START_OPTION_WIDTHS = {"rtransid": 4, "rtermid": 4, "queue": 8}  # the stub's opt_value widths (ggcics_taskcontrol.c)


def start_records(case: dict[str, Any], sc: dict[str, Any], enc: str) -> list[dict[str, Any]]:
    """#7475: the START data records the task was started with, in RETRIEVE order: {"data": bytes | None (no FROM),
    "rtransid" / "rtermid" / "queue": str, each only when the START gave it}. A record may state the options beside
    its text / hex / mqtm, or only the options (a START with no FROM). A record with neither stores nothing in CICS
    (RETRIEVE gets ENDDATA), so it is refused."""
    out = []
    for r in sc.get("start_data", case.get("start_data", [])):
        rec: dict[str, Any] = {"data": None}
        if "mqtm" in r:
            rec["data"] = mqtm(r["mqtm"], enc)
        elif "hex" in r:
            rec["data"] = bytes.fromhex(r["hex"])
        elif "text" in r:
            rec["data"] = str(r["text"]).encode(enc)
        for k, width in START_OPTION_WIDTHS.items():
            if r.get(k) is not None:
                if len(str(r[k])) > width:
                    raise ValueError(f"start_data {k} {r[k]!r} is longer than {width} bytes")
                rec[k] = str(r[k])
        if rec["data"] is None and len(rec) == 1:
            raise ValueError(f"start_data record {r!r} gives no FROM data and no RTRANSID / RTERMID / QUEUE")
        out.append(rec)
    return out


def start_data(case: dict[str, Any], sc: dict[str, Any], enc: str) -> list[bytes]:
    """The START data records the task was started with (RETRIEVE's), in the data's page (FROM's bytes only)."""
    return [rec["data"] for rec in start_records(case, sc, enc) if rec["data"] is not None]


def start_opt_text(rec: dict[str, Any]) -> str | None:
    """#7475: the stub's retrieve_NNN.opt line for a record (`from=0|1 rtransid=<hex> ...`), None when the record is
    FROM data alone (only retrieve_NNN.bin then). The very format tests/tools/cics_crucible.py writes."""
    named = {k: rec[k] for k in START_OPTION_WIDTHS if rec.get(k) is not None}
    if not named and rec.get("data") is not None:
        return None
    return (
        f"from={int(rec.get('data') is not None)}"
        + "".join(f" {k}={v.encode('latin-1').hex()}" for k, v in named.items())
        + "\n"
    )


def cobol_event(verb: str, kv: dict[str, str], data: bytes) -> dict[str, Any]:
    """An MQI call ggmq.c logged, as QueueManager records it."""
    e: dict[str, Any] = {"event": verb, "queue": kv.get("queue", ""), "cc": int(kv["cc"]), "rc": int(kv["rc"])}
    for key in ("len", "options", "hobj"):
        if key in kv:
            e[key] = int(kv[key])
    if "msgid" in kv:
        e["msgid"] = kv["msgid"]
    if verb in ("MQGET", "MQPUT", "MQPUT1"):
        e["data"] = data.hex().upper()
    return e


def queues_left(path: Path) -> dict[str, list[str]] | None:
    """The queues a task left (ggmq.c's mq.out): {queue: ["MQMD-hex data-hex", ...]}, None when it had none."""
    if not path.is_file():
        return None
    out: dict[str, list[str]] = {}
    current = None
    for line in path.read_text(encoding="ascii").splitlines():
        if line.startswith("Q "):
            current = out.setdefault(line[2:], [])
        elif line.startswith("M ") and current is not None:
            current.append(line[2:])
    return out


def compare(c: dict[str, Any], j: dict[str, Any]) -> list[dict[str, Any]]:
    """An MQI event's (or the MQ-QUEUES event's) fields beyond the queue and data, both ways."""
    keys = ("queues",) if c["event"] == "MQ-QUEUES" else COMPARED
    return [{"field": k, "cobol": c.get(k), "java": j.get(k)} for k in keys
            if (k in c or k in j) and c.get(k) != j.get(k)]  # fmt: skip
