# ==============================================================================
# GitGalaxy Core: CICS web / API services from the assistant JCL (#3496)
#
# PURPOSE:
# A CICS estate exposes programs as SOAP / JSON services -- and calls out to
# others -- through IBM's web-services assistants, batch utilities run from JCL:
#
#   DFHLS2WS  language structure -> web service (a PROVIDER: the program becomes
#             a SOAP service at URI, its COMMAREA / container described by the
#             request / response copybooks)
#   DFHLS2JS  language structure -> JSON service (provider)
#   DFHWS2LS  WSDL -> language structure (a REQUESTER: the program calls out)
#   DFHJS2LS  JSON schema -> language structure (requester)
#
# Their parameters are in-stream `KEY=VALUE` lines (the INPUT.SYSUT1 / SYSIN
# `DD *` data after the EXEC). That is the estate's existing API surface, which
# nothing recorded (CICS GENAPP's wsa*.jcl expose LGICUS01, LGIPOL01, ... as
# services). One row per assistant step:
#
#   assistant  DFHLS2WS | DFHLS2JS | DFHWS2LS | DFHJS2LS
#   direction  provider | requester
#   program    PGMNAME        uri        URI (the path under the pipeline)
#   request    REQMEM         response   RESPMEM (copybook members)
#   interface  PGMINT (COMMAREA | CHANNEL)   container  CONTID
#   binding    WSBIND         document   WSDL / JSON-SCHEMA(-REQUEST|-RESPONSE)
#   transaction TRANSACTION   line       the EXEC's line
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per JCL member, values as written (installation
#     placeholders such as `<ZFSHOME>` kept). Joining the program to its file and
#     the members to copybooks, and adding the CSD URIMAP / PIPELINE definitions,
#     is the reader's (GalaxyIR.api_surface).
#   - Program-side EXEC CICS WEB / INVOKE SERVICE / TRANSFORM are cics_resources
#     rows (#3512); api_surface joins an INVOKE to its requester step here.
#   - A value continued with a non-blank column 72 is joined to the next line.
# ==============================================================================
import re
from typing import Any

_ASSISTANTS = {"DFHLS2WS": "provider", "DFHLS2JS": "provider", "DFHWS2LS": "requester", "DFHJS2LS": "requester"}
_STEP = r"^//[A-Z0-9@#$<>]*\s+EXEC\s+(?:PROC=|PGM=)?"  # a JCL EXEC statement's head
_EXEC = re.compile(_STEP + "(" + "|".join(_ASSISTANTS) + r")\b", re.I)
_PARAM = re.compile(r"^\s*([A-Z][A-Z0-9-]{1,30})\s*=\s*(.*?)\s*$", re.I)
_FIELDS = {
    "PGMNAME": "program", "URI": "uri", "REQMEM": "request", "RESPMEM": "response", "PGMINT": "interface",
    "CONTID": "container", "WSBIND": "binding", "WSDL": "document", "JSON-SCHEMA": "document",
    "JSON-SCHEMA-REQUEST": "document", "TRANSACTION": "transaction",
}  # fmt: skip


def jcl_web_services(code_stream: str) -> list[dict[str, Any]]:
    """One row per web-services assistant step of a JCL member (see the header)."""
    if not code_stream or not re.search(r"DFH(?:LS2WS|LS2JS|WS2LS|JS2LS)", code_stream, re.I):
        return []
    lines = code_stream.split("\n")
    rows: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        m = _EXEC.match(lines[i][:72])
        if not m:
            i += 1
            continue
        name = m.group(1).upper()
        row: dict[str, Any] = {"assistant": name, "direction": _ASSISTANTS[name], "program": None, "uri": None,
                               "request": None, "response": None, "interface": None, "container": None,
                               "binding": None, "document": None, "transaction": None, "line": i + 1}  # fmt: skip
        j = i + 1
        in_data = False
        while j < len(lines):
            raw = lines[j]
            if raw.startswith("/*") or (raw.startswith("//") and (in_data or _EXEC.match(raw[:72]))):
                break
            if raw.startswith("//"):
                in_data = in_data or bool(re.search(r"\sDD\s+(?:\*|DATA)", raw[:72], re.I))
                j += 1
                continue
            if in_data:
                text = raw[:72]
                while len(raw) > 71 and raw[71] not in " " and j + 1 < len(lines):  # column-72 continuation
                    j += 1
                    raw = lines[j]
                    text = text[:71] + raw[:72].strip()
                p = _PARAM.match(text)
                if p and p.group(1).upper() in _FIELDS and row[_FIELDS[p.group(1).upper()]] is None:
                    row[_FIELDS[p.group(1).upper()]] = p.group(2).strip()
            j += 1
        rows.append(row)
        i = j
    return rows
