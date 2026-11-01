"""#5274: the queue commands: transient data (WRITEQ / READQ / DELETEQ TD, INQUIRE / SET TDQUEUE) and temporary storage, split out of det/cics.py onto CicsTask. `Cics` inherits these methods, and its COMMAND_FAMILIES
registry calls `dispatch`. The translator's shared helpers come from det/cics_common.py (#7153)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from gitgalaxy.tools.cobol_to_java.det.cics_common import (
    CicsError,
    _arg,
    _msg,
    _requires,
)


class QueueCommands:
    """The queue commands of `Cics` (det/cics.py), which defines the members declared below."""

    if TYPE_CHECKING:
        g: Any
        gp: Any
        generated: Any
        package: str
        region_used: bool
        passes_bytes: bool

        def __getattr__(self, name: str) -> Any:
            """The members `Cics` defines, for the type checker."""

    def dispatch_queues(self, words: list[str], verb: str, key: str, opts: dict, ind: str) -> list[str] | None:
        """The queue commands, or None for a command of another family."""
        g = self.g
        if key in (
            "INQUIRE TDQUEUE",
            "SET TDQUEUE",
        ):  # #5168 rounds 3, 5 (X61, X66): an extrapartition queue's open state, a queue's availability
            if not opts.get("TDQUEUE"):
                raise CicsError(_msg(key, "required", "TDQUEUE"))
            r = g.tmpname("tdq")
            queue = self.name(_arg(opts["TDQUEUE"]))
            if key == "SET TDQUEUE":
                given = [o for o in ("OPENSTATUS", "ENABLESTATUS", "TRIGGERLEVEL") if opts.get(o)]
                if len(given) > 1:
                    raise CicsError(f"SET TDQUEUE with {' and '.join(given)} together: not modelled")
                if not given:
                    raise CicsError(_requires(key, "TDQUEUE", "OPENSTATUS"))
                o = given[0]
                call = {
                    "ENABLESTATUS": "setTdQueueEnableStatus",
                    "OPENSTATUS": "setTdQueueOpenStatus",
                    "TRIGGERLEVEL": "setTdQueueTriggerLevel",  # #5168 round 7 (X66)
                }[o]
                return [f"{ind}int[] {r} = task.{call}({queue}, {self.int_(_arg(opts[o]))});",
                        *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]  # fmt: skip
            order = ("OPENSTATUS", "TYPE", "ENABLESTATUS", "TRIGGERLEVEL", "RECOVSTATUS", "TRANSID")
            wanted = [o for o in order if opts.get(o)]
            if not wanted:
                raise CicsError(_requires(key, "TDQUEUE", "OPENSTATUS"))
            # the 3-argument call (the round 3 shape) unless ENABLESTATUS is asked for; the 6-argument one (round 6) for the ATI options
            width = (
                6 if {"TRIGGERLEVEL", "RECOVSTATUS", "TRANSID"} & set(wanted) else 3 if "ENABLESTATUS" in wanted else 2
            )
            wants = ", ".join(str(o in wanted).lower() for o in order[:width])
            lines = [f"{ind}int[] {r} = task.inquireTdQueue({queue}, {wants});", f"{ind}if ({r}[0] == 0) {{"]
            for o, i in (("OPENSTATUS", 2), ("TYPE", 3), ("ENABLESTATUS", 4), ("TRIGGERLEVEL", 5), ("RECOVSTATUS", 6)):
                if o in wanted:
                    lines.append(
                        ind + "    " + g.store_into(self.ref(_arg(opts[o])), f"BigDecimal.valueOf({r}[{i}])", False)
                    )
            if "TRANSID" in wanted:
                lines.append(f"{ind}    Cobol.move(task.tdTransid({queue}), {self.field(_arg(opts['TRANSID']))}, CS);")
            return [*lines, f"{ind}}}", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
        if verb == "WRITEQ TD":
            r = g.tmpname("resp")
            f = self.read_field(_arg(opts["FROM"]))
            if opts.get("LENGTH"):  # X6 (ASSUMED): a LENGTH past FROM writes FROM's bytes then spaces, as the stub does
                data = f'new String(DetCics.padded({f}, {self.int_(_arg(opts["LENGTH"]))}, "WRITEQ TD", CS), CS)'
            else:
                data = f"Cobol.text({f}, CS)"
            return [f"{ind}int {r} = task.writeqTd({self.name(_arg(opts['QUEUE']))}, {data});",
                    *self.outcome(opts, r, "0", ind)]  # fmt: skip
        if verb == "DELETEQ TD":  # #5079 (X57): every record of an intrapartition queue
            r = g.tmpname("resp")
            return [f"{ind}int {r} = task.deleteqTd({self.name(_arg(opts['QUEUE']))});",
                    *self.outcome(opts, r, "0", ind)]  # fmt: skip
        if verb == "READQ TD":
            return self.readq_td(opts, ind)
        if verb in ("WRITEQ TS", "WRITEQ", "READQ TS", "READQ", "DELETEQ TS", "DELETEQ") \
                and verb.startswith(("WRITEQ", "READQ", "DELETEQ")) and "TD" not in words:  # fmt: skip
            return self.ts_queue(verb.split()[0], opts, ind)
        return None

    def readq_td(self, opts: dict, ind: str) -> list[str]:
        """#5079 (X57): READQ TD QUEUE INTO [LENGTH] -- a destructive read of the task's intrapartition queue. The record
        goes INTO as the program's own text (a WRITEQ TD wrote it so); a record moved past INTO is refused at run time
        (DetCics.readTd), as READ INTO's is. LENGTH(data-area) is set to the record's length on NORMAL and LENGERR.
        #5168: SET(pointer) LENGTH(data-area) puts the record in a new block, valid to the next READQ TD; NOSUSPEND
        is passed on: only a planned QBUSY (another task writing a LOGICAL queue) reads it."""
        g = self.g
        r = g.tmpname("td")
        setp = opts.get("SET")
        if setp:
            if opts.get("INTO"):
                raise CicsError(_msg("READQ TD", "at_most_one", "INTO"))
            if not opts.get("LENGTH"):
                raise CicsError(_msg("READQ TD", "requires", "SET"))
            if re.fullmatch(r"(?is)\d+|LENGTH\s+OF\s+.+", opts["LENGTH"].strip()) is not None:
                raise CicsError("READQ TD SET with a literal LENGTH: IBM says LENGTH must then be a data area")
            ptr = self.pointer(setp)
            into, maxlen = None, "Integer.MAX_VALUE"  # IBM gives SET no most: LENGTH is only set
        else:
            into = self.field(_arg(opts["INTO"]))
            maxlen = self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else f"{into}.length()"
        nos = ", true" if "NOSUSPEND" in opts else ""
        out = [f"{ind}CicsTask.TdResult {r} = task.readqTd({self.name(_arg(opts['QUEUE']))}, {maxlen}{nos});"]
        if setp:
            out.append(f'{ind}if ({r}.data() != null) DetCics.setBlock(task, {ptr}, "READQ TD", {r}.data(), CS);')
        else:
            out.append(f"{ind}if ({r}.data() != null) DetCics.readTd({into}, {r}.data().getBytes(CS));")
        if opts.get("LENGTH") and re.fullmatch(r"(?is)\d+|LENGTH\s+OF\s+.+", opts["LENGTH"].strip()) is None:
            out.append(f"{ind}if ({r}.length() >= 0) Cobol.store({self.field(_arg(opts['LENGTH']))}, "
                       f"BigDecimal.valueOf({r}.length()), false, CS);")  # fmt: skip
        return out + self.outcome(opts, f"{r}.resp()", "0", ind)

    def ts_queue(self, verb: str, opts: dict, ind: str) -> list[str]:
        """WRITEQ TS / READQ TS on the task's temporary storage (CicsTask): an item is the program's own bytes in the
        region's code page (#4528: REGION, region_page) -- written from the storage's page (CS) and read back into
        it, character by character, as the COBOL side's region moves them."""
        q = opts.get("QUEUE") or opts.get("QNAME")
        if q is None:
            raise CicsError(_msg(f"{verb} TS", "one_of", "QUEUE"))
        queue = self.name(q)
        g = self.g
        r = g.tmpname("ts")
        out: list[str] = []
        self.region_used = True
        if verb == "DELETEQ":  # #4415 slice 2 (X29): the whole queue; QIDERR for one that does not exist
            return [f"{ind}int {r} = task.deleteqTs({queue});", *self.outcome(opts, r, "0", ind)]
        if verb == "WRITEQ":
            f = self.read_field(_arg(opts.get("FROM")))
            if opts.get("LENGTH"):  # X6 (ASSUMED): a LENGTH past FROM writes FROM's bytes then spaces, as the stub does
                body = f'DetCics.padded({f}, {self.int_(_arg(opts["LENGTH"]))}, "WRITEQ TS", CS)'
            else:
                body = f"DetCics.bytes({f}, {f}.length())"
            # #4528: the item in the region's page, as the COBOL side's region keeps it
            data = f"DetCics.toRegion({body}, CS, REGION)"
            if "REWRITE" in opts:
                out.append(
                    f"{ind}CicsTask.TsResult {r} = task.rewriteqTs({queue}, {self.int_(_arg(opts.get('ITEM')))}, {data});"
                )
            else:
                out.append(f"{ind}CicsTask.TsResult {r} = task.writeqTs({queue}, {data});")
                if opts.get("ITEM"):  # the item number assigned
                    out.append(
                        f"{ind}Cobol.store({self.field(_arg(opts['ITEM']))}, BigDecimal.valueOf({r}.item()), false, CS);"
                    )
        else:
            setp = opts.get("SET")
            if setp:  # #5042 (X58): SET(pointer) LENGTH(data-area): the item in a new block, valid to the next READQ TS
                if opts.get("INTO"):
                    raise CicsError(_msg("READQ TS", "at_most_one", "INTO"))
                if not opts.get("LENGTH"):
                    raise CicsError(_msg("READQ TS", "requires", "SET"))
                if re.fullmatch(r"(?is)\d+|LENGTH\s+OF\s+.+", opts["LENGTH"].strip()) is not None:
                    raise CicsError("READQ TS SET with a literal LENGTH: IBM says LENGTH must then be a data area")
                ptr = self.pointer(setp)
                into, maxlen = None, "Integer.MAX_VALUE"  # IBM gives SET no most: LENGTH is only set
            else:
                into = self.field(_arg(opts.get("INTO")))
                maxlen = self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else f"{into}.length()"
            if "NEXT" in opts or not opts.get("ITEM"):
                out.append(f"{ind}CicsTask.TsResult {r} = task.readqTsNext({queue}, {maxlen});")
            else:
                out.append(
                    f"{ind}CicsTask.TsResult {r} = task.readqTs({queue}, {self.int_(_arg(opts['ITEM']))}, {maxlen});"
                )
            if setp:
                out.append(f'{ind}if ({r}.data() != null) DetCics.setBlock(task, {ptr}, "READQ", '
                           f"DetCics.fromRegion({r}.data(), REGION, CS));")  # fmt: skip
            else:
                out.append(
                    f"{ind}if ({r}.data() != null) DetCics.put({into}, DetCics.fromRegion({r}.data(), REGION, CS));"
                )
            # #4737: LENGTH(LENGTH OF x) / a literal is the most the program takes; CICS's length goes to a temporary
            if opts.get("LENGTH") and re.fullmatch(r"(?is)\d+|LENGTH\s+OF\s+.+", opts["LENGTH"].strip()) is None:
                out.append(f"{ind}if ({r}.length() >= 0) Cobol.store({self.field(_arg(opts['LENGTH']))}, "
                           f"BigDecimal.valueOf({r}.length()), false, CS);")  # fmt: skip
            if opts.get("ITEM") and "NEXT" in opts:
                out.append(
                    f"{ind}Cobol.store({self.field(_arg(opts['ITEM']))}, BigDecimal.valueOf({r}.item()), false, CS);"
                )
        if opts.get("NUMITEMS"):
            out.append(
                f"{ind}Cobol.store({self.field(_arg(opts['NUMITEMS']))}, BigDecimal.valueOf({r}.numItems()), false, CS);"
            )
        return out + self.outcome(opts, f"DetCics.resp({r}.resp())", "0", ind)
