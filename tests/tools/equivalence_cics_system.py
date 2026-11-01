"""#5274: the remaining services of the CICS harness's stub translator (equivalence_cics.translate), split out of
equivalence_cics.py: ENQ / DEQ, ASKTIME, FORMATTIME, SYNCPOINT, BIF DEEDIT, DOCUMENT, VERIFY, WRITE OPERATOR, INQUIRE
PROGRAM / ASSOCIATION / URIMAP and the harness's own Db2 abend marker. The family registry in equivalence_cics calls
`command`; it reaches the shared helpers through the module at call time, so the import works either way round."""

from __future__ import annotations


import equivalence_cics_faults as cics_faults
import equivalence_cics as ec


# FORMATTIME's date forms (IBM CICS TS, EXEC CICS FORMATTIME): the parts in order, and the separator's default
_DATE_FORMS = {"YYYYMMDD": ("GG-Y", "GG-M", "GG-D"), "MMDDYYYY": ("GG-M", "GG-D", "GG-Y"),
               "DDMMYYYY": ("GG-D", "GG-M", "GG-Y"), "YYMMDD": ("GG-Y(3:2)", "GG-M", "GG-D"),
               "MMDDYY": ("GG-M", "GG-D", "GG-Y(3:2)"), "DDMMYY": ("GG-D", "GG-M", "GG-Y(3:2)"),
               "YYDDD": ("GG-Y(3:2)", "GG-DOY"), "YYYYDDD": ("GG-Y", "GG-DOY"),
               "YYDDMM": ("GG-Y(3:2)", "GG-D", "GG-M"), "YYYYDDMM": ("GG-Y", "GG-D", "GG-M")}  # fmt: skip
# #4415 slice 3 (X46): the binary forms, each the COBOL expression of IBM's value (DAYCOUNT: 1 January 1900 is day 1;
# DAYOFWEEK: Sunday=0; GG-DAYS 0 is a Monday)
_NUMBER_FORMS = {"DAYCOUNT": "GG-DAYS + 1", "DAYOFMONTH": "GG-D", "DAYOFWEEK": "FUNCTION MOD(GG-DAYS + 1, 7)",
                 "MONTHOFYEAR": "GG-M", "YEAR": "GG-Y", "MILLISECONDS": "FUNCTION MOD({t}, 1000)"}  # fmt: skip


def _formattime(opts: dict[str, str]) -> list[str]:
    """FORMATTIME ABSTIME(t) [date forms] [DATESEP] [TIME] [TIMESEP], in COBOL: t split into the day number since
    1900-01-01 and the milliseconds into the day. DATESEP / TIMESEP without a value are '/' and ':'; absent, none."""
    ec._check_spec("FORMATTIME", opts, ("FORMATTIME",), lambda bad: ["FORMATTIME"])
    if not opts.get("ABSTIME"):
        raise ec.Unsupported("FORMATTIME without ABSTIME", ["FORMATTIME"])
    t = opts["ABSTIME"]
    lines = [f"COMPUTE GG-DAYS = {t} / 86400000", f"COMPUTE GG-REM = {t} - GG-DAYS * 86400000",
             "COMPUTE GG-DATE8 = FUNCTION DATE-OF-INTEGER(GG-DAYS",
             "    + FUNCTION INTEGER-OF-DATE(19000101))",
             "COMPUTE GG-DOY = FUNCTION INTEGER-OF-DATE(GG-DATE8)",
             "    - FUNCTION INTEGER-OF-DATE(GG-Y * 10000 + 101) + 1",
             "COMPUTE GG-HH = GG-REM / 3600000", "COMPUTE GG-MI = (GG-REM - GG-HH * 3600000) / 60000",
             "COMPUTE GG-SS = (GG-REM - GG-HH * 3600000", "    - GG-MI * 60000) / 1000"]  # fmt: skip

    def sep(option: str, default: str) -> str | None:
        if option not in opts:
            return None
        return opts[option] or f"'{default}'"

    def build(parts: tuple[str, ...], separator: str | None, target: str) -> list[str]:
        pieces = []
        for i, p in enumerate(parts):
            if i and separator:
                pieces.append(separator)
            pieces.append(p)
        width = sum({"GG-Y": 4, "GG-DOY": 3}.get(p, 2) for p in parts) + (len(parts) - 1 if separator else 0)
        return (["MOVE SPACES TO GG-OUT", "STRING " + " ".join(pieces), "    DELIMITED BY SIZE INTO GG-OUT"]
                + [f"MOVE GG-OUT(1:{width}) TO {target}(1:{width})"])  # fmt: skip

    body: list[str] = []
    for form, parts in _DATE_FORMS.items():
        if opts.get(form):
            body += build(parts, sep("DATESEP", "/"), opts[form])
    for form, expr in _NUMBER_FORMS.items():
        if opts.get(form):
            body += [f"COMPUTE {opts[form]} = {expr.format(t=t)}"]
    if opts.get("TIME"):
        body += build(("GG-HH", "GG-MI", "GG-SS"), sep("TIMESEP", ":"), opts["TIME"])
    # #4737 (X28): IBM, INVREQ RESP2 1 "The ABSTIME value is less than zero or not in packed-decimal format": with RESP /
    # RESP2 nothing is formatted and the condition is the program's; without them INVREQ's handling is not modelled
    # (refused, as CicsTask refuses it)
    if not opts.get("RESP") and not opts.get("RESP2"):
        return [f"IF {t} < 0", "    DISPLAY 'FORMATTIME ABSTIME < 0 NO RESP: not modelled'",
                "    MOVE 98 TO RETURN-CODE", "    STOP RUN", "END-IF"] + lines + body  # fmt: skip
    return (["MOVE 0 TO GG-RESP", "MOVE 0 TO GG-RESP2", f"IF {t} < 0", "    MOVE 16 TO GG-RESP",
             "    MOVE 1 TO GG-RESP2", "ELSE"] + [f"    {ln}" for ln in lines + body] + ["END-IF"])  # fmt: skip


def command(
    verb: str,
    opts: dict[str, str | None],
    pairs: list[tuple[str, str | None]],
    labels: list[str],
    handle_aid: bool,
) -> list[str] | None:
    """The system service commands, or None for a command of another family."""
    if verb == "GGSQLAB":  # #6271 (X73): the harness's own marker after a Db2 statement planned to abend AD2Z
        return [
            "MOVE 0 TO GG-GOTO",
            f"MOVE {opts['NAME']} TO GG-FLAGS",
            *ec._call("GGCSQLAB", []),
            *ec._map_abend(labels),
        ]
    if verb in ("ENQ", "DEQ"):
        # one task in the region: nothing else holds the resource (ENQ / DEQ NORMAL), and a task takes no time
        # (EIBTIME / ASKTIME stay as dispatched; oracle_assumptions.md X4)
        ec._check_spec(verb, opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        if verb == "ENQ":  # #5089: GGCENQ -- NORMAL, or the ENQBUSY a scenario plans (faults, name = the RESOURCE text)
            key = cics_faults.enq_fault_key(opts.get("RESOURCE"))
            flag = "MOVE 'NOSUSPEND' TO GG-NAME1" if "NOSUSPEND" in opts else "MOVE SPACES TO GG-NAME1"
            given = ("L" if opts.get("LENGTH") else "") + ("M" if opts.get("MAXLIFETIME") else "")  # X60: GG-NAME2
            ops = [f"MOVE {opts['LENGTH']} TO GG-LEN"] if opts.get("LENGTH") else []
            ops += [f"MOVE {opts['MAXLIFETIME']} TO GG-NUM"] if opts.get("MAXLIFETIME") else []
            ops.append(f"MOVE '{given}' TO GG-NAME2" if given else "MOVE SPACES TO GG-NAME2")
            return [f"MOVE '{key}' TO GG-FLAGS", flag, *ops] + ec._call("GGCENQ", []) + ec._resp(opts, True, labels)
        return ["MOVE 0 TO GG-RESP", "MOVE 0 TO GG-RESP2"] + ec._resp(opts, False, labels)
    if verb == "ASKTIME":  # the task's clock; a task takes no time, so EIBDATE / EIBTIME stay as dispatched
        ec._check_spec("ASKTIME", opts, (verb,))
        if not opts.get("ABSTIME"):
            return ["CONTINUE"]
        return ["MOVE FUNCTION CURRENT-DATE(1:8) TO GG-YMD", "MOVE FUNCTION CURRENT-DATE(9:8) TO GG-HMSC",
                f"COMPUTE {opts['ABSTIME']} =", "    (FUNCTION INTEGER-OF-DATE(GG-DATE8)",
                "    - FUNCTION INTEGER-OF-DATE(19000101)) * 86400000",
                "    + GG-HH * 3600000 + GG-MI * 60000", "    + GG-SS * 1000 + GG-CS * 10"]  # fmt: skip
    if verb == "FORMATTIME":
        out = _formattime(opts)
        return out + ec._resp(opts, True, labels) if opts.get("RESP") or opts.get("RESP2") else out
    if verb == "SYNCPOINT":
        ec._check_spec("SYNCPOINT", opts, (verb,))
        mode = "MOVE 'ROLLBACK' TO GG-FLAGS" if "ROLLBACK" in opts else "MOVE SPACES TO GG-FLAGS"
        return [mode] + ec._call("GGCSYNC", []) + ec._resp(opts, False, labels)
    if verb == "INQUIRE" and "PROGRAM" in opts:  # #4023 follow-up: is the program installed (COMEN01C's option check)
        ec._check_spec("INQUIRE PROGRAM", opts, (verb,), lambda bad: ["INQUIRE PROGRAM"])
        if not opts["PROGRAM"]:
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, ["INQUIRE PROGRAM"])
        if "STATUS" in opts and not opts["STATUS"]:
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, ["INQUIRE PROGRAM"])
        status = (["IF GG-RESP = 0", f"    MOVE GG-NUM TO {opts['STATUS']}", "END-IF"]
                  if opts.get("STATUS") else [])  # #4768 (X34): the definition's CVDA, on NORMAL only  # fmt: skip
        return [ec._name(opts["PROGRAM"], "GG-NAME1")] + ec._call("GGCINQP", []) + status + ec._resp(opts, True, labels)
    if verb == "BIF" and "DEEDIT" in opts:  # #4415 slice 1 (X26): FIELD edited in place, in the region's EBCDIC page
        ec._check_spec("BIF DEEDIT", opts, ("BIF", "DEEDIT"), lambda bad: ["BIF DEEDIT"])
        if not opts.get("FIELD"):
            raise ec.Unsupported(ec._rule("BIF DEEDIT", "required", "FIELD"), ["BIF DEEDIT"])
        field = opts["FIELD"]
        return ([f"MOVE {opts.get('LENGTH') or f'LENGTH OF {field}'} TO GG-NUM"]
                + ec._call("GGCDEED", [f"BY REFERENCE {field}", f"BY VALUE LENGTH OF {field}"])
                + ec._resp(opts, True, labels))  # fmt: skip
    if verb == "INQUIRE" and "ASSOCIATION" in opts:  # #4415 slice 2 (X29): the task's own origin data
        ec._check_spec("INQUIRE ASSOCIATION", opts, (verb,), lambda bad: ["INQUIRE ASSOCIATION"])
        if not opts["ASSOCIATION"] or opts["ASSOCIATION"].strip().upper() != "EIBTASKN":
            raise ec.Unsupported(
                f"INQUIRE ASSOCIATION({opts['ASSOCIATION']}): only the task's own number, EIBTASKN, is "
                "modelled (IBM gives no representation for the 4 bytes)",
                ["INQUIRE ASSOCIATION"],
            )
        wanted = [o for o in ("ODAPPLID", "ODUSERID", "ODFACILNAME", "ODNETWORKID", "ODFACILTYPE") if opts.get(o)]
        if not wanted:  # IBM's INVREQ RESP2 2 ("specified with no arguments") is ambiguous about ASSOCIATION alone
            raise ec.Unsupported(
                "INQUIRE ASSOCIATION without an origin option: IBM's INVREQ RESP2 2 does not say whether "
                "ASSOCIATION alone is none: not modelled",
                ["INQUIRE ASSOCIATION"],
            )
        lines = []
        for o in wanted:
            lines += [f"MOVE '{o}' TO GG-FLAGS"] + ec._call("GGCINQA", [])
            lines.append(f"MOVE GG-NUM TO {opts[o]}" if o == "ODFACILTYPE" else f"MOVE GG-NAME1 TO {opts[o]}")
        return lines + ec._resp(opts, False, labels)
    if verb == "DOCUMENT" and ({"CREATE", "RETRIEVE"} & set(opts)):  # #4769 zECS (X33): the document handler
        form = "CREATE" if "CREATE" in opts else "RETRIEVE"
        key = f"DOCUMENT {form}"
        ec._check_spec(key, opts, (verb, form), lambda bad: [f"{key} {o}" for o in bad])
        tok = opts.get("DOCTOKEN")
        if not tok:
            raise ec.Unsupported(ec._rule(key, "required", "DOCTOKEN"), [key])
        for o in ("DOCTOKEN", "TEXT", "BINARY", "INTO"):  # (IBM's COBOL form takes a data area)
            if opts.get(o) and ec._literal(opts[o]):
                raise ec.Unsupported(f"{key} {o} as a literal: a data area is the COBOL form", [key])
        tokarg = [f"BY REFERENCE {tok}", f"BY VALUE LENGTH OF {tok}"]
        if form == "CREATE":
            given = [o for o in ("TEXT", "BINARY", "TEMPLATE") if o in opts]
            if len(given) > 1:
                raise ec.Unsupported(ec._rule(key, "at_most_one", "TEXT"), [key])
            for o in ("TEXT", "BINARY"):
                if o in opts and "LENGTH" not in opts:
                    raise ec.Unsupported(ec._rule(key, "requires", "TEXT"), [key])
            if "LENGTH" in opts and not ({"TEXT", "BINARY"} & set(opts)):
                raise ec.Unsupported(ec._rule(key, "requires", "LENGTH"), [key])
            if "TEXT" in opts or "BINARY" in opts:
                area = opts["TEXT"] if "TEXT" in opts else opts["BINARY"]
                lines = [f"MOVE {opts['LENGTH']} TO GG-LEN", "MOVE 'DATA' TO GG-FLAGS"]
                src = [f"BY REFERENCE {area}", f"BY VALUE LENGTH OF {area}"]
            elif "TEMPLATE" in opts:
                t = opts["TEMPLATE"]
                lit = ec._literal(t)
                lines = ["MOVE 'TEMPLATE' TO GG-FLAGS"]
                src = [f"BY REFERENCE {t}", f"BY VALUE {len(lit) if lit is not None else f'LENGTH OF {t}'}"]
            else:
                lines = ["MOVE 'EMPTY' TO GG-FLAGS"]
                src = tokarg[:1] + ["BY VALUE 0"]
            return lines + ec._call("GGCDOCC", src + tokarg) + ec._resp(opts, True, labels)
        for o in ("INTO", "MAXLENGTH", "DATAONLY"):
            if o not in opts:
                raise ec.Unsupported(ec._rule(key, "required", o), [key])
        after = []
        if opts.get("LENGTH"):  # (LENGTH is set on NORMAL and on the truncating LENGERR, RESP2 2, only)
            after = ["IF GG-RESP = 0 OR (GG-RESP = 22 AND GG-RESP2 = 2)", f"    MOVE GG-LEN TO {opts['LENGTH']}",
                     "END-IF"]  # fmt: skip
        return ([f"MOVE {opts['MAXLENGTH']} TO GG-LEN"]
                + ec._call("GGCDOCR", tokarg + [f"BY REFERENCE {opts['INTO']}", f"BY VALUE LENGTH OF {opts['INTO']}"])
                + after + ec._resp(opts, True, labels))  # fmt: skip
    if verb == "INQUIRE" and "URIMAP" in opts:  # #4270 zECS (X32): the browse of the installed URIMAP definitions
        ec._check_spec("INQUIRE URIMAP", opts, (verb,), lambda bad: [f"INQUIRE URIMAP {o}" for o in bad])
        form = [f for f in ("START", "NEXT", "END") if f in opts]
        if len(form) > 1:
            raise ec.Unsupported(ec._rule("INQUIRE URIMAP", "at_most_one", "START"), ["INQUIRE URIMAP"])
        if not form:  # #4768 (X34): the direct form, URIMAP(name) -- NOTFND RESP2 3 when it is not installed
            if not opts.get("URIMAP"):
                raise ec.Unsupported(ec._rule("INQUIRE URIMAP", "required", "URIMAP"), ["INQUIRE URIMAP"])
            outs = [o for o in ("PATH", "TRANSACTION") if opts.get(o)]
            lines = [ec._name(opts["URIMAP"], "GG-NAME1"), "MOVE 'DIRECT' TO GG-FLAGS"] + ec._call("GGCURIB", [])
        else:
            outs = [o for o in ("URIMAP", "PATH", "TRANSACTION") if opts.get(o)]
            if form[0] != "NEXT" and outs:
                raise ec.Unsupported(f"INQUIRE URIMAP {form[0]} {outs[0]}: a browse {form[0]} returns no definition",
                                  ["INQUIRE URIMAP"])  # fmt: skip
            lines = [f"MOVE '{form[0]}' TO GG-FLAGS"] + ec._call("GGCURIB", [])
        if outs:
            lines.append("IF GG-RESP = 0")
            for o in outs:
                lines += [f"    MOVE '{o}' TO GG-FLAGS"] + [
                    f"    {ln}"
                    for ln in ec._call("GGCURIP", [f"BY REFERENCE {opts[o]}", f"BY VALUE LENGTH OF {opts[o]}"])
                ]
            lines.append("END-IF")
        return lines + ec._resp(opts, True, labels)
    # #5859 (X32): GGCVER -- the verdict a scenario states for the USERID
    if verb == "VERIFY" and not ({"PHRASE", "TOKEN"} & set(opts)):
        ec._check_spec("VERIFY PASSWORD", opts, (verb,), lambda bad: [f"VERIFY PASSWORD {bad[0]}"])
        for need in ("USERID", "PASSWORD"):
            if not opts.get(need):
                raise ec.Unsupported(f"VERIFY PASSWORD without {need}", ["VERIFY PASSWORD"])
        user = opts["USERID"]
        return (ec._call("GGCVER", [f"BY REFERENCE {user}", f"BY VALUE LENGTH OF {user}"])
                + ec._resp(opts, True, labels))  # fmt: skip
    if verb == "VERIFY":
        raise ec._stub_only("VERIFY PHRASE / VERIFY TOKEN")
    if verb == "WRITE" and "OPERATOR" in opts:  # #4270 zECS (X32): a plain message to the console
        ec._check_spec("WRITE OPERATOR", opts, (verb, "OPERATOR"))
        text = opts.get("TEXT")
        if not text:
            raise ec.Unsupported(ec._rule("WRITE OPERATOR", "required", "TEXT"), ["WRITE OPERATOR"])
        if ec._literal(text):  # (IBM's COBOL form takes a data area)
            raise ec.Unsupported("WRITE OPERATOR TEXT as a literal: a data area is the COBOL form", ["WRITE OPERATOR"])
        if ("ROUTECODES" in opts) != ("NUMROUTES" in opts):  # (the rule goes both ways)
            raise ec.Unsupported(ec._rule("WRITE OPERATOR", "requires", "ROUTECODES"), ["WRITE OPERATOR"])
        if not any(o in opts for o in ("TEXTLENGTH", "ROUTECODES")):
            return ([f"MOVE LENGTH OF {text} TO GG-LEN"] + ec._call("GGCWTO", [f"BY REFERENCE {text}"])
                    + ec._resp(opts, True, labels))  # fmt: skip
        # #5859 (X32): TEXTLENGTH is GG-LEN, ROUTECODES / NUMROUTES the routes area and GG-NUM; GG-FLAGS says which were given
        # (EVENTUAL changes nothing observable). The areas' sizes go by value; the flags are cleared after the call.
        flags = " ".join(f for f, o in (("TEXTLENGTH", "TEXTLENGTH"), ("ROUTES", "ROUTECODES")) if o in opts)
        routes = opts.get("ROUTECODES") or text
        lines = [
            f"MOVE {opts['TEXTLENGTH']} TO GG-LEN" if opts.get("TEXTLENGTH") else f"MOVE LENGTH OF {text} TO GG-LEN"
        ]
        if opts.get("NUMROUTES"):
            lines.append(f"MOVE {opts['NUMROUTES']} TO GG-NUM")
        lines.append(f"MOVE '{flags}' TO GG-FLAGS")
        lines += ec._call("GGCWTO", [f"BY REFERENCE {text}", f"BY VALUE LENGTH OF {text}", f"BY REFERENCE {routes}",
                                  f"BY VALUE LENGTH OF {routes}"])  # fmt: skip
        return lines + ["MOVE SPACES TO GG-FLAGS"] + ec._resp(opts, True, labels)
    return None
