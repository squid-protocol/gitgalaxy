"""#5274: the conditions family of the det CICS translator, split out of det/cics.py -- ASSIGN, the conditions a HANDLE /
IGNORE CONDITION names, HANDLE AID, PUSH / POP HANDLE and the AID transfer after an input command (#4414, #4270). `Cics`
inherits these methods; its command dispatch and `command_key` stay the registry. The translator's shared helpers come from
det/cics_common.py (#7153): importing them back from det/cics.py closed an import cycle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gitgalaxy.standards.cics.commands.assign import TERMINAL_OPTIONS
from gitgalaxy.standards.cics.commands.handles import AID_KEYS
from gitgalaxy.standards.cics.resp import DFHRESP
from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError, _arg, jstr

if TYPE_CHECKING:
    from gitgalaxy.tools.cobol_to_java.det import expr as E


class ConditionCommands:
    """The condition, handler and ASSIGN commands of `Cics` (det/cics.py), which defines the members declared below."""

    if TYPE_CHECKING:
        g: Any
        handle_aid: bool

        def ref(self, text: str) -> E.Ref: ...
        def field(self, text: str) -> str: ...
        def outcome(self, opts: dict, resp: str, resp2: str, ind: str) -> list[str]: ...

    def assign(self, opts: dict, ind: str) -> list[str]:
        """ASSIGN (IBM CICS TS, EXEC CICS ASSIGN): each option's value into its data area. #4270 slice 3: STARTCODE /
        USERID from what the harness states (CicsTask.withStartcode / withUserid); FACILITY, SCRNHT, SCRNWD from the
        task's terminal -- for a task with none, INVREQ RESP2 5 ("The task is not associated with a terminal; or the
        task has no principal facility"), and then no data area is written (IBM does not say what the others hold:
        register X19). Without a FACILITY / SCRNHT / SCRNWD, ASSIGN raises no condition: RESP is NORMAL."""

        stores = []
        for k, v in opts.items():
            if k in ("RESP", "RESP2", "NOHANDLE"):
                continue
            if k in ("SCRNHT", "SCRNWD"):  # a halfword binary
                n = f"BigDecimal.valueOf(task.assignScreen({'true' if k == 'SCRNWD' else 'false'}))"
                stores.append(self.g.store_into(self.ref(_arg(v)), n, False))
                continue
            src = {"APPLID": "task.assignApplid()", "SYSID": "task.assignSysid()", "ABCODE": "task.abcode()",
                   # the running program's own name, 8 characters
                   "PROGRAM": jstr(f"{self.g.p.name[:8]:<8}"),
                   "INVOKINGPROG": "task.invokingProgram()",
                   "CHANNEL": "task.assignChannel()",  # #4270: 16 characters, blanks without one
                   "STARTCODE": "task.assignStartcode()", "USERID": "task.assignUserid()",
                   "FACILITY": "task.assignFacility()"}.get(k)  # fmt: skip
            if src is None:
                raise CicsError(f"ASSIGN {k}")
            stores.append(f"DetCics.putText({self.field(_arg(v))}, {src}, CS);")
        if not any(k in opts for k in TERMINAL_OPTIONS):  # INVREQ RESP2 5 without a terminal (raised_by)
            return [ind + x for x in stores] + (
                self.outcome(opts, "0", "0", ind) if "RESP" in opts or "RESP2" in opts else []
            )
        r = self.g.tmpname("assign")
        return ([f"{ind}int {r} = task.assignTerminalResp();", f"{ind}if ({r} == 0) {{"]
                + [f"{ind}    {x}" for x in stores] + [f"{ind}}}"]
                + self.outcome(opts, r, f"({r} == 0 ? 0 : 5)", ind))  # fmt: skip

    def conditions(self, verb: str, opts: dict, ignore: bool = False) -> list[str]:
        """The conditions a HANDLE / IGNORE CONDITION names: each one IBM documents (DFHRESP), never NORMAL. IGNORE
        CONDITION names no label (IBM, EXEC CICS IGNORE CONDITION: "condition -- the name of the condition to be
        ignored"). IGNORE CONDITION ERROR is refused: IBM's HANDLE CONDITION takes "the action for ERROR" for a
        condition with no action of its own whose default is an abend, but does not say whether an IGNORE of ERROR is
        such an action (docs/language_status/oracle_assumptions.md X16)."""

        for cond, label in opts.items():
            if cond not in DFHRESP or cond == "NORMAL":
                raise CicsError(f"{verb} {cond}: not a documented condition")
            if ignore and label is not None:
                raise CicsError(f"{verb} {cond}({label}): IGNORE CONDITION names no label")
            if ignore and cond == "ERROR":
                raise CicsError("IGNORE CONDITION ERROR: whether ERROR's action can be to ignore is not documented")
        return list(opts)

    def handle_aid_(self, opts: dict, ind: str) -> list[str]:
        """HANDLE AID key(label) ... (IBM, EXEC CICS HANDLE AID): each key's label, taken after an input command
        (input_outcome); a key with no label is deactivated ("To ignore an AID, issue a HANDLE AID command that
        specifies the associated option without a label"). Only the attention keys: RESP / NOHANDLE are refused too
        (no key; HANDLE AID raises no condition here)."""

        out = []
        for key, label in opts.items():
            if key not in AID_KEYS:
                raise CicsError(f"HANDLE AID {key}: not an attention key")
            if label is None:  # (-1: deactivated, which DetCics.aidLabel tells from never handled)
                out.append(f"{ind}aids.put({jstr(key)}, -1);")
                continue
            if label.upper() not in self.g.para_index:
                raise CicsError(f"HANDLE AID {key}({label}): no such paragraph")
            out.append(f"{ind}aids.put({jstr(key)}, {self.g.para_index[label.upper()]});")
        return out

    def push_pop(self, verb: str, opts: dict, ind: str) -> list[str]:
        """PUSH HANDLE suspends the program's HANDLE CONDITION, IGNORE CONDITION, HANDLE AID and HANDLE ABEND state;
        POP HANDLE restores the one last pushed, INVREQ when none was (IBM, EXEC CICS PUSH HANDLE / POP HANDLE). The
        HANDLE ABEND part is CicsTask's (pushHandle / popHandle), the rest the program's own (handlers, aids)."""
        r = self.g.tmpname("resp")
        if verb == "PUSH HANDLE":
            out = [f"{ind}pushed.push(new DetCics.Handlers(handlers, aids));",
                   f"{ind}handlers.clear();", f"{ind}aids.clear();",
                   f"{ind}int {r} = DetCics.resp(task.pushHandle());"]  # fmt: skip
        else:
            out = [f"{ind}int {r} = DetCics.resp(task.popHandle());",
                   f"{ind}if ({r} == 0) {{",
                   f"{ind}    pushed.pop().restore(handlers, aids);",
                   f"{ind}}}"]  # fmt: skip
        return out + self.outcome(opts, r, "0", ind)

    def input_outcome(self, opts: dict, resp: str, ind: str) -> list[str]:
        """#4414: after an input command (RECEIVE MAP, terminal RECEIVE): its outcome, then -- in a program that
        issues HANDLE AID, unless RESP or NOHANDLE ("no action is to be taken for any condition or attention
        identifier (AID)") -- the label of the key pressed, else ANYKEY's for a PA / PF key or CLEAR ("Control is
        passed after the input command is completed"). Which comes first when the command also raised a condition
        is not documented: the program's aid() refuses that before the condition is acted on (X16)."""
        if not self.handle_aid or "RESP" in opts or "NOHANDLE" in opts:
            return self.outcome(opts, resp, "0", ind)
        to = self.g.tmpname("aidTo")
        return [f"{ind}aid({resp});", *self.outcome(opts, resp, "0", ind),
                f"{ind}int {to} = aid({resp});", f"{ind}if ({to} >= 0) {self.g.jump(to)}"]  # fmt: skip
