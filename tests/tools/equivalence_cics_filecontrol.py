"""#5274: the file control family of the CICS harness's stub translator (equivalence_cics.translate), split out of
equivalence_cics.py: READ (incl. GTEQ / GENERIC / TOKEN / SET), WRITE, REWRITE, the browse (STARTBR, READNEXT, READPREV,
ENDBR, keyed or by RBA), DELETE (record, GENERIC, TOKEN, the held record) and UNLOCK. equivalence_cics's command dispatch
calls `file_command`; it reaches the shared helpers (the spec, `_call`, `_resp`, the refusals) through the module at call
time, so the import works either way round."""

from __future__ import annotations

import re

import equivalence_cics as ec

FILE_VERBS = frozenset({"READ", "WRITE", "REWRITE", "STARTBR", "READNEXT", "READPREV", "ENDBR", "DELETE", "UNLOCK"})


def _name(operand: str | None, into: str) -> str:
    return f"MOVE {operand} TO {into}" if operand else f"MOVE SPACES TO {into}"


def _set_target(key: str, setp: str) -> tuple[str, list[str]]:
    """#5079 (X58): the pointer a locate-mode file command hands to the stub, and what follows a delivered record.
    SET(ptr): the pointer itself, nothing after. SET(ADDRESS OF rec): GG-PTR, then `SET ADDRESS OF rec TO GG-PTR` --
    the caller runs it only when a record came (NORMAL, or DUPKEY for READ), so the address stays as it was otherwise."""
    m = re.fullmatch(r"(?is)\s*ADDRESS\s+OF\s+([A-Z][A-Z0-9-]*)\s*", setp or "")
    if m is None:
        return ec._pointer(key, setp), []
    return "GG-PTR", [f"SET ADDRESS OF {m.group(1)} TO GG-PTR"]


def file_command(verb: str, opts: dict[str, str | None], labels: list[str] | None) -> list[str] | None:
    """One file control command -> the COBOL statements that replace it; None when `verb` with these options is not a
    file control command (a DELETE with no FILE, say), for the caller to go on."""
    if verb == "READ":
        ec._check_spec("READ", opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        for bad in ("RBA", "XRBA", "RRN"):
            if bad in opts:
                raise ec._stub_only(f"READ {bad}")
        file, into, ridfld = opts.get("FILE") or opts.get("DATASET"), opts.get("INTO"), opts.get("RIDFLD")
        setp = opts.get("SET")  # #5042 (X58): SET(pointer) -> GGCRDST, the record as a new block
        if "SET" in opts and into:
            raise ec.Unsupported(ec._rule("READ", "one_of", "INTO"), ["READ"])
        if not (file and (into or setp) and ridfld):
            raise ec.Unsupported("READ without FILE / INTO / RIDFLD")
        keylen = opts.get("KEYLENGTH") or f"LENGTH OF {ridfld}"
        # #4270 GTEQ / GENERIC (X22): a search, the generic key KEYLENGTH long; the option rules as the translator's
        if "GTEQ" in opts and "EQUAL" in opts:
            raise ec.Unsupported(ec._rule("READ", "at_most_one", "EQUAL", "EQUAL", "GTEQ"), ["READ GTEQ"])
        if "GENERIC" in opts and "KEYLENGTH" not in opts:
            raise ec.Unsupported(ec._rule("READ", "requires", "GENERIC"), ["READ GENERIC"])
        # UPDATE holds the record; TOKEN (#5078, X52) implies it and holds it under a token of its own, GG-NUM out
        words = [w for w in ("UPDATE", "TOKEN", "GTEQ", "GENERIC") if w in opts or (w == "UPDATE" and "TOKEN" in opts)]
        if (
            "KEYLENGTH" in opts and "GENERIC" not in opts
        ):  # #5092 (X52): given, so INVREQ 26 unless it is the key's length
            words.append("KEYLENGTH")
        if "TOKEN" in opts and not opts["TOKEN"]:
            raise ec.Unsupported("READ TOKEN needs a data area", ["READ TOKEN"])
        update = f"MOVE '{' '.join(words)}' TO GG-FLAGS" if words else "MOVE SPACES TO GG-FLAGS"
        # #4436: LENGTH is in-out (IBM, EXEC CICS READ): in, the most INTO takes (a longer record is truncated, with
        # LENGERR); out, the record's length, on NORMAL and LENGERR. Without it, LENGTH OF INTO (as the translator
        # supplies it). A literal / LENGTH OF is set in a temporary no one reads.
        length = opts.get("LENGTH")
        settable = bool(length) and re.fullmatch(r"(?is)\d+|LENGTH\s+OF\s+.+", length.strip()) is None
        after = ["IF GG-RESP = 0 OR GG-RESP = 22", f"    MOVE GG-LEN TO {length}", "END-IF"] if settable else []
        if "TOKEN" in opts:
            after += ["IF GG-RESP = 0", f"    MOVE GG-NUM TO {opts['TOKEN']}", "END-IF"]
        if setp:  # (LENGTH(data-area) is set to the record's length, on NORMAL and DUPKEY, as the translator's)
            if length and not settable:
                raise ec.Unsupported("READ SET with a literal LENGTH: only a data area is modelled", ["READ SET"])
            target, locate = _set_target("READ", setp)
            after = (
                [
                    "IF GG-RESP = 0 OR GG-RESP = 15",
                    *(f"    {x}" for x in locate),
                    *([f"    MOVE GG-LEN TO {length}"] if length else []),
                    "END-IF",
                ]
                if (length or locate)
                else []
            )
            if "TOKEN" in opts:
                after += ["IF GG-RESP = 0", f"    MOVE GG-NUM TO {opts['TOKEN']}", "END-IF"]
            return ([_name(file, "GG-NAME1"), update, "MOVE 0 TO GG-LEN"]
                    + ec._call("GGCRDST", [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}", f"BY REFERENCE {target}"])
                    + after + ec._resp(opts, True, labels))  # fmt: skip
        return ([_name(file, "GG-NAME1"), update, f"MOVE {length or f'LENGTH OF {into}'} TO GG-LEN"]
                + ec._call("GGCREAD", [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}", f"BY REFERENCE {into}",
                                    f"BY VALUE LENGTH OF {into}"])
                + after + ec._resp(opts, True, labels))  # fmt: skip
    if verb == "WRITE" and {"FILE", "DATASET"} & set(opts):
        ec._check_spec("WRITE", opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        for bad in ("RBA", "XRBA", "RRN"):
            if bad in opts:
                raise ec._stub_only(f"WRITE {bad}")
        file, frm, ridfld = opts.get("FILE") or opts.get("DATASET"), opts.get("FROM"), opts.get("RIDFLD")
        if not (file and frm and ridfld):
            raise ec.Unsupported("WRITE without FILE / FROM / RIDFLD")
        keylen = opts.get("KEYLENGTH") or f"LENGTH OF {ridfld}"
        return ([_name(file, "GG-NAME1")]
                + ec._call("GGCWRIT", [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}", f"BY REFERENCE {frm}",
                                    f"BY VALUE {opts.get('LENGTH') or f'LENGTH OF {frm}'}"])
                + ec._resp(opts, True, labels))  # fmt: skip
    if verb == "REWRITE" and ({"FILE", "DATASET"} & set(opts)):
        ec._check_spec("REWRITE", opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        file, frm = opts.get("FILE") or opts.get("DATASET"), opts.get("FROM")
        if not (file and frm):
            raise ec.Unsupported("REWRITE without FILE / FROM")
        length = opts.get("LENGTH") or f"LENGTH OF {frm}"  # LENGTH bytes from FROM's first, as CICS reads them
        if "TOKEN" in opts:  # #5078 (X52): the record the READ UPDATE TOKEN holds (GG-NUM in)
            if not opts["TOKEN"]:
                raise ec.Unsupported("REWRITE TOKEN needs a value", ["REWRITE TOKEN"])
            return ([_name(file, "GG-NAME1"), "MOVE 'TOKEN' TO GG-FLAGS", f"MOVE {opts['TOKEN']} TO GG-NUM"]
                    + ec._call("GGCREWR", [f"BY REFERENCE {frm}", f"BY VALUE {length}"]) + ec._resp(opts, True, labels))  # fmt: skip
        return ([_name(file, "GG-NAME1"), "MOVE SPACES TO GG-FLAGS"] + ec._call("GGCREWR", [f"BY REFERENCE {frm}", f"BY VALUE {length}"])
                + ec._resp(opts, True, labels))  # fmt: skip
    if verb == "STARTBR":  # browse (CardDemo's lists): one browse per file, full keys -- or an ESDS's RBAs (#4213)
        rba = "RBA" in opts
        ec._check_spec("STARTBR", opts, (verb,), lambda bad: [f"STARTBR {'RBA ' if rba else ''}{bad[0]}"])
        for bad in ("RRN", "XRBA") + (("GTEQ", "KEYLENGTH") if rba else ()):
            if bad in opts:
                raise ec._stub_only(f"STARTBR {'RBA ' if rba else ''}{bad}")
        file, ridfld = opts.get("FILE") or opts.get("DATASET"), opts.get("RIDFLD")
        if not (file and ridfld):
            raise ec.Unsupported("STARTBR without FILE / RIDFLD")
        keylen = opts.get("KEYLENGTH") or f"LENGTH OF {ridfld}"
        # GTEQ is a keyed browse's default; EQUAL "is the default for a direct ESDS browse" (IBM, STARTBR), and GTEQ
        # "is not valid for directly browsing an ESDS"
        mode = ("MOVE 'EQUAL RBA' TO GG-FLAGS" if rba else
                "MOVE 'EQUAL' TO GG-FLAGS" if "EQUAL" in opts else "MOVE SPACES TO GG-FLAGS")  # fmt: skip
        return ([_name(file, "GG-NAME1"), mode] + ec._call("GGCSTBR", [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}"])
                + ec._resp(opts, True, labels))  # fmt: skip
    if verb in ("READNEXT", "READPREV"):
        rba = "RBA" in opts  # #4213: every READNEXT / READPREV of an RBA browse says RBA too
        ec._check_spec(verb, opts, (verb,), lambda bad: [f"{verb} {'RBA ' if rba else ''}{bad[0]}"])
        for bad in ("RRN", "XRBA") + (("KEYLENGTH",) if rba else ()):
            if bad in opts:
                raise ec._stub_only(f"{verb} {'RBA ' if rba else ''}{bad}")
        file, into, ridfld = opts.get("FILE") or opts.get("DATASET"), opts.get("INTO"), opts.get("RIDFLD")
        setp = opts.get("SET")  # #5042 (X58): SET(pointer) -> GGCRDNS / GGCRDPS, the record as a new block
        if "SET" in opts and (into or rba or opts.get("LENGTH")):
            raise ec.Unsupported(f"{verb} SET with INTO, RBA or LENGTH: not modelled", [f"{verb} SET"])
        if not (file and (into or setp) and ridfld):
            raise ec.Unsupported(f"{verb} without FILE / INTO / RIDFLD")
        keylen = opts.get("KEYLENGTH") or f"LENGTH OF {ridfld}"
        if setp:
            stub = "GGCRDNS" if verb == "READNEXT" else "GGCRDPS"
            target, locate = _set_target(verb, setp)
            after = ["IF GG-RESP = 0", *(f"    {x}" for x in locate), "END-IF"] if locate else []
            return ([_name(file, "GG-NAME1"), "MOVE SPACES TO GG-FLAGS"]
                    + ec._call(stub, [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}", f"BY REFERENCE {target}"])
                    + after + ec._resp(opts, True, labels))  # fmt: skip
        stub = "GGCRDNX" if verb == "READNEXT" else "GGCRDPV"
        return ([_name(file, "GG-NAME1"), "MOVE 'RBA' TO GG-FLAGS" if rba else "MOVE SPACES TO GG-FLAGS"]
                + ec._call(stub, [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}", f"BY REFERENCE {into}",
                               f"BY VALUE LENGTH OF {into}"])
                + ec._resp(opts, True, labels))  # fmt: skip
    if verb == "ENDBR":
        ec._check_spec("ENDBR", opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        file = opts.get("FILE") or opts.get("DATASET")
        if not file:
            raise ec.Unsupported("ENDBR without FILE")
        return [_name(file, "GG-NAME1")] + ec._call("GGCENBR", []) + ec._resp(opts, True, labels)
    if verb == "DELETE" and ({"FILE", "DATASET"} & set(opts)):
        ec._check_spec("DELETE", opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        for bad in ("RBA", "XRBA", "RRN"):
            if bad in opts:
                raise ec._stub_only(f"DELETE {bad}")
        file, ridfld = opts.get("FILE") or opts.get("DATASET"), opts.get("RIDFLD")
        if "TOKEN" in opts and "GENERIC" in opts:  # #5078 (X52)
            raise ec.Unsupported(ec._rule("DELETE", "at_most_one", "GENERIC", "GENERIC", "TOKEN"), ["DELETE TOKEN"])
        if "GENERIC" in opts:  # #4771 (X22): every record with the generic key, KEYLENGTH long
            for o in ("KEYLENGTH", "RIDFLD"):
                if not opts.get(o):
                    raise ec.Unsupported(
                        next(g.msg for g in ec.SPEC["DELETE"].groups if o in g.any_of), ["DELETE GENERIC"]
                    )
            args = [f"BY REFERENCE {ridfld}", f"BY VALUE {opts['KEYLENGTH']}"]
            return ([_name(file, "GG-NAME1"), "MOVE 'GENERIC' TO GG-FLAGS"] + ec._call("GGCDELT", args)
                    + ec._resp(opts, True, labels))  # fmt: skip
        if "TOKEN" in opts:  # #5078 (X52): the record the READ UPDATE TOKEN holds, no RIDFLD
            if ridfld:
                raise ec.Unsupported(ec._rule("DELETE", "at_most_one", "RIDFLD", "RIDFLD", "TOKEN"), ["DELETE TOKEN"])
            if not opts["TOKEN"]:
                raise ec.Unsupported("DELETE TOKEN needs a value", ["DELETE TOKEN"])
            return ([_name(file, "GG-NAME1"), "MOVE 'TOKEN' TO GG-FLAGS", f"MOVE {opts['TOKEN']} TO GG-NUM"]
                    + ec._call("GGCDELT", ["BY REFERENCE GG-FLAGS", "BY VALUE 0"]) + ec._resp(opts, True, labels))  # fmt: skip
        if ridfld:  # the record with that key
            keylen = opts.get("KEYLENGTH") or f"LENGTH OF {ridfld}"
            args = [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}"]
            # #5092 (X22): a given KEYLENGTH is INVREQ 26 unless it is the key's length, as READ's (GG-FLAGS KEYLENGTH)
            mode = "MOVE 'KEYLENGTH' TO GG-FLAGS" if opts.get("KEYLENGTH") else "MOVE SPACES TO GG-FLAGS"
        else:  # the record a READ UPDATE holds
            args, mode = ["BY REFERENCE GG-FLAGS", "BY VALUE 0"], "MOVE 'HELD' TO GG-FLAGS"
        return [_name(file, "GG-NAME1"), mode] + ec._call("GGCDELT", args) + ec._resp(opts, True, labels)
    if verb == "UNLOCK" and ({"FILE", "DATASET"} & set(opts)):  # #5078 (X52): UNLOCK TOKEN -> GGCUNLK (GG-NUM in)
        ec._check_spec("UNLOCK", opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        file = opts.get("FILE") or opts.get("DATASET")
        token = (
            [f"MOVE {opts['TOKEN']} TO GG-NUM", "MOVE 'TOKEN' TO GG-FLAGS"]
            if opts.get("TOKEN")
            else ["MOVE SPACES TO GG-FLAGS"]
        )
        return (
            [_name(file, "GG-NAME1"), *token] + ec._call("GGCUNLK", []) + ec._resp(opts, True, labels)
        )  # #5079: no TOKEN, the file's hold
    return None
