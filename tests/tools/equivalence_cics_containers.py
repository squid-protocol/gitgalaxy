"""#5274: the channels / containers family of the CICS harness's stub translator (equivalence_cics.translate), split
out of equivalence_cics.py: PUT / GET / DELETE CONTAINER (#4270), MOVE CONTAINER and the container browse (#4951),
DELETE / QUERY CHANNEL (#5005). equivalence_cics's command dispatch calls these; they reach its shared helpers (the
spec, `_call`, `_resp`, the refusals) through the module at call time, so the import works either way round."""

from __future__ import annotations

import re

import equivalence_cics as ec


def _container_ccsid(opts: dict[str, str | None], option: str) -> list[str]:
    """#4270 (X17): the CCSID option of a PUT / GET CONTAINER (FROMCCSID / INTOCCSID) as `MOVE value TO GG-NUM` (the flag in
    GG-FLAGS is the caller's); not given: no lines."""
    return [f"MOVE {opts[option]} TO GG-NUM"] if option in opts else []


def _container_command(verb: str, opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4270: PUT / GET / DELETE CONTAINER -> GGCPUTC / GGCGETC / GGCDELC. The container's name in GG-QNAME, the
    channel's in GG-CHAN (GG-FLAGS 'CHANNEL'; none: the current channel), the data type, APPEND and NODATA in
    GG-FLAGS, FLENGTH in GG-LEN (PUT: the bytes FROM gives; GET: the most INTO takes, then the container's length,
    set back on NORMAL / LENGERR; BYTEOFFSET: GG-NUM, flag BYTEOFFSET, #5005). The CCSID options (code-page conversion) and SET (a pointer)
    are refused, as det/cics.py refuses them; so is an FLENGTH past FROM / INTO (storage GnuCOBOL lays out unlike
    IBM's compiler)."""
    feature = f"{verb} CONTAINER"
    ec._check_spec(feature, opts, (verb,), lambda bad: [f"{feature} {o}" for o in sorted(bad)])
    if not opts.get("CONTAINER"):
        raise ec.Unsupported(ec.NEEDS_ARGUMENT, [f"{feature} ?"])
    flags = ["CHANNEL"] if opts.get("CHANNEL") else []
    lines = [f"MOVE {opts['CONTAINER']} TO GG-QNAME",
             f"MOVE {opts['CHANNEL']} TO GG-CHAN" if opts.get("CHANNEL") else "MOVE SPACES TO GG-CHAN"]  # fmt: skip
    if verb == "DELETE":
        return (
            lines
            + [f"MOVE '{' '.join(flags)}' TO GG-FLAGS" if flags else "MOVE SPACES TO GG-FLAGS"]
            + ec._call("GGCDELC", [])
            + ec._resp(opts, True, labels)
        )
    flength = opts.get("FLENGTH")
    if verb == "PUT":
        frm = opts.get("FROM")
        if not frm:
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, [feature])
        types = [t for t in ("BIT", "CHAR") if t in opts]
        if opts.get("DATATYPE"):
            m = re.fullmatch(r"\s*DFHVALUE\s*\(\s*(BIT|CHAR)\s*\)\s*", opts["DATATYPE"], re.I)
            if m is None:
                raise ec.Unsupported(f"PUT CONTAINER DATATYPE({opts['DATATYPE']}): only DFHVALUE(BIT / CHAR) is modelled",
                                  [f"{feature} DATATYPE"])  # fmt: skip
            types.append(m.group(1).upper())
        if len(types) > 1:
            raise ec.Unsupported(ec._rule("PUT CONTAINER", "at_most_one", "BIT", " and ".join(types)), [feature])
        if "APPEND" in opts and "PREPEND" in opts:  # #5005 (X17)
            raise ec.Unsupported(ec._rule("PUT CONTAINER", "at_most_one", "APPEND", "PREPEND"), [feature])
        flags += types + (["APPEND"] if "APPEND" in opts else []) + (["PREPEND"] if "PREPEND" in opts else [])
        code = _container_ccsid(opts, "FROMCCSID")
        flags += ["FROMCCSID"] if code else []
        return (lines + code + [f"MOVE '{' '.join(flags)}' TO GG-FLAGS" if flags else "MOVE SPACES TO GG-FLAGS",
                         f"MOVE {flength or f'LENGTH OF {frm}'} TO GG-LEN"]
                + ec._past_from(flength, frm, "PUT CONTAINER") + ec._call("GGCPUTC", [f"BY REFERENCE {frm}"])
                + ec._resp(opts, True, labels))  # fmt: skip
    into, nodata = opts.get("INTO"), "NODATA" in opts
    if [bool(into), nodata, "SET" in opts].count(True) != 1:
        raise ec.Unsupported(ec._rule("GET CONTAINER", "one_of", "INTO"), [feature])
    settable = bool(flength) and re.fullmatch(r"(?is)[+-]?\d+|LENGTH\s+OF\s+.+", flength.strip()) is None
    if "BYTEOFFSET" in opts:  # #5005 (X17): GG-NUM carries the offset, as the CCSID options' GG-NUM does theirs
        if not into:
            need = next(
                g.msg for g in ec.SPEC["GET CONTAINER"].groups if g.kind == "requires" and g.options == ("BYTEOFFSET",)
            )
            raise ec.Unsupported(need, [feature])
        for other in ("INTOCCSID", "CONVERTST", "CCSID"):
            if other in opts:
                raise ec.Unsupported(ec._rule("GET CONTAINER", "at_most_one", "BYTEOFFSET", other), [feature])
    if "SET" in opts:  # #5042 (X58): SET(pointer) FLENGTH(data-area) -> GGCGETS, a copy in a new block
        if not settable:
            raise ec.Unsupported(ec._rule("GET CONTAINER", "requires", "SET"), [feature])
        lines += _container_get_options(opts, flags)
        lines += [
            "MOVE SPACES TO GG-FLAGS" if not flags else f"MOVE '{' '.join(flags)}' TO GG-FLAGS",
            "MOVE 0 TO GG-LEN",
        ]
        lines += ec._call("GGCGETS", [f"BY REFERENCE {ec._pointer('GET CONTAINER', opts['SET'])}"])
        return (lines + ["IF GG-RESP = 0", f"    MOVE GG-LEN TO {flength}"] + _container_ccsid_out(opts)
                + ["END-IF"] + ec._resp(opts, True, labels))  # fmt: skip
    flags += ["NODATA"] if nodata else []
    if "BYTEOFFSET" in opts:  # GG-NUM carries the offset, as the CCSID options' GG-NUM does theirs
        flags.append("BYTEOFFSET")
        lines.append(f"MOVE {opts['BYTEOFFSET']} TO GG-NUM")
    lines += _container_get_options(opts, flags)
    lines += [
        f"MOVE '{' '.join(flags)}' TO GG-FLAGS" if flags else "MOVE SPACES TO GG-FLAGS",
        "MOVE 0 TO GG-LEN" if nodata else f"MOVE {flength or f'LENGTH OF {into}'} TO GG-LEN",
    ]
    if into and flength:
        lines += ec._past_from(flength, into, "GET CONTAINER")
    lines += ec._call("GGCGETC", [f"BY REFERENCE {into or 'GG-FLAGS'}"])
    if settable or "CCSID" in opts:
        lines += ["IF GG-RESP = 0 OR GG-RESP = 22"] + ([f"    MOVE GG-LEN TO {flength}"] if settable else [])
        lines += _container_ccsid_out(opts) + ["END-IF"]
    return lines + ec._resp(opts, True, labels)


def _container_get_options(opts: dict[str, str | None], flags: list[str]) -> list[str]:
    """#4270 (X17): GET CONTAINER's INTOCCSID (GG-NUM in, flag INTOCCSID) and CONVERTST(NOCONVERT) (flag NOCONVERT); `flags` gains
    the flag. As the translator: one target code page, CCSID only with CONVERTST."""
    if "INTOCCSID" in opts and "CONVERTST" in opts:
        raise ec.Unsupported(
            ec._rule("GET CONTAINER", "at_most_one", "INTOCCSID", "INTOCCSID and CONVERTST"), ["GET CONTAINER"]
        )
    if "CCSID" in opts and "CONVERTST" not in opts:
        raise ec.Unsupported(ec._rule("GET CONTAINER", "requires", "CCSID"), ["GET CONTAINER"])
    if "CONVERTST" in opts:
        if re.fullmatch(r"(?is)\s*(DFHVALUE\s*\(\s*NOCONVERT\s*\)|734)\s*", opts["CONVERTST"] or "") is None:
            raise ec.Unsupported(f"GET CONTAINER CONVERTST({opts['CONVERTST']}): only DFHVALUE(NOCONVERT) is modelled",
                              ["GET CONTAINER CONVERTST"])  # fmt: skip
        flags.append("NOCONVERT")
        return []
    code = _container_ccsid(opts, "INTOCCSID")
    flags += ["INTOCCSID"] if code else []
    return code


def _container_ccsid_out(opts: dict[str, str | None]) -> list[str]:
    """GET CONTAINER CCSID(area): the container's CCSID (0: BIT), which the stub leaves in GG-NUM."""
    return [f"    MOVE GG-NUM TO {opts['CCSID']}"] if "CCSID" in opts else []


def _container_browse_command(verb: str, opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4951: MOVE CONTAINER -> GGCMOVC (CONTAINER in GG-QNAME, AS in GG-AS, CHANNEL in GG-CHAN, TOCHANNEL in GG-TOCHAN;
    GG-FLAGS says which channels are given), STARTBROWSE CONTAINER -> GGCSBRC (the token comes back in GG-NUM), GETNEXT
    CONTAINER -> GGCGNXC (the token in GG-NUM; the name comes back in GG-QNAME) and ENDBROWSE CONTAINER -> GGCEBRC."""
    key = f"{verb} CONTAINER"
    ec._check_spec(key, opts, (verb, "CONTAINER") if verb in ("STARTBROWSE", "ENDBROWSE") else (verb,))
    for need in ec.SPEC[key].groups:
        if need.kind == "required" and not opts.get(need.options[0]):
            raise ec.Unsupported(need.msg, [key])
    flags = [f for f, o in (("CHANNEL", "CHANNEL"), ("TOCHAN", "TOCHANNEL")) if opts.get(o)]
    chans = ([f"MOVE {opts['CHANNEL']} TO GG-CHAN"] if opts.get("CHANNEL") else []) + (
        [f"MOVE {opts['TOCHANNEL']} TO GG-TOCHAN"] if opts.get("TOCHANNEL") else []
    )
    setflags = f"MOVE '{' '.join(flags)}' TO GG-FLAGS" if flags else "MOVE SPACES TO GG-FLAGS"
    if verb == "MOVE":
        lines = [f"MOVE {opts['CONTAINER']} TO GG-QNAME", f"MOVE {opts['AS']} TO GG-AS", *chans, setflags]
        return lines + ec._call("GGCMOVC", []) + ec._resp(opts, True, labels)
    if verb == "STARTBROWSE":
        token = opts["BROWSETOKEN"]
        return ([*chans, setflags] + ec._call("GGCSBRC", []) + ["IF GG-RESP = 0", f"    MOVE GG-NUM TO {token}", "END-IF"]
                + ec._resp(opts, True, labels))  # fmt: skip
    lines = [f"MOVE {opts['BROWSETOKEN']} TO GG-NUM"]
    if verb == "GETNEXT":
        return (lines + ec._call("GGCGNXC", []) + ["IF GG-RESP = 0", f"    MOVE GG-QNAME TO {opts['CONTAINER']}", "END-IF"]
                + ec._resp(opts, True, labels))  # fmt: skip
    return lines + ec._call("GGCEBRC", []) + ec._resp(opts, True, labels)


def _channel_command(verb: str, opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#5005: DELETE CHANNEL -> GGCDELH and QUERY CHANNEL -> GGCQCHN (CHANNEL in GG-CHAN; the count comes back in GG-NUM and
    is moved to CONTAINERCNT on NORMAL)."""
    key = f"{verb} CHANNEL"
    ec._check_spec(key, opts, (verb,))
    for need in ec.SPEC[key].groups:
        if need.kind == "required" and not opts.get(need.options[0]):
            raise ec.Unsupported(need.msg, [key])
    lines = [f"MOVE {opts['CHANNEL']} TO GG-CHAN"]
    if verb == "DELETE":
        return lines + ec._call("GGCDELH", []) + ec._resp(opts, True, labels)
    return (lines + ec._call("GGCQCHN", []) + ["IF GG-RESP = 0", f"    MOVE GG-NUM TO {opts['CONTAINERCNT']}", "END-IF"]
            + ec._resp(opts, True, labels))  # fmt: skip


def command(
    verb: str,
    opts: dict[str, str | None],
    pairs: list[tuple[str, str | None]],
    labels: list[str],
    handle_aid: bool,
) -> list[str] | None:
    """The container and channel commands, or None for a command of another family."""
    if verb in ("PUT", "GET", "DELETE") and "CONTAINER" in opts:  # #4270
        return _container_command(verb, opts, labels)
    if (
        verb in ("PUT64", "GET64") and "CONTAINER" in opts
    ):  # #5005 (X17): the base command; SET (64-bit pointer) refused
        if "SET" in opts:
            raise ec.Unsupported(ec.SPEC[f"{verb} CONTAINER"].refusal_message(["SET"]), [f"{verb} CONTAINER SET"])
        return _container_command(verb[:3], {o: v for o, v in opts.items() if o != verb}, labels)
    if verb in ("MOVE", "STARTBROWSE", "GETNEXT", "ENDBROWSE") and "CONTAINER" in opts:  # #4951
        return _container_browse_command(verb, opts, labels)
    if verb in ("DELETE", "QUERY") and "CHANNEL" in opts and "CONTAINER" not in opts:  # #5005
        return _channel_command(verb, opts, labels)
    return None
