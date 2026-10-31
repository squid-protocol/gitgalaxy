"""#5274: the channels / containers family of the det CICS translator, split out of det/cics.py -- PUT / GET / DELETE
CONTAINER (#4270), MOVE CONTAINER and the container browse (#4951), DELETE / QUERY CHANNEL (#5005), onto CicsTask's
channels (cics_task_containers.py). `Cics` inherits these methods; its command dispatch and `command_key` stay the
registry. The translator's shared helpers come from det/cics_common.py (#7153): importing them back from det/cics.py
closed an import cycle."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError, _arg, _msg, _option, _requires, jstr, region_page

if TYPE_CHECKING:
    from gitgalaxy.tools.cobol_to_java.det import expr as E


class ContainerCommands:
    """The container and channel commands of `Cics` (det/cics.py), which defines the members declared below."""

    if TYPE_CHECKING:
        g: Any
        region: str

        def ref(self, text: str) -> E.Ref: ...
        def name(self, text: str) -> str: ...
        def int_(self, text: str) -> str: ...
        def field(self, text: str) -> str: ...
        def read_field(self, text: str) -> str: ...
        def size(self, text: str) -> int: ...
        def outcome(self, opts: dict, resp: str, resp2: str, ind: str) -> list[str]: ...
        def pointer(self, text: str | None) -> str: ...

    def container(self, key: str, opts: dict, ind: str) -> list[str]:
        """PUT / GET / DELETE CONTAINER (IBM CICS TS, EXEC CICS PUT CONTAINER (CHANNEL), GET CONTAINER (CHANNEL),
        DELETE CONTAINER (CHANNEL)) on CicsTask's channels. No CHANNEL: the current channel. The data is the
        program's own bytes, never converted (OPTIONS: BIT, or CHAR in the region's CCSID both ways); CHANNELERR,
        CONTAINERERR, INVREQ and LENGERR come back as CicsTask documents them, with their RESP2, through RESP /
        HANDLE CONDITION like any condition (AEZV / AEZJ / AEIP / AEIV by default).

        PUT: FROM's first FLENGTH bytes (FLENGTH omitted: FROM's length), the data type BIT / CHAR /
        DATATYPE(DFHVALUE(..)) or none, APPEND. GET: INTO takes at most FLENGTH's value (else INTO's length) -- the
        data into INTO's first bytes, longer data truncated with LENGERR RESP2 11 -- or NODATA; FLENGTH, a data
        area, is set to the container's length on NORMAL and LENGERR (IBM: "As an output field, FLENGTH returns
        the length of the data in the container"; on another condition IBM does not say, so it is left alone)."""

        g = self.g
        name = self.name(_arg(opts.get("CONTAINER")))
        chan = self.name(_arg(opts["CHANNEL"])) if "CHANNEL" in opts else "null"
        r = g.tmpname("cont")
        out: list[str] = []
        if key == "PUT CONTAINER":
            frm = _arg(opts.get("FROM"))
            f = self.read_field(frm)
            given = _option(opts, "FLENGTH")
            n = self.int_(given) if given else str(self.size(frm))
            dtype = _datatype(opts)
            ln = g.tmpname("flen")
            from_ccsid = self.container_ccsid(opts, "FROMCCSID", "PUT CONTAINER")
            if "PREPEND" in opts and "APPEND" in opts:  # #5005 (X17)
                raise CicsError(_msg("PUT CONTAINER", "at_most_one", "APPEND", "PREPEND"))
            tail = ""  # the trailing arguments: FROMCCSID (-1: none), then PREPEND
            if "PREPEND" in opts:
                tail = f", {from_ccsid or '-1'}, true"
            elif from_ccsid:
                tail = f", {from_ccsid}"
            out += [f"{ind}int {ln} = {n};",
                    (f"{ind}CicsTask.ContainerResult {r} = task.putContainer({chan}, {name}, "
                     f"DetCics.containerData({f}, {ln}), {ln}, {jstr(dtype) if dtype else 'null'}, "
                     f"{str('APPEND' in opts).lower()}{tail});")]  # fmt: skip
        elif key == "GET CONTAINER":
            into, nodata = opts.get("INTO") or "", "NODATA" in opts
            if [bool(into), nodata, "SET" in opts].count(True) != 1:
                raise CicsError(_msg("GET CONTAINER", "one_of", "INTO"))
            flen = _option(opts, "FLENGTH")
            settable = flen is not None and re.fullmatch(r"(?is)[+-]?\d+|LENGTH\s+OF\s+.+", flen.strip()) is None
            if "BYTEOFFSET" in opts:  # #5005 (X17): INTO only, a BIT container, the offset a fullword
                if not into:
                    raise CicsError(_requires("GET CONTAINER", "BYTEOFFSET", "INTO"))
                for other in ("INTOCCSID", "CONVERTST", "CCSID"):
                    if other in opts:
                        raise CicsError(_msg("GET CONTAINER", "at_most_one", "BYTEOFFSET", other))
            into_ccsid = self.container_ccsid(opts, "INTOCCSID", "GET CONTAINER")
            convert = _convertst(opts)
            if convert and "INTOCCSID" in opts:
                raise CicsError(_msg("GET CONTAINER", "at_most_one", "INTOCCSID", "INTOCCSID and CONVERTST"))
            if "CCSID" in opts and convert is None:
                raise CicsError(_msg("GET CONTAINER", "requires", "CCSID"))
            conv = f", {into_ccsid or '-1'}, {str(bool(convert)).lower()}" if into_ccsid or convert else ""
            if "SET" in opts:  # #5042 (X58): SET(pointer) FLENGTH(data-area): a copy of the data in a new block
                if not settable:
                    raise CicsError(_msg("GET CONTAINER", "requires", "SET"))
                ptr = self.pointer(opts["SET"])
                out += [f"{ind}CicsTask.SetBlock {r}s = task.getContainerSet({chan}, {name}{conv});",
                        f"{ind}CicsTask.ContainerResult {r} = {r}s.result();",
                        f"{ind}if ({r}s.handle() != 0) DetCics.setPointer({ptr}, {r}s.handle());"]  # fmt: skip
            elif nodata:
                out.append(f"{ind}CicsTask.ContainerResult {r} = task.getContainer({chan}, {name}, -1{conv});")
            else:
                target = self.field(into)
                most = self.int_(flen) if flen else str(self.size(into))
                if "BYTEOFFSET" in opts:
                    call = (
                        f"task.getContainerAt({chan}, {name}, DetCics.containerLimit({target}, {most}), "
                        f"{self.int_(_arg(opts['BYTEOFFSET']))})"
                    )
                else:
                    call = f"task.getContainer({chan}, {name}, DetCics.containerLimit({target}, {most}){conv})"
                out += [f"{ind}CicsTask.ContainerResult {r} = {call};",
                        f"{ind}if ({r}.data() != null) DetCics.put({target}, {r}.data());"]  # fmt: skip
            if flen is not None and settable:
                set_back = g.store_into(self.ref(flen), f"BigDecimal.valueOf({r}.length())", False)
                out.append(f"{ind}if ({r}.length() >= 0) {set_back}")
            if "CCSID" in opts:  # the container's own CCSID (0: BIT), set with FLENGTH: on NORMAL and LENGERR
                set_ccsid = g.store_into(
                    self.ref(_arg(opts["CCSID"])), "BigDecimal.valueOf(task.containerCcsid())", False
                )
                out.append(f"{ind}if ({r}.length() >= 0) {set_ccsid}")
        else:
            out.append(f"{ind}CicsTask.ContainerResult {r} = task.deleteContainer({chan}, {name});")
        return out + self.outcome(opts, f"DetCics.resp({r}.resp())", f"{r}.resp2()", ind)

    def container_ccsid(self, opts: dict, option: str, verb: str) -> str | None:
        """#4270 (X17): PUT's FROMCCSID or GET's INTOCCSID as a Java int expression (a data value; the runtime refuses one outside
        37 / 500 / 1140 / 1208), None when not given. The port's storage is read as the region's page (#4528), which the
        conversion assumes is CCSID 037: another declared page refuses the option."""

        if option not in opts:
            return None
        if self.region != region_page(None):
            raise CicsError(
                f"{verb} {option}: code-page conversion assumes the region's page is CCSID 037, not {self.region}"
            )
        return self.int_(_arg(opts[option]))

    def channel_command(self, key: str, opts: dict, ind: str) -> list[str]:
        """#5005: DELETE CHANNEL and QUERY CHANNEL (IBM CICS TS, EXEC CICS DELETE CHANNEL, QUERY CHANNEL) on CicsTask's
        channels. DELETE: the channel and its containers go. QUERY: CONTAINERCNT, a fullword, is set to the number of
        containers on NORMAL (not on a condition: IBM does not say). CHANNELERR RESP2 2 comes back through RESP / HANDLE
        CONDITION (AEZV by default); what IBM leaves open is refused at run time (register X44)."""

        r = self.g.tmpname("chan")
        chan = self.name(_arg(opts.get("CHANNEL")))
        if key == "DELETE CHANNEL":
            call = f"task.deleteChannel({chan})"
            return [f"{ind}CicsTask.ContainerResult {r} = {call};",
                    *self.outcome(opts, f"DetCics.resp({r}.resp())", f"{r}.resp2()", ind)]  # fmt: skip
        count = _arg(opts.get("CONTAINERCNT"))
        return [f"{ind}CicsTask.ContainerResult {r} = task.queryChannel({chan});",
                f"{ind}if ({r}.length() >= 0) " + self.g.store_into(self.ref(count), f"BigDecimal.valueOf({r}.length())", False),
                *self.outcome(opts, f"DetCics.resp({r}.resp())", f"{r}.resp2()", ind)]  # fmt: skip

    def container_browse(self, key: str, opts: dict, ind: str) -> list[str]:
        """#4951: MOVE CONTAINER and the container browse (IBM CICS TS, EXEC CICS MOVE CONTAINER (CHANNEL),
        STARTBROWSE / GETNEXT / ENDBROWSE CONTAINER (CHANNEL)) on CicsTask's channels. MOVE: CONTAINER and AS, the
        channels CHANNEL / TOCHANNEL (omitted: the current channel). STARTBROWSE: BROWSETOKEN, a fullword the token
        is stored in (not on a condition: IBM does not say); CHANNEL, omitted: the current channel. GETNEXT: the next
        container's 16-character name into CONTAINER (not on END / TOKENERR). ENDBROWSE: the token. CHANNELERR,
        CONTAINERERR, INVREQ, END, ILLOGIC and TOKENERR come back with their RESP2 through RESP / HANDLE CONDITION;
        what IBM leaves open is refused or assumed at run time (register X42)."""

        g = self.g
        r = g.tmpname("cont")

        def named(option: str) -> str:
            return self.name(_arg(opts[option])) if option in opts else "null"

        if key == "MOVE CONTAINER":
            for need in ("CONTAINER", "AS"):
                _arg(opts.get(need))
            call = f"task.moveContainer({named('CHANNEL')}, {named('CONTAINER')}, {named('AS')}, {named('TOCHANNEL')})"
            return [f"{ind}CicsTask.ContainerResult {r} = {call};",
                    *self.outcome(opts, f"DetCics.resp({r}.resp())", f"{r}.resp2()", ind)]  # fmt: skip
        token = _arg(opts.get("BROWSETOKEN"))
        out: list[str] = []
        if key == "STARTBROWSE CONTAINER":
            out.append(f"{ind}CicsTask.ContainerResult {r} = task.startBrowseContainer({named('CHANNEL')});")
            out.append(
                f"{ind}if ({r}.length() >= 0) "
                + g.store_into(self.ref(token), f"BigDecimal.valueOf({r}.length())", False)
            )
        elif key == "GETNEXT CONTAINER":
            out.append(f"{ind}CicsTask.ContainerResult {r} = task.getNextContainer({self.int_(token)});")
            out.append(
                f"{ind}if ({r}.name() != null) DetCics.putText({self.field(_arg(opts['CONTAINER']))}, {r}.name(), CS);"
            )
        else:
            out.append(f"{ind}CicsTask.ContainerResult {r} = task.endBrowseContainer({self.int_(token)});")
        return out + self.outcome(opts, f"DetCics.resp({r}.resp())", f"{r}.resp2()", ind)


def _convertst(opts: dict) -> bool | None:
    """#4270 (X17): GET CONTAINER CONVERTST -- True for DFHVALUE(NOCONVERT) (734), the only value IBM documents; None when
    not given."""

    named = _option(opts, "CONVERTST")
    if named is None:
        return None
    if re.fullmatch(r"(?is)\s*(DFHVALUE\s*\(\s*NOCONVERT\s*\)|734)\s*", named) is None:
        raise CicsError(f"GET CONTAINER CONVERTST({named}): only DFHVALUE(NOCONVERT) is modelled")
    return True


def _datatype(opts: dict) -> str | None:
    """#4270: PUT CONTAINER's data type -- BIT, CHAR, DATATYPE(DFHVALUE(BIT | CHAR)) -- or None when none is named."""

    given = [t for t in ("BIT", "CHAR") if t in opts]
    named = _option(opts, "DATATYPE")
    if named is not None:
        m = re.fullmatch(r"(?is)\s*DFHVALUE\s*\(\s*(BIT|CHAR)\s*\)\s*", named)
        if m is None:
            raise CicsError(f"PUT CONTAINER DATATYPE({named}): only DFHVALUE(BIT / CHAR) is modelled")
        given.append(m.group(1).upper())
    if len(given) > 1:
        raise CicsError(_msg("PUT CONTAINER", "at_most_one", "BIT", " and ".join(given)))
    return given[0] if given else None
