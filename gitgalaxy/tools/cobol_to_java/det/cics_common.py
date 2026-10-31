"""#7153: the helpers the det CICS translator and its mixins share (cics.py, cics_taskcontrol.py ...), in a leaf that
imports nothing from det/cics.py or det/gen.py: a mixin that imported them back from cics.py closed an import cycle
(CodeQL py/cyclic-import). cics.py re-exports every name here, so existing importers are unchanged."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands import COMMANDS as SPEC
from gitgalaxy.standards.cics.commands.shared import BOTH_FORMS, NEEDS_ARGUMENT
from gitgalaxy.standards.cics.commands.terminal import SEND_CONTROL_OPTIONS
from gitgalaxy.standards.cics.model import GroupKind

_SEND_CONTROL = frozenset(SEND_CONTROL_OPTIONS)  # #4413: its device controls


class CicsError(Exception):
    pass


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
