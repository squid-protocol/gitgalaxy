"""#5274: the terminal commands: SEND TEXT / MAP / CONTROL, RECEIVE, RECEIVE MAP and INQUIRE / SET TERMINAL, split out of det/cics.py onto CicsTask. `Cics` inherits these methods, and its COMMAND_FAMILIES
registry calls `dispatch`. The translator's shared helpers come from det/cics_common.py (#7153)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from gitgalaxy.standards.cics.commands.send_text import TEXT_OPTIONS
from gitgalaxy.standards.cics.commands.terminal import MAP_OPTIONS
from gitgalaxy.tools.cobol_to_java.det import expr as E
from gitgalaxy.tools.cobol_to_java.det.cics_common import (
    CicsError,
    _arg,
    _msg,
    _one_of,
    jstr,
)


class TerminalCommands:
    """The terminal commands of `Cics` (det/cics.py), which defines the members declared below."""

    if TYPE_CHECKING:
        g: Any
        gp: Any
        generated: Any
        package: str
        region_used: bool
        passes_bytes: bool

        def __getattr__(self, name: str) -> Any: ...

    def dispatch(self, words: list[str], verb: str, key: str, opts: dict, ind: str) -> list[str] | None:  # noqa: ARG002
        """The terminal commands, or None for a command of another family."""
        g = self.g
        if verb == "SEND" and "MAP" in opts:
            return self.send_map(opts, ind)
        if verb == "SEND" or verb == "SEND TEXT":
            for o in ("CURSOR", "CTLCHAR"):  # (passed on as flags: a value would be dropped)
                if opts.get(o):
                    raise CicsError(f"SEND TEXT {o}({opts[o]}): its value is not modelled")
            f = self.read_field(_arg(opts["FROM"]))
            n = self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else str(self.size(_arg(opts["FROM"])))
            flags = [o for o in TEXT_OPTIONS if o in opts]
            t = g.tmpname("text")
            fixed_len = self.constant_int(_arg(opts["LENGTH"])) if opts.get("LENGTH") else None
            # #4270 (GenApp LGICVS01: FROM(WRITE-MSG-H) X(14) LENGTH(24)): CICS sends LENGTH bytes from FROM's first,
            # so a LENGTH past FROM sends the items after it in its record; past the record, refused (X6)
            past = bool(opts.get("LENGTH")) and not (
                fixed_len is not None and fixed_len <= self.size(_arg(opts["FROM"]))
            )
            text = (
                'new String(DetCics.withinRecord({}, {}, "SEND TEXT"), CS)' if past else "Cobol.text({}, CS)"
            ).format(f, n)
            # #6882: the bytes after FROM are its record's: typed items in it are packed into them first
            rec = g.record_bytes(self.ref(_arg(opts["FROM"]))) if past else None
            pl = g.tmpname("planned")  # #6271 (X71): a planned TSIOERR / INVREQ / LENGERR sends nothing
            return [*([f"{ind}Field {g.tmpname('rec')} = {rec};"] if rec else []),
                    f"{ind}String {t} = {text};",
                    f'{ind}int[] {pl} = task.planned("SEND-TEXT", "-");',
                    (f"{ind}if ({pl}[0] == 0) task.sendText({t}.substring(0, Math.min({t}.length(), {n})), {n}"
                     f"{''.join(', ' + jstr(x) for x in flags)});"),
                    *self.outcome(opts, f"{pl}[0]", f"{pl}[1]", ind)]  # fmt: skip
        if verb == "RECEIVE" and "MAP" in opts:
            return self.receive_map(opts, ind)
        if key in ("INQUIRE TERMINAL", "SET TERMINAL"):  # #4415 slice 1: the terminal's UCTRANST CVDA (register X26)
            if "UCTRANST" not in opts:
                raise CicsError(f"{key} without UCTRANST")
            r = g.tmpname("term")
            term = self.name(_arg(opts.get("TERMINAL")))
            if key == "SET TERMINAL":
                # #6882 (X26): a scenario's planned TERMIDERR / INVREQ answers instead and the SET is not performed
                return [f"{ind}int[] {r} = task.planned(\"SET-TERMINAL\", \"-\"); if ({r}[0] == 0) {r} = task.setUctranst({term}, {self.int_(_arg(opts['UCTRANST']))});",
                        *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]  # fmt: skip
            return [f"{ind}int[] {r} = task.planned(\"INQ-TERMINAL\", \"-\"); if ({r}[0] == 0) {r} = task.inquireUctranst({term});",
                    f"{ind}if ({r}[0] == 0) "
                    + g.store_into(self.ref(_arg(opts["UCTRANST"])), f"BigDecimal.valueOf({r}[2])", False),
                    *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]  # fmt: skip
        if verb == "SEND CONTROL":
            return self.send_control(opts, ind)
        if verb == "RECEIVE":
            return self.receive(opts, ind)
        return None

    def receive(self, opts: dict, ind: str) -> list[str]:
        """A terminal RECEIVE (IBM, EXEC CICS RECEIVE (3270 logical), (LUTYPE2/LUTYPE3)) on CicsTask.receive.

        INTO: the most taken is MAXLENGTH, else LENGTH's value, else INTO's length; the data goes into INTO's first
        bytes. SET(ADDRESS OF record): the LINKAGE record addresses the data (DetCics.receivedSet); it needs
        LENGTH(data-area). With SET, LENGTH is only an output (IBM: the data area "is set to the length of the data"), so
        without MAXLENGTH nothing bounds the data: the whole input comes back (an unbounded limit; X15). LENGTH / FLENGTH is set to the length the runtime returns (the data's, or under
        LENGERR the original length). LENGERR (22) and EOC (6, an LUTYPE2 terminal; ignored by default) go through
        RESP / HANDLE CONDITION like any condition."""
        length = _one_of(opts, "LENGTH", "FLENGTH")  # (FLENGTH / MAXFLENGTH: the fullword forms)
        most = _one_of(opts, "MAXLENGTH", "MAXFLENGTH")
        settable = length is not None and re.fullmatch(r"(?is)[+-]?\d+|LENGTH\s+OF\s+.+", length.strip()) is None
        g = self.g
        if opts.get("INTO") and "SET" not in opts:
            target = self.field(opts["INTO"])
            limit = self.int_(most) if most else self.int_(length) if length else str(self.size(opts["INTO"]))
            put = "received"
        elif opts.get("SET") and "INTO" not in opts:
            m = re.fullmatch(r"(?is)ADDRESS\s+OF\s+([A-Z0-9-]+)", opts["SET"].strip())
            if not settable:
                raise CicsError("RECEIVE SET without LENGTH(data-area)")
            limit = self.int_(most) if most else "Integer.MAX_VALUE"  # LENGTH is output-only with SET (X15)
            if m is None:  # #5042 (X58): SET(pointer): the data in a new block of task storage the pointer addresses
                target = self.pointer(opts["SET"])
                put = "setBlock"
            else:
                item = g.resolve(E.Ref(m.group(1).upper()))
                if getattr(item, "section", None) != "LINKAGE" or getattr(item, "level", None) != 1:
                    raise CicsError(f"RECEIVE SET(ADDRESS OF {m.group(1)}): not a LINKAGE 01 record")
                target = self.field(m.group(1))
                put = "receivedSet"
        else:
            raise CicsError(_msg("RECEIVE", "one_of", "INTO"))
        r = g.tmpname("received")
        store = (
            f'DetCics.setBlock(task, {target}, "RECEIVE", {r}.data(), CS);'
            if put == "setBlock"
            else f"DetCics.{put}({target}, {r}.data(), CS);"
        )
        out = [f"{ind}CicsTask.Received {r} = task.receive({limit}, {str('NOTRUNCATE' in opts).lower()});",
               f"{ind}{store}"]  # fmt: skip
        if settable and length is not None:
            out.append(ind + g.store_into(self.ref(length), f"BigDecimal.valueOf({r}.length())", False))
        return out + self.input_outcome(opts, f"DetCics.resp({r}.resp())", ind)

    def symbolic(self, map_name: str, suffix: str, name: str, record: str | None, k: int | None = None) -> str | None:
        """The symbolic map item <name><suffix> under `record` (COSGN0AI / COSGN0AO), or None. #5076 `k`: occurrence k
        of a repeated field (ACCOUNTO(3))."""
        for rec in [*([record] if record else []), map_name + "I", map_name + "O"]:
            found = self._field_or_none(name + suffix, rec, k)
            if found is not None:
                return found
        return None

    def _field_or_none(self, name: str, rec: str, subscript: int | None = None) -> str | None:
        try:
            return self.g.field_expr(E.Ref(name, [rec], [] if subscript is None else [E.Lit(E.NumLit(str(subscript)))]))
        except Exception:
            return None

    def map_names(self, opts: dict, area: str | None, suffix: str, ind: str) -> tuple[str, str, list[str]]:
        """(map, mapset, guard): constants; else the map whose symbolic record the FROM / INTO area is
        (CACTVWAO -> CACTVWA), the names checked at run time -- a different one is a hole, never a wrong screen."""
        # IBM CICS TS (BMS maps): a map / mapset name is 1-8 characters, blank-padded to 8 -- 'NBLKMAP ' IS NBLKMAP
        m = self.constant(opts["MAP"])
        ms = self.constant(opts.get("MAPSET") or opts["MAP"])
        m = m.rstrip(" ") if m is not None else None
        ms = ms.rstrip(" ") if ms is not None else None
        guard: list[str] = []
        if m is None and area is not None:
            name = self.ref(area).name
            if name.endswith(suffix) and name[:-1] in self.gp.screens:
                m = name[:-1]
                guard.append(f'{ind}if (!{self.name(opts["MAP"])}.equals({jstr(m)})) '
                             f'throw new Hole("MAP " + {self.name(opts["MAP"])} + ": not the map of {name}");')  # fmt: skip
        if ms is None and m is not None and opts.get("MAPSET"):
            cls = self.gp.screens.get(m)
            if cls is None:
                raise CicsError(f"no screen class for map {m}")
            ms_text = re.search(
                r'String MAPSET = "([^"]+)"', self.gp._file("dto/screen", cls).read_text(encoding="utf-8")
            )
            if ms_text:
                ms = ms_text.group(1)
                guard.append(f'{ind}if (!{self.name(opts["MAPSET"])}.equals({jstr(ms)})) '
                             f'throw new Hole("MAPSET " + {self.name(opts["MAPSET"])} + ": not {ms}");')  # fmt: skip
        if m is None or ms is None:
            raise CicsError("MAP / MAPSET not a constant, nor fixed by the symbolic map")
        return m, ms, guard

    def screen_slots(self, cls: str) -> list[tuple[str, int | None]]:
        """#5076: a screen class's fields as (name, occurrence): a repeated field once per occurrence (ACCOUNT, 3), any
        other once (COMPANY, None)."""
        repeated = self.gp.screen_occurs(cls)
        return [
            (n, k) for n in self.gp.screen_fields(cls) for k in (range(1, repeated[n] + 1) if n in repeated else [None])
        ]

    def no_screen(self, m: str) -> CicsError:
        """Why map `m` has no generated screen, by name (a map of no BMS source we hold)."""
        return CicsError(f"no generated screen for map {m}")

    def send_map(self, opts: dict, ind: str) -> list[str]:
        m, ms, guard = self.map_names(opts, opts.get("FROM"), "O", ind)
        cls = self.gp.screens.get(m)
        if cls is None:
            missing = self.map_not_found(m, ms, ind)
            if missing is not None:
                return [*guard, *missing]
            raise self.no_screen(m)
        self.used_screens.add(cls)
        frm = self.ref(opts["FROM"]).name if opts.get("FROM") else m + "O"
        v, sub, scr = self.g.tmpname("values"), self.g.tmpname("sub"), self.g.tmpname("screen")
        out = [*guard, f"{ind}java.util.Map<String, String> {v} = new java.util.LinkedHashMap<>();",
               f"{ind}CicsTask.MapSubfields {sub} = new CicsTask.MapSubfields();"]  # fmt: skip
        for name, k in self.screen_slots(cls):  # #5076: a repeated field's every occurrence, keyed NAME.k
            key = name if k is None else f"{name}.{k}"
            o = self.symbolic(m, "O", name, frm, k)
            if o is None:
                raise CicsError(f"map {m}: no {name}O" + ("" if k is None else f"({k})"))
            out.append(f"{ind}{v}.put({jstr(key)}, Cobol.text({o}, CS));")
            parts = [self.symbolic(m, s, name, None, k) for s in ("L", "A", "C", "H")]
            if parts[1] is None:
                parts[1] = self.symbolic(m, "F", name, None, k)
            out.append(f"{ind}DetCics.subfields({sub}, {jstr(key)}, "
                       f"{', '.join(p or 'null' for p in parts)}, CS);")  # fmt: skip
        if opts.get("CURSOR"):
            out.append(f"{ind}{sub}.cursorAt({self.int_(opts['CURSOR'])});")
        flags = [o for o in MAP_OPTIONS if o in opts]
        screen = "null" if "MAPONLY" in opts else f"{cls}.fromValues({v})"
        out.append(f"{ind}{cls} {scr} = {screen};")
        pl = self.g.tmpname("planned")  # #6271 (X71): a planned INVMPSZ / TSIOERR / INVREQ sends nothing
        out.append(f'{ind}int[] {pl} = task.planned("SEND-MAP", {jstr(m)});')
        out.append(f"{ind}if ({pl}[0] == 0) task.sendMap({jstr(m)}, {jstr(ms)}, {scr}, {sub}"
                   f"{''.join(', ' + jstr(x) for x in flags)});")  # fmt: skip
        return out + self.outcome(opts, f"{pl}[0]", f"{pl}[1]", ind)

    def receive_map(self, opts: dict, ind: str) -> list[str]:
        # #4737 (X28): ASIS -- IBM: "lowercase characters in the 3270 input data stream are not translated to uppercase".
        # The operator's input reaches the program as typed (CicsTask.receive), which is what ASIS asks for
        as_is = "ASIS" in opts  # noqa: F841  (the option is honoured by doing nothing: no translation exists to switch off)
        m, ms, guard = self.map_names(opts, opts.get("INTO"), "I", ind)
        cls = self.gp.screens.get(m)
        if cls is None:
            missing = self.map_not_found(m, ms, ind)
            if missing is not None:
                return [*guard, *missing]
            raise self.no_screen(m)
        into = self.ref(opts["INTO"]) if opts.get("INTO") else E.Ref(m + "I")
        fi = self.g.field_expr(into)
        r, vals, resp = self.g.tmpname("received"), self.g.tmpname("typed"), self.g.tmpname("resp")
        pl = self.g.tmpname("planned")  # #6271 (X71): a planned INVMPSZ / INVREQ receives nothing: INTO is untouched
        out = [*guard, f"{ind}int[] {pl} = task.planned(\"RECEIVE-MAP\", {jstr(m)});",
               (f"{ind}java.util.Optional<{cls}> {r} = {pl}[0] != 0 ? java.util.Optional.empty() "
                f": task.receive({jstr(m)}, {jstr(ms)}, {cls}.class);"),
               f"{ind}int {resp} = {pl}[0] != 0 ? {pl}[0] : {r}.isPresent() ? 0 : 36;", f"{ind}if ({r}.isPresent()) {{",
               (f"{ind}    java.util.Arrays.fill({fi}.storage().bytes, {fi}.offset(), {fi}.offset() + {fi}.length(), "
                "(byte) 0);"),
               f"{ind}    java.util.Map<String, String> {vals} = {r}.get().screenValues();"]  # fmt: skip
        justify = self.gp.screen_justify(cls)
        for name, k in self.screen_slots(cls):  # #5076: every occurrence of a repeated field, keyed NAME.k
            key = name if k is None else f"{name}.{k}"
            i = self.symbolic(m, "I", name, into.name, k)
            ln = self.symbolic(m, "L", name, into.name, k)
            if i is None:
                continue
            out.append(f"{ind}    if ({vals}.get({jstr(key)}) != null) {{")
            # #5082: IBM DFHMDF JUSTIFY -- the input right-justified / zero-filled as the field says; none: as typed
            tail = f", {jstr(justify[name])}" if name in justify else ""
            call = f"{self.package}.cobolrt.cics.DetJustify.place" if name in justify else "DetCics.typed"
            out.append(f"{ind}        {call}({i}, {ln or 'null'}, {vals}.get({jstr(key)}), CS{tail});")
            out.append(f"{ind}    }}")
        out.append(f"{ind}}}")
        return out + self.input_outcome(opts, resp, ind)
