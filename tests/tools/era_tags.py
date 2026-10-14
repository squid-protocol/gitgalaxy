#!/usr/bin/env python3
"""#5117: tag a COBOL / CICS program with its era, from evidence in the source -- the tells it used, not a date.

    python tests/tools/era_tags.py PROGRAM.cbl [...]

Era model (approximate; the tag cites tells, never years):
  0  CICS macro level      DFHxx macro calls (DFHPC TYPE=...), CSA / TCA dsects, no EXEC CICS
  1  command level, OS/VS  BLL cells, SERVICE RELOAD, HANDLE CONDITION / AID / ABEND, DL/I, LANGLVL(1)
  2  COBOL II / COBOL 85   ADDRESS OF, SET ADDRESS, RESP / RESP2, EXEC SQL, DPL (LINK SYSID), CMPR2, LANGLVL(2)
  3  LE / COBOL for OS/390 MQ calls, EXCI, 3270 bridge, LE callable services (CEExxxx)
  4  Enterprise COBOL      channels / containers, WEB / SOAP, JSON / XML, async (RUN TRANSID, FETCH), named counters

A program's `era` is the latest era a tell reaches (the code is at least that modern). Most tells are floors ("era 2+":
RESP, EXEC SQL, channels are written in every later era), so they only raise `era`. A few are period-bound (macro
calls, BLL cells, HANDLE CONDITION, DL/I, CMPR2, LANGLVL): `earliest` is the oldest of those, and a program whose
period-bound tell is older than its `era` is `mixed` -- layered code, such as a command-level 1980s program with a
2010s channel call. The tells of each era are listed. A program with no tell has `era` None. Old tells survive in new code (HANDLE CONDITION
is still written today), so the tag is evidence, not a verdict. This detects only: the macro tables (#5120) and the
macro-level refusal (#5121) are separate. Only the program's own text is read: a tell inside a copybook is not seen.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ERAS = (0, 1, 2, 3, 4)

_I = re.IGNORECASE
_NAME = r"[A-Z0-9][A-Z0-9-]*"


def _word(name: str) -> str:
    """A COBOL word `name`, possibly the head, tail or middle of a hyphenated data name (WS-BLL-CELLS)."""
    return rf"(?<![A-Z0-9-])(?:{_NAME}-)?{name}(?:-{_NAME})?(?![A-Z0-9-])"


# (tell, era, scope, pattern). scope: "asm" = the file as written, only `*` lines dropped (assembler macro text), "raw" = the COBOL lines as written (CALL targets, CBL cards), "code" = the
# program text without comments, sequence area and string literals, "cics" = inside EXEC CICS blocks, "cbl" = the CBL / PROCESS cards.
TELLS: tuple[tuple[str, int, str, re.Pattern[str]], ...] = (
    ("dfh-macro-call", 0, "asm", re.compile(r"^(?:[A-Z0-9@#$]+\s+)?DFH[A-Z]{2}\s+(?:TYPE\s*=|[A-Z]+\s*=)", _I | re.M)),
    ("csa-tca-dsect", 0, "code", re.compile(r"(?<![A-Z0-9-])DFH(?:CSADS|TCADS)(?![A-Z0-9-])", _I)),
    ("bll-cells", 1, "code", re.compile(_word("BLL") + r"|(?<![A-Z0-9-])BLL\d+(?![A-Z0-9-])", _I)),
    ("service-reload", 1, "code", re.compile(r"\bSERVICE\s+RELOAD\b", _I)),
    ("handle-condition", 1, "cics", re.compile(r"\bHANDLE\s+(?:CONDITION|AID|ABEND)\b", _I)),
    ("dli", 1, "raw", re.compile(r"\bCALL\s+['\"]CBLTDLI['\"]|\bEXEC\s+DLI\b", _I)),
    ("langlvl-1", 1, "cbl", re.compile(r"\bLANGLVL\s*\(\s*1\s*\)", _I)),
    ("address-of", 2, "code", re.compile(r"\bADDRESS\s+OF\b", _I)),
    ("set-address", 2, "code", re.compile(r"\bSET\s+ADDRESS\b", _I)),
    ("resp", 2, "cics", re.compile(r"\bRESP2?\s*\(", _I)),
    ("exec-sql", 2, "code", re.compile(r"\bEXEC\s+SQL\b", _I)),
    ("dpl-link-sysid", 2, "cics", re.compile(r"\bLINK\b[^\0]*?\bSYSID\s*\(", _I | re.S)),
    ("cmpr2", 2, "cbl", re.compile(r"(?<!NO)\bCMPR2\b", _I)),
    ("langlvl-2", 2, "cbl", re.compile(r"\bLANGLVL\s*\(\s*2", _I)),
    (
        "mq-call",
        3,
        "raw",
        re.compile(r"\bCALL\s+['\"]MQ(?:CONNX?|OPEN|PUT1?|GET|CLOSE|DISC|INQ|SET|CMIT|BACK)['\"]", _I),
    ),
    ("exci", 3, "raw", re.compile(r"['\"]DFHXCIS['\"]|(?<![A-Z0-9-])(?:EXCI|DFHXCOPT|DFHXCPRX)(?![A-Z0-9-])", _I)),
    ("bridge-3270", 3, "code", re.compile(r"(?<![A-Z0-9-])DFHBR[A-Z0-9]+(?![A-Z0-9-])", _I)),
    ("le-callable", 3, "raw", re.compile(r"\bCALL\s+['\"]CEE[A-Z0-9]+['\"]", _I)),
    (
        "channel-container",
        4,
        "cics",
        re.compile(r"\b(?:PUT|GET|DELETE|MOVE|STARTBROWSE|GETNEXT|ENDBROWSE)\s+CONTAINER\b|\bCHANNEL\s*\(", _I),
    ),
    ("web-soap", 4, "cics", re.compile(r"\bWEB\s+[A-Z]|\bINVOKE\s+(?:SERVICE|WEBSERVICE)\b|\bSOAPFAULT\b", _I)),
    ("json-xml", 4, "code", re.compile(r"\b(?:JSON|XML)\s+(?:PARSE|GENERATE)\b", _I)),
    ("async", 4, "cics", re.compile(r"\bRUN\s+TRANSID\b|\bFETCH\s+(?:CHILD|ANY)\b|\bFREE\s+CHILD\b", _I)),
    ("named-counter", 4, "cics", re.compile(r"\b(?:GET|UPDATE|DEFINE|DELETE)\s+D?COUNTER\b", _I)),
    ("arith-extend", 4, "cbl", re.compile(r"\bARITH\s*\(\s*EXTEND\s*\)", _I)),
)

# Tells that belong to their period (the construct went out of use or was replaced); every other tell is a floor.
PERIOD_BOUND = frozenset(
    {
        "dfh-macro-call",
        "csa-tca-dsect",
        "bll-cells",
        "service-reload",
        "handle-condition",
        "dli",
        "langlvl-1",
        "cmpr2",
        "langlvl-2",
    }
)

_EXEC = re.compile(r"\bEXEC\s+CICS\b(.*?)\bEND-EXEC\b", _I | re.S)
_CBL = re.compile(r"^\s{0,6}(?:CBL|PROCESS)\s+(.*)$", _I | re.M)
_LITERAL = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"")
_SEQ = re.compile(r"^[ 0-9]{6}")


def _is_fixed(lines: list[str]) -> bool:
    """Fixed form: most lines (CBL / PROCESS cards aside) carry only blanks or digits in columns 1-6."""
    body = [ln for ln in lines if ln.strip() and not _CBL.match(ln) and not ln.lstrip().startswith("*>")]
    if not body:
        return True
    return sum(bool(_SEQ.match(ln)) for ln in body) * 2 >= len(body)


def clean(text: str) -> tuple[str, str]:
    """(raw, code): `raw` is the text with comment lines blanked and the sequence / identification areas cut (fixed
    form), `code` is `raw` with string literals blanked as well. Line numbers are kept (a blanked line stays a line)."""
    lines = text.splitlines()
    fixed = _is_fixed(lines)
    out = []
    for ln in lines:
        s = ln.lstrip()
        if s.startswith("*>"):
            out.append("")
        elif fixed and not _CBL.match(ln):
            out.append("" if len(ln) > 6 and ln[6] in "*/" else ln[6:72] if len(ln) > 6 else "")
        elif fixed:
            out.append(ln[:72])
        else:
            out.append("" if ln.startswith("*") else ln)
    raw = "\n".join(out)
    return raw, "\n".join(_LITERAL.sub(lambda m: " " * len(m.group()), ln) for ln in out)


def tag_program(text: str) -> dict[str, Any]:
    """The era tag of one program's source text: {era, earliest, mixed, tells: [{tell, era, count, first_line}]}."""
    raw, code = clean(text)
    asm = "\n".join("" if ln.startswith("*") else ln for ln in text.splitlines())
    exec_text = "\0".join(m.group(0) for m in _EXEC.finditer(code))
    cbl_text = "\n".join(m.group(1) for m in _CBL.finditer(raw))
    found = []
    for tell, era, scope, pat in TELLS:
        if scope == "asm":
            hay = asm
        elif scope == "raw":
            hay = raw
        elif scope == "cbl":
            hay = cbl_text
        elif scope == "cics":
            hay = exec_text
        else:
            hay = code
        hits = list(pat.finditer(hay))
        if not hits:
            continue
        # "cics" and "cbl" scopes are joined blocks: the line is only meaningful against the whole text.
        first = hay.count("\n", 0, hits[0].start()) + 1 if scope in ("raw", "code") else None
        found.append({"tell": tell, "era": era, "count": len(hits), "first_line": first})
    if found and any(t["era"] == 0 for t in found) and re.search(r"\bEXEC\s+CICS\b", code, _I):
        # DFHxx text beside EXEC CICS is a translated listing or a comment-like mention, not macro-level code.
        found = [t for t in found if t["tell"] != "dfh-macro-call"]
    eras = [t["era"] for t in found]
    era = max(eras) if eras else None
    bound = [t["era"] for t in found if t["tell"] in PERIOD_BOUND]
    earliest = min(bound) if bound else era
    return {
        "era": era,
        "earliest": earliest,
        "mixed": era is not None and earliest < era,
        "tells": found,
    }


def summarise(programs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The estate summary of per-program tags: programs per era, mixed, untagged, programs per tell."""
    by_era = Counter("none" if t["era"] is None else str(t["era"]) for t in programs.values())
    tells: Counter[str] = Counter()
    for t in programs.values():
        tells.update(x["tell"] for x in t["tells"])
    return {
        "programs": len(programs),
        "by_era": {k: by_era[k] for k in ("0", "1", "2", "3", "4", "none")},
        "mixed": sum(t["mixed"] for t in programs.values()),
        "tells": dict(sorted(tells.items())),
    }


def main(argv: list[str] | None = None) -> int:
    paths = [Path(a) for a in (argv if argv is not None else sys.argv[1:])]
    if not paths:
        print(__doc__)
        return 2
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from gitgalaxy.core.source_text import read_source

    for p in paths:
        t = tag_program(read_source(p).text)
        names = ", ".join(f"{x['tell']}(era {x['era']})" for x in t["tells"]) or "no tell"
        print(f"{p}: era {t['era']}{' MIXED from ' + str(t['earliest']) if t['mixed'] else ''}: {names}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
