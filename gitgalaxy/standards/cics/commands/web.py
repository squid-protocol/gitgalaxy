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
        "CHARACTERSET": Refusal("code-page conversion is not modelled: the exchange is in the program's characters", "X35"),
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
        requires(("QUERYSTRING",), ("QUERYSTRLEN",), msg="WEB CONVERSE QUERYSTRING without QUERYSTRLEN", both_ways=True),
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

COMMANDS = (WEB_OPEN, WEB_CONVERSE, WEB_CLOSE)
