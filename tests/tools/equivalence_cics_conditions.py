"""#5274: the conditions family of the CICS harness's stub translator (equivalence_cics.translate), split out of
equivalence_cics.py: HANDLE CONDITION / IGNORE CONDITION / HANDLE ABEND / HANDLE AID / PUSH and POP HANDLE / ASSIGN
(#4003, #4007, #4270), the AID transfer after an input command (#4414) and the program-wide numbering of handler labels.
equivalence_cics's command dispatch calls these; they reach its shared helpers (the spec, `_call`, `_resp`, the
refusals) through the module at call time, so the import works either way round."""

from __future__ import annotations

import re

import equivalence_cics as ec
from gitgalaxy.standards.cics.commands.assign import TERMINAL_OPTIONS

# #4007: the keys HANDLE AID names (IBM, EXEC CICS HANDLE AID).
AID_KEYS = frozenset(["ANYKEY", "ENTER", "CLEAR", "CLRPARTN", "LIGHTPEN", "OPERID", "TRIGGER", "PA1", "PA2", "PA3"]
                     + [f"PF{n}" for n in range(1, 25)])  # fmt: skip


def aid(opts: dict[str, str | None], labels: list[str]) -> list[str]:
    """#4007: after an input command (RECEIVE MAP, terminal RECEIVE) that completed normally, HANDLE AID's
    label for the key pressed -- unless RESP or NOHANDLE suspends the handlers (IBM, RESP: "RESP implies
    NOHANDLE"; NOHANDLE: "no action is to be taken for any condition or attention identifier (AID)")."""
    if opts.get("RESP") or "NOHANDLE" in opts:
        return []
    return (["IF GG-RESP = 0", "    MOVE EIBAID TO GG-NAME1", "    CALL 'GGCAID' USING GG-CICS"]
            + [f"    {ln}" for ln in ec._transfer(labels)] + ["END-IF"])  # fmt: skip


def input_resp(opts: dict[str, str | None], labels: list[str], handle_aid: bool) -> list[str]:
    """#4414: an input command's outcome (_resp) and, in a program that issues HANDLE AID, its AID (aid). Which
    CICS acts on first when the command also raised a condition and a HANDLE AID label applies to the key is not
    documented: GGCAID, called first with the condition, records AID-REFUSED for the driver to refuse."""
    if not handle_aid:
        return ec._resp(opts, True, labels)
    first = ([] if opts.get("RESP") or "NOHANDLE" in opts
             else ["IF GG-RESP NOT = 0", "    MOVE EIBAID TO GG-NAME1", "    CALL 'GGCAID' USING GG-CICS", "END-IF"])  # fmt: skip
    return first + ec._resp(opts, True, labels) + aid(opts, labels)


# #4003: the commands whose options name the labels a program's handlers transfer to.
_HANDLE_KINDS = ("CONDITION", "ABEND", "AID")


def handler_labels(bodies: list[str]) -> list[str]:
    """Every label a program's HANDLE CONDITION / HANDLE ABEND LABEL / HANDLE AID names, in first-use
    order: GG-GOTO numbers them from 1."""
    out: list[str] = []
    for body in bodies:
        try:
            pairs = ec._options(body)
        except ec.Unsupported:
            continue
        if len(pairs) < 2 or pairs[0][0] != "HANDLE" or pairs[1][0] not in _HANDLE_KINDS:
            continue
        for opt, value in pairs[2:]:
            if value and not (pairs[1][0] == "ABEND" and opt != "LABEL"):
                label = value.upper()
                if label not in out:
                    out.append(label)
    return out


def handle(pairs: list[tuple[str, str | None]], labels: list[str]) -> list[str]:
    """#4003: HANDLE CONDITION / IGNORE CONDITION / HANDLE ABEND / PUSH / POP HANDLE / ASSIGN ABCODE."""
    verb, kind = pairs[0][0], pairs[1][0] if len(pairs) > 1 else None
    opts = dict(pairs)
    if verb in ("PUSH", "POP") and kind == "HANDLE":
        ec._check_spec(f"{verb} HANDLE", opts, (verb, "HANDLE"))
        return ec._call("GGCPUSH" if verb == "PUSH" else "GGCPOP", []) + ec._resp(opts, True, labels)
    if verb == "ASSIGN":  # ABCODE (#4003); APPLID / SYSID: the region's identity, from the case's "region";
        # PROGRAM: the name of the program running (IBM CICS TS, ASSIGN: "the name of the current program")
        asked = [(n, v) for n, v in pairs[1:] if n not in ("RESP", "RESP2", "NOHANDLE")]
        # #4270 slice 3: STARTCODE / USERID / FACILITY / SCRNHT / SCRNWD, from what the runner states (GGCASGN)
        ec._check_spec("ASSIGN", opts, ("ASSIGN",), lambda bad: [f"ASSIGN {n}" for n in bad])
        if not asked or not all(v for _n, v in asked):
            raise ec.Unsupported("ASSIGN without a target", ["ASSIGN ?"])
        lines: list[str] = []
        for n, target in asked:
            if n == "CHANNEL":  # #4270: the current channel's name, blanks without one (GGCASCH)
                lines += ec._call("GGCASCH", []) + [f"MOVE GG-CHAN TO {target}"]
                continue
            if n in ("SCRNHT", "SCRNWD"):  # a halfword, in GG-NUM
                lines += [f"MOVE '{n}' TO GG-NAME2"] + ec._call("GGCASGN", []) + [f"MOVE GG-NUM TO {target}"]
                continue
            width = ec.SPEC["ASSIGN"].options[n].width
            lines += ["MOVE SPACES TO GG-NAME2" if n == "ABCODE" else f"MOVE '{n[:8]}' TO GG-NAME2"] + ec._call(
                "GGCASGN", []
            )
            # IBM writes exactly `width` bytes and leaves the rest of a wider data area as it was (det: DetCics.put); a
            # plain MOVE would space-pad that tail (#4049), so the target is reference-modified to the width
            if re.search(r"\(\s*\d*\s*:", target):
                raise ec.Unsupported(f"ASSIGN {n}: a reference-modified target", [f"ASSIGN {n}"])
            lines.append(f"MOVE GG-NAME1(1:{width}) TO {target}(1:{width})")
        if not any(n in TERMINAL_OPTIONS for n, _v in asked):
            return lines + ec._resp(opts, False)
        # INVREQ RESP2 5 for a task with no terminal, and then no data area written (register X19)
        check = ["MOVE 'TERMCHK' TO GG-NAME2"] + ec._call("GGCASGN", [])
        return (check + ["IF GG-RESP = 0"] + [f"    {ln}" for ln in lines] + ["    MOVE 0 TO GG-RESP GG-RESP2", "END-IF"]
                + ec._resp(opts, True, labels))  # fmt: skip
    if verb == "HANDLE" and kind == "AID":  # #4007
        lines = []
        for key, label in pairs[2:]:
            if key not in AID_KEYS:
                raise ec.Unsupported(f"HANDLE AID {key}: not an attention key", ["HANDLE AID"])
            index = labels.index(label.upper()) + 1 if label else -1  # #4414: -1 deactivated (GGCAID)
            lines += [f"MOVE '{key}' TO GG-NAME1", f"MOVE {index} TO GG-ITEM"] + ec._call("GGCHAID", [])
        return lines
    if kind == "ABEND":
        if verb == "HANDLE":
            ec._check_spec("HANDLE ABEND", opts, ("HANDLE", "ABEND"))
        if "PROGRAM" in opts:
            raise ec._stub_only("HANDLE ABEND PROGRAM")
        label = opts.get("LABEL")
        if label:
            return ["MOVE 'LABEL' TO GG-NAME2", f"MOVE {labels.index(label.upper()) + 1} TO GG-ITEM",
                    f"MOVE '{label.upper()[:30]}' TO GG-FLAGS"] + ec._call("GGCHABN", [])  # fmt: skip
        return [f"MOVE '{'CANCEL' if 'CANCEL' in opts else 'RESET'}' TO GG-NAME2"] + ec._call("GGCHABN", [])
    lines: list[str] = []
    for cond, label in pairs[2:]:
        if cond not in ec.DFHRESP or cond == "NORMAL":
            raise ec.Unsupported(f"{verb} CONDITION {cond}: not a documented condition", [f"{verb} CONDITION"])
        if verb == "IGNORE" and cond == "ERROR":  # #4414: IBM does not say whether ERROR's action can be to ignore
            raise ec.Unsupported("IGNORE CONDITION ERROR: not documented", ["IGNORE CONDITION ERROR"])
        index = -1 if verb == "IGNORE" else (labels.index(label.upper()) + 1 if label else 0)
        lines += [f"MOVE {ec.DFHRESP[cond]} TO GG-NUM", f"MOVE {index} TO GG-ITEM"] + ec._call("GGCHCND", [])
    return lines


def command(
    verb: str,
    opts: dict[str, str | None],
    pairs: list[tuple[str, str | None]],
    labels: list[str],
    handle_aid: bool,
) -> list[str] | None:
    """The handler and ASSIGN commands, or None for a command of another family."""
    if (
        (verb in ("HANDLE", "IGNORE") and len(pairs) > 1 and pairs[1][0] in ("CONDITION", "ABEND", "AID"))
        or (verb in ("PUSH", "POP") and len(pairs) > 1 and pairs[1][0] == "HANDLE")
        or verb == "ASSIGN"
    ):
        return handle(pairs, labels)  # fmt: skip
    return None
