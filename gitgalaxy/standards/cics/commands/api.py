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
variants -- SEND (3270 logical), RECEIVE (LUTYPE6.1), PUT CONTAINER (BTS) ... -- are one name. 46 of them have full
entries (with INQUIRE PROGRAM, an SPI command, the 45 of OPTIONS + LOAD / RELEASE); 9 are forms of a modelled
command that the translator reads as that command (RUN TRANSID; START ATTACH / BREXIT / CHANNEL; SEND TEXT MAPPED /
NOEDIT; the device SENDs; SEND MAP / RECEIVE MAP MAPPINGDEV), refused there by option. The other 203 are here.

A name-only entry becomes a full one only when the blocker ranking (cics_census.py blockers, #4587) calls for it.
The reasons the translator gave before PR 2 are kept word for word (container MOVE / browse, a parent waiting for its
child task); the named-counter commands are refused by det/cics.py with its own "named counters" message."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands.shared import ibm
from gitgalaxy.standards.cics.model import Command

# the whole-command reasons det/cics.py gave before PR 2, word for word
CONTAINER_LATER = "#4270: container MOVE / browse, a later slice"
CHILD_LATER = "#4270: a parent waiting for its child task, a later slice"

_BTS = "business transaction services (BTS processes, activities, events, timers) are not modelled"
_DTP = "distributed transaction processing (APPC / LUTYPE6.1 / MRO conversations) is not modelled"
_GDS = "generalized data stream (APPC conversations from assembler) is not modelled"
_BATCH_DATA = "batch data interchange (a 3770 / 3790 / LUTYPE4 logical unit's data sets) is not modelled"
_DEVICE = "terminal control beyond the one 3270 display the region defines is not modelled"
_STORAGE = "storage CICS acquires for the task, addressed by a pointer, is not modelled"
_JOURNAL = "journals (log streams) are not modelled"
_SECURITY = "security: the region has no security manager and no signed-on user"
COUNTER = "named counters are not modelled"  # (det/cics.py: "<verb> COUNTER: <this>")
_DOCUMENT = "CICS documents (the document handler) are not modelled"
_WEB = "CICS web support (HTTP server / client) is not modelled"
_WEB_SERVICE = "web services (SOAP / WS-Addressing) are not modelled"
_TRANSFORM = "XML / JSON transformation (TRANSFORM) is not modelled"
_SPOOL = "the JES spool interface is not modelled"
_EVENT_WAIT = "event control blocks and waiting on them are not modelled (one task runs at a time)"
_LOGICAL_MESSAGE = "a BMS logical message (ACCUM / PAGING, completed by SEND PAGE) is not modelled"
_PARTITION = "partitions / logical device codes: the region's terminal is one unpartitioned display"
_OTEL = "OpenTelemetry spans are not modelled"
_TRACE = "user trace and monitoring points are not modelled"

# (name, IBM topic after "summary-" -- None: the name's own -- reason)
_NAME_ONLY: tuple[tuple[str, str | None, str], ...] = (
    # channels and containers beyond PUT / GET / DELETE CONTAINER (#4270 slice 1)
    ("MOVE CONTAINER", "move-container-channel", CONTAINER_LATER),
    ("STARTBROWSE CONTAINER", "startbrowse-container-channel", CONTAINER_LATER),
    ("GETNEXT CONTAINER", "getnext-container-channel", CONTAINER_LATER),
    ("ENDBROWSE CONTAINER", "endbrowse-container-channel", CONTAINER_LATER),
    ("DELETE CHANNEL", None, "deleting a channel is not modelled"),
    ("QUERY CHANNEL", None, "QUERY CHANNEL (a channel's container count) is not modelled"),
    ("GET64 CONTAINER", None, "64-bit storage is not modelled"),
    ("PUT64 CONTAINER", None, "64-bit storage is not modelled"),
    # child tasks (#4270 slice 2: RUN TRANSID)
    ("FETCH CHILD", None, CHILD_LATER),
    ("FETCH ANY", None, CHILD_LATER),
    ("FREE CHILD", None, CHILD_LATER),
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
    ("INQUIRE CONTAINER", None, _BTS),
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
    ("CONVERSE", "converse-default", "CONVERSE (send, then receive, on a terminal or a conversation) is not modelled"),
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
    ("GETMAIN", None, _STORAGE),
    ("GETMAIN64", None, _STORAGE),
    ("FREEMAIN", None, _STORAGE),
    ("FREEMAIN64", None, _STORAGE),
    (
        "ADDRESS",
        None,
        "the addresses of CICS areas (EIB, COMMAREA, CWA, TWA, TCTUA) set into pointers are not modelled",
    ),
    ("ADDRESS SET", None, "setting a pointer from a data area's address (or the reverse) is not modelled"),
    # queues and files beyond the modelled ones
    ("READQ TD", None, "reading a transient-data queue is not modelled (only WRITEQ TD)"),
    ("DELETEQ TD", None, "deleting a transient-data queue is not modelled"),
    ("RESETBR", None, "repositioning a browse (RESETBR) is not modelled"),
    ("UNLOCK", None, "releasing a record's update lock (UNLOCK) is not modelled"),
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
    # named counters other than GET COUNTER
    ("DEFINE COUNTER", "define-counter-define-dcounter", COUNTER),
    ("DELETE COUNTER", "delete-counter-delete-dcounter", COUNTER),
    ("REWIND COUNTER", "rewind-counter-rewind-dcounter", COUNTER),
    ("UPDATE COUNTER", "update-counter-update-dcounter", COUNTER),
    # documents
    ("DOCUMENT CREATE", None, _DOCUMENT),
    ("DOCUMENT DELETE", None, _DOCUMENT),
    ("DOCUMENT INSERT", None, _DOCUMENT),
    ("DOCUMENT RETRIEVE", None, _DOCUMENT),
    ("DOCUMENT SET", None, _DOCUMENT),
    # web, web services, transformation
    ("WEB CLOSE", None, _WEB),
    ("WEB CONVERSE", None, _WEB),
    ("WEB ENDBROWSE FORMFIELD", None, _WEB),
    ("WEB ENDBROWSE HTTPHEADER", None, _WEB),
    ("WEB ENDBROWSE QUERYPARM", None, _WEB),
    ("WEB EXTRACT", None, _WEB),
    ("WEB OPEN", None, _WEB),
    ("WEB PARSE URL", None, _WEB),
    ("WEB READ FORMFIELD", None, _WEB),
    ("WEB READ HTTPHEADER", None, _WEB),
    ("WEB READ QUERYPARM", None, _WEB),
    ("WEB READNEXT FORMFIELD", None, _WEB),
    ("WEB READNEXT HTTPHEADER", None, _WEB),
    ("WEB READNEXT QUERYPARM", None, _WEB),
    ("WEB RECEIVE", "web-receive-server", _WEB),
    ("WEB RETRIEVE", None, _WEB),
    ("WEB SEND", "web-send-server", _WEB),
    ("WEB STARTBROWSE FORMFIELD", None, _WEB),
    ("WEB STARTBROWSE HTTPHEADER", None, _WEB),
    ("WEB STARTBROWSE QUERYPARM", None, _WEB),
    ("WEB WRITE HTTPHEADER", None, _WEB),
    ("EXTRACT WEB", None, _WEB),
    ("EXTRACT TCPIP", None, _WEB),
    ("INVOKE APPLICATION", None, "invoking an application by its operation (INVOKE APPLICATION) is not modelled"),
    ("INVOKE SERVICE", None, _WEB_SERVICE),
    ("INVOKE WEBSERVICE", None, _WEB_SERVICE),
    ("SOAPFAULT ADD", None, _WEB_SERVICE),
    ("SOAPFAULT CREATE", None, _WEB_SERVICE),
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
    ("POST", None, _EVENT_WAIT),
    ("WAIT EVENT", None, _EVENT_WAIT),
    ("WAIT EXTERNAL", None, _EVENT_WAIT),
    ("WAITCICS", None, _EVENT_WAIT),
    ("ENTER TRACENUM", None, _TRACE),
    ("MONITOR", None, _TRACE),
    ("WRITE OPERATOR", None, "a message to the system console (WRITE OPERATOR) is not modelled"),
    ("DUMP TRANSACTION", None, "a transaction dump is not modelled"),
    ("OTEL ENDSPAN", None, _OTEL),
    ("OTEL EXTRACT", None, _OTEL),
    ("OTEL STARTSPAN", None, _OTEL),
    ("BIF DIGEST", None, "message digests (BIF DIGEST) are not modelled"),
    ("CHANGE TASK", None, "task priority is not modelled (one task runs at a time)"),
    ("CONVERTTIME", None, "converting a date and time string to ABSTIME (CONVERTTIME) is not modelled"),
)

COMMANDS = tuple(
    Command(
        key=name,
        ibm=ibm(f"EXEC CICS {name}", "summary-" + (topic or name.lower().replace(" ", "-"))),
        status="refused",
        why=why,
    )
    for name, topic, why in _NAME_ONLY
)
