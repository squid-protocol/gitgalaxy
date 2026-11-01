"""#5274: the remaining services: ASKTIME, FORMATTIME, SYNCPOINT, BIF DEEDIT, WRITE OPERATOR, VERIFY PASSWORD and INQUIRE ASSOCIATION / URIMAP / PROGRAM, split out of det/cics.py onto CicsTask. `Cics` inherits these methods, and its COMMAND_FAMILIES
registry calls `dispatch`. The translator's shared helpers come from det/cics_common.py (#7153)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from gitgalaxy.standards.cics.commands.task import DATE_FORMS, NUMBER_FORMS
from gitgalaxy.tools.cobol_to_java.det.cics_common import (
    CicsError,
    _arg,
    _msg,
    _requires,
    jstr,
)


class SystemCommands:
    """The system service commands of `Cics` (det/cics.py), which defines the members declared below."""

    if TYPE_CHECKING:
        g: Any
        gp: Any
        generated: Any
        package: str
        region_used: bool
        passes_bytes: bool

        def __getattr__(self, name: str) -> Any: ...

    def dispatch(self, words: list[str], verb: str, key: str, opts: dict, ind: str) -> list[str] | None:  # noqa: ARG002
        """The system service commands, or None for a command of another family."""
        g = self.g
        if verb == "ASKTIME":
            if "ABSTIME" not in opts:  # #4737: only EIBDATE / EIBTIME are updated, and the region keeps them (X4)
                return [f"{ind}task.asktime();"]
            return [
                f"{ind}Cobol.store({self.field(_arg(opts['ABSTIME']))}, BigDecimal.valueOf(task.asktime()), false, CS);"
            ]
        if verb == "FORMATTIME":
            t = f"Cobol.num({self.field(_arg(opts['ABSTIME']))}, CS).longValue()"
            body = []
            for form in DATE_FORMS:
                if form in opts:
                    # DATESEP with no value is IBM's default separator, '/'; no DATESEP, none
                    sep = (self.text(_arg(opts["DATESEP"])) if opts.get("DATESEP")
                           else '"/"' if "DATESEP" in opts else '""')  # fmt: skip
                    body.append(f"Cobol.move(CicsTask.formatDate({t}, {jstr(form)}, {sep}), "
                                f"{self.field(_arg(opts[form]))}, CS);")  # fmt: skip
            # #4415 slice 3 (X46): a binary integer, stored by the area's declared usage
            body += [self.g.store_into(self.ref(_arg(opts[form])),
                                       f"BigDecimal.valueOf(CicsTask.formatNumber({t}, {jstr(form)}))", False)
                     for form in NUMBER_FORMS if form in opts]  # fmt: skip
            if "TIME" in opts:
                sep = (self.text(_arg(opts["TIMESEP"])) if opts.get("TIMESEP")
                       else '":"' if "TIMESEP" in opts else '""')  # TIMESEP alone: IBM's ':'  # fmt: skip
                body.append(f"Cobol.move(CicsTask.formatTime({t}, {sep}), {self.field(_arg(opts['TIME']))}, CS);")
            if not body:
                raise CicsError("FORMATTIME form")
            if "RESP" not in opts and "RESP2" not in opts:
                # #4737 (X28): without RESP the INVREQ's handling (HANDLE CONDITION, the default abend) is not modelled:
                # CicsTask.formatDate / formatTime refuse an ABSTIME below zero at run time
                return [f"{ind}{ln}" for ln in body]
            # INVREQ RESP2 1 for an ABSTIME below zero (IBM), nothing written, through RESP / RESP2
            chk = g.tmpname("fmt")
            return [f"{ind}int[] {chk} = CicsTask.formattimeCheck({t});",
                    f"{ind}if ({chk}[0] == 0) {{",
                    *[f"{ind}    {ln}" for ln in body],
                    f"{ind}}}",
                    *self.outcome(opts, f"{chk}[0]", f"{chk}[1]", ind)]  # fmt: skip
        if key == "BIF DEEDIT":  # #4415 slice 1: IBM, EXEC CICS BIF DEEDIT (register X26)
            fld = self.field(_arg(opts.get("FIELD")))
            n = self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else f"{fld}.length()"
            r = g.tmpname("resp")
            self.region_used = True
            return [f"{ind}int {r} = CicsTask.deeditResp({n});",
                    f"{ind}if ({r} == 0) DetCics.deedit({fld}, {n}, CS, REGION);",
                    *self.outcome(opts, r, "0", ind)]  # fmt: skip
        if key == "INQUIRE ASSOCIATION":  # #4415 slice 2: the origin data of the task's own association (register X29)
            return self.inquire_association(opts, ind)
        if key == "INQUIRE URIMAP":  # #4270 zECS: the browse of the installed URIMAPs (register X32)
            return self.inquire_urimap(opts, ind)
        if key == "WRITE OPERATOR":  # #4270 zECS: a plain message to the console (register X32)
            if not opts.get("TEXT"):
                raise CicsError(_msg("WRITE OPERATOR", "required", "TEXT"))
            r = g.tmpname("wto")
            f = self.read_field(_arg(opts["TEXT"]))
            if ("ROUTECODES" in opts) != ("NUMROUTES" in opts):  # (the rule goes both ways)
                raise CicsError(_requires("WRITE OPERATOR", "ROUTECODES", "NUMROUTES"))
            if not any(o in opts for o in ("TEXTLENGTH", "ROUTECODES")):
                return [f"{ind}int {r} = task.writeOperator(Cobol.text({f}, CS));", *self.outcome(opts, r, "0", ind)]
            # #5859: TEXTLENGTH (a fullword value), ROUTECODES with NUMROUTES; EVENTUAL changes nothing observable
            n = f"Integer.valueOf({self.int_(_arg(opts['TEXTLENGTH']))})" if opts.get("TEXTLENGTH") else "null"
            rc = f"Cobol.text({self.read_field(_arg(opts['ROUTECODES']))}, CS)" if opts.get("ROUTECODES") else "null"
            nr = f"Integer.valueOf({self.int_(_arg(opts['NUMROUTES']))})" if opts.get("NUMROUTES") else "null"
            return [f"{ind}int[] {r} = task.writeOperator(Cobol.text({f}, CS), {n}, {rc}, {nr});",
                    *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]  # fmt: skip
        if key == "VERIFY PASSWORD":  # #5859 zECS ZECS002: the verdict a scenario states for the USERID (register X32)
            if not (opts.get("USERID") and opts.get("PASSWORD")):
                raise CicsError(_msg("VERIFY PASSWORD", "required", "USERID" if not opts.get("USERID") else "PASSWORD"))
            r = g.tmpname("ver")
            u = self.read_field(_arg(opts["USERID"]))
            return [f"{ind}int[] {r} = task.verifyPassword(Cobol.text({u}, CS));",
                    *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]  # fmt: skip
        if verb == "INQUIRE" and "PROGRAM" in opts:
            r = g.tmpname("resp")
            prog = self.name(_arg(opts["PROGRAM"]))
            out = [f"{ind}int {r} = task.inquireProgram({prog});"]
            if "STATUS" in opts:  # #4768 (X34): the definition's CVDA, written on NORMAL only
                out.append(
                    f"{ind}if ({r} == 0) "
                    + g.store_into(
                        self.ref(_arg(opts["STATUS"])), f"BigDecimal.valueOf(task.programStatus({prog}))", False
                    )
                )
            return out + self.outcome(opts, r, "0", ind)
        if verb in ("SYNCPOINT", "SYNCPOINT ROLLBACK"):
            # #4437: NORMAL -- the only outcome in this region (OPTIONS says why); EIBRESP / RESP / RESP2 written as
            # CICS writes them, never left as the previous command set them
            back = verb == "SYNCPOINT ROLLBACK" or "ROLLBACK" in opts
            pl = g.tmpname(
                "planned"
            )  # #6271 (X71): a planned INVREQ (RESP2 200) is not performed and raises as any condition
            call = f'{ind}int[] {pl} = task.planned({jstr("ROLLBACK" if back else "SYNCPOINT")}, "-");'
            call2 = f"{ind}if ({pl}[0] == 0) task.{'rollback' if back else 'syncpoint'}();"
            out = [call, call2, *self.outcome(opts, f"{pl}[0]", f"{pl}[1]", ind)]
            if "RESP2" in opts and "RESP" not in opts:  # RESP2 alone is written too
                out.append(
                    ind + self.g.store_into(self.ref(_arg(opts["RESP2"])), f"BigDecimal.valueOf({pl}[1])", False)
                )
            return out
        return None

    def inquire_association(self, opts: dict, ind: str) -> list[str]:
        """INQUIRE ASSOCIATION(EIBTASKN) ODAPPLID / ODUSERID / ODFACILNAME / ODNETWORKID (8 characters) and ODFACILTYPE (a
        CVDA): the origin data of the task's own association data, as the run states it (CicsTask.withOrigin; unstated,
        refused). IBM gives no representation for the task number, so only the task's own number, EIBTASKN, is read: any
        other operand (a literal, a copy of it) is refused. A command with no origin option is refused: IBM's
        INVREQ RESP2 2 ("The command was specified with no arguments") does not say whether ASSOCIATION alone is none."""
        if re.fullmatch(r"(?is)\s*EIBTASKN\s*", _arg(opts.get("ASSOCIATION"))) is None:
            raise CicsError(
                f"INQUIRE ASSOCIATION({opts.get('ASSOCIATION')}): only the task's own number, EIBTASKN, is "
                "modelled (IBM gives no representation for the 4 bytes)"
            )
        wanted = [o for o in ("ODAPPLID", "ODUSERID", "ODFACILNAME", "ODNETWORKID", "ODFACILTYPE") if o in opts]
        if not wanted:
            raise CicsError(
                "INQUIRE ASSOCIATION without an origin option: IBM's INVREQ RESP2 2 (\"The command was "
                'specified with no arguments") does not say whether ASSOCIATION alone is none: not modelled'
            )
        r = self.g.tmpname("assoc")
        out = [f"{ind}CicsTask.Origin {r} = task.inquireAssociation();"]
        for k, acc in (("ODAPPLID", "applid"), ("ODUSERID", "userid"), ("ODFACILNAME", "facilname"),
                       ("ODNETWORKID", "networkid")):  # fmt: skip
            if k in opts:
                out.append(f"{ind}DetCics.putText({self.field(_arg(opts[k]))}, {r}.{acc}(), CS);")
        if "ODFACILTYPE" in opts:
            out.append(
                ind
                + self.g.store_into(self.ref(_arg(opts["ODFACILTYPE"])), f"BigDecimal.valueOf({r}.faciltype())", False)
            )
        return out + self.outcome(opts, "0", "0", ind)

    def inquire_urimap(self, opts: dict, ind: str) -> list[str]:
        """INQUIRE URIMAP START / NEXT / END (IBM CICS TS, INQUIRE URIMAP, "Browsing resource definitions"): the browse of
        the URIMAP definitions the run states are installed (CicsTask.withUrimaps; unstated, refused). NEXT hands back the
        definition's name (8), PATH (255) and TRANSACTION (4), blank-padded, only on NORMAL; END (RESP2 2) and ILLOGIC
        (RESP2 1) leave the areas alone. START / END name no output area. #4768 (X34): with no browse option, the direct
        form reads the definition URIMAP names (NOTFND RESP2 3 when it is not installed), PATH / TRANSACTION as NEXT's."""
        g = self.g
        form = [f for f in ("START", "NEXT", "END") if f in opts]
        if len(form) > 1:
            raise CicsError(_msg("INQUIRE URIMAP", "at_most_one", "START"))
        r = g.tmpname("urimap")
        if not form:  # #4768 (X34): the direct form, URIMAP(name): that definition, NOTFND RESP2 3 when not installed
            if "URIMAP" not in opts:
                raise CicsError(_msg("INQUIRE URIMAP", "required", "URIMAP"))
            name = self.name(_arg(opts["URIMAP"]))
            outs = [k for k in ("PATH", "TRANSACTION") if k in opts]
            out = [f"{ind}int[] {r} = task.inquireUrimap({name});"]
        else:
            call = {"START": "inquireUrimapStart", "NEXT": "inquireUrimapNext", "END": "inquireUrimapEnd"}[form[0]]
            outs = [k for k in ("URIMAP", "PATH", "TRANSACTION") if k in opts]
            if form[0] != "NEXT" and outs:
                raise CicsError(f"INQUIRE URIMAP {form[0]} {outs[0]}: a browse {form[0]} returns no definition")
            out = [f"{ind}int[] {r} = task.{call}();"]
        if outs:
            out.append(f"{ind}if ({r}[0] == 0) {{")
            for k, acc in (("URIMAP", "urimapName"), ("PATH", "urimapPath"), ("TRANSACTION", "urimapTransaction")):
                if k in outs:
                    out.append(f"{ind}    DetCics.putText({self.field(_arg(opts[k]))}, task.{acc}(), CS);")
            out.append(f"{ind}}}")
        return out + self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)
