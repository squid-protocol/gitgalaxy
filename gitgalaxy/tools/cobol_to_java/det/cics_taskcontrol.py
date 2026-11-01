"""#5274: the task / interval control family of the det CICS translator, split out of det/cics.py -- START and RETRIEVE
(#4270, #4950), RUN TRANSID / FETCH / FREE CHILD (#4884), DELAY, POST, WAIT EVENT, CANCEL, CONVERSE and SEND CONTROL,
onto CicsTask. `Cics` inherits these methods; its command dispatch and `command_key` stay the registry. The
translator's shared helpers come from det/cics_common.py (#7153), which imports nothing back from cics.py or gen.py."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gitgalaxy.tools.cobol_to_java.det import expr as E


class TaskControlCommands:
    """The task and interval control commands of `Cics` (det/cics.py), which defines the members declared below."""

    if TYPE_CHECKING:
        g: Any
        region: str
        region_used: bool

        def ref(self, text: str) -> E.Ref: ...
        def name(self, text: str) -> str: ...
        def int_(self, text: str) -> str: ...
        def field(self, text: str) -> str: ...
        def read_field(self, text: str) -> str: ...
        def size(self, text: str) -> int: ...
        def constant_int(self, text: str) -> int | None: ...
        def outcome(self, opts: dict, resp: str, resp2: str, ind: str) -> list[str]: ...
        def pointer(self, text: str | None) -> str: ...

    def _number(self, text: str) -> str:
        """An INTERVAL / TIME / HOURS ... value as a Java int expression (a literal's leading zeros dropped)."""
        import re

        t = text.strip()
        return str(int(t)) if re.fullmatch(r"\d+", t) else self.int_(t)

    def start(self, opts: dict, ind: str) -> list[str]:
        """START TRANSID (IBM CICS TS, EXEC CICS START) on CicsTask.startRequest: INTERVAL(hhmmss) / TIME(hhmmss) /
        AFTER or AT HOURS MINUTES SECONDS (none: INTERVAL(0)), TERMID, REQID, PROTECT, FROM's first LENGTH bytes (no
        LENGTH: FROM's length), and the data options RTRANSID / RTERMID / QUEUE the started task RETRIEVEs. The
        request's expiry, INVREQ RESP2 4 / 5 / 6, LENGERR, TRANSIDERR, TERMIDERR and IOERR are CicsTask's, through
        RESP / HANDLE CONDITION. FROM's bytes go in the region's page, as a TS item's do (#4528): the started task's
        RETRIEVE reads them back into its own storage's page."""
        from gitgalaxy.tools.cobol_to_java.det.cics_common import SPEC, CicsError, _arg, _msg, _one_of

        if not opts.get("TRANSID"):
            raise CicsError(_msg("START", "required", "TRANSID"))
        whens = [w for w in ("INTERVAL", "TIME", "AFTER", "AT") if w in opts]
        if len(whens) > 1:
            raise CicsError(_msg("START", "at_most_one", "INTERVAL", " and ".join(whens)))
        when = whens[0] if whens else "INTERVAL"
        hms = [o for o in ("HOURS", "MINUTES", "SECONDS") if o in opts]
        if (when in ("AFTER", "AT")) != bool(hms):
            raise CicsError(_msg("START", "requires", "HOURS", when, " ".join(hms)))
        for g in SPEC["START"].groups:  # #4950: START CHANNEL's form -- no expiry, no data options, no REQID
            if g.kind == "at_most_one" and g.options[0] == "CHANNEL" and all(o in opts for o in g.options):
                raise CicsError(g.msg.format(g.options[1]))
        chain = f"task.startRequest({self.name(_arg(opts['TRANSID']))})"
        if hms:
            vals = [self._number(_arg(opts[o])) if o in opts else "null" for o in ("HOURS", "MINUTES", "SECONDS")]
            chain += f".{when.lower()}({', '.join(vals)})"
        elif when in opts:
            chain += f".{when.lower()}({self._number(_arg(opts[when]))})"
        for o in ("TERMID", "REQID", "RTRANSID", "RTERMID", "QUEUE", "CHANNEL"):  # (#4950: START CHANNEL)
            if o in opts:
                chain += f".{o.lower()}({self.name(_arg(opts[o]))})"
        if "FROM" in opts:
            frm = _arg(opts["FROM"])
            f = self.read_field(frm)
            length = _one_of(opts, "LENGTH", "FLENGTH")
            n = self.int_(length) if length else str(self.size(frm))
            self.region_used = True
            chain += f".from(DetCics.toRegion(DetCics.startData({f}, {n}), CS, REGION))"
        elif "LENGTH" in opts or "FLENGTH" in opts:
            raise CicsError(_msg("START", "requires", "LENGTH"))
        if "PROTECT" in opts:
            chain += ".protect(true)"
        r = self.g.tmpname("start")
        return [f"{ind}CicsTask.StartResult {r} = {chain}.issue();",
                *self.outcome(opts, f"DetCics.resp({r}.resp())", f"{r}.resp2()", ind)]  # fmt: skip

    def retrieve(self, opts: dict, ind: str) -> list[str]:
        """RETRIEVE (IBM CICS TS, EXEC CICS RETRIEVE) on CicsTask.retrieve: INTO takes at most LENGTH's value (else
        INTO's length) -- the data into INTO's first bytes, back in the storage's page; LENGTH, a data area, is set to
        the data's length on NORMAL and LENGERR ("On completion of the retrieval operation, the data area is set to
        the original length of the data"); RTRANSID / RTERMID / QUEUE get the values the START gave. ENDDATA,
        ENVDEFERR and LENGERR through RESP / HANDLE CONDITION. SET(pointer) LENGTH(data-area) (#5042, X58): the data in a new
        block of task storage the pointer addresses (DetCics.setBlock), LENGTH its length. WAIT is refused (OPTIONS)."""
        import re

        from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError, _arg, _msg, _one_of

        into = opts.get("INTO")
        length = _one_of(opts, "LENGTH", "FLENGTH")
        into_ptr = ""  # set by the SET branch below; read only under the same guard
        named = [o for o in ("RTRANSID", "RTERMID", "QUEUE") if o in opts]
        if "SET" in opts:  # #5042 (X58): SET(pointer) LENGTH(data-area): the data in a new block of task storage
            if into:
                raise CicsError(_msg("RETRIEVE", "at_most_one", "INTO"))
            if length is None:
                raise CicsError(_msg("RETRIEVE", "requires", "SET"))
            if re.fullmatch(r"(?is)[+-]?\d+|LENGTH\s+OF\s+.+", length.strip()) is not None:
                raise CicsError("RETRIEVE SET with a literal LENGTH: IBM says the argument must be a data area")
            into_ptr = self.pointer(opts["SET"])
        elif not into and (not named or length is not None):
            raise CicsError(_msg("RETRIEVE", "requires", "LENGTH"))
        g = self.g
        r = g.tmpname("retrieved")
        most = "null"
        if into:
            most = self.int_(length) if length else str(self.size(into))
        elif "SET" in opts:
            most = "Integer.MAX_VALUE"  # IBM gives SET no most: LENGTH is only set
        flags = ", ".join(str(o in named).lower() for o in ("RTRANSID", "RTERMID", "QUEUE"))
        out = [f"{ind}CicsTask.RetrieveResult {r} = task.retrieve({most}, {flags});"]
        if "SET" in opts:
            self.region_used = True
            # IBM gives the pointer no validity end for RETRIEVE: it lasts to the task's end (ASSUMED, X58)
            out.append(f"{ind}if ({r}.data() != null) DetCics.setBlock(task, {into_ptr}, null, "
                       f"DetCics.fromRegion({r}.data(), REGION, CS));")  # fmt: skip
            set_back = g.store_into(self.ref(length or ""), f"BigDecimal.valueOf({r}.length())", False)
            out.append(f"{ind}if ({r}.length() >= 0) {set_back}")
        elif into:
            self.region_used = True
            out.append(f"{ind}if ({r}.data() != null) DetCics.put({self.field(into)}, "
                       f"DetCics.fromRegion({r}.data(), REGION, CS));")  # fmt: skip
            settable = length is not None and re.fullmatch(r"(?is)[+-]?\d+|LENGTH\s+OF\s+.+", length.strip()) is None
            if settable and length is not None:
                set_back = g.store_into(self.ref(length), f"BigDecimal.valueOf({r}.length())", False)
                out.append(f"{ind}if ({r}.length() >= 0) {set_back}")
        out += [f"{ind}if ({r}.{o.lower()}() != null) DetCics.putPadded({self.field(_arg(opts[o]))}, "
                f"{r}.{o.lower()}(), CS);" for o in named]  # fmt: skip
        return out + self.outcome(opts, f"DetCics.resp({r}.resp())", "0", ind)

    def run_transid(self, opts: dict, ind: str) -> list[str]:
        """RUN TRANSID CHILD (IBM CICS TS, EXEC CICS RUN TRANSID) on CicsTask.runTransid: the child task runs once this task
        has ended (the harness's scheduler); CHILD's 16-character area gets the child token on NORMAL; TRANSIDERR
        RESP2 1 through RESP / HANDLE CONDITION."""
        from gitgalaxy.tools.cobol_to_java.det.cics_common import NEEDS_ARGUMENT, CicsError, _msg, _option

        transid, child = _option(opts, "TRANSID"), _option(opts, "CHILD")
        if not transid or not child:
            raise CicsError(_msg("RUN", "required", "TRANSID"))
        r = self.g.tmpname("run")
        channel = _option(opts, "CHANNEL")  # #4884: the child's copy of a channel (it runs after this task ends)
        if "CHANNEL" in opts and not channel:
            raise CicsError(NEEDS_ARGUMENT)
        arg = self.name(transid) + (f", {self.name(channel)}" if channel else "")
        return [f"{ind}CicsTask.RunResult {r} = task.runTransid({arg});",
                f"{ind}if ({r}.child() != null) DetCics.putPadded({self.field(child)}, {r}.child(), CS);",
                *self.outcome(opts, f"DetCics.resp({r}.resp())", f"{r}.resp2()", ind)]  # fmt: skip

    def fetch(self, key: str, opts: dict, ind: str) -> list[str]:
        """FETCH ANY / FETCH CHILD(token) (IBM CICS TS, EXEC CICS FETCH) on CicsTask.fetch, #4950: NOSUSPEND, TIMEOUT
        (milliseconds) or neither (it waits); on NORMAL the token goes to ANY, the reply channel's name to CHANNEL, the
        abend code to ABCODE (only for a child that abended) and the completion status's CVDA to COMPSTATUS. The
        conditions (NOTFINISHED 52 / 53, NOTFND, INVREQ 50 / 52) through RESP / HANDLE CONDITION."""
        from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError, _arg, _msg, _option

        form = key.split()[1]
        token = _option(opts, form)
        if not token:
            raise CicsError(_msg(key, "required", form))
        if "NOSUSPEND" in opts and "TIMEOUT" in opts:
            raise CicsError(_msg(key, "at_most_one", "NOSUSPEND", "NOSUSPEND", "TIMEOUT"))
        mode, timeout = "WAIT", "0"
        if "NOSUSPEND" in opts:
            mode = "NOSUSPEND"
        elif "TIMEOUT" in opts:
            mode, timeout = "TIMEOUT", self._number(_arg(opts["TIMEOUT"]))
        r = self.g.tmpname("fetch")
        child = self.name(token) if form == "CHILD" else "null"
        out = [f'{ind}CicsTask.FetchResult {r} = task.fetch({child}, "{mode}", {timeout}, {str("CHANNEL" in opts).lower()});',
               f"{ind}if ({r}.child() != null) {{"]  # fmt: skip
        if form == "ANY":
            out.append(f"{ind}    DetCics.putPadded({self.field(token)}, {r}.child(), CS);")
        if "CHANNEL" in opts:
            out.append(f"{ind}    DetCics.putPadded({self.field(_arg(opts['CHANNEL']))}, {r}.channel(), CS);")
        if "ABCODE" in opts:
            out.append(
                f"{ind}    if ({r}.abcode() != null) DetCics.putPadded({self.field(_arg(opts['ABCODE']))}, {r}.abcode(), CS);"
            )
        if "COMPSTATUS" in opts:
            out.append(ind + "    " + self.g.store_into(self.ref(_arg(opts["COMPSTATUS"])),
                                                     f"BigDecimal.valueOf({r}.compstatus())", False))  # fmt: skip
        out.append(f"{ind}}}")
        return out + self.outcome(opts, f"DetCics.resp({r}.resp())", f"{r}.resp2()", ind)

    def free_child(self, opts: dict, ind: str) -> list[str]:
        """#4950: FREE CHILD(token) (IBM CICS TS, EXEC CICS FREE CHILD) on CicsTask.freeChild: INVREQ 50 for a token
        that is not a child's or was freed, through RESP / HANDLE CONDITION."""
        from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError, _msg, _option

        token = _option(opts, "CHILD")
        if not token:
            raise CicsError(_msg("FREE CHILD", "required", "CHILD"))
        r = self.g.tmpname("freed")
        return [f"{ind}CicsTask.FetchResult {r} = task.freeChild({self.name(token)});",
                *self.outcome(opts, f"DetCics.resp({r}.resp())", f"{r}.resp2()", ind)]  # fmt: skip

    def delay(self, opts: dict, ind: str) -> list[str]:
        """#4950: DELAY (IBM CICS TS, EXEC CICS DELAY) on CicsTask.delay: INTERVAL(hhmmss), or [FOR] HOURS / MINUTES /
        SECONDS / MILLISECS, as milliseconds (CicsTask.delayMillis: -1 out of IBM's ranges); none, INTERVAL(0). A task
        takes no time (X4): NORMAL at once, after the RUN children the wait dispatches. TIME (a time of day) and a
        value out of range are refused in a task with RUN children (CicsTask.delay). #6271 (X72): a scenario's planned
        EXPIRED / INVREQ (CicsTask.planned) answers instead, and the delay is not performed."""
        from gitgalaxy.tools.cobol_to_java.det.cics_common import _arg

        def num(o: str) -> str:
            return f"Long.valueOf({self._number(_arg(opts[o]))})" if o in opts else "null"

        if "TIME" in opts:
            ms, what = "-1L", "DELAY TIME (a time of day)"
        elif "INTERVAL" in opts:
            ms, what = f"CicsTask.delayMillis({num('INTERVAL')}, null, null, null, null)", "DELAY out of range"
        elif any(o in opts for o in ("HOURS", "MINUTES", "SECONDS", "MILLISECS")):
            ms = f"CicsTask.delayMillis(null, {num('HOURS')}, {num('MINUTES')}, {num('SECONDS')}, {num('MILLISECS')})"
            what = "DELAY out of range"
        else:
            ms, what = "0L", "DELAY"
        # #6271 (X72): a planned EXPIRED / INVREQ is not performed and raises as any condition
        pl = self.g.tmpname("planned")
        return [
            f'{ind}int[] {pl} = task.planned("DELAY", "-");',
            f'{ind}if ({pl}[0] == 0) task.delay({ms}, "{what}");',
            *self.outcome(opts, f"{pl}[0]", f"{pl}[1]", ind),
        ]

    def post(self, opts: dict, ind: str) -> list[str]:
        """#5079 (X63): POST INTERVAL(hhmmss) | TIME(hhmmss) | AFTER / AT HOURS MINUTES SECONDS [SET(ptr)] [REQID] (IBM CICS TS,
        EXEC CICS POST) on CicsTask.post. SET: the pointer takes the new timer-event control area's handle (the 4 bytes
        SET ADDRESS OF reads, zero until posted); EXPIRED and INVREQ RESP2 4 / 5 / 6 leave it as it was. No REQID: IBM
        "generates one" and returns it in EIBREQID, which gets CicsTask's POSTnnnn (ASSUMED). No expiry option:
        INTERVAL(0). The conditions go through RESP / HANDLE CONDITION."""
        from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError, _arg, _msg

        whens = [w for w in ("INTERVAL", "TIME", "AFTER", "AT") if w in opts]
        if len(whens) > 1:
            raise CicsError(_msg("POST", "at_most_one", "INTERVAL", " and ".join(whens)))
        when = whens[0] if whens else "INTERVAL"
        hms = [o for o in ("HOURS", "MINUTES", "SECONDS") if o in opts]
        if (when in ("AFTER", "AT")) != bool(hms):
            raise CicsError(_msg("POST", "requires", "HOURS", when, " ".join(hms)))
        vals = [self._number(_arg(opts[o])) if o in opts else "null" for o in ("HOURS", "MINUTES", "SECONDS")]
        hhmmss = self._number(_arg(opts[when])) if when in ("INTERVAL", "TIME") and when in opts else "0"
        reqid = self.name(_arg(opts["REQID"])) if "REQID" in opts else "null"
        r = self.g.tmpname("post")
        out = [f'{ind}CicsTask.PostResult {r} = task.post("{when}", {hhmmss}, {", ".join(vals)}, {reqid});']
        if "SET" in opts:
            out.append(f"{ind}if ({r}.handle() != 0) DetCics.setPointer({self.pointer(opts['SET'])}, {r}.handle());")
        if "REQID" not in opts:
            out.append(f"{ind}if ({r}.handle() != 0) DetCics.putPadded({self.field('EIBREQID')}, {r}.reqid(), CS);")
        return [*out, *self.outcome(opts, f"DetCics.resp({r}.resp())", f"{r}.resp2()", ind)]

    def wait_event(self, opts: dict, ind: str) -> list[str]:
        """#5079 (X63): WAIT EVENT ECADDR(ptr) [NAME] (IBM CICS TS, EXEC CICS WAIT EVENT) on CicsTask.waitEvent: the area
        a POST made is posted at its expiry (the clock runs to it; a task takes no time, X4), so the task resumes at once;
        INVREQ RESP2 2 for a null pointer. An address that is no POST's area, or one a later POST / CANCEL / START /
        DELAY ended, is refused when it runs. NAME only labels the waiting task (INQUIRE TASK): it changes nothing."""
        from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError, _msg

        if not opts.get("ECADDR"):
            raise CicsError(_msg("WAIT EVENT", "required", "ECADDR"))
        r = self.g.tmpname("waited")
        return [f"{ind}int[] {r} = task.waitEvent(DetCics.pointerValue({self.pointer(opts['ECADDR'])}));",
                *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]  # fmt: skip

    def wait_external(self, key: str, opts: dict, ind: str) -> list[str]:
        """#5079 (X63): WAIT EXTERNAL / WAITCICS ECBLIST(ptr) NUMEVENTS(n) [NAME] [PURGEABLE | NOTPURGEABLE] (IBM CICS TS,
        EXEC CICS WAIT EXTERNAL / WAITCICS) on CicsTask.waitExternal: ECBLIST is a plain POINTER item whose handle addresses
        a task-storage block of NUMEVENTS 8-byte handles (a POINTER table over it, as the pointer lane keeps them). An ECB is
        posted when its first byte is X'40' (ASSUMED: IBM names no bit); a posted one returns NORMAL at once. INVREQ RESP2 2
        (WAIT EXTERNAL only) for a null ECBLIST, 3 NUMEVENTS not positive, 5 every address null. A list with no posted ECB
        is refused when it runs (nothing else runs to post one). NAME and PURGEABLE / NOTPURGEABLE change nothing here."""
        from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError, _arg, _msg

        for needed in ("ECBLIST", "NUMEVENTS"):
            if not opts.get(needed):
                raise CicsError(_msg(key, "required", needed))
        if "PURGEABLE" in opts and "NOTPURGEABLE" in opts:
            raise CicsError(_msg(key, "at_most_one", "PURGEABLE"))
        r = self.g.tmpname("waited")
        call = (f"task.waitExternal({'true' if key == 'WAITCICS' else 'false'}, "
                f"DetCics.pointerValue({self.pointer(opts['ECBLIST'])}), {self._number(_arg(opts['NUMEVENTS']))})")  # fmt: skip
        return [f"{ind}int[] {r} = {call};", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]

    def converse(self, opts: dict, ind: str) -> list[str]:
        """#5079 (X63): CONVERSE FROM [FROMLENGTH] INTO [TOLENGTH] [MAXLENGTH] [NOTRUNCATE] (IBM CICS TS, EXEC CICS CONVERSE
        (default)) on CicsTask.converse: the FROM data written to the terminal (what a plain SEND records: its first
        FROMLENGTH bytes, else FROM's length), then a terminal RECEIVE of the reply (as `receive`: the most taken is
        MAXLENGTH, else TOLENGTH's value, else INTO's length; TOLENGTH set to the reply's length, or the original length
        under LENGERR). LENGERR is the only condition IBM lists; the reply's EOC of an LUTYPE2 terminal is refused when it
        runs. A negative FROMLENGTH is LENGERR with nothing sent (ASSUMED). SET(pointer) puts the reply in a task-storage
        block as RECEIVE SET does (X58; needs TOLENGTH(data-area)); the conversation options are refused by name by the spec."""
        import re

        from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError, _arg, _msg, _one_of

        if not opts.get("FROM"):
            raise CicsError(_msg("CONVERSE", "required", "FROM"))
        if bool(opts.get("INTO")) == bool(opts.get("SET")):  # one of INTO / SET, not both, not neither
            raise CicsError(_msg("CONVERSE", "one_of", "INTO"))
        frm = _arg(opts["FROM"])
        sent = _one_of(opts, "FROMLENGTH", "FROMFLENGTH")
        length = _one_of(opts, "TOLENGTH", "TOFLENGTH")
        most = _one_of(opts, "MAXLENGTH", "MAXFLENGTH")
        settable = length is not None and re.fullmatch(r"(?is)[+-]?\d+|LENGTH\s+OF\s+.+", length.strip()) is None
        g = self.g
        n = self.int_(sent) if sent else str(self.size(frm))
        fixed = self.constant_int(sent) if sent else None
        t, r = g.tmpname("text"), g.tmpname("conversed")
        past = bool(sent) and not (fixed is not None and fixed <= self.size(frm))
        text = ('new String(DetCics.withinRecord({}, {}, "CONVERSE"), CS)' if past else "Cobol.text({}, CS)").format(
            self.read_field(frm), n
        )
        rec = g.record_bytes(self.ref(frm)) if past else None  # #6882: typed items in FROM's record packed first
        if opts.get("SET"):  # #5079 (X58): the reply in a block a pointer addresses, as RECEIVE SET(pointer)
            if not settable:
                raise CicsError("CONVERSE SET without TOLENGTH(data-area)")
            target = self.pointer(opts["SET"])
            limit = self.int_(most) if most else "Integer.MAX_VALUE"  # TOLENGTH is output-only with SET (X15)
            store = f'DetCics.setBlock(task, {target}, "RECEIVE", {r}.data(), CS);'
        else:
            target = self.field(opts["INTO"])
            limit = self.int_(most) if most else self.int_(length) if length else str(self.size(opts["INTO"]))
            store = f"DetCics.received({target}, {r}.data(), CS);"
        out = [*([f"{ind}Field {g.tmpname('rec')} = {rec};"] if rec else []),
               f"{ind}String {t} = {text};",
               (f"{ind}CicsTask.Received {r} = task.converse({t}.substring(0, Math.min({t}.length(), Math.max({n}, 0))), "
                f"{n}, {limit}, {str('NOTRUNCATE' in opts).lower()});"),
               f"{ind}if ({r}.data() != null) {store}"]  # fmt: skip
        if settable and length is not None:
            out.append(
                f"{ind}if ({r}.length() >= 0) "
                + g.store_into(self.ref(length), f"BigDecimal.valueOf({r}.length())", False)
            )
        return out + self.outcome(opts, f"DetCics.resp({r}.resp())", "0", ind)

    def cancel(self, opts: dict, ind: str) -> list[str]:
        """CANCEL REQID (IBM CICS TS, EXEC CICS CANCEL) on CicsTask.cancel: NORMAL for a request not yet expired,
        NOTFND when none matches "an unexpired interval control command"."""
        from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError, _msg, _option

        reqid = _option(opts, "REQID")
        if not reqid:
            raise CicsError(_msg("CANCEL", "required", "REQID"))
        r = self.g.tmpname("cancelled")
        return [f"{ind}int {r} = DetCics.resp(task.cancel({self.name(reqid)}));",
                *self.outcome(opts, r, "0", ind)]  # fmt: skip

    # -- #4413: terminal control without a map
    def send_control(self, opts: dict, ind: str) -> list[str]:
        """SEND CONTROL (IBM, EXEC CICS SEND CONTROL): device controls, recorded with CicsTask.sendControl. CURSOR
        names an offset ("a halfword binary value that specifies the cursor position relative to zero"); without
        one IBM documents no meaning (symbolic cursor positioning needs a map), so it is refused. No condition it
        documents arises on a plain terminal: NORMAL."""
        from gitgalaxy.tools.cobol_to_java.det.cics_common import _SEND_CONTROL, CicsError
        from gitgalaxy.tools.cobol_to_java.det.cics_common import jstr as G_jstr

        cursor = "null"
        if "CURSOR" in opts:
            if not opts["CURSOR"]:
                raise CicsError("SEND CONTROL CURSOR without a value: not modelled")
            cursor = self.int_(opts["CURSOR"])
        flags = [o for o in _SEND_CONTROL if o in opts]  # (sorted by the runtime)
        return [f"{ind}task.sendControl({cursor}{''.join(', ' + G_jstr(x) for x in sorted(flags))});",
                *self.outcome(opts, "0", "0", ind)]  # fmt: skip
