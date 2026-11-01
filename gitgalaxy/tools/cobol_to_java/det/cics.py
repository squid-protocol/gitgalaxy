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
from typing import Any

from gitgalaxy.standards.cics.commands import COMMANDS as SPEC
from gitgalaxy.standards.cics.commands import whole_refusal
from gitgalaxy.standards.cics.commands.assign import (
    TERMINAL_OPTIONS,  # noqa: F401 -- the conditions mixin reads it here
)
from gitgalaxy.standards.cics.commands.handles import AID_KEYS  # noqa: F401 -- the conditions mixin reads it here
from gitgalaxy.standards.cics.commands.send_text import TEXT_OPTIONS  # noqa: F401 -- tests read it here
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
    _literal,
    _msg,
    _one_of,
    _option,
    _requires,
    jstr,
    region_page,
)
from gitgalaxy.tools.cobol_to_java.det.cics_conditions import ConditionCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_containers import ContainerCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_counters import CounterCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_faults import FaultCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_filecontrol import FileControlCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_program import ProgramControlCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_queues import QueueCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_storage import StorageCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_system import SystemCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_taskcontrol import TaskControlCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_terminal import TerminalCommands  # #5274
from gitgalaxy.tools.cobol_to_java.det.cics_web import WebCommands  # #5274

COPY = Path(__file__).parent / "copy"  # DFHEIBLK, DFHAID, DFHBMSCA

# The translator's command families (#5274): `Cics._command` asks each `dispatch` in turn and the first that answers with
# lines wins. A new command goes in its family's `dispatch`, so a slice leaves this file alone; a new family is one line
# here and one base of `Cics`. The order is the dispatch order, and it matters: containers and task control come before
# counters, whose `dispatch` refuses every other command naming a counter; queues come before system (INQUIRE).
COMMAND_FAMILIES: tuple[Any, ...] = (
    ContainerCommands,
    TaskControlCommands,
    CounterCommands,
    TerminalCommands,
    ProgramControlCommands,
    FileControlCommands,
    ConditionCommands,
    QueueCommands,
    SystemCommands,
    StorageCommands,
    WebCommands,
)


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
class Cics(
    ConditionCommands,
    ContainerCommands,
    CounterCommands,
    FaultCommands,
    FileControlCommands,
    ProgramControlCommands,
    QueueCommands,
    StorageCommands,
    SystemCommands,
    TaskControlCommands,
    TerminalCommands,
    WebCommands,
):
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
            # #5079 (X63): WAIT EVENT ECADDR(ptr) and WAIT EXTERNAL ECBLIST(ptr) are commands of their own
            for second in ("EVENT", "EXTERNAL"):
                if second in opts and opts[second] is None:
                    words = ["WAIT", second]
                    del opts[second]
                    break
        verb = " ".join(words)
        check_options(words, opts)  # #4411: an option the translation would ignore is refused first
        key = command_key(words, opts)
        for family in COMMAND_FAMILIES:
            lines = family.dispatch(self, words, verb, key, opts, ind)
            if lines is not None:
                return lines
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

    def pointer(self, text: str | None) -> str:
        """#4771 (X47): the Field of the plain USAGE POINTER item an option names (SET / DATAPOINTER)."""

        try:
            ref = E.Parser(
                E.tokenize(_arg(text).strip())
            ).ref()  # #5079: `PTR` or an element `TBL(I)` of a pointer table
            return self.g.pointer_item(ref.name, ref if ref.subscripts else None)
        except Untranslatable as e:
            raise CicsError(str(e)) from None

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


G_jstr = jstr
