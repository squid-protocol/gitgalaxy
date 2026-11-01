"""#5274: the storage commands: GETMAIN / FREEMAIN (#4771), LOAD / RELEASE (#6876) and ADDRESS (#5079), split out of det/cics.py onto CicsTask. `Cics` inherits these methods, and its COMMAND_FAMILIES
registry calls `dispatch`. The translator's shared helpers come from det/cics_common.py (#7153)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from gitgalaxy.tools.cobol_to_java.det import expr as E
from gitgalaxy.tools.cobol_to_java.det.cics_common import (
    CicsError,
    Untranslatable,
    _arg,
    _literal,
    _msg,
)


class StorageCommands:
    """The storage commands of `Cics` (det/cics.py), which defines the members declared below."""

    if TYPE_CHECKING:
        g: Any
        gp: Any
        generated: Any
        package: str
        region_used: bool
        passes_bytes: bool

        def __getattr__(self, name: str) -> Any:
            """The members `Cics` defines, for the type checker."""

    def dispatch_storage(self, words: list[str], verb: str, key: str, opts: dict, ind: str) -> list[str] | None:  # noqa: ARG002
        """The storage commands, or None for a command of another family."""
        if key in ("GETMAIN", "FREEMAIN"):  # #4771 (X47): task storage addressed by a pointer
            return self.storage(key, opts, ind)
        if key in ("LOAD", "RELEASE"):  # #6876 (X65): a program image addressed by a pointer
            return self.load_release(key, opts, ind)
        if key == "ADDRESS":  # #5079 (X59): a pointer to the EIB / the COMMAREA
            return self.address(opts, ind)
        return None

    def storage(self, key: str, opts: dict, ind: str) -> list[str]:
        """#4771 (X47): GETMAIN SET(ptr) FLENGTH / LENGTH [INITIMG(area)] and FREEMAIN DATAPOINTER(ptr) / DATA(record) on CicsTask's blocks
        of task storage (IBM, EXEC CICS GETMAIN / FREEMAIN). The pointer holds the block's handle; a LENGERR (RESP2 1)
        sets it to zero. INITIMG is a one-byte data area (IBM: "In COBOL, use a data area rather than a data value"). Without INITIMG (#6876) IBM gives the storage no contents: the run answers LENGERR for a length
        below 1 and refuses a valid one."""

        r = self.g.tmpname("storage")
        if key == "FREEMAIN":
            if opts.get("DATA") and opts.get("DATAPOINTER"):
                raise CicsError(_msg(key, "at_most_one", "DATAPOINTER"))
            if opts.get("DATA"):  # #6876 (X47): the storage a 01 LINKAGE record addresses (SET ADDRESS OF rec TO ptr)
                m = re.fullmatch(r"(?is)\s*([A-Z][A-Z0-9-]*)\s*", opts["DATA"])
                if m is None:
                    raise CicsError("FREEMAIN DATA: a data area is the COBOL form")
                try:
                    rec = self.g.address_record(m.group(1))
                except Untranslatable as e:
                    raise CicsError(str(e).replace("ADDRESS OF", "FREEMAIN DATA", 1)) from None
                return [f"{ind}int[] {r} = DetCics.freemainData(task, {rec});",
                        *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]  # fmt: skip
            if not opts.get("DATAPOINTER"):
                raise CicsError(_msg(key, "one_of", "DATAPOINTER"))
            ptr = self.pointer(opts["DATAPOINTER"])
            return [f"{ind}int[] {r} = task.freemain(DetCics.pointerValue({ptr}));",
                    *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]  # fmt: skip
        if not opts.get("SET"):
            raise CicsError(_msg(key, "required", "SET"))
        if ("FLENGTH" in opts) == ("LENGTH" in opts):
            raise CicsError(_msg(key, "one_of", "FLENGTH"))
        if "USERDATAKEY" in opts and "CICSDATAKEY" in opts:
            raise CicsError(_msg(key, "at_most_one", "USERDATAKEY"))
        img = opts.get("INITIMG")
        if img is not None:
            if _literal(img) is not None or not re.fullmatch(r"(?is)\s*[A-Z][A-Z0-9-]*\s*", img):
                raise CicsError("GETMAIN INITIMG as a literal: a data area is the COBOL form")
            if self.size(img) != 1:
                raise CicsError("GETMAIN INITIMG is not one byte")
        ptr = self.pointer(opts["SET"])
        form = "FLENGTH" if "FLENGTH" in opts else "LENGTH"
        if not opts.get(form):
            raise CicsError(f"{form} needs an argument")
        halfword = str(form == "LENGTH").lower()
        if img is None:  # #6876: IBM gives no default contents: LENGERR answers, a valid length is refused when it runs
            return [f"{ind}long[] {r}g = task.getmain({self.int_(opts[form])}, {halfword}, -1);",
                    f"{ind}DetCics.setPointer({ptr}, {r}g[2]);",
                    f"{ind}int[] {r} = new int[] {{(int) {r}g[0], (int) {r}g[1]}};",
                    *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]  # fmt: skip
        call = f"DetCics.getmain(task, {ptr}, {self.int_(opts[form])}, {halfword}, {self.read_field(opts['INITIMG'])})"
        return [f"{ind}int[] {r} = {call};", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]

    def load_release(self, key: str, opts: dict, ind: str) -> list[str]:
        """#6876 (X65): LOAD PROGRAM [SET(ptr)] [LENGTH(halfword)] and RELEASE PROGRAM on CicsTask's loaded programs (IBM, EXEC
        CICS LOAD / RELEASE). LOAD: PGMIDERR RESP2 1 for a program the CSD does not define (the pointer and LENGTH are then
        left alone); else the pointer holds the handle of a 256-byte image block and LENGTH its length (IBM states neither:
        the stub's values, ASSUMED). RELEASE: NORMAL once for a program this task loaded, INVREQ for one it did not (or
        released already), PGMIDERR RESP2 1 for an undefined one. A program that reads the image is refused when it runs."""
        if not opts.get("PROGRAM"):
            raise CicsError(_msg(key, "required", "PROGRAM"))
        prog = self.name(_arg(opts["PROGRAM"]))
        r = self.g.tmpname("load")
        if key == "RELEASE":
            return [f"{ind}int[] {r} = task.releaseProgram({prog});", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
        ptr = self.pointer(opts["SET"]) if opts.get("SET") else None
        out = [
            f"{ind}long[] {r}g = task.loadProgram({prog});",
            f"{ind}int[] {r} = new int[] {{(int) {r}g[0], (int) {r}g[1]}};",
        ]
        body: list[str] = []
        if ptr is not None:
            body.append(f"{ind}    DetCics.setPointer({ptr}, {r}g[2]);")
        if opts.get("LENGTH"):
            body.append(
                f"{ind}    " + self.g.store_into(self.ref(_arg(opts["LENGTH"])), f"BigDecimal.valueOf({r}g[3])", False)
            )
        if body:
            out += [f"{ind}if ({r}[0] == 0) {{", *body, f"{ind}}}"]
        return [*out, *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]

    def address(self, opts: dict, ind: str) -> list[str]:
        """#5079 (X59): ADDRESS EIB(ptr) / COMMAREA(ptr) (IBM, EXEC CICS ADDRESS: "a pointer reference set to the address of
        the EXEC interface block" / "of the communication area (COMMAREA) available to the currently executing program").
        The pointer holds the handle of the record's own bytes (DetCics.setPointerToRecord), so SET ADDRESS OF rec TO ptr
        shares them: a later EIB update shows through it. COMMAREA needs the program's 01 DFHCOMMAREA to address: a task with
        none (EIBCALEN 0) gets IBM's X'FF000000' (no COBOL NULL; the program's `PIC X(4)` byte view tests it,
        DetCics.isNoCommareaAddress), and a program with no 01 DFHCOMMAREA run with a COMMAREA is refused when it runs. The command has no
        condition: NORMAL. TWA / TCTUA (#5079 slice 2) set the pointer to the handle of the transaction work area / the
        terminal's user area the definitions size (TWASIZE / USERAREALEN), or X'FF000000' when none (DetCics.addressTwa /
        addressTctua). CWA (slice 2a) is the region's common work area, SIT WRKAREA bytes shared by every task, or X'FF000000' when the
        case states none (DetCics.addressCwa). ACEE and ADDRESS SET are refused by the spec entry (check_options)."""

        if not any(opts.get(o) for o in ("EIB", "COMMAREA", "CWA", "TWA", "TCTUA")):
            raise CicsError("ADDRESS without an area option: the pointer to set")
        out: list[str] = []
        for option in ("EIB", "COMMAREA", "CWA", "TWA", "TCTUA"):
            if option not in opts:
                continue
            ptr = self.pointer(opts[option])
            if option in ("CWA", "TWA", "TCTUA"):
                out.append(f"{ind}DetCics.address{option.capitalize()}(task, {ptr});")
                continue
            if option == "EIB":
                out.append(f"{ind}DetCics.setPointerToRecord(task, {ptr}, {self.g.field_expr(E.Ref('DFHEIBLK'))});")
                continue
            try:
                rec = self.g.address_record("DFHCOMMAREA")
            except Untranslatable:
                # #6876 (X59): no 01 DFHCOMMAREA, so no storage to address a COMMAREA through: a task with none (EIBCALEN 0)
                # gets IBM's X'FF000000' (the byte view the program tests), a task with one is refused when it runs
                out.append(f"{ind}DetCics.addressNoCommarea(task, {ptr}, {self.int_('EIBCALEN')});")
                continue
            out.append(f"{ind}DetCics.addressCommarea(task, {ptr}, {rec}, {self.int_('EIBCALEN')});")
        return [*out, *self.outcome(opts, "0", "0", ind)]
