"""#5274: the program control family of the CICS harness's stub translator (equivalence_cics.translate), split out of
equivalence_cics.py: RETURN, XCTL (#4008, #4270, #5005, #6271), LINK (#4004, #4270) and ABEND (#4003). The family registry in
equivalence_cics calls `command`; it reaches the shared helpers through the module at call time, so the import works
either way round."""

from __future__ import annotations

import equivalence_cics as ec


def command(
    verb: str,
    opts: dict[str, str | None],
    pairs: list[tuple[str, str | None]],
    labels: list[str],
    handle_aid: bool,
) -> list[str] | None:
    """The program control commands, or None for a command of another family."""
    if verb in ("RETURN", "XCTL"):
        if verb == "XCTL" and not opts.get("PROGRAM"):
            raise ec.Unsupported("XCTL without PROGRAM")
        ec._check_spec(verb, opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        if verb == "RETURN" and "CHANNEL" in opts:  # #5005 (X17): the next task's current channel (GGCRETC)
            if not opts.get("TRANSID") or {"COMMAREA", "LENGTH", "IMMEDIATE"} & opts.keys():
                raise ec.Unsupported(ec._rule("RETURN", "at_most_one", "CHANNEL"), ["RETURN CHANNEL"])
            return ([ec._name(opts["TRANSID"], "GG-NAME1"), f"MOVE {opts['CHANNEL']} TO GG-CHAN"]
                    + ec._call("GGCRETC", ["BY REFERENCE GG-FLAGS", "BY VALUE 0"])
                    + ["IF GG-RESP = 0", "    GOBACK", "END-IF"] + ec._resp(opts, True, labels))  # fmt: skip
        if verb == "XCTL" and opts.get("CHANNEL"):  # #4270: the target's current channel (GGCXCTL)
            if "COMMAREA" in opts or "LENGTH" in opts:
                raise ec.Unsupported(ec._rule("XCTL", "at_most_one", "CHANNEL"), ["XCTL CHANNEL"])
            return ([ec._name(opts["PROGRAM"], "GG-NAME1"), "MOVE 0 TO GG-ITEM", "MOVE 'CHANNEL' TO GG-FLAGS",
                     f"MOVE {opts['CHANNEL']} TO GG-CHAN"]
                    + ec._call("GGCXCTL", ["BY REFERENCE GG-FLAGS", "BY VALUE 0"])
                    + ["IF GG-RESP = 0", "    GOBACK", "END-IF"] + ec._resp(opts, True, labels))  # fmt: skip
        target = opts.get("TRANSID") if verb == "RETURN" else opts.get("PROGRAM")
        area = opts.get("COMMAREA")
        args = ([f"BY REFERENCE {area}", f"BY VALUE {opts.get('LENGTH') or f'LENGTH OF {area}'}"] if area
                else ["BY REFERENCE GG-FLAGS", "BY VALUE 0"])  # fmt: skip
        if verb == "RETURN" and "IMMEDIATE" in opts:  # #4270 (X27): the next task attached at once; can fail (GGCRETI)
            if not target:
                raise ec.Unsupported("RETURN IMMEDIATE without TRANSID: IBM does not say what it attaches (not modelled)",
                                  ["RETURN IMMEDIATE"])  # fmt: skip
            return ([ec._name(target, "GG-NAME1"), f"MOVE {1 if area else 0} TO GG-ITEM"]
                    + ec._call("GGCRETI", args) + ["IF GG-RESP = 0", "    GOBACK", "END-IF"]
                    + ec._resp(opts, True, labels))  # fmt: skip
        if verb == "RETURN" and opts.get("TRANSID") and opts.get("RESP"):  # #6271 (X71): a planned fault fails it
            return ([ec._name(target, "GG-NAME1"), "MOVE 2 TO GG-ITEM"] + ec._call("GGCRETN", args)
                    + ["IF GG-RESP = 0", "    GOBACK", "END-IF"] + ec._resp(opts, True, labels))  # fmt: skip
        if verb == "RETURN":
            return [ec._name(target, "GG-NAME1")] + ec._call("GGCRETN", args) + ["GOBACK"]
        # #4008: a failed XCTL (LENGERR, PGMIDERR) leaves control here, through the condition handling
        return ([ec._name(target, "GG-NAME1"), f"MOVE {1 if area else 0} TO GG-ITEM", "MOVE SPACES TO GG-FLAGS"]
                + ec._call("GGCXCTL", args)
                + ["IF GG-RESP = 0", "    GOBACK", "END-IF"] + ec._resp(opts, True, labels))  # fmt: skip
    if verb == "LINK":  # #4004: a new level runs the program on the caller's own COMMAREA storage
        ec._check_spec("LINK", opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        if not opts.get("PROGRAM"):
            raise ec.Unsupported("LINK without PROGRAM", ["LINK"])
        if "CHANNEL" in opts and not opts["CHANNEL"]:
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, ["LINK CHANNEL"])
        if "CHANNEL" in opts and ("COMMAREA" in opts or "LENGTH" in opts):
            raise ec.Unsupported(ec._rule("LINK", "at_most_one", "CHANNEL"), ["LINK CHANNEL"])
        area = opts.get("COMMAREA")
        # #4270: CHANNEL -- the callee's current channel (GGCLINK)
        chan = (
            ["MOVE 'CHANNEL' TO GG-FLAGS", f"MOVE {opts['CHANNEL']} TO GG-CHAN"]
            if opts.get("CHANNEL")
            else ["MOVE SPACES TO GG-FLAGS"]
        )
        length = opts.get("LENGTH") or opts.get("FLENGTH") or (f"LENGTH OF {area}" if area else "0")
        ref = area or "GG-FLAGS"
        return ([ec._name(opts["PROGRAM"], "GG-NAME1"), f"MOVE {length} TO GG-LEN", f"MOVE {1 if area else 0} TO GG-ITEM"]
                + chan + ec._call("GGCLINK", [f"BY REFERENCE {ref}"])
                + ec._map_abend(labels)  # #6271 (X70): a planned abend at the LINK went to the exit, or ended the task
                + ["IF GG-RESP = 0", f"    CALL 'GGCRUN' USING {ref}", "    CALL 'GGCLRET' USING GG-CICS"]
                + [f"    {ln}" for ln in ec._transfer(labels)]
                + ["    IF GG-GOTO < 0", "        GOBACK", "    END-IF", "END-IF"]
                + ec._resp(opts, True, labels))  # fmt: skip
    if verb == "ABEND":  # #4003: an exit at this level takes it by GO TO; else the program is left
        ec._check_spec("ABEND", opts, (verb,))
        return ([ec._name(opts.get("ABCODE"), "GG-NAME1"), "MOVE 'CANCEL' TO GG-FLAGS" if "CANCEL" in opts else "MOVE SPACES TO GG-FLAGS"]
                + ec._call("GGCABND", []) + ec._transfer(labels) + ["GOBACK"])  # fmt: skip
    return None
