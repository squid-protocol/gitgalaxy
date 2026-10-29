# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 / #4767: CICS web support as an HTTP client -- WEB OPEN, WEB CONVERSE, WEB CLOSE (register X35), the commands
zECS's ECS001 (the sample client) and ZECS000 / ZECS001 / ZECS003 (replication to the partner data center) use to talk to
another zECS over HTTP.

IBM (EXEC CICS WEB OPEN, WEB CONVERSE, WEB CLOSE): WEB OPEN opens a connection to a server named by HOST / HOSTLENGTH /
PORTNUMBER / SCHEME or by a CLIENT URIMAP and returns an 8-byte SESSTOKEN; WEB CONVERSE sends one request on it (METHOD,
PATH, QUERYSTRING, a body FROM with its MEDIATYPE) and receives the response (INTO at most MAXLENGTH bytes, TOLENGTH,
STATUSCODE, STATUSTEXT, MEDIATYPE); WEB CLOSE ends the session.

The server is not part of the region, so it is a fact whoever runs the task STATES (`http_peers`: each peer's scheme, host,
port, its CLIENT URIMAP name and path if it has one, and the responses it gives, request by request); a program that
opens a connection to a peer the run does not state, or sends a request the peer states no response to, is refused at
run time. The exchange is stated and recorded in the program's own characters: code-page conversion (CLIENTCONV and its
CVDAs) changes nothing within the model -- the stated response is what reaches the program's area -- and CHARACTERSET /
BODYCHARSET are refused. Every request the program sends is recorded (a WEB-CONVERSE event: host, method, path, query, the
media type and body when there is a body, RESP / RESP2), so a proof compares what each side sent.

WEB PARSE URL (register X36) takes a URL apart, purely; WEB SEND (register X37), the server's response, is recorded as a
WEB-SEND event on a request whoever runs the task STATES (`http_request`, a fact like the peers).

Refused by name: everything the corpus does not use (CERTIFICATE, CODEPAGE, CIPHERS, HTTPVNUM / HTTPRNUM; on CONVERSE a
URIMAP, DOCTOKEN, CONTAINER, SET, NOTRUNCATE, TOCONTAINER, ACTION, CLOSESTATUS, AUTHENTICATE ...)."""

from __future__ import annotations

from dataclasses import replace

from gitgalaxy.standards.cics.commands.shared import RESP_OPTIONS, ibm
from gitgalaxy.standards.cics.model import (
    Arg,
    Command,
    Fact,
    Outcome,
    Refusal,
    RuntimeRefusal,
    at_most_one,
    one_of,
    required,
    requires,
)

_TOKEN_OUT = Arg("area_out", width=8)
_TOKEN_IN = Arg("area_in", width=8)
_CONVERT_FLAGS = ("CLICONVERT", "NOINCONVERT", "NOOUTCONVERT", "NOCLICONVERT")

# the stated server(s): one fact both runtimes read (CicsTask.withHttpPeers, $GGCICS_HTTP)
_PEERS = Fact(
    "http_peers",
    java="withHttpPeers",
    env="GGCICS_HTTP",
    region_default=None,
    options=("SESSTOKEN",),
)
_UNSTATED = RuntimeRefusal(
    "the HTTP peers (servers and the responses they give) are not stated for the task",
    "X35",
    java="the HTTP peers are not stated (withHttpPeers)",
    c="WEB: the HTTP peers are not stated for this task",
)

WEB_OPEN = Command(
    key="WEB OPEN",
    ibm=ibm("EXEC CICS WEB OPEN", "summary-web-open"),
    status="modelled",
    register="X35",
    options={
        "SESSTOKEN": _TOKEN_OUT,
        "HOST": Arg("area_in"),
        "HOSTLENGTH": Arg("value"),
        "PORTNUMBER": Arg("value"),
        "SCHEME": Arg("cvda"),
        "URIMAP": Arg("name", width=8),
        **RESP_OPTIONS,
    },
    refused={
        "CERTIFICATE": Refusal("TLS client certificates are not modelled", "X35"),
        "CODEPAGE": Refusal("code-page conversion is not modelled: the exchange is in the program's characters", "X35"),
        "HTTPVNUM": Refusal("the server's HTTP version is not stated", "X35"),
        "HTTPRNUM": Refusal("the server's HTTP version is not stated", "X35"),
    },
    default_refusal=Refusal("only SESSTOKEN, HOST / HOSTLENGTH / PORTNUMBER / SCHEME and URIMAP are modelled", "X35"),
    groups=(
        required("SESSTOKEN", msg="WEB OPEN without SESSTOKEN"),
        one_of("URIMAP", "HOST", msg="WEB OPEN needs one of URIMAP and HOST"),
        requires(("HOST",), ("HOSTLENGTH",), msg="WEB OPEN HOST without HOSTLENGTH", both_ways=True),
        requires(("HOST",), ("SCHEME",), msg="WEB OPEN HOST without SCHEME: IBM states no default scheme"),
        requires(
            ("PORTNUMBER", "SCHEME"),
            ("HOST",),
            msg="WEB OPEN {} without HOST: with URIMAP, IBM says not to specify it",
        ),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("SESSTOKEN",)),
        Outcome("LENGERR", 21, "Incorrect host length (HOSTLENGTH not greater than zero)", raised_by=("HOSTLENGTH",)),
        Outcome("INVREQ", 40, "Scheme incorrect", raised_by=("SCHEME",)),
        Outcome("INVREQ", 138, "The port number is greater than 65535", raised_by=("PORTNUMBER",)),
    ),
    facts=(_PEERS,),
    runtime_refusals=(
        _UNSTATED,
        RuntimeRefusal(
            "a connection to a server (host, port, scheme) or a CLIENT URIMAP the run does not state",
            "X35",
            java="WEB OPEN of a peer the run does not state",
            c="WEB OPEN of a peer the run does not state",
        ),
        RuntimeRefusal(
            "a PORTNUMBER below 1: IBM gives it no condition",
            "X35",
            java="WEB OPEN PORTNUMBER below 1",
            c="WEB OPEN PORTNUMBER below 1",
        ),
        RuntimeRefusal(
            "a HOSTLENGTH past the HOST area: CICS reads the storage that follows it, which GnuCOBOL lays out unlike IBM's compiler",
            "X35",
            java="WEB OPEN HOSTLENGTH",
            c="WEB OPEN HOSTLENGTH",
        ),
    ),
    state=("handle_table",),
)

WEB_CONVERSE = Command(
    key="WEB CONVERSE",
    ibm=ibm("EXEC CICS WEB CONVERSE", "summary-web-converse"),
    status="modelled",
    register="X35",
    options={
        "SESSTOKEN": _TOKEN_IN,
        "METHOD": Arg("cvda"),
        "PATH": Arg("area_in"),
        "PATHLENGTH": Arg("value"),
        "QUERYSTRING": Arg("area_in"),
        "QUERYSTRLEN": Arg("value"),
        "FROM": Arg("area_in"),
        "FROMLENGTH": Arg("value"),
        "MEDIATYPE": Arg("area_inout", width=56),
        "INTO": Arg("area_out"),
        "MAXLENGTH": Arg("value"),
        "TOLENGTH": Arg("area_out", width=4, binary=True),
        "STATUSCODE": Arg("area_out", width=2, binary=True),
        "STATUSTEXT": Arg("area_out"),
        "STATUSLEN": Arg("value"),
        "CLIENTCONV": Arg("cvda"),
        **{f: Arg("flag") for f in _CONVERT_FLAGS},
        **RESP_OPTIONS,
    },
    refused={
        "URIMAP": Refusal("a request URIMAP on WEB CONVERSE is not modelled (no zECS program uses one)", "X35"),
        "CHARACTERSET": Refusal(
            "code-page conversion is not modelled: the exchange is in the program's characters", "X35"
        ),
        "BODYCHARSET": Refusal("the response's character set is not stated", "X35"),
        "DOCTOKEN": Refusal("a document as the request body is not modelled", "X35"),
        "CONTAINER": Refusal("a container as the request body is not modelled", "X35"),
        "SET": Refusal("a response held in CICS storage (SET) is not modelled", "X35"),
        "NOTRUNCATE": Refusal("a response kept for later RECEIVEs (NOTRUNCATE) is not modelled", "X35"),
        "TOCONTAINER": Refusal("a response into a container is not modelled", "X35"),
    },
    default_refusal=Refusal(
        "only METHOD, PATH, QUERYSTRING, FROM, MEDIATYPE, INTO / MAXLENGTH / TOLENGTH, STATUSCODE / STATUSTEXT / "
        "STATUSLEN and CLIENTCONV are modelled",
        "X35",
    ),
    groups=(
        required("SESSTOKEN", msg="WEB CONVERSE without SESSTOKEN"),
        required("METHOD", msg="WEB CONVERSE without METHOD"),
        required("INTO", msg="WEB CONVERSE without INTO: only a response into the program's area is modelled"),
        requires(("PATH",), ("PATHLENGTH",), msg="WEB CONVERSE PATH without PATHLENGTH", both_ways=True),
        requires(
            ("QUERYSTRING",), ("QUERYSTRLEN",), msg="WEB CONVERSE QUERYSTRING without QUERYSTRLEN", both_ways=True
        ),
        requires(("FROM",), ("FROMLENGTH",), msg="WEB CONVERSE FROM without FROMLENGTH", both_ways=True),
        requires(("STATUSTEXT",), ("STATUSLEN",), msg="WEB CONVERSE STATUSTEXT without STATUSLEN", both_ways=True),
        at_most_one("CLIENTCONV", *_CONVERT_FLAGS, msg="WEB CONVERSE with more than one conversion option"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "TOLENGTH", "STATUSCODE", "STATUSTEXT", "MEDIATYPE")),
        Outcome("NOTOPEN", 27, "Invalid session token", raised_by=("SESSTOKEN",)),
        Outcome("INVREQ", 33, "Method does not support a body", raised_by=("FROM",)),
        Outcome("INVREQ", 34, "Method requires a body", raised_by=("METHOD",)),
        Outcome("INVREQ", 54, "The HTTP method is not valid", raised_by=("METHOD",)),
        Outcome("INVREQ", 76, "MEDIATYPE option required (a request with a body)", raised_by=("FROM",)),
        Outcome("LENGERR", 5, "PATHLENGTH not greater than zero", raised_by=("PATHLENGTH",)),
        Outcome("LENGERR", 8, "QUERYSTRLEN not greater than zero", raised_by=("QUERYSTRLEN",)),
        Outcome("LENGERR", 16, "Invalid MAXLENGTH (less than zero)", raised_by=("MAXLENGTH",)),
        Outcome("LENGERR", 50, "FROMLENGTH not greater than zero", raised_by=("FROMLENGTH",)),
        Outcome(
            "LENGERR",
            57,
            "The response body exceeds the length specified; the remainder was discarded",
            writes=("INTO", "TOLENGTH", "STATUSCODE", "STATUSTEXT", "MEDIATYPE"),
        ),
        Outcome("LENGERR", 59, "STATUSLEN not greater than zero", raised_by=("STATUSLEN",)),
    ),
    facts=(_PEERS,),
    runtime_refusals=(
        _UNSTATED,
        RuntimeRefusal(
            "a request the stated peer gives no response to (method, path and query string)",
            "X35",
            java="WEB CONVERSE request the peer states no response to",
            c="WEB CONVERSE request the peer states no response to",
        ),
        RuntimeRefusal(
            "more than one condition at once (IBM does not order them), a METHOD of TRACE / OPTIONS, a MAXLENGTH of zero, "
            "no PATH on a session opened by HOST, a body with a blank MEDIATYPE",
            "X35",
            java="WEB CONVERSE",
            c="WEB CONVERSE",
        ),
        RuntimeRefusal(
            "a reason phrase longer than STATUSLEN (LENGERR 58: what STATUSTEXT then holds is not stated)",
            "X35",
            java="WEB CONVERSE status text longer than STATUSLEN",
            c="WEB CONVERSE status text longer than STATUSLEN",
        ),
        RuntimeRefusal(
            "a length past its area (PATHLENGTH, QUERYSTRLEN, FROMLENGTH, MAXLENGTH, STATUSLEN): CICS reads or writes the "
            "storage that follows it, which GnuCOBOL lays out unlike IBM's compiler",
            "X35",
            java="WEB CONVERSE length beyond its area",
            c="WEB CONVERSE length beyond its area",
        ),
    ),
    event="WEB-CONVERSE",
    state=("handle_table",),
)

WEB_CLOSE = Command(
    key="WEB CLOSE",
    ibm=ibm("EXEC CICS WEB CLOSE", "summary-web-close"),
    status="modelled",
    register="X35",
    options={"SESSTOKEN": _TOKEN_IN, **RESP_OPTIONS},
    groups=(required("SESSTOKEN", msg="WEB CLOSE without SESSTOKEN"),),
    outcomes=(Outcome("NORMAL", 0, ""), Outcome("NOTOPEN", 27, "Invalid session token")),
    facts=(_PEERS,),
    runtime_refusals=(_UNSTATED,),
    state=("handle_table",),
)

_PARSE_OPEN = (
    "a scheme other than HTTP / HTTPS, a URL with a user-info part, a fragment, an IPv6 host, an empty or non-numeric "
    "port, a port of 0, a lowercase hex digit in an escape, a URLLENGTH not above zero or past its area, a PATH or "
    "QUERYSTRING asked for when the URL has none, two conditions at once"
)

WEB_PARSE_URL = Command(
    key="WEB PARSE URL",
    ibm=ibm("EXEC CICS WEB PARSE URL", "summary-web-parse-url"),
    status="modelled",
    register="X36",
    options={
        "URL": Arg("area_in"),
        "URLLENGTH": Arg("value"),
        "SCHEMENAME": Arg("area_out", width=16),
        "HOST": Arg("area_out"),
        "HOSTLENGTH": Arg("area_inout", binary=True),
        "PORTNUMBER": Arg("area_out", width=4, binary=True),
        "PATH": Arg("area_out"),
        "PATHLENGTH": Arg("area_inout", binary=True),
        "QUERYSTRING": Arg("area_out"),
        "QUERYSTRLEN": Arg("area_inout", binary=True),
        **RESP_OPTIONS,
    },
    refused={
        "HOSTTYPE": Refusal(
            "an IPv6 host is refused, so the host type is always HOSTNAME or IPV4: not modelled", "X36"
        ),
    },
    default_refusal=Refusal(
        "only URL / URLLENGTH, SCHEMENAME, HOST / HOSTLENGTH, PORTNUMBER, PATH / PATHLENGTH and QUERYSTRING / "
        "QUERYSTRLEN are modelled",
        "X36",
    ),
    groups=(
        required("URL", msg="WEB PARSE URL without URL"),
        required("URLLENGTH", msg="WEB PARSE URL without URLLENGTH"),
        requires(("HOST",), ("HOSTLENGTH",), msg="WEB PARSE URL HOST without HOSTLENGTH", both_ways=True),
        requires(("PATH",), ("PATHLENGTH",), msg="WEB PARSE URL PATH without PATHLENGTH", both_ways=True),
        requires(
            ("QUERYSTRING",), ("QUERYSTRLEN",), msg="WEB PARSE URL QUERYSTRING without QUERYSTRLEN", both_ways=True
        ),
    ),
    outcomes=(
        Outcome(
            "NORMAL",
            0,
            "",
            writes=(
                "SCHEMENAME",
                "HOST",
                "HOSTLENGTH",
                "PORTNUMBER",
                "PATH",
                "PATHLENGTH",
                "QUERYSTRING",
                "QUERYSTRLEN",
            ),
        ),
        Outcome("INVREQ", 28, "Incorrect URL"),
        Outcome("INVREQ", 65, "Bad escape sequence in the URL"),
        Outcome("LENGERR", 8, "The query string is longer than QUERYSTRLEN", raised_by=("QUERYSTRLEN",)),
        Outcome("LENGERR", 29, "The host name is longer than HOSTLENGTH", raised_by=("HOSTLENGTH",)),
        Outcome("LENGERR", 30, "The path is longer than PATHLENGTH", raised_by=("PATHLENGTH",)),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "a LENGERR (a piece longer than its length option): IBM truncates but does not say what the length option "
            "then holds",
            "X36",
            java="WEB PARSE URL piece longer than its length",
            c="WEB PARSE URL piece longer than its length",
        ),
        RuntimeRefusal(_PARSE_OPEN, "X36", java="WEB PARSE URL", c="WEB PARSE URL"),
        RuntimeRefusal(
            "a length past its area (URLLENGTH, HOSTLENGTH, PATHLENGTH, QUERYSTRLEN, SCHEMENAME shorter than the scheme): "
            "CICS reads or writes the storage that follows it, which GnuCOBOL lays out unlike IBM's compiler",
            "X36",
            java="WEB PARSE URL length beyond its area",
            c="WEB PARSE URL length beyond its area",
        ),
    ),
)

_REQUEST = Fact(
    "http_request",
    java="withHttpRequest",
    env="GGCICS_WEBREQ",
    region_default=None,
    options=("FROM", "DOCTOKEN"),
)
_NO_REQUEST = RuntimeRefusal(
    "the inbound HTTP request the task serves is not stated for the task",
    "X37",
    java="the HTTP request is not stated (withHttpRequest)",
    c="the HTTP request is not stated for this task",
)

WEB_SEND = Command(
    key="WEB SEND",
    ibm=ibm("EXEC CICS WEB SEND (server)", "summary-web-send-server"),
    status="modelled",
    register="X37",
    options={
        "FROM": Arg("area_in"),
        "FROMLENGTH": Arg("value"),
        "DOCTOKEN": Arg("area_in", width=16),
        "CONTAINER": Arg("name", width=16),  # #5037: the response body is a container's data
        "CHANNEL": Arg("name", width=16),  # omitted: the current channel
        "MEDIATYPE": Arg("area_in", width=56),
        "ACTION": Arg("cvda"),
        "DOCSTATUS": Arg("cvda"),
        "STATUSCODE": Arg("value"),
        "STATUSTEXT": Arg("area_in"),
        "STATUSLEN": Arg("value"),
        "SRVCONVERT": Arg("flag"),
        "NOSRVCONVERT": Arg("flag"),
        **RESP_OPTIONS,
    },
    refused={
        "CHUNKING": Refusal(
            "a chunked response is not modelled: it is a sequence of sends (CHUNKYES ... CHUNKEND) with IBM's own error "
            "responses (AWBP abend, RESP2 77 / 89-95) and no stated rule for the body the client sees",
            "X37",
        ),
        "CHARACTERSET": Refusal(
            "code-page conversion is not modelled: the response is in the program's characters", "X37"
        ),
        "CLNTCODEPAGE": Refusal(
            "code-page conversion is not modelled: the response is in the program's characters", "X37"
        ),
        "HOSTCODEPAGE": Refusal(
            "code-page conversion is not modelled: the response is in the program's characters", "X37"
        ),
        "CLOSESTATUS": Refusal("closing the connection after the response is not modelled", "X37"),
        "LENGTH": Refusal("LENGTH is kept for upgrade only (STATUSLEN replaces it): not modelled", "X37"),
    },
    default_refusal=Refusal(
        "only FROM / FROMLENGTH, DOCTOKEN or CONTAINER / CHANNEL, MEDIATYPE, ACTION, DOCSTATUS, STATUSCODE, STATUSTEXT / STATUSLEN and "
        "SRVCONVERT / NOSRVCONVERT are modelled",
        "X37",
    ),
    groups=(
        one_of(
            "FROM",
            "DOCTOKEN",
            "CONTAINER",
            msg="WEB SEND needs exactly one of FROM, DOCTOKEN and CONTAINER: only a response body from the program's area, "
            "a document or a container is modelled (IBM does not say what two bodies mean)",
        ),
        requires(("CHANNEL",), ("CONTAINER",), msg="WEB SEND CHANNEL without CONTAINER"),
        requires(("FROM",), ("FROMLENGTH",), msg="WEB SEND FROM without FROMLENGTH"),
        requires(("FROMLENGTH",), ("FROM",), msg="WEB SEND FROMLENGTH without FROM"),
        requires(("STATUSLEN",), ("STATUSTEXT",), msg="WEB SEND STATUSLEN without STATUSTEXT"),
        requires(("DOCSTATUS",), ("DOCTOKEN",), msg="WEB SEND DOCSTATUS without DOCTOKEN"),
        at_most_one("SRVCONVERT", "NOSRVCONVERT", msg="WEB SEND with both SRVCONVERT and NOSRVCONVERT"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome(
            "NOTFND",
            1,
            "The document has not been created, or has been deleted, or the name is incorrectly specified",
            raised_by=("DOCTOKEN",),
        ),
        Outcome(
            "CONTAINERERR",
            2,
            "The container specified by the CONTAINER option could not be found",
            raised_by=("CONTAINER",),
        ),
        Outcome(
            "CHANNELERR", 2, "The channel specified by the CHANNEL option could not be found", raised_by=("CHANNEL",)
        ),
        Outcome("INVREQ", 145, "Channel was not specified, and there is no current channel", raised_by=("CONTAINER",)),
        Outcome(
            "INVREQ",
            150,
            "Conversion requested, but data to be sent is in a DATATYPE BIT container",
            raised_by=("CONTAINER",),
        ),
        Outcome("INVREQ", 11, "Action code invalid", raised_by=("ACTION",)),
        Outcome("INVREQ", 143, "The DOCSTATUS value specified is invalid", raised_by=("DOCSTATUS",)),
        Outcome("INVREQ", 72, "Status code does not support a message body", raised_by=("STATUSCODE",)),
    ),
    facts=(_REQUEST,),
    runtime_refusals=(
        _NO_REQUEST,
        RuntimeRefusal(
            "a second send after an IMMEDIATE one (IBM gives no RESP2)",
            "X37",
            java="WEB SEND after a response was sent",
            c="WEB SEND after a response was sent",
        ),
        RuntimeRefusal(
            "an IMMEDIATE send after an EVENTUAL one (IBM allows one response per task and says only that a second EVENTUAL "
            "send replaces the first)",
            "X37",
            java="WEB SEND ACTION(IMMEDIATE) after an ACTION(EVENTUAL) send",
            c="WEB SEND ACTION(IMMEDIATE) after an ACTION(EVENTUAL) send",
        ),
        RuntimeRefusal(
            "a task that ended in an abend while an EVENTUAL response was held (IBM does not say whether it is sent)",
            "X37",
            java="WEB SEND ACTION(EVENTUAL) response held when the task ended in an abend",
            c="WEB SEND ACTION(EVENTUAL) response held when the task ended in an abend",
        ),
        RuntimeRefusal(
            "a FROMLENGTH or STATUSLEN not above zero (IBM lists LENGERR 50 and INVREQ 131 for zero), a STATUSCODE outside "
            "100-599, a blank or malformed MEDIATYPE, SRVCONVERT on a media type that is not text/*, more than one "
            "condition at once",
            "X37",
            java="WEB SEND",
            c="WEB SEND",
        ),
        RuntimeRefusal(
            "a container as the response body that is empty (IBM does not say what an empty body is)",
            "X37",
            java="WEB SEND of an empty container",
            c="WEB SEND of an empty container",
        ),
        RuntimeRefusal(
            "a DATATYPE BIT container sent without conversion (non-text bytes are not compared as text)",
            "X37",
            java="WEB SEND of a DATATYPE BIT container",
            c="WEB SEND of a DATATYPE BIT container",
        ),
        RuntimeRefusal(
            "a length past its area (FROMLENGTH, STATUSLEN): CICS reads the storage that follows it, which GnuCOBOL lays out "
            "unlike IBM's compiler",
            "X37",
            java="WEB SEND length beyond its area",
            c="WEB SEND length beyond its area",
        ),
    ),
    event="WEB-SEND",
)

# ---- the server reading the request it serves (register X38) ---------------------------------------------------------
_NO_REQUEST_READ = RuntimeRefusal(
    "the inbound HTTP request the task serves is not stated for the task",
    "X38",
    java="the HTTP request is not stated (withHttpRequest)",
    c="the HTTP request is not stated for this task",
)
_NOT_BYTES = "a length past its area: CICS reads or writes the storage that follows it, which GnuCOBOL lays out unlike IBM's compiler"

WEB_EXTRACT = Command(
    key="WEB EXTRACT",
    ibm=ibm("EXEC CICS WEB EXTRACT", "summary-web-extract"),
    status="modelled",
    register="X38",
    options={
        "SCHEME": Arg("area_out", width=4, binary=True),
        "HOST": Arg("area_out"),
        "HOSTLENGTH": Arg("area_inout", binary=True),
        "HTTPMETHOD": Arg("area_out"),
        "METHODLENGTH": Arg("area_inout", binary=True),
        "HTTPVERSION": Arg("area_out"),
        "VERSIONLEN": Arg("area_inout", binary=True),
        "PATH": Arg("area_out"),
        "PATHLENGTH": Arg("area_inout", binary=True),
        "PORTNUMBER": Arg("area_out", width=4, binary=True),
        "QUERYSTRING": Arg("area_out"),
        "QUERYSTRLEN": Arg("area_inout", binary=True),
        "REQUESTTYPE": Arg("area_out", width=4, binary=True),
        **RESP_OPTIONS,
    },
    refused={
        "SESSTOKEN": Refusal("the client form (a connection's host, version and default path) is not modelled", "X38"),
        "REALM": Refusal("the client form (a 401's realm) is not modelled", "X38"),
        "REALMLEN": Refusal("the client form (a 401's realm) is not modelled", "X38"),
        "HOSTTYPE": Refusal("the address format of the host is not stated by the request", "X38"),
        "URIMAP": Refusal("the URIMAP the request matched is not stated by the request", "X38"),
    },
    default_refusal=Refusal(
        "only SCHEME, HOST / HOSTLENGTH, HTTPMETHOD / METHODLENGTH, HTTPVERSION / VERSIONLEN, PATH / PATHLENGTH, "
        "PORTNUMBER, QUERYSTRING / QUERYSTRLEN and REQUESTTYPE are modelled",
        "X38",
    ),
    groups=(
        requires(("HOST",), ("HOSTLENGTH",), msg="WEB EXTRACT HOST without HOSTLENGTH", both_ways=True),
        requires(("HTTPMETHOD",), ("METHODLENGTH",), msg="WEB EXTRACT HTTPMETHOD without METHODLENGTH", both_ways=True),
        requires(("HTTPVERSION",), ("VERSIONLEN",), msg="WEB EXTRACT HTTPVERSION without VERSIONLEN", both_ways=True),
        requires(("PATH",), ("PATHLENGTH",), msg="WEB EXTRACT PATH without PATHLENGTH", both_ways=True),
        requires(("QUERYSTRING",), ("QUERYSTRLEN",), msg="WEB EXTRACT QUERYSTRING without QUERYSTRLEN", both_ways=True),
    ),
    outcomes=(
        Outcome(
            "NORMAL",
            0,
            "",
            writes=(
                "SCHEME",
                "HOST",
                "HOSTLENGTH",
                "HTTPMETHOD",
                "METHODLENGTH",
                "HTTPVERSION",
                "VERSIONLEN",
                "PATH",
                "PATHLENGTH",
                "PORTNUMBER",
                "QUERYSTRING",
                "QUERYSTRLEN",
                "REQUESTTYPE",
            ),
        ),
        Outcome("LENGERR", 4, "The method is longer than METHODLENGTH", raised_by=("METHODLENGTH",)),
        Outcome("LENGERR", 5, "PATHLENGTH not greater than zero", raised_by=("PATHLENGTH",)),
        Outcome("LENGERR", 6, "The HTTP version is longer than VERSIONLEN", raised_by=("VERSIONLEN",)),
        Outcome("LENGERR", 7, "VERSIONLEN not greater than zero", raised_by=("VERSIONLEN",)),
        Outcome("LENGERR", 8, "The query string is longer than QUERYSTRLEN", raised_by=("QUERYSTRLEN",)),
        Outcome("LENGERR", 21, "HOSTLENGTH not greater than zero", raised_by=("HOSTLENGTH",)),
        Outcome("LENGERR", 29, "The host name is longer than HOSTLENGTH", raised_by=("HOSTLENGTH",)),
        Outcome("LENGERR", 30, "The path is longer than PATHLENGTH", raised_by=("PATHLENGTH",)),
    ),
    facts=(
        Fact("http_request", java="withHttpRequest", env="GGCICS_WEBREQ", region_default=None, options=("SCHEME",)),
    ),
    runtime_refusals=(
        _NO_REQUEST_READ,
        RuntimeRefusal(
            "a LENGERR on a piece longer than its length (IBM truncates but does not say what the length option then "
            "holds), a METHODLENGTH or QUERYSTRLEN not above zero (IBM lists no condition), more than one condition at once",
            "X38",
            java="WEB EXTRACT",
            c="WEB EXTRACT",
        ),
        RuntimeRefusal(
            _NOT_BYTES, "X38", java="WEB EXTRACT length beyond its area", c="WEB EXTRACT length beyond its area"
        ),
    ),
)

# #4972: EXTRACT WEB is IBM's "synonym of WEB EXTRACT" (summary-extract-web: the same options, the same conditions); one
# table, so one runtime call and one set of refusals. Its messages name the form the program wrote.
EXTRACT_WEB = replace(
    WEB_EXTRACT,
    key="EXTRACT WEB",
    ibm=ibm("EXEC CICS EXTRACT WEB", "summary-extract-web"),
    groups=tuple(replace(g, msg=g.msg.replace("WEB EXTRACT", "EXTRACT WEB")) for g in WEB_EXTRACT.groups),
)

_TCPIP_IPV4 = RuntimeRefusal(
    "an address that is not IPv4 dotted decimal (IPv6: CLNTADDR6NU / SRVRADDR6NU and the colon form are not modelled), "
    "CLIENTADDRNU / SERVERADDRNU of an address that does not fit a signed fullword (IBM gives the unsigned value; a COBOL "
    "fullword holds the signed one)",
    "X38",
    java="EXTRACT TCPIP address",
    c="EXTRACT TCPIP address",
)

# the stated connection: whoever runs the task STATES it (`tcpip`), as the request is (X37)
EXTRACT_TCPIP = Command(
    key="EXTRACT TCPIP",
    ibm=ibm("EXEC CICS EXTRACT TCPIP", "summary-extract-tcpip"),
    status="modelled",
    register="X38",
    options={
        "CLIENTADDR": Arg("area_out"),
        "CADDRLENGTH": Arg("area_inout", binary=True),
        "CLIENTADDRNU": Arg("area_out", width=4, binary=True),
        "CLIENTNAME": Arg("area_out"),
        "CNAMELENGTH": Arg("area_inout", binary=True),
        "CLNTIPFAMILY": Arg("area_out", width=4, binary=True),
        "SERVERADDR": Arg("area_out"),
        "SADDRLENGTH": Arg("area_inout", binary=True),
        "SERVERADDRNU": Arg("area_out", width=4, binary=True),
        "SERVERNAME": Arg("area_out"),
        "SNAMELENGTH": Arg("area_inout", binary=True),
        "SRVRIPFAMILY": Arg("area_out", width=4, binary=True),
        "PORTNUMNU": Arg("area_out", width=4, binary=True),
        "SSLTYPE": Arg("area_out", width=4, binary=True),
        **RESP_OPTIONS,
    },
    refused={
        "PORTNUMBER": Refusal("the port in character form: IBM does not say how its 5 characters are padded", "X38"),
        "CLNTADDR6NU": Refusal("an IPv6 address is not modelled", "X38"),
        "SRVRADDR6NU": Refusal("an IPv6 address is not modelled", "X38"),
        "AUTHENTICATE": Refusal("the authentication the TCPIPSERVICE asks for is not stated by the connection", "X38"),
        "TCPIPSERVICE": Refusal("the TCPIPSERVICE definition is not stated by the connection", "X38"),
        "PRIVACY": Refusal("the TCPIPSERVICE definition is not stated by the connection", "X38"),
        "MAXDATALEN": Refusal("the TCPIPSERVICE definition is not stated by the connection", "X38"),
    },
    default_refusal=Refusal(
        "only CLIENTADDR / CADDRLENGTH, CLIENTADDRNU, CLIENTNAME / CNAMELENGTH, CLNTIPFAMILY, SERVERADDR / SADDRLENGTH, "
        "SERVERADDRNU, SERVERNAME / SNAMELENGTH, SRVRIPFAMILY, PORTNUMNU and SSLTYPE are modelled",
        "X38",
    ),
    groups=(
        requires(("CADDRLENGTH",), ("CLIENTADDR",), msg="EXTRACT TCPIP CADDRLENGTH without CLIENTADDR"),
        requires(("CNAMELENGTH",), ("CLIENTNAME",), msg="EXTRACT TCPIP CNAMELENGTH without CLIENTNAME"),
        requires(("SADDRLENGTH",), ("SERVERADDR",), msg="EXTRACT TCPIP SADDRLENGTH without SERVERADDR"),
        requires(("SNAMELENGTH",), ("SERVERNAME",), msg="EXTRACT TCPIP SNAMELENGTH without SERVERNAME"),
    ),
    outcomes=(
        Outcome(
            "NORMAL",
            0,
            "",
            writes=(
                "CLIENTADDR",
                "CADDRLENGTH",
                "CLIENTADDRNU",
                "CLIENTNAME",
                "CNAMELENGTH",
                "CLNTIPFAMILY",
                "SERVERADDR",
                "SADDRLENGTH",
                "SERVERADDRNU",
                "SERVERNAME",
                "SNAMELENGTH",
                "SRVRIPFAMILY",
                "PORTNUMNU",
                "SSLTYPE",
            ),
        ),
        Outcome(
            "LENGERR",
            1,
            "CLIENTADDR, SERVERADDR, CLIENTNAME or SERVERNAME is given and its length option is missing or not above zero",
            raised_by=("CADDRLENGTH", "CNAMELENGTH", "SADDRLENGTH", "SNAMELENGTH"),
        ),
        Outcome("LENGERR", 3, "CLIENTADDR is too small for the address", raised_by=("CADDRLENGTH",)),
        Outcome("LENGERR", 4, "SERVERADDR is too small for the address", raised_by=("SADDRLENGTH",)),
        Outcome("LENGERR", 6, "CLIENTNAME is too small for the name", raised_by=("CNAMELENGTH",)),
        Outcome("LENGERR", 7, "SERVERNAME is too small for the name", raised_by=("SNAMELENGTH",)),
    ),
    facts=(
        Fact(
            "tcpip",
            java="withTcpip",
            env="GGCICS_TCPIP",
            region_default=None,
            options=("CLIENTADDR", "SERVERADDR", "PORTNUMNU", "SSLTYPE"),
        ),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "the TCP/IP connection the task was started on is not stated for the task",
            "X38",
            java="the TCP/IP connection is not stated (withTcpip)",
            c="the TCP/IP connection is not stated for this task",
        ),
        _TCPIP_IPV4,
        RuntimeRefusal(
            "a name or address longer than its length (LENGERR RESP2 3 / 4 / 6 / 7: IBM does not say what the length "
            "option or the area then holds), a SERVERNAME the connection does not state, more than one condition at once",
            "X38",
            java="EXTRACT TCPIP",
            c="EXTRACT TCPIP",
        ),
        RuntimeRefusal(
            _NOT_BYTES, "X38", java="EXTRACT TCPIP length beyond its area", c="EXTRACT TCPIP length beyond its area"
        ),
    ),
)

WEB_RECEIVE = Command(
    key="WEB RECEIVE",
    ibm=ibm("EXEC CICS WEB RECEIVE (server)", "summary-web-receive-server"),
    status="modelled",
    register="X38",
    options={
        "INTO": Arg("area_out"),
        "SET": Arg("pointer"),
        "LENGTH": Arg("area_out", width=4, binary=True),
        "MAXLENGTH": Arg("value"),
        "MEDIATYPE": Arg("area_out", width=56),
        "SRVCONVERT": Arg("flag"),
        "NOSRVCONVERT": Arg("flag"),
        **RESP_OPTIONS,
    },
    refused={
        "NOTRUNCATE": Refusal("a body kept for later RECEIVEs (NOTRUNCATE) is not modelled", "X38"),
        "TOCONTAINER": Refusal("a body into a container is not modelled", "X38"),
        "TOCHANNEL": Refusal("a body into a container is not modelled", "X38"),
        "CHARACTERSET": Refusal("code-page conversion is not modelled: the body is in the program's characters", "X38"),
        "HOSTCODEPAGE": Refusal("code-page conversion is not modelled: the body is in the program's characters", "X38"),
        "CLNTCODEPAGE": Refusal("code-page conversion is not modelled: the body is in the program's characters", "X38"),
        "SERVERCONV": Refusal("the values of SERVERCONV are not documented", "X38"),
        "BODYCHARSET": Refusal("the body's character set is not stated", "X38"),
        "TYPE": Refusal("TYPE (HTTPYES / HTTPNO) is not modelled: a stated request is always an HTTP request", "X38"),
    },
    default_refusal=Refusal(
        "only INTO / SET, LENGTH / MAXLENGTH, MEDIATYPE and SRVCONVERT / NOSRVCONVERT are modelled", "X38"
    ),
    groups=(
        one_of(
            "INTO",
            "SET",
            msg="WEB RECEIVE needs one of INTO / SET: the body into the program's area or into CICS storage",
        ),
        requires(("INTO",), ("MAXLENGTH",), msg="WEB RECEIVE INTO without MAXLENGTH (IBM: INVREQ RESP2 16)"),
        requires(("SET",), ("LENGTH",), msg="WEB RECEIVE SET without LENGTH (IBM: LENGTH must be specified with SET)"),
        at_most_one("SRVCONVERT", "NOSRVCONVERT", msg="WEB RECEIVE with both SRVCONVERT and NOSRVCONVERT"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "SET", "LENGTH", "MEDIATYPE")),
        Outcome("LENGERR", 16, "MAXLENGTH less than or equal to zero", raised_by=("MAXLENGTH",)),
        Outcome(
            "LENGERR",
            57,
            "The body exceeds the length specified and the remainder was discarded",
            writes=("INTO", "SET", "LENGTH", "MEDIATYPE"),
        ),
    ),
    facts=(
        Fact("http_request", java="withHttpRequest", env="GGCICS_WEBREQ", region_default=None, options=("INTO", "SET")),
    ),
    runtime_refusals=(
        _NO_REQUEST_READ,
        RuntimeRefusal(
            "a request with no body, a second WEB RECEIVE other than one SRVCONVERT pass after a NOSRVCONVERT one (IBM does not say what a body already received returns again; the pass returns the same body and media type, ASSUMED)",
            "X38",
            java="WEB RECEIVE",
            c="WEB RECEIVE",
        ),
        RuntimeRefusal(
            _NOT_BYTES, "X38", java="WEB RECEIVE length beyond its area", c="WEB RECEIVE length beyond its area"
        ),
        RuntimeRefusal(
            "a body longer than the limit the run states for CICS storage (X47)",
            "X47",
            java="WEB RECEIVE SET body beyond the limit",
            c="WEB RECEIVE SET body beyond the limit",
        ),
    ),
)

WEB_READ_HTTPHEADER = Command(
    key="WEB READ HTTPHEADER",
    ibm=ibm("EXEC CICS WEB READ HTTPHEADER", "summary-web-read-httpheader"),
    status="modelled",
    register="X38",
    options={
        "HTTPHEADER": Arg("area_in"),
        "NAMELENGTH": Arg("value"),
        "VALUE": Arg("area_out"),
        "VALUELENGTH": Arg("area_inout", binary=True),
        **RESP_OPTIONS,
    },
    refused={
        "SESSTOKEN": Refusal("the client form (a response's headers) is not modelled", "X38"),
    },
    default_refusal=Refusal("only HTTPHEADER / NAMELENGTH and VALUE / VALUELENGTH are modelled", "X38"),
    groups=(
        required("HTTPHEADER", msg="WEB READ HTTPHEADER without the header name"),
        required("NAMELENGTH", msg="WEB READ HTTPHEADER without NAMELENGTH"),
        required("VALUE", msg="WEB READ HTTPHEADER without VALUE"),
        required("VALUELENGTH", msg="WEB READ HTTPHEADER without VALUELENGTH"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("VALUE", "VALUELENGTH")),
        Outcome("INVREQ", 43, "No HTTP headers found"),
        Outcome("LENGERR", 1, "VALUELENGTH not greater than zero", raised_by=("VALUELENGTH",)),
        Outcome("LENGERR", 2, "The value is longer than VALUELENGTH", raised_by=("VALUELENGTH",)),
        Outcome("NOTFND", 1, "No header with the given name was found"),
    ),
    facts=(
        Fact("http_request", java="withHttpRequest", env="GGCICS_WEBREQ", region_default=None, options=("HTTPHEADER",)),
    ),
    runtime_refusals=(
        _NO_REQUEST_READ,
        RuntimeRefusal(
            "a header found only when the names are compared without case, two headers of the same name, a NAMELENGTH "
            "not above zero (IBM lists the condition for a client only), a value longer than VALUELENGTH (LENGERR 2: "
            "what VALUELENGTH then holds is not stated), more than one condition at once",
            "X38",
            java="WEB READ HTTPHEADER",
            c="WEB READ HTTPHEADER",
        ),
        RuntimeRefusal(
            _NOT_BYTES,
            "X38",
            java="WEB READ HTTPHEADER length beyond its area",
            c="WEB READ HTTPHEADER length beyond its area",
        ),
    ),
)

WEB_WRITE_HTTPHEADER = Command(
    key="WEB WRITE HTTPHEADER",
    ibm=ibm("EXEC CICS WEB WRITE HTTPHEADER", "summary-web-write-httpheader"),
    status="modelled",
    register="X38",
    options={
        "HTTPHEADER": Arg("area_in"),
        "NAMELENGTH": Arg("value"),
        "VALUE": Arg("area_in"),
        "VALUELENGTH": Arg("value"),
        **RESP_OPTIONS,
    },
    refused={
        "SESSTOKEN": Refusal("the client form (a request's headers) is not modelled", "X38"),
    },
    default_refusal=Refusal("only HTTPHEADER / NAMELENGTH and VALUE / VALUELENGTH are modelled", "X38"),
    groups=(
        required("HTTPHEADER", msg="WEB WRITE HTTPHEADER without the header name"),
        required("NAMELENGTH", msg="WEB WRITE HTTPHEADER without NAMELENGTH"),
        required("VALUE", msg="WEB WRITE HTTPHEADER without VALUE"),
        required("VALUELENGTH", msg="WEB WRITE HTTPHEADER without VALUELENGTH"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("LENGERR", 35, "NAMELENGTH not greater than zero", raised_by=("NAMELENGTH",)),
        Outcome("LENGERR", 55, "VALUELENGTH not greater than zero or greater than 32000", raised_by=("VALUELENGTH",)),
    ),
    facts=(
        Fact("http_request", java="withHttpRequest", env="GGCICS_WEBREQ", region_default=None, options=("HTTPHEADER",)),
    ),
    runtime_refusals=(
        _NO_REQUEST_READ,
        RuntimeRefusal(
            "a header written after the response was sent, a name that is blank or holds a blank or a colon, more than one "
            "condition at once",
            "X38",
            java="WEB WRITE HTTPHEADER",
            c="WEB WRITE HTTPHEADER",
        ),
        RuntimeRefusal(
            _NOT_BYTES,
            "X38",
            java="WEB WRITE HTTPHEADER length beyond its area",
            c="WEB WRITE HTTPHEADER length beyond its area",
        ),
    ),
    event="WEB-HEADER",
)

WEB_RETRIEVE = Command(
    key="WEB RETRIEVE",
    ibm=ibm("EXEC CICS WEB RETRIEVE", "summary-web-retrieve"),
    status="modelled",
    register="X41",
    options={"DOCTOKEN": Arg("area_out", width=16), **RESP_OPTIONS},
    default_refusal=Refusal("DOCTOKEN is the only option IBM lists", "X41"),
    groups=(required("DOCTOKEN", msg="WEB RETRIEVE without DOCTOKEN"),),
    outcomes=(
        # (IBM's NORMAL: the last WEB SEND was an ACTION(EVENTUAL) document send that was not DOCDELETE, X37)
        Outcome("NORMAL", 0, "", writes=("DOCTOKEN",)),
        Outcome("INVREQ", 2, "No WEB SEND command has been issued"),
        Outcome(
            "NOTFND",
            1,
            "The document is not available: the last WEB SEND was DOCDELETE, or not a document send with ACTION(EVENTUAL)",
        ),
    ),
    facts=(
        Fact("http_request", java="withHttpRequest", env="GGCICS_WEBREQ", region_default=None, options=("DOCTOKEN",)),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "the inbound HTTP request the task serves is not stated for the task (IBM's INVREQ RESP2 1, a task that is not "
            "CICS web support, cannot be told from an unstated request)",
            "X41",
            java="the HTTP request is not stated (withHttpRequest)",
            c="the HTTP request is not stated for this task",
        ),
        RuntimeRefusal(
            "a WEB RETRIEVE after a WEB SEND that ended in a condition (IBM does not say whether that send was issued)",
            "X41",
            java="WEB RETRIEVE after a WEB SEND that ended in a condition",
            c="WEB RETRIEVE after a WEB SEND that ended in a condition",
        ),
    ),
)

# #4940 (register X38): WEB READ FORMFIELD / QUERYPARM and the WEB browse forms (STARTBROWSE / READNEXT / ENDBROWSE of
# HTTPHEADER, FORMFIELD, QUERYPARM) over the same stated `http_request`. FORMFIELD reads the name=value pairs of the
# request body (an application/x-www-form-urlencoded form), QUERYPARM those of the query string, HTTPHEADER the headers.
_CODEPAGE = Refusal("code-page conversion is not modelled: the data is in the program's characters", "X38")
_DATA_FORM = (
    "data that is not plain escaped NAME=VALUE pairs joined by '&' (a pair without '=' or with an empty name, a ';' "
    "or '+' (IBM does not say what they mean), an escape that is not %XX, an escaped name, a byte outside the printable "
    "ASCII characters): IBM does not say where the data is invalid (INVREQ RESP2 17 / 6) or how such a pair reads"
)
_FORM_BODY = (
    "a form body whose media type is not application/x-www-form-urlencoded (IBM does not say how the form type is "
    "told: LENGERR RESP2 153 / 154)"
)
_TWO_CONDITIONS = "more than one condition at once"


def _read_param(kind: str, topic: str) -> Command:
    return Command(
        key=f"WEB READ {kind}",
        ibm=ibm(f"EXEC CICS WEB READ {kind}", topic),
        status="modelled",
        register="X38",
        options={
            kind: Arg("area_in"),
            "NAMELENGTH": Arg("value"),
            "VALUE": Arg("area_out"),
            "VALUELENGTH": Arg("area_inout", binary=True),
            **RESP_OPTIONS,
        },
        refused={
            "SET": Refusal("a value in CICS storage (SET) needs the pointer lane, which is not modelled", "X38"),
            "HOSTCODEPAGE": _CODEPAGE,
            "CHARACTERSET": _CODEPAGE,
            "CLNTCODEPAGE": _CODEPAGE,
        },
        default_refusal=Refusal(f"only {kind} / NAMELENGTH and VALUE / VALUELENGTH are modelled", "X38"),
        groups=(
            required(kind, msg=f"WEB READ {kind} without the name"),
            required("NAMELENGTH", msg=f"WEB READ {kind} without NAMELENGTH"),
            required("VALUE", msg=f"WEB READ {kind} without VALUE"),
            required("VALUELENGTH", msg=f"WEB READ {kind} without VALUELENGTH"),
        ),
        outcomes=(
            Outcome("NORMAL", 0, "", writes=("VALUE", "VALUELENGTH")),
            Outcome(
                "INVREQ",
                13,
                "The HTTP request contains no forms data"
                if kind == "FORMFIELD"
                else "No keyword parameters were supplied",
            ),
            Outcome(
                "LENGERR", 1, "NAMELENGTH or VALUELENGTH not greater than zero", raised_by=("NAMELENGTH", "VALUELENGTH")
            ),
            Outcome(
                "LENGERR",
                5,
                "The value was truncated because the receiving buffer is too small (VALUELENGTH returns the real length)",
                writes=("VALUE", "VALUELENGTH"),
                raised_by=("VALUELENGTH",),
            ),
            Outcome("NOTFND", 1, "No such name was found", raised_by=(kind,)),
        ),
        facts=(
            Fact("http_request", java="withHttpRequest", env="GGCICS_WEBREQ", region_default=None, options=(kind,)),
        ),
        runtime_refusals=(
            _NO_REQUEST_READ,
            RuntimeRefusal(
                f"{_DATA_FORM}; two pairs of the name (IBM does not say how duplicates read); {_TWO_CONDITIONS}"
                + (f"; {_FORM_BODY}" if kind == "FORMFIELD" else ""),
                "X38",
                java=f"WEB {kind}" if kind == "FORMFIELD" else f"WEB READ {kind}",
                c=f"WEB {kind}" if kind == "FORMFIELD" else f"WEB READ {kind}",
            ),
            RuntimeRefusal(
                _NOT_BYTES,
                "X38",
                java=f"WEB READ {kind} length beyond its area",
                c=f"WEB READ {kind} length beyond its area",
            ),
        ),
    )


def _browse(kind: str, form: str, topic: str) -> Command:
    header = kind == "HTTPHEADER"
    named = not header
    if form == "STARTBROWSE":
        options = {kind: Arg("area_in")} if named else {kind: Arg("flag")}
        if named:
            options["NAMELENGTH"] = Arg("value")
        outcomes = [
            Outcome("NORMAL", 0, ""),
            Outcome("ILLOGIC", 10 if header else 5, f"A {kind} browse is already in progress"),
            Outcome(
                "INVREQ",
                43 if header else 13,
                "No HTTP headers were found" if header else "No forms data / keyword parameters",
            ),
        ]
        if named:
            outcomes += [
                Outcome("LENGERR", 1, "NAMELENGTH not greater than zero", raised_by=("NAMELENGTH",)),
                Outcome("NOTFND", 1, "The name was not found", raised_by=(kind,)),
            ]
        groups: tuple = ()
    elif form == "READNEXT":
        options = {
            kind: Arg("area_out"),
            "NAMELENGTH": Arg("area_inout", binary=True),
            "VALUE": Arg("area_out"),
            "VALUELENGTH": Arg("area_inout", binary=True),
        }
        outcomes = [
            Outcome("NORMAL", 0, "", writes=(kind, "NAMELENGTH", "VALUE", "VALUELENGTH")),
            Outcome("INVREQ", 4, "Issued before WEB STARTBROWSE"),
            Outcome("ENDFILE", None, "All the pairs have been read"),
            Outcome(
                "LENGERR", 1, "NAMELENGTH or VALUELENGTH is zero or negative", raised_by=("NAMELENGTH", "VALUELENGTH")
            ),
        ]
        if not header:  # (a header truncated: refused, below)
            outcomes += [
                Outcome(
                    "LENGERR",
                    4,
                    "The name was truncated; the same pair is returned again",
                    writes=(kind, "NAMELENGTH", "VALUE", "VALUELENGTH"),
                    raised_by=("NAMELENGTH",),
                ),
                Outcome(
                    "LENGERR",
                    5,
                    "The value was truncated; the same pair is returned again",
                    writes=(kind, "NAMELENGTH", "VALUE", "VALUELENGTH"),
                    raised_by=("VALUELENGTH",),
                ),
            ]
        groups = tuple(
            required(o, msg=f"WEB READNEXT {kind} without {o}") for o in (kind, "NAMELENGTH", "VALUE", "VALUELENGTH")
        )
    else:
        options = {kind: Arg("flag")}
        outcomes = [Outcome("NORMAL", 0, ""), Outcome("INVREQ", 4, "Issued before WEB STARTBROWSE")]
        groups = ()
    refused = {"SESSTOKEN": Refusal("the client form (a response's headers) is not modelled", "X38")} if header else {}
    if not header and form == "STARTBROWSE":
        refused = {"HOSTCODEPAGE": _CODEPAGE, "CHARACTERSET": _CODEPAGE, "CLNTCODEPAGE": _CODEPAGE}
    refusals = [_NO_REQUEST_READ]
    key = f"WEB {form} {kind}"
    if form == "STARTBROWSE" and named:
        refusals.append(
            RuntimeRefusal(
                f"a name found only when the names are compared without case, two pairs of the name (IBM does not say how "
                f"duplicates or case read), {_DATA_FORM}, {_TWO_CONDITIONS}"
                + (f"; {_FORM_BODY}" if kind == "FORMFIELD" else ""),
                "X38",
                java=key,
                c=key,
            )
        )
        refusals.append(
            RuntimeRefusal(_NOT_BYTES, "X38", java=f"{key} length beyond its area", c=f"{key} length beyond its area")
        )
    elif form == "STARTBROWSE":
        refusals.append(RuntimeRefusal(_TWO_CONDITIONS, "X38", java=key, c=key))
    elif form == "READNEXT":
        refusals.append(
            RuntimeRefusal(
                "a READNEXT after ENDFILE (IBM does not say what it returns), a name and a value both truncated (which "
                f"RESP2), {_TWO_CONDITIONS}"
                + (
                    "; a truncated header (IBM does not say what the lengths hold or whether the browse moves on)"
                    if header
                    else f"; {_DATA_FORM}" + (f"; {_FORM_BODY}" if kind == "FORMFIELD" else "")
                ),
                "X38",
                java=key,
                c=key,
            )
        )
        refusals.append(
            RuntimeRefusal(_NOT_BYTES, "X38", java=f"{key} length beyond its area", c=f"{key} length beyond its area")
        )
    return Command(
        key=key,
        ibm=ibm(f"EXEC CICS WEB {form} {kind}", topic),
        status="modelled",
        register="X38",
        options={**options, **RESP_OPTIONS},
        refused=refused,
        default_refusal=Refusal(
            "only the name / value options are modelled" if form != "ENDBROWSE" else "ENDBROWSE takes no option", "X38"
        ),
        groups=groups,
        outcomes=tuple(outcomes),
        facts=(
            Fact("http_request", java="withHttpRequest", env="GGCICS_WEBREQ", region_default=None, options=(kind,)),
        ),
        runtime_refusals=tuple(refusals),
    )


WEB_READ_FORMFIELD = _read_param("FORMFIELD", "summary-web-read-formfield")
WEB_READ_QUERYPARM = _read_param("QUERYPARM", "summary-web-read-queryparm")
WEB_BROWSE = tuple(
    _browse(kind, form, f"summary-web-{form.lower()}-{kind.lower()}")
    for kind in ("HTTPHEADER", "FORMFIELD", "QUERYPARM")
    for form in ("STARTBROWSE", "READNEXT", "ENDBROWSE")
)

COMMANDS = (
    WEB_OPEN,
    WEB_CONVERSE,
    WEB_CLOSE,
    WEB_PARSE_URL,
    WEB_SEND,
    WEB_EXTRACT,
    EXTRACT_WEB,
    EXTRACT_TCPIP,
    WEB_RECEIVE,
    WEB_READ_HTTPHEADER,
    WEB_WRITE_HTTPHEADER,
    WEB_RETRIEVE,
    WEB_READ_FORMFIELD,
    WEB_READ_QUERYPARM,
    *WEB_BROWSE,
)
