# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 slice 1 (#4575): PUT / GET / DELETE CONTAINER (CHANNEL), register X17; #4951: MOVE CONTAINER and the container
browse (STARTBROWSE / GETNEXT / ENDBROWSE CONTAINER), register X42; #5005: DELETE CHANNEL and QUERY CHANNEL, register
X44."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands.shared import CODEPAGE, NEEDS_ARGUMENT, POINTER, RESP_OPTIONS, ibm
from gitgalaxy.standards.cics.model import (
    Arg,
    Command,
    EngineFacts,
    Impl,
    Outcome,
    Refusal,
    RuntimeRefusal,
    at_most_one,
    one_of,
    required,
)

_NAME = Arg("name", width=16)  # "the name (1 - 16 characters)"

# what every container command refuses while running: a channel an XCTL left behind, an illegal name
_SCOPE = RuntimeRefusal(
    "a channel an XCTL left behind: IBM's scope tables do not say",
    "X17",
    java=" after an XCTL that did not pass it: its scope ",
    c="channel %s after an XCTL that did not pass it",
)
_ILLEGAL_NAME = RuntimeRefusal(
    "a channel / container name that is blank or has an embedded blank (IBM's illegal-character rules)",
    "X17",
    java=" name '\" + name + \"': not modelled",
    c="%s name '%s'",
)
_CONTAINER_IMPL = {"translator": "Cics.container", "harness": "_container_command"}

PUT_CONTAINER = Command(
    key="PUT CONTAINER",
    ibm=ibm("EXEC CICS PUT CONTAINER (CHANNEL)", "summary-put-container-channel"),
    status="modelled",
    register="X17",
    options={
        "CONTAINER": _NAME,
        "CHANNEL": _NAME,  # omitted: the current channel
        "FROM": Arg("area_in"),
        "FLENGTH": Arg("value"),  # omitted: FROM's length
        "BIT": Arg("flag"),
        "CHAR": Arg("flag"),  # in the region's CCSID both ways: never converted
        "DATATYPE": Arg("cvda"),  # DFHVALUE(BIT | CHAR) only
        "APPEND": Arg("flag"),
        **RESP_OPTIONS,
    },
    refused={
        "FROMCCSID": CODEPAGE,
        "FROMCODEPAGE": CODEPAGE,
        "PREPEND": Refusal("not modelled (no corpus program uses it)", "X17"),
    },
    groups=(
        required("CONTAINER", msg=NEEDS_ARGUMENT),
        required("FROM", msg=NEEDS_ARGUMENT),
        at_most_one("BIT", "CHAR", "DATATYPE", msg="PUT CONTAINER {}: one data type"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("INVREQ", 4, "no CHANNEL and no current channel"),
        Outcome("INVREQ", 1, "no CHANNEL and no current channel, with a data type named"),
        Outcome("LENGERR", 1, "FLENGTH below zero"),
    ),
    runtime_refusals=(
        _SCOPE,
        _ILLEGAL_NAME,
        RuntimeRefusal(
            "a data type named for an existing container of the other type: ignored, or INVREQ RESP2 33?",
            "X17",
            java=" on an existing container of the other ",
            c="PUT CONTAINER changing an existing container's data type",
        ),
        RuntimeRefusal("an FLENGTH past FROM's end", "X17", java="PUT CONTAINER FLENGTH "),
    ),
    state=("channel_scope", "handle_table"),
    engine=EngineFacts(resource="CONTAINER", access="write"),
    impl=Impl(java="putContainer", c="GGCPUTC", **_CONTAINER_IMPL),
)

GET_CONTAINER = Command(
    key="GET CONTAINER",
    ibm=ibm("EXEC CICS GET CONTAINER (CHANNEL)", "summary-get-container-channel"),
    status="modelled",
    register="X17",
    options={
        "CONTAINER": _NAME,
        "CHANNEL": _NAME,
        "INTO": Arg("area_out"),
        # in: "the length of the data to be read"; out: "the length of the data in the container"
        "FLENGTH": Arg("area_inout", width=4, binary=True, inout_unless_literal=True),
        "NODATA": Arg("flag"),
        **RESP_OPTIONS,
    },
    refused={
        "INTOCCSID": CODEPAGE,
        "INTOCODEPAGE": CODEPAGE,
        "CONVERTST": CODEPAGE,
        "CCSID": CODEPAGE,
        "SET": Refusal(POINTER, "X17"),
        "BYTEOFFSET": Refusal("a partial GET is not modelled (no corpus program uses it)", "X17"),
    },
    groups=(
        required("CONTAINER", msg=NEEDS_ARGUMENT),
        one_of("INTO", "NODATA", msg="GET CONTAINER needs one of INTO / NODATA"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "FLENGTH")),
        Outcome("LENGERR", 11, "the data is longer than INTO takes: truncated", writes=("INTO", "FLENGTH")),
        Outcome("CHANNELERR", 2, "the channel is not in the program's scope"),
        Outcome("INVREQ", 4, "no CHANNEL and no current channel"),
        Outcome("CONTAINERERR", 10, "the channel has no such container"),
    ),
    runtime_refusals=(
        _SCOPE,
        _ILLEGAL_NAME,
        RuntimeRefusal(
            "an FLENGTH past INTO's end, or below zero",
            "X17",
            java="-byte INTO: not modelled",
            c="GET CONTAINER FLENGTH below zero",
        ),
    ),
    state=("channel_scope", "handle_table"),
    engine=EngineFacts(resource="CONTAINER", access="read"),
    impl=Impl(java="getContainer", c="GGCGETC", **_CONTAINER_IMPL),
)

DELETE_CONTAINER = Command(
    key="DELETE CONTAINER",
    ibm=ibm("EXEC CICS DELETE CONTAINER (CHANNEL)", "summary-delete-container-channel"),
    status="modelled",
    register="X17",
    options={"CONTAINER": _NAME, "CHANNEL": _NAME, **RESP_OPTIONS},
    groups=(required("CONTAINER", msg=NEEDS_ARGUMENT),),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("CHANNELERR", 2, "the channel is not in the program's scope"),
        Outcome("INVREQ", 4, "issued outside the scope of a currently-active channel"),
        Outcome("CONTAINERERR", 10, "the channel has no such container"),
    ),
    runtime_refusals=(_SCOPE, _ILLEGAL_NAME),
    state=("channel_scope", "handle_table"),
    engine=EngineFacts(resource="CONTAINER", access="delete"),
    impl=Impl(java="deleteContainer", c="GGCDELC", **_CONTAINER_IMPL),
)

MOVE_CONTAINER = Command(
    key="MOVE CONTAINER",
    ibm=ibm("EXEC CICS MOVE CONTAINER (CHANNEL)", "summary-move-container-channel"),
    status="modelled",
    register="X42",
    options={
        "CONTAINER": _NAME,  # the source
        "AS": _NAME,  # the target: "If it already exists, its contents are overwritten"
        "CHANNEL": _NAME,  # the source's channel; omitted: the current channel
        "TOCHANNEL": _NAME,  # the target's channel ("created" when absent); omitted: the current channel
        **RESP_OPTIONS,
    },
    groups=(required("CONTAINER", msg=NEEDS_ARGUMENT), required("AS", msg=NEEDS_ARGUMENT)),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("CHANNELERR", 2, "the channel named on CHANNEL could not be found"),
        Outcome("INVREQ", 4, "CHANNEL or TOCHANNEL not given and no current channel"),
        Outcome("CONTAINERERR", 10, "the source container could not be found"),
    ),
    runtime_refusals=(
        _SCOPE,
        _ILLEGAL_NAME,
        RuntimeRefusal(
            "a container moved onto itself (the same name in the same channel): IBM does not say",
            "X42",
            java="MOVE CONTAINER onto itself",
            c="MOVE CONTAINER onto itself",
        ),
        RuntimeRefusal(
            "a container moved onto an existing one of the other data type: its type, or INVREQ, is not documented",
            "X42",
            java="MOVE CONTAINER onto a container of the other data type",
            c="MOVE CONTAINER onto a container of the other data type",
        ),
    ),
    state=("channel_scope", "handle_table"),
    engine=EngineFacts(resource="CONTAINER", access="move"),
    impl=Impl(java="moveContainer", c="GGCMOVC", **_CONTAINER_IMPL),
)

_BROWSE_IMPL = {"translator": "Cics.container_browse", "harness": "_container_browse_command"}
_BROWSE_STALE = RuntimeRefusal(
    "a GETNEXT after a container was added to or removed from the browsed channel: IBM says nothing of changes "
    "during a browse",
    "X42",
    java="the browsed channel changed during the browse",
    c="the browsed channel changed during the browse",
)

STARTBROWSE_CONTAINER = Command(
    key="STARTBROWSE CONTAINER",
    ibm=ibm("EXEC CICS STARTBROWSE CONTAINER (CHANNEL)", "summary-startbrowse-container-channel"),
    status="modelled",
    register="X42",
    options={"CHANNEL": _NAME, "BROWSETOKEN": Arg("area_out", width=4, binary=True), **RESP_OPTIONS},
    groups=(required("BROWSETOKEN", msg=NEEDS_ARGUMENT),),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("BROWSETOKEN",)),
        Outcome("CHANNELERR", 2, "the channel named on CHANNEL could not be found"),
    ),
    runtime_refusals=(
        _SCOPE,
        _ILLEGAL_NAME,
        RuntimeRefusal(
            "no CHANNEL and no current channel: IBM treats the command as the BTS form, which is not modelled",
            "X42",
            java="STARTBROWSE CONTAINER with no channel",
            c="STARTBROWSE CONTAINER with no channel",
        ),
    ),
    state=("channel_scope", "handle_table"),
    impl=Impl(java="startBrowseContainer", c="GGCSBRC", **_BROWSE_IMPL),
)

GETNEXT_CONTAINER = Command(
    key="GETNEXT CONTAINER",
    ibm=ibm("EXEC CICS GETNEXT CONTAINER (CHANNEL)", "summary-getnext-container-channel"),
    status="modelled",
    register="X42",
    options={
        "CONTAINER": Arg("area_out", width=16),  # "the 16-character name of the next data-container"
        "BROWSETOKEN": Arg("value", width=4, binary=True),
        **RESP_OPTIONS,
    },
    groups=(required("CONTAINER", msg=NEEDS_ARGUMENT), required("BROWSETOKEN", msg=NEEDS_ARGUMENT)),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("CONTAINER",)),
        Outcome("END", 2, "no more containers remain"),
        Outcome("TOKENERR", 3, "the browse token is not valid"),
    ),
    runtime_refusals=(_BROWSE_STALE,),
    state=("handle_table",),
    impl=Impl(java="getNextContainer", c="GGCGNXC", **_BROWSE_IMPL),
)

ENDBROWSE_CONTAINER = Command(
    key="ENDBROWSE CONTAINER",
    ibm=ibm("EXEC CICS ENDBROWSE CONTAINER (CHANNEL)", "summary-endbrowse-container-channel"),
    status="modelled",
    register="X42",
    options={"BROWSETOKEN": Arg("value", width=4, binary=True), **RESP_OPTIONS},
    groups=(required("BROWSETOKEN", msg=NEEDS_ARGUMENT),),
    outcomes=(Outcome("NORMAL", 0, ""), Outcome("TOKENERR", 3, "the browse token is not valid")),
    state=("handle_table",),
    impl=Impl(java="endBrowseContainer", c="GGCEBRC", **_BROWSE_IMPL),
)

_CHANNEL_IMPL = {"translator": "Cics.channel_command", "harness": "_channel_command"}

DELETE_CHANNEL = Command(
    key="DELETE CHANNEL",
    ibm=ibm("EXEC CICS DELETE CHANNEL", "summary-delete-channel"),
    status="modelled",
    register="X44",
    options={"CHANNEL": _NAME, **RESP_OPTIONS},  # deleting a channel deletes every container it holds
    groups=(required("CHANNEL", msg=NEEDS_ARGUMENT),),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("CHANNELERR", 2, "the channel named on CHANNEL could not be found"),
    ),
    runtime_refusals=(
        _SCOPE,
        _ILLEGAL_NAME,
        RuntimeRefusal(
            "the program's current channel: IBM gives CHANNELERR RESP2 4 (current), 5 (transaction channel) or 6 (not "
            "owned by the calling program), and a channel a program is passed is all of them, unranked",
            "X44",
            java="DELETE CHANNEL of the current channel",
            c="DELETE CHANNEL of the current channel",
        ),
    ),
    state=("channel_scope", "handle_table"),
    impl=Impl(java="deleteChannel", c="GGCDELH", **_CHANNEL_IMPL),
)

QUERY_CHANNEL = Command(
    key="QUERY CHANNEL",
    ibm=ibm("EXEC CICS QUERY CHANNEL", "summary-query-channel"),
    status="modelled",
    register="X44",
    options={
        "CHANNEL": _NAME,
        "CONTAINERCNT": Arg("area_out", width=4, binary=True),  # "a count of the number of containers", a fullword
        **RESP_OPTIONS,
    },
    groups=(required("CHANNEL", msg=NEEDS_ARGUMENT), required("CONTAINERCNT", msg=NEEDS_ARGUMENT)),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("CONTAINERCNT",)),
        Outcome("CHANNELERR", 2, "the channel named on CHANNEL could not be found"),
    ),
    runtime_refusals=(_SCOPE, _ILLEGAL_NAME),
    state=("channel_scope", "handle_table"),
    impl=Impl(java="queryChannel", c="GGCQCHN", **_CHANNEL_IMPL),
)

COMMANDS = (
    PUT_CONTAINER,
    GET_CONTAINER,
    DELETE_CONTAINER,
    MOVE_CONTAINER,
    STARTBROWSE_CONTAINER,
    GETNEXT_CONTAINER,
    ENDBROWSE_CONTAINER,
    DELETE_CHANNEL,
    QUERY_CHANNEL,
)
