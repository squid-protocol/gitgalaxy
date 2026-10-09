"""EXEC CICS commands of a deterministic port, onto the generated project's CicsTask.

Every typed object at the boundary is the generator's: the COMMAREA DTOs (dto/contract, each property's comment
naming its COBOL field, PICTURE and offset), the screen view models (dto/screen: fromValues / screenValues by BMS
field name), and the entities of each CICS file (the stub's "<DSN> as CICS file <NAME>" methods). The port converts
between them and the program's own bytes -- nothing is taken from a test case."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from gitgalaxy.standards.cics.commands import COMMANDS as SPEC
from gitgalaxy.standards.cics.commands import whole_refusal
from gitgalaxy.standards.cics.commands.api import CHILD_LATER, CONTAINER_LATER, COUNTER
from gitgalaxy.standards.cics.commands.assign import TERMINAL_OPTIONS
from gitgalaxy.standards.cics.commands.handles import AID_KEYS
from gitgalaxy.standards.cics.commands.send_text import TEXT_OPTIONS
from gitgalaxy.standards.cics.commands.shared import BOTH_FORMS, NEEDS_ARGUMENT
from gitgalaxy.standards.cics.commands.task import DATE_FORMS
from gitgalaxy.standards.cics.commands.terminal import MAP_OPTIONS, SEND_CONTROL_OPTIONS
from gitgalaxy.standards.cics.model import GroupKind
from gitgalaxy.standards.cics.resp import DFHRESP
from gitgalaxy.tools.cobol_to_java.det import expr as E
from gitgalaxy.tools.cobol_to_java.det import layout as L

COPY = Path(__file__).parent / "copy"  # DFHEIBLK, DFHAID, DFHBMSCA


class CicsError(Exception):
    pass


# #4528: CICS's default CCSID, the region's page when the estate declares no EBCDIC one (cics-crucible SPEC 2: "every
# byte in every area is CCSID 037")
REGION_PAGE = "cp037"


def region_page(declared: str | None) -> str:
    """#4528: the JDK name of the region's code page -- the page a TS item's bytes are in on the COBOL side: the
    estate's declared code page for the program when it is an EBCDIC one (cp273, cp277 ...: EngineCopies.page, the
    page the engine decoded it with), else CCSID 037. An ASCII-family declaration says how the source was
    transferred, not which page the region runs."""
    from gitgalaxy.core.ebcdic_codecs import java_charset_name, register

    register()
    page = REGION_PAGE
    if declared:
        try:
            if " ".encode(declared) == b"\x40":
                page = declared
        except (LookupError, UnicodeError):
            pass
    return java_charset_name(page)


# #4411: every option each modelled command accepts -- the CICS command spec's (gitgalaxy/standards/cics, #4270 spec
# PR 2): an option outside its command's set is refused by name (the statement becomes a hole), with the reason the
# command's own spec entry gives, never accepted and ignored: a silently divergent port is worse than a visible hole.
# None: every option is checked by the command's handler (HANDLE / IGNORE CONDITION's conditions, HANDLE AID's keys).
OPTIONS: dict[str, frozenset | None] = {
    k: None if c.open_options else frozenset(c.options) for k, c in SPEC.items() if c.status == "modelled"
}
_FORMS = DATE_FORMS
_SEND_CONTROL = frozenset(SEND_CONTROL_OPTIONS)  # #4413: its device controls


def _msg(key: str, kind: GroupKind, option: str, *parts: str) -> str:
    """The message of the command's option rule (its spec Group), with the parts it names filled in."""
    return SPEC[key].group(kind, option).msg.format(*parts)


def command_key(words: list[str], opts: dict) -> str:
    """The OPTIONS key of a parsed command (the verb words, plus the option that names the form: SEND MAP)."""
    verb = " ".join(words)
    first = words[0] if words else ""
    if first in ("ENQ", "DEQ", "DELAY"):
        return first
    if first in ("GET", "PUT", "DELETE", "MOVE") and "CONTAINER" in opts:  # #4270 (DELETE CONTAINER is no file's)
        return f"{first} CONTAINER"
    if verb != "GET" and ("COUNTER" in opts or "DCOUNTER" in opts):
        return f"{verb} COUNTER"  # (not modelled: refused whole by Cics.command)
    if first == "SEND":
        return "SEND MAP" if "MAP" in opts else "SEND TEXT" if verb in ("SEND", "SEND TEXT") else verb
    for form in _FORM_OPTION.get(verb, ()):
        if form in opts:
            return f"{verb} {form}"
    if verb in ("WRITEQ", "READQ", "DELETEQ"):  # (a TD option after the verb is refused, never read as TS)
        return f"{verb} TS"
    return verb


_FORM_OPTION = {
    "RECEIVE": ("MAP",),
    "GET": ("COUNTER",),
    "INQUIRE": ("PROGRAM", "TERMINAL", "ASSOCIATION", "URIMAP"),
    "SET": ("TERMINAL",),
}


def check_options(words: list[str], opts: dict) -> None:
    """#4411: refuse, by name, an option the command's translation would not honour. (A command not in OPTIONS is
    refused whole by Cics.command.)"""
    key = command_key(words, opts)
    if key not in OPTIONS:
        return
    allowed = OPTIONS[key]
    if allowed is None:
        return
    bad = [o for o in opts if o not in allowed]
    if bad:
        raise CicsError(SPEC[key].refusal_message(bad))


# ---- the EXEC text ----------------------------------------------------------------------------------------------
def _arg(v: str | None) -> str:
    """An EXEC CICS option's argument text; a bare option where one is needed is an error."""
    if v is None:
        raise CicsError(NEEDS_ARGUMENT)
    return v


# an option with no argument that can come first, so is never a verb word (#4413: RECEIVE NOTRUNCATE INTO(...))
_BARE_OPTIONS = ("NOTRUNCATE", "NOHANDLE")  # (#4737: ASKTIME NOHANDLE)


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
        elif not opts and len(words) < 2 and name not in MAP_OPTIONS and name not in _BARE_OPTIONS:
            words.append(name)
        else:
            opts[name] = None
    return words, opts


# ---- the generated DTOs ----------------------------------------------------------------------------------------
_PROP = re.compile(r"//\s*(.+?)\n\s*private\s+([\w.<>]+)\s+(\w+);")
_LEAF = re.compile(r"([A-Z0-9-]+):\s*PIC\s+(\S+?)(?:\s+(COMP-3|COMP-5|COMP-4|COMP|BINARY|PACKED-DECIMAL|DISPLAY))?,"
                   r"\s*offset\s+(\d+),\s*(\d+)\s+bytes(?:\s*\(([^)]+)\))?")  # fmt: skip
_PART = re.compile(r"offset\s+(\d+),\s*(\d+)\s+bytes\s*->\s*([A-Z0-9-]+)")
_POINTER = re.compile(r"([A-Z0-9-]+):\s*POINTER,\s*offset\s+(\d+),\s*(\d+)\s+bytes(?:\s*\(([^)]+)\))?")
POINTER_BYTES = 8  # GnuCOBOL's on x86-64, and so the port's storage; IBM's is 4 (oracle_assumptions.md C9)
IBM_POINTER_BYTES = 4  # Enterprise COBOL's (AMODE 31), as the generated DTOs lay a POINTER out
_DTO_RECORD = re.compile(r"COBOL record [A-Z0-9-]+ \([^)]*\), (\d+) bytes")


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
    """A generated COMMAREA DTO. Its offsets are IBM's (the generator lays a POINTER out in 4 bytes, as Enterprise
    COBOL does); the port's storage is GnuCOBOL's, where a POINTER is POINTER_BYTES (oracle_assumptions.md C9).
    `at` maps a DTO offset to the storage's: each POINTER before it is that much wider there. `size` is in storage
    bytes."""

    cls: str
    leaves: list = field(default_factory=list)
    parts: list = field(default_factory=list)  # (var, Dto, offset)
    record: int | None = None  # the bytes the DTO's header declares (IBM's), when it says
    occurs: bool = False  # the header says OCCURS fields appear once: the leaves end before the record does

    @property
    def wider(self) -> int:
        """How many bytes wider the record is in the port's storage than in IBM's: its POINTERs'."""
        own = sum(POINTER_BYTES - x.size for x in self.leaves if x.usage == "POINTER")
        return own + sum(p.wider for _, p, _ in self.parts)

    def at(self, off: int) -> int:
        """The storage offset of DTO offset `off` (a field's start): past every POINTER before it."""
        shift = sum(POINTER_BYTES - x.size for x in self.leaves if x.usage == "POINTER" and x.offset < off)
        return off + shift + sum(p.wider for _, p, o in self.parts if o < off)

    @property
    def size(self) -> int:
        n = max((self.at(x.offset) + (POINTER_BYTES if x.usage == "POINTER" else x.size) for x in self.leaves),
                default=0)  # fmt: skip
        n = max([n] + [self.at(off) + p.size for _, p, off in self.parts])
        if self.wider and self.occurs and self.record:
            # #4270 (C9): a DTO with a POINTER whose OCCURS fields appear once (CBSA's INQACCCU-COMMAREA, 20 accounts):
            # the whole record, every occurrence, travels -- its declared bytes, each POINTER as wide as the storage's
            n = max(n, self.record + self.wider)
        return n


class Generated:
    """What the generated project says about one program's CICS boundary."""

    def target_contract(self, program: str) -> str | None:
        """The COMMAREA DTO another program's generated service takes (its handleLink / handleTransaction), or None."""
        from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base

        f = next(self.java.rglob(f"service/{java_class_base(program)}Service.java"), None)
        if f is None:
            return None
        text = f.read_text(encoding="utf-8")
        m = re.search(r"public \w+ handleLink\((\w+) request\)", text) or re.search(
            r"handleTransaction\(String transid, (\w+) request\)", text
        )
        return m.group(1) if m else None

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
        self.mapsets: dict[str, list[str]] = {}  # mapset -> its maps, from the generated screens
        for p in sorted(self.java.rglob("dto/screen/*Screen.java")):
            mm = re.search(r'String MAP = "([^"]+)"', p.read_text(encoding="utf-8"))
            if mm:
                self.screens[mm.group(1).upper()] = p.stem
                ms = re.search(r'String MAPSET = "([^"]+)"', p.read_text(encoding="utf-8"))
                if ms:
                    self.mapsets.setdefault(ms.group(1).upper(), []).append(mm.group(1).upper())
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
        text = self._file("dto/contract", cls).read_text(encoding="utf-8")
        head = _DTO_RECORD.search(text)
        d.record = int(head.group(1)) if head else None
        d.occurs = "Fields inside an OCCURS group appear once" in text
        for comment, jtype, var in _PROP.findall(text):
            part = _PART.search(comment)
            if part:
                d.parts.append((var, self.dto(jtype), int(part.group(1))))
                continue
            ptr = _POINTER.search(comment)
            if ptr and jtype == "String":  # CBSA's PCB pointers: NULL travels, an address cannot (DetCics.pointerIn)
                if int(ptr.group(3)) != IBM_POINTER_BYTES:
                    raise CicsError(f"{cls}.{var}: a {ptr.group(3)}-byte POINTER (IBM's is {IBM_POINTER_BYTES}: the "
                                    "DTO's later offsets cannot be mapped to the port's storage)")  # fmt: skip
                d.leaves.append(Leaf(var, jtype, ptr.group(1), "", "POINTER", int(ptr.group(2)), int(ptr.group(3)),
                                     ptr.group(4)))  # fmt: skip
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
        # #4414: the program issues HANDLE AID (its input commands consult the keys' labels) / PUSH HANDLE (its
        # handler state is stacked); set by program._translate from the source before any statement is translated
        self.handle_aid = False
        self.push_handle = False
        # #4528: the region's code page (region_page), set by program._translate; `region_used`: the port declares
        # REGION (a TS command moves bytes between the program's storage and the region)
        self.region = region_page(None)
        self.region_used = False

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

    def read_field(self, text: str) -> str:
        """An operand the command only reads (FROM): a typed group's bytes need no unpack after it."""
        with self.g.reading():
            return self.field(text)

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

    # -- ASSIGN
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
                   "PROGRAM": G_jstr(f"{self.g.p.name[:8]:<8}"),
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

    # -- #4414: IGNORE CONDITION, HANDLE AID, PUSH / POP HANDLE
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
                out.append(f"{ind}aids.put({G_jstr(key)}, -1);")
                continue
            if label.upper() not in self.g.para_index:
                raise CicsError(f"HANDLE AID {key}({label}): no such paragraph")
            out.append(f"{ind}aids.put({G_jstr(key)}, {self.g.para_index[label.upper()]});")
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
        # #4270 (C9): the DTO's offsets are IBM's, the storage's GnuCOBOL's -- each field is placed past the wider
        # POINTERs before it (Dto.at), so the data after a POINTER is the same field on both sides; a POINTER inside an
        # OCCURS would be wider once per occurrence, which the DTO (fields listed once) cannot say: refused by name
        ends = [x.offset for x in d.leaves if x.usage != "POINTER"] + [off for _, _, off in d.parts]
        for leaf in d.leaves:
            if leaf.usage == "POINTER" and any(o > leaf.offset for o in ends):  # (a trailing one shifts nothing)
                self.pointer_outside_occurs(cls, leaf)
        for leaf in d.leaves:
            at = d.at(leaf.offset)
            if leaf.usage == "POINTER":
                cap = leaf.var[0].upper() + leaf.var[1:]
                lines_in.append(f"        DetCics.pointerIn(d.get{cap}(), s, base + {at}, {POINTER_BYTES});")
                lines_out.append(f"        d.set{cap}(DetCics.pointerOut(s, base + {at}, {POINTER_BYTES}));")
                continue
            it = item_for(leaf)
            if it.size != leaf.size:
                # the comment does not carry everything (SIGN LEADING SEPARATE): the item as its copybook declares it
                it = self.declared(leaf)
            f = self.g.factory(it, "s", f"base + {at}")
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
            lines_in.append(f"        in_{part.cls}(d.get{cap}(), s, base + {d.at(off)});")
            lines_out.append(f"        d.set{cap}(out_{part.cls}(s, base + {d.at(off)}));")
        self.codecs[cls] = [*lines_in, "    }", "", *lines_out, "    }", "",
                            f"    private {cls} out_{cls}(Storage s, int base) {{", f"        {cls} d = new {cls}();",
                            f"        fill_{cls}(d, s, base);", "        return d;", "    }", ""]  # fmt: skip
        return cls

    def pointer_outside_occurs(self, cls: str, leaf: Leaf) -> None:
        """#4270 (C9): a DTO's POINTER, as its copybook declares it, is under no OCCURS -- else each occurrence would
        shift the storage's offsets once more than the DTO's, which lists its fields once. Refused by name."""
        if not leaf.source:
            raise CicsError(f"{cls}: POINTER {leaf.cobol} names no copybook (is it under an OCCURS?)")
        for it in self._copybook_items(leaf, f"{leaf.cobol} DTO POINTER"):
            if it.name == leaf.cobol and it.usage == "POINTER":
                up = it
                while up is not None:
                    if up.occurs > 1 or up.depending:
                        raise CicsError(f"{cls}: POINTER {leaf.cobol} under an OCCURS (each occurrence is "
                                        f"{POINTER_BYTES - IBM_POINTER_BYTES} bytes wider than IBM's)")  # fmt: skip
                    up = up.parent
                return
        raise CicsError(f"{cls}: POINTER {leaf.cobol} is not declared in {Path(leaf.source).name}")

    def _copybook_items(self, leaf: Leaf, what: str, missing: str = ""):
        """Every item of the copybook the generator read a DTO field from, as one record (GG-DTO-RECORD)."""
        from gitgalaxy.tools.cobol_to_java.det.source import CopyAmbiguous, _raw_lines, _search_member, logical_lines

        name = Path(leaf.source or "").name
        try:  # #4461: the member the source reader resolves, never the first directory holding the name
            path = _search_member(name, self.g.copy_dirs, frozenset(), what) if name else None
        except CopyAmbiguous as e:
            raise CicsError(str(e)) from e
        if path is None:
            raise CicsError(missing or f"{leaf.cobol}: its copybook {name!r} not found")
        raw = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. GGDTO.", "       DATA DIVISION.",
               "       WORKING-STORAGE SECTION.", "       01 GG-DTO-RECORD."]  # fmt: skip
        # #4528: decoded with the code page the estate declares for it, as the engine and the source reader do
        raw += _raw_lines(path, self.g.engine)
        try:
            records = L.parse(logical_lines(raw, str(path)))
        except L.LayoutError as e:  # (a program's own source, say: not a member to copy into a record)
            raise CicsError(f"{what}: {name} is not read as a copybook ({e})") from e
        for rec in records:
            yield from rec.walk()

    def declared(self, leaf: Leaf) -> L.Item:
        """A DTO field's item as the copybook the generator read it from declares it."""
        name = Path(leaf.source or "").name
        missing = f"{leaf.cobol}: {leaf.size} bytes, PIC {leaf.pic} is not; its copybook {name!r} not found"
        if not name:
            raise CicsError(missing)
        for it in self._copybook_items(leaf, f"{leaf.cobol} DTO field", missing):
            if it.name == leaf.cobol and it.size == leaf.size:
                return it
        raise CicsError(f"{leaf.cobol}: not a {leaf.size}-byte item of {name}")

    def _value_name(self, operand: str | None) -> str | None:
        """A data item's literal VALUE (a program named through a constant), or None."""
        if not operand or _literal(operand):
            return None
        try:
            it = self.g.resolve(self.ref(_arg(operand)))
        except Exception:  # not a plain data name
            return None
        vals = getattr(it, "values", None) or []
        return vals[0][1].strip().upper() if vals and vals[0][0] == "lit" else None

    def dto_for(self, area: E.Ref, size: int, program: str | None = None) -> str:
        """The DTO a COMMAREA travels as: the target's (XCTL), the program's own contract when the area is its size,
        else the record's own DTO."""
        if program and program in self.gp.xctl:
            return self.codec(self.gp.xctl[program])
        if program and program in self.gp.links:
            return self.codec(self.gp.links[program])
        target = self.gp.target_contract(program) if program else None
        if target:  # the stub types no link to it: what the target accepts
            return self.codec(target)
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
        """(the DTO expression, the LENGTH expression or 'null') of a COMMAREA option. An XCTL's or a RETURN's LENGTH
        past the DTO passes the bytes (#4501 XCTL, #4679 RETURN: CardDemo's LENGTH 2000 WS-COMMAREA over its DTO)."""
        r = self.ref(opts["COMMAREA"])
        size = self.size(opts["COMMAREA"])
        cls = self.dto_for(r, size, program)
        with self.g.reading():  # RETURN / XCTL only read it (a LINK's write-back is the caller's own code)
            f = self.g.field_expr(r)
        dto = f"out_{cls}({f}.storage(), {f}.offset())"
        length = self.int_(opts["LENGTH"]) if opts.get("LENGTH") else "null"
        if length != "null":
            # #4501 / #4679: a LENGTH past the DTO passes that many bytes (DetCics.commareaOut), which the DTO cannot hold
            size = self.gp.dto(cls).size
            known = self.constant_int(opts["LENGTH"])
            if known is None or known > size:
                dto = f"DetCics.commareaOut({dto}, {f}, {length}, {size}, CS)"
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
                f"b -> {entity}.fromRecord(b, CS), e -> task.write({G_jstr(name)}, () -> {repo}.save(e)), "
                f"e -> task.write({G_jstr(name)}, () -> {repo}.delete(e)), {off}, {length}, CS)"
                # the base cluster's key: findById; an alternate index keeps the ordered scan
                + (self.g.find_by_id(entity, repo) if prop is None else "")
            )
            self.g.entities.add(entity)
        return f"store({self.name(arg)})"

    # -- the command
    def command(self, text: str, ind: str) -> list[str]:
        words, opts = parse_exec(text)
        verb = " ".join(words)
        check_options(words, opts)  # #4411: an option the translation would ignore is refused first
        key = command_key(words, opts)
        if key in ("PUT CONTAINER", "GET CONTAINER", "DELETE CONTAINER"):
            return self.container(key, opts, ind)
        if key == "MOVE CONTAINER" or words[:1] in (["STARTBROWSE"], ["GETNEXT"], ["ENDBROWSE"]):
            # #4270: no non-burned corpus program MOVEs a container; one browses (with GETMAIN / SOAPFAULT beside)
            raise CicsError(f"EXEC CICS {key} not modelled ({CONTAINER_LATER})")
        if verb == "RUN":  # #4270 slice 2
            return self.run_transid(opts, ind)
        if words[:1] == ["FETCH"] or verb == "FREE CHILD":
            raise CicsError(f"EXEC CICS {verb} not modelled ({CHILD_LATER})")
        if verb in ("START", "RETRIEVE", "CANCEL"):  # #4270 slice 2: interval control
            return {"START": self.start, "RETRIEVE": self.retrieve, "CANCEL": self.cancel}[verb](opts, ind)
        if verb.split()[0] in ("ENQ", "DEQ", "DELAY"):  # (DELAY FOR SECONDS(n): words DELAY FOR)
            return self.outcome(opts, "0", "0", ind)  # (OPTIONS: one task in the region, nothing waits)
        if (
            verb == "GET" and "COUNTER" in opts
        ):  # GET COUNTER: its value, then +1; INVREQ RESP2 201 for a counter not defined (X30)
            if not opts.get("VALUE"):
                raise CicsError(_msg("GET COUNTER", "required", "VALUE"))
            v = self.g.tmpname("counter")
            pool = self.name(_arg(opts["POOL"])) if opts.get("POOL") else '""'
            return [f"{ind}long[] {v} = task.getCounter({pool}, {self.name(_arg(opts['COUNTER']))});",
                    f"{ind}if ({v}[0] == 0) {{",
                    ind + "    " + self.g.store_into(self.ref(_arg(opts["VALUE"])), f"BigDecimal.valueOf({v}[2])", False),
                    f"{ind}}}",
                    *self.outcome(opts, f"(int) {v}[0]", f"(int) {v}[1]", ind)]  # fmt: skip
        if verb in ("DEFINE", "DELETE") and "COUNTER" in opts:  # #4270 (X30): the region's named counters
            v = self.g.tmpname("counter")
            pool = self.name(_arg(opts["POOL"])) if opts.get("POOL") else '""'
            nm = self.name(_arg(opts["COUNTER"]))
            if verb == "DELETE":
                call = f"task.deleteCounter({pool}, {nm})"
            else:  # (VALUE omitted: IBM's initial value of zero)
                call = (
                    f"task.defineCounter({pool}, {nm}, {self.int_(_arg(opts['VALUE'])) if opts.get('VALUE') else '0'})"
                )
            return [f"{ind}int[] {v} = {call};", *self.outcome(opts, f"{v}[0]", f"{v}[1]", ind)]
        if verb == "QUERY" and "COUNTER" in opts:  # #4415 slice 2 (X29): its value, unchanged; INVREQ RESP2 201 if none
            v = self.g.tmpname("counter")
            pool = self.name(_arg(opts["POOL"])) if opts.get("POOL") else '""'
            return [f"{ind}int[] {v} = task.queryCounter({pool}, {self.name(_arg(opts['COUNTER']))});",
                    f"{ind}if ({v}[0] == 0) {{",
                    ind + "    " + self.g.store_into(self.ref(_arg(opts["VALUE"])), f"BigDecimal.valueOf({v}[2])", False),
                    f"{ind}}}",
                    *self.outcome(opts, f"{v}[0]", f"{v}[1]", ind)]  # fmt: skip
        if "COUNTER" in opts or "DCOUNTER" in opts:
            # the other named-counter commands (DEFINE / UPDATE / DELETE COUNTER, DCOUNTER): not modelled
            raise CicsError(f"{verb} COUNTER: {COUNTER}")
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
            text = (
                "Cobol.text({}, CS)"
                if not opts.get("LENGTH") or (fixed_len is not None and fixed_len <= self.size(_arg(opts["FROM"])))
                else 'new String(DetCics.withinRecord({}, {}, "SEND TEXT"), CS)'
            ).format(f, n)
            return [f"{ind}String {t} = {text};",
                    f"{ind}task.sendText({t}.substring(0, Math.min({t}.length(), {n})), {n}"
                    f"{''.join(', ' + G_jstr(x) for x in flags)});",
                    *self.outcome(opts, "0", "0", ind)]  # fmt: skip
        if verb == "RECEIVE" and "MAP" in opts:
            return self.receive_map(opts, ind)
        if verb == "LINK":
            # #4270 (X27): "SYNCONRETURN is only applicable to remote links, it is ignored if the link is local" (IBM,
            # EXEC CICS LINK); SYSID, the only way to a remote link, is refused, so every LINK here is local
            opts = {k: v for k, v in opts.items() if k != "SYNCONRETURN"}
            # a literal, or a data item's VALUE (GenApp's 01 LGUPVS01 PIC X(8) VALUE 'LGUPVS01'): the program the
            # COMMAREA's DTO is typed for -- the name the LINK uses at run time is still the item's
            prog_lit = _literal(opts.get("PROGRAM")) or self._value_name(opts.get("PROGRAM"))
            prog = self.name(_arg(opts.get("PROGRAM")))
            g = self.g
            r, ca = g.tmpname("lr"), g.tmpname("ca")
            out: list[str] = []
            cls: str | None = None
            if "CHANNEL" in opts:  # #4270: the callee's current channel (CicsTask.linkChannel)
                if "COMMAREA" in opts or "LENGTH" in opts:
                    raise CicsError(_msg("LINK", "at_most_one", "CHANNEL"))
                out.append(f"{ind}String {r} = task.linkChannel({prog}, {self.name(_arg(opts['CHANNEL']))});")
            elif "COMMAREA" in opts:
                area = self.ref(_arg(opts["COMMAREA"]))
                try:
                    cls = self.dto_for(area, self.size(_arg(opts["COMMAREA"])), prog_lit)
                except CicsError as e:
                    if "no generated DTO" not in str(e):
                        raise
                    cls = None
                f = g.field_expr(area)
                length = (
                    self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else str(self.size(_arg(opts["COMMAREA"])))
                )
            else:
                out.append(f"{ind}String {r} = task.link({prog});")
            if "COMMAREA" in opts and cls is None:
                # #4679: no DTO types the target (cics-crucible ca-link-lengths: CAGONE, which no CSD defines -- the LINK
                # is PGMIDERR RESP2 1): the COMMAREA travels as its LENGTH bytes, by reference, as an XCTL's past its DTO
                w = g.tmpname("cw")
                out += [f"{ind}Storage {w} = Cobol.commarea({f}, Math.max(0, Math.min({length}, 32763)));",
                        f"{ind}String {r} = task.link({prog}, DetCics.commareaBytes({w}.bytes, CS), {length}, {w}.bytes);",
                        f"{ind}if (\"NORMAL\".equals({r})) Cobol.commareaBack({w}, {f});"]  # fmt: skip
            elif cls is not None:  # (a COMMAREA a DTO types)
                # #4181: the target's DTO over the caller's storage from the area on, never past its record's end;
                # #4679: a LENGTH past the DTO passes that many bytes (by reference: the target's EIBCALEN is LENGTH)
                w = g.tmpname("cw")
                dsize = self.gp.dto(cls).size
                fixed = self.constant_int(_arg(opts["LENGTH"])) if opts.get("LENGTH") else None
                span = (
                    str(dsize)
                    if not opts.get("LENGTH") or (fixed is not None and fixed <= dsize)
                    else f"Math.max({dsize}, Math.min({length}, 32763))"
                )
                out += [f"{ind}Storage {w} = Cobol.commarea({f}, {span});",
                        f"{ind}{cls} {ca} = out_{cls}({w}, 0);",
                        # #4181 follow-up: the bytes too (by reference), every one the target's DTO does not name
                        f"{ind}String {r} = task.link({prog}, {ca}, {length}, {w}.bytes);",
                        # what the linked program left in the COMMAREA is the caller's area now
                        f"{ind}if (\"NORMAL\".equals({r})) {{ in_{cls}({ca}, {w}, 0); Cobol.commareaBack({w}, {f}); }}"]  # fmt: skip
            ex = g.tmpname("exit")
            out += [f"{ind}String {ex} = task.abendExit();",  # an abend below went to this program's exit
                    f"{ind}if ({ex} != null) {g.jump(f'paragraph({ex})')}",
                    f"{ind}if (task.ended()) throw abended();"]  # #4534: unwound past this level  # fmt: skip
            return out + self.outcome(opts, f"DetCics.resp({r})", f"DetCics.linkResp2({r})", ind)  # #4679
        if verb == "RETURN":
            if "IMMEDIATE" in opts:  # #4270 (X27): IBM, EXEC CICS RETURN IMMEDIATE -- TRANSID's task attached at once
                if not opts.get("TRANSID"):
                    raise CicsError(
                        "RETURN IMMEDIATE without TRANSID: IBM does not say what it attaches (not modelled)"
                    )
                tid = self.name(_arg(opts["TRANSID"]))
                dto, length = self.commarea_out(opts) if "COMMAREA" in opts else ("null", "null")
                rr = g.tmpname("rr")
                # failing (INVREQ / LENGERR) it returns to the program, which tests RESP; else the task ends
                return [f"{ind}int[] {rr} = task.returnImmediate({tid}, {dto}, {length});",
                        f"{ind}if ({rr}[0] == 0) {{ caBack.run(); throw new Goback(); }}",
                        *self.outcome(opts, f"{rr}[0]", f"{rr}[1]", ind)]  # fmt: skip
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
            if "CHANNEL" in opts:  # #4270: the target's current channel (CicsTask.xctlChannel)
                if "COMMAREA" in opts or "LENGTH" in opts:
                    raise CicsError(_msg("XCTL", "at_most_one", "CHANNEL"))
                call = f"task.xctlChannel({prog}, {self.name(_arg(opts['CHANNEL']))})"
            elif "COMMAREA" in opts:
                dto, length = self.commarea_out(opts, prog_lit)
                call = f"task.xctl({prog}, {dto}, {length})" if length != "null" else f"task.xctl({prog}, {dto})"
            else:
                call = f"task.xctl({prog}, null)"
            r = g.tmpname("xr")
            return ([f"{ind}String {r} = {call};", f"{ind}if (\"NORMAL\".equals({r})) throw new Goback();",
                    *self.outcome(opts, f"DetCics.resp({r})", f"DetCics.xctlResp2({r})", ind)])  # fmt: skip
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
            self.conditions(verb, opts)
            for cond, target in opts.items():
                if target is None:
                    out.append(f"{ind}handlers.remove({G_jstr(cond)});")
                    continue
                if target.upper() not in g.para_index:
                    raise CicsError(f"HANDLE CONDITION {cond}({target}): no such paragraph")
                out.append(f"{ind}handlers.put({G_jstr(cond)}, {g.para_index[target.upper()]});")
            return out
        if verb == "IGNORE CONDITION":
            return [f"{ind}handlers.put({G_jstr(c)}, -1);" for c in self.conditions(verb, opts, ignore=True)]
        if verb == "HANDLE AID":
            return self.handle_aid_(opts, ind)
        if verb in ("PUSH HANDLE", "POP HANDLE"):
            return self.push_pop(verb, opts, ind)
        if verb == "ABEND":
            code = self.name(_arg(opts["ABCODE"])) if opts.get("ABCODE") else '""'
            fn = "abendCancel" if "CANCEL" in opts else "abend"
            lbl = g.tmpname("exit")
            return [f"{ind}String {lbl} = task.{fn}({code});", f"{ind}if ({lbl} == null) throw abended();",
                    f"{ind}if (true) {g.jump(f'paragraph({lbl})')}"]  # fmt: skip
        if verb == "ASSIGN":
            return self.assign(opts, ind)
        if verb == "ASKTIME":
            if "ABSTIME" not in opts:  # #4737: only EIBDATE / EIBTIME are updated, and the region keeps them (X4)
                return [f"{ind}task.asktime();"]
            return [
                f"{ind}Cobol.store({self.field(_arg(opts['ABSTIME']))}, BigDecimal.valueOf(task.asktime()), false, CS);"
            ]
        if verb == "FORMATTIME":
            t = f"Cobol.num({self.field(_arg(opts['ABSTIME']))}, CS).longValue()"
            body = []
            for form in DATE_FORMS:
                if form in opts:
                    # DATESEP with no value is IBM's default separator, '/'; no DATESEP, none
                    sep = (self.text(_arg(opts["DATESEP"])) if opts.get("DATESEP")
                           else '"/"' if "DATESEP" in opts else '""')  # fmt: skip
                    body.append(f"Cobol.move(CicsTask.formatDate({t}, {G_jstr(form)}, {sep}), "
                                f"{self.field(_arg(opts[form]))}, CS);")  # fmt: skip
            if "TIME" in opts:
                sep = (self.text(_arg(opts["TIMESEP"])) if opts.get("TIMESEP")
                       else '":"' if "TIMESEP" in opts else '""')  # TIMESEP alone: IBM's ':'  # fmt: skip
                body.append(f"Cobol.move(CicsTask.formatTime({t}, {sep}), {self.field(_arg(opts['TIME']))}, CS);")
            if not body:
                raise CicsError("FORMATTIME form")
            if "RESP" not in opts and "RESP2" not in opts:
                # #4737 (X28): without RESP the INVREQ's handling (HANDLE CONDITION, the default abend) is not modelled:
                # CicsTask.formatDate / formatTime refuse an ABSTIME below zero at run time
                return [f"{ind}{ln}" for ln in body]
            # INVREQ RESP2 1 for an ABSTIME below zero (IBM), nothing written, through RESP / RESP2
            chk = g.tmpname("fmt")
            return [f"{ind}int[] {chk} = CicsTask.formattimeCheck({t});",
                    f"{ind}if ({chk}[0] == 0) {{",
                    *[f"{ind}    {ln}" for ln in body],
                    f"{ind}}}",
                    *self.outcome(opts, f"{chk}[0]", f"{chk}[1]", ind)]  # fmt: skip
        if key == "BIF DEEDIT":  # #4415 slice 1: IBM, EXEC CICS BIF DEEDIT (register X26)
            fld = self.field(_arg(opts.get("FIELD")))
            n = self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else f"{fld}.length()"
            r = g.tmpname("resp")
            self.region_used = True
            return [f"{ind}int {r} = CicsTask.deeditResp({n});",
                    f"{ind}if ({r} == 0) DetCics.deedit({fld}, {n}, CS, REGION);",
                    *self.outcome(opts, r, "0", ind)]  # fmt: skip
        if key == "INQUIRE ASSOCIATION":  # #4415 slice 2: the origin data of the task's own association (register X29)
            return self.inquire_association(opts, ind)
        if key == "INQUIRE URIMAP":  # #4270 zECS: the browse of the installed URIMAPs (register X32)
            return self.inquire_urimap(opts, ind)
        if key == "WRITE OPERATOR":  # #4270 zECS: a plain message to the console (register X32)
            if not opts.get("TEXT"):
                raise CicsError(_msg("WRITE OPERATOR", "required", "TEXT"))
            r = g.tmpname("wto")
            f = self.read_field(_arg(opts["TEXT"]))
            return [f"{ind}int {r} = task.writeOperator(Cobol.text({f}, CS));", *self.outcome(opts, r, "0", ind)]
        if key in ("INQUIRE TERMINAL", "SET TERMINAL"):  # #4415 slice 1: the terminal's UCTRANST CVDA (register X26)
            if "UCTRANST" not in opts:
                raise CicsError(f"{key} without UCTRANST")
            r = g.tmpname("term")
            term = self.name(_arg(opts.get("TERMINAL")))
            if key == "SET TERMINAL":
                return [f"{ind}int[] {r} = task.setUctranst({term}, {self.int_(_arg(opts['UCTRANST']))});",
                        *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]  # fmt: skip
            return [f"{ind}int[] {r} = task.inquireUctranst({term});",
                    f"{ind}if ({r}[0] == 0) "
                    + g.store_into(self.ref(_arg(opts["UCTRANST"])), f"BigDecimal.valueOf({r}[2])", False),
                    *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]  # fmt: skip
        if verb == "INQUIRE" and "PROGRAM" in opts:
            r = g.tmpname("resp")
            return [f"{ind}int {r} = task.inquireProgram({self.name(_arg(opts['PROGRAM']))});",
                    *self.outcome(opts, r, "0", ind)]  # fmt: skip
        if verb == "WRITEQ TD":
            r = g.tmpname("resp")
            f = self.read_field(_arg(opts["FROM"]))
            n = self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else str(self.size(_arg(opts["FROM"])))
            if opts.get("LENGTH"):  # #4607 x X6: a LENGTH past FROM is refused, as the stub refuses it
                n = f'DetCics.within({f}, {n}, "WRITEQ TD")'
            return [f"{ind}int {r} = task.writeqTd({self.name(_arg(opts['QUEUE']))}, "
                    f"Cobol.text({f}, CS).substring(0, {n}));",
                    *self.outcome(opts, r, "0", ind)]  # fmt: skip
        if verb in ("WRITEQ TS", "WRITEQ", "READQ TS", "READQ", "DELETEQ TS", "DELETEQ") \
                and verb.startswith(("WRITEQ", "READQ", "DELETEQ")) and "TD" not in words:  # fmt: skip
            return self.ts_queue(verb.split()[0], opts, ind)
        if verb in ("SYNCPOINT", "SYNCPOINT ROLLBACK"):
            # #4437: NORMAL -- the only outcome in this region (OPTIONS says why); EIBRESP / RESP / RESP2 written as
            # CICS writes them, never left as the previous command set them
            call = f"{ind}task.{'rollback' if verb == 'SYNCPOINT ROLLBACK' or 'ROLLBACK' in opts else 'syncpoint'}();"
            out = [call, *self.outcome({**opts, "NOHANDLE": None}, "0", "0", ind)]  # (NORMAL raises no condition)
            if "RESP2" in opts and "RESP" not in opts:  # RESP2 alone is written too
                out.append(ind + self.g.store_into(self.ref(_arg(opts["RESP2"])), "BigDecimal.valueOf(0)", False))
            return out
        if verb == "SEND CONTROL":
            return self.send_control(opts, ind)
        if verb == "RECEIVE":
            return self.receive(opts, ind)
        # #4270 spec PR 2: a command we do not model, refused whole -- with its name-only (or engine-only) entry's
        # reason when it is a CICS application command the spec lists
        known = whole_refusal(key, verb, next(iter(opts), None))
        raise CicsError(known.whole_message(verb) if known is not None else f"EXEC CICS {verb} not modelled")

    # -- #4270: channels and containers
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
            out += [f"{ind}int {ln} = {n};",
                    (f"{ind}CicsTask.ContainerResult {r} = task.putContainer({chan}, {name}, "
                     f"DetCics.containerData({f}, {ln}), {ln}, {G_jstr(dtype) if dtype else 'null'}, "
                     f"{str('APPEND' in opts).lower()});")]  # fmt: skip
        elif key == "GET CONTAINER":
            into, nodata = opts.get("INTO") or "", "NODATA" in opts
            if bool(into) == nodata:
                raise CicsError(_msg("GET CONTAINER", "one_of", "INTO"))
            flen = _option(opts, "FLENGTH")
            settable = flen is not None and re.fullmatch(r"(?is)[+-]?\d+|LENGTH\s+OF\s+.+", flen.strip()) is None
            if nodata:
                out.append(f"{ind}CicsTask.ContainerResult {r} = task.getContainer({chan}, {name}, -1);")
            else:
                target = self.field(into)
                most = self.int_(flen) if flen else str(self.size(into))
                out += [(f"{ind}CicsTask.ContainerResult {r} = task.getContainer({chan}, {name}, "
                         f"DetCics.containerLimit({target}, {most}));"),
                        f"{ind}if ({r}.data() != null) DetCics.put({target}, {r}.data());"]  # fmt: skip
            if flen is not None and settable:
                set_back = g.store_into(self.ref(flen), f"BigDecimal.valueOf({r}.length())", False)
                out.append(f"{ind}if ({r}.length() >= 0) {set_back}")
        else:
            out.append(f"{ind}CicsTask.ContainerResult {r} = task.deleteContainer({chan}, {name});")
        return out + self.outcome(opts, f"DetCics.resp({r}.resp())", f"{r}.resp2()", ind)

    # -- #4270 slice 2: interval control
    def _number(self, text: str) -> str:
        """An INTERVAL / TIME / HOURS ... value as a Java int expression (a literal's leading zeros dropped)."""
        t = text.strip()
        return str(int(t)) if re.fullmatch(r"\d+", t) else self.int_(t)

    def start(self, opts: dict, ind: str) -> list[str]:
        """START TRANSID (IBM CICS TS, EXEC CICS START) on CicsTask.startRequest: INTERVAL(hhmmss) / TIME(hhmmss) /
        AFTER or AT HOURS MINUTES SECONDS (none: INTERVAL(0)), TERMID, REQID, PROTECT, FROM's first LENGTH bytes (no
        LENGTH: FROM's length), and the data options RTRANSID / RTERMID / QUEUE the started task RETRIEVEs. The
        request's expiry, INVREQ RESP2 4 / 5 / 6, LENGERR, TRANSIDERR, TERMIDERR and IOERR are CicsTask's, through
        RESP / HANDLE CONDITION. FROM's bytes go in the region's page, as a TS item's do (#4528): the started task's
        RETRIEVE reads them back into its own storage's page."""
        if not opts.get("TRANSID"):
            raise CicsError(_msg("START", "required", "TRANSID"))
        whens = [w for w in ("INTERVAL", "TIME", "AFTER", "AT") if w in opts]
        if len(whens) > 1:
            raise CicsError(_msg("START", "at_most_one", "INTERVAL", " and ".join(whens)))
        when = whens[0] if whens else "INTERVAL"
        hms = [o for o in ("HOURS", "MINUTES", "SECONDS") if o in opts]
        if (when in ("AFTER", "AT")) != bool(hms):
            raise CicsError(_msg("START", "requires", "HOURS", when, " ".join(hms)))
        chain = f"task.startRequest({self.name(_arg(opts['TRANSID']))})"
        if hms:
            vals = [self._number(_arg(opts[o])) if o in opts else "null" for o in ("HOURS", "MINUTES", "SECONDS")]
            chain += f".{when.lower()}({', '.join(vals)})"
        elif when in opts:
            chain += f".{when.lower()}({self._number(_arg(opts[when]))})"
        for o in ("TERMID", "REQID", "RTRANSID", "RTERMID", "QUEUE"):
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
        ENVDEFERR and LENGERR through RESP / HANDLE CONDITION. SET (a pointer) and WAIT are refused (OPTIONS)."""
        into = opts.get("INTO")
        length = _one_of(opts, "LENGTH", "FLENGTH")
        named = [o for o in ("RTRANSID", "RTERMID", "QUEUE") if o in opts]
        if not into and (not named or length is not None):
            raise CicsError(_msg("RETRIEVE", "requires", "LENGTH"))
        g = self.g
        r = g.tmpname("retrieved")
        most = "null"
        if into:
            most = self.int_(length) if length else str(self.size(into))
        flags = ", ".join(str(o in named).lower() for o in ("RTRANSID", "RTERMID", "QUEUE"))
        out = [f"{ind}CicsTask.RetrieveResult {r} = task.retrieve({most}, {flags});"]
        if into:
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
        transid, child = _option(opts, "TRANSID"), _option(opts, "CHILD")
        if not transid or not child:
            raise CicsError(_msg("RUN", "required", "TRANSID"))
        r = self.g.tmpname("run")
        return [f"{ind}CicsTask.RunResult {r} = task.runTransid({self.name(transid)});",
                f"{ind}if ({r}.child() != null) DetCics.putPadded({self.field(child)}, {r}.child(), CS);",
                *self.outcome(opts, f"DetCics.resp({r}.resp())", f"{r}.resp2()", ind)]  # fmt: skip

    def cancel(self, opts: dict, ind: str) -> list[str]:
        """CANCEL REQID (IBM CICS TS, EXEC CICS CANCEL) on CicsTask.cancel: NORMAL for a request not yet expired,
        NOTFND when none matches "an unexpired interval control command"."""
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
        cursor = "null"
        if "CURSOR" in opts:
            if not opts["CURSOR"]:
                raise CicsError("SEND CONTROL CURSOR without a value: not modelled")
            cursor = self.int_(opts["CURSOR"])
        flags = [o for o in _SEND_CONTROL if o in opts]  # (sorted by the runtime)
        return [f"{ind}task.sendControl({cursor}{''.join(', ' + G_jstr(x) for x in sorted(flags))});",
                *self.outcome(opts, "0", "0", ind)]  # fmt: skip

    def receive(self, opts: dict, ind: str) -> list[str]:
        """A terminal RECEIVE (IBM, EXEC CICS RECEIVE (3270 logical), (LUTYPE2/LUTYPE3)) on CicsTask.receive.

        INTO: the most taken is MAXLENGTH, else LENGTH's value, else INTO's length; the data goes into INTO's first
        bytes. SET(ADDRESS OF record): the LINKAGE record addresses the data (DetCics.receivedSet); it needs MAXLENGTH
        -- without it IBM's "the value indicated in the LENGTH option is assumed" reads LENGTH, which SET only sets
        -- and LENGTH(data-area). LENGTH / FLENGTH is set to the length the runtime returns (the data's, or under
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
            if m is None:
                raise CicsError(f"RECEIVE SET({opts['SET']}): pointers are not modelled, only SET(ADDRESS OF record)")
            item = g.resolve(E.Ref(m.group(1).upper()))
            if getattr(item, "section", None) != "LINKAGE" or getattr(item, "level", None) != 1:
                raise CicsError(f"RECEIVE SET(ADDRESS OF {m.group(1)}): not a LINKAGE 01 record")
            if not most:
                raise CicsError("RECEIVE SET without MAXLENGTH: the most it takes is not documented")
            if not settable:
                raise CicsError("RECEIVE SET without LENGTH(data-area)")
            target = self.field(m.group(1))
            limit = self.int_(most)
            put = "receivedSet"
        else:
            raise CicsError(_msg("RECEIVE", "one_of", "INTO"))
        r = g.tmpname("received")
        out = [f"{ind}CicsTask.Received {r} = task.receive({limit}, {str('NOTRUNCATE' in opts).lower()});",
               f"{ind}DetCics.{put}({target}, {r}.data(), CS);"]  # fmt: skip
        if settable and length is not None:
            out.append(ind + g.store_into(self.ref(length), f"BigDecimal.valueOf({r}.length())", False))
        return out + self.input_outcome(opts, f"DetCics.resp({r}.resp())", ind)

    def inquire_association(self, opts: dict, ind: str) -> list[str]:
        """INQUIRE ASSOCIATION(EIBTASKN) ODAPPLID / ODUSERID / ODFACILNAME / ODNETWORKID (8 characters) and ODFACILTYPE (a
        CVDA): the origin data of the task's own association data, as the run states it (CicsTask.withOrigin; unstated,
        refused). IBM gives no representation for the task number, so only the task's own number, EIBTASKN, is read: any
        other operand (a literal, a copy of it) is refused. A command with no origin option is refused: IBM's
        INVREQ RESP2 2 ("The command was specified with no arguments") does not say whether ASSOCIATION alone is none."""
        if re.fullmatch(r"(?is)\s*EIBTASKN\s*", _arg(opts.get("ASSOCIATION"))) is None:
            raise CicsError(
                f"INQUIRE ASSOCIATION({opts.get('ASSOCIATION')}): only the task's own number, EIBTASKN, is "
                "modelled (IBM gives no representation for the 4 bytes)"
            )
        wanted = [o for o in ("ODAPPLID", "ODUSERID", "ODFACILNAME", "ODNETWORKID", "ODFACILTYPE") if o in opts]
        if not wanted:
            raise CicsError(
                "INQUIRE ASSOCIATION without an origin option: IBM's INVREQ RESP2 2 (\"The command was "
                'specified with no arguments") does not say whether ASSOCIATION alone is none: not modelled'
            )
        r = self.g.tmpname("assoc")
        out = [f"{ind}CicsTask.Origin {r} = task.inquireAssociation();"]
        for k, acc in (("ODAPPLID", "applid"), ("ODUSERID", "userid"), ("ODFACILNAME", "facilname"),
                       ("ODNETWORKID", "networkid")):  # fmt: skip
            if k in opts:
                out.append(f"{ind}DetCics.putText({self.field(_arg(opts[k]))}, {r}.{acc}(), CS);")
        if "ODFACILTYPE" in opts:
            out.append(
                ind
                + self.g.store_into(self.ref(_arg(opts["ODFACILTYPE"])), f"BigDecimal.valueOf({r}.faciltype())", False)
            )
        return out + self.outcome(opts, "0", "0", ind)

    def inquire_urimap(self, opts: dict, ind: str) -> list[str]:
        """INQUIRE URIMAP START / NEXT / END (IBM CICS TS, INQUIRE URIMAP, "Browsing resource definitions"): the browse of
        the URIMAP definitions the run states are installed (CicsTask.withUrimaps; unstated, refused). NEXT hands back the
        definition's name (8), PATH (255) and TRANSACTION (4), blank-padded, only on NORMAL; END (RESP2 2) and ILLOGIC
        (RESP2 1) leave the areas alone. START / END name no output area."""
        g = self.g
        form = [f for f in ("START", "NEXT", "END") if f in opts]
        if len(form) != 1:
            raise CicsError(_msg("INQUIRE URIMAP", "one_of", "START"))
        r = g.tmpname("urimap")
        call = {"START": "inquireUrimapStart", "NEXT": "inquireUrimapNext", "END": "inquireUrimapEnd"}[form[0]]
        outs = [k for k in ("URIMAP", "PATH", "TRANSACTION") if k in opts]
        if form[0] != "NEXT" and outs:
            raise CicsError(f"INQUIRE URIMAP {form[0]} {outs[0]}: a browse {form[0]} returns no definition")
        out = [f"{ind}int[] {r} = task.{call}();"]
        if outs:
            out.append(f"{ind}if ({r}[0] == 0) {{")
            for k, acc in (("URIMAP", "urimapName"), ("PATH", "urimapPath"), ("TRANSACTION", "urimapTransaction")):
                if k in opts:
                    out.append(f"{ind}    DetCics.putText({self.field(_arg(opts[k]))}, task.{acc}(), CS);")
            out.append(f"{ind}}}")
        return out + self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)

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
            n = self.int_(_arg(opts["LENGTH"])) if opts.get("LENGTH") else f"{f}.length()"
            if opts.get("LENGTH"):  # #4607 x X6: a LENGTH past FROM is refused, as the stub refuses it
                n = f'DetCics.within({f}, {n}, "WRITEQ TS")'
            # #4528: the item in the region's page, as the COBOL side's region keeps it
            data = f"DetCics.toRegion(DetCics.bytes({f}, {n}), CS, REGION)"
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
            out.append(f"{ind}if ({r}.data() != null) DetCics.put({into}, DetCics.fromRegion({r}.data(), REGION, CS));")
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

    def map_not_found(self, m: str, ms: str, ind: str) -> list[str] | None:
        """IBM CICS TS (SEND MAP / RECEIVE MAP; abend code ABM0, register X31): a map is found only inside its own
        mapset (BMS: DFHMSD names the mapset, each DFHMDI a map; MAPSET defaults to the MAP name when omitted). A name
        that is a mapset of the estate but no map of it asks CICS for a map the mapset does not hold: ABM0, "The map
        specified for a basic mapping support (BMS) request could not be located", the transaction abnormally
        terminated. No condition is raised (neither command lists one), so RESP / HANDLE CONDITION do not see it; a
        HANDLE ABEND exit does -- the lines are EXEC CICS ABEND's, with the abend CICS raises. None: not that case."""
        if ms not in self.gp.mapsets or m in self.gp.mapsets[ms]:
            return None
        lbl = self.g.tmpname("exit")
        return [f"{ind}String {lbl} = task.abendMapNotFound({G_jstr(m)}, {G_jstr(ms)});",
                f"{ind}if ({lbl} == null) throw abended();",
                f"{ind}if (true) {self.g.jump(f'paragraph({lbl})')}"]  # fmt: skip

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
        return out + self.input_outcome(opts, resp, ind)

    # -- #4213: an ESDS browsed by relative byte address (IBM DBB EPSMLIST)
    def _rba(self, verb: str, opts: dict) -> bool:
        """Whether the command addresses its file by RBA; what is not modelled is a hole by name. Modelled: STARTBR /
        READNEXT / READPREV ... RBA (CicsTask's RBA browse, oracle_assumptions.md X13). XRBA, RRN, READ / WRITE / DELETE
        by RBA, and GTEQ / KEYLENGTH / GENERIC / REQID in an RBA browse are not (IBM: GTEQ "is not valid for directly
        browsing an ESDS")."""
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

    def constant_int(self, text: str) -> int | None:
        """An option's value when the translator knows it: an integer literal, LENGTH OF an item, or a data item
        with a numeric VALUE the program never changes; else None."""
        from gitgalaxy.tools.cobol_to_java.det.gen import Untranslatable

        unknown = (CicsError, E.ExprError, KeyError, Untranslatable)  # (None: the caller refuses)
        t = text.strip()
        if re.fullmatch(r"\d+", t):
            return int(t)
        m = re.fullmatch(r"(?is)LENGTH\s+OF\s+(.+)", t)
        if m:
            try:
                return self.size(m.group(1))
            except unknown:
                return None
        try:
            it = self.g.resolve(self.ref(t))
        except unknown:
            return None
        vals = getattr(it, "values", None) or []
        if len(vals) == 1 and vals[0][0] == "num" and self.g.never_written(it):
            return int(vals[0][1])
        return None

    def _keylength(self, verb: str, opts: dict) -> int | None:
        """#4411: KEYLENGTH is honoured only as what it changes nothing for, the file's full key (a shorter one is a
        generic key, an unequal one INVREQ): a known value equal to the key's length, on a file the port knows.

        #4270 READ GENERIC (oracle_assumptions.md X22): the generic key's length -- a known value above zero and
        shorter than the key (IBM, EXEC CICS READ: INVREQ RESP2 25 for one "greater than or equal to the length of a
        full key", 42 below zero; zero undocumented), refused by name otherwise. Returns the length searched: the
        generic key's, else the full key's (None without KEYLENGTH)."""
        generic = verb == "READ" and "GENERIC" in opts
        if "KEYLENGTH" not in opts:
            return None
        arg = _arg(opts["KEYLENGTH"])
        n = self.constant_int(arg)
        name = self.constant(opts.get("DATASET") or opts.get("FILE"))
        mapped = self.gp.file(name) if name is not None else None
        if n is None or mapped is None:
            raise CicsError(f"{verb} KEYLENGTH({arg}): not a known length on a known file, so maybe not the full key")
        _, key = self.gp.entity_key(mapped[1], mapped[2])
        if generic and n >= key:
            raise CicsError(f"{verb} GENERIC KEYLENGTH({arg}) = {n}, the key is {key}: INVREQ (RESP2 25) not modelled")
        if generic and n <= 0:
            raise CicsError(f"{verb} GENERIC KEYLENGTH({arg}) = {n}: not above zero (INVREQ / undocumented)")
        if not generic and n != key:
            raise CicsError(f"{verb} KEYLENGTH({arg}) = {n}, the key is {key}: a partial key is not modelled")
        return n

    def _search(self, opts: dict, file: str, st: str, rec: str) -> tuple[str, str] | None:
        """#4270 READ GTEQ / GENERIC (oracle_assumptions.md X22): the read call and the held key's expression, None for
        a plain keyed READ. IBM, EXEC CICS READ: GENERIC -- "the search key is a generic key whose length is
        specified in the KEYLENGTH option"; GTEQ -- "if the search for a record that has the same key (complete or
        generic) ... is unsuccessful, the first record that has a greater key is retrieved"; NOTFND RESP2 80
        (CicsTask.readSearch). A READ UPDATE holds the record found (its key, not RIDFLD's)."""
        gteq, generic = "GTEQ" in opts, "GENERIC" in opts
        if not (gteq or generic):
            return None
        if gteq and "EQUAL" in opts:
            raise CicsError(_msg("READ", "at_most_one", "EQUAL", "EQUAL", "GTEQ"))
        if generic and "KEYLENGTH" not in opts:
            raise CicsError(_msg("READ", "requires", "GENERIC"))
        n = self._keylength("READ", opts)
        if n is None:  # GTEQ on the full key: the file's
            name = self.constant(opts.get("DATASET") or opts.get("FILE"))
            mapped = self.gp.file(name) if name is not None else None
            if mapped is None:
                raise CicsError("READ GTEQ: not a known file, so not a known key length")
            _, n = self.gp.entity_key(mapped[1], mapped[2])
        rid = _arg(opts.get("RIDFLD"))
        if self.size(rid) < n:  # CICS would read the storage after RIDFLD, laid out unlike IBM's by GnuCOBOL (X6)
            raise CicsError(f"READ RIDFLD({rid}) is {self.size(rid)} bytes, shorter than the {n} bytes searched")
        update = "true" if "UPDATE" in opts else "false"
        call = f"task.readSearch({file}, {update}, () -> {st}.search({rec}, {n}, {'true' if gteq else 'false'}))"
        return call, f"{st}.keyOf({{}}.record())"

    def _read_length(self, verb: str, opts: dict) -> str | None:
        """A read's LENGTH (IBM, EXEC CICS READ: "the length ... of the data area where the record is to be put. On
        completion ... the actual length of the record"; a longer record "is truncated", LENGERR RESP2 11).

        #4436: a keyed READ models it (DetCics.readInto): the LENGTH operand is returned for the code to emit, or None
        where it changes nothing -- a literal or LENGTH OF equal to INTO's own length, nothing to set back. READNEXT /
        READPREV and the RBA browse still honour only INTO's own length (#4411); any other is refused by name."""
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
        if self._rba(verb, opts):
            self._read_length(verb, opts)
            return self.rba_browse(verb, opts, ind)
        searched = verb == "READ" and ("GTEQ" in opts or "GENERIC" in opts)
        if not searched:
            self._keylength(verb, opts)
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
            fn = "readForUpdate" if "UPDATE" in opts else "read"
            call, held = f"task.{fn}({file}, () -> {st}.find({rec}))", rec
            search = self._search(opts, file, st, rec)
            if search is not None:
                call, held = search[0], search[1].format(r)
            out = [
                f"{ind}byte[] {rec} = DetCics.bytes({rid});",
                f"{ind}CicsTask.FileRead<byte[]> {r} = {call};",
                f"{ind}if ({r}.record() != null) {{",
                f"{ind}    DetCics.put({into}, {r}.record());",
                *([f"{ind}    heldKey.put({file}, {held});"] if "UPDATE" in opts else []),
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

    def read_length(self, opts: dict, length: str, file: str, st: str, into: str, rid: str, ind: str) -> list[str]:
        """#4436: READ ... INTO LENGTH(length). LENGTH's value is the most the program takes: the record goes INTO,
        truncated to it with LENGERR (22, RESP2 11) when longer, and LENGTH is set to the record's length (on NORMAL
        and LENGERR; a literal's or LENGTH OF's temporary is set by CICS and read by no one). What IBM leaves
        undocumented or the storage layout decides is refused at run time by DetCics.readInto (a negative LENGTH; a
        record moved past INTO; LENGERR on READ UPDATE -- whether the record is still held)."""
        g = self.g
        r, rec = g.tmpname("read"), g.tmpname("rec")
        resp, resp2 = g.tmpname("resp"), g.tmpname("resp2")
        update = "UPDATE" in opts
        fn = "readForUpdate" if update else "read"
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
        if update:
            out.append(f"{ind}    heldKey.put({file}, {held});")  # (LENGERR on READ UPDATE: refused above)
        if settable:
            set_back = g.store_into(self.ref(length), f"BigDecimal.valueOf({r}.record().length)", False)
            out.append(f"{ind}    {set_back}")
        out.append(f"{ind}}}")
        return out + self.outcome(opts, resp, resp2, ind)

    def record_from(self, opts: dict) -> str:
        """A WRITE / REWRITE's record: FROM's bytes, or LENGTH bytes from FROM's first (as CICS reads them)."""
        frm = self.read_field(opts["FROM"])
        if opts.get("LENGTH"):
            return f"DetCics.bytes({frm}, {self.int_(_arg(opts['LENGTH']))})"
        return f"DetCics.bytes({frm})"

    def file_update(self, verb: str, opts: dict, ind: str) -> list[str]:
        if self._rba(verb, opts):
            return self.rba_browse(verb, opts, ind)
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


def _option(opts: dict, name: str) -> str | None:
    """#4270: an option's argument, None when the option is not given; given without one, refused."""
    if name not in opts:
        return None
    return _arg(opts[name])


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


def _one_of(opts: dict, name: str, alt: str) -> str | None:
    """#4413: the argument of option `name` or its alternative form `alt` (LENGTH / FLENGTH), None when neither is
    given; both, or one without an argument, refused."""
    given = [o for o in (name, alt) if o in opts]
    if len(given) > 1:
        raise CicsError(BOTH_FORMS.format(name, alt))
    if given and not opts[given[0]]:
        raise CicsError(f"{given[0]} needs an argument")
    return opts[given[0]] if given else None


def _literal(text: str | None) -> str | None:
    if text and text.strip()[:1] in "'\"":
        return text.strip()[1:-1].upper()
    return None


def G_jstr(s: str) -> str:
    from gitgalaxy.tools.cobol_to_java.det.gen import jstr

    return jstr(s)
