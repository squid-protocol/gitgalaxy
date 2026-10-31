"""#7153: the helpers the det CICS translator and its mixins share (cics.py, cics_taskcontrol.py ...), in a leaf that
imports nothing from det/cics.py or det/gen.py: a mixin that imported them back from cics.py closed an import cycle
(CodeQL py/cyclic-import). cics.py re-exports every name here, so existing importers are unchanged."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gitgalaxy.standards.cics.commands import COMMANDS as SPEC
from gitgalaxy.standards.cics.commands.shared import BOTH_FORMS, NEEDS_ARGUMENT
from gitgalaxy.standards.cics.commands.terminal import SEND_CONTROL_OPTIONS
from gitgalaxy.standards.cics.model import GroupKind

if TYPE_CHECKING:
    from gitgalaxy.tools.cobol_to_java.det import layout as L

_SEND_CONTROL = frozenset(SEND_CONTROL_OPTIONS)  # #4413: its device controls


class CicsError(Exception):
    pass


class Untranslatable(Exception):
    """#7153: the translator refuses a construct by name. Defined here, in the leaf, so dli.py and dyncall.py raise it
    without importing det.gen back (gen.py re-exports it: `gen.Untranslatable` is this class)."""


class KeylengthInvreq(CicsError):
    """#5092 (X52): a KEYLENGTH IBM answers INVREQ (RESP2 25 / 26 / 42); READ emits the result, any other verb refuses."""

    def __init__(self, msg: str, resp2: int):
        super().__init__(msg)
        self.resp2 = resp2


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


def _msg(key: str, kind: GroupKind, option: str, *parts: str) -> str:
    """The message of the command's option rule (its spec Group), with the parts it names filled in."""
    return SPEC[key].group(kind, option).msg.format(*parts)


def _requires(key: str, option: str, needed: str) -> str:
    """#4767: the message of the command's `requires` rule from `option` to `needed` (its spec Group)."""
    for g in SPEC[key].groups:
        if g.kind == "requires" and g.options[0] == option and needed in g.any_of:
            return g.msg
    raise KeyError(f"{key}: no requires group of {option} -> {needed}")


def _arg(v: str | None) -> str:
    """An EXEC CICS option's argument text; a bare option where one is needed is an error."""
    if v is None:
        raise CicsError(NEEDS_ARGUMENT)
    return v


def _option(opts: dict, name: str) -> str | None:
    """#4270: an option's argument, None when the option is not given; given without one, refused."""
    if name not in opts:
        return None
    return _arg(opts[name])


def _one_of(opts: dict, name: str, alt: str) -> str | None:
    """#4413: the argument of option `name` or its alternative form `alt` (LENGTH / FLENGTH), None when neither is
    given; both, or one without an argument, refused."""
    given = [o for o in (name, alt) if o in opts]
    if len(given) > 1:
        raise CicsError(BOTH_FORMS.format(name, alt))
    if given and not opts[given[0]]:
        raise CicsError(f"{given[0]} needs an argument")
    return opts[given[0]] if given else None


def jstr(s: str) -> str:
    """A Java string literal; every non-ASCII or control character escaped."""
    out = []
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif 32 <= o < 127:
            out.append(ch)
        elif o < 256:
            # #4690: never the u-escapes 000a / 000d / 0022 (Java translates them before lexing, cutting the literal open);
            # a three-digit octal escape is exact and cannot swallow a following digit
            out.append(f"\\{o:03o}")
        else:
            out.append(f"\\u{o:04x}")
    return '"' + "".join(out) + '"'


# Library routines the runtime models (each the twin of the harness's COBOL-side model): program -> (Java, args)
LIBRARY = {
    "CEEDAYS": ("__PACKAGE__.cobolrt.le.Ceedays.call", 4),
    "COBDATFT": ("__PACKAGE__.cobolrt.le.Cobdatft.call", 1),
    "MVSWAIT": ("__PACKAGE__.cobolrt.le.Mvswait.call", 1),  # #5106: CardDemo's assembler wait (COBSWAIT)
    "CEELOCT": ("__PACKAGE__.cobolrt.le.Ceeloct.call", 4),  # #4884: also takes the clock first and the charset last
    # #4949: the LE date/time services (register L6); each is the twin of tests/equivalence/le/le_time.c
    "CEEGMT": ("__PACKAGE__.cobolrt.le.Ceegmt.call", 3),
    "CEEUTC": ("__PACKAGE__.cobolrt.le.Ceeutc.call", 3),
    "CEEDATM": ("__PACKAGE__.cobolrt.le.Ceedatm.call", 4),
    "CEESECS": ("__PACKAGE__.cobolrt.le.Ceesecs.call", 4),
    "CEEDATE": ("__PACKAGE__.cobolrt.le.Ceedate.call", 4),
    "CEEISEC": ("__PACKAGE__.cobolrt.le.Ceeisec.call", 9),
    "CEEQCEN": ("__PACKAGE__.cobolrt.le.Ceeqcen.call", 2),
    # #5003: sets the window CEEQCEN reads (one class, one setting)
    "CEESCEN": ("__PACKAGE__.cobolrt.le.Ceeqcen.set", 2),
    # #5003: Lilian seconds to integer fields (the inverse of CEEISEC) and the day of the week of a Lilian date
    "CEESECI": ("__PACKAGE__.cobolrt.le.Ceeseci.call", 9),
    "CEEDYWK": ("__PACKAGE__.cobolrt.le.Ceedywk.call", 3),
    # #5003: the offset from GMT (zero: the run's clock is GMT); CEEUTCO is the same service as CEEGMTO
    "CEEGMTO": ("__PACKAGE__.cobolrt.le.Ceegmto.call", 4),
    "CEEUTCO": ("__PACKAGE__.cobolrt.le.Ceegmto.call", 4),
    # #5858 (register Q5): Db2's SQLCA message formatter as a stand-in, the twin of tests/equivalence/le/dsntiac.c
    "DSNTIAC": ("__PACKAGE__.cobolrt.le.Dsntiac.call", 5),
    # #5945 (register X47): zECS's store-clock wrapper; its 16 bytes are a stated input of the run ($GGC_ZUIDSTCK_TOD)
    "ZUIDSTCK": ("__PACKAGE__.cobolrt.le.Zuidstck.call", 1),
}
LIBRARY_RC = {"DSNTIAC"}  # the routines whose int result is the CALL's RETURN-CODE
LIBRARY_CLOCK = {
    "CEELOCT",
    "CEEGMT",
    "CEEUTC",
    "CEESECS",  # #5003: the system year the century window (a YY) is anchored on
}  # the routines that read the run's clock (the harness pins it, like CURRENT-DATE)
# The COMP-2 arguments (by position) a routine reads or stores by value (Cobol.num / Cobol.store), never by bytes: HFP on
# z/OS, IEEE on the oracle (register C6). Every routine with one, and every clock routine, also takes the charset last.
LIBRARY_FLOATS = {
    "CEELOCT": {1},
    "CEEGMT": {1},
    "CEEUTC": {1},
    "CEEDATM": {0},
    "CEESECS": {2},
    "CEEISEC": {7},
    "CEESECI": {0},
    "CEEGMTO": {2},
    "CEEUTCO": {2},
}
LIBRARY_CHARSET = {*LIBRARY_CLOCK, *LIBRARY_FLOATS, *LIBRARY_RC, "CEEDATE", "CEEQCEN", "CEESCEN"}


def _extents(it: L.Item) -> tuple[tuple[int, int], tuple[int, int], list[int]]:
    """An item's bytes within its record: its first occurrence, the whole of its outermost table, and the ids of
    the OCCURS items it lies in."""
    first = (it.offset, it.offset + it.size * it.occurs)
    full, tables = first, []
    a: L.Item | None = it
    while a is not None:
        if a.occurs > 1:
            tables.append(id(a))
            full = (a.offset, a.offset + a.size * a.occurs)
        a = a.parent
    return first, full, tables


def _occurs_chain(it: L.Item) -> list[L.Item]:
    """The OCCURS items from the outermost to `it` (itself included when it OCCURS)."""
    chain = []
    a: L.Item | None = it
    while a is not None:
        if a.occurs > 1 or a.depending:
            chain.append(a)
        a = a.parent
    return list(reversed(chain))
