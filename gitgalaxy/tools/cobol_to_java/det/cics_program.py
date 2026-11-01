"""#5274: the program control commands: LINK, RETURN and XCTL (#4270, #4679, #4806, #5005, #6271), split out of det/cics.py onto CicsTask. `Cics` inherits these methods, and its COMMAND_FAMILIES
registry calls `dispatch`. The translator's shared helpers come from det/cics_common.py (#7153)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gitgalaxy.tools.cobol_to_java.det.cics_common import (
    CicsError,
    _arg,
    _literal,
    _msg,
)


class ProgramControlCommands:
    """The program control commands of `Cics` (det/cics.py), which defines the members declared below."""

    if TYPE_CHECKING:
        g: Any
        gp: Any
        generated: Any
        package: str
        region_used: bool
        passes_bytes: bool

        def __getattr__(self, name: str) -> Any:
            """The members `Cics` defines, for the type checker."""

    def dispatch_program(self, words: list[str], verb: str, key: str, opts: dict, ind: str) -> list[str] | None:  # noqa: ARG002
        """The program control commands, or None for a command of another family."""
        g = self.g
        if verb == "LINK":
            # #4270 (X27): "SYNCONRETURN is only applicable to remote links, it is ignored if the link is local" (IBM,
            # EXEC CICS LINK); SYSID, the only way to a remote link, is refused, so every LINK here is local
            opts = {k: v for k, v in opts.items() if k != "SYNCONRETURN"}
            # a literal, or a data item's VALUE (GenApp's 01 LGUPVS01 PIC X(8) VALUE 'LGUPVS01'): the program the
            # COMMAREA's DTO is typed for -- the name the LINK uses at run time is still the item's
            prog_lit = _literal(opts.get("PROGRAM")) or self._value_name(opts.get("PROGRAM"))
            prog = self.name(_arg(opts.get("PROGRAM")))
            g = self.g
            r, ca = g.tmpname("lr"), g.tmpname("ca")
            out: list[str] = []
            cls: str | None = None
            f = length = ""  # (set by the COMMAREA arm, the only one that reads them)
            if "CHANNEL" in opts:  # #4270: the callee's current channel (CicsTask.linkChannel)
                if "COMMAREA" in opts or "LENGTH" in opts:
                    raise CicsError(_msg("LINK", "at_most_one", "CHANNEL"))
                out.append(f"{ind}String {r} = task.linkChannel({prog}, {self.name(_arg(opts['CHANNEL']))});")
            elif "COMMAREA" in opts:
                area = self.ref(_arg(opts["COMMAREA"]))
                try:
                    cls = self.dto_for(area, self.size(_arg(opts["COMMAREA"])), prog_lit, link=True)
                except CicsError as e:
                    if "no generated DTO" not in str(e):
                        raise
                    cls = None
                f = g.field_expr(area)
                length = (
                    self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else str(self.size(_arg(opts["COMMAREA"])))
                )
            else:
                out.append(f"{ind}String {r} = task.link({prog});")
            if "COMMAREA" in opts and cls is None:
                # #4679: no DTO types the target (cics-crucible ca-link-lengths: CAGONE, which no CSD defines -- the LINK
                # is PGMIDERR RESP2 1): the COMMAREA travels as its LENGTH bytes, by reference, as an XCTL's past its DTO
                w = g.tmpname("cw")
                out += [f"{ind}Storage {w} = Cobol.commarea({f}, Math.max(0, Math.min({length}, 32763)));",
                        f"{ind}String {r} = task.link({prog}, DetCics.commareaBytes({w}.bytes, CS), {length}, {w}.bytes);",
                        f"{ind}if (\"NORMAL\".equals({r})) Cobol.commareaBack({w}, {f});"]  # fmt: skip
            elif cls is not None:  # (a COMMAREA a DTO types)
                # #4181: the target's DTO over the caller's storage from the area on, never past its record's end;
                # #4679: a LENGTH past the DTO passes that many bytes (by reference: the target's EIBCALEN is LENGTH)
                w = g.tmpname("cw")
                dsize = self.gp.dto(cls).size
                fixed = self.constant_int(_arg(opts["LENGTH"])) if opts.get("LENGTH") else None
                span = (
                    str(dsize)
                    if not opts.get("LENGTH") or (fixed is not None and fixed <= dsize)
                    else f"Math.max({dsize}, Math.min({length}, 32763))"
                )
                out += [f"{ind}Storage {w} = Cobol.commarea({f}, {span});",
                        f"{ind}{cls} {ca} = out_{cls}({w}, 0);",
                        # #4181 follow-up: the bytes too (by reference), every one the target's DTO does not name
                        f"{ind}String {r} = task.link({prog}, {ca}, {length}, {w}.bytes);",
                        # what the linked program left in the COMMAREA is the caller's area now: #4806 its bytes when
                        # it took them (task.linkAreaBack: a det port), never its DTO over them -- a numeric field
                        # holding spaces it did not write would come back as digits; else (it took the object) the DTO
                        f"{ind}if (\"NORMAL\".equals({r})) {{",
                        f"{ind}    if (!task.linkAreaBack()) {{ in_{cls}({ca}, {w}, 0); }}",
                        f"{ind}    Cobol.commareaBack({w}, {f});",
                        f"{ind}}}"]  # fmt: skip
            out += self.abend_exit(ind)  # #4534: an abend below went to the exit, or unwound
            return out + self.outcome(opts, f"DetCics.resp({r})", "task.transferResp2()", ind)  # #4679
        if verb == "RETURN":
            if "CHANNEL" in opts:  # #5005 (X17): the next task's current channel (CicsTask.returnChannel)
                if not opts.get("TRANSID") or {"COMMAREA", "LENGTH", "IMMEDIATE"} & opts.keys():
                    raise CicsError(_msg("RETURN", "at_most_one", "CHANNEL"))
                tid, chan = self.name(_arg(opts["TRANSID"])), self.name(_arg(opts["CHANNEL"]))
                rr = g.tmpname("rr")
                # below the highest level it fails (INVREQ RESP2 2) and returns to the program; else the task ends
                return [f"{ind}int[] {rr} = task.returnChannel({tid}, {chan});",
                        f"{ind}if ({rr}[0] == 0) {{ caBack.run(); throw new Goback(); }}",
                        *self.outcome(opts, f"{rr}[0]", f"{rr}[1]", ind)]  # fmt: skip
            if "IMMEDIATE" in opts:  # #4270 (X27): IBM, EXEC CICS RETURN IMMEDIATE -- TRANSID's task attached at once
                if not opts.get("TRANSID"):
                    raise CicsError(
                        "RETURN IMMEDIATE without TRANSID: IBM does not say what it attaches (not modelled)"
                    )
                tid = self.name(_arg(opts["TRANSID"]))
                ret_pre, call = self._return_call("returnImmediate", tid, opts, ind, g)
                rr = g.tmpname("rr")
                # failing (INVREQ / LENGERR) it returns to the program, which tests RESP; else the task ends
                return [*ret_pre, f"{ind}int[] {rr} = {call};",
                        f"{ind}if ({rr}[0] == 0) {{ caBack.run(); throw new Goback(); }}",
                        *self.outcome(opts, f"{rr}[0]", f"{rr}[1]", ind)]  # fmt: skip
            if opts.get("TRANSID") and "RESP" in opts:  # #6271 (X71): a planned INVREQ / LENGERR returns to the program
                tid = self.name(_arg(opts["TRANSID"]))
                ret_pre, call = self._return_call("returnTransidResp", tid, opts, ind, g)
                rr = g.tmpname("rr")
                return [*ret_pre, f"{ind}int[] {rr} = {call};",
                        f"{ind}if ({rr}[0] == 0) {{ caBack.run(); throw new Goback(); }}",
                        *self.outcome(opts, f"{rr}[0]", f"{rr}[1]", ind)]  # fmt: skip
            if "TRANSID" in opts or "COMMAREA" in opts:
                tid = self.name(_arg(opts["TRANSID"])) if opts.get("TRANSID") else "null"
                ret_pre, call = self._return_call("returnTransid", tid, opts, ind, g)
                return [*ret_pre, f"{ind}caBack.run();", f"{ind}{call};",
                        f"{ind}if (true) throw new Goback();"]  # fmt: skip
            # (a LINKed program's COMMAREA goes back to its caller before the RETURN is recorded)
            return [
                f"{ind}caBack.run();",
                f"{ind}task.returnTransid(null, null);",
                f"{ind}if (true) throw new Goback();",
            ]
        if verb == "XCTL":
            prog_lit = _literal(opts["PROGRAM"])
            prog = self.name(_arg(opts["PROGRAM"]))
            pre: list[str] = []
            if "CHANNEL" in opts:  # #4270: the target's current channel (CicsTask.xctlChannel)
                if "COMMAREA" in opts or "LENGTH" in opts:
                    raise CicsError(_msg("XCTL", "at_most_one", "CHANNEL"))
                call = f"task.xctlChannel({prog}, {self.name(_arg(opts['CHANNEL']))})"
            elif "COMMAREA" in opts:
                dto, length = self.commarea_out(opts, prog_lit)
                if self.in_dfhcommarea(
                    str(opts["COMMAREA"])
                ):  # #4816: a LINKed program's is its caller's storage (X39)
                    pre.append(f"{ind}task.xctlOfLinkage();")
                if not dto.startswith("DetCics.commareaOut("):
                    # #4806: the bytes too -- a det target's DFHCOMMAREA is them, not the DTO's reading of them
                    xarea = self.commarea_bytes(opts, prog_lit)
                    call = f"task.xctl({prog}, {dto}, {length if length != 'null' else '(Integer) null'}, {xarea})"
                elif length != "null" and self.constant_int(str(opts["LENGTH"])) is None:
                    # a LENGTH known at run time: the bytes past the DTO (#4501), else the DTO and its bytes (#4806)
                    xc = g.tmpname("xc")
                    pre.append(f"{ind}Object {xc} = {dto};")
                    xarea = f"({xc} instanceof byte[] ? null : {self.commarea_bytes(opts, prog_lit)})"
                    call = f"task.xctl({prog}, {xc}, {length}, {xarea})"
                else:  # always the bytes past the DTO (#4501 LENGTH, #4765 a table's every occurrence)
                    call = f"task.xctl({prog}, {dto}, {length})" if length != "null" else f"task.xctl({prog}, {dto})"
            else:
                # #5291: no COMMAREA: the target may RETURN a wide COMMAREA as bytes (#4695), which this program's
                # facade then reads through its own DTO (bytes no layout reads are answered as before)
                self.passes_bytes = True
                call = f"task.xctl({prog}, null)"
            r = g.tmpname("xr")
            return ([*pre, f"{ind}String {r} = {call};", f"{ind}if (\"NORMAL\".equals({r})) throw new Goback();",
                    *self.outcome(opts, f"DetCics.resp({r})", "task.transferResp2()", ind)])  # fmt: skip
        return None

    def _return_call(self, method: str, tid: str, opts: dict, ind: str, g) -> tuple[list[str], str]:
        """RETURN [IMMEDIATE] TRANSID COMMAREA: (statements first, the runtime call). #4817: the COMMAREA's bytes go
        beside its DTO, so the next task gets every byte (spaces in a numeric DISPLAY field too), as IBM passes them."""
        pre: list[str] = []
        if "COMMAREA" in opts:
            dto, length = self.commarea_out(opts)
            if not dto.startswith("DetCics.commareaOut("):
                # #4817: pass the bytes beside the plain DTO (#4679/#4501 already carry a byte[])
                xarea = self.commarea_bytes(opts)
                ln = length if length != "null" else "(Integer) null"
                call = f"task.{method}({tid}, {dto}, {ln}, {xarea})"
            elif length != "null" and self.constant_int(str(opts["LENGTH"])) is None:
                xc = g.tmpname("xc")
                pre.append(f"{ind}Object {xc} = {dto};")
                xarea = f"({xc} instanceof byte[] ? null : {self.commarea_bytes(opts)})"
                call = f"task.{method}({tid}, {xc}, {length}, {xarea})"
            else:
                call = (
                    f"task.{method}({tid}, {dto}, {length})"
                    if length != "null"
                    else f"task.{method}({tid}, {dto}, null)"
                )
        else:
            call = f"task.{method}({tid}, null, null)"
        return pre, call
