# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 slice 1 (#4575): PUT / GET / DELETE CONTAINER (CHANNEL), register X17."""

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

COMMANDS = (PUT_CONTAINER, GET_CONTAINER, DELETE_CONTAINER)
