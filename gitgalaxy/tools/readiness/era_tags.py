# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#5117: tag a COBOL / CICS program with its era, from evidence in the source -- the tells it used, not a date.

    python -m gitgalaxy.tools.readiness.era_tags PROGRAM.cbl [...]   (or tests/tools/era_tags.py)

Part of the shipped readiness scanner (#4726): `gitgalaxy assess` tags each program with it.

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
macro-level refusal (#5121) are separate. The program's own text is read first, then the copybooks its COPY statements resolved
(`tag_program(text, copybooks)`): a tell found in one lists it under `copybooks`, and `via_copybook` marks a tell the
program text alone does not show. The tag then also carries `program_era`, the era of the program's own text.
An assembler member is tagged the same way through the COPY and macro members it pulls in (`asm_members`; nested ones
too, a macro call only when an estate member has that name). A program whose copybook pass was refused or cut short
(a missing member, a COPY loop, macro level, an unreadable member) carries `copybook_skipped: <reason code>` (#5195):
its tells are the program's own text, so a tell in a copybook may be missing.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gitgalaxy.core import cics_macro_level as ML

ERAS = (0, 1, 2, 3, 4)

_I = re.IGNORECASE
_NAME = r"[A-Z0-9][A-Z0-9-]*"


def _word(name: str) -> str:
    """A COBOL word `name`, possibly the head, tail or middle of a hyphenated data name (WS-BLL-CELLS)."""
    return rf"(?<![A-Z0-9-])(?:{_NAME}-)?{name}(?:-{_NAME})?(?![A-Z0-9-])"


# (tell, era, scope, pattern). scope: "asm" = the file as written, only `*` lines dropped (assembler macro text), "raw" = the COBOL lines as written (CALL targets, CBL cards), "code" = the
# program text without comments, sequence area and string literals, "cics" = inside EXEC CICS blocks, "cbl" = the CBL / PROCESS cards.
TELLS: tuple[tuple[str, int, str, re.Pattern[str]], ...] = (
    (
        "dfh-macro-call",
        0,
        "asm",
        re.compile(r"^(?:[A-Z0-9@#$]*[ \t]+)?DFH[A-Z]{2}[ \t]+(?:TYPE\s*=|[A-Z]+\s*=)", _I | re.M),
    ),
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

# The IBM release or manual behind each tell. `verified` is True only where an opened IBM page states it (see `source`);
# the rest is still to be checked, and `note` says what was tried and what IBM leaves unstated (never invent a cite).
CITE: dict[str, dict[str, Any]] = {
    "dfh-macro-call": {
        "ibm": "CICS macro-level API; support dropped from CICS/ESA 3.2 (1991), replaced by EXEC CICS command level",
        "verified": True,
        "source": "https://www.ibm.com/support/pages/history-cics-transaction-server",
        "note": "Opened when #5117 landed; on 2026-10-16 (#5195) this URL answered HTTP 404, so it could not be re-opened. Re-check it.",
    },
    "csa-tca-dsect": {
        "ibm": "CICS macro-level CSA / TCA dsects (DFHCSADS, DFHTCADS); gone with macro level",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): no IBM page that states the DFHCSADS / DFHTCADS dsects or their withdrawal was opened.",
    },
    "bll-cells": {
        "ibm": "OS/VS COBOL Base Locator for Linkage; replaced by ADDRESS OF in COBOL II (1.x)",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): no opened IBM page states BLL cells or that ADDRESS OF replaced them; the OS/VS COBOL manuals were not reachable.",
    },
    "service-reload": {
        "ibm": "OS/VS COBOL SERVICE RELOAD; withdrawn with OS/VS COBOL",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): no opened IBM page states SERVICE RELOAD or its withdrawal.",
    },
    "handle-condition": {
        "ibm": "CICS command level HANDLE family; RESP / RESP2 are the later style",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): no opened IBM page states that RESP / RESP2 are the later style; the HANDLE family page was not reached.",
    },
    "dli": {
        "ibm": "IMS DL/I call interface (CBLTDLI) and EXEC DLI under CICS",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): no opened IBM page states CBLTDLI or EXEC DLI under CICS.",
    },
    "langlvl-1": {
        "ibm": "OS/VS COBOL language level option LANGLVL(1) (COBOL 74 rules)",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): the Enterprise COBOL 6.4 LANGLVL page was opened and says nothing about LANGLVL(1) or its release.",
    },
    "address-of": {
        "ibm": "COBOL II Release 1: ADDRESS OF special register",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): the Enterprise COBOL 6.4 ADDRESS OF page was opened and states neither the register nor the COBOL II release.",
    },
    "set-address": {
        "ibm": "COBOL II Release 1: SET ADDRESS OF",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): no opened IBM page states SET ADDRESS OF or the COBOL II release it arrived with.",
    },
    "resp": {
        "ibm": "CICS command-level RESP / RESP2 options (CICS/MVS 2.1 and later)",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): no opened IBM page states RESP / RESP2 or CICS/MVS 2.1; the 6.x documentation index was reached, not the option page.",
    },
    "exec-sql": {
        "ibm": "Db2 precompiler EXEC SQL host-language support",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): no opened IBM page states the Db2 precompiler's EXEC SQL host-language support.",
    },
    "dpl-link-sysid": {
        "ibm": "CICS distributed program link (LINK ... SYSID)",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): the CICS 6.x documentation index was reached; no page that states DPL or LINK SYSID was opened.",
    },
    "cmpr2": {
        "ibm": "COBOL for OS/390 and later: CMPR2 compiler option, COBOL II compatibility",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): the Enterprise COBOL V3R3 customization guide was opened: no CMPR2 entry was readable, so no release is stated.",
    },
    "langlvl-2": {
        "ibm": "COBOL II LANGLVL(2) (COBOL 85 rules)",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): the Enterprise COBOL 6.4 LANGLVL page was opened and says nothing about LANGLVL(2) or COBOL 85 rules.",
    },
    "mq-call": {
        "ibm": "IBM MQ MQI calls from COBOL (MQSeries)",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): no opened IBM page states the MQI calls from COBOL or the MQSeries name.",
    },
    "exci": {
        "ibm": "CICS external call interface (EXCI), DFHXCIS",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): IBM's 'Using EXCI' PDFs exist but their text was not readable; no opened page states DFHXCIS or the release.",
    },
    "bridge-3270": {
        "ibm": "CICS 3270 bridge (DFHBRARC and related copybooks)",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): the CICS 6.x '3270 bridge' page was opened: it names no release and none of the DFHBR* copybooks.",
    },
    "le-callable": {
        "ibm": "Language Environment callable services (CEExxxx), LE for OS/390",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): no opened IBM page states the CEExxxx callable services or LE for OS/390.",
    },
    "channel-container": {
        "ibm": "CICS TS 3.1: channels and containers",
        "verified": True,
        "source": "https://www.redbooks.ibm.com/abstracts/sg247227.html",
    },
    "web-soap": {
        "ibm": "CICS web support (EXEC CICS WEB) and web services (SOAPFAULT, INVOKE SERVICE)",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): no opened IBM page states EXEC CICS WEB, SOAPFAULT or INVOKE SERVICE.",
    },
    "json-xml": {
        "ibm": "Enterprise COBOL 6.1 JSON GENERATE, 6.2 JSON PARSE (XML PARSE / GENERATE are older)",
        "verified": True,
        "source": "https://www.ibm.com/support/pages/system/files/support/swg/swgdocs.nsf/0/a1f5f4c663a37eb58525818a00320a76/$FILE/COBOL%20V6.2%20Whats%20New.pdf",
    },
    "async": {
        "ibm": "CICS asynchronous API (RUN TRANSID, FETCH, FREE CHILD)",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): the CICS 6.x documentation index was reached; no page that states RUN TRANSID / FETCH / FREE CHILD was opened.",
    },
    "named-counter": {
        "ibm": "CICS named counter facility (GET / UPDATE / DEFINE / DELETE COUNTER, fullword and DCOUNTER doubleword)",
        "verified": True,
        "source": "https://www.ibm.com/docs/en/cics-ts/6.x?topic=servers-using-named-counter-exec-interface",
        "note": "The page states the commands, not a release; the era (4) is this tool's reading, not an IBM date.",
    },
    "arith-extend": {
        "ibm": "Enterprise COBOL ARITH(EXTEND) compiler option",
        "verified": False,
        "note": "Checked 2026-10-16 (#5195): the Enterprise COBOL V3R3 customization guide lists an ARITH option but its text was not readable, so the release that added EXTEND is not stated.",
    },
}


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

_ASM_TELLS = frozenset(t[0] for t in TELLS if t[2] == "asm")
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


def _scan(text: str) -> list[dict[str, Any]]:
    """The tells of one source text (a program or a copybook): [{tell, era, count, first_line}]."""
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
    return found


def _verdict(found: list[dict[str, Any]]) -> tuple[int | None, int | None, bool]:
    eras = [t["era"] for t in found]
    era = max(eras) if eras else None
    bound = [t["era"] for t in found if t["tell"] in PERIOD_BOUND]
    earliest = min(bound) if bound else era
    return era, earliest, era is not None and earliest < era


def tag_program(text: str, copybooks: dict[str, str] | None = None, asm: bool = False) -> dict[str, Any]:
    """The era tag of one program's source text: {era, earliest, mixed, tells: [{tell, era, count, first_line}]}.

    `copybooks` (#5117) maps each copybook the program's COPY statements resolved (the expansion's member files) to its
    text. Its tells are read the same way, except assembler macro text: a tell it shares with the program lists the
    copybook under `copybooks`; one only it has is a tell of the program too (`via_copybook`, count over the copybooks,
    no line). Those keys, `program_era` (when it differs from `era`) and `copybooks` are present only when non-empty.
    `asm` (an assembler member, #5195): its members are macro / COPY text too, so their assembler tells count."""
    found = _scan(text)
    program_era = _verdict(found)[0]
    by_tell = {t["tell"]: t for t in found}
    books = copybooks or {}
    for name in sorted(books):
        for t in _scan(books[name]):
            if t["tell"] in _ASM_TELLS and not asm:
                continue
            mine = by_tell.get(t["tell"])
            if mine is None:
                mine = {"tell": t["tell"], "era": t["era"], "count": 0, "first_line": None, "via_copybook": True}
                by_tell[t["tell"]] = mine
                found.append(mine)
            if mine.get("via_copybook"):
                mine["count"] += t["count"]
            mine.setdefault("copybooks", []).append(name)
    found.sort(key=lambda t: [x[0] for x in TELLS].index(t["tell"]))
    era, earliest, mixed = _verdict(found)
    out: dict[str, Any] = {"era": era, "earliest": earliest, "mixed": mixed, "tells": found}
    if program_era != era:
        out["program_era"] = program_era
    return out


_COPY_DEPTH = 8  # nested COPY / macro members read before the pass is refused (a deeper chain is a loop in practice)


def asm_members(
    text: str, find: Callable[[str], tuple[str, str] | None], depth: int = _COPY_DEPTH
) -> tuple[dict[str, str], str | None]:
    """(members, skipped) of an assembler source (#5195): the COPY members and macro members it pulls in, nested ones too.

    `find(name)` returns (key, text) of the estate member of that name, or None. `COPY X` must resolve: a missing member
    is `CopyNotFound`. A macro call is expanded only when its name is an estate member; any other name is an instruction
    or a system macro (DFHPC, ...) and is no gap -- IBM's own macros are never shipped. A COPY loop is `CopyCycle`, a
    chain past `depth` levels `CopyDepth`; the members read so far are kept. `skipped` is the first such reason or None."""
    books: dict[str, str] = {}
    state: dict[str, str | None] = {"skipped": None}
    looked: dict[str, tuple[str, str] | None] = {}

    def walk(body: str, path: tuple[str, ...]) -> None:
        after_macro = False
        for _line, stmt in ML._asm_statements(body.splitlines()):
            m = ML._ASM_STATEMENT.match(stmt)
            if not m:
                continue
            op = m.group(2).upper()
            if after_macro:  # the prototype statement names the macro being defined, not a call
                after_macro = False
                continue
            if op == "MACRO":
                after_macro = True
                continue
            is_copy = op == "COPY"
            name = ML._first_operand(m.group(3) or "") if is_copy else op
            if not name:
                continue
            if name in path:
                if is_copy:  # a macro may call itself (HLASM recursion); a COPY may not
                    state["skipped"] = state["skipped"] or "CopyCycle"
                continue
            if name not in looked:
                looked[name] = find(name)
            hit = looked[name]
            if hit is None:
                if is_copy:
                    state["skipped"] = state["skipped"] or "CopyNotFound"
                continue
            key, member = hit
            if key in books:  # a member two paths reach is read once
                continue
            if len(path) >= depth:
                state["skipped"] = state["skipped"] or "CopyDepth"
                continue
            books[key] = member
            walk(member, (*path, name))

    walk(text, ())
    return books, state["skipped"]


def mark_skipped(tag: dict[str, Any], reason: str) -> dict[str, Any]:
    """#5195: the tag of a program whose copybook pass did not run (or did not finish): its tells are the program's own
    text only (or the members read before the stop), so a copybook tell may be missing. `copybook_skipped` is the
    reason (an exception class or `CopyNotFound`, `CopyCycle`, `CopyDepth`, `UnreadableCopybook`), never a message."""
    return {**tag, "copybook_skipped": tag.get("copybook_skipped") or reason}


def summarise(programs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The estate summary of per-program tags: programs per era, mixed, untagged, programs per tell."""
    by_era = Counter("none" if t["era"] is None else str(t["era"]) for t in programs.values())
    tells: Counter[str] = Counter()
    for t in programs.values():
        tells.update(x["tell"] for x in t["tells"])
    out = {
        "programs": len(programs),
        "by_era": {k: by_era[k] for k in ("0", "1", "2", "3", "4", "none")},
        "mixed": sum(t["mixed"] for t in programs.values()),
        "tells": dict(sorted(tells.items())),
    }
    raised = sum("program_era" in t for t in programs.values())
    if raised:  # present only when a copybook raised some program's era
        out["raised_by_copybook"] = raised
    skipped = sum("copybook_skipped" in t for t in programs.values())
    if skipped:  # present only when some program's copybook pass was skipped (#5195)
        out["copybook_skipped"] = skipped
    return out


def main(argv: list[str] | None = None) -> int:
    paths = [Path(a) for a in (argv if argv is not None else sys.argv[1:])]
    if not paths:
        print(__doc__)
        return 2
    from gitgalaxy.core.source_text import read_source

    for p in paths:
        t = tag_program(read_source(p).text)
        names = ", ".join(f"{x['tell']}(era {x['era']})" for x in t["tells"]) or "no tell"
        print(f"{p}: era {t['era']}{' MIXED from ' + str(t['earliest']) if t['mixed'] else ''}: {names}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
