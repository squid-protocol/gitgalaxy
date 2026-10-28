"""#5274: the file-control family of the det CICS translator, split out of det/cics.py -- READ / READNEXT / READPREV /
STARTBR / RESETBR / ENDBR / WRITE / REWRITE / DELETE / UNLOCK onto CicsTask's files, including the RBA browse (#4213),
KEYLENGTH / GENERIC (#4411, #4270), the update TOKEN (#5078) and the generic delete (#4771). `Cics` inherits these
methods; its command dispatch and `command_key` stay the registry. The translator's shared helpers are imported inside
each method, as det/cics_containers.py does: a module-level import would close a cycle."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gitgalaxy.tools.cobol_to_java.det import expr as E


_TEMPLATE_WILD = r"@[^@.\s]+@|#+"


def has_template(names: Any) -> bool:
    """#4771: a stored CICS file named by a template (the CSD's `ZC@ID@FILE`, galaxy_ir's template join)."""
    return any("@" in n or "#" in n for n in names)


def file_key_call(names: Any, expr: str) -> str:
    """The Java expression a run-time file name is switched on: `fileKey(expr)` when a stored file is a template, else
    the name itself (a program with none keeps its text)."""
    return f"fileKey({expr})" if has_template(names) else expr


def file_key_method(names: Any) -> list[str]:
    """#4771: `fileKey(n)`, which maps a run-time file name (ZC01FILE) onto the template store that names it
    (ZC@ID@FILE): a name that is a store's own key stays, else the one template its characters fit. One shared store
    stands behind every instance (register X22 assumption)."""
    import re

    from gitgalaxy.tools.cobol_to_java.det.cics import G_jstr

    tpl = sorted(n for n in names if "@" in n or "#" in n)
    if not tpl:
        return []
    out = [
        "    private static String fileKey(String n) {",
        "        if (n == null) return n;",
        "        String t = n.stripTrailing();",
    ]
    for n in tpl:
        rx = "".join(".+" if m else re.escape(c) for c, m in _split(n))
        out.append(f"        if (t.matches({G_jstr(rx)})) return {G_jstr(n)};")
    out += ["        return n;", "    }", ""]
    return out


def _split(name: str) -> Iterator[tuple[str, bool]]:
    import re

    pos = 0
    for m in re.finditer(_TEMPLATE_WILD, name):
        for c in name[pos : m.start()]:
            yield c, False
        yield "", True
        pos = m.end()
    for c in name[pos:]:
        yield c, False


class FileControlCommands:
    """The file-control commands of `Cics` (det/cics.py), which defines the members declared below."""

    if TYPE_CHECKING:
        g: Any
        gp: Any
        region: str

        def ref(self, text: str) -> E.Ref: ...
        def name(self, text: str) -> str: ...
        def int_(self, text: str) -> str: ...
        def field(self, text: str) -> str: ...
        def read_field(self, text: str) -> str: ...
        def past_from(self, text: str, length: int | None) -> None: ...
        def size(self, text: str) -> int: ...
        def store(self, opts: dict) -> str: ...
        def constant(self, text: str | None) -> str | None: ...
        def constant_int(self, text: str) -> int | None: ...
        def pointer(self, text: str | None) -> str: ...
        def outcome(self, opts: dict, resp: str, resp2: str, ind: str) -> list[str]: ...

    # -- #4213: an ESDS browsed by relative byte address (IBM DBB EPSMLIST)
    def _rba(self, verb: str, opts: dict) -> bool:
        """Whether the command addresses its file by RBA; what is not modelled is a hole by name. Modelled: STARTBR /
        READNEXT / READPREV ... RBA (CicsTask's RBA browse, oracle_assumptions.md X13). XRBA, RRN, READ / WRITE / DELETE
        by RBA, and GTEQ / KEYLENGTH / GENERIC / REQID in an RBA browse are not (IBM: GTEQ "is not valid for directly
        browsing an ESDS")."""
        from gitgalaxy.tools.cobol_to_java.det.cics import CicsError

        for o in ("XRBA", "RRN"):
            if o in opts:
                raise CicsError(f"{verb} {o}: not modelled")
        if "RBA" not in opts:
            return False
        if verb not in ("STARTBR", "READNEXT", "READPREV"):
            raise CicsError(f"{verb} RBA: not modelled")
        for o in ("GTEQ", "KEYLENGTH", "GENERIC", "REQID"):
            if o in opts:
                raise CicsError(f"{verb} RBA {o}: not modelled")
        if self.size(opts["RIDFLD"]) < 4:
            raise CicsError(f"{verb} RBA: RIDFLD {opts['RIDFLD']} is shorter than the fullword an RBA is")
        return True

    def rba_browse(self, verb: str, opts: dict, ind: str) -> list[str]:
        from gitgalaxy.tools.cobol_to_java.det.cics import _arg

        file = self.name(_arg(opts.get("DATASET") or opts.get("FILE")))
        rid = self.field(opts["RIDFLD"])
        rba = f"CicsTask.rba(DetCics.bytes({rid}, 4))"
        if verb == "STARTBR":
            r = self.g.tmpname("resp")
            return [f"{ind}int {r} = task.startbrRba({file}, {rba});", *self.outcome(opts, r, "task.resp2()", ind)]
        r = self.g.tmpname("read")
        fn = "readnextRba" if verb == "READNEXT" else "readprevRba"
        into = self.field(opts["INTO"])
        return [f"{ind}CicsTask.BrowsedRba {r} = task.{fn}({file}, {rba}, {self.size(opts['INTO'])});",
                f"{ind}if ({r}.record() != null) {{",
                f"{ind}    DetCics.put({rid}, CicsTask.rbaBytes({r}.rba()));",
                f"{ind}    DetCics.put({into}, {r}.record());",
                f"{ind}}}",
                *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)]  # fmt: skip

    def _keylength(self, verb: str, opts: dict) -> int | None:
        """#4411: KEYLENGTH is honoured only as what it changes nothing for, the file's full key (a shorter one is a
        generic key, an unequal one INVREQ): a known value equal to the key's length, on a file the port knows.

        #4270 READ GENERIC (oracle_assumptions.md X22): the generic key's length -- a known value above zero and
        shorter than the key (IBM, EXEC CICS READ: INVREQ RESP2 25 for one "greater than or equal to the length of a
        full key", 42 below zero; zero undocumented), refused by name otherwise. Returns the length searched: the
        generic key's, else the full key's (None without KEYLENGTH)."""
        import re

        from gitgalaxy.tools.cobol_to_java.det.cics import CicsError, KeylengthInvreq, _arg

        generic = verb == "READ" and "GENERIC" in opts
        if "KEYLENGTH" not in opts:
            return None
        arg = _arg(opts["KEYLENGTH"])
        n = self.constant_int(arg)
        if n is None and re.fullmatch(r"-\s*\d+", arg.strip()):  # a negative literal (IBM: INVREQ 42 for GENERIC)
            n = -int(re.sub(r"\D", "", arg))
        name = self.constant(opts.get("DATASET") or opts.get("FILE"))
        mapped = self.gp.file(name) if name is not None else None
        if n is None or mapped is None:
            raise CicsError(f"{verb} KEYLENGTH({arg}): not a known length on a known file, so maybe not the full key")
        _, key = self.gp.entity_key(mapped[1], mapped[2])
        # #5092 (X52), IBM, EXEC CICS READ: INVREQ RESP2 25 GENERIC KEYLENGTH "greater than or equal to the length of a
        # full key", 42 "less than zero", 26 a KEYLENGTH without GENERIC that is not the key's length; zero is undocumented
        if generic and n < 0:
            raise KeylengthInvreq(f"{verb} GENERIC KEYLENGTH({arg}) = {n}: INVREQ (RESP2 42)", 42)
        if generic and n >= key:
            raise KeylengthInvreq(f"{verb} GENERIC KEYLENGTH({arg}) = {n}, the key is {key}: INVREQ (RESP2 25)", 25)
        if generic and n == 0:
            raise CicsError(f"{verb} GENERIC KEYLENGTH({arg}) = {n}: not above zero (INVREQ / undocumented)")
        if not generic and n != key:
            raise KeylengthInvreq(f"{verb} KEYLENGTH({arg}) = {n}, the key is {key}: INVREQ (RESP2 26)", 26)
        return n

    def _search(self, opts: dict, file: str, st: str, rec: str) -> tuple[str, str] | None:
        """#4270 READ GTEQ / GENERIC (oracle_assumptions.md X22): the read call and the held key's expression, None for
        a plain keyed READ. IBM, EXEC CICS READ: GENERIC -- "the search key is a generic key whose length is
        specified in the KEYLENGTH option"; GTEQ -- "if the search for a record that has the same key (complete or
        generic) ... is unsuccessful, the first record that has a greater key is retrieved"; NOTFND RESP2 80
        (CicsTask.readSearch). A READ UPDATE holds the record found (its key, not RIDFLD's)."""
        from gitgalaxy.tools.cobol_to_java.det.cics import CicsError, _arg, _msg

        gteq, generic = "GTEQ" in opts, "GENERIC" in opts
        if not (gteq or generic):
            return None
        if gteq and "EQUAL" in opts:
            raise CicsError(_msg("READ", "at_most_one", "EQUAL", "EQUAL", "GTEQ"))
        if generic and "KEYLENGTH" not in opts:
            raise CicsError(_msg("READ", "requires", "GENERIC"))
        n = self._keylength("READ", opts)
        rid = _arg(opts.get("RIDFLD"))
        gt = "true" if gteq else "false"
        update = "true" if "UPDATE" in opts and "TOKEN" not in opts else "false"  # a TOKEN read is held by its token
        if n is None:  # GTEQ on the full key: the file's
            name = self.constant(opts.get("DATASET") or opts.get("FILE"))
            if name is None:
                # #4771 (zECS FILE(ZF-FCT)): a file named at run time -- its key length is the one of the store that name
                # picks then; a name the project stores no file for is a Hole then, as store() makes it for every other
                # command on such a file; a RIDFLD shorter than that key is refused then, as below (X6)
                if not self.gp.files:
                    hole = f'throw new Hole("CICS file " + {file} + ": the program names no file the generated project stores");'
                    return f"task.readSearch({file}, {update}, () -> {{ {hole} }})", f"{st}.keyOf({{}}.record())"
                k = self.g.tmpname("keylen")
                search = (f"{{ int {k} = {self._runtime_keylength(file)}; if ({rec}.length < {k}) throw new "
                          f'DetCics.PastFrom("READ RIDFLD({rid}) shorter than the key searched: not modelled"); '
                          f"return {st}.search({rec}, {k}, {gt}); }}")  # fmt: skip
                return f"task.readSearch({file}, {update}, () -> {search})", f"{st}.keyOf({{}}.record())"
            mapped = self.gp.file(name) if name is not None else None
            if mapped is None:
                raise CicsError(
                    "READ GTEQ: not a known file, so not a known key length"
                    + f" (FILE {name!r} is no file the project stores)"
                )
            _, n = self.gp.entity_key(mapped[1], mapped[2])
        if self.size(rid) < n:  # CICS would read the storage after RIDFLD, laid out unlike IBM's by GnuCOBOL (X6)
            raise CicsError(f"READ RIDFLD({rid}) is {self.size(rid)} bytes, shorter than the {n} bytes searched")
        call = f"task.readSearch({file}, {update}, () -> {st}.search({rec}, {n}, {gt}))"
        return call, f"{st}.keyOf({{}}.record())"

    def _read_length(self, verb: str, opts: dict) -> str | None:
        """A read's LENGTH (IBM, EXEC CICS READ: "the length ... of the data area where the record is to be put. On
        completion ... the actual length of the record"; a longer record "is truncated", LENGERR RESP2 11).

        #4436: a keyed READ models it (DetCics.readInto): the LENGTH operand is returned for the code to emit, or None
        where it changes nothing -- a literal or LENGTH OF equal to INTO's own length, nothing to set back. READNEXT /
        READPREV and the RBA browse still honour only INTO's own length (#4411); any other is refused by name."""
        import re

        from gitgalaxy.tools.cobol_to_java.det.cics import CicsError, _arg

        if "LENGTH" not in opts:
            return None
        arg = _arg(opts["LENGTH"])
        n = self.constant_int(arg)
        into = self.size(_arg(opts.get("INTO")))
        fixed = re.fullmatch(r"(?is)\d+|LENGTH\s+OF\s+.+", arg.strip()) is not None
        if n is not None and n == into and (fixed or verb != "READ" or "RBA" in opts):
            return None
        if verb == "READ" and "RBA" not in opts:
            return arg
        raise CicsError(f"{verb} LENGTH({arg}): not INTO's length (LENGERR, the length read: not modelled)")

    def read(self, verb: str, opts: dict, ind: str) -> list[str]:
        """READ / READNEXT / READPREV. #5042 (X58) SET(pointer): the record in a new block of task storage the pointer
        addresses (DetCics.setBlock), valid -- IBM, EXEC CICS READ -- "until the next READ command for the same file or until
        completion of a corresponding REWRITE, DELETE, or UNLOCK command, or a SYNCPOINT in the case of READ UPDATE SET";
        READNEXT / READPREV: "until the next READNEXT or READPREV command specifies SET for the same browse (REQID) for the
        same file ... no longer valid after an ENDBR or SYNCPOINT" (CicsTask.acquireSet / invalidateSet). RBA, a LENGTH on
        a browse and a SET with INTO are refused by name; READ's LENGTH(data-area) is set to the record's length."""
        from gitgalaxy.tools.cobol_to_java.det.cics import CicsError, KeylengthInvreq, _arg, _msg

        if bool(opts.get("INTO")) == ("SET" in opts):
            raise CicsError(_msg(verb, "one_of", "INTO", verb))
        if "SET" in opts and ("RBA" in opts or "RRN" in opts or "XRBA" in opts):
            raise CicsError(
                f"{verb} SET with RBA / RRN / XRBA: not modelled (the block would hold a relative-byte record)"
            )
        if self._rba(verb, opts):
            self._read_length(verb, opts)
            return self.rba_browse(verb, opts, ind)
        searched = verb == "READ" and ("GTEQ" in opts or "GENERIC" in opts)
        if verb == "READ":
            try:
                self._keylength(verb, opts)
            except (
                KeylengthInvreq
            ) as bad:  # #5092 (X52): the read is not done: INVREQ with IBM's RESP2 (CicsTask.readInvalid)
                r = self.g.tmpname("read")
                file = self.name(_arg(opts.get("DATASET") or opts.get("FILE")))
                update = "true" if "UPDATE" in opts and "TOKEN" not in opts else "false"
                return [
                    f"{ind}CicsTask.FileRead<byte[]> {r} = task.readInvalid({file}, {update}, {bad.resp2});",
                    *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind),
                ]
        elif not searched:
            self._keylength(verb, opts)
        if "SET" in opts:
            return self.read_set(verb, opts, ind)
        length = self._read_length(verb, opts)
        st = self.store(opts)
        file = self.name(_arg(opts.get("DATASET") or opts.get("FILE")))
        into = self.field(opts["INTO"])
        rid = self.field(opts["RIDFLD"])
        if verb == "READ" and length is not None:
            return self.read_length(opts, length, file, st, into, rid, ind)
        g = self.g
        r, rec = g.tmpname("read"), g.tmpname("rec")
        if verb == "READ":
            fn = "readForUpdate" if "UPDATE" in opts and "TOKEN" not in opts else "read"  # TOKEN: held by the token
            call, held = f"task.{fn}({file}, () -> {st}.find({rec}))", rec
            search = self._search(opts, file, st, rec)
            if search is not None:
                call, held = search[0], search[1].format(r)
            out = [
                f"{ind}byte[] {rec} = DetCics.bytes({rid});",
                f"{ind}CicsTask.FileRead<byte[]> {r} = {call};",
                f"{ind}if ({r}.record() != null) {{",
                f"{ind}    DetCics.put({into}, {r}.record());",
                *([f"{ind}    heldKey.put({file}, {held});"] if "UPDATE" in opts and "TOKEN" not in opts else []),
                *self.token_out(opts, file, st, r, f"{ind}    "),
                f"{ind}}}",
            ]
            return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)
        fn = "readnext" if verb == "READNEXT" else "readprev"
        out = [f"{ind}CicsTask.Browsed {r} = task.{fn}({file}, new String(DetCics.bytes({rid}), CS));",
               f"{ind}if ({r}.normal()) {{",
               f"{ind}    DetCics.put({rid}, {r}.key().getBytes(CS));",
               f"{ind}    {st}.find({r}.key().getBytes(CS)).ifPresent(b -> DetCics.put({into}, b));",
               f"{ind}}}"]  # fmt: skip
        return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)

    def read_set(self, verb: str, opts: dict, ind: str) -> list[str]:
        """#5042 (X58): READ / READNEXT / READPREV SET(pointer): as the INTO form (the same store lookups, holds and
        tokens), but the record goes into a new block the pointer addresses. READ's LENGTH(data-area) is set to the
        record's length (IBM: "the LENGTH parameter contains the actual length of the record"); a LENGTH that is a
        literal, on a browse, or with a READ UPDATE LENGERR has nothing to say here and is refused."""
        import re

        from gitgalaxy.tools.cobol_to_java.det.cics import CicsError, _arg

        g = self.g
        ptr = self.pointer(opts["SET"])
        st = self.store(opts)
        file = self.name(_arg(opts.get("DATASET") or opts.get("FILE")))
        rid = self.field(opts["RIDFLD"])
        length = None
        if "LENGTH" in opts:
            arg = _arg(opts["LENGTH"])
            if verb != "READ" or re.fullmatch(r"(?is)[+-]?\d+|LENGTH\s+OF\s+.+", arg.strip()) is not None:
                raise CicsError(f"{verb} SET with LENGTH({arg}): only a data area on READ is modelled (it is set to the "
                                "record's length)")  # fmt: skip
            length = arg
        r, rec = g.tmpname("read"), g.tmpname("rec")
        if verb == "READ":
            update = "UPDATE" in opts or "TOKEN" in opts  # TOKEN implies UPDATE
            fn = "readForUpdate" if "UPDATE" in opts and "TOKEN" not in opts else "read"
            call, held = f"task.{fn}({file}, () -> {st}.find({rec}))", rec
            search = self._search(opts, file, st, rec)
            if search is not None:
                call, held = search[0], search[1].format(r)
            out = [f"{ind}byte[] {rec} = DetCics.bytes({rid});",
                   f"{ind}CicsTask.FileRead<byte[]> {r} = {call};",
                   f"{ind}if ({r}.record() != null) {{",
                   f'{ind}    DetCics.setBlock(task, {ptr}, "READ " + {file}, {r}.record(), {str(update).lower()});',
                   *([f"{ind}    heldKey.put({file}, {held});"] if "UPDATE" in opts and "TOKEN" not in opts else []),
                   *self.token_out(opts, file, st, r, f"{ind}    ")]  # fmt: skip
            if length is not None:
                out.append(
                    f"{ind}    " + g.store_into(self.ref(length), f"BigDecimal.valueOf({r}.record().length)", False)
                )
            out.append(f"{ind}}}")
            return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)
        fn = "readnext" if verb == "READNEXT" else "readprev"
        got = g.tmpname("rec")
        out = [f"{ind}CicsTask.Browsed {r} = task.{fn}({file}, new String(DetCics.bytes({rid}), CS));",
               f"{ind}if ({r}.normal()) {{",
               f"{ind}    DetCics.put({rid}, {r}.key().getBytes(CS));",
               f"{ind}    byte[] {got} = {st}.find({r}.key().getBytes(CS)).orElse(null);",
               f'{ind}    if ({got} != null) DetCics.setBlock(task, {ptr}, "BROWSE " + {file}, {got}, true);',
               f"{ind}}}"]  # fmt: skip
        return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)

    def token_out(self, opts: dict, file: str, st: str, r: str, ind: str) -> list[str]:
        """#5078 (X52): READ ... UPDATE TOKEN(d) -- the record read is held under a token (CicsTask.holdToken) that is
        stored into d, a fullword (IBM, EXEC CICS READ: "a unique identifier for this READ UPDATE request"; "If you
        specify TOKEN it implies update"). The key held is the record's own, as the stub holds it."""
        from gitgalaxy.tools.cobol_to_java.det.cics import CicsError, _arg

        if "TOKEN" not in opts:
            return []
        if not opts["TOKEN"]:
            raise CicsError("READ TOKEN needs a data area")
        tok = self.g.tmpname("tok")
        return [f"{ind}int {tok} = task.holdToken({file}, {st}.keyOf({r}.record()));",
                f"{ind}{self.g.store_into(self.ref(_arg(opts['TOKEN'])), f'BigDecimal.valueOf({tok})', False)}"]  # fmt: skip

    def read_length(self, opts: dict, length: str, file: str, st: str, into: str, rid: str, ind: str) -> list[str]:
        """#4436: READ ... INTO LENGTH(length). LENGTH's value is the most the program takes: the record goes INTO,
        truncated to it with LENGERR (22, RESP2 11) when longer, and LENGTH is set to the record's length (on NORMAL
        and LENGERR; a literal's or LENGTH OF's temporary is set by CICS and read by no one). What IBM leaves
        undocumented or the storage layout decides is refused at run time by DetCics.readInto (a negative LENGTH; a
        record moved past INTO; LENGERR on READ UPDATE -- whether the record is still held)."""
        import re

        g = self.g
        r, rec = g.tmpname("read"), g.tmpname("rec")
        resp, resp2 = g.tmpname("resp"), g.tmpname("resp2")
        update = "UPDATE" in opts or "TOKEN" in opts  # TOKEN implies UPDATE
        fn = "readForUpdate" if "UPDATE" in opts and "TOKEN" not in opts else "read"
        call, held = f"task.{fn}({file}, () -> {st}.find({rec}))", rec
        search = self._search(opts, file, st, rec)  # #4270: GTEQ / GENERIC
        if search is not None:
            call, held = search[0], search[1].format(r)
        settable = re.fullmatch(r"(?is)\d+|LENGTH\s+OF\s+.+", length.strip()) is None
        out = [f"{ind}byte[] {rec} = DetCics.bytes({rid});",
               f"{ind}CicsTask.FileRead<byte[]> {r} = {call};",
               f"{ind}int {resp} = {r}.resp();",
               f"{ind}int {resp2} = {r}.resp2();",
               f"{ind}if ({r}.record() != null) {{",
               f"{ind}    {resp} = DetCics.readInto({into}, {r}.record(), {self.int_(length)}, {str(update).lower()});",
               f"{ind}    {resp2} = {resp} == 22 ? 11 : 0;"]  # fmt: skip
        if update and "TOKEN" not in opts:
            out.append(f"{ind}    heldKey.put({file}, {held});")  # (LENGERR on READ UPDATE: refused above)
        out += self.token_out(opts, file, st, r, f"{ind}    ")
        if settable:
            set_back = g.store_into(self.ref(length), f"BigDecimal.valueOf({r}.record().length)", False)
            out.append(f"{ind}    {set_back}")
        out.append(f"{ind}}}")
        return out + self.outcome(opts, resp, resp2, ind)

    def record_from(self, opts: dict) -> str:
        """A WRITE / REWRITE's record: FROM's bytes, or LENGTH bytes from FROM's first (as CICS reads them)."""
        from gitgalaxy.tools.cobol_to_java.det.cics import _arg

        frm = self.read_field(opts["FROM"])
        if opts.get("LENGTH"):
            known = self.constant_int(_arg(opts["LENGTH"]))
            if known is None or known > self.size(_arg(opts["FROM"])):
                self.past_from(_arg(opts["FROM"]), known)  # #6072: the items after FROM it writes stay byte storage
            return f"DetCics.bytes({frm}, {self.int_(_arg(opts['LENGTH']))})"
        return f"DetCics.bytes({frm})"

    def _runtime_keylength(self, file: str) -> str:
        """#4771: the key length of the store a file name picks at run time (the project's stores, by name); a name it
        stores no file for is a Hole then, as store() makes it."""
        from gitgalaxy.tools.cobol_to_java.det.cics import G_jstr

        lengths = "; ".join(f"case {G_jstr(f)} -> {self.gp.entity_key(e, p)[1]}"
                            for f, (_repo, e, p) in self.gp.files.items())  # fmt: skip
        return (f'switch ({file_key_call(self.gp.files, file)}) {{ {lengths}; default -> throw new Hole("CICS file " + {file} + ": no store in the '
                f'generated project"); }}')  # fmt: skip

    def delete_generic(self, opts: dict, ind: str) -> list[str]:
        """#4771 (zECS ZECS003) DELETE GENERIC (IBM, EXEC CICS DELETE; register X22): every record whose key starts with
        RIDFLD's first KEYLENGTH bytes, NOTFND RESP2 80 when none does (CicsTask.deleteGeneric). #5092 (X22), IBM INVREQ
        RESP2: 42 a KEYLENGTH below zero, 25 one "greater than or equal to the length of a full key" (here when the file is
        known, at run time when it is named then), 22 on a file that is not a KSDS (CicsTask, at run time); zero is
        undocumented and refused by name."""
        import re

        from gitgalaxy.tools.cobol_to_java.det.cics import CicsError, _arg, _requires

        for o in ("KEYLENGTH", "RIDFLD"):
            if not opts.get(o):
                raise CicsError(_requires("DELETE", "GENERIC", o))
        arg = _arg(opts["KEYLENGTH"])
        n = self.constant_int(arg)
        if n is None and re.fullmatch(r"-\s*\d+", arg.strip()):  # a negative literal
            n = -int(re.sub(r"\D", "", arg))
        if n is None:
            raise CicsError(f"DELETE GENERIC KEYLENGTH({arg}): not a known length")
        if n == 0:
            raise CicsError(f"DELETE GENERIC KEYLENGTH({arg}) = {n}: not above zero (undocumented)")
        file = self.name(_arg(opts.get("DATASET") or opts.get("FILE")))
        name = self.constant(opts.get("DATASET") or opts.get("FILE"))
        g = self.g
        r = g.tmpname("resp")
        bad = 42 if n < 0 else None
        if name is not None and bad is None:
            mapped = self.gp.file(name)
            if mapped is None:
                raise CicsError(f"DELETE GENERIC: FILE {name!r} is no file the project stores, so not a known key")
            if n >= self.gp.entity_key(mapped[1], mapped[2])[1]:
                bad = 25
        if bad is not None:  # INVREQ: nothing is read from RIDFLD nor deleted (CicsTask.deleteInvalid)
            return [
                f"{ind}int {r} = task.deleteInvalid({file}, true, {bad});",
                *self.outcome(opts, r, "task.resp2()", ind),
            ]
        rid = _arg(opts["RIDFLD"])
        if self.size(rid) < n:  # CICS would read the storage after RIDFLD, laid out unlike IBM's by GnuCOBOL (X6)
            raise CicsError(f"DELETE RIDFLD({rid}) is {self.size(rid)} bytes, shorter than the {n}-byte generic key")
        st = self.store(opts)
        gk, found = g.tmpname("generic"), g.tmpname("found")
        out = [f"{ind}byte[] {gk} = DetCics.bytes({self.field(rid)});"]
        call = [f"task.deleteGeneric({file}, {st}.search({gk}, {n}, false).isPresent(), () -> {{",
                f"{ind}    java.util.Optional<byte[]> {found};",
                f"{ind}    while (({found} = {st}.search({gk}, {n}, false)).isPresent()) {st}.remove({st}.keyOf({found}.get()));",
                f"{ind}}})"]  # fmt: skip
        if name is None and self.gp.files:  # named at run time: the key of the store the name picks then
            out += [f"{ind}int {r};",
                    f"{ind}if ({n} >= {self._runtime_keylength(file)}) {r} = task.deleteInvalid({file}, true, 25);",
                    f"{ind}else {r} = {call[0]}", *call[1:-1], f"{call[-1]};"]  # fmt: skip
        else:
            out += [f"{ind}int {r} = {call[0]}", *call[1:-1], f"{call[-1]};"]
        return out + self.outcome(opts, r, "task.resp2()", ind)

    def token_update(self, verb: str, opts: dict, ind: str) -> list[str]:
        """#5078 (X52): REWRITE / DELETE / UNLOCK TOKEN(t) act on the record the READ UPDATE TOKEN that returned `t` holds
        (IBM). A token matching none in use is INVREQ RESP2 47 (CicsTask.rewriteToken / deleteToken / unlockToken)."""
        from gitgalaxy.tools.cobol_to_java.det.cics import CicsError, _arg, _msg

        if not opts["TOKEN"]:
            raise CicsError(f"{verb} TOKEN needs a value")
        if verb == "DELETE" and opts.get("RIDFLD"):
            raise CicsError(_msg("DELETE", "at_most_one", "RIDFLD", "RIDFLD", "TOKEN"))
        st = self.store(opts)
        file = self.name(_arg(opts.get("DATASET") or opts.get("FILE")))
        tok = self.int_(_arg(opts["TOKEN"]))
        r = self.g.tmpname("resp")
        if verb == "REWRITE":
            rec = self.g.tmpname("rec")
            out = [f"{ind}byte[] {rec} = {self.record_from(opts)};",
                   f"{ind}int {r} = task.rewriteToken({file}, {tok}, {st}.keyOf({rec}), () -> {st}.store({rec}));"]  # fmt: skip
        elif verb == "DELETE":
            out = [f"{ind}int {r} = task.deleteToken({file}, {tok}, k -> {st}.remove(k));"]
        else:  # UNLOCK
            out = [f"{ind}int {r} = task.unlockToken({file}, {tok});"]
        return out + self.outcome(opts, r, "task.resp2()", ind)

    def file_update(self, verb: str, opts: dict, ind: str) -> list[str]:
        from gitgalaxy.tools.cobol_to_java.det.cics import CicsError, KeylengthInvreq, _arg, _msg

        if self._rba(verb, opts):
            return self.rba_browse(verb, opts, ind)
        if verb == "DELETE" and "GENERIC" in opts:  # #4771
            if "TOKEN" in opts:
                raise CicsError(_msg("DELETE", "at_most_one", "GENERIC", "GENERIC", "TOKEN"))
            return self.delete_generic(opts, ind)
        if "TOKEN" in opts:  # #5078 (X52): the record a READ UPDATE TOKEN holds
            return self.token_update(verb, opts, ind)
        if verb == "UNLOCK":  # #5079 (X52): the file's tokenless hold
            file = self.name(_arg(opts.get("DATASET") or opts.get("FILE")))
            r = self.g.tmpname("resp")
            return [f"{ind}int {r} = task.unlockHeld({file});", *self.outcome(opts, r, "task.resp2()", ind)]
        if verb == "DELETE":
            try:
                self._keylength(verb, opts)
            except KeylengthInvreq as bad:  # #5092 (X22): IBM INVREQ 26, a KEYLENGTH that is not the key's length
                file = self.name(_arg(opts.get("DATASET") or opts.get("FILE")))
                r = self.g.tmpname("resp")
                return [f"{ind}int {r} = task.deleteInvalid({file}, false, {bad.resp2});",
                        *self.outcome(opts, r, "task.resp2()", ind)]  # fmt: skip
        else:
            self._keylength(verb, opts)
        st = self.store(opts)
        file = self.name(_arg(opts.get("DATASET") or opts.get("FILE")))
        g = self.g
        r = g.tmpname("resp")
        if verb == "WRITE":
            rid = self.field(opts["RIDFLD"])
            out = [f"{ind}int {r} = task.write({file}, {st}.exists(DetCics.bytes({rid})), "
                   f"() -> {st}.store({self.record_from(opts)}));"]  # fmt: skip
        elif verb == "REWRITE":
            out = [f"{ind}int {r} = task.rewrite({file}, () -> {st}.store({self.record_from(opts)}));"]
        elif verb == "DELETE":
            if opts.get("RIDFLD"):
                rid = self.field(opts["RIDFLD"])
                out = [f"{ind}int {r} = task.delete({file}, {st}.exists(DetCics.bytes({rid})), "
                       f"() -> {st}.remove(DetCics.bytes({rid})));"]  # fmt: skip
            else:
                held = g.tmpname("held")
                out = [f"{ind}byte[] {held} = heldKey.get({file});",
                       f"{ind}int {r} = task.deleteHeld({file}, () -> {st}.remove({held}));"]  # fmt: skip
        elif verb == "STARTBR":
            rid = self.field(opts["RIDFLD"])
            out = [f"{ind}int {r} = task.startbr({file}, new String(DetCics.bytes({rid}), CS), "
                   f"{'true' if 'EQUAL' in opts else 'false'}, () -> {st}.keys());"]  # fmt: skip
        else:  # ENDBR
            out = [f"{ind}int {r} = task.endbr({file});"]
        return out + self.outcome(opts, r, "task.resp2()", ind)  # #4657: IBM's RESP2 (CicsTask.resp2)
