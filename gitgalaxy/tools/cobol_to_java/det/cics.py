"""EXEC CICS commands of a deterministic port, onto the generated project's CicsTask.

Every typed object at the boundary is the generator's: the COMMAREA DTOs (dto/contract, each property's comment
naming its COBOL field, PICTURE and offset), the screen view models (dto/screen: fromValues / screenValues by BMS
field name), and the entities of each CICS file (the stub's "<DSN> as CICS file <NAME>" methods). The port converts
between them and the program's own bytes -- nothing is taken from a test case."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from gitgalaxy.tools.cobol_to_java.det import expr as E
from gitgalaxy.tools.cobol_to_java.det import layout as L

COPY = Path(__file__).parent / "copy"  # DFHEIBLK, DFHAID, DFHBMSCA

# IBM CICS TS, RESP values (DFHRESP)
DFHRESP = {"NORMAL": 0, "ERROR": 1, "EOF": 4, "EODS": 5, "EOC": 6, "INBFMH": 7, "ENDINPT": 8, "NONVAL": 9,
           "NOSTART": 10, "TERMIDERR": 11, "FILENOTFOUND": 12, "NOTFND": 13, "DUPREC": 14, "DUPKEY": 15,
           "INVREQ": 16, "IOERR": 17, "NOSPACE": 18, "NOTOPEN": 19, "ENDFILE": 20, "ILLOGIC": 21, "LENGERR": 22,
           "QZERO": 23, "SIGNAL": 24, "QBUSY": 25, "ITEMERR": 26, "PGMIDERR": 27, "TRANSIDERR": 28,
           "ENDDATA": 29, "INVTSREQ": 30, "EXPIRED": 31, "RETPAGE": 32, "RTEFAIL": 33, "RTESOME": 34,
           "TSIOERR": 35, "MAPFAIL": 36, "INVERRTERM": 37, "INVMPSZ": 38, "IGREQID": 39, "OVERFLOW": 40,
           "INVLDC": 41, "NOSTG": 42, "JIDERR": 43, "QIDERR": 44, "NOJBUFSP": 45, "DSSTAT": 46, "SELNERR": 47,
           "FUNCERR": 48, "UNEXPIN": 49, "NOPASSBKRD": 50, "NOPASSBKWR": 51, "SYSIDERR": 53, "ISCINVREQ": 54,
           "ENQBUSY": 55, "ENVDEFERR": 56, "IGREQCD": 57, "SESSIONERR": 58, "SYSBUSY": 59, "SESSBUSY": 60,
           "NOTALLOC": 61, "CBIDERR": 62, "INVEXITREQ": 63, "INVPARTNSET": 64, "INVPARTN": 65,
           "PARTNFAIL": 66, "USERIDERR": 69, "NOTAUTH": 70, "VOLIDERR": 71, "SUPPRESSED": 72, "RESIDERR": 75,
           "NOSPOOL": 80, "TERMERR": 81, "ROLLEDBACK": 82, "END": 83, "DISABLED": 84, "ALLOCERR": 85,
           "STRELERR": 86, "OPENERR": 87, "SPOLBUSY": 88, "SPOLERR": 89, "NODEIDERR": 90, "TASKIDERR": 91,
           "TCIDERR": 92, "DSNNOTFOUND": 93, "LOADING": 94, "MODELIDERR": 95, "OUTDESCRERR": 96,
           "PARTNERIDERR": 97, "PROFILEIDERR": 98, "NETNAMEIDERR": 99, "LOCKED": 100, "RECORDBUSY": 101,
           "UOWNOTFOUND": 102, "UOWLNOTFOUND": 103,
           # IBM CICS TS API Reference, RESP values (BUSY 128 / INCOMPLETE 126 in its SPI table; the others as the
           # equivalence harness's own table, tests/tools/equivalence_cics.py, which agrees on every shared name)
           "RDATT": 2, "WRBRK": 3, "DSIDERR": 12, "CHANNELERR": 122, "CCSIDERR": 123, "TIMEDOUT": 124,
           "CODEPAGEERR": 125, "INCOMPLETE": 126, "APPNOTFOUND": 127, "BUSY": 128}  # fmt: skip

MAP_OPTIONS = ("ERASE", "ERASEAUP", "FREEKB", "ALARM", "CURSOR", "FRSET", "MAPONLY", "DATAONLY", "PRINT", "LAST",
               "WAIT", "ACCUM", "PAGING", "TERMINAL", "NLEOM", "FORMFEED")  # fmt: skip
TEXT_OPTIONS = ("ERASE", "FREEKB", "ALARM", "CURSOR", "PRINT", "LAST", "WAIT", "INVITE", "DEFRESP", "STRFIELD",
                "CTLCHAR")  # fmt: skip


class CicsError(Exception):
    pass


# ---- the EXEC text ----------------------------------------------------------------------------------------------
def _arg(v: str | None) -> str:
    """An EXEC CICS option's argument text; a bare option where one is needed is an error."""
    if v is None:
        raise CicsError("EXEC CICS option needs an argument")
    return v


def parse_exec(text: str) -> tuple[list[str], dict[str, str | None]]:
    """EXEC CICS VERB [VERB2] OPT(arg) OPT ... END-EXEC -> ([verb words], {option: arg text or None})."""
    body = re.sub(r"(?is)^\s*EXEC\s+CICS\s+|\s*END-EXEC\s*\.?\s*$", "", text).strip()
    words: list[str] = []
    opts: dict[str, str | None] = {}
    i = 0
    while i < len(body):
        if body[i].isspace():
            i += 1
            continue
        m = re.match(r"[A-Za-z0-9-]+", body[i:])
        if not m:
            raise CicsError(f"cannot read {body[i : i + 20]!r}")
        name = m.group(0).upper()
        i += m.end()
        j = i
        while j < len(body) and body[j].isspace():
            j += 1
        if j < len(body) and body[j] == "(":
            depth, k, quote = 0, j, None
            while k < len(body):
                ch = body[k]
                if quote:
                    if ch == quote:
                        quote = None
                elif ch in "'\"":
                    quote = ch
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            opts[name] = body[j + 1 : k].strip()
            i = k + 1
        elif not opts and len(words) < 2 and name not in MAP_OPTIONS:
            words.append(name)
        else:
            opts[name] = None
    return words, opts


# ---- the generated DTOs ----------------------------------------------------------------------------------------
_PROP = re.compile(r"//\s*(.+?)\n\s*private\s+([\w.<>]+)\s+(\w+);")
_LEAF = re.compile(r"([A-Z0-9-]+):\s*PIC\s+(\S+?)(?:\s+(COMP-3|COMP-5|COMP-4|COMP|BINARY|PACKED-DECIMAL|DISPLAY))?,"
                   r"\s*offset\s+(\d+),\s*(\d+)\s+bytes(?:\s*\(([^)]+)\))?")  # fmt: skip
_PART = re.compile(r"offset\s+(\d+),\s*(\d+)\s+bytes\s*->\s*([A-Z0-9-]+)")


@dataclass
class Leaf:
    var: str
    jtype: str
    cobol: str
    pic: str
    usage: str
    offset: int
    size: int
    source: str | None = None  # the copybook the generator read the field from


@dataclass
class Dto:
    cls: str
    leaves: list = field(default_factory=list)
    parts: list = field(default_factory=list)  # (var, Dto, offset)

    @property
    def size(self) -> int:
        n = max((x.offset + x.size for x in self.leaves), default=0)
        return max([n] + [off + p.size for _, p, off in self.parts])


class Generated:
    """What the generated project says about one program's CICS boundary."""

    def __init__(self, project: Path, stub: str):
        self.java = project / "src/main/java"
        self.dtos: dict[str, Dto] = {}
        self.contract = None
        m = re.search(r"handleTransaction\(String transid, (\w+) request\)", stub)
        if m:
            self.contract = m.group(1)
        else:  # a program only ever LINKed to (CBSA's): its COMMAREA is handleLink's
            m = re.search(r"public \w+ handleLink\((\w+) request\)", stub)
            if m:
                self.contract = m.group(1)
        # LINK targets: link<Program>(Type request), as the stub types each (local or distributed)
        self.links = {mm.group(1).upper(): mm.group(2)
                      for mm in re.finditer(r"public \w+ link(\w+)\((\w+) request\)", stub)}  # fmt: skip
        self.xctl = {mm.group(1).upper(): mm.group(2)
                     for mm in re.finditer(r"public \w+ xctl(\w+)\((\w+) request\)", stub)}  # fmt: skip
        self.files: dict[str, tuple[str, str, str | None]] = {}  # CICS file -> (repository, entity, findBy prop)
        self.inferred: list[str] = []
        self._map_files(stub, self.files)
        # a file this program's stub does not map (it only WRITEs it, say): the repository every other program's
        # stub binds that CICS file name to, when they agree
        self.estate_files: dict[str, set] = {}
        for p in sorted(self.java.rglob("service/*Service.java")):
            got: dict[str, tuple] = {}
            self._map_files(p.read_text(encoding="utf-8"), got)
            for k, v in got.items():
                self.estate_files.setdefault(k, set()).add(v)
        self.screens: dict[str, str] = {}
        for p in sorted(self.java.rglob("dto/screen/*Screen.java")):
            mm = re.search(r'String MAP = "([^"]+)"', p.read_text(encoding="utf-8"))
            if mm:
                self.screens[mm.group(1).upper()] = p.stem
        self.records: dict[str, str] = {}  # COBOL record -> its contract DTO
        for p in sorted(self.java.rglob("dto/contract/*.java")):
            mm = re.search(r"COBOL record ([A-Z0-9-]+) \(", p.read_text(encoding="utf-8"))
            if mm:
                self.records.setdefault(mm.group(1), p.stem)

    def file(self, name: str) -> tuple | None:
        if name in self.files:
            return self.files[name]
        cands = self.estate_files.get(name, set())
        if len(cands) == 1:
            self.inferred.append(f"CICS file {name} -> {next(iter(cands))[0]}: as the estate's other programs bind it")
            self.files[name] = next(iter(cands))
            return self.files[name]
        return None

    @staticmethod
    def _map_files(stub: str, files: dict) -> None:
        for mm in re.finditer(r"as CICS file (\S+) at .*?\*/(.*?)(?=/\*\*|\Z)", stub, re.S):
            body = mm.group(2)
            r = re.search(r"\b(\w+Repository)\.(\w+)\(", body)
            ent = re.search(r"(?:Optional|List)<(\w+)>", body)
            if r and ent:
                # an alternate index: findBy<Property>(key); a browse (findBy...GreaterThanEqual...OrderBy...) and
                # findById are the base cluster's key
                alt = re.fullmatch(r"findBy([A-Z]\w*)", r.group(2))
                prop = (
                    alt.group(1)
                    if alt
                    and not (alt.group(1) == "Id" or re.search(r"GreaterThan|LessThan|OrderBy|Between", alt.group(1)))
                    else None
                )
                name = mm.group(1).upper()
                if name not in files or prop is None:
                    files[name] = (r.group(1), ent.group(1), prop[0].lower() + prop[1:] if prop else None)

    def _file(self, kind: str, cls: str) -> Path:
        hits = list(self.java.rglob(f"{kind}/{cls}.java"))
        if len(hits) != 1:
            raise CicsError(f"no generated {kind} class {cls}")
        return hits[0]

    def dto(self, cls: str) -> Dto:
        if cls in self.dtos:
            return self.dtos[cls]
        d = Dto(cls)
        for comment, jtype, var in _PROP.findall(self._file("dto/contract", cls).read_text(encoding="utf-8")):
            part = _PART.search(comment)
            if part:
                d.parts.append((var, self.dto(jtype), int(part.group(1))))
                continue
            leaf = _LEAF.search(comment)
            if not leaf or jtype not in ("String", "Integer", "Long", "Short", "BigDecimal", "java.math.BigDecimal"):
                raise CicsError(f"{cls}.{var}: a property the port cannot convert ({jtype})")
            d.leaves.append(Leaf(var, jtype, leaf.group(1), leaf.group(2), (leaf.group(3) or "DISPLAY").upper(),
                                 int(leaf.group(4)), int(leaf.group(5)), leaf.group(6)))  # fmt: skip
        self.dtos[cls] = d
        return d

    def entity_key(self, entity: str, prop: str | None) -> tuple[int, int]:
        text = self._file("entity/vsam", entity).read_text(encoding="utf-8")
        if prop is None:
            m = re.search(r"Key: .*?\(offset (\d+), (\d+) bytes", text)
            if not m:
                raise CicsError(f"{entity}: no key")
            return int(m.group(1)), int(m.group(2))
        for m in re.finditer(r"//[^\n]*offset (\d+), (\d+) bytes[^\n]*\n(?:\s*@[^\n]*\n)*\s*private\s+[\w.<>]+\s+(\w+);",
                             text):  # fmt: skip
            if m.group(3) == prop:
                return int(m.group(1)), int(m.group(2))
        raise CicsError(f"{entity}.{prop}: no offset")

    def screen_fields(self, cls: str) -> list[str]:
        text = self._file("dto/screen", cls).read_text(encoding="utf-8")
        return re.findall(r'values\.put\("([A-Z0-9-]+)",', text)


def item_for(leaf: Leaf) -> L.Item:
    usage = {"COMP": "BINARY", "COMP-4": "BINARY", "BINARY": "BINARY", "COMP-3": "PACKED", "PACKED-DECIMAL": "PACKED",
             "COMP-5": "COMP-5"}.get(leaf.usage, "DISPLAY")  # fmt: skip
    it = L.Item(5, leaf.cobol, "LINKAGE", pic=leaf.pic, usage=usage)
    L.layout(it)
    return it


# ---- the commands ------------------------------------------------------------------------------------------------
class Cics:
    """Translates EXEC CICS for one program; `gen` is the program's det.gen.Gen."""

    def __init__(self, gen, generated: Generated, package: str):
        self.g = gen
        self.gp = generated
        self.package = package
        self.codecs: dict[str, list[str]] = {}  # DTO class -> its in / out methods
        self.stores: dict[str, str] = {}  # CICS file -> the Java Store expression
        self.repos: dict[str, str] = {}  # repository class -> field
        self.used_screens: set[str] = set()

    # -- operands
    def operand(self, text: str):
        p = E.Parser(E.tokenize(text))
        e = p.arith() if text.strip().upper().startswith("LENGTH") or "+" in text or "*" in text else p.operand()
        if not p.done():
            raise CicsError(f"operand {text!r}")
        return e

    def ref(self, text: str) -> E.Ref:
        e = self.operand(text)
        if not isinstance(e, E.Ref):
            raise CicsError(f"not a data area: {text}")
        return e

    def text(self, text: str) -> str:
        e = self.operand(text)
        return self.g.text(e)

    def name(self, text: str) -> str:
        """A resource name (a literal, or a data area's text), trimmed."""
        return f"{self.text(text)}.strip()"

    def int_(self, text: str) -> str:
        return self.g.int_expr(self.operand(text))

    def field(self, text: str) -> str:
        return self.g.field_expr(self.ref(text))

    def size(self, text: str) -> int:
        r = self.ref(text)
        it = self.g.resolve(r)
        return it.size * (1 if r.subscripts else it.occurs)

    # -- RESP
    def outcome(self, opts: dict, resp: str, resp2: str, ind: str) -> list[str]:
        """After a command: EIBRESP, then RESP / RESP2 when given; else a condition other than NORMAL goes to its
        HANDLE CONDITION label, or (NOHANDLE aside) takes CICS's default action, an abend."""
        out = [f"{ind}Cobol.store({self.g.eib('EIBRESP')}, BigDecimal.valueOf({resp}), false, CS);",
               f"{ind}Cobol.store({self.g.eib('EIBRESP2')}, BigDecimal.valueOf({resp2}), false, CS);"]  # fmt: skip
        if "RESP" in opts:
            out.append(ind + self.g.store_into(self.ref(_arg(opts["RESP"])), f"BigDecimal.valueOf({resp})", False))
            if "RESP2" in opts:
                out.append(
                    ind + self.g.store_into(self.ref(_arg(opts["RESP2"])), f"BigDecimal.valueOf({resp2})", False)
                )
            return out
        if "NOHANDLE" in opts:
            return out
        out.append(f"{ind}if ({resp} != 0) {{")
        out.append(f"{ind}    int to = condition(DetCics.condition({resp}));")
        out.append(f"{ind}    if (to >= 0) {self.g.jump('to')}")
        out.append(f"{ind}}}")
        return out

    # -- COMMAREA codecs
    def codec(self, cls: str) -> str:
        if cls in self.codecs:
            return cls
        d = self.gp.dto(cls)
        self.codecs[cls] = []  # (recursion guard)
        lines_in = [f"    private void in_{cls}({cls} d, Storage s, int base) {{", "        if (d == null) {",
                    "            return;", "        }"]  # fmt: skip
        # fill_: the bytes into an existing DTO (a LINKed program's COMMAREA is its caller's object); out_: a new one
        lines_out = [f"    private void fill_{cls}({cls} d, Storage s, int base) {{"]
        for leaf in d.leaves:
            it = item_for(leaf)
            if it.size != leaf.size:
                # the comment does not carry everything (SIGN LEADING SEPARATE): the item as its copybook declares it
                it = self.declared(leaf)
            f = self.g.factory(it, "s", f"base + {leaf.offset}")
            cap = leaf.var[0].upper() + leaf.var[1:]
            if leaf.jtype == "String":
                lines_in.append(f'        Cobol.move(d.get{cap}() == null ? "" : d.get{cap}(), {f}, CS);')
                lines_out.append(f"        d.set{cap}(Cobol.text({f}, CS));")
            else:
                lines_in.append(f"        Cobol.move(d.get{cap}() == null ? BigDecimal.ZERO : new BigDecimal("
                                f"d.get{cap}().toString()), {f}, CS);")  # fmt: skip
                conv = {"Integer": ".intValue()", "Long": ".longValue()", "Short": ".shortValue()"}.get(leaf.jtype, "")
                lines_out.append(f"        d.set{cap}(Cobol.num({f}, CS){conv});")
        for var, part, off in d.parts:
            self.codec(part.cls)
            cap = var[0].upper() + var[1:]
            lines_in.append(f"        in_{part.cls}(d.get{cap}(), s, base + {off});")
            lines_out.append(f"        d.set{cap}(out_{part.cls}(s, base + {off}));")
        self.codecs[cls] = [*lines_in, "    }", "", *lines_out, "    }", "",
                            f"    private {cls} out_{cls}(Storage s, int base) {{", f"        {cls} d = new {cls}();",
                            f"        fill_{cls}(d, s, base);", "        return d;", "    }", ""]  # fmt: skip
        return cls

    def declared(self, leaf: Leaf) -> L.Item:
        """A DTO field's item as the copybook the generator read it from declares it."""
        from gitgalaxy.tools.cobol_to_java.det.source import logical_lines

        name = Path(leaf.source or "").name
        path = next((d / name for d in self.g.copy_dirs if name and (d / name).is_file()), None)
        if path is None:
            raise CicsError(f"{leaf.cobol}: {leaf.size} bytes, PIC {leaf.pic} is not; its copybook {name!r} not found")
        raw = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. GGDTO.", "       DATA DIVISION.",
               "       WORKING-STORAGE SECTION.", "       01 GG-DTO-RECORD."]  # fmt: skip
        raw += path.read_text(encoding="latin-1").splitlines()
        for rec in L.parse(logical_lines(raw, str(path))):
            for it in rec.walk():
                if it.name == leaf.cobol and it.size == leaf.size:
                    return it
        raise CicsError(f"{leaf.cobol}: not a {leaf.size}-byte item of {name}")

    def dto_for(self, area: E.Ref, size: int, program: str | None = None) -> str:
        """The DTO a COMMAREA travels as: the target's (XCTL), the program's own contract when the area is its size,
        else the record's own DTO."""
        if program and program in self.gp.xctl:
            return self.codec(self.gp.xctl[program])
        if program and program in self.gp.links:
            return self.codec(self.gp.links[program])
        if self.gp.contract and self.gp.dto(self.gp.contract).size == size:
            return self.codec(self.gp.contract)
        it = self.g.resolve(area)
        cls = self.gp.records.get(it.name)
        if cls is None:
            if self.gp.contract:
                return self.codec(self.gp.contract)
            raise CicsError(f"no generated DTO for COMMAREA {area.name}")
        return self.codec(cls)

    def commarea_out(self, opts: dict, program: str | None = None) -> tuple[str, str]:
        """(the DTO expression, the LENGTH expression or 'null') of a COMMAREA option."""
        r = self.ref(opts["COMMAREA"])
        size = self.size(opts["COMMAREA"])
        cls = self.dto_for(r, size, program)
        f = self.g.field_expr(r)
        dto = f"out_{cls}({f}.storage(), {f}.offset())"
        length = self.int_(opts["LENGTH"]) if opts.get("LENGTH") else "null"
        return dto, length

    # -- files
    def store(self, opts: dict) -> str:
        """The Store of the command's file (a literal name); a name only known at run time: looked up then."""
        arg = opts.get("DATASET") or opts.get("FILE")
        if arg is None:
            raise CicsError("no DATASET / FILE")
        lit = self.constant(arg)
        if lit is not None:
            self.gp.file(lit)  # this program's stub's mapping, else the estate's (recorded as inferred)
        for name, (repo, entity, prop) in self.gp.files.items():
            if name in self.stores:
                continue
            off, length = self.gp.entity_key(entity, prop)
            rcls = repo[0].upper() + repo[1:]
            self.repos[rcls] = repo
            self.stores[name] = (
                f"new DetCics.Store<{entity}>({repo}::findAll, e -> e.toRecord(CS), "
                f"b -> {entity}.fromRecord(b, CS), {repo}::save, {repo}::delete, {off}, {length}, CS)"
                # the base cluster's key: findById; an alternate index keeps the ordered scan
                + (self.g.find_by_id(entity, repo) if prop is None else "")
            )
            self.g.entities.add(entity)
        return f"store({self.name(arg)})"

    # -- the command
    def command(self, text: str, ind: str) -> list[str]:
        words, opts = parse_exec(text)
        verb = " ".join(words)
        if "COUNTER" in opts or "DCOUNTER" in opts:
            # named counters (DEFINE / GET / UPDATE / DELETE COUNTER): neither this runtime nor the harness models them
            raise CicsError(f"{verb} COUNTER: named counters are not modelled")
        g = self.g
        if verb == "SEND" and "MAP" in opts:
            return self.send_map(opts, ind)
        if verb == "SEND" or verb == "SEND TEXT":
            f = self.field(_arg(opts["FROM"]))
            n = self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else str(self.size(_arg(opts["FROM"])))
            flags = [o for o in TEXT_OPTIONS if o in opts]
            t = g.tmpname("text")
            return [f"{ind}String {t} = Cobol.text({f}, CS);",
                    f"{ind}task.sendText({t}.substring(0, Math.min({t}.length(), {n})), {n}"
                    f"{''.join(', ' + G_jstr(x) for x in flags)});",
                    *self.outcome(opts, "0", "0", ind)]  # fmt: skip
        if verb == "RECEIVE" and "MAP" in opts:
            return self.receive_map(opts, ind)
        if verb == "LINK":
            prog_lit = _literal(opts.get("PROGRAM"))
            prog = self.name(_arg(opts.get("PROGRAM")))
            if "CHANNEL" in opts or "INPUTMSG" in opts:
                raise CicsError("LINK with CHANNEL / INPUTMSG")
            g = self.g
            r, ca = g.tmpname("lr"), g.tmpname("ca")
            out: list[str] = []
            if "COMMAREA" in opts:
                area = self.ref(_arg(opts["COMMAREA"]))
                cls = self.dto_for(area, self.size(_arg(opts["COMMAREA"])), prog_lit)
                f = g.field_expr(area)
                length = (
                    self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else str(self.size(_arg(opts["COMMAREA"])))
                )
                out += [f"{ind}{cls} {ca} = out_{cls}({f}.storage(), {f}.offset());",
                        f"{ind}String {r} = task.link({prog}, {ca}, {length});",
                        # what the linked program left in the COMMAREA is the caller's area now
                        f"{ind}if (\"NORMAL\".equals({r})) in_{cls}({ca}, {f}.storage(), {f}.offset());"]  # fmt: skip
            else:
                out.append(f"{ind}String {r} = task.link({prog});")
            ex = g.tmpname("exit")
            out += [f"{ind}String {ex} = task.abendExit();",  # an abend below went to this program's exit
                    f"{ind}if ({ex} != null) {g.jump(f'paragraph({ex})')}",
                    f"{ind}if (task.ended()) throw new Goback();"]  # fmt: skip
            return out + self.outcome(opts, f"DetCics.resp({r})", "0", ind)
        if verb == "RETURN":
            if "TRANSID" in opts or "COMMAREA" in opts:
                tid = self.name(_arg(opts["TRANSID"])) if opts.get("TRANSID") else "null"
                dto, length = self.commarea_out(opts) if "COMMAREA" in opts else ("null", "null")
                return [f"{ind}caBack.run();", f"{ind}task.returnTransid({tid}, {dto}, {length});",
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
            if "COMMAREA" in opts:
                dto, length = self.commarea_out(opts, prog_lit)
                call = f"task.xctl({prog}, {dto}, {length})" if length != "null" else f"task.xctl({prog}, {dto})"
            else:
                call = f"task.xctl({prog}, null)"
            r = g.tmpname("xr")
            return ([f"{ind}String {r} = {call};", f"{ind}if (\"NORMAL\".equals({r})) throw new Goback();",
                    *self.outcome(opts, f"DetCics.resp({r})", "0", ind)])  # fmt: skip
        if verb in ("READ", "READNEXT", "READPREV"):
            return self.read(verb, opts, ind)
        if verb in ("WRITE", "REWRITE", "DELETE", "STARTBR", "ENDBR"):
            return self.file_update(verb, opts, ind)
        if verb == "HANDLE ABEND":
            if "LABEL" in opts:
                label = _arg(opts["LABEL"]).upper()
                if label not in g.para_index:
                    raise CicsError(f"HANDLE ABEND LABEL({label}): no such paragraph")
                return [f"{ind}task.handleAbend({G_jstr(label)});"]
            if "CANCEL" in opts:
                return [f"{ind}task.handleAbendCancel();"]
            if "RESET" in opts:
                return [f"{ind}task.handleAbendReset();"]
            raise CicsError("HANDLE ABEND PROGRAM")
        if verb == "HANDLE CONDITION":
            out = []
            for cond, target in opts.items():
                if target is None:
                    out.append(f"{ind}handlers.remove({G_jstr(cond)});")
                    continue
                if target.upper() not in g.para_index:
                    raise CicsError(f"HANDLE CONDITION {cond}({target}): no such paragraph")
                out.append(f"{ind}handlers.put({G_jstr(cond)}, {g.para_index[target.upper()]});")
            return out
        if verb == "ABEND":
            code = self.name(_arg(opts["ABCODE"])) if opts.get("ABCODE") else '""'
            fn = "abendCancel" if "CANCEL" in opts else "abend"
            lbl = g.tmpname("exit")
            return [f"{ind}String {lbl} = task.{fn}({code});", f"{ind}if ({lbl} == null) throw new Goback();",
                    f"{ind}if (true) {g.jump(f'paragraph({lbl})')}"]  # fmt: skip
        if verb == "ASSIGN":
            out = []
            for k, v in opts.items():
                src = {"APPLID": "task.assignApplid()", "SYSID": "task.assignSysid()", "ABCODE": "task.abcode()",
                       # the running program's own name, 8 characters
                       "PROGRAM": G_jstr(f"{self.g.p.name[:8]:<8}")}.get(k)  # fmt: skip
                if src is None:
                    raise CicsError(f"ASSIGN {k}")
                out.append(f"{ind}DetCics.putText({self.field(_arg(v))}, {src}, CS);")
            return out
        if verb == "ASKTIME":
            return [
                f"{ind}Cobol.store({self.field(_arg(opts['ABSTIME']))}, BigDecimal.valueOf(task.asktime()), false, CS);"
            ]
        if verb == "FORMATTIME":
            t = f"Cobol.num({self.field(_arg(opts['ABSTIME']))}, CS).longValue()"
            out = []
            for form in ("YYYYMMDD", "MMDDYYYY", "DDMMYYYY", "YYMMDD", "MMDDYY", "DDMMYY"):
                if form in opts:
                    sep = self.text(_arg(opts["DATESEP"])) if opts.get("DATESEP") else '""'
                    out.append(f"{ind}Cobol.move(CicsTask.formatDate({t}, {G_jstr(form)}, {sep}), "
                               f"{self.field(_arg(opts[form]))}, CS);")  # fmt: skip
            if "TIME" in opts:
                sep = self.text(_arg(opts["TIMESEP"])) if opts.get("TIMESEP") else '""'
                out.append(f"{ind}Cobol.move(CicsTask.formatTime({t}, {sep}), {self.field(_arg(opts['TIME']))}, CS);")
            if not out:
                raise CicsError("FORMATTIME form")
            return out
        if verb == "INQUIRE" and "PROGRAM" in opts:
            r = g.tmpname("resp")
            return [f"{ind}int {r} = task.inquireProgram({self.name(_arg(opts['PROGRAM']))});",
                    *self.outcome(opts, r, "0", ind)]  # fmt: skip
        if verb == "WRITEQ TD":
            r = g.tmpname("resp")
            f = self.field(_arg(opts["FROM"]))
            n = self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else str(self.size(_arg(opts["FROM"])))
            return [f"{ind}int {r} = task.writeqTd({self.name(_arg(opts['QUEUE']))}, "
                    f"Cobol.text({f}, CS).substring(0, {n}));",
                    *self.outcome(opts, r, "0", ind)]  # fmt: skip
        if verb in ("WRITEQ TS", "WRITEQ", "READQ TS", "READQ") and verb.startswith(("WRITEQ", "READQ")) \
                and "TD" not in words:  # fmt: skip
            return self.ts_queue(verb.split()[0], opts, ind)
        if verb in ("SYNCPOINT", "SYNCPOINT ROLLBACK"):
            return [f"{ind}task.{'rollback' if verb == 'SYNCPOINT ROLLBACK' or 'ROLLBACK' in opts else 'syncpoint'}();"]
        raise CicsError(f"EXEC CICS {verb} not modelled")

    def ts_queue(self, verb: str, opts: dict, ind: str) -> list[str]:
        """WRITEQ TS / READQ TS on the task's temporary storage (CicsTask): an item is the program's own bytes.
        (The proofs cover no TS command yet: declared in docs/language_status/det_port_design.md.)"""
        q = opts.get("QUEUE") or opts.get("QNAME")
        if q is None:
            raise CicsError(f"{verb} TS without QUEUE / QNAME")
        queue = self.name(q)
        g = self.g
        r = g.tmpname("ts")
        out: list[str] = []
        if verb == "WRITEQ":
            f = self.field(_arg(opts.get("FROM")))
            n = self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else f"{f}.length()"
            data = f"DetCics.bytes({f}, {n})"
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
            into = self.field(_arg(opts.get("INTO")))
            maxlen = self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else f"{into}.length()"
            if "NEXT" in opts or not opts.get("ITEM"):
                out.append(f"{ind}CicsTask.TsResult {r} = task.readqTsNext({queue}, {maxlen});")
            else:
                out.append(
                    f"{ind}CicsTask.TsResult {r} = task.readqTs({queue}, {self.int_(_arg(opts['ITEM']))}, {maxlen});"
                )
            out.append(f"{ind}if ({r}.data() != null) DetCics.put({into}, {r}.data());")
            if opts.get("LENGTH"):
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

    def symbolic(self, map_name: str, suffix: str, name: str, record: str | None) -> str | None:
        """The symbolic map item <name><suffix> under `record` (COSGN0AI / COSGN0AO), or None."""
        for rec in [*([record] if record else []), map_name + "I", map_name + "O"]:
            found = self._field_or_none(name + suffix, rec)
            if found is not None:
                return found
        return None

    def _field_or_none(self, name: str, rec: str) -> str | None:
        try:
            return self.g.field_expr(E.Ref(name, [rec]))
        except Exception:
            return None

    def constant(self, text: str | None) -> str | None:
        """A literal, or a data item with a VALUE the program never changes (LIT-THISMAP), as its text."""
        if text is None:
            return None
        lit = _literal(text)
        if lit is not None:
            return lit
        try:
            r = self.ref(text)
            it = self.g.resolve(r)
        except Exception:
            return None
        if len(it.values) != 1 or it.values[0][0] != "lit" or not self.g.never_written(it):
            return None
        return it.values[0][1].strip().upper()

    def map_names(self, opts: dict, area: str | None, suffix: str, ind: str) -> tuple[str, str, list[str]]:
        """(map, mapset, guard): constants; else the map whose symbolic record the FROM / INTO area is
        (CACTVWAO -> CACTVWA), the names checked at run time -- a different one is a hole, never a wrong screen."""
        m = self.constant(opts["MAP"])
        ms = self.constant(opts.get("MAPSET") or opts["MAP"])
        guard: list[str] = []
        if m is None and area is not None:
            name = self.ref(area).name
            if name.endswith(suffix) and name[:-1] in self.gp.screens:
                m = name[:-1]
                guard.append(f'{ind}if (!{self.name(opts["MAP"])}.equals({G_jstr(m)})) '
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
                guard.append(f'{ind}if (!{self.name(opts["MAPSET"])}.equals({G_jstr(ms)})) '
                             f'throw new Hole("MAPSET " + {self.name(opts["MAPSET"])} + ": not {ms}");')  # fmt: skip
        if m is None or ms is None:
            raise CicsError("MAP / MAPSET not a constant, nor fixed by the symbolic map")
        return m, ms, guard

    def send_map(self, opts: dict, ind: str) -> list[str]:
        m, ms, guard = self.map_names(opts, opts.get("FROM"), "O", ind)
        cls = self.gp.screens.get(m)
        if cls is None:
            raise CicsError(f"no generated screen for map {m}")
        self.used_screens.add(cls)
        frm = self.ref(opts["FROM"]).name if opts.get("FROM") else m + "O"
        v, sub, scr = self.g.tmpname("values"), self.g.tmpname("sub"), self.g.tmpname("screen")
        out = [*guard, f"{ind}java.util.Map<String, String> {v} = new java.util.LinkedHashMap<>();",
               f"{ind}CicsTask.MapSubfields {sub} = new CicsTask.MapSubfields();"]  # fmt: skip
        for name in self.gp.screen_fields(cls):
            o = self.symbolic(m, "O", name, frm)
            if o is None:
                raise CicsError(f"map {m}: no {name}O")
            out.append(f"{ind}{v}.put({G_jstr(name)}, Cobol.text({o}, CS));")
            parts = [self.symbolic(m, s, name, None) for s in ("L", "A", "C", "H")]
            if parts[1] is None:
                parts[1] = self.symbolic(m, "F", name, None)
            out.append(f"{ind}DetCics.subfields({sub}, {G_jstr(name)}, "
                       f"{', '.join(p or 'null' for p in parts)}, CS);")  # fmt: skip
        if opts.get("CURSOR"):
            out.append(f"{ind}{sub}.cursorAt({self.int_(opts['CURSOR'])});")
        flags = [o for o in MAP_OPTIONS if o in opts]
        screen = "null" if "MAPONLY" in opts else f"{cls}.fromValues({v})"
        out.append(f"{ind}{cls} {scr} = {screen};")
        out.append(f"{ind}task.sendMap({G_jstr(m)}, {G_jstr(ms)}, {scr}, {sub}"
                   f"{''.join(', ' + G_jstr(x) for x in flags)});")  # fmt: skip
        return out + self.outcome(opts, "0", "0", ind)

    def receive_map(self, opts: dict, ind: str) -> list[str]:
        m, ms, guard = self.map_names(opts, opts.get("INTO"), "I", ind)
        cls = self.gp.screens.get(m)
        if cls is None:
            raise CicsError(f"no generated screen for map {m}")
        into = self.ref(opts["INTO"]) if opts.get("INTO") else E.Ref(m + "I")
        fi = self.g.field_expr(into)
        r, vals, resp = self.g.tmpname("received"), self.g.tmpname("typed"), self.g.tmpname("resp")
        out = [*guard, f"{ind}java.util.Optional<{cls}> {r} = task.receive({G_jstr(m)}, {G_jstr(ms)}, {cls}.class);",
               f"{ind}int {resp} = {r}.isPresent() ? 0 : 36;", f"{ind}if ({r}.isPresent()) {{",
               f"{ind}    java.util.Arrays.fill({fi}.storage().bytes, {fi}.offset(), {fi}.offset() + {fi}.length(), "
               "(byte) 0);",
               f"{ind}    java.util.Map<String, String> {vals} = {r}.get().screenValues();"]  # fmt: skip
        for name in self.gp.screen_fields(cls):
            i = self.symbolic(m, "I", name, into.name)
            ln = self.symbolic(m, "L", name, into.name)
            if i is None:
                continue
            out.append(f"{ind}    if ({vals}.get({G_jstr(name)}) != null) {{")
            out.append(f"{ind}        DetCics.typed({i}, {ln or 'null'}, {vals}.get({G_jstr(name)}), CS);")
            out.append(f"{ind}    }}")
        out.append(f"{ind}}}")
        return out + self.outcome(opts, resp, "0", ind)

    def read(self, verb: str, opts: dict, ind: str) -> list[str]:
        st = self.store(opts)
        file = self.name(_arg(opts.get("DATASET") or opts.get("FILE")))
        into = self.field(opts["INTO"])
        rid = self.field(opts["RIDFLD"])
        g = self.g
        r, rec = g.tmpname("read"), g.tmpname("rec")
        if verb == "READ":
            fn = "readForUpdate" if "UPDATE" in opts else "read"
            out = [
                f"{ind}byte[] {rec} = DetCics.bytes({rid});",
                f"{ind}CicsTask.FileRead<byte[]> {r} = task.{fn}({file}, () -> {st}.find({rec}));",
                f"{ind}if ({r}.record() != null) {{",
                f"{ind}    DetCics.put({into}, {r}.record());",
                *([f"{ind}    heldKey.put({file}, {rec});"] if "UPDATE" in opts else []),
                f"{ind}}}",
            ]
            return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)
        fn = "readnext" if verb == "READNEXT" else "readprev"
        out = [f"{ind}CicsTask.Browsed {r} = task.{fn}({file}, new String(DetCics.bytes({rid}), CS));",
               f"{ind}if ({r}.normal()) {{",
               f"{ind}    DetCics.put({rid}, {r}.key().getBytes(CS));",
               f"{ind}    {st}.find({r}.key().getBytes(CS)).ifPresent(b -> DetCics.put({into}, b));",
               f"{ind}}}"]  # fmt: skip
        return out + self.outcome(opts, f"{r}.resp()", "0", ind)

    def record_from(self, opts: dict) -> str:
        """A WRITE / REWRITE's record: FROM's bytes, or LENGTH bytes from FROM's first (as CICS reads them)."""
        frm = self.field(opts["FROM"])
        if opts.get("LENGTH"):
            return f"DetCics.bytes({frm}, {self.int_(_arg(opts['LENGTH']))})"
        return f"DetCics.bytes({frm})"

    def file_update(self, verb: str, opts: dict, ind: str) -> list[str]:
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
        return out + self.outcome(opts, r, "0", ind)


def _literal(text: str | None) -> str | None:
    if text and text.strip()[:1] in "'\"":
        return text.strip()[1:-1].upper()
    return None


def G_jstr(s: str) -> str:
    from gitgalaxy.tools.cobol_to_java.det.gen import jstr

    return jstr(s)
