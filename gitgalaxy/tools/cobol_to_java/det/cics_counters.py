"""#5274: the named counter commands: GET / DEFINE / DELETE / QUERY / REWIND / UPDATE COUNTER and DCOUNTER (#4270, #4770, #5039), split out of det/cics.py onto CicsTask. `Cics` inherits these methods, and its COMMAND_FAMILIES
registry calls `dispatch`. The translator's shared helpers come from det/cics_common.py (#7153)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gitgalaxy.standards.cics.commands.api import COUNTER
from gitgalaxy.tools.cobol_to_java.det.cics_common import (
    CicsError,
    _arg,
    _msg,
    _requires,
)


class CounterCommands:
    """The named counter commands of `Cics` (det/cics.py), which defines the members declared below."""

    if TYPE_CHECKING:
        g: Any
        gp: Any
        generated: Any
        package: str
        region_used: bool
        passes_bytes: bool

        def __getattr__(self, name: str) -> Any: ...

    def dispatch(self, words: list[str], verb: str, key: str, opts: dict, ind: str) -> list[str] | None:  # noqa: ARG002
        """The named counter commands; any other command naming a counter is refused here, or None for a command of another family."""
        if verb == "GET" and ("COUNTER" in opts or "DCOUNTER" in opts):
            # GET COUNTER: its value, then +1; INVREQ RESP2 201 for a counter not defined (X30). #4767 (X30) GET DCOUNTER
            # INCREMENT(n) [WRAP]: the value, then +n (the doubleword form; WRAP acts at a maximum the run does not state)
            if not opts.get("VALUE"):
                raise CicsError(_msg("GET COUNTER", "required", "VALUE"))
            if ("COUNTER" in opts) == ("DCOUNTER" in opts):
                raise CicsError(_msg("GET COUNTER", "one_of", "COUNTER"))
            v = self.g.tmpname("counter")
            pool = self.name(_arg(opts["POOL"])) if opts.get("POOL") else '""'
            nm = self.name(_arg(opts.get("COUNTER") or opts["DCOUNTER"]))
            # #4770 (X45): INCREMENT is an unsigned doubleword and WRAP acts at a DEFINE DCOUNTER counter's maximum; the VALUE
            # of a doubleword counter is unsigned too (a 64-bit value past 2**63 is not a negative number)
            inc = f", {self.long_(_arg(opts['INCREMENT']))}" if opts.get("INCREMENT") else ""
            if "REDUCE" in opts or opts.get("COMPAREMIN") or opts.get("COMPAREMAX"):
                # #5039 (X53): REDUCE, COMPAREMIN / COMPAREMAX (the bounds the value handed out must meet; null: not given)
                bound = lambda o: f"Long.valueOf({self.long_(_arg(opts[o]))})" if opts.get(o) else "null"  # noqa: E731
                inc = (f"{inc or ', 1L'}, {'true' if 'WRAP' in opts else 'false'}, {'true' if 'REDUCE' in opts else 'false'}, "
                       f"{bound('COMPAREMIN')}, {bound('COMPAREMAX')}, {'true' if 'COUNTER' in opts else 'false'}")  # fmt: skip
            elif "WRAP" in opts:
                inc = f"{inc or ', 1L'}, true"
            val = (
                f"new BigDecimal(Long.toUnsignedString({v}[2]))"
                if "DCOUNTER" in opts
                else f"BigDecimal.valueOf({v}[2])"
            )
            full = (
                "COUNTER" in opts
            )  # #4770 (X30): a fullword GET of a counter past 31 bits is LENGERR with the low 32 bits
            return [f"{ind}long[] {v} = task.getCounter({pool}, {nm}{inc});",
                    *([f"{ind}{v} = task.fullwordGet({pool}, {nm}, {v});"] if full else []),
                    f"{ind}if ({v}[0] == 0{' || ' + v + '[0] == 22' if full else ''}) {{",
                    ind + "    " + self.g.store_into(self.ref(_arg(opts["VALUE"])), val, False),
                    f"{ind}}}",
                    *self.outcome(opts, f"(int) {v}[0]", f"(int) {v}[1]", ind)]  # fmt: skip
        if verb in ("DEFINE", "DELETE", "QUERY") and ("COUNTER" in opts or "DCOUNTER" in opts):
            # #4770 (X45), #5039 (X50): the spec's groups, for the commands that take both forms
            if ("COUNTER" in opts) == ("DCOUNTER" in opts):
                raise CicsError(_msg(f"{verb} COUNTER", "one_of", "COUNTER"))
            if verb == "DEFINE" and opts.get("MINIMUM") and not opts.get("VALUE"):
                raise CicsError(_requires("DEFINE COUNTER", "MINIMUM", "VALUE"))
        if verb in ("DEFINE", "DELETE") and (
            "COUNTER" in opts or "DCOUNTER" in opts
        ):  # #4270 (X30): the region's named counters
            v = self.g.tmpname("counter")
            pool = self.name(_arg(opts["POOL"])) if opts.get("POOL") else '""'
            nm = self.name(_arg(opts.get("COUNTER") or opts["DCOUNTER"]))
            if verb == "DELETE":
                call = f"task.deleteCounter({pool}, {nm})"
            elif (
                "DCOUNTER" in opts
            ):  # #4770 (X45): doubleword limits; IBM's defaults MINIMUM zero, MAXIMUM a doubleword of X'FF'
                val = self.long_(_arg(opts["VALUE"])) if opts.get("VALUE") else "0L"
                lo = self.long_(_arg(opts["MINIMUM"])) if opts.get("MINIMUM") else "0L"
                hi = self.long_(_arg(opts["MAXIMUM"])) if opts.get("MAXIMUM") else "-1L"
                call = f"task.defineDcounter({pool}, {nm}, {val}, {lo}, {hi})"
            else:  # #5039 (X50): fullword limits; IBM's defaults MINIMUM zero, MAXIMUM X'7FFFFFFF' (2147483647)
                val = self.int_(_arg(opts["VALUE"])) if opts.get("VALUE") else "0"
                lo = self.int_(_arg(opts["MINIMUM"])) if opts.get("MINIMUM") else "0"
                hi = self.int_(_arg(opts["MAXIMUM"])) if opts.get("MAXIMUM") else "2147483647"
                call = f"task.defineCounter({pool}, {nm}, {val}, {lo}, {hi})"
            return [f"{ind}int[] {v} = {call};", *self.outcome(opts, f"{v}[0]", f"{v}[1]", ind)]
        if verb == "QUERY" and "DCOUNTER" in opts:  # #4770 (X45): value and limits, unsigned doublewords
            v = self.g.tmpname("counter")
            pool = self.name(_arg(opts["POOL"])) if opts.get("POOL") else '""'
            limits = "true" if opts.get("MINIMUM") or opts.get("MAXIMUM") else "false"
            lines = [
                f"{ind}long[] {v} = task.queryDcounter({pool}, {self.name(_arg(opts['DCOUNTER']))}, {limits});",
                f"{ind}if ({v}[0] == 0 || {v}[0] == 22) {{",
            ]  # fmt: skip  (#4770: LENGERR still writes the low 32 bits)
            for o, i in (("VALUE", 2), ("MINIMUM", 3), ("MAXIMUM", 4)):
                if opts.get(o):
                    lines.append(
                        ind
                        + "    "
                        + self.g.store_into(
                            self.ref(_arg(opts[o])), f"new BigDecimal(Long.toUnsignedString({v}[{i}]))", False
                        )
                    )
            return [*lines, f"{ind}}}", *self.outcome(opts, f"(int) {v}[0]", f"(int) {v}[1]", ind)]
        if verb == "QUERY" and "COUNTER" in opts:  # #5039 (X50): value and limits, fullwords
            v = self.g.tmpname("counter")
            pool = self.name(_arg(opts["POOL"])) if opts.get("POOL") else '""'
            limits = "true" if opts.get("MINIMUM") or opts.get("MAXIMUM") else "false"
            lines = [
                f"{ind}int[] {v} = task.queryCounter({pool}, {self.name(_arg(opts['COUNTER']))}, {limits});",
                f"{ind}if ({v}[0] == 0 || {v}[0] == 22) {{",
            ]  # fmt: skip  (#4770: LENGERR still writes the low 32 bits)
            for o, i in (("VALUE", 2), ("MINIMUM", 3), ("MAXIMUM", 4)):
                if opts.get(o):
                    lines.append(
                        ind
                        + "    "
                        + self.g.store_into(self.ref(_arg(opts[o])), f"BigDecimal.valueOf({v}[{i}])", False)
                    )
            return [*lines, f"{ind}}}", *self.outcome(opts, f"{v}[0]", f"{v}[1]", ind)]
        if verb in ("REWIND", "UPDATE") and ("COUNTER" in opts or "DCOUNTER" in opts):
            # #5039 (X53): the spec's groups, then CicsTask.rewindCounter / updateCounter
            if ("COUNTER" in opts) == ("DCOUNTER" in opts):
                raise CicsError(_msg(f"{verb} COUNTER", "one_of", "COUNTER"))
            v = self.g.tmpname("counter")
            pool = self.name(_arg(opts["POOL"])) if opts.get("POOL") else '""'
            nm = self.name(_arg(opts.get("COUNTER") or opts["DCOUNTER"]))
            if verb == "REWIND":
                inc = self.long_(_arg(opts["INCREMENT"])) if opts.get("INCREMENT") else "1L"
                call = f"task.rewindCounter({pool}, {nm}, {inc})"
            else:
                if not opts.get("VALUE"):
                    raise CicsError(_msg("UPDATE COUNTER", "required", "VALUE"))
                call = f"task.updateCounter({pool}, {nm}, {self.long_(_arg(opts['VALUE']))}, {'true' if 'COUNTER' in opts else 'false'})"
            return [f"{ind}int[] {v} = {call};", *self.outcome(opts, f"{v}[0]", f"{v}[1]", ind)]
        if "COUNTER" in opts or "DCOUNTER" in opts:
            # any other named-counter command: not modelled
            raise CicsError(f"{verb} COUNTER: {COUNTER}")
        return None
