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
        return None
    for q, msgs in (sc.get("mq_messages") or {}).items():
        if q not in st["queues"]:
            raise ValueError(f'scenario {sc.get("name")}: "mq_messages" names {q}, a queue the "mq" section has not')
        st["queues"][q]["messages"] = msgs
    return st


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


def start_data(case: dict[str, Any], sc: dict[str, Any], enc: str) -> list[bytes]:
    """The START data records the task was started with (RETRIEVE's), in the data's page."""
    out = []
    for r in sc.get("start_data", case.get("start_data", [])):
        if "mqtm" in r:
            out.append(mqtm(r["mqtm"], enc))
        elif "hex" in r:
            out.append(bytes.fromhex(r["hex"]))
        else:
            out.append(str(r["text"]).encode(enc))
    return out


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
