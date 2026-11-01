"""#5274: the terminal family of the CICS harness's stub translator (equivalence_cics.translate), split out of
equivalence_cics.py: SEND MAP / CONTROL / TEXT, RECEIVE MAP, RECEIVE (#4005, #4413, #5042) and INQUIRE / SET TERMINAL
(#4415). CONVERSE stays with task control. The family registry in equivalence_cics calls `command`; it reaches the shared
helpers through the module at call time, so the import works either way round."""

from __future__ import annotations

import re

import equivalence_cics_conditions as cics_conditions
import equivalence_cics as ec


def command(
    verb: str,
    opts: dict[str, str | None],
    pairs: list[tuple[str, str | None]],
    labels: list[str],
    handle_aid: bool,
) -> list[str] | None:
    """The terminal commands, or None for a command of another family."""
    if verb in ("INQUIRE", "SET") and "TERMINAL" in opts:  # #4415 slice 1 (X26): the terminal's UCTRANST CVDA
        key = f"{verb} TERMINAL"
        ec._check_spec(key, opts, (verb,), lambda bad: [key])
        if not opts.get("TERMINAL"):
            raise ec.Unsupported(ec._rule(key, "required", "TERMINAL"), [key])
        if not opts.get("UCTRANST"):
            raise ec.Unsupported(f"{key} without UCTRANST", [key])
        if verb == "SET":
            return ([ec._name(opts["TERMINAL"], "GG-NAME1"), f"MOVE {opts['UCTRANST']} TO GG-NUM"]
                    + ec._call("GGCSETT", []) + ec._resp(opts, True, labels))  # fmt: skip
        return ([ec._name(opts["TERMINAL"], "GG-NAME1")] + ec._call("GGCINQT", [])
                + ["IF GG-RESP = 0", f"    MOVE GG-NUM TO {opts['UCTRANST']}", "END-IF"]
                + ec._resp(opts, True, labels))  # fmt: skip
    if verb == "RECEIVE" and "MAP" in opts:
        ec._check_spec("RECEIVE MAP", opts, (verb,))
        into = opts.get("INTO") or (f"{ec._literal(opts['MAP'])}I" if ec._literal(opts["MAP"]) else None)
        if not into:
            raise ec.Unsupported("RECEIVE MAP(data-name) without INTO")
        return ([ec._name(opts["MAP"], "GG-NAME1"), ec._name(opts.get("MAPSET") or opts["MAP"], "GG-NAME2")]
                + ec._call("GGCRECV", [f"BY REFERENCE {into}", f"BY VALUE LENGTH OF {into}"])
                + ec._map_abend(labels)
                + cics_conditions.input_resp(opts, labels, handle_aid))  # fmt: skip
    if verb == "RECEIVE":  # #4005: terminal input, unformatted (SPEC 5: the step's `text`)
        ec._check_spec("RECEIVE", opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        into, setp = opts.get("INTO"), opts.get("SET")
        # LENGTH / FLENGTH is in-out: in, the most INTO takes (unless MAXLENGTH / MAXFLENGTH says so);
        # out, the length of the data. COBOL may omit it: the translator supplies LENGTH OF INTO.
        length = ec._one_of("RECEIVE", opts, "LENGTH", "FLENGTH")
        most = ec._one_of("RECEIVE", opts, "MAXLENGTH", "MAXFLENGTH")
        flags = "MOVE 'NOTRUNCATE' TO GG-FLAGS" if "NOTRUNCATE" in opts else "MOVE SPACES TO GG-FLAGS"  # #4413
        if setp:  # #4413: SET(ADDRESS OF record), LENGTH(data-area) required; no MAXLENGTH: all the input (det/cics.py says why)
            m = re.fullmatch(r"ADDRESS\s+OF\s+([A-Z0-9-]+)", setp, re.I)
            if into or not length:
                raise ec.Unsupported("RECEIVE SET without LENGTH", ["RECEIVE SET"])
            most = most or "32768"  # LENGTH is output-only with SET (X15): the whole input, the stub's buffer size
            if not m:  # #5042 (X58): SET(pointer) -> GGCRECP, the data in a new block the pointer addresses
                return ([flags, f"MOVE {most} TO GG-LEN"] + ec._call("GGCRECP", [f"BY REFERENCE {ec._pointer('RECEIVE', setp)}"])
                        + [f"MOVE GG-LEN TO {length}"] + cics_conditions.input_resp(opts, labels, handle_aid))  # fmt: skip
            return ([flags, f"MOVE {most} TO GG-LEN"] + ec._call("GGCRECS", ["BY REFERENCE GG-PTR"])
                    + [f"SET ADDRESS OF {m.group(1)} TO GG-PTR", f"MOVE GG-LEN TO {length}"]
                    + cics_conditions.input_resp(opts, labels, handle_aid))  # fmt: skip
        if not into:
            raise ec.Unsupported(ec._rule("RECEIVE", "one_of", "INTO"), ["RECEIVE"])
        limit = most or length or f"LENGTH OF {into}"
        lines = [flags, f"MOVE {limit} TO GG-LEN"] + ec._call("GGCRECT", [f"BY REFERENCE {into}"])
        if length:
            lines.append(f"MOVE GG-LEN TO {length}")
        return lines + cics_conditions.input_resp(opts, labels, handle_aid)
    if verb == "SEND" and "MAP" in opts:
        ec._check_spec("SEND MAP", opts, (verb,))
        lines = [ec._name(opts["MAP"], "GG-NAME1"), ec._name(opts.get("MAPSET") or opts["MAP"], "GG-NAME2")]
        mapflags = [n for n, _v in pairs[1:] if n in ("ERASE", "ERASEAUP", "MAPONLY", "DATAONLY", "CURSOR",
                                                       "FREEKB", "ALARM", "FRSET", "PRINT")]  # fmt: skip
        lines.append(f"MOVE '{' '.join(mapflags)[:40]}' TO GG-FLAGS" if mapflags else "MOVE SPACES TO GG-FLAGS")
        lines.append(f"MOVE {opts.get('CURSOR') or '-1'} TO GG-LEN")  # #4001: CURSOR(n); -1: none given
        if "MAPONLY" in opts:
            args = ["BY REFERENCE GG-FLAGS", "BY VALUE 0"]
        else:
            src = opts.get("FROM") or (f"{ec._literal(opts['MAP'])}O" if ec._literal(opts["MAP"]) else None)
            if not src:
                raise ec.Unsupported("SEND MAP(data-name) without FROM")
            args = [f"BY REFERENCE {src}", f"BY VALUE {opts.get('LENGTH') or f'LENGTH OF {src}'}"]
        return lines + ec._call("GGCSMAP", args) + ec._map_abend(labels) + ec._resp(opts, can_fail=False)
    if verb == "SEND" and "CONTROL" in opts:  # #4413: device controls; CURSOR's value in GG-LEN, -1: none
        ec._check_spec("SEND CONTROL", opts, (verb, "CONTROL"), lambda bad: ["SEND CONTROL"])
        if "CURSOR" in opts and not opts["CURSOR"]:
            raise ec.Unsupported("SEND CONTROL CURSOR without a value", ["SEND CONTROL"])
        ctl = sorted(o for o in opts if o in ("ERASE", "ERASEAUP", "FREEKB", "ALARM", "FRSET", "CURSOR"))
        return ([f"MOVE '{' '.join(ctl)[:40]}' TO GG-FLAGS" if ctl else "MOVE SPACES TO GG-FLAGS",
                 f"MOVE {opts.get('CURSOR') or '-1'} TO GG-LEN"]
                + ec._call("GGCSCTL", []) + ec._resp(opts, can_fail=False))  # fmt: skip
    if verb == "SEND" and ("TEXT" in opts or "FROM" in opts) and "CONTROL" not in opts:
        src = opts.get("FROM")
        if not src:
            raise ec.Unsupported("SEND TEXT without FROM")
        # #4270 slice 4: TERMINAL, the default output disposition (the principal facility), changes nothing; the
        # full-BMS / printer / partition options are refused by name, as the det port refuses them (register X20)
        ec._check_spec(
            "SEND TEXT", opts, (verb, "TEXT")
        )  # (a deny-list until spec PR 3: an unknown option was ignored)
        kind = ["TEXT"] if "TEXT" in opts else ["DATA"]
        flags = [n for n, v in pairs[1:] if v is None and n not in ("NOHANDLE",)]
        textflags = " ".join(kind + [n for n in flags if n in ("ERASE", "FREEKB", "ALARM", "WAIT", "LAST")])
        return ([f"MOVE '{textflags[:40]}' TO GG-FLAGS"]
                + ec._call("GGCSTXT", [f"BY REFERENCE {src}", f"BY VALUE {opts.get('LENGTH') or f'LENGTH OF {src}'}"])
                + ec._resp(opts, can_fail=True))  # fmt: skip
    return None
