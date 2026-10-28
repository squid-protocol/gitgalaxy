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
        "ibm": "CICS macro-level API; obsolete and replaced by EXEC CICS commands (macro-level programs do not compile with Enterprise COBOL or execute under Language Environment)",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/dfhp300.pdf",
        "note": "CICS TS for OS/390 R3 Application Programming Guide (SC33-1687-02) Appendix A p.555 ('CICS commands and their equivalent obsolete macros'); Enterprise COBOL V3R1 Migration Guide (GC27-1409-00, igy3mg00.pdf) ch.17 p.205.",
    },
    "csa-tca-dsect": {
        "ibm": "CICS macro-level CSA / TCA dsects (DFHCSADS, DFHTCADS); gone with macro level",
        "verified": True,
        "source": "https://www.ibm.com/docs/SSGMCP_5.6.0/pdf/data-areas_pdf.pdf",
        "note": "CICS TS 5.6 Data Areas p.73 Table 53 ('DFHCSADS SECTION - CSA') & p.860 ('TCA - Task Control Area'); CICS TS for OS/390 R3 Application Programming Guide (SC33-1687-02, dfhp300.pdf) ch.4 p.34 (`DFHTCADS`). Also CICS/VS System Programmer's Reference Manual (SH20-1043-6) p.117 (`COPY DFHCSADS`, `COPY DFHTCADS`).",
    },
    "bll-cells": {
        "ibm": "OS/VS COBOL Base Locator for Linkage; replaced by ADDRESS OF in VS COBOL II and Enterprise COBOL",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/igy3mg00.pdf",
        "note": "Enterprise COBOL V3R1 Compiler and Run-Time Migration Guide (GC27-1409-00) ch.2 Table 8 p.9 ('eliminates the need for BLL cells') & ch.17 p.210-215 ('Base locator for LINKAGE-SECTION (BLL) cells', Example 1-3 replacing BLL cells with `ADDRESS OF` and `SET ADDRESS OF`).",
    },
    "service-reload": {
        "ibm": "OS/VS COBOL SERVICE RELOAD; not required in VS COBOL II or Enterprise COBOL (treated as a comment)",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/igy3mg00.pdf",
        "note": "Enterprise COBOL V3R1 Migration Guide (GC27-1409-00) ch.17 p.210 ('In OS/VS COBOL, for programs to be executed under CICS, the SERVICE RELOAD statement is required to ensure addressability of items defined in the LINKAGE SECTION. In Enterprise COBOL, the SERVICE RELOAD statement is not required. If it is encountered, it is treated as a comment'); also SC33-1688-02 (dfhp400.pdf) p.12 ('In OS/VS COBOL (but not VS COBOL II)...').",
    },
    "handle-condition": {
        "ibm": "CICS command level HANDLE family (HANDLE CONDITION, HANDLE AID, HANDLE ABEND); RESP / RESP2 are the inline alternative",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/dfhp400.pdf",
        "note": "CICS TS for OS/390 R3 Application Programming Reference (SC33-1688-02) ch.1 p.149 (`HANDLE ABEND`), p.150 (`HANDLE AID`), p.152 (`HANDLE CONDITION`), and CICS Application Programming Guide (SC33-1687-02, dfhp300.pdf) ch.20 p.225-234 ('Dealing with exception conditions').",
    },
    "dli": {
        "ibm": "IMS DL/I call interface (CBLTDLI) and EXEC DLI under CICS",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/igy3mg00.pdf",
        "note": "Enterprise COBOL V3R1 Migration Guide (GC27-1409-00) ch.17 Table 44 p.206 (`CALL CBLTDLI`), p.209 (`EXEC DLI`), p.211-212 (`CALL 'CBLTDLI' USING PCB PSBNAME ADDRESS OF DLIUIB`), and Appendix E p.279 (`EXEC DLI` vs `CBLTDLI`).",
    },
    "langlvl-1": {
        "ibm": "OS/VS COBOL language level option LANGLVL(1) (COBOL 68 / 74 elements)",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/igy3mg00.pdf",
        "note": "Enterprise COBOL V3R1 Migration Guide (GC27-1409-00) ch.10 p.113 ('OS/VS COBOL programs compiled with either LANGLVL(1) or LANGLVL(2) can contain either COBOL 68 Standard or COBOL 74 Standard elements') & Appendix C p.261 ('LANGLVL(1) statements not supported').",
    },
    "address-of": {
        "ibm": "VS COBOL II and later: ADDRESS OF special register",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/igy3mg00.pdf",
        "note": "Enterprise COBOL V3R1 Migration Guide (GC27-1409-00) ch.17 p.211-214 (`SET(ADDRESS OF AREA1)` replacing BLL cells); also CICS Application Programming Guide (SC33-1687-02, dfhp300.pdf) ch.4 p.34-36 ('Based addressing').",
    },
    "set-address": {
        "ibm": "VS COBOL II and later: SET ADDRESS OF statement",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/igy3mg00.pdf",
        "note": "Enterprise COBOL V3R1 Migration Guide (GC27-1409-00) ch.17 p.212 (`SET ADDRESS OF PCB-ADDRESSES TO PCBADDR`) & p.214 (`SET ADDRESS OF CHAINED-STORAGE TO CHS-NEXT`).",
    },
    "resp": {
        "ibm": "CICS command-level RESP / RESP2 inline condition-handling options",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/dfhp400.pdf",
        "note": "CICS TS for OS/390 R3 Application Programming Reference (SC33-1688-02) ch.1 p.5 ('RESP and RESP2 options: You can use the RESP option with any command to test whether a condition was raised during its execution... use the RESP2 option to determine exactly why a condition occurred').",
    },
    "exec-sql": {
        "ibm": "Db2 precompiler and integrated coprocessor EXEC SQL host-language support",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/igy3mg00.pdf",
        "note": "Enterprise COBOL V3R1 Migration Guide (GC27-1409-00) Appendix K p.311 ('DB2 Coprocessor Integration', example of `EXEC SQL INCLUDE SQLCA END-EXEC` and `EXEC SQL SELECT ... END-EXEC` with the DB2 precompiler and `SQL` compiler option).",
    },
    "dpl-link-sysid": {
        "ibm": "CICS distributed program link (LINK ... SYSID)",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/dfhp400.pdf",
        "note": "CICS TS for OS/390 R3 Application Programming Reference (SC33-1688-02) ch.1 p.186 (`LINK PROGRAM(name) ... SYSID(systemname)`: 'Distributed program link: ... You specify a remote region name on the SYSID option').",
    },
    "cmpr2": {
        "ibm": "VS COBOL II and IBM COBOL CMPR2 compiler option (COBOL 74 compatibility; removed in Enterprise COBOL)",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/igy3mg00.pdf",
        "note": "Enterprise COBOL V3R1 Migration Guide (GC27-1409-00) ch.2 p.16 ('CMPR2 compiler option not available: Existing programs compiled with CMPR2 must be converted to NOCMPR2 (1985 COBOL Standard)') & ch.12 p.157 ('Upgrading VS COBOL II programs compiled with the CMPR2 compiler option').",
    },
    "langlvl-2": {
        "ibm": "OS/VS COBOL LANGLVL(2) compiler option",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/igy3mg00.pdf",
        "note": "Enterprise COBOL V3R1 Migration Guide (GC27-1409-00) ch.10 p.113 & Appendix C p.261 ('LANGLVL(1) and LANGLVL(2) statements not supported').",
    },
    "mq-call": {
        "ibm": "IBM MQ (WebSphere MQ / MQSeries) MQI calls from COBOL (CALL 'MQCONN', 'MQOPEN', 'MQPUT', 'MQGET', ...)",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/csqzal06.pdf",
        "note": "WebSphere MQ V5.3 Application Programming Guide (SC34-6064-00) ch.10-13 & Appendix B p.545-555 ('COBOL examples', `CALL 'MQCONN'`, `CALL 'MQOPEN'`, `CALL 'MQPUT'`, `CALL 'MQGET'`, `CALL 'MQCLOSE'`, `CALL 'MQDISC'`).",
    },
    "exci": {
        "ibm": "CICS external call interface (EXCI), CALL DFHXCIS and DFHXCOPT",
        "verified": True,
        "source": "https://www.ibm.com/docs/SSGMCP_5.4.0/pdf/exci_pdf.pdf",
        "note": "CICS TS for z/OS 5.4 Using EXCI ch.2 p.11-20 (`CALL DFHXCIS` syntax for Initialize_User, Allocate_Pipe, Open_Pipe, DPL_Request, Close_Pipe, Deallocate_Pipe) & ch.3 p.65 (`DFHXCOPT`).",
    },
    "bridge-3270": {
        "ibm": "CICS 3270 bridge and BMS ADS descriptor copybooks (DFHBR* copybooks)",
        "verified": True,
        "source": "https://www.ibm.com/docs/SSGMCP_5.4.0/pdf/external-interfaces_pdf.pdf",
        "note": "CICS TS for z/OS 5.4 External Interfaces Guide ch.2 Table 5 & Table 6 p.24-25 ('Link3270 message copybooks': `DFHBRIHO`, `DFHBRIIO`, `DFHBRIOO`, `DFHBRICO`, `DFHBR2HO`, ...), CICS TS for OS/390 R3 Application Programming Guide (SC33-1687-02, dfhp300.pdf) ch.26 Table 22 p.330 (`DFHBRARD`, `DFHBRARH`, `DFHBRARL`, `DFHBRARO`), and WebSphere MQ Application Programming Guide (SC34-6064-00, csqzal06.pdf) ch.17 p.287 (`DFHBRMQO`).",
    },
    "le-callable": {
        "ibm": "Language Environment callable services (CEExxxx), LE for OS/390 and z/OS",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/igy3mg00.pdf",
        "note": "Enterprise COBOL V3R1 Migration Guide (GC27-1409-00) ch.2 Table 8 p.10-11 ('Language Environment callable services'), ch.6 p.71 (`CALL CEE3ABD`), and Appendix G Table 52 p.291 (`CEE3ABD`, `CEEDAYS`, `CEEDATE`, `CEEHDLR`, ...).",
    },
    "channel-container": {
        "ibm": "CICS TS 3.1: channels and containers",
        "verified": True,
        "source": "https://www.redbooks.ibm.com/abstracts/sg247227.html",
    },
    "web-soap": {
        "ibm": "CICS web support (EXEC CICS WEB) and web services (SOAPFAULT, INVOKE SERVICE / INVOKE WEBSERVICE)",
        "verified": True,
        "source": "https://www.ibm.com/docs/SSGMCP_5.5.0/pdf/web-services_pdf.pdf",
        "note": "CICS TS for z/OS 5.5 Using Web Services with CICS p.131-133 (`EXEC CICS SOAPFAULT`, `EXEC CICS INVOKE WEBSERVICE`, `INVOKE SERVICE`) and CICS TS for z/OS 5.2 Internet Guide (SC34-7281-00, publibfp.dhe.ibm.com/epubs/pdf/dfhtlg00.pdf) ch.11 p.251 (`EXEC CICS WEB SEND`, `INVOKE SERVICE`).",
    },
    "json-xml": {
        "ibm": "Enterprise COBOL 6.1 JSON GENERATE, 6.2 JSON PARSE (XML PARSE / GENERATE are older)",
        "verified": True,
        "source": "https://www.ibm.com/support/pages/system/files/support/swg/swgdocs.nsf/0/a1f5f4c663a37eb58525818a00320a76/$FILE/COBOL%20V6.2%20Whats%20New.pdf",
    },
    "async": {
        "ibm": "CICS TS 5.4 asynchronous API (RUN TRANSID, FETCH CHILD / ANY, FREE CHILD)",
        "verified": True,
        "source": "https://www.redbooks.ibm.com/redbooks/pdfs/sg248411.pdf",
        "note": "IBM Redbooks SG24-8411-00 'IBM CICS Asynchronous API: Concurrent Processing Made Simple' ch.1-2 (`EXEC CICS RUN TRANSID`, `EXEC CICS FETCH CHILD`, `EXEC CICS FETCH ANY`, `EXEC CICS FREE CHILD`, introduced in CICS TS V5.4).",
    },
    "named-counter": {
        "ibm": "CICS named counter facility (GET / UPDATE / DEFINE / DELETE COUNTER, fullword and DCOUNTER doubleword)",
        "verified": True,
        "source": "https://www.ibm.com/docs/en/cics-ts/6.x?topic=servers-using-named-counter-exec-interface",
        "note": "The page states the commands, not a release; the era (4) is this tool's reading, not an IBM date.",
    },
    "arith-extend": {
        "ibm": "Enterprise COBOL ARITH(EXTEND) compiler option (31-digit decimal precision)",
        "verified": True,
        "source": "https://publibfp.dhe.ibm.com/epubs/pdf/igy3mg00.pdf",
        "note": "Enterprise COBOL V3R1 Migration Guide (GC27-1409-00) ch.2 Table 7 p.7 ('With ARITH(EXTEND) you can specify 31 digits in the PICTURE clause, fixed-point numeric literals, and arguments to NUMVAL and NUMVAL-C') & Appendix F Table 47 p.281 (`ARITH(EXTEND)` vs `ARITH(COMPAT)`).",
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
