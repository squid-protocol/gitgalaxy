"""#5274: the named counter family of the CICS harness's stub translator (equivalence_cics.translate), split out of
equivalence_cics.py: GET / REWIND / UPDATE / QUERY / DEFINE / DELETE COUNTER and DCOUNTER (#4270, #4415, #4770, #5039).
The family registry in equivalence_cics calls `command`; it reaches the shared helpers through the module at call time,
so the import works either way round."""

from __future__ import annotations

import re

import equivalence_cics as ec


def _dcounter_areas(opts: dict[str, str | None], names: tuple[str, ...]) -> list[str]:
    """#4770 (X45): the doubleword areas of a DCOUNTER command as (area, length) pairs, `BY VALUE 0` for one the command omits;
    a literal is refused (the stub reads and writes the area's bytes: a data area is the COBOL form)."""
    out: list[str] = []
    for o in names:
        v = opts.get(o)
        if v and (ec._literal(v) or re.fullmatch(r"[+-]?\d+", v)):
            raise ec.Unsupported(f"DCOUNTER {o} as a literal: a data area is the COBOL form", ["DEFINE COUNTER"])
        out += [f"BY REFERENCE {v}", f"BY VALUE LENGTH OF {v}"] if v else ["BY REFERENCE GG-NAME2", "BY VALUE 0"]
    return out


def _counter_areas(
    opts: dict[str, str | None], names: tuple[str, ...], literals: tuple[str, ...] = ()
) -> tuple[list[str], list[str]]:
    """#5039 (X50): the fullword areas of a COUNTER command as (area, length) pairs, `BY VALUE 0` for one the command omits,
    with the lines that stage a numeric literal. A command that WRITES an area (QUERY) takes a data area only; DEFINE
    reads its VALUE / MINIMUM / MAXIMUM (`literals`), so a decimal literal is staged big-endian in GG-FLAGS (the stub reads
    the bytes as IBM's fullword binary), as before X50 gave it a literal VALUE through GG-NUM."""
    out: list[str] = []
    pre: list[str] = []
    for n, o in enumerate(names):
        v = opts.get(o)
        if v and (ec._literal(v) or re.fullmatch(r"[+-]?\d+", v)):
            if o not in literals or not re.fullmatch(r"[+-]?\d+", v):
                raise ec.Unsupported(f"COUNTER {o} as a literal: a data area is the COBOL form", ["DEFINE COUNTER"])
            slot = f"GG-FLAGS({4 * n + 1}:4)"
            pre.append(f"MOVE X'{int(v) & 0xFFFFFFFF:08X}' TO {slot}")
            v = slot
        out += [f"BY REFERENCE {v}", f"BY VALUE LENGTH OF {v}"] if v else ["BY REFERENCE GG-NAME2", "BY VALUE 0"]
    return pre, out


def command(
    verb: str,
    opts: dict[str, str | None],
    pairs: list[tuple[str, str | None]],
    labels: list[str],
    handle_aid: bool,
) -> list[str] | None:
    """The counter commands, or None for a command of another family."""
    if verb == "GET" and ("COUNTER" in opts or "DCOUNTER" in opts):  # a named counter (IBM CICS TS, GET COUNTER)
        ec._check_spec("GET COUNTER", opts, (verb,), lambda bad: ["GET COUNTER"])
        if not opts.get("VALUE"):
            raise ec.Unsupported(ec._rule("GET COUNTER", "required", "VALUE"), ["GET COUNTER"])
        if ("COUNTER" in opts) == ("DCOUNTER" in opts):
            raise ec.Unsupported(ec._rule("GET COUNTER", "one_of", "COUNTER"), ["GET COUNTER"])
        for o in ("VALUE", "INCREMENT", "COMPAREMIN", "COMPAREMAX"):
            # (#5039: a bound is read from its bytes, so a number written in place is no area either)
            if opts.get(o) and (
                ec._literal(opts[o]) or (o.startswith("COMPARE") and re.fullmatch(r"[+-]?\d+", opts[o]))
            ):
                kind = "DCOUNTER" if "DCOUNTER" in opts else "COUNTER"
                raise ec.Unsupported(f"{kind} {o} as a literal: a data area is the COBOL form", ["GET COUNTER"])
        full = "COUNTER" in opts  # #5039 (X50): the fullword form
        inc = opts.get("INCREMENT") or "GG-NAME2"
        head = ([ec._name(opts.get("COUNTER") or opts["DCOUNTER"], "GG-QNAME"), ec._name(opts.get("POOL") or "' '", "GG-NAME1")]
                + ([] if opts.get("INCREMENT") else ["MOVE X'0000000000000001' TO GG-NAME2"]))  # fmt: skip
        areas = [f"BY REFERENCE {opts['VALUE']}", f"BY VALUE LENGTH OF {opts['VALUE']}",
                 f"BY REFERENCE {inc}", f"BY VALUE LENGTH OF {inc}", f"BY VALUE {1 if 'WRAP' in opts else 0}"]  # fmt: skip
        if "REDUCE" in opts or opts.get("COMPAREMIN") or opts.get("COMPAREMAX"):
            # #5039 (X53): REDUCE and the bounds (an area each, length 0: not given)
            areas.append(f"BY VALUE {1 if 'REDUCE' in opts else 0}")
            for o in ("COMPAREMIN", "COMPAREMAX"):
                v = opts.get(o)
                areas += (
                    [f"BY REFERENCE {v}", f"BY VALUE LENGTH OF {v}"] if v else ["BY REFERENCE GG-NAME2", "BY VALUE 0"]
                )
            return head + ec._call("GGCGCNX" if full else "GGCGDCX", areas) + ec._resp(opts, True, labels)
        # #5039 (X50): GET COUNTER fullword form with INCREMENT and WRAP; #4767 (X30): GET DCOUNTER, the doubleword form: the stub
        # writes VALUE (8 bytes) and reads INCREMENT (an area; 1 when not given, through GG-NAME2's 8 bytes); #4770 (X45): WRAP
        # acts at DEFINE DCOUNTER's limits
        return head + ec._call("GGCGCNT" if full else "GGCGDCN", areas) + ec._resp(opts, True, labels)
    if verb in ("REWIND", "UPDATE") and {"COUNTER", "DCOUNTER"} & set(opts):  # #5039 (X53): REWIND / UPDATE COUNTER
        ec._check_spec(f"{verb} COUNTER", opts, (verb,), lambda bad: [f"{verb} COUNTER"])
        if ("COUNTER" in opts) == ("DCOUNTER" in opts):
            raise ec.Unsupported(ec._rule(f"{verb} COUNTER", "one_of", "COUNTER"), [f"{verb} COUNTER"])
        head = [
            ec._name(opts.get("COUNTER") or opts["DCOUNTER"], "GG-QNAME"),
            ec._name(opts.get("POOL") or "' '", "GG-NAME1"),
        ]
        full = "COUNTER" in opts
        o = "INCREMENT" if verb == "REWIND" else "VALUE"
        v = opts.get(o)
        if verb == "UPDATE" and not v:
            raise ec.Unsupported(ec._rule("UPDATE COUNTER", "required", "VALUE"), ["UPDATE COUNTER"])
        if v and (ec._literal(v) or re.fullmatch(r"[+-]?\d+", v)):
            raise ec.Unsupported(
                f"{'COUNTER' if full else 'DCOUNTER'} {o} as a literal: a data area is the COBOL form",
                [f"{verb} COUNTER"],
            )
        fn = {"REWIND": ("GGCRCNT", "GGCRDCN"), "UPDATE": ("GGCUCNT", "GGCUDCN")}[verb][0 if full else 1]
        areas = [f"BY REFERENCE {v}", f"BY VALUE LENGTH OF {v}"] if v else ["BY REFERENCE GG-NAME2", "BY VALUE 0"]
        return head + ec._call(fn, areas) + ec._resp(opts, True, labels)
    if verb == "QUERY" and (
        "COUNTER" in opts or "DCOUNTER" in opts
    ):  # #4415 slice 2 (X29): a named counter's value, unchanged
        ec._check_spec("QUERY COUNTER", opts, (verb,), lambda bad: ["QUERY COUNTER"])
        if not opts.get("VALUE"):
            raise ec.Unsupported(ec._rule("QUERY COUNTER", "required", "VALUE"), ["QUERY COUNTER"])
        if ("COUNTER" in opts) == ("DCOUNTER" in opts):
            raise ec.Unsupported(ec._rule("QUERY COUNTER", "one_of", "COUNTER"), ["QUERY COUNTER"])
        if "DCOUNTER" in opts:  # #4770 (X45): value and limits, unsigned doublewords in 8-byte areas
            return ([ec._name(opts["DCOUNTER"], "GG-QNAME"), ec._name(opts.get("POOL") or "' '", "GG-NAME1")]
                    + ec._call("GGCQDCN", _dcounter_areas(opts, ("VALUE", "MINIMUM", "MAXIMUM")))
                    + ec._resp(opts, True, labels))  # fmt: skip
        return ([ec._name(opts["COUNTER"], "GG-QNAME"), ec._name(opts.get("POOL") or "' '", "GG-NAME1")]
                + ec._call("GGCQCNT", _counter_areas(opts, ("VALUE", "MINIMUM", "MAXIMUM"))[1])
                + ec._resp(opts, True, labels))  # fmt: skip
    if verb in ("DEFINE", "DELETE") and (
        {"COUNTER", "DCOUNTER"} & set(opts)
    ):  # #4270 (X30): DEFINE / DELETE COUNTER -> GGCDCNT / GGCXCNT
        ec._check_spec(f"{verb} COUNTER", opts, (verb,), lambda bad: [f"{verb} COUNTER"])
        if ("COUNTER" in opts) == ("DCOUNTER" in opts):
            raise ec.Unsupported(ec._rule(f"{verb} COUNTER", "one_of", "COUNTER"), [f"{verb} COUNTER"])
        if verb == "DEFINE" and opts.get("MINIMUM") and not opts.get("VALUE"):
            why = next(
                g.msg for g in ec.SPEC["DEFINE COUNTER"].groups if g.kind == "requires" and "VALUE" in (g.any_of or ())
            )
            raise ec.Unsupported(why, ["DEFINE COUNTER"])
        head = [
            ec._name(opts.get("COUNTER") or opts["DCOUNTER"], "GG-QNAME"),
            ec._name(opts.get("POOL") or "' '", "GG-NAME1"),
        ]
        if verb == "DELETE":
            return head + ec._call("GGCXCNT", []) + ec._resp(opts, True, labels)
        if "DCOUNTER" in opts:  # #4770 (X45): VALUE / MINIMUM / MAXIMUM, each an 8-byte area (length 0: omitted)
            return (
                head
                + ec._call("GGCDDCN", _dcounter_areas(opts, ("VALUE", "MINIMUM", "MAXIMUM")))
                + ec._resp(opts, True, labels)
            )
        staged, areas = _counter_areas(opts, ("VALUE", "MINIMUM", "MAXIMUM"), ("VALUE", "MINIMUM", "MAXIMUM"))
        return head + staged + ec._call("GGCDCNT", areas) + ec._resp(opts, True, labels)
    return None
