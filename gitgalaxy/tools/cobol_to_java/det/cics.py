"""EXEC CICS commands of a deterministic port, onto the generated project's CicsTask.

Every typed object at the boundary is the generator's: the COMMAREA DTOs (dto/contract, each property's comment
naming its COBOL field, PICTURE and offset), the screen view models (dto/screen: fromValues / screenValues by BMS
field name), and the entities of each CICS file (the stub's "<DSN> as CICS file <NAME>" methods). The port converts
between them and the program's own bytes -- nothing is taken from a test case."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from gitgalaxy.standards.cics.commands import COMMANDS as SPEC
from gitgalaxy.standards.cics.commands import whole_refusal
from gitgalaxy.standards.cics.commands.api import COUNTER
from gitgalaxy.standards.cics.commands.assign import (
    TERMINAL_OPTIONS,  # noqa: F401 -- the conditions mixin reads it here
)
from gitgalaxy.standards.cics.commands.handles import AID_KEYS  # noqa: F401 -- the conditions mixin reads it here
from gitgalaxy.standards.cics.commands.send_text import TEXT_OPTIONS
from gitgalaxy.standards.cics.commands.task import DATE_FORMS, NUMBER_FORMS
from gitgalaxy.standards.cics.commands.terminal import MAP_OPTIONS
from gitgalaxy.standards.cics.resp import DFHRESP  # noqa: F401 -- tests and the conditions mixin read it here
from gitgalaxy.tools.cobol_to_java.det import expr as E
from gitgalaxy.tools.cobol_to_java.det import layout as L
from gitgalaxy.tools.cobol_to_java.det.cics_common import (  # noqa: F401 -- re-exported for the mixins' old importers
    _SEND_CONTROL,
    REGION_PAGE,
    CicsError,
    KeylengthInvreq,
    Untranslatable,
    _arg,
    _msg,
    _one_of,
    _option,
    _requires,
    jstr,
    region_page,
)
from gitgalaxy.tools.cobol_to_java.det.cics_conditions import ConditionCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_containers import ContainerCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_faults import FaultCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_filecontrol import FileControlCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_taskcontrol import TaskControlCommands  # #5274

COPY = Path(__file__).parent / "copy"  # DFHEIBLK, DFHAID, DFHBMSCA


# #5126 (X64): the file control commands set EIBDS, "the symbolic identifier of the last data set referred to in a file
# control request" (IBM, EIB fields); the stub's twin is equivalence_cics.EIBDS_VERBS
EIBDS_VERBS = frozenset({"READ", "READNEXT", "READPREV", "RESETBR", "STARTBR", "ENDBR", "WRITE", "REWRITE", "DELETE",
                         "UNLOCK"})  # fmt: skip
EIBDS_WORD = re.compile(r"(?<![A-Z0-9-])EIBDS(?![A-Z0-9-])")
EIBRCODE_WORD = re.compile(r"(?<![A-Z0-9-])EIBRCODE(?![A-Z0-9-])")


def reads_eibds(statements, word=EIBDS_WORD) -> bool:
    """#5126 (X64): does any statement text name EIBDS -- a whole word, not the front of a hyphenated user name
    (EIBDS-X) and not a literal's text ('EIBDS: ')? `word` picks the field (EIBRCODE_WORD: reads_eibrcode)."""
    return any(word.search(re.sub(r"'[^']*'|\"[^\"]*\"", "''", t.upper())) for t in statements)


def reads_eibrcode(statements) -> bool:
    """#5126 (X64): the same whole-word rule for EIBRCODE (the stub's twin is equivalence_cics.reads_eibrcode)."""
    return reads_eibds(statements, EIBRCODE_WORD)


# #4411: every option each modelled command accepts -- the CICS command spec's (gitgalaxy/standards/cics, #4270 spec
# PR 2): an option outside its command's set is refused by name (the statement becomes a hole), with the reason the
# command's own spec entry gives, never accepted and ignored: a silently divergent port is worse than a visible hole.
# None: every option is checked by the command's handler (HANDLE / IGNORE CONDITION's conditions, HANDLE AID's keys).
OPTIONS: dict[str, frozenset | None] = {
    k: None if c.open_options else frozenset(c.options) for k, c in SPEC.items() if c.status == "modelled"
}
_FORMS = (*DATE_FORMS, *NUMBER_FORMS)


def command_key(words: list[str], opts: dict) -> str:
    """The OPTIONS key of a parsed command (the verb words, plus the option that names the form: SEND MAP)."""
    verb = " ".join(words)
    first = words[0] if words else ""
    if first in ("ENQ", "DEQ", "DELAY"):
        return first
    if first in ("GET", "PUT", "DELETE", "MOVE") and "CONTAINER" in opts:  # #4270 (DELETE CONTAINER is no file's)
        return f"{first} CONTAINER"
    if first in ("GET64", "PUT64") and "CONTAINER" in opts:  # #5005 (X17): the 64-bit forms
        return f"{first} CONTAINER"
    if (
        first in ("DELETE", "QUERY") and "CHANNEL" in opts and "CONTAINER" not in opts
    ):  # #5005 (DELETE CONTAINER is above)
        return f"{first} CHANNEL"
    if first == "GETNEXT" and "CONTAINER" in opts:  # #4951: GETNEXT CONTAINER(area) BROWSETOKEN(token)
        return "GETNEXT CONTAINER"
    if verb == "GET" and "DCOUNTER" in opts:  # #4767 (X30): GET DCOUNTER is the doubleword form of GET COUNTER's entry
        return "GET COUNTER"
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
    "INQUIRE": ("PROGRAM", "TERMINAL", "ASSOCIATION", "URIMAP", "TDQUEUE"),
    "SET": ("TERMINAL", "TDQUEUE"),
    "VERIFY": ("PASSWORD",),  # #5859: VERIFY PASSWORD(pw) USERID(id), the form word is an option
    "WEB READ": ("HTTPHEADER", "FORMFIELD", "QUERYPARM"),  # #4767 / #4940 (X38): the form word is an option
    "WEB WRITE": ("HTTPHEADER",),
    "WEB STARTBROWSE": ("HTTPHEADER", "FORMFIELD", "QUERYPARM"),  # #4940 (X38): the WEB browse forms
    "WEB READNEXT": ("HTTPHEADER", "FORMFIELD", "QUERYPARM"),
    "WEB ENDBROWSE": ("HTTPHEADER", "FORMFIELD", "QUERYPARM"),
    "FETCH": ("ANY", "CHILD"),  # #4884
    "FREE": ("CHILD",),  # #4950: FREE CHILD(token): the form word is an option with an argument
    "WEB PARSE": ("URL",),  # #4767 (X36): WEB PARSE URL(area): the form word is an option with an argument
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
# an option with no argument that can come first, so is never a verb word (#4413: RECEIVE NOTRUNCATE INTO(...))
_BARE_OPTIONS = ("NOTRUNCATE", "NOHANDLE")  # (#4737: ASKTIME NOHANDLE)
# a second word that is an option of the verb before it, never a verb word (#5119: IBM's own `READ UPDATE DATASET(...)`)
_SECOND_OPTIONS = {
    "READ": ("UPDATE",),
    "READNEXT": ("UPDATE",),
    "READPREV": ("UPDATE",),
    "POST": ("AFTER", "AT"),  # #5079 (X63): POST AFTER SECONDS(n)
}


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
        elif (
            not opts
            and len(words) < 2
            and name not in MAP_OPTIONS
            and name not in _BARE_OPTIONS
            and not (words and name in _SECOND_OPTIONS.get(words[0], ()))
        ):
            words.append(name)
        else:
            opts[name] = None
    return words, opts


# ---- the generated DTOs ----------------------------------------------------------------------------------------
_PROP = re.compile(r"//\s*(.+?)\n(?:\s*//\s*OCCURS\s+(\d+)\s+TIMES\n)?\s*private\s+([\w.<>]+)\s+(\w+);")
_LIST = re.compile(r"List<(\w+)>")
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
    size: int  # one occurrence's bytes
    source: str | None = None  # the copybook the generator read the field from
    occurs: int = 1  # #5565: a List<T> property: `occurs` consecutive `size`-byte items


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
    def extent(self) -> int:
        """Where the DTO's last property ends, in storage bytes: what its object carries."""
        n = max((self.at(x.offset) + (POINTER_BYTES if x.usage == "POINTER" else x.size * x.occurs) for x in self.leaves),
                default=0)  # fmt: skip
        return max([n] + [self.at(off) + p.size for _, p, off in self.parts])

    @property
    def size(self) -> int:
        """The bytes the COMMAREA's record spans in the port's storage: what a LINK passes, a RETURN / XCTL hands on
        and EIBCALEN says -- the declared record, never only the bytes the DTO's properties reach."""
        n = self.extent
        if self.record:
            # #4270 (C9) / #4765: a DTO whose OCCURS fields appear once (CBSA's INQACCCU-COMMAREA, 20 accounts): the
            # whole record, every occurrence, travels -- its declared bytes, each POINTER as wide as the storage's.
            # #4778: so does one whose record ends in a FILLER no property names (CBSA's CUSTCTRL DFHCOMMAREA, 217
            # bytes of FILLER after CUSTOMER-CONTROL-FAIL-CODE; GenApp LGICVS01's 60): its caller's bytes, by reference
            n = max(n, self.record + self.wider)
        return n


def _typed(cls: str) -> str | None:
    """#5053: the class a stub types a COMMAREA with, None when it types none: a DFHCOMMAREA that is no record (PIC X(30))
    is `Object request`, and Object is no generated DTO (it read as a missing dto/contract class: a hole)."""
    return None if cls == "Object" else cls


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
        return _typed(m.group(1)) if m else None

    def __init__(self, project: Path, stub: str):
        self.java = project / "src/main/java"
        self.dtos: dict[str, Dto] = {}
        self.contract = None
        m = re.search(r"handleTransaction\(String transid, (\w+) request\)", stub)
        if m:
            self.contract = _typed(m.group(1))
        else:  # a program only ever LINKed to (CBSA's): its COMMAREA is handleLink's
            m = re.search(r"public \w+ handleLink\((\w+) request\)", stub)
            if m:
                self.contract = _typed(m.group(1))
        # LINK targets: link<Program>(Type request), as the stub types each (local or distributed)
        self.links = {mm.group(1).upper(): mm.group(2)
                      for mm in re.finditer(r"public \w+ link(\w+)\((\w+) request\)", stub) if _typed(mm.group(2))}  # fmt: skip
        self.xctl = {mm.group(1).upper(): mm.group(2)
                     for mm in re.finditer(r"public \w+ xctl(\w+)\((\w+) request\)", stub) if _typed(mm.group(2))}  # fmt: skip
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
            entity = ent.group(1) if ent else None
            if r and not ent and r.group(2) == "deleteById" and len(r.group(1)) > len("Repository"):
                # #4771: a file the program only DELETEs by RIDFLD (ZC@ID@KEY) has a void deleteX(key) stub, no entity
                # in its signature; the forge names the repository field <entity>Repository
                stem = r.group(1)[: -len("Repository")]
                entity = stem[:1].upper() + stem[1:]
            if r and entity:
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
                    files[name] = (r.group(1), entity, prop[0].lower() + prop[1:] if prop else None)

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
        for comment, table, jtype, var in _PROP.findall(text):
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
            n, elem = int(table or 1), _LIST.fullmatch(jtype) if table else None
            if elem:  # #5565: `OCCURS n` on an elementary item is a List of its occurrences (CardDemo's PAUKEY-PREV-PG)
                jtype = elem.group(1)
            if not leaf or jtype not in ("String", "Integer", "Long", "Short", "BigDecimal", "java.math.BigDecimal") \
                    or bool(table) != bool(elem):  # fmt: skip
                raise CicsError(f"{cls}.{var}: a property the port cannot convert ({jtype})")
            width = int(leaf.group(5))
            if width % n:
                raise CicsError(f"{cls}.{var}: an OCCURS {n} table whose {width} bytes are not {n} equal items")
            d.leaves.append(Leaf(var, jtype, leaf.group(1), leaf.group(2), (leaf.group(3) or "DISPLAY").upper(),
                                 int(leaf.group(4)), width // n, leaf.group(6), n))  # fmt: skip
        self.dtos[cls] = d
        return d

    def entity_key(self, entity: str, prop: str | None) -> tuple[int, int]:
        text = self._file("entity/vsam", entity).read_text(encoding="utf-8")
        if prop is None:
            m = re.search(r"Key: .*?\(offset (\d+), (\d+) bytes", text)
            if not m:
                # #6876: the forge writes "Key: TODO: no key is known" when no IDCAMS DEFINE / RECORD KEY / RIDFLD
                # field of the record names one (a RIDFLD item outside the record, as HCUNLK's WS-KEY, names none);
                # a KSDS key offset is the cluster's definition, so the port does not guess offset 0
                raise CicsError(
                    f"{entity}: no key (the generated entity states none: no IDCAMS DEFINE, RECORD KEY or RIDFLD "
                    "field inside the record names it, and a KSDS key's offset is not guessed)"
                )
            return int(m.group(1)), int(m.group(2))
        for m in re.finditer(r"//[^\n]*offset (\d+), (\d+) bytes[^\n]*\n(?:\s*@[^\n]*\n)*\s*private\s+[\w.<>]+\s+(\w+);",
                             text):  # fmt: skip
            if m.group(3) == prop:
                return int(m.group(1)), int(m.group(2))
        raise CicsError(f"{entity}.{prop}: no offset")

    def screen_fields(self, cls: str) -> list[str]:
        text = self._file("dto/screen", cls).read_text(encoding="utf-8")
        return re.findall(r'values\.put\("([A-Z0-9-]+)"(?:,| \+ )', text)  # #5076: a repeated field: "NAME" + "." + i

    def screen_occurs(self, cls: str) -> dict[str, int]:
        """#5076: the BMS fields a map repeats (DFHMDF OCCURS=n), by name -> n, read off the screen class's LAYOUT
        (`new ScreenField(name, ..., occurs, justify)`); a field without OCCURS is absent."""
        text = self._file("dto/screen", cls).read_text(encoding="utf-8")
        rows = re.findall(r'new ScreenField\("([A-Z0-9-]+)",.*, (\d+), (?:null|"[A-Z,]+")\)\)?[,;]?\s*$', text, re.M)
        return {name: int(n) for name, n in rows if int(n) > 1}

    def screen_justify(self, cls: str) -> dict[str, str]:
        """#5082: a named field's DFHMDF JUSTIFY ("RIGHT", "RIGHT,ZERO", "LEFT,ZERO" ...), read off the screen class's
        LAYOUT (cobol_to_java_screen_forge: `new ScreenField(name, ..., occurs, justify)`); a field without one is absent."""
        text = self._file("dto/screen", cls).read_text(encoding="utf-8")
        return dict(re.findall(r'new ScreenField\("([A-Z0-9-]+)",.*, "([A-Z,]+)"\)\)?[,;]?\s*$', text, re.M))


def item_for(leaf: Leaf) -> L.Item:
    usage = {"COMP": "BINARY", "COMP-4": "BINARY", "BINARY": "BINARY", "COMP-3": "PACKED", "PACKED-DECIMAL": "PACKED",
             "COMP-5": "COMP-5"}.get(leaf.usage, "DISPLAY")  # fmt: skip
    it = L.Item(5, leaf.cobol, "LINKAGE", pic=leaf.pic, usage=usage)
    L.layout(it)
    return it


# ---- the commands ------------------------------------------------------------------------------------------------
class Cics(ConditionCommands, ContainerCommands, FaultCommands, FileControlCommands, TaskControlCommands):
    """Translates EXEC CICS for one program; `gen` is the program's det.gen.Gen. A command family split out of this
    file (#5274: the containers / channels commands, det/cics_containers.py) is a base class: `command` dispatches."""

    def __init__(self, gen, generated: Generated, package: str):
        self.g = gen
        self.gp = generated
        self.package = package
        self.codecs: dict[str, list[str]] = {}  # DTO class -> its in / out methods
        self.stores: dict[str, str] = {}  # CICS file -> the Java Store expression
        self.repos: dict[str, str] = {}  # repository class -> field
        self.passes_bytes = (
            False  # #4695: a RETURN / XCTL passes its COMMAREA as bytes (commareaOut): a facade reads them
        )
        self.used_screens: set[str] = set()
        # #4414: the program issues HANDLE AID (its input commands consult the keys' labels) / PUSH HANDLE (its
        # handler state is stacked); set by program._translate from the source before any statement is translated
        self.handle_aid = False
        self.push_handle = False
        self.handle_abend = False  # #6271 (X70): the program has HANDLE ABEND, so a file command checks for its exit
        self.eibds_read = False  # #5126 (X64): the program reads EIBDS, so a file control command sets it
        # #5126 (X64): the program reads EIBRCODE, so a file control command's outcome puts a planned condition's bytes
        # there (`rcode_cmd`: the command being translated is one)
        self.eibrcode_read = False
        self.rcode_cmd = False
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

    def file_name(self, text: str) -> str:
        """#6072: a FILE / DATASET name, its trailing blanks dropped and its leading ones kept: IBM pads a file name
        with trailing blanks, so '    FILE' (a prefix never moved in) is not FILE, and no region defines it
        (CicsTask.undefinableFile: FILENOTFOUND, as the stub answers it)."""
        return f"{self.text(text)}.stripTrailing()"

    def int_(self, text: str) -> str:
        return self.g.int_expr(self.operand(text))

    def long_(self, text: str) -> str:
        """#4770 (X45): a doubleword operand's 64 bits (an unsigned one past 2**63 keeps its low 64 bits, as the counters hold it)."""
        e = self.operand(text)
        if isinstance(e, E.Lit) and isinstance(e.value, Decimal):
            return f"{int(e.value) if int(e.value) < 2**63 else int(e.value) - 2**64}L"
        return f"{self.g.num(e)}.longValue()"

    def field(self, text: str) -> str:
        return self.g.field_expr(self.ref(text))

    def read_field(self, text: str) -> str:
        """An operand the command only reads (FROM): a typed group's bytes need no unpack after it."""
        with self.g.reading():
            return self.field(text)

    def linkage_record(self, text: str) -> bool:
        """Whether the operand is a LINKAGE 01 record (a SET ADDRESS OF can window it onto a larger block)."""
        try:
            it = self.g.resolve(self.ref(text))
        except Untranslatable:  # an ambiguous name: the plain path says so
            return False
        return getattr(it, "section", None) == "LINKAGE" and getattr(it, "level", None) == 1

    def size(self, text: str) -> int:
        r = self.ref(text)
        it = self.g.resolve(r)
        return it.size * (1 if r.subscripts else it.occurs)

    def _return_call(self, method: str, tid: str, opts: dict, ind: str, g) -> tuple[list[str], str]:
        """RETURN [IMMEDIATE] TRANSID COMMAREA: (statements first, the runtime call). #4817: the COMMAREA's bytes go
        beside its DTO, so the next task gets every byte (spaces in a numeric DISPLAY field too), as IBM passes them."""
        pre: list[str] = []
        if "COMMAREA" in opts:
            dto, length = self.commarea_out(opts)
            if not dto.startswith("DetCics.commareaOut("):
                # #4817: pass the bytes beside the plain DTO (#4679/#4501 already carry a byte[])
                xarea = self.commarea_bytes(opts)
                ln = length if length != "null" else "(Integer) null"
                call = f"task.{method}({tid}, {dto}, {ln}, {xarea})"
            elif length != "null" and self.constant_int(str(opts["LENGTH"])) is None:
                xc = g.tmpname("xc")
                pre.append(f"{ind}Object {xc} = {dto};")
                xarea = f"({xc} instanceof byte[] ? null : {self.commarea_bytes(opts)})"
                call = f"task.{method}({tid}, {xc}, {length}, {xarea})"
            else:
                call = (
                    f"task.{method}({tid}, {dto}, {length})"
                    if length != "null"
                    else f"task.{method}({tid}, {dto}, null)"
                )
        else:
            call = f"task.{method}({tid}, null, null)"
        return pre, call

    # -- RESP
    def outcome(self, opts: dict, resp: str, resp2: str, ind: str) -> list[str]:
        """After a command: EIBRESP, (EIBRCODE,) then RESP / RESP2 when given; else a condition other than NORMAL goes to its
        HANDLE CONDITION label, or (NOHANDLE aside) takes CICS's default action, an abend."""
        out = [f"{ind}Cobol.store({self.g.eib('EIBRESP')}, BigDecimal.valueOf({resp}), false, CS);",
               f"{ind}Cobol.store({self.g.eib('EIBRESP2')}, BigDecimal.valueOf({resp2}), false, CS);"]  # fmt: skip
        if self.rcode_cmd:  # #5126 (X64): as the stub's GGCRCOD, before a condition's jump; unstated, the field is left
            out.append(f"{ind}if ({resp} != 0 && task.rcode() != null) {self.g.eib('EIBRCODE')}.putRaw(task.rcode());")
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
            cap = leaf.var[0].upper() + leaf.var[1:]
            if leaf.occurs > 1:
                lines_in.append(self.table_in(leaf, it, cap, at))
                lines_out.append(self.table_out(leaf, it, cap, at))
                continue
            f = self.g.factory(it, "s", f"base + {at}")
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

    def table_in(self, leaf: Leaf, it: L.Item, cap: str, at: int) -> str:
        """#5565: a List property into storage -- occurrence i at `at + i * size`; an absent or short list leaves the
        rest as an unset scalar does (spaces / zero)."""
        f = self.g.factory(it, "s", f"base + {at} + i * {leaf.size}")
        got = f"d.get{cap}() == null || d.get{cap}().size() <= i"
        if leaf.jtype == "String":
            move = f'Cobol.move({got} ? "" : d.get{cap}().get(i), {f}, CS);'
        else:
            move = f"Cobol.move({got} ? BigDecimal.ZERO : new BigDecimal(d.get{cap}().get(i).toString()), {f}, CS);"
        return f"        for (int i = 0; i < {leaf.occurs}; i++) {{ {move} }}"

    def table_out(self, leaf: Leaf, it: L.Item, cap: str, at: int) -> str:
        """#5565: every occurrence out of storage, as a List of exactly `occurs` items."""
        f = self.g.factory(it, "s", f"base + {at} + i * {leaf.size}")
        conv = {"Integer": ".intValue()", "Long": ".longValue()", "Short": ".shortValue()"}.get(leaf.jtype, "")
        item = f"Cobol.text({f}, CS)" if leaf.jtype == "String" else f"Cobol.num({f}, CS){conv}"
        jtype = "java.math.BigDecimal" if leaf.jtype == "BigDecimal" else leaf.jtype
        return (f"        {{ java.util.List<{jtype}> t = new java.util.ArrayList<>(); "
                f"for (int i = 0; i < {leaf.occurs}; i++) {{ t.add({item}); }} d.set{cap}(t); }}")  # fmt: skip

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

    def dto_for(self, area: E.Ref, size: int, program: str | None = None, link: bool = False) -> str:
        """The DTO a COMMAREA travels as: the target's (XCTL), the program's own contract when the area is its size,
        else the record's own DTO. A LINK's area no DTO types is never the caller's own contract of another size
        (#6839: ZECS001's 66-byte ZECS002-COMM-AREA to the HLASM ZECS002, which the forge gives no contract): it is
        refused here, and the LINK passes the bytes (#4679)."""
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
            if self.gp.contract and not link:
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
        d = self.gp.dto(cls)
        if length != "null":
            # #4501 / #4679: a LENGTH past the DTO passes that many bytes (DetCics.commareaOut), which the DTO cannot hold
            known = self.constant_int(opts["LENGTH"])
            if known is None or known > d.extent:
                dto = f"DetCics.commareaOut({dto}, {f}, {length}, {d.extent}, CS)"
                self.passes_bytes = True
        elif d.size > d.extent:
            # #4765: a DTO whose OCCURS fields appear once holds the first occurrence only: the record's bytes go, every
            # occurrence of the table (as a LINK's span, Dto.size); #4778: and a trailing FILLER's
            dto = f"DetCics.commareaOut({dto}, {f}, {d.size}, {d.extent}, CS)"
            self.passes_bytes = True
        return dto, length

    def in_dfhcommarea(self, text: str) -> bool:
        """#4816: whether a COMMAREA operand lies inside a LINKAGE 01 record. DFHCOMMAREA is the LINK caller's area; any
        other LINKAGE record can be the same storage under another name (#4957: a CALLed subprogram's USING record --
        SET ADDRESS OF forms never reach here, they are holes), so it is marked too and the runtime refuses it only
        when the program was LINKed with a COMMAREA (X39)."""
        try:
            it = self.g.resolve(self.ref(text))
        except LookupError:  # an operand commarea_out handled without an item of its own: no caller's record
            return False
        while it.parent is not None:
            it = it.parent
        return it.section == "LINKAGE"

    def commarea_bytes(self, opts: dict, program: str | None = None) -> str:
        """#4806: the COMMAREA's bytes as its DTO spans them (a byte[] expression): passed beside the DTO, they are
        the target's DFHCOMMAREA as they are -- a numeric field holding spaces too, which the DTO reads as a number."""
        r = self.ref(opts["COMMAREA"])
        cls = self.dto_for(r, self.size(opts["COMMAREA"]), program)
        with self.g.reading():
            f = self.g.field_expr(r)
        return f"Cobol.commarea({f}, {self.gp.dto(cls).size}).bytes"

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
                + f".withLengths(CicsTask.recordLengths({G_jstr(entity)}))"  # #6839: a variable-length file's
            )
            self.g.entities.add(entity)
        return f"store({self.file_name(arg)})"

    # -- the command
    def command(self, text: str, ind: str) -> list[str]:
        """One EXEC CICS command's Java; a file control command leads with `Cobol.move(<file>, EIBDS)` (#5126, X64),
        set before the command runs so a failed request leaves its file named, in a program that reads EIBDS."""
        if self.eibrcode_read:
            words, opts = parse_exec(text)
            self.rcode_cmd = bool(
                words[:1] and " ".join(words) in EIBDS_VERBS and (opts.get("FILE") or opts.get("DATASET"))
            )
        lines = self._command(text, ind)
        self.rcode_cmd = False
        if self.eibds_read or self.handle_abend:
            words, opts = parse_exec(text)
            file = opts.get("FILE") or opts.get("DATASET")
            if words[:1] and " ".join(words) in EIBDS_VERBS and file:
                if self.handle_abend and " ".join(words) != "UNLOCK":  # #6271 (X70): an injected file abend
                    lines = [*lines, *self.abend_exit(ind)]  # went to this program's exit, or unwound past this level
                if self.eibds_read:
                    return [f"{ind}Cobol.move({self.text(file)}, {self.g.eib('EIBDS')}, CS);", *lines]
        return lines

    def _command(self, text: str, ind: str) -> list[str]:
        words, opts = parse_exec(text)
        if not words and next(iter(opts), None) == "WAIT":
            # #5079: WAIT is a bare option (RETRIEVE ... WAIT) to the parser, so a command that starts with it (WAIT EVENT,
            # WAIT EXTERNAL, WAIT TERMINAL ...) read as no verb at all and crashed on the empty verb: WAIT is its verb
            words = ["WAIT"]
            del opts["WAIT"]
            if "EVENT" in opts and opts["EVENT"] is None:  # #5079 (X63): WAIT EVENT ECADDR(ptr) is a command of its own
                words = ["WAIT", "EVENT"]
                del opts["EVENT"]
        verb = " ".join(words)
        check_options(words, opts)  # #4411: an option the translation would ignore is refused first
        key = command_key(words, opts)
        if key in ("PUT CONTAINER", "GET CONTAINER", "DELETE CONTAINER"):
            return self.container(key, opts, ind)
        if key in ("PUT64 CONTAINER", "GET64 CONTAINER"):  # #5005 (X17): the same, INTO / FROM an ordinary item
            return self.container(key.replace("64", ""), opts, ind)
        if key in ("MOVE CONTAINER", "STARTBROWSE CONTAINER", "GETNEXT CONTAINER", "ENDBROWSE CONTAINER"):
            return self.container_browse(key, opts, ind)  # #4951
        if key in ("DELETE CHANNEL", "QUERY CHANNEL"):
            return self.channel_command(key, opts, ind)  # #5005
        if verb == "RUN":  # #4270 slice 2
            return self.run_transid(opts, ind)
        if words[:1] == ["FETCH"]:  # #4884, #4950: FETCH ANY / FETCH CHILD
            return self.fetch(key, opts, ind)
        if key == "FREE CHILD":  # #4950
            return self.free_child(opts, ind)
        if verb.split()[0] == "DELAY":  # #4950: the wait at which RUN children are dispatched
            return self.delay(opts, ind)
        if key == "POST":  # #5079 (X63): a timer-event control area
            return self.post(opts, ind)
        if key == "WAIT EVENT":
            return self.wait_event(opts, ind)
        if key == "CONVERSE":
            return self.converse(opts, ind)
        if verb in ("START", "RETRIEVE", "CANCEL"):  # #4270 slice 2: interval control
            return {"START": self.start, "RETRIEVE": self.retrieve, "CANCEL": self.cancel}[verb](opts, ind)
        if (
            verb == "ENQ"
        ):  # #5089 (X60): CicsTask.enq -- NORMAL, or the ENQBUSY a scenario plans for the RESOURCE as written
            res = re.sub(r"\s+", "", (opts.get("RESOURCE") or "").upper())
            r = self.g.tmpname("enq")
            # LENGTH / MAXLIFETIME (X60): LENGERR 1 outside 1-255, INVREQ 2 for a CVDA that is not UOW / TASK
            opt = {o: f"Integer.valueOf({self._number(_arg(opts[o]))})" if opts.get(o) else "null" for o in ("LENGTH", "MAXLIFETIME")}  # fmt: skip
            nos = "true" if "NOSUSPEND" in opts else "false"
            call = f"{ind}int[] {r} = task.enqChecked({G_jstr(res)}, {nos}, {opt['LENGTH']}, {opt['MAXLIFETIME']});"
            return [call, *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
        if verb.split()[0] in ("ENQ", "DEQ", "DELAY"):  # (DELAY FOR SECONDS(n): words DELAY FOR)
            return self.outcome(opts, "0", "0", ind)  # (OPTIONS: one task in the region, nothing waits)
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
                    f"{ind}if ({pl}[0] == 0) task.sendText({t}.substring(0, Math.min({t}.length(), {n})), {n}"
                    f"{''.join(', ' + G_jstr(x) for x in flags)});",
                    *self.outcome(opts, f"{pl}[0]", f"{pl}[1]", ind)]  # fmt: skip
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
                    cls = self.dto_for(area, self.size(_arg(opts["COMMAREA"])), prog_lit, link=True)
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
                        # what the linked program left in the COMMAREA is the caller's area now: #4806 its bytes when
                        # it took them (task.linkAreaBack: a det port), never its DTO over them -- a numeric field
                        # holding spaces it did not write would come back as digits; else (it took the object) the DTO
                        f"{ind}if (\"NORMAL\".equals({r})) {{",
                        f"{ind}    if (!task.linkAreaBack()) {{ in_{cls}({ca}, {w}, 0); }}",
                        f"{ind}    Cobol.commareaBack({w}, {f});",
                        f"{ind}}}"]  # fmt: skip
            out += self.abend_exit(ind)  # #4534: an abend below went to the exit, or unwound
            return out + self.outcome(opts, f"DetCics.resp({r})", "task.transferResp2()", ind)  # #4679
        if verb == "RETURN":
            if "CHANNEL" in opts:  # #5005 (X17): the next task's current channel (CicsTask.returnChannel)
                if not opts.get("TRANSID") or {"COMMAREA", "LENGTH", "IMMEDIATE"} & opts.keys():
                    raise CicsError(_msg("RETURN", "at_most_one", "CHANNEL"))
                tid, chan = self.name(_arg(opts["TRANSID"])), self.name(_arg(opts["CHANNEL"]))
                rr = g.tmpname("rr")
                # below the highest level it fails (INVREQ RESP2 2) and returns to the program; else the task ends
                return [f"{ind}int[] {rr} = task.returnChannel({tid}, {chan});",
                        f"{ind}if ({rr}[0] == 0) {{ caBack.run(); throw new Goback(); }}",
                        *self.outcome(opts, f"{rr}[0]", f"{rr}[1]", ind)]  # fmt: skip
            if "IMMEDIATE" in opts:  # #4270 (X27): IBM, EXEC CICS RETURN IMMEDIATE -- TRANSID's task attached at once
                if not opts.get("TRANSID"):
                    raise CicsError(
                        "RETURN IMMEDIATE without TRANSID: IBM does not say what it attaches (not modelled)"
                    )
                tid = self.name(_arg(opts["TRANSID"]))
                ret_pre, call = self._return_call("returnImmediate", tid, opts, ind, g)
                rr = g.tmpname("rr")
                # failing (INVREQ / LENGERR) it returns to the program, which tests RESP; else the task ends
                return [*ret_pre, f"{ind}int[] {rr} = {call};",
                        f"{ind}if ({rr}[0] == 0) {{ caBack.run(); throw new Goback(); }}",
                        *self.outcome(opts, f"{rr}[0]", f"{rr}[1]", ind)]  # fmt: skip
            if opts.get("TRANSID") and "RESP" in opts:  # #6271 (X71): a planned INVREQ / LENGERR returns to the program
                tid = self.name(_arg(opts["TRANSID"]))
                ret_pre, call = self._return_call("returnTransidResp", tid, opts, ind, g)
                rr = g.tmpname("rr")
                return [*ret_pre, f"{ind}int[] {rr} = {call};",
                        f"{ind}if ({rr}[0] == 0) {{ caBack.run(); throw new Goback(); }}",
                        *self.outcome(opts, f"{rr}[0]", f"{rr}[1]", ind)]  # fmt: skip
            if "TRANSID" in opts or "COMMAREA" in opts:
                tid = self.name(_arg(opts["TRANSID"])) if opts.get("TRANSID") else "null"
                ret_pre, call = self._return_call("returnTransid", tid, opts, ind, g)
                return [*ret_pre, f"{ind}caBack.run();", f"{ind}{call};",
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
            pre: list[str] = []
            if "CHANNEL" in opts:  # #4270: the target's current channel (CicsTask.xctlChannel)
                if "COMMAREA" in opts or "LENGTH" in opts:
                    raise CicsError(_msg("XCTL", "at_most_one", "CHANNEL"))
                call = f"task.xctlChannel({prog}, {self.name(_arg(opts['CHANNEL']))})"
            elif "COMMAREA" in opts:
                dto, length = self.commarea_out(opts, prog_lit)
                if self.in_dfhcommarea(
                    str(opts["COMMAREA"])
                ):  # #4816: a LINKed program's is its caller's storage (X39)
                    pre.append(f"{ind}task.xctlOfLinkage();")
                if not dto.startswith("DetCics.commareaOut("):
                    # #4806: the bytes too -- a det target's DFHCOMMAREA is them, not the DTO's reading of them
                    xarea = self.commarea_bytes(opts, prog_lit)
                    call = f"task.xctl({prog}, {dto}, {length if length != 'null' else '(Integer) null'}, {xarea})"
                elif length != "null" and self.constant_int(str(opts["LENGTH"])) is None:
                    # a LENGTH known at run time: the bytes past the DTO (#4501), else the DTO and its bytes (#4806)
                    xc = g.tmpname("xc")
                    pre.append(f"{ind}Object {xc} = {dto};")
                    xarea = f"({xc} instanceof byte[] ? null : {self.commarea_bytes(opts, prog_lit)})"
                    call = f"task.xctl({prog}, {xc}, {length}, {xarea})"
                else:  # always the bytes past the DTO (#4501 LENGTH, #4765 a table's every occurrence)
                    call = f"task.xctl({prog}, {dto}, {length})" if length != "null" else f"task.xctl({prog}, {dto})"
            else:
                # #5291: no COMMAREA: the target may RETURN a wide COMMAREA as bytes (#4695), which this program's
                # facade then reads through its own DTO (bytes no layout reads are answered as before)
                self.passes_bytes = True
                call = f"task.xctl({prog}, null)"
            r = g.tmpname("xr")
            return ([*pre, f"{ind}String {r} = {call};", f"{ind}if (\"NORMAL\".equals({r})) throw new Goback();",
                    *self.outcome(opts, f"DetCics.resp({r})", "task.transferResp2()", ind)])  # fmt: skip
        if verb in ("READ", "READNEXT", "READPREV"):
            return self.read(verb, opts, ind)
        if verb in ("WRITE", "REWRITE", "DELETE", "STARTBR", "ENDBR", "UNLOCK"):
            return self.file_update(verb, opts, ind)
        if verb == "HANDLE ABEND":
            return self.handle_abend_(opts, ind)
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
            return self.abend(opts, ind)
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
            # #4415 slice 3 (X46): a binary integer, stored by the area's declared usage
            body += [self.g.store_into(self.ref(_arg(opts[form])),
                                       f"BigDecimal.valueOf(CicsTask.formatNumber({t}, {G_jstr(form)}))", False)
                     for form in NUMBER_FORMS if form in opts]  # fmt: skip
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
            if ("ROUTECODES" in opts) != ("NUMROUTES" in opts):  # (the rule goes both ways)
                raise CicsError(_requires("WRITE OPERATOR", "ROUTECODES", "NUMROUTES"))
            if not any(o in opts for o in ("TEXTLENGTH", "ROUTECODES")):
                return [f"{ind}int {r} = task.writeOperator(Cobol.text({f}, CS));", *self.outcome(opts, r, "0", ind)]
            # #5859: TEXTLENGTH (a fullword value), ROUTECODES with NUMROUTES; EVENTUAL changes nothing observable
            n = f"Integer.valueOf({self.int_(_arg(opts['TEXTLENGTH']))})" if opts.get("TEXTLENGTH") else "null"
            rc = f"Cobol.text({self.read_field(_arg(opts['ROUTECODES']))}, CS)" if opts.get("ROUTECODES") else "null"
            nr = f"Integer.valueOf({self.int_(_arg(opts['NUMROUTES']))})" if opts.get("NUMROUTES") else "null"
            return [f"{ind}int[] {r} = task.writeOperator(Cobol.text({f}, CS), {n}, {rc}, {nr});",
                    *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]  # fmt: skip
        if key == "VERIFY PASSWORD":  # #5859 zECS ZECS002: the verdict a scenario states for the USERID (register X32)
            if not (opts.get("USERID") and opts.get("PASSWORD")):
                raise CicsError(_msg("VERIFY PASSWORD", "required", "USERID" if not opts.get("USERID") else "PASSWORD"))
            r = g.tmpname("ver")
            u = self.read_field(_arg(opts["USERID"]))
            return [f"{ind}int[] {r} = task.verifyPassword(Cobol.text({u}, CS));",
                    *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]  # fmt: skip
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
        if verb == "INQUIRE" and "PROGRAM" in opts:
            r = g.tmpname("resp")
            prog = self.name(_arg(opts["PROGRAM"]))
            out = [f"{ind}int {r} = task.inquireProgram({prog});"]
            if "STATUS" in opts:  # #4768 (X34): the definition's CVDA, written on NORMAL only
                out.append(
                    f"{ind}if ({r} == 0) "
                    + g.store_into(
                        self.ref(_arg(opts["STATUS"])), f"BigDecimal.valueOf(task.programStatus({prog}))", False
                    )
                )
            return out + self.outcome(opts, r, "0", ind)
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
        if verb in ("SYNCPOINT", "SYNCPOINT ROLLBACK"):
            # #4437: NORMAL -- the only outcome in this region (OPTIONS says why); EIBRESP / RESP / RESP2 written as
            # CICS writes them, never left as the previous command set them
            back = verb == "SYNCPOINT ROLLBACK" or "ROLLBACK" in opts
            pl = g.tmpname(
                "planned"
            )  # #6271 (X71): a planned INVREQ (RESP2 200) is not performed and raises as any condition
            call = f'{ind}int[] {pl} = task.planned({G_jstr("ROLLBACK" if back else "SYNCPOINT")}, "-");'
            call2 = f"{ind}if ({pl}[0] == 0) task.{'rollback' if back else 'syncpoint'}();"
            out = [call, call2, *self.outcome(opts, f"{pl}[0]", f"{pl}[1]", ind)]
            if "RESP2" in opts and "RESP" not in opts:  # RESP2 alone is written too
                out.append(
                    ind + self.g.store_into(self.ref(_arg(opts["RESP2"])), f"BigDecimal.valueOf({pl}[1])", False)
                )
            return out
        if verb == "SEND CONTROL":
            return self.send_control(opts, ind)
        if verb == "RECEIVE":
            return self.receive(opts, ind)
        if key in ("GETMAIN", "FREEMAIN"):  # #4771 (X47): task storage addressed by a pointer
            return self.storage(key, opts, ind)
        if key in ("LOAD", "RELEASE"):  # #6876 (X65): a program image addressed by a pointer
            return self.load_release(key, opts, ind)
        if key == "ADDRESS":  # #5079 (X59): a pointer to the EIB / the COMMAREA
            return self.address(opts, ind)
        if key in ("DOCUMENT CREATE", "DOCUMENT RETRIEVE"):  # #4769 (X33): the document handler
            return self.document(key, opts, ind)
        if key in ("WEB OPEN", "WEB CONVERSE", "WEB CLOSE"):  # #4767 (X35): CICS web support, HTTP client
            return self.web(key, opts, ind)
        if key == "WEB PARSE URL":  # #4767 (X36): a URL taken apart, pure
            return self.web_parse(key, opts, ind)
        if key == "WEB SEND":  # #4767 (X37): the response to the stated inbound request
            return self.web_send(key, opts, ind)
        if key in (
            "WEB EXTRACT",
            "EXTRACT WEB",
            "WEB RECEIVE",
            "WEB READ HTTPHEADER",
            "WEB WRITE HTTPHEADER",
            "WEB RETRIEVE",
        ) or key.startswith(
            ("WEB READ FORMFIELD", "WEB READ QUERYPARM", "WEB STARTBROWSE ", "WEB READNEXT ", "WEB ENDBROWSE ")
        ):  # #4767 / #4940 (X38), #4941 (X41)
            return self.web_request(key, opts, ind)
        if key == "EXTRACT TCPIP":  # #4972 (X38): the connection the run states
            return self.extract_tcpip(key, opts, ind)
        # #4270 spec PR 2: a command we do not model, refused whole -- with its name-only (or engine-only) entry's
        # reason when it is a CICS application command the spec lists
        if (
            key == "DUMP"
        ):  # #4415 slice 3 (X46): the old bare form; IBM's page is DUMP TRANSACTION and does not equate them
            raise CicsError(
                "EXEC CICS DUMP: the bare DUMP form is read as DUMP TRANSACTION, which is not modelled (X46)"
            )
        known = whole_refusal(key, verb, next(iter(opts), None))
        raise CicsError(known.whole_message(verb) if known is not None else f"EXEC CICS {verb} not modelled")

    def document(self, key: str, opts: dict, ind: str) -> list[str]:
        """DOCUMENT CREATE / DOCUMENT RETRIEVE (IBM CICS TS, EXEC CICS DOCUMENT CREATE, DOCUMENT RETRIEVE; register X33)
        on the task's documents (CicsTask). CREATE: an empty document, TEXT / BINARY(area) LENGTH(n) (the area's bytes,
        unchanged) or TEMPLATE(name) (the text the installed DOCTEMPLATE yields, as the run states it), its DOCTOKEN
        written on NORMAL only; LENGERR RESP2 1 (negative LENGTH), NOTFND RESP2 3 (no such template). RETRIEVE: the
        document INTO the area, at most MAXLENGTH bytes (rest of INTO left alone), LENGTH its length (the length it needs
        when truncated: LENGERR RESP2 2); NOTFND RESP2 1 (no such token); LENGERR RESP2 1 (MAXLENGTH below zero, no LENGTH).
        Every other option is refused by name by the spec entry (check_options); the rules that need the options together
        are the entry's groups."""
        g = self.g
        r = g.tmpname("doc")
        if not opts.get("DOCTOKEN"):
            raise CicsError(_msg(key, "required", "DOCTOKEN"))
        if key == "DOCUMENT CREATE":
            given = [o for o in ("TEXT", "BINARY", "TEMPLATE") if o in opts]
            if len(given) > 1:
                raise CicsError(_msg(key, "at_most_one", "TEXT"))
            for o in ("TEXT", "BINARY"):
                if o in opts and "LENGTH" not in opts:
                    raise CicsError(_msg(key, "requires", "TEXT"))
            if "LENGTH" in opts and not ("TEXT" in opts or "BINARY" in opts):
                raise CicsError(_msg(key, "requires", "LENGTH"))
            if "TEXT" in opts or "BINARY" in opts:
                area = _arg(opts["TEXT"] if "TEXT" in opts else opts["BINARY"])
                n = self.int_(_arg(opts["LENGTH"]))
                call = f"task.documentCreateData(DetCics.documentBytes({self.read_field(area)}, {n}), {n})"
            elif "TEMPLATE" in opts:
                call = f"task.documentCreateTemplate({self.name(_arg(opts['TEMPLATE']))}, CS)"
            else:
                call = "task.documentCreateEmpty()"
            return [f"{ind}CicsTask.DocumentCreated {r} = {call};",
                    f"{ind}if ({r}.resp() == 0) DetCics.putText({self.field(_arg(opts['DOCTOKEN']))}, {r}.doctoken(), CS);",
                    *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)]  # fmt: skip
        for o in ("INTO", "MAXLENGTH", "DATAONLY"):
            if o not in opts:
                raise CicsError(_msg(key, "required", o))
        token = self.read_field(_arg(opts["DOCTOKEN"]))
        maxlength = self.int_(_arg(opts["MAXLENGTH"]))
        out = [f"{ind}CicsTask.DocumentData {r} = task.documentRetrieve(Cobol.text({token}, CS), {maxlength});",
               f"{ind}if ({r}.data() != null) DetCics.putDocument({self.field(_arg(opts['INTO']))}, {r}.data());"]  # fmt: skip
        if "LENGTH" in opts:  # (written after MAXLENGTH was read: ZECS gives both the same area)
            out.append(
                f"{ind}if ({r}.length() >= 0) "
                + g.store_into(self.ref(_arg(opts["LENGTH"])), f"BigDecimal.valueOf({r}.length())", False)
            )
        return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)

    def web(self, key: str, opts: dict, ind: str) -> list[str]:
        """WEB OPEN / WEB CONVERSE / WEB CLOSE (IBM CICS TS, EXEC CICS WEB OPEN, WEB CONVERSE, WEB CLOSE; register X35) on
        the HTTP peers the run states (CicsTask.withHttpPeers). OPEN: HOST(area) HOSTLENGTH [PORTNUMBER] SCHEME, or
        URIMAP(name); the SESSTOKEN written on NORMAL only. CONVERSE: the request from METHOD, PATH / PATHLENGTH,
        QUERYSTRING / QUERYSTRLEN, FROM / FROMLENGTH and MEDIATYPE (each area's text and its length, checked by the
        task); on NORMAL or LENGERR 57 the response goes INTO (at most MAXLENGTH, INTO's length when omitted; MAXLENGTH
        read before TOLENGTH is written: zECS names one area for both), TOLENGTH, STATUSCODE, STATUSTEXT (the reason
        phrase's bytes) and MEDIATYPE (blank-padded to 56). CLOSE: NOTOPEN 27 for a token that is no open session's.
        Every other option is refused by name by the spec entry (check_options)."""
        g = self.g
        r = g.tmpname("web")
        if not opts.get("SESSTOKEN"):
            raise CicsError(_msg(key, "required", "SESSTOKEN"))
        if key == "WEB CLOSE":
            tok = f"Cobol.text({self.read_field(_arg(opts['SESSTOKEN']))}, CS)"
            return [f"{ind}int[] {r} = task.webClose({tok});", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
        if key == "WEB OPEN":
            if ("URIMAP" in opts) == ("HOST" in opts):
                raise CicsError(_msg(key, "one_of", "URIMAP"))
            if ("HOST" in opts) != ("HOSTLENGTH" in opts):
                raise CicsError(_requires(key, "HOST", "HOSTLENGTH"))
            if "HOST" in opts and "SCHEME" not in opts:
                raise CicsError(_requires(key, "HOST", "SCHEME"))
            for o in ("PORTNUMBER", "SCHEME"):
                if o in opts and "HOST" not in opts:
                    raise CicsError(_requires(key, "PORTNUMBER", "HOST").format(o))
            if "URIMAP" in opts:
                call = f"task.webOpenUrimap({self.name(_arg(opts['URIMAP']))})"
            else:
                host = f"Cobol.text({self.read_field(_arg(opts['HOST']))}, CS)"
                port = self.int_(_arg(opts["PORTNUMBER"])) if "PORTNUMBER" in opts else "0"
                call = (f"task.webOpenHost({host}, {self.int_(_arg(opts['HOSTLENGTH']))}, {port}, "
                        f"{'true' if 'PORTNUMBER' in opts else 'false'}, {self.int_(_arg(opts['SCHEME']))})")  # fmt: skip
            return [f"{ind}CicsTask.WebOpened {r} = {call};",
                    f"{ind}if ({r}.resp() == 0) DetCics.putText({self.field(_arg(opts['SESSTOKEN']))}, {r}.sesstoken(), CS);",
                    *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)]  # fmt: skip
        for o in ("METHOD", "INTO"):
            if not opts.get(o):
                raise CicsError(_msg(key, "required", o))
        for a, n in (("PATH", "PATHLENGTH"), ("QUERYSTRING", "QUERYSTRLEN"), ("FROM", "FROMLENGTH"),
                     ("STATUSTEXT", "STATUSLEN")):  # fmt: skip
            if (a in opts) != (n in opts):
                raise CicsError(_requires(key, a, n))
        if sum(o in opts for o in ("CLIENTCONV", "CLICONVERT", "NOINCONVERT", "NOOUTCONVERT", "NOCLICONVERT")) > 1:
            raise CicsError(_msg(key, "at_most_one", "CLIENTCONV"))
        if "CLIENTCONV" in opts:  # (its value changes nothing within the model, but it is read as IBM reads it)
            _arg(opts["CLIENTCONV"])

        def text(o: str) -> str:
            return f"Cobol.text({self.read_field(_arg(opts[o]))}, CS)" if o in opts else "null"

        def num(o: str, absent: str) -> str:
            return self.int_(_arg(opts[o])) if o in opts else absent

        into = _arg(opts["INTO"])
        call = (f"task.webConverse({text('SESSTOKEN')}, {num('METHOD', '0')}, {text('PATH')}, {num('PATHLENGTH', '0')}, "
                f"{text('QUERYSTRING')}, {num('QUERYSTRLEN', '0')}, {text('FROM')}, {num('FROMLENGTH', '0')}, "
                f"{text('MEDIATYPE')}, {num('MAXLENGTH', str(self.size(into)))}, {num('STATUSLEN', '-1')}, CS)")  # fmt: skip

        def received(area: str, data: str, what: str) -> str:
            """What a WEB CONVERSE received, at the area's start (the rest left alone); more bytes than the area holds
            refused (PastFrom): CICS writes the storage that follows it, which GnuCOBOL lays out unlike IBM's (X6)."""
            f = self.field(area)
            return (f'{ind}    if ({data}.length > {f}.length()) throw new DetCics.PastFrom("{what} beyond its area: '
                    f'not modelled"); DetCics.put({f}, {data});')  # fmt: skip

        out = [f"{ind}CicsTask.WebResponse {r} = {call};", f"{ind}if ({r}.body() != null) {{",
               received(into, f"{r}.body()", "WEB CONVERSE INTO")]  # fmt: skip
        if "TOLENGTH" in opts:
            out.append(
                f"{ind}    "
                + g.store_into(self.ref(_arg(opts["TOLENGTH"])), f"BigDecimal.valueOf({r}.toLength())", False)
            )
        if "STATUSCODE" in opts:
            out.append(
                f"{ind}    "
                + g.store_into(self.ref(_arg(opts["STATUSCODE"])), f"BigDecimal.valueOf({r}.status())", False)
            )
        if "STATUSTEXT" in opts:
            out.append(received(_arg(opts["STATUSTEXT"]), f"{r}.statusText().getBytes(CS)", "WEB CONVERSE STATUSTEXT"))
        if opts.get("MEDIATYPE"):
            out.append(f"{ind}    DetCics.putText({self.field(_arg(opts['MEDIATYPE']))}, {r}.mediaType(), CS);")
        out.append(f"{ind}}}")
        return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)

    def web_send(self, key: str, opts: dict, ind: str) -> list[str]:
        """WEB SEND (IBM CICS TS, EXEC CICS WEB SEND, server; register X37): CicsTask.webSend takes FROM's text and
        FROMLENGTH, MEDIATYPE's text, ACTION's value (0 when absent), STATUSCODE (-1), STATUSTEXT's text with STATUSLEN
        (-1: the whole area, ASSUMED) and the conversion flag; the response is recorded as WEB-SEND. Every option the
        spec entry does not model is refused by name (check_options)."""
        if sum(o in opts for o in ("FROM", "DOCTOKEN", "CONTAINER")) != 1:
            raise CicsError(_msg(key, "one_of", "FROM"))
        if "CHANNEL" in opts and "CONTAINER" not in opts:
            raise CicsError(_requires(key, "CHANNEL", "CONTAINER"))
        if "FROM" in opts and "FROMLENGTH" not in opts:
            raise CicsError(_requires(key, "FROM", "FROMLENGTH"))
        if "FROMLENGTH" in opts and "FROM" not in opts:
            raise CicsError(_requires(key, "FROMLENGTH", "FROM"))
        if "SRVCONVERT" in opts and "NOSRVCONVERT" in opts:
            raise CicsError(_msg(key, "at_most_one", "SRVCONVERT"))
        if "STATUSLEN" in opts and "STATUSTEXT" not in opts:
            raise CicsError(_requires(key, "STATUSLEN", "STATUSTEXT"))
        if "DOCSTATUS" in opts and "DOCTOKEN" not in opts:
            raise CicsError(_requires(key, "DOCSTATUS", "DOCTOKEN"))

        def text(o: str) -> str:
            return f"Cobol.text({self.read_field(_arg(opts[o]))}, CS)" if o in opts else "null"

        def num(o: str, absent: str) -> str:
            return self.int_(_arg(opts[o])) if o in opts else absent

        conv = 1 if "SRVCONVERT" in opts else 2 if "NOSRVCONVERT" in opts else 0
        r = self.g.tmpname("web")
        if "CONTAINER" in opts:  # #5037 (X37): the response is a container's data
            chan = self.name(_arg(opts["CHANNEL"])) if "CHANNEL" in opts else "null"
            call = (f"task.webSendContainer({chan}, {self.name(_arg(opts['CONTAINER']))}, {text('MEDIATYPE')}, "
                    f"{num('ACTION', '0')}, {num('STATUSCODE', '-1')}, {text('STATUSTEXT')}, {num('STATUSLEN', '-1')}, "
                    f"{conv}, CS)")  # fmt: skip
            return [f"{ind}int[] {r} = {call};", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
        if "DOCTOKEN" in opts:  # #4767 (X37): the response is a document the task created (DOCUMENT CREATE)
            call = (f"task.webSendDocument({text('DOCTOKEN')}, {text('MEDIATYPE')}, {num('ACTION', '0')}, "
                    f"{num('STATUSCODE', '-1')}, {text('STATUSTEXT')}, {num('STATUSLEN', '-1')}, {conv}, "
                    f"{num('DOCSTATUS', '0')}, CS)")  # fmt: skip
            return [f"{ind}int[] {r} = {call};", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
        frm = text("FROM")
        if "FROM" in opts and self.linkage_record(_arg(opts["FROM"])):  # #6839: an area set onto a larger block
            frm = f"DetCics.fromText({self.read_field(_arg(opts['FROM']))}, {num('FROMLENGTH', '0')}, CS)"
        call = (f"task.webSend({frm}, {num('FROMLENGTH', '0')}, {text('MEDIATYPE')}, {num('ACTION', '0')}, "
                f"{num('STATUSCODE', '-1')}, {text('STATUSTEXT')}, {num('STATUSLEN', '-1')}, {conv})")  # fmt: skip
        return [f"{ind}int[] {r} = {call};", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]

    def web_parse(self, key: str, opts: dict, ind: str) -> list[str]:
        """WEB PARSE URL (IBM CICS TS, EXEC CICS WEB PARSE URL; register X36): CicsTask.webParse takes the URL area's text
        and URLLENGTH apart; HOSTLENGTH / PATHLENGTH / QUERYSTRLEN are read before the pieces are written and set to
        each piece's length, SCHEMENAME is blank-padded to its area, PORTNUMBER is explicit or 80 / 443. On NORMAL only
        (an error leaves every area alone: ASSUMED). The pieces' areas are checked against the lengths by the task."""
        g = self.g
        for o in ("URL", "URLLENGTH"):
            if not opts.get(o):
                raise CicsError(_msg(key, "required", o))
        for a, n in (("HOST", "HOSTLENGTH"), ("PATH", "PATHLENGTH"), ("QUERYSTRING", "QUERYSTRLEN")):
            if (a in opts) != (n in opts):
                raise CicsError(_requires(key, a, n))
        r = g.tmpname("web")

        def length(n: str) -> str:
            return f"Integer.valueOf({self.int_(_arg(opts[n]))})" if n in opts else "null"

        def cap(a: str) -> str:
            return str(self.size(_arg(opts[a]))) if a in opts else "0"

        call = (f"task.webParse(Cobol.text({self.read_field(_arg(opts['URL']))}, CS), {self.int_(_arg(opts['URLLENGTH']))}, "
                f"{cap('SCHEMENAME')}, {length('HOSTLENGTH')}, {cap('HOST')}, {length('PATHLENGTH')}, {cap('PATH')}, "
                f"{length('QUERYSTRLEN')}, {cap('QUERYSTRING')})")  # fmt: skip
        out = [f"{ind}CicsTask.WebParsed {r} = {call};", f"{ind}if ({r}.resp() == 0) {{"]
        if "SCHEMENAME" in opts:
            out.append(f"{ind}    DetCics.putText({self.field(_arg(opts['SCHEMENAME']))}, {r}.scheme(), CS);")
        for area, ln, piece in (("HOST", "HOSTLENGTH", "host"), ("PATH", "PATHLENGTH", "path"),
                                ("QUERYSTRING", "QUERYSTRLEN", "query")):  # fmt: skip
            if area in opts:
                out.append(f"{ind}    DetCics.putText({self.field(_arg(opts[area]))}, {r}.{piece}(), CS);")
                out.append(
                    f"{ind}    "
                    + g.store_into(self.ref(_arg(opts[ln])), f"BigDecimal.valueOf({r}.{piece}().length())", False)
                )
        if "PORTNUMBER" in opts:
            out.append(
                f"{ind}    "
                + g.store_into(self.ref(_arg(opts["PORTNUMBER"])), f"BigDecimal.valueOf({r}.port())", False)
            )
        out.append(f"{ind}}}")
        return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)

    def web_request(self, key: str, opts: dict, ind: str) -> list[str]:
        """The server reading the request it serves (IBM CICS TS, EXEC CICS WEB EXTRACT, WEB RECEIVE, WEB READ HTTPHEADER,
        WEB WRITE HTTPHEADER; register X38) on the request the run states (CicsTask.withHttpRequest). EXTRACT: each piece
        asked for, its length option read before it is written (the area's size is the cap); on NORMAL the pieces' bytes,
        their lengths, the port, SCHEME's CVDA and REQUESTTYPE's HTTPYES. RECEIVE INTO: the body (at most MAXLENGTH) at
        INTO's start, LENGTH, MEDIATYPE blank-padded to 56. READ HTTPHEADER: the value at VALUE's start, VALUELENGTH.
        WRITE HTTPHEADER: the header recorded as WEB-HEADER. Every other option is refused by name (check_options)."""
        g = self.g
        r = g.tmpname("web")

        def req(o: str) -> str:
            if not opts.get(o):
                raise CicsError(_msg(key, "required", o))
            return _arg(opts[o])

        def text(o: str) -> str:
            return f"Cobol.text({self.read_field(req(o))}, CS)"

        def store(o: str, value: str) -> str:
            return f"{ind}    " + g.store_into(self.ref(_arg(opts[o])), f"BigDecimal.valueOf({value})", False)

        def put(area: str, data: str, what: str) -> str:
            """A piece at the area's start (the rest left alone); more bytes than the area holds refused (PastFrom)."""
            f = self.field(area)
            return (f'{ind}    if ({data}.length > {f}.length()) throw new DetCics.PastFrom("{what} beyond its area: '
                    f'not modelled"); DetCics.put({f}, {data});')  # fmt: skip

        if (
            key == "WEB RETRIEVE"
        ):  # #4941 (X41): the DOCTOKEN of the last EVENTUAL document send, written on NORMAL only
            area = self.field(req("DOCTOKEN"))
            return [f"{ind}CicsTask.DocumentCreated {r} = task.webRetrieve();",
                    f"{ind}if ({r}.resp() == 0) DetCics.putText({area}, {r}.doctoken(), CS);",
                    *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)]  # fmt: skip
        if key.startswith(
            ("WEB READ FORMFIELD", "WEB READ QUERYPARM", "WEB STARTBROWSE ", "WEB READNEXT ", "WEB ENDBROWSE ")
        ):
            return self.web_forms(key, opts, ind, text, req, store, put)
        if key == "WEB WRITE HTTPHEADER":
            call = f"task.webWriteHeader({text('HTTPHEADER')}, {self.int_(req('NAMELENGTH'))}, {text('VALUE')}, {self.int_(req('VALUELENGTH'))})"
            return [f"{ind}int[] {r} = {call};", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
        if key == "WEB READ HTTPHEADER":
            vl = req("VALUELENGTH")
            call = (f"task.webReadHeader({text('HTTPHEADER')}, {self.int_(req('NAMELENGTH'))}, {self.int_(vl)}, "
                    f"{self.size(req('VALUE'))})")  # fmt: skip
            return [f"{ind}CicsTask.WebHeader {r} = {call};", f"{ind}if ({r}.resp() == 0) {{",
                    put(req("VALUE"), f"{r}.value().getBytes(CS)", "WEB READ HTTPHEADER VALUE"),
                    store("VALUELENGTH", f"{r}.value().length()"), f"{ind}}}",
                    *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)]  # fmt: skip
        if key == "WEB RECEIVE":
            if ("INTO" in opts) == ("SET" in opts) or not (opts.get("INTO") or opts.get("SET")):
                raise CicsError(_msg(key, "one_of", "INTO"))
            if "INTO" in opts and not opts.get("MAXLENGTH"):
                raise CicsError(_requires(key, "INTO", "MAXLENGTH"))
            if "SET" in opts and not opts.get("LENGTH"):
                raise CicsError(_requires(key, "SET", "LENGTH"))
            if "SRVCONVERT" in opts and "NOSRVCONVERT" in opts:
                raise CicsError(_msg(key, "at_most_one", "SRVCONVERT"))
            conv = 1 if "SRVCONVERT" in opts else 2 if "NOSRVCONVERT" in opts else 0
            if "SET" in opts:  # #4771 (X47): the body in a new block of task storage the pointer addresses
                ptr = self.pointer(opts["SET"])
                most = self.int_(req("MAXLENGTH")) if opts.get("MAXLENGTH") else "Integer.MAX_VALUE"
                out = [f"{ind}CicsTask.WebReceived {r} = task.webReceive({most}, Integer.MAX_VALUE, {conv});",
                       f"{ind}if ({r}.body() != null) {{",
                       f"{ind}    DetCics.receivedBlock(task, {ptr}, {r}.body(), CS);"]  # fmt: skip
            else:
                into = req("INTO")
                call = f"task.webReceive({self.int_(req('MAXLENGTH'))}, {self.size(into)}, {conv})"
                out = [f"{ind}CicsTask.WebReceived {r} = {call};", f"{ind}if ({r}.body() != null) {{",
                       put(into, f"{r}.body().getBytes(CS)", "WEB RECEIVE INTO")]  # fmt: skip
            if "LENGTH" in opts:
                out.append(store("LENGTH", f"{r}.body().length()"))
            if "MEDIATYPE" in opts:
                out.append(f"{ind}    DetCics.putText({self.field(req('MEDIATYPE'))}, "
                           f'String.format("%-56s", {r}.mediaType()), CS);')  # fmt: skip
            out.append(f"{ind}}}")
            return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)
        pieces = (("HOST", "HOSTLENGTH", "host"), ("HTTPMETHOD", "METHODLENGTH", "method"),
                  ("HTTPVERSION", "VERSIONLEN", "version"), ("PATH", "PATHLENGTH", "path"),
                  ("QUERYSTRING", "QUERYSTRLEN", "query"))  # fmt: skip
        for a, n, _ in pieces:
            if (a in opts) != (n in opts):
                raise CicsError(_requires(key, a, n))

        def length(n: str) -> str:
            return f"Integer.valueOf({self.int_(_arg(opts[n]))})" if n in opts else "null"

        def cap(a: str) -> str:
            return str(self.size(_arg(opts[a]))) if a in opts else "0"

        call = "task.webExtract(" + ", ".join(f"{length(n)}, {cap(a)}" for a, n, _ in pieces) + ")"
        out = [f"{ind}CicsTask.WebExtracted {r} = {call};", f"{ind}if ({r}.resp() == 0) {{"]
        for a, n, piece in pieces:
            if a in opts:
                out.append(put(_arg(opts[a]), f"{r}.{piece}().getBytes(CS)", f"WEB EXTRACT {a}"))
                out.append(store(n, f"{r}.{piece}().length()"))
        if "PORTNUMBER" in opts:
            out.append(store("PORTNUMBER", f"{r}.port()"))
        if "SCHEME" in opts:
            out.append(store("SCHEME", f"{r}.scheme()"))
        if "REQUESTTYPE" in opts:
            out.append(store("REQUESTTYPE", "1033"))
        out.append(f"{ind}}}")
        return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)

    def extract_tcpip(self, key: str, opts: dict, ind: str) -> list[str]:
        """#4972 (register X38): EXTRACT TCPIP (IBM CICS TS, EXEC CICS EXTRACT TCPIP) over the connection the run states
        (CicsTask.withTcpip). CicsTask.extractTcpip takes each address / name area's length option (an area asked for whose
        length option is missing: 0, LENGERR RESP2 1) and its size; on NORMAL the bytes at each area's start (the rest left
        alone), the lengths, the address numbers, the IPv4 CVDA (300), the port and the SSL type's CVDA."""
        g = self.g
        r = g.tmpname("tcp")
        pieces = (("CLIENTADDR", "CADDRLENGTH", "clientAddr"), ("CLIENTNAME", "CNAMELENGTH", "clientName"),
                  ("SERVERADDR", "SADDRLENGTH", "serverAddr"), ("SERVERNAME", "SNAMELENGTH", "serverName"))  # fmt: skip
        for a, n, _ in pieces:
            if n in opts and a not in opts:
                raise CicsError(_requires(key, n, a))

        def length(a: str, n: str) -> str:
            if a not in opts:
                return "null"
            return f"Integer.valueOf({self.int_(_arg(opts[n]))})" if n in opts else "Integer.valueOf(0)"

        def cap(a: str) -> str:
            return str(self.size(_arg(opts[a]))) if a in opts else "0"

        def store(o: str, value: str) -> str:
            return f"{ind}    " + g.store_into(self.ref(_arg(opts[o])), f"BigDecimal.valueOf({value})", False)

        args = ", ".join(f"{length(a, n)}, {cap(a)}" for a, n, _ in pieces)
        flags = ", ".join(
            str(o in opts).lower() for o in ("CLIENTADDRNU", "SERVERADDRNU", "CLNTIPFAMILY", "SRVRIPFAMILY")
        )
        out = [
            f"{ind}CicsTask.TcpipExtracted {r} = task.extractTcpip({args}, {flags});",
            f"{ind}if ({r}.resp() == 0) {{",
        ]
        for a, n, piece in pieces:
            if a in opts:
                f = self.field(_arg(opts[a]))
                data = f"{r}.{piece}().getBytes(CS)"
                out.append(f'{ind}    if ({data}.length > {f}.length()) throw new DetCics.PastFrom("EXTRACT TCPIP {a} beyond '
                           f'its area: not modelled"); DetCics.put({f}, {data});')  # fmt: skip
                if n in opts:
                    out.append(store(n, f"{r}.{piece}().length()"))
        for o, value in (("CLIENTADDRNU", f"{r}.clientNu()"), ("SERVERADDRNU", f"{r}.serverNu()"), ("CLNTIPFAMILY", "300"),
                         ("SRVRIPFAMILY", "300"), ("PORTNUMNU", f"{r}.port()"), ("SSLTYPE", f"{r}.ssl()")):  # fmt: skip
            if o in opts:
                out.append(store(o, value))
        out.append(f"{ind}}}")
        return out + self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)

    def web_forms(self, key: str, opts: dict, ind: str, text, req, store, put) -> list[str]:
        """#4940 (register X38): WEB READ FORMFIELD / QUERYPARM and the WEB browse forms (IBM CICS TS, EXEC CICS WEB READ
        FORMFIELD, WEB READ QUERYPARM, WEB STARTBROWSE / READNEXT / ENDBROWSE HTTPHEADER, FORMFIELD, QUERYPARM) on the stated
        request (CicsTask.webReadParam / webStartBrowse / webReadNext / webEndBrowse). A read: the value at VALUE's start
        (cut to VALUELENGTH, LENGERR RESP2 5) and VALUELENGTH its whole length. READNEXT: the pair's name and value at the
        areas' starts and their whole lengths (also when cut, LENGERR RESP2 4 / 5)."""
        g = self.g
        r = g.tmpname("web")
        form, kind = key.split()[1], key.split()[2]
        ok = f"{ind}if ({r}.value() != null) {{"
        if form == "READ":
            call = (f'task.webReadParam("{kind}", {text(kind)}, {self.int_(req("NAMELENGTH"))}, '
                    f"{self.int_(req('VALUELENGTH'))}, {self.size(req('VALUE'))})")  # fmt: skip
            return [f"{ind}CicsTask.WebParam {r} = {call};", ok,
                    put(req("VALUE"), f"{r}.value().getBytes(CS)", f"{key} VALUE"),
                    store("VALUELENGTH", f"{r}.length()"), f"{ind}}}",
                    *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)]  # fmt: skip
        if form == "READNEXT":
            for o in (kind, "NAMELENGTH", "VALUE", "VALUELENGTH"):
                req(o)
            call = (f'task.webReadNext("{kind}", {self.int_(req("NAMELENGTH"))}, {self.size(req(kind))}, '
                    f"{self.int_(req('VALUELENGTH'))}, {self.size(req('VALUE'))})")  # fmt: skip
            return [f"{ind}CicsTask.WebNext {r} = {call};", f"{ind}if ({r}.name() != null) {{",
                    put(req(kind), f"{r}.name().getBytes(CS)", f"{key} {kind}"), store("NAMELENGTH", f"{r}.nameLength()"),
                    put(req("VALUE"), f"{r}.value().getBytes(CS)", f"{key} VALUE"),
                    store("VALUELENGTH", f"{r}.valueLength()"), f"{ind}}}",
                    *self.outcome(opts, f"{r}.resp()", f"{r}.resp2()", ind)]  # fmt: skip
        if form == "ENDBROWSE":
            return [f'{ind}int[] {r} = task.webEndBrowse("{kind}");', *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]
        named = bool(opts.get(kind))  # STARTBROWSE
        if kind == "HTTPHEADER" and named:
            raise CicsError("WEB STARTBROWSE HTTPHEADER: a name to start at is not documented: not modelled")
        if named and not opts.get("NAMELENGTH"):
            raise CicsError(f"WEB STARTBROWSE {kind}(name) without NAMELENGTH (IBM: it is required with a name)")
        if "NAMELENGTH" in opts and not named:
            raise CicsError(f"WEB STARTBROWSE {kind} NAMELENGTH without a name")
        if named:
            call = f'task.webStartBrowse("{kind}", {text(kind)}, Integer.valueOf({self.int_(req("NAMELENGTH"))}))'
        else:
            call = f'task.webStartBrowse("{kind}", null, null)'
        return [f"{ind}int[] {r} = {call};", *self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)]

    def pointer(self, text: str | None) -> str:
        """#4771 (X47): the Field of the plain USAGE POINTER item an option names (SET / DATAPOINTER)."""

        try:
            return self.g.pointer_item(_arg(text).strip())
        except Untranslatable as e:
            raise CicsError(str(e)) from None

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
            if not most:
                raise CicsError("RECEIVE SET without MAXLENGTH: the most it takes is not documented")
            if not settable:
                raise CicsError("RECEIVE SET without LENGTH(data-area)")
            limit = self.int_(most)
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
        (RESP2 1) leave the areas alone. START / END name no output area. #4768 (X34): with no browse option, the direct
        form reads the definition URIMAP names (NOTFND RESP2 3 when it is not installed), PATH / TRANSACTION as NEXT's."""
        g = self.g
        form = [f for f in ("START", "NEXT", "END") if f in opts]
        if len(form) > 1:
            raise CicsError(_msg("INQUIRE URIMAP", "at_most_one", "START"))
        r = g.tmpname("urimap")
        if not form:  # #4768 (X34): the direct form, URIMAP(name): that definition, NOTFND RESP2 3 when not installed
            if "URIMAP" not in opts:
                raise CicsError(_msg("INQUIRE URIMAP", "required", "URIMAP"))
            name = self.name(_arg(opts["URIMAP"]))
            outs = [k for k in ("PATH", "TRANSACTION") if k in opts]
            out = [f"{ind}int[] {r} = task.inquireUrimap({name});"]
        else:
            call = {"START": "inquireUrimapStart", "NEXT": "inquireUrimapNext", "END": "inquireUrimapEnd"}[form[0]]
            outs = [k for k in ("URIMAP", "PATH", "TRANSACTION") if k in opts]
            if form[0] != "NEXT" and outs:
                raise CicsError(f"INQUIRE URIMAP {form[0]} {outs[0]}: a browse {form[0]} returns no definition")
            out = [f"{ind}int[] {r} = task.{call}();"]
        if outs:
            out.append(f"{ind}if ({r}[0] == 0) {{")
            for k, acc in (("URIMAP", "urimapName"), ("PATH", "urimapPath"), ("TRANSACTION", "urimapTransaction")):
                if k in outs:
                    out.append(f"{ind}    DetCics.putText({self.field(_arg(opts[k]))}, task.{acc}(), CS);")
            out.append(f"{ind}}}")
        return out + self.outcome(opts, f"{r}[0]", f"{r}[1]", ind)

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
            out.append(f"{ind}{v}.put({G_jstr(key)}, Cobol.text({o}, CS));")
            parts = [self.symbolic(m, s, name, None, k) for s in ("L", "A", "C", "H")]
            if parts[1] is None:
                parts[1] = self.symbolic(m, "F", name, None, k)
            out.append(f"{ind}DetCics.subfields({sub}, {G_jstr(key)}, "
                       f"{', '.join(p or 'null' for p in parts)}, CS);")  # fmt: skip
        if opts.get("CURSOR"):
            out.append(f"{ind}{sub}.cursorAt({self.int_(opts['CURSOR'])});")
        flags = [o for o in MAP_OPTIONS if o in opts]
        screen = "null" if "MAPONLY" in opts else f"{cls}.fromValues({v})"
        out.append(f"{ind}{cls} {scr} = {screen};")
        pl = self.g.tmpname("planned")  # #6271 (X71): a planned INVMPSZ / TSIOERR / INVREQ sends nothing
        out.append(f'{ind}int[] {pl} = task.planned("SEND-MAP", {G_jstr(m)});')
        out.append(f"{ind}if ({pl}[0] == 0) task.sendMap({G_jstr(m)}, {G_jstr(ms)}, {scr}, {sub}"
                   f"{''.join(', ' + G_jstr(x) for x in flags)});")  # fmt: skip
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
        out = [*guard, f"{ind}int[] {pl} = task.planned(\"RECEIVE-MAP\", {G_jstr(m)});",
               (f"{ind}java.util.Optional<{cls}> {r} = {pl}[0] != 0 ? java.util.Optional.empty() "
                f": task.receive({G_jstr(m)}, {G_jstr(ms)}, {cls}.class);"),
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
            out.append(f"{ind}    if ({vals}.get({G_jstr(key)}) != null) {{")
            # #5082: IBM DFHMDF JUSTIFY -- the input right-justified / zero-filled as the field says; none: as typed
            tail = f", {G_jstr(justify[name])}" if name in justify else ""
            call = f"{self.package}.cobolrt.cics.DetJustify.place" if name in justify else "DetCics.typed"
            out.append(f"{ind}        {call}({i}, {ln or 'null'}, {vals}.get({G_jstr(key)}), CS{tail});")
            out.append(f"{ind}    }}")
        out.append(f"{ind}}}")
        return out + self.input_outcome(opts, resp, ind)

    def constant_int(self, text: str) -> int | None:
        """An option's value when the translator knows it: an integer literal, LENGTH OF an item, or a data item
        with a numeric VALUE the program never changes; else None."""

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


def _literal(text: str | None) -> str | None:
    if text and text.strip()[:1] in "'\"":
        return text.strip()[1:-1].upper()
    return None


G_jstr = jstr
