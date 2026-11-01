"""#5274: the transient data family of the CICS harness's stub translator (equivalence_cics.translate), split out of
equivalence_cics.py: WRITEQ / READQ / DELETEQ TD (#5079) and INQUIRE / SET TDQUEUE (#5168). The family registry in
equivalence_cics calls `command`; it reaches the shared helpers through the module at call time, so the import works
either way round."""

from __future__ import annotations

import re

import equivalence_cics as ec


def _td_command(verb: str, opts: dict[str, str | None], labels: list[str] | None = None) -> list[str]:
    """#5079 (X57): READQ TD / DELETEQ TD -> GGCRDTD / GGCDLTD (the queue in GG-QNAME). READQ's LENGTH is in-out, as READ's:
    in, the most INTO takes; out, the record's length, on NORMAL and LENGERR."""
    feature = f"{verb} TD"
    ec._check_spec(feature, opts, (verb, "TD"), lambda bad: [f"{feature} {bad[0]}"])
    queue = opts.get("QUEUE")
    if not queue:
        raise ec.Unsupported(f"{feature} without QUEUE", [feature])
    lines = [f"MOVE {queue} TO GG-QNAME"]
    if verb == "DELETEQ":
        return lines + ec._call("GGCDLTD", []) + ec._resp(opts, True, labels)
    into, length = opts.get("INTO"), opts.get("LENGTH")
    if (
        "NOSUSPEND" in opts
    ):  # #5168 (X61): the stub reads (and clears) it: a planned QBUSY needs NOSUSPEND, else IBM suspends
        lines.append("MOVE 'TDNOSUSPEND' TO GG-FLAGS")
    if opts.get(
        "SET"
    ):  # #5168 (X61): SET(pointer) LENGTH(data-area) -> GGCRDTS, the record as a new block (X58's lane)
        if into:
            raise ec.Unsupported(ec._rule(feature, "at_most_one", "INTO"), [feature])
        if not length or re.fullmatch(r"(?is)\d+|LENGTH\s+OF\s+.+", length.strip()):
            raise ec.Unsupported(ec._rule(feature, "requires", "SET"), [feature])
        return (lines + ec._call("GGCRDTS", [f"BY REFERENCE {ec._pointer(feature, opts['SET'])}"])
                + ["IF GG-RESP = 0", f"    MOVE GG-LEN TO {length}", "END-IF"] + ec._resp(opts, True, labels))  # fmt: skip
    if not into:
        raise ec.Unsupported(f"{feature} without INTO", [feature])
    settable = bool(length) and re.fullmatch(r"(?is)\d+|LENGTH\s+OF\s+.+", length.strip()) is None
    after = ["IF GG-RESP = 0 OR GG-RESP = 22", f"    MOVE GG-LEN TO {length}", "END-IF"] if settable else []
    lines.append(f"MOVE {length or f'LENGTH OF {into}'} TO GG-LEN")
    return (lines + ec._call("GGCRDTD", [f"BY REFERENCE {into}", f"BY VALUE LENGTH OF {into}"])
            + after + ec._resp(opts, True, labels))  # fmt: skip


def command(
    verb: str,
    opts: dict[str, str | None],
    pairs: list[tuple[str, str | None]],
    labels: list[str],
    handle_aid: bool,
) -> list[str] | None:
    """The transient data commands, or None for a command of another family."""
    if verb in ("INQUIRE", "SET") and "TDQUEUE" in opts:  # #5168 round 3 (X61): an extrapartition queue's open state
        key = f"{verb} TDQUEUE"
        ec._check_spec(key, opts, (verb,), lambda bad: [key])
        if not opts.get("TDQUEUE"):
            raise ec.Unsupported(ec._rule(key, "required", "TDQUEUE"), [key])
        queue = ec._name(opts["TDQUEUE"], "GG-QNAME")
        if verb == "SET":
            given = [o for o in ("OPENSTATUS", "ENABLESTATUS", "TRIGGERLEVEL") if opts.get(o)]
            if not given:
                raise ec.Unsupported(ec._rule(key, "requires", "TDQUEUE"), [key])
            if len(given) > 1:  # #5168 round 5 (X66): one state per command
                raise ec.Unsupported(f"SET TDQUEUE with {' and '.join(given)} together", [key])
            if opts.get("TRIGGERLEVEL"):  # #5168 round 7 (X66): the level in GG-NUM
                return ([queue, f"MOVE {opts['TRIGGERLEVEL']} TO GG-NUM"] + ec._call("GGCSTDT", [])
                        + ec._resp(opts, True, labels))  # fmt: skip
            if opts.get("ENABLESTATUS"):
                return ([queue, f"MOVE {opts['ENABLESTATUS']} TO GG-NUM"] + ec._call("GGCSTDE", [])
                        + ec._resp(opts, True, labels))  # fmt: skip
            return (
                [queue, f"MOVE {opts['OPENSTATUS']} TO GG-NUM"] + ec._call("GGCSTDQ", []) + ec._resp(opts, True, labels)
            )
        wanted = [
            o for o in ("OPENSTATUS", "TYPE", "ENABLESTATUS", "TRIGGERLEVEL", "RECOVSTATUS", "TRANSID") if opts.get(o)
        ]
        if not wanted:
            raise ec.Unsupported(ec._rule(key, "requires", "TDQUEUE"), [key])
        # #5168 round 6 (X66): TRIGGERLEVEL, RECOVSTATUS and TRANSID come back in the otherwise unused GG-HOURS, GG-MINS, GG-RTRAN
        field = {"OPENSTATUS": "GG-NUM", "TYPE": "GG-LEN", "ENABLESTATUS": "GG-ITEM", "TRIGGERLEVEL": "GG-HOURS",
                 "RECOVSTATUS": "GG-MINS", "TRANSID": "GG-RTRAN"}  # fmt: skip
        return ([queue, f"MOVE '{' '.join(wanted)}' TO GG-FLAGS"] + ec._call("GGCITDQ", []) + ["IF GG-RESP = 0"]
                + [f"    MOVE {field[o]} TO {opts[o]}" for o in wanted]
                + ["END-IF"] + ec._resp(opts, True, labels))  # fmt: skip
    if verb == "WRITEQ" and "TD" in opts:  # transient data: a record on an extrapartition / intrapartition queue
        ec._check_spec("WRITEQ TD", opts, (verb, "TD"), lambda bad: [f"WRITEQ TD {bad[0]}"])
        queue, frm = opts.get("QUEUE"), opts.get("FROM")
        if not (queue and frm):
            raise ec.Unsupported("WRITEQ TD without QUEUE / FROM", ["WRITEQ TD"])
        return ([ec._name(queue, "GG-QNAME"), f"MOVE {opts.get('LENGTH') or 'LENGTH OF ' + frm} TO GG-LEN"]
                + ec._write_from(opts.get("LENGTH"), frm, "WRITEQ TD", ec._call("GGCWRTD", [f"BY REFERENCE {frm}"]))
                + ec._resp(opts, True, labels))  # fmt: skip
    if verb in ("READQ", "DELETEQ") and "TD" in opts:  # #5079 (X57): transient data, intrapartition
        return _td_command(verb, opts, labels)
    return None
