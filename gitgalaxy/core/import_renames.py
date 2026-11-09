# ==============================================================================
# GitGalaxy Core: names a file imports under another name (#8161, X5)
#
# PURPOSE:
# `import { add as plus2 } from "./math"`, `from m import f as g` and
# `use a::b as c;` bind a local name to another module's definition. A bare
# `plus2()` is then a call to `add`, which no definition is named after, so the
# call resolver found nothing (no row). This module reads one file's
# literal-shielded text and returns local name -> imported name; the detector
# records it per unit for the bare calls that use one (`calls_out_renames`),
# and the resolver looks the call up under the imported name. Default imports,
# namespace imports (`import * as m`, `import numpy as np`: the module itself)
# and re-exports (`export { x as y }`, a barrel's own map) are not renames of a
# definition here. Every quantifier is bounded.
# ==============================================================================
import re

RENAME_LANGS = frozenset({"typescript", "javascript", "python", "rust"})

_JS_IDENT = r"[A-Za-z_$][\w$]{0,127}"
_JS_NAMED = re.compile(r"\bimport\b[^;{}]{0,300}?\{(?P<names>[^{}]{0,3000})\}[^;{}]{0,300}?\bfrom\b")
_JS_PAIR = re.compile(
    r"^(?:type[ \t\r\n]+)?(?P<orig>" + _JS_IDENT + r")[ \t\r\n]+as[ \t\r\n]+(?P<local>" + _JS_IDENT + r")$"
)
_PY_IDENT = r"[A-Za-z_]\w{0,127}"
_PY_FROM = re.compile(r"(?m)^[ \t]*from[ \t]+[\w.]{1,200}[ \t]+import[ \t]+(?P<names>\([^()]{0,3000}\)|[^\n#]{1,1000})")
_PY_PAIR = re.compile(r"^(?P<orig>" + _PY_IDENT + r")[ \t\r\n]+as[ \t\r\n]+(?P<local>" + _PY_IDENT + r")$")
_RS_USE = re.compile(r"\buse[ \t\r\n]+(?P<body>[^;]{1,3000});")
_RS_PAIR = re.compile(
    r"(?<![\w])(?P<orig>[A-Za-z_]\w{0,127})[ \t\r\n]+as[ \t\r\n]+(?P<local>[A-Za-z_]\w{0,127})(?![\w])"
)


def _note(out: dict[str, str | None], local: str, orig: str) -> None:
    """Record `local -> orig`; a local name bound to two different names is no rename (None)."""
    if local in out and out[local] != orig:
        out[local] = None
    else:
        out.setdefault(local, orig)


def import_renames(lang: str, code: str) -> dict[str, str]:
    """Local name -> the imported definition's own name, for the file `code` (literal-shielded)."""
    out: dict[str, str | None] = {}
    if lang in ("typescript", "javascript"):
        for m in _JS_NAMED.finditer(code):
            for item in m.group("names").split(","):
                p = _JS_PAIR.match(item.strip())
                if p and p.group("orig") != "default" and p.group("orig") != p.group("local"):
                    _note(out, p.group("local"), p.group("orig"))
    elif lang == "python":
        for m in _PY_FROM.finditer(code):
            for item in m.group("names").strip("() \t\r\n").split(","):
                p = _PY_PAIR.match(item.strip())
                if p and p.group("orig") != p.group("local"):
                    _note(out, p.group("local"), p.group("orig"))
    elif lang == "rust":
        for m in _RS_USE.finditer(code):
            for p in _RS_PAIR.finditer(m.group("body")):
                orig, local = p.group("orig"), p.group("local")
                if orig not in ("self", "super", "crate") and local != "_" and orig != local:
                    _note(out, local, orig)
    return {k: v for k, v in out.items() if v}
