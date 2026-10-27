"""#5274: the faults family of the det CICS translator, split out of det/cics.py -- the abend commands (HANDLE ABEND,
ABEND), the abend CICS raises for a map its mapset does not hold (ABM0, X31) and the check that follows a command an
injected abend may have unwound (#4534, #6271). `Cics` inherits these methods; its command dispatch stays the registry,
and `outcome` and the `handle_abend` flag stay there too (every family shares them). The translator's shared helpers
are imported inside each method, as det/cics_conditions.py does: a module-level import would close a cycle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gitgalaxy.tools.cobol_to_java.det import expr as E  # noqa: F401


class FaultCommands:
    """The abend commands of `Cics` (det/cics.py), which defines the members declared below."""

    if TYPE_CHECKING:
        g: Any
        gp: Any

        def name(self, text: str) -> str: ...

    def abend_exit(self, ind: str) -> list[str]:
        """What follows a command an abend may have hit: an abend below went to this program's exit (HANDLE ABEND), or
        unwound past this level (#4534)."""
        ex = self.g.tmpname("exit")
        return [f"{ind}String {ex} = task.abendExit();",
                f"{ind}if ({ex} != null) {self.g.jump(f'paragraph({ex})')}",
                f"{ind}if (task.ended()) throw abended();"]  # fmt: skip

    def handle_abend_(self, opts: dict, ind: str) -> list[str]:
        """HANDLE ABEND LABEL(label) | CANCEL | RESET (IBM, EXEC CICS HANDLE ABEND): the exit CicsTask runs on an abend."""
        from gitgalaxy.tools.cobol_to_java.det.cics import CicsError, G_jstr, _arg

        if "LABEL" in opts:
            label = _arg(opts["LABEL"]).upper()
            if label not in self.g.para_index:
                raise CicsError(f"HANDLE ABEND LABEL({label}): no such paragraph")
            return [f"{ind}task.handleAbend({G_jstr(label)});"]
        if "CANCEL" in opts:
            return [f"{ind}task.handleAbendCancel();"]
        if "RESET" in opts:
            return [f"{ind}task.handleAbendReset();"]
        raise CicsError("HANDLE ABEND without LABEL, CANCEL or RESET")

    def abend(self, opts: dict, ind: str) -> list[str]:
        """ABEND [ABCODE(code)] [CANCEL] (IBM, EXEC CICS ABEND): to the HANDLE ABEND exit, else the task ends."""
        from gitgalaxy.tools.cobol_to_java.det.cics import _arg

        code = self.name(_arg(opts["ABCODE"])) if opts.get("ABCODE") else '""'
        fn = "abendCancel" if "CANCEL" in opts else "abend"
        lbl = self.g.tmpname("exit")
        return [f"{ind}String {lbl} = task.{fn}({code});", f"{ind}if ({lbl} == null) throw abended();",
                f"{ind}if (true) {self.g.jump(f'paragraph({lbl})')}"]  # fmt: skip

    def map_not_found(self, m: str, ms: str, ind: str) -> list[str] | None:
        """IBM CICS TS (SEND MAP / RECEIVE MAP; abend code ABM0, register X31): a map is found only inside its own
        mapset (BMS: DFHMSD names the mapset, each DFHMDI a map; MAPSET defaults to the MAP name when omitted). A name
        that is a mapset of the estate but no map of it asks CICS for a map the mapset does not hold: ABM0, "The map
        specified for a basic mapping support (BMS) request could not be located", the transaction abnormally
        terminated. No condition is raised (neither command lists one), so RESP / HANDLE CONDITION do not see it; a
        HANDLE ABEND exit does -- the lines are EXEC CICS ABEND's, with the abend CICS raises. None: not that case."""
        from gitgalaxy.tools.cobol_to_java.det.cics import G_jstr

        if ms not in self.gp.mapsets or m in self.gp.mapsets[ms]:
            return None
        lbl = self.g.tmpname("exit")
        return [f"{ind}String {lbl} = task.abendMapNotFound({G_jstr(m)}, {G_jstr(ms)});",
                f"{ind}if ({lbl} == null) throw abended();",
                f"{ind}if (true) {self.g.jump(f'paragraph({lbl})')}"]  # fmt: skip
