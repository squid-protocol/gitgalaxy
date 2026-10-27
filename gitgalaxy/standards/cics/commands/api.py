# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 spec PR 2: NAME-ONLY entries -- every other CICS application (API) command, with its IBM topic and why the
translator refuses it whole (cics_command_spec.md section 9, decision 4). No SPI / system-programming command.

IBM's "CICS command summary" (CICS TS 6.x) lists 336 API command topics: 259 command names once the device / role
variants -- SEND (3270 logical), RECEIVE (LUTYPE6.1), PUT CONTAINER (BTS) ... -- are one name. 50 of them have full
entries (with INQUIRE PROGRAM, an SPI command, the 45 of OPTIONS + LOAD / RELEASE); 9 are forms of a modelled
command that the translator reads as that command (RUN TRANSID; START ATTACH / BREXIT / CHANNEL; SEND TEXT MAPPED /
NOEDIT; the device SENDs; SEND MAP / RECEIVE MAP MAPPINGDEV), refused there by option. The other 176 are here (#4767: WEB OPEN / CONVERSE / CLOSE,
WEB PARSE URL, WEB SEND, WEB EXTRACT / RECEIVE, EXTRACT WEB / TCPIP, WEB READ / WRITE HTTPHEADER / FORMFIELD / QUERYPARM and the WEB browse forms moved to web.py).

A name-only entry becomes a full one only when the blocker ranking (cics_census.py blockers, #4587) calls for it.
The reasons the translator gave before PR 2 are kept word for word (container MOVE / browse, a parent waiting for its
child task); the named-counter commands are refused by det/cics.py with its own "named counters" message."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands.shared import ibm
from gitgalaxy.standards.cics.model import Command, Refusal

_BTS = "business transaction services (BTS processes, activities, events, timers) are not modelled"
_DTP = "distributed transaction processing (APPC / LUTYPE6.1 / MRO conversations) is not modelled"
_GDS = "generalized data stream (APPC conversations from assembler) is not modelled"
_BATCH_DATA = "batch data interchange (a 3770 / 3790 / LUTYPE4 logical unit's data sets) is not modelled"
_DEVICE = "terminal control beyond the one 3270 display the region defines is not modelled"
_STORAGE = "storage CICS acquires for the task, addressed by a pointer, is not modelled"
_JOURNAL = "journals (log streams) are not modelled"
_SECURITY = "security: the region has no security manager and no signed-on user"
COUNTER = "named counters are not modelled"  # (det/cics.py: "<verb> COUNTER: <this>")
_DOCUMENT = "DOCUMENT INSERT / SET / DELETE (bookmarks, the symbol table, deleting a document) are not modelled: only DOCUMENT CREATE and RETRIEVE are (X33)"
_WEB = "CICS web support (HTTP server / client) is not modelled"
_WEB_SERVICE = "web services (SOAP / WS-Addressing) are not modelled"
_TRANSFORM = "XML / JSON transformation (TRANSFORM) is not modelled"
_SPOOL = "the JES spool interface is not modelled"
_EVENT_WAIT = (
    "waiting on an event control block other than a POST's timer-event control area (WAIT EVENT, X63) is not modelled"
    " (one task runs at a time)"
)
_LOGICAL_MESSAGE = "a BMS logical message (ACCUM / PAGING, completed by SEND PAGE) is not modelled"
_PARTITION = "partitions / logical device codes: the region's terminal is one unpartitioned display"
_OTEL = "OpenTelemetry spans are not modelled"
_TRACE = "user trace and monitoring points are not modelled"

_INQUIRE_CONTAINER = (
    "IBM documents INQUIRE CONTAINER only for a BTS data-container (ACTIVITYID / PROCESS / PROCESSTYPE); BTS is not "
    "modelled and there is no channel form (a channel's container names come from STARTBROWSE CONTAINER, its length "
    "from GET CONTAINER NODATA FLENGTH)"
)

# (name, IBM topic after "summary-" -- None: the name's own -- reason)
_NAME_ONLY: tuple[tuple[str, str | None, str], ...] = (
    # BTS
    ("ACQUIRE", None, _BTS),
    ("ADD SUBEVENT", None, _BTS),
    ("CHECK ACQPROCESS", None, _BTS),
    ("CHECK ACTIVITY", None, _BTS),
    ("CHECK TIMER", None, _BTS),
    ("DEFINE ACTIVITY", None, _BTS),
    ("DEFINE COMPOSITE EVENT", None, _BTS),
    ("DEFINE INPUT EVENT", None, _BTS),
    ("DEFINE PROCESS", None, _BTS),
    ("DEFINE TIMER", None, _BTS),
    ("DELETE ACTIVITY", None, _BTS),
    ("DELETE EVENT", None, _BTS),
    ("DELETE TIMER", None, _BTS),
    ("ENDBROWSE ACTIVITY", None, _BTS),
    ("ENDBROWSE EVENT", None, _BTS),
    ("ENDBROWSE PROCESS", None, _BTS),
    ("ENDBROWSE TIMER", None, _BTS),
    ("FORCE TIMER", None, _BTS),
    ("GETNEXT ACTIVITY", None, _BTS),
    ("GETNEXT EVENT", None, _BTS),
    ("GETNEXT PROCESS", None, _BTS),
    ("GETNEXT TIMER", None, _BTS),
    ("INQUIRE ACTIVITYID", None, _BTS),
    # IBM documents INQUIRE CONTAINER only in its BTS form (ACTIVITYID / PROCESS / PROCESSTYPE / DATALENGTH / SET): no
    # channel or browse form (the channel browse is STARTBROWSE / GETNEXT / ENDBROWSE CONTAINER, X42) (#5005, X44)
    ("INQUIRE CONTAINER", None, _INQUIRE_CONTAINER),
    ("INQUIRE EVENT", None, _BTS),
    ("INQUIRE PROCESS", None, _BTS),
    ("INQUIRE TIMER", None, _BTS),
    ("LINK ACQPROCESS", None, _BTS),
    ("LINK ACTIVITY", None, _BTS),
    ("REMOVE SUBEVENT", None, _BTS),
    ("RESET ACQPROCESS", None, _BTS),
    ("RESET ACTIVITY", None, _BTS),
    ("RESUME", None, _BTS),
    ("RETRIEVE REATTACH EVENT", None, _BTS),
    ("RETRIEVE SUBEVENT", None, _BTS),
    ("SIGNAL EVENT", None, _BTS),
    ("STARTBROWSE ACTIVITY", None, _BTS),
    ("STARTBROWSE EVENT", None, _BTS),
    ("STARTBROWSE PROCESS", None, _BTS),
    ("STARTBROWSE TIMER", None, _BTS),
    ("TEST EVENT", None, _BTS),
    ("SUSPEND", None, "giving up control to other tasks (SUSPEND) is not modelled: one task runs at a time"),
    # distributed transaction processing
    ("ALLOCATE", "allocate-appc", _DTP),
    ("BUILD ATTACH", "build-attach-mro", _DTP),
    ("CONNECT PROCESS", None, _DTP),
    ("EXTRACT ATTACH", "extract-attach-mro", _DTP),
    ("EXTRACT ATTRIBUTES", "extract-attributes-appc", _DTP),
    ("EXTRACT PROCESS", None, _DTP),
    ("FREE", None, _DTP),
    ("ISSUE ABEND", None, _DTP),
    ("ISSUE CONFIRMATION", None, _DTP),
    ("ISSUE ERROR", None, _DTP),
    ("ISSUE PREPARE", None, _DTP),
    ("ISSUE SIGNAL", "issue-signal-appc", _DTP),
    ("WAIT CONVID", "wait-convid-appc", _DTP),
    ("GDS ALLOCATE", None, _GDS),
    ("GDS ASSIGN", None, _GDS),
    ("GDS CONNECT PROCESS", None, _GDS),
    ("GDS EXTRACT ATTRIBUTES", None, _GDS),
    ("GDS EXTRACT PROCESS", None, _GDS),
    ("GDS FREE", None, _GDS),
    ("GDS ISSUE ABEND", None, _GDS),
    ("GDS ISSUE CONFIRMATION", None, _GDS),
    ("GDS ISSUE ERROR", None, _GDS),
    ("GDS ISSUE PREPARE", None, _GDS),
    ("GDS ISSUE SIGNAL", None, _GDS),
    ("GDS RECEIVE", None, _GDS),
    ("GDS SEND", None, _GDS),
    ("GDS WAIT", None, _GDS),
    # batch data interchange and other devices
    ("ISSUE ABORT", None, _BATCH_DATA),
    ("ISSUE ADD", None, _BATCH_DATA),
    ("ISSUE END", None, _BATCH_DATA),
    ("ISSUE ERASE", None, _BATCH_DATA),
    ("ISSUE NOTE", None, _BATCH_DATA),
    ("ISSUE QUERY", None, _BATCH_DATA),
    ("ISSUE RECEIVE", None, _BATCH_DATA),
    ("ISSUE REPLACE", None, _BATCH_DATA),
    ("ISSUE SEND", None, _BATCH_DATA),
    ("ISSUE WAIT", None, _BATCH_DATA),
    ("ISSUE ENDFILE", None, _BATCH_DATA),
    ("ISSUE ENDOUTPUT", None, _BATCH_DATA),
    ("ISSUE EODS", None, _BATCH_DATA),
    ("ISSUE COPY", "issue-copy-3270-logical", _DEVICE),
    ("ISSUE DISCONNECT", "issue-disconnect-default", _DEVICE),
    ("ISSUE ERASEAUP", None, _DEVICE),
    ("ISSUE LOAD", None, _DEVICE),
    ("ISSUE PASS", None, "passing the terminal to another VTAM application is not modelled"),
    ("ISSUE PRINT", None, _DEVICE),
    ("ISSUE RESET", None, _DEVICE),
    ("POINT", None, _DEVICE),
    ("WAIT SIGNAL", None, _DEVICE),
    ("WAIT TERMINAL", None, _DEVICE),
    ("EXTRACT LOGONMSG", None, _DEVICE),
    ("EXTRACT TCT", None, _DEVICE),
    # BMS beyond SEND MAP / RECEIVE MAP / SEND TEXT / SEND CONTROL
    ("SEND PAGE", None, _LOGICAL_MESSAGE),
    ("PURGE MESSAGE", None, _LOGICAL_MESSAGE),
    ("ROUTE", None, "BMS message routing to other terminals is not modelled"),
    ("SEND PARTNSET", None, _PARTITION),
    ("RECEIVE PARTN", None, _PARTITION),
    # storage and addresses
    ("GETMAIN64", None, _STORAGE),
    ("FREEMAIN64", None, _STORAGE),
    ("ADDRESS SET", None, "setting a pointer from a data area's address (or the reverse) is not modelled"),
    # queues and files beyond the modelled ones
    ("RESETBR", None, "repositioning a browse (RESETBR) is not modelled"),
    # journals
    ("JOURNAL", None, _JOURNAL),
    ("WRITE JOURNALNAME", None, _JOURNAL),
    ("WRITE JOURNALNUM", None, _JOURNAL),
    ("WAIT JOURNALNAME", None, _JOURNAL),
    ("WAIT JOURNALNUM", None, _JOURNAL),
    # security
    ("CHANGE PASSWORD", None, _SECURITY),
    ("CHANGE PHRASE", None, _SECURITY),
    ("EXTRACT CERTIFICATE", None, _SECURITY),
    ("QUERY SECURITY", None, _SECURITY),
    ("REQUEST ENCRYPTPTKT", None, _SECURITY),
    ("REQUEST PASSTICKET", None, _SECURITY),
    ("SIGNOFF", None, _SECURITY),
    ("SIGNON", None, _SECURITY),
    ("SIGNON TOKEN", None, _SECURITY),
    ("VERIFY PASSWORD", None, _SECURITY),
    ("VERIFY PHRASE", None, _SECURITY),
    ("VERIFY TOKEN", None, _SECURITY),
    # documents
    ("DOCUMENT DELETE", None, _DOCUMENT),
    ("DOCUMENT INSERT", None, _DOCUMENT),
    ("DOCUMENT SET", None, _DOCUMENT),
    # web, web services, transformation
    ("INVOKE APPLICATION", None, "invoking an application by its operation (INVOKE APPLICATION) is not modelled"),
    ("INVOKE SERVICE", None, _WEB_SERVICE),
    ("INVOKE WEBSERVICE", None, _WEB_SERVICE),
    ("SOAPFAULT ADD", None, _WEB_SERVICE),
    ("SOAPFAULT DELETE", None, _WEB_SERVICE),
    ("WSACONTEXT BUILD", None, _WEB_SERVICE),
    ("WSACONTEXT DELETE", None, _WEB_SERVICE),
    ("WSACONTEXT GET", None, _WEB_SERVICE),
    ("WSAEPR CREATE", None, _WEB_SERVICE),
    ("TRANSFORM DATATOJSON", None, _TRANSFORM),
    ("TRANSFORM DATATOXML", None, _TRANSFORM),
    ("TRANSFORM JSONTODATA", None, _TRANSFORM),
    ("TRANSFORM XMLTODATA", None, _TRANSFORM),
    # spool
    ("SPOOLCLOSE", None, _SPOOL),
    ("SPOOLOPEN INPUT", None, _SPOOL),
    ("SPOOLOPEN OUTPUT", None, _SPOOL),
    ("SPOOLREAD", None, _SPOOL),
    ("SPOOLWRITE", None, _SPOOL),
    # event control, trace, monitoring, the rest
    ("WAIT EXTERNAL", None, _EVENT_WAIT),
    ("WAITCICS", None, _EVENT_WAIT),
    ("ENTER TRACENUM", None, _TRACE),
    ("MONITOR", None, _TRACE),
    # #4415 slice 3 (X46): the dump's outcome (SUPPRESSED by the dump table or a user exit, IOERR, NOTOPEN, a DUMPID's run
    # number) is the region's dump setup, which the run does not state; the page does not say the task continues after one
    (
        "DUMP TRANSACTION",
        None,
        "a transaction dump is not modelled: its outcome is the region's dump setup, not stated (X46)",
    ),
    ("OTEL ENDSPAN", None, _OTEL),
    ("OTEL EXTRACT", None, _OTEL),
    ("OTEL STARTSPAN", None, _OTEL),
    ("BIF DIGEST", None, "message digests (BIF DIGEST) are not modelled"),
    ("CHANGE TASK", None, "task priority is not modelled (one task runs at a time)"),
    ("CONVERTTIME", None, "converting a date and time string to ABSTIME (CONVERTTIME) is not modelled"),
)

# #4270 (X65): every other name-only command is refused with its class reason, listed in X65. #5079 (X59, X63): the
# old-style commands refused by name with a register entry citing IBM's page for each
_REGISTER = {
    "SEND PAGE": "X59",
    "PURGE MESSAGE": "X59",
    "DUMP TRANSACTION": "X46",
    "WAIT EXTERNAL": "X63",
    "WAITCICS": "X63",
}

# #5235: IBM's SOAPFAULT CREATE options (EXEC CICS SOAPFAULT CREATE), named so the spec knows every word of the command
# DBB epscsmrd issues (CLIENT, FAULTSTRING, FAULTSTRLEN); the whole command stays refused (web services, X65)
_SOAPFAULT_CREATE_OPTIONS = (
    "CLIENT",
    "SERVER",
    "SENDER",
    "RECEIVER",
    "FAULTCODE",
    "FAULTCODESTR",
    "FAULTCODELEN",
    "FAULTSTRING",
    "FAULTSTRLEN",
    "NATLANG",
    "ROLE",
    "ROLELENGTH",
    "FAULTACTOR",
    "FAULTACTLEN",
    "DETAIL",
    "DETAILLENGTH",
    "FROMCCSID",
)
_SOAPFAULT_CREATE = Command(
    key="SOAPFAULT CREATE",
    ibm=ibm("EXEC CICS SOAPFAULT CREATE", "summary-soapfault-create"),
    status="refused",
    why=_WEB_SERVICE,
    register="X65",
    refused={o: Refusal(_WEB_SERVICE, "X65", whole=True) for o in _SOAPFAULT_CREATE_OPTIONS},
)

COMMANDS = (
    _SOAPFAULT_CREATE,
    *(
        Command(
            key=name,
            ibm=ibm(f"EXEC CICS {name}", "summary-" + (topic or name.lower().replace(" ", "-"))),
            status="refused",
            why=why,
            register=_REGISTER.get(name, "X65"),
        )
        for name, topic, why in _NAME_ONLY
    ),
)
