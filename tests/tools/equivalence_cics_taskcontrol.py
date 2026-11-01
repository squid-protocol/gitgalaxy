"""#5274: the task / interval control family of the CICS harness's stub translator (equivalence_cics.translate), split out
of equivalence_cics.py: START / RETRIEVE / CANCEL (#4006, #4270, #5042), RUN TRANSID, FETCH, FREE CHILD (#4950), DELAY,
POST, WAIT EVENT and CONVERSE (#5079), and how a START or RETRIEVE event is read back on the COBOL and Java sides (#4270,
#5089). equivalence_cics's command dispatch calls these; they reach its shared helpers (the spec, `_call`, `_resp`, the
refusals) through the module at call time, so the import works either way round."""

from __future__ import annotations

import re
from typing import Any

import equivalence_common as common
import equivalence_cics as ec


def _fetch_child(key: str, opts: dict[str, str | None], labels: list[str]) -> list[str]:
    """#4884, #4950: FETCH ANY / FETCH CHILD(token) -> GGCFETCH: GG-FLAGS names CHILD (the token in GG-QNAME), NOSUSPEND,
    TIMEOUT (GG-NUM) and CHANNEL; on NORMAL the stub's answers go to the program's areas -- the token (ANY), the reply
    channel's name (CHANNEL), the abend code (ABCODE, only for a child that abended) and COMPSTATUS's CVDA."""
    form = key.split()[1]
    ec._check_spec(key, opts, ("FETCH",))
    if not opts.get(form):
        raise ec.Unsupported(ec._rule(key, "required", form), [key])
    if "NOSUSPEND" in opts and "TIMEOUT" in opts:
        raise ec.Unsupported(ec._rule(key, "at_most_one", "NOSUSPEND", "NOSUSPEND", "TIMEOUT"), [key])
    if any(o in opts and not opts[o] for o in ("TIMEOUT", "CHANNEL", "ABCODE", "COMPSTATUS")):
        raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
    flags = " ".join(
        o for o in ("CHILD", "NOSUSPEND", "TIMEOUT", "CHANNEL") if o in opts or (o == "CHILD" and form == "CHILD")
    )
    lines = [f"MOVE {opts['CHILD']} TO GG-QNAME" if form == "CHILD" else "MOVE SPACES TO GG-QNAME",
             f"MOVE '{flags}' TO GG-FLAGS" if flags else "MOVE SPACES TO GG-FLAGS",
             f"MOVE {opts['TIMEOUT']} TO GG-NUM" if "TIMEOUT" in opts else "MOVE 0 TO GG-NUM"]  # fmt: skip
    after = [f"    MOVE GG-QNAME TO {opts['ANY']}"] if form == "ANY" else []
    if "CHANNEL" in opts:
        after.append(f"    MOVE GG-CHAN TO {opts['CHANNEL']}")
    if "ABCODE" in opts:
        after += ["    IF GG-ITEM = 1", f"        MOVE GG-NAME1(1:4) TO {opts['ABCODE']}", "    END-IF"]
    if "COMPSTATUS" in opts:
        after.append(f"    MOVE GG-NUM TO {opts['COMPSTATUS']}")
    after = ["IF GG-RESP = 0", *after, "END-IF"] if after else []
    return lines + ec._call("GGCFETCH", []) + after + ec._resp(opts, True, labels)


def _free_child(opts: dict[str, str | None], labels: list[str]) -> list[str]:
    """#4950: FREE CHILD(token) -> GGCFREE (the token in GG-QNAME)."""
    ec._check_spec("FREE CHILD", opts, ("FREE", "CHILD"))
    if not opts.get("CHILD"):
        raise ec.Unsupported(ec._rule("FREE CHILD", "required", "CHILD"), ["FREE CHILD"])
    return [f"MOVE {opts['CHILD']} TO GG-QNAME"] + ec._call("GGCFREE", []) + ec._resp(opts, True, labels)


def _delay(opts: dict[str, str | None], labels: list[str]) -> list[str]:
    """#4950: DELAY -> GGCDLAY: GG-FLAGS INTERVAL (GG-NUM), TIME, or FOR (HOURS / MINUTES / SECONDS / MILLISECS in GG-HOURS
    / GG-MINS / GG-SECS / GG-LEN, -999999999 when not given); none: INTERVAL(0). The stub dispatches the RUN children
    at it (a task takes no time, X4: NORMAL at once)."""
    ec._check_spec("DELAY", opts, ("DELAY",), lambda bad: [f"DELAY {bad[0]}"])
    given = [o for o in ("INTERVAL", "TIME", "HOURS", "MINUTES", "SECONDS", "MILLISECS") if o in opts]
    if any(not opts[o] for o in given):
        raise ec.Unsupported(ec.NEEDS_ARGUMENT, ["DELAY"])
    if "TIME" in opts:
        lines = ["MOVE 'TIME' TO GG-FLAGS"]
    elif "INTERVAL" in opts:
        lines = ["MOVE 'INTERVAL' TO GG-FLAGS", f"MOVE {opts['INTERVAL']} TO GG-NUM"]
    elif given:
        lines = ["MOVE 'FOR' TO GG-FLAGS"] + [f"MOVE {opts.get(o) or -999999999} TO {f}" for o, f in (
            ("HOURS", "GG-HOURS"), ("MINUTES", "GG-MINS"), ("SECONDS", "GG-SECS"), ("MILLISECS", "GG-LEN"))]  # fmt: skip
    else:
        lines = ["MOVE SPACES TO GG-FLAGS"]
    return lines + ec._call("GGCDLAY", []) + ec._resp(opts, True, labels)


def _post(opts: dict[str, str | None], labels: list[str]) -> list[str]:
    """#5079 (register X63): POST INTERVAL / TIME (GG-NUM) | AFTER / AT HOURS MINUTES SECONDS (GG-HOURS / GG-MINS / GG-SECS,
    -999999999 when not given; GG-FLAGS says which) [REQID (GG-QNAME)] [SET(ptr)] -> GGCPOST, which sets the pointer to the
    timer-event control area (no SET: GG-PTR takes it), and returns the REQID it ran under in GG-NAME1: EIBREQID when the
    program gave none (IBM: CICS "generates one", ASSUMED POSTnnnn). The option rules as the det translator's."""
    key = "POST"
    ec._check_spec(key, opts, ("POST",), lambda bad: [f"{key} {o}" for o in bad])
    whens = [w for w in ("INTERVAL", "TIME", "AFTER", "AT") if w in opts]
    if len(whens) > 1:
        raise ec.Unsupported(ec._rule(key, "at_most_one", "INTERVAL", " and ".join(whens)), ["POST " + " ".join(whens)])
    when = whens[0] if whens else "INTERVAL"
    hms = [o for o in ("HOURS", "MINUTES", "SECONDS") if o in opts]
    if (when in ("AFTER", "AT")) != bool(hms):
        raise ec.Unsupported(ec._rule(key, "requires", "HOURS", when, " ".join(hms)), [f"POST {when}"])
    if any(not opts.get(o) for o in [*hms, *(o for o in ("INTERVAL", "TIME", "SET", "REQID") if o in opts)]):
        raise ec.Unsupported(ec.NEEDS_ARGUMENT, [f"POST {when}"])
    lines = [f"MOVE '{when}' TO GG-FLAGS",
             f"MOVE {opts['REQID']} TO GG-QNAME" if opts.get("REQID") else "MOVE SPACES TO GG-QNAME",
             f"MOVE {opts.get(when) or 0} TO GG-NUM" if when in ("INTERVAL", "TIME") else "MOVE 0 TO GG-NUM"]  # fmt: skip
    lines += [f"MOVE {opts.get(o) or -999999999} TO {f}"
              for o, f in (("HOURS", "GG-HOURS"), ("MINUTES", "GG-MINS"), ("SECONDS", "GG-SECS")) if hms]  # fmt: skip
    ptr = ec._pointer(key, opts["SET"]) if opts.get("SET") else "GG-PTR"
    lines += ec._call("GGCPOST", [f"BY REFERENCE {ptr}"])
    if not opts.get("REQID"):
        lines += ["IF GG-RESP = 0", "    MOVE GG-NAME1 TO EIBREQID", "END-IF"]
    return lines + ec._resp(opts, True, labels)


def _wait_event(opts: dict[str, str | None], labels: list[str]) -> list[str]:
    """#5079 (register X63): WAIT EVENT ECADDR(ptr) [NAME] -> GGCWEVT (the area a POST made is posted at its expiry; INVREQ
    RESP2 2 for a null pointer; an address that is no POST's area is refused by the stub). The option rules as the translator's."""
    key = "WAIT EVENT"
    ec._check_spec(
        key, {o: v for o, v in opts.items() if o != "EVENT"}, ("WAIT",), lambda bad: [f"{key} {o}" for o in bad]
    )
    if not opts.get("ECADDR"):
        raise ec.Unsupported(ec._rule(key, "required", "ECADDR"), [key])
    return ec._call("GGCWEVT", [f"BY REFERENCE {ec._pointer(key, opts['ECADDR'])}"]) + ec._resp(opts, True, labels)


def _converse(opts: dict[str, str | None], labels: list[str]) -> list[str]:
    """#5079 (register X63): CONVERSE FROM [FROMLENGTH] INTO [TOLENGTH] [MAXLENGTH] [NOTRUNCATE] -> GGCCONV: the FROM data
    written to the terminal (a plain SEND's event), then the terminal RECEIVE of the reply (GG-LEN the most taken, GG-FLAGS
    NOTRUNCATE; on return the reply's length, -1 for a negative FROMLENGTH: LENGERR, nothing sent). TOLENGTH is set on NORMAL
    / LENGERR. The option rules as the det translator's (the conversation options refused by name); SET(pointer) -> GGCCONS."""
    key = "CONVERSE"
    ec._check_spec(key, opts, (key,), lambda bad: [f"{key} {o}" for o in bad])
    if not opts.get("FROM"):
        raise ec.Unsupported(ec._rule(key, "required", "FROM"), [key])
    if bool(opts.get("INTO")) == bool(opts.get("SET")):
        raise ec.Unsupported(ec._rule(key, "one_of", "INTO"), [key])
    sent = ec._one_of(key, opts, "FROMLENGTH", "FROMFLENGTH")
    length = ec._one_of(key, opts, "TOLENGTH", "TOFLENGTH")
    most = ec._one_of(key, opts, "MAXLENGTH", "MAXFLENGTH")
    src, into = opts["FROM"], opts.get("INTO")
    settable = bool(length) and re.fullmatch(r"(?is)[+-]?\d+|LENGTH\s+OF\s+.+", length.strip()) is None
    if opts.get(
        "SET"
    ):  # X58: SET(pointer) -> GGCCONS, the reply in a new block; TOLENGTH is output-only, as the det port requires
        if not settable:
            raise ec.Unsupported("CONVERSE SET without TOLENGTH(data-area)", [key])
        lines = ["MOVE 'NOTRUNCATE' TO GG-FLAGS" if "NOTRUNCATE" in opts else "MOVE SPACES TO GG-FLAGS",
                 f"MOVE {most or '32768'} TO GG-LEN"]  # fmt: skip
        lines += ec._call("GGCCONS", [f"BY REFERENCE {src}", f"BY VALUE {sent or f'LENGTH OF {src}'}",
                                      f"BY REFERENCE {ec._pointer(key, opts['SET'])}"])  # fmt: skip
        lines += ["IF GG-LEN >= 0 AND (GG-RESP = 0 OR GG-RESP = 22)", f"    MOVE GG-LEN TO {length}", "END-IF"]
        return lines + ec._resp(opts, True, labels)
    lines = ["MOVE 'NOTRUNCATE' TO GG-FLAGS" if "NOTRUNCATE" in opts else "MOVE SPACES TO GG-FLAGS",
             f"MOVE {most or length or f'LENGTH OF {into}'} TO GG-LEN"]  # fmt: skip
    lines += ec._call(
        "GGCCONV", [f"BY REFERENCE {src}", f"BY VALUE {sent or f'LENGTH OF {src}'}", f"BY REFERENCE {into}"]
    )
    if settable:
        lines += ["IF GG-LEN >= 0 AND (GG-RESP = 0 OR GG-RESP = 22)", f"    MOVE GG-LEN TO {length}", "END-IF"]
    return lines + ec._resp(opts, True, labels)


def _run_transid(opts: dict[str, str | None], labels: list[str]) -> list[str]:
    """#4270 slice 2: RUN TRANSID(x) CHILD(area) -> GGCRUNT (the child is an event; the runner's scheduler runs it
    once this task has ended). CHANNEL (#4884): the child's copy of a channel, in GG-CHAN. Any option IBM's RUN TRANSID
    lists beyond TRANSID / CHILD / CHANNEL is refused."""
    ec._check_spec("RUN", opts, ("RUN",))
    if not opts.get("TRANSID") or not opts.get("CHILD"):
        raise ec.Unsupported(ec._rule("RUN", "required", "TRANSID"), ["RUN"])
    if "CHANNEL" in opts and not opts["CHANNEL"]:
        raise ec.Unsupported(ec.NEEDS_ARGUMENT, ["RUN CHANNEL"])
    channel = ["MOVE 'CHANNEL' TO GG-FLAGS", f"MOVE {opts['CHANNEL']} TO GG-CHAN"] if opts.get("CHANNEL") else [
        "MOVE SPACES TO GG-FLAGS"]  # fmt: skip
    return (
        [f"MOVE {opts['TRANSID']} TO GG-NAME1", *channel]
        + ec._call("GGCRUNT", [f"BY REFERENCE {opts['CHILD']}"])
        + ec._resp(opts, True, labels)
    )


def _interval_command(verb: str, opts: dict[str, str | None], labels: list[str]) -> list[str]:
    """#4006: START -> GGCSTRT (the request is an event; the runner's scheduler dispatches it), RETRIEVE
    -> GGCRTRV (LENGTH in-out, set back on NORMAL / LENGERR), CANCEL REQID -> GGCCNCL. #4270: AFTER / AT HOURS /
    MINUTES / SECONDS (GG-HOURS / GG-MINS / GG-SECS, -999999999 when not given) and the data options RTRANSID /
    RTERMID / QUEUE (GG-RTRAN / GG-RTERM / GG-RQUEUE, named in GG-FLAGS) on both."""
    ec._check_spec(verb, opts, (verb,))  # (a deny-list until spec PR 3: an unknown option was ignored)
    named = [o for o in ("RTRANSID", "RTERMID", "QUEUE") if o in opts]
    if any(not opts.get(o) for o in named):
        raise ec.Unsupported(ec.NEEDS_ARGUMENT, [f"{verb} {o}" for o in named])
    data_in = {"RTRANSID": "GG-RTRAN", "RTERMID": "GG-RTERM", "QUEUE": "GG-RQUEUE"}
    if verb == "START":
        if not opts.get("TRANSID"):
            raise ec.Unsupported(ec._rule("START", "required", "TRANSID"), ["START"])
        whens = [w for w in ("INTERVAL", "TIME", "AFTER", "AT") if w in opts]
        if len(whens) > 1:
            raise ec.Unsupported(ec._rule("START", "at_most_one", "INTERVAL", " and ".join(whens)),
                              ["START " + " ".join(whens)])  # fmt: skip
        when = whens[0] if whens else "INTERVAL"
        hms = [o for o in ("HOURS", "MINUTES", "SECONDS") if o in opts]
        if (when in ("AFTER", "AT")) != bool(hms):
            raise ec.Unsupported(ec._rule("START", "requires", "HOURS", when, " ".join(hms)), [f"START {when}"])
        if any(not opts.get(o) for o in hms):
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, [f"START {when}"])
        area = opts.get("FROM")
        given_length = ec._one_of("START", opts, "LENGTH", "FLENGTH")
        if given_length is not None and not area:  # (a deny-list until spec PR 3: the length was moved, no area)
            raise ec.Unsupported(ec._rule("START", "requires", "LENGTH"), ["START"])
        if "CHANNEL" in opts:  # #4950: START CHANNEL's form -- no expiry, no data options, no REQID
            if not opts["CHANNEL"]:
                raise ec.Unsupported(ec.NEEDS_ARGUMENT, ["START CHANNEL"])
            for g in ec.SPEC["START"].groups:
                if g.kind == "at_most_one" and g.options[0] == "CHANNEL" and all(o in opts for o in g.options):
                    raise ec.Unsupported(g.msg.format(g.options[1]), ["START CHANNEL"])
        flags = " ".join(
            [when] + (["PROTECT"] if "PROTECT" in opts else []) + named + (["CHANNEL"] if "CHANNEL" in opts else [])
        )
        length = given_length or (f"LENGTH OF {area}" if area else "0")
        lines = [f"MOVE {opts['TRANSID']} TO GG-NAME1",
                 f"MOVE {opts['TERMID']} TO GG-NAME2" if opts.get("TERMID") else "MOVE SPACES TO GG-NAME2",
                 f"MOVE {opts['REQID']} TO GG-QNAME" if opts.get("REQID") else "MOVE SPACES TO GG-QNAME",
                 f"MOVE {opts.get(when) or 0} TO GG-NUM",  # (AFTER / AT: GG-HOURS ...)
                 f"MOVE '{flags}' TO GG-FLAGS", f"MOVE {length} TO GG-LEN",
                 f"MOVE {1 if area else 0} TO GG-ITEM"]  # fmt: skip
        if hms:
            lines += [f"MOVE {opts.get(o) or -999999999} TO {f}"
                      for o, f in (("HOURS", "GG-HOURS"), ("MINUTES", "GG-MINS"), ("SECONDS", "GG-SECS"))]  # fmt: skip
        lines += [f"MOVE {opts[o]} TO {data_in[o]}" for o in named]
        if "CHANNEL" in opts:
            lines.append(f"MOVE {opts['CHANNEL']} TO GG-CHAN")
        lines += ec._past_from(opts.get("LENGTH") or opts.get("FLENGTH"), area, "START")
        return lines + ec._call("GGCSTRT", [f"BY REFERENCE {area or 'GG-FLAGS'}"]) + ec._resp(opts, True, labels)
    if verb == "RETRIEVE":
        into, setp = opts.get("INTO"), opts.get("SET")
        length = ec._one_of("RETRIEVE", opts, "LENGTH", "FLENGTH")
        if setp:  # #5042 (X58): SET(pointer) LENGTH(data-area) -> GGCRTRS, the data as a new block
            if into:
                raise ec.Unsupported(ec._rule("RETRIEVE", "at_most_one", "INTO"), ["RETRIEVE"])
            if not length or re.fullmatch(r"(?is)[+-]?\d+|LENGTH\s+OF\s+.+", length.strip()):
                raise ec.Unsupported(ec._rule("RETRIEVE", "requires", "SET"), ["RETRIEVE"])
        elif not into and (not named or length):
            raise ec.Unsupported(ec._rule("RETRIEVE", "requires", "LENGTH"), ["RETRIEVE"])
        flags = " ".join((["INTO"] if into or setp else []) + named)
        lines = [f"MOVE '{flags}' TO GG-FLAGS", f"MOVE {length or (f'LENGTH OF {into}' if into else '0')} TO GG-LEN"]
        if setp:
            lines += ec._call("GGCRTRS", [f"BY REFERENCE {ec._pointer('RETRIEVE', setp)}"])
        else:
            lines += ec._call("GGCRTRV", [f"BY REFERENCE {into or 'GG-FLAGS'}"])
        if length:
            lines += ["IF GG-RESP = 0 OR GG-RESP = 22", f"    MOVE GG-LEN TO {length}", "END-IF"]
        if named:
            lines += [
                "IF GG-RESP = 0 OR GG-RESP = 22",
                *[f"    MOVE {data_in[o]} TO {opts[o]}" for o in named],
                "END-IF",
            ]
        return lines + ec._resp(opts, True, labels)
    if not opts.get("REQID"):
        raise ec.Unsupported(ec._rule("CANCEL", "required", "REQID"), ["CANCEL without REQID"])
    return [f"MOVE {opts['REQID']} TO GG-QNAME"] + ec._call("GGCCNCL", []) + ec._resp(opts, True, labels)


def _cobol_start(kv: dict[str, str], data: bytes, enc: str) -> dict[str, Any]:
    """#4270 (GenApp LGWEBST5): a START the stub logged (GGCSTRT: `interval=` or `time=` hhmmss, `protect` 0 / 1,
    `resp` by number, `expires` from $GGCICS_NOW -- the case's clock --, `area` 1 with FROM, its bytes in the event's
    blob) as CicsTask.start records it: {transid, termid, interval | time, reqid, protect, resp, resp2, expires,
    from}. FROM is compared as text in the data's page, as a WRITEQ TS item is (`java_start_as_compared`)."""
    resp = ec.RESP_NAMES.get(int(kv.get("resp", "0")), kv.get("resp", ""))
    when = "time" if "time" in kv else "interval"
    out: dict[str, Any] = {"transid": kv.get("transid", ""), "termid": kv.get("termid") or None,
                           when: kv.get(when) or None, "protect": kv.get("protect") == "1", "resp": resp,
                           "expires": kv.get("expires") or None}  # fmt: skip
    if kv.get("reqid"):
        out["reqid"] = kv["reqid"]
    if resp in ("INVREQ", "CHANNELERR"):  # (#4950: CHANNELERR RESP2 1, an incorrect CHANNEL name)
        out["resp2"] = int(kv.get("resp2", "0"))
    for key in ("rtransid", "rtermid", "queue"):  # the data options the program named (hex of the trimmed name)
        if key in kv:
            out[key] = bytes.fromhex(kv[key]).decode("latin-1")
    if kv.get("area") == "1":
        text = common._decode_text(data, enc)
        out["from"] = f"<undecodable {data!r} in {enc}>" if text is None else text
    else:
        out["from"] = None
    return out


def _cobol_retrieve(kv: dict[str, str], data: bytes, enc: str) -> dict[str, Any]:
    """#5089: a RETRIEVE the stub logged (GGCRTRV: `resp` by number, `len` the stored length -1 for none, `into` 1 with
    INTO, the bytes copied in the event's blob, `rtransid` / `rtermid` / `queue` as hex of the name) as
    CicsTask.retrieve records it: {resp, length, data, rtransid?, rtermid?, queue?}; the data compared as text in the
    data's page, as START's FROM is (java_retrieve_as_compared)."""
    resp = ec.RESP_NAMES.get(int(kv.get("resp", "0")), kv.get("resp", ""))
    length = int(kv.get("len", "-1"))
    out: dict[str, Any] = {"resp": resp, "length": None if length < 0 or kv.get("into") != "1" else length}
    if kv.get("into") == "1" and length >= 0:
        text = common._decode_text(data, enc)
        out["data"] = f"<undecodable {data!r} in {enc}>" if text is None else text
    else:
        out["data"] = None
    for key in ("rtransid", "rtermid", "queue"):
        if key in kv:
            out[key] = bytes.fromhex(kv[key]).decode("latin-1")
    return out


def java_retrieve_as_compared(e: dict[str, Any]) -> dict[str, Any]:
    """#5089: CicsTask's RETRIEVE event as the comparison reads it: its data (bytes, base64 in the JSON) in the region's
    page, as text (java_start_as_compared)."""
    import base64

    from gitgalaxy.tools.cobol_to_java.det.cics import REGION_PAGE

    data = e.get("data")
    if not isinstance(data, str):
        return {**e, "data": None}
    raw = base64.b64decode(data)
    try:
        return {**e, "data": raw.decode(REGION_PAGE)}
    except UnicodeDecodeError:
        return {**e, "data": f"<undecodable {raw!r} in {REGION_PAGE}>"}


def java_start_as_compared(e: dict[str, Any]) -> dict[str, Any]:
    """#4270: CicsTask's START event as the comparison reads it: its FROM data (bytes, base64 in the JSON) in the
    region's page, as text (java_ts_as_compared)."""
    import base64

    from gitgalaxy.tools.cobol_to_java.det.cics import REGION_PAGE

    data = e.get("from")
    if not isinstance(data, str):
        return {**e, "from": None}
    raw = base64.b64decode(data)
    try:
        return {**e, "from": raw.decode(REGION_PAGE)}
    except UnicodeDecodeError:
        return {**e, "from": f"<undecodable {raw!r} in {REGION_PAGE}>"}
