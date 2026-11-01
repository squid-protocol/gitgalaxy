"""#5274: the temporary storage family of the CICS harness's stub translator (equivalence_cics.translate), split out of
equivalence_cics.py: READQ / WRITEQ / DELETEQ TS (#4002, #4415, #5042), the TS queues a task starts with (#4270) and
how a TS event is read back on the COBOL and Java sides (#4607). equivalence_cics's command dispatch calls these; they
reach its shared helpers (the spec, `_call`, `_resp`, the refusals) through the module at call time, so the import works
either way round."""

from __future__ import annotations

import re
from typing import Any

import equivalence_cics as ec


def ts_seed(case: dict[str, Any], sc: dict[str, Any]) -> dict[str, list[str]]:
    """#4270 (GenApp LGICVS01 reads its control queue GENACNTL): the TS queues the region holds when the task starts
    ({"QUEUE": [item text, ...]}), the scenario's "ts", else the case's -- as the cics-crucible runner seeds a
    scenario's initial ts_queues. The stub gets each item's bytes in the data's encoding ($GGCICS_DIR/ts, the layout
    GGCREADQ reads); CicsTask the same text in the region's code page (DetCics.region: a TS item is "the bytes the
    program wrote, in the region's code page", #4528)."""
    seed = sc.get("ts", case.get("ts")) or {}
    for q, items in seed.items():
        if not (0 < len(q) <= 16 and isinstance(items, list) and all(isinstance(i, str) for i in items)):
            raise ec.Unsupported(f'scenario {sc.get("name")}: "ts" maps a queue name (1-16) to a list of item texts')
    return seed


def ts_command(verb: str, opts: dict[str, str | None], labels: list[str] | None = None) -> list[str]:
    """#4002: READQ TS / WRITEQ TS -> GGCREADQ / GGCWRTQ. LENGTH is in-out on READQ (the most INTO
    takes; then the item's length, set on NORMAL and LENGERR only: IBM documents it for neither
    ITEMERR nor QIDERR). ITEM is a value on READQ (NEXT: 0) and on WRITEQ REWRITE, a data area WRITEQ
    sets otherwise; NUMITEMS is set on NORMAL."""
    feature = f"{verb} TS"
    ec._check_spec(feature, opts, (verb,), lambda bad: [f"{feature} {bad[0]}"])
    queue = opts.get("QUEUE") or opts.get("QNAME")
    area = opts.get("INTO") if verb == "READQ" else opts.get("FROM")
    setp = opts.get("SET") if verb == "READQ" else None
    if not queue:
        raise ec.Unsupported(ec._rule(feature, "one_of", "QUEUE"), [feature])
    if setp:  # #5042 (X58): READQ TS SET(pointer) LENGTH(data-area) -> GGCRDQS, the item as a new block
        if area:
            raise ec.Unsupported(ec._rule(feature, "at_most_one", "INTO"), [feature])
        length = opts.get("LENGTH") or opts.get("FLENGTH")
        if not length or re.fullmatch(r"(?is)\d+|LENGTH\s+OF\s+.+", length.strip()):
            raise ec.Unsupported(ec._rule(feature, "requires", "SET"), [feature])
        item, num = opts.get("ITEM"), opts.get("NUMITEMS")
        lines = [f"MOVE {queue} TO GG-QNAME", "MOVE 0 TO GG-LEN",
                 f"MOVE {item} TO GG-ITEM" if item and "NEXT" not in opts else "MOVE 0 TO GG-ITEM"]  # fmt: skip
        lines += ec._call("GGCRDQS", [f"BY REFERENCE {ec._pointer(feature, setp)}"])
        lines += ["IF GG-RESP = 0", f"    MOVE GG-LEN TO {length}", "END-IF"]
        if num:
            lines += ["IF GG-RESP = 0", f"    MOVE GG-NUM TO {num}", "END-IF"]
        return lines + ec._resp(opts, True, labels)
    if not area:
        raise ec.Unsupported(f"{feature} without QUEUE / {'INTO' if verb == 'READQ' else 'FROM'}", [feature])
    length, item, num = opts.get("LENGTH") or opts.get("FLENGTH"), opts.get("ITEM"), opts.get("NUMITEMS")
    lines = [f"MOVE {queue} TO GG-QNAME", f"MOVE {length or f'LENGTH OF {area}'} TO GG-LEN"]
    after = []
    if verb == "READQ":
        lines.append(f"MOVE {item} TO GG-ITEM" if item and "NEXT" not in opts else "MOVE 0 TO GG-ITEM")
        lines += ec._call("GGCREADQ", [f"BY REFERENCE {area}"])
        if length and not ec._literal(length) and not re.fullmatch(r"(?is)LENGTH\s+OF\s+.+", length.strip()):
            # (#4737: a literal / LENGTH OF is the most INTO takes; CICS's length goes to a temporary nobody reads)
            after += ["IF GG-RESP = 0 OR GG-RESP = 22", f"    MOVE GG-LEN TO {length}", "END-IF"]
    else:
        rewrite = "REWRITE" in opts
        if rewrite and not item:
            raise ec.Unsupported(f"{feature} REWRITE without ITEM", [feature])
        lines += [f"MOVE {item if rewrite else 0} TO GG-ITEM",
                  "MOVE 'REWRITE' TO GG-FLAGS" if rewrite else "MOVE SPACES TO GG-FLAGS"]  # fmt: skip
        lines += ec._write_from(length, area, "WRITEQ TS", ec._call("GGCWRTQ", [f"BY REFERENCE {area}"]))
        if item and not rewrite:
            after += ["IF GG-RESP = 0", f"    MOVE GG-ITEM TO {item}", "END-IF"]
    if num:
        after += ["IF GG-RESP = 0", f"    MOVE GG-NUM TO {num}", "END-IF"]
    return lines + after + ec._resp(opts, True, labels)


def delete_queue(opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4415 slice 2 (X29): DELETEQ TS -> GGCDELQ, the whole TS queue."""
    ec._check_spec("DELETEQ TS", opts, ("DELETEQ",), lambda bad: [f"DELETEQ TS {bad[0]}"])
    queue = opts.get("QUEUE") or opts.get("QNAME")
    if not queue:
        raise ec.Unsupported(ec._rule("DELETEQ TS", "one_of", "QUEUE"), ["DELETEQ TS"])
    return [f"MOVE {queue} TO GG-QNAME"] + ec._call("GGCDELQ", []) + ec._resp(opts, True, labels)


def cobol_ts(kv: dict[str, str], data: bytes, enc: str) -> dict[str, Any]:
    """#4607: a WRITEQ TS the stub logged (`queue` the name's bytes in hex, `item` 0 when none was written, `resp` by
    number; the bytes written in the event's blob) as CicsTask records it: {queue, data, resp, item}. The data of a
    write that failed is not compared (the stub logs none for a LENGTH outside 1-32763)."""
    name = bytes.fromhex(kv.get("queue", ""))
    resp = ec.RESP_NAMES.get(int(kv.get("resp", "0")), kv.get("resp", ""))
    text = ec.common._decode_text(data, enc) if resp == "NORMAL" else None
    if resp == "NORMAL" and text is None:
        text = f"<undecodable {data!r} in {enc}>"
    return {"queue": (ec.common._decode_text(name, enc) or name.hex()).rstrip(" \x00"), "data": text, "resp": resp,
            "item": int(kv.get("item", "0")) or None}  # fmt: skip


def java_ts_as_compared(e: dict[str, Any]) -> dict[str, Any]:
    """#4607: CicsTask's WRITEQ-TS event as the comparison reads it: its data (bytes, base64 in the JSON) in the
    region's page -- the det port writes an item there (#4528: DetCics.toRegion; CICS's default CCSID 037, the page
    det/cics.region_page gives an estate that declares no EBCDIC one) -- as text; none for a write that failed. A
    port whose region page is another shows as a difference, never as a pass."""
    import base64

    from gitgalaxy.tools.cobol_to_java.det.cics import REGION_PAGE

    data = e.get("data")
    text = None
    if e.get("resp") == "NORMAL" and isinstance(data, str):
        raw = base64.b64decode(data)
        try:
            text = raw.decode(REGION_PAGE)
        except UnicodeDecodeError:
            text = f"<undecodable {raw!r} in {REGION_PAGE}>"
    return {**e, "data": text, "item": e.get("item") or None}


def command(
    verb: str,
    opts: dict[str, str | None],
    pairs: list[tuple[str, str | None]],
    labels: list[str],
    handle_aid: bool,
) -> list[str] | None:
    """The temporary storage queue commands, or None for a command of another family."""
    if verb == "DELETEQ" and "TD" not in opts:  # #4415 slice 2 (X29): the whole TS queue
        return delete_queue(opts, labels)
    if verb in ("READQ", "WRITEQ") and "TD" not in opts:  # #4002: temporary storage (TS is the default)
        return ts_command(verb, opts, labels)
    return None
