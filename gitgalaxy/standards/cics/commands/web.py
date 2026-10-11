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
    options=("FROM",),
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
        "MEDIATYPE": Arg("area_in", width=56),
        "ACTION": Arg("cvda"),
        "STATUSCODE": Arg("value"),
        "STATUSTEXT": Arg("area_in"),
        "STATUSLEN": Arg("value"),
        "SRVCONVERT": Arg("flag"),
        "NOSRVCONVERT": Arg("flag"),
        **RESP_OPTIONS,
    },
    refused={
        "DOCTOKEN": Refusal("a document as the response body is not modelled", "X37"),
        "CONTAINER": Refusal("a container as the response body is not modelled", "X37"),
        "CHANNEL": Refusal("a container as the response body is not modelled", "X37"),
        "CHUNKING": Refusal("a chunked response is not modelled", "X37"),
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
        "DOCSTATUS": Refusal("a document as the response body is not modelled", "X37"),
        "LENGTH": Refusal("LENGTH is kept for upgrade only (STATUSLEN replaces it): not modelled", "X37"),
    },
    default_refusal=Refusal(
        "only FROM / FROMLENGTH, MEDIATYPE, ACTION, STATUSCODE, STATUSTEXT / STATUSLEN and SRVCONVERT / NOSRVCONVERT are "
        "modelled",
        "X37",
    ),
    groups=(
        required("FROM", msg="WEB SEND without FROM: only a response body from the program's area is modelled"),
        requires(("FROM",), ("FROMLENGTH",), msg="WEB SEND FROM without FROMLENGTH", both_ways=True),
        requires(("STATUSLEN",), ("STATUSTEXT",), msg="WEB SEND STATUSLEN without STATUSTEXT"),
        at_most_one("SRVCONVERT", "NOSRVCONVERT", msg="WEB SEND with both SRVCONVERT and NOSRVCONVERT"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("INVREQ", 11, "Action code invalid", raised_by=("ACTION",)),
        Outcome("INVREQ", 72, "Status code does not support a message body", raised_by=("STATUSCODE",)),
    ),
    facts=(_REQUEST,),
    runtime_refusals=(
        _NO_REQUEST,
        RuntimeRefusal(
            "an ACTION other than IMMEDIATE (EVENTUAL, and the default, send at the end of the task and a later send "
            "replaces them), a second send after IMMEDIATE (IBM gives no RESP2)",
            "X37",
            java="WEB SEND ACTION not IMMEDIATE",
            c="WEB SEND ACTION not IMMEDIATE",
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

WEB_RECEIVE = Command(
    key="WEB RECEIVE",
    ibm=ibm("EXEC CICS WEB RECEIVE (server)", "summary-web-receive-server"),
    status="modelled",
    register="X38",
    options={
        "INTO": Arg("area_out"),
        "LENGTH": Arg("area_out", width=4, binary=True),
        "MAXLENGTH": Arg("value"),
        "MEDIATYPE": Arg("area_out", width=56),
        "SRVCONVERT": Arg("flag"),
        "NOSRVCONVERT": Arg("flag"),
        **RESP_OPTIONS,
    },
    refused={
        "SET": Refusal(
            "a body in CICS storage (SET) needs the pointer lane (GETMAIN, SET ADDRESS OF), which is not modelled",
            "X38",
        ),
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
        "only INTO / LENGTH / MAXLENGTH, MEDIATYPE and SRVCONVERT / NOSRVCONVERT are modelled", "X38"
    ),
    groups=(
        required("INTO", msg="WEB RECEIVE without INTO: only a body into the program's area is modelled"),
        requires(("INTO",), ("MAXLENGTH",), msg="WEB RECEIVE INTO without MAXLENGTH (IBM: INVREQ RESP2 16)"),
        at_most_one("SRVCONVERT", "NOSRVCONVERT", msg="WEB RECEIVE with both SRVCONVERT and NOSRVCONVERT"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "LENGTH", "MEDIATYPE")),
        Outcome("LENGERR", 16, "MAXLENGTH less than or equal to zero", raised_by=("MAXLENGTH",)),
        Outcome(
            "LENGERR",
            57,
            "The body exceeds the length specified and the remainder was discarded",
            writes=("INTO", "LENGTH", "MEDIATYPE"),
        ),
    ),
    facts=(Fact("http_request", java="withHttpRequest", env="GGCICS_WEBREQ", region_default=None, options=("INTO",)),),
    runtime_refusals=(
        _NO_REQUEST_READ,
        RuntimeRefusal(
            "a request with no body, a second WEB RECEIVE (IBM does not say what a body already received returns again)",
            "X38",
            java="WEB RECEIVE",
            c="WEB RECEIVE",
        ),
        RuntimeRefusal(
            _NOT_BYTES, "X38", java="WEB RECEIVE length beyond its area", c="WEB RECEIVE length beyond its area"
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

COMMANDS = (
    WEB_OPEN,
    WEB_CONVERSE,
    WEB_CLOSE,
    WEB_PARSE_URL,
    WEB_SEND,
    WEB_EXTRACT,
    WEB_RECEIVE,
    WEB_READ_HTTPHEADER,
    WEB_WRITE_HTTPHEADER,
)
