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
X44; #5005: GET64 / PUT64 CONTAINER, register X17."""

from __future__ import annotations

from dataclasses import replace

from gitgalaxy.standards.cics.commands.shared import NEEDS_ARGUMENT, RESP_OPTIONS, ibm
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
    requires,
)

# #4270 (X17): the IANA code-page names (FROMCODEPAGE / INTOCODEPAGE) are not modelled: they raise CODEPAGEERR, whose RESP2 values
# are IBM's own list beside CCSIDERR's, and no corpus program uses them
_CODEPAGE_NAME = Refusal(
    "IANA code-page names are not modelled (CODEPAGEERR; no corpus program uses them): use the CCSID", "X17"
)

_NAME = Arg("name", width=16)  # "the name (1 - 16 characters)"

# what every container command refuses while running: a channel an XCTL left behind, an illegal name (PUT CONTAINER
# alone has IBM's CHANNELERR 1 / CONTAINERERR 18 for one: its page gives the name's character set; the others' pages say
# nothing of one)
_SCOPE = RuntimeRefusal(
    "a channel an XCTL left behind: IBM's scope tables do not say",
    "X17",
    java=" after an XCTL that did not pass it: its scope ",
    c="channel %s after an XCTL that did not pass it",
)
_ILLEGAL_NAME = RuntimeRefusal(
    "a channel / container name that is blank, longer than 16 or holds a character outside IBM's set (A-Z a-z 0-9 $ @ # / % ? ! : | \" = , ; > . - _, no leading or embedded blank), on a command whose page says nothing of one",
    "X17",
    java=" name '\" + name + \"': not modelled",
    c="%s name '%s'",
)
_DISPUTED_NAME = RuntimeRefusal(
    "a channel / container name holding & < or the not sign: RUN TRANSID's page allows them, PUT CONTAINER's does not",
    "X17",
    java="holds & < or a not sign: IBM's RUN ",
    c="holds & < or a not sign: IBM's RUN TRANSID",
)
# #5005 (X42 / X44): IBM's MOVE CONTAINER (INVREQ RESP2 30 / 31, CHANNELERR 3) and DELETE CHANNEL (CHANNELERR 3) pages name
# CICS-defined read-only containers and channels and list none (they mention DFHTRANSACTION only): no state here is read-only, so a
# name beginning DFH is refused by name rather than run as on an ordinary one.
_CICS_DEFINED = RuntimeRefusal(
    "a container or channel named DFH...: it may be a CICS-defined read-only one (INVREQ RESP2 30 / 31, CHANNELERR RESP2 3), and "
    "IBM lists none",
    "X42",
    java="naming a CICS-defined (DFH...) container or channel",
    c="naming a CICS-defined (DFH...) container or channel",
)
# #4270 (X17): what the CHAR container conversion (FROMCCSID / INTOCCSID / CONVERTST, the region's 037) refuses while running
_CCSID_REFUSALS = (
    RuntimeRefusal(
        "a CCSID other than 37, 500, 1140 and 1208 (IBM: CCSIDERR RESP2 1 outside the valid range, 2 for an unsupported pair)",
        "X17",
        java=": only the CCSIDs 37, 500, 1140 and 1208 are modelled",
        c=": only the CCSIDs 37, 500, 1140 and 1208 are modelled",
    ),
    RuntimeRefusal(
        "a character the target CCSID lacks (037 / 500 <-> 1140: the currency sign and the euro): CCSIDERR RESP2 4 replaces it "
        "with a blank, and IBM does not say what FLENGTH or the stored data then are",
        "X17",
        java="code-page conversion of a character the target CCSID lacks",
        c="code-page conversion of a character the target CCSID lacks",
    ),
    RuntimeRefusal(
        "a CCSID 1208 byte beyond ASCII (a multibyte character changes the length)",
        "X17",
        java="code-page conversion of a CCSID 1208 byte beyond ASCII",
        c="code-page conversion of a CCSID 1208 byte beyond ASCII",
    ),
    RuntimeRefusal(
        "a character beyond ASCII converted to CCSID 1208 (a multibyte sequence changes the length)",
        "X17",
        java="code-page conversion to CCSID 1208 of a character beyond ASCII",
        c="code-page conversion to CCSID 1208 of a character beyond ASCII",
    ),
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
        "CHAR": Arg("flag"),  # in the region's CCSID (037) unless FROMCCSID says another
        "DATATYPE": Arg("cvda"),  # DFHVALUE(BIT | CHAR) only
        # #4270 (X17): the data's CCSID (CHAR is implied): 037, 500, 1140 or 1208 (ASCII)
        "FROMCCSID": Arg("value"),
        "APPEND": Arg("flag"),
        "PREPEND": Arg("flag"),  # #5005 (X17): BIT containers only ("6.2 and later")
        **RESP_OPTIONS,
    },
    refused={
        "FROMCODEPAGE": _CODEPAGE_NAME,
    },
    groups=(
        required("CONTAINER", msg=NEEDS_ARGUMENT),
        required("FROM", msg=NEEDS_ARGUMENT),
        at_most_one("BIT", "CHAR", "DATATYPE", msg="PUT CONTAINER {}: one data type"),
        at_most_one(
            "APPEND", "PREPEND", msg="PUT CONTAINER {}: APPEND and PREPEND together are not modelled (IBM does not say)"
        ),
    ),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("INVREQ", 4, "no CHANNEL and no current channel"),
        Outcome("INVREQ", 1, "no CHANNEL and no current channel, with a data type named"),
        Outcome("LENGERR", 1, "FLENGTH below zero"),
        Outcome("INVREQ", 2, "FROMCCSID with no CHANNEL and no current channel", raised_by=("FROMCCSID",)),
        Outcome("INVREQ", 34, "BIT (or DATATYPE(BIT)) with FROMCCSID", raised_by=("FROMCCSID",)),
        Outcome(
            "CHANNELERR", 1, "the CHANNEL name contains an illegal character or combination", raised_by=("CHANNEL",)
        ),
        Outcome(
            "CONTAINERERR",
            18,
            "the CONTAINER name contains an illegal character or combination",
            raised_by=("CONTAINER",),
        ),
    ),
    runtime_refusals=(
        _SCOPE,
        _ILLEGAL_NAME,
        _DISPUTED_NAME,
        RuntimeRefusal(
            "an illegal CONTAINER and CHANNEL name together, or one with a negative FLENGTH or no channel: which condition "
            "IBM raises first is not documented",
            "X17",
            java="which condition IBM raises first is not documented",
            c="which condition IBM raises first is not documented",
        ),
        RuntimeRefusal(
            "a data type named for an existing container of the other type: ignored, or INVREQ RESP2 33?",
            "X17",
            java=" on an existing container of the other ",
            c="PUT CONTAINER changing an existing container's data type",
        ),
        RuntimeRefusal("an FLENGTH past FROM's end", "X17", java="PUT CONTAINER FLENGTH "),
        RuntimeRefusal(
            "PREPEND on a CHAR container (or with FROMCCSID): IBM counts a CHAR container's data in its code page",
            "X17",
            java="PUT CONTAINER PREPEND on a CHAR container",
            c="PUT CONTAINER PREPEND on a CHAR container",
        ),
        *_CCSID_REFUSALS,
        RuntimeRefusal(
            "FROMCCSID with a data type and no channel in scope: INVREQ RESP2 1 and RESP2 2 both fit, and IBM ranks neither",
            "X17",
            java="PUT CONTAINER FROMCCSID with a data type and no channel",
            c="PUT CONTAINER FROMCCSID with a data type and no channel",
        ),
        RuntimeRefusal(
            "FROMCCSID with a negative FLENGTH: which condition IBM raises first is not documented",
            "X17",
            java="PUT CONTAINER FROMCCSID with a negative FLENGTH",
            c="PUT CONTAINER FROMCCSID with a negative FLENGTH",
        ),
        RuntimeRefusal(
            "FROMCCSID onto an existing BIT container: IBM does not say",
            "X17",
            java="PUT CONTAINER FROMCCSID onto an existing BIT container",
            c="PUT CONTAINER FROMCCSID onto an existing BIT container",
        ),
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
        # #5042 (X58): "the address of the retrieved data"; FLENGTH is then the output length
        "SET": Arg("pointer"),
        # #4270 (X17): the CCSID the data comes back in (default: the region's, 037);
        # CONVERTST(DFHVALUE(NOCONVERT)): the container's own; CCSID(fullword): the CCSID the data came back in (0: BIT)
        "INTOCCSID": Arg("value"),
        "CONVERTST": Arg("cvda"),
        "CCSID": Arg("area_out", width=4, binary=True),
        # #5005 (X17): "the offset in bytes where the data returned starts" (a fullword; below zero: zero), BIT containers with INTO
        "BYTEOFFSET": Arg("value"),
        **RESP_OPTIONS,
    },
    refused={
        "INTOCODEPAGE": _CODEPAGE_NAME,
    },
    groups=(
        required("CONTAINER", msg=NEEDS_ARGUMENT),
        one_of("INTO", "NODATA", "SET", msg="GET CONTAINER needs one of INTO / NODATA / SET"),
        requires(
            ("SET",), any_of=("FLENGTH",), msg="GET CONTAINER SET without FLENGTH(data-area): the length of the data"
        ),
        at_most_one(
            "INTOCCSID", "CONVERTST", msg="GET CONTAINER {}: one target code page (INTOCCSID, CONVERTST(NOCONVERT))"
        ),
        requires(
            ("BYTEOFFSET",),
            any_of=("INTO",),
            msg="GET CONTAINER BYTEOFFSET needs INTO (NODATA and SET are not modelled with it)",
        ),
        at_most_one(
            "BYTEOFFSET",
            "INTOCCSID",
            "CONVERTST",
            "CCSID",
            msg="GET CONTAINER BYTEOFFSET with {}: not modelled (IBM counts the offset in the requested code page)",
        ),
        requires(
            ("CCSID",),
            any_of=("CONVERTST",),
            msg="GET CONTAINER CCSID without CONVERTST(DFHVALUE(NOCONVERT)): IBM returns it only for the unconverted data",
        ),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "SET", "FLENGTH", "CCSID")),
        Outcome("LENGERR", 11, "the data is longer than INTO takes: truncated", writes=("INTO", "FLENGTH", "CCSID")),
        Outcome("LENGERR", 12, "BYTEOFFSET at or past the end of the container's data", raised_by=("BYTEOFFSET",)),
        Outcome("CHANNELERR", 2, "the channel is not in the program's scope"),
        Outcome("INVREQ", 4, "no CHANNEL and no current channel"),
        Outcome("INVREQ", 2, "INTOCCSID with no CHANNEL and no current channel", raised_by=("INTOCCSID",)),
        Outcome("CONTAINERERR", 10, "the channel has no such container"),
        Outcome(
            "CCSIDERR",
            3,
            "INTOCCSID on a BIT container: the data is returned without any code page conversion",
            writes=("INTO",),
            raised_by=("INTOCCSID",),
        ),
    ),
    runtime_refusals=(
        _SCOPE,
        _ILLEGAL_NAME,
        _DISPUTED_NAME,
        RuntimeRefusal(
            "an FLENGTH past INTO's end, or below zero",
            "X17",
            java="-byte INTO: not modelled",
            c="GET CONTAINER FLENGTH below zero",
        ),
        *_CCSID_REFUSALS,
        RuntimeRefusal(
            "INTOCCSID on a BIT container longer than INTO: whether LENGERR or CCSIDERR wins is not documented",
            "X17",
            java="GET CONTAINER INTOCCSID on a BIT container longer than INTO",
            c="GET CONTAINER INTOCCSID on a BIT container longer than INTO",
        ),
        RuntimeRefusal(
            "SET with INTOCCSID on a BIT container: the data is returned unconverted, and IBM does not say whether a block is acquired",
            "X17",
            java="GET CONTAINER SET INTOCCSID on a BIT container",
            c="GET CONTAINER SET INTOCCSID on a BIT container",
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
    runtime_refusals=(_SCOPE, _ILLEGAL_NAME, _DISPUTED_NAME, _CICS_DEFINED),
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
        _DISPUTED_NAME,
        _CICS_DEFINED,
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
        _DISPUTED_NAME,
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
        _DISPUTED_NAME,
        _CICS_DEFINED,
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
    runtime_refusals=(_SCOPE, _ILLEGAL_NAME, _DISPUTED_NAME),
    state=("channel_scope", "handle_table"),
    impl=Impl(java="queryChannel", c="GGCQCHN", **_CHANNEL_IMPL),
)

# #5005 (X17): GET64 / PUT64 CONTAINER are the same commands with 64-bit data areas: IBM's pages give the same options,
# conditions and RESP2 values, FLENGTH a fullword on both, and only INTO / FROM / SET "64-bit". A COBOL item has no
# address above the bar, so INTO / FROM are modelled as the item (ASSUMED, X17); SET returns a 64-bit pointer, which the
# pointer lane (X47, 31-bit-style blocks) does not hold: refused by name.
_SET64 = Refusal(
    "GET64 CONTAINER SET returns a 64-bit pointer reference (an address above the bar): the pointer lane holds "
    "31-bit-style blocks only (X47 / X58): use INTO",
    "X17",
)


def _sixty_four(base: Command, verb: str, topic: str) -> Command:
    """The 64-bit form of a container command: the base's options, outcomes and refusals, SET (the 64-bit pointer) refused."""
    no_set = "SET" in base.options
    return replace(
        base,
        key=f"{verb}64 CONTAINER",
        ibm=ibm(f"EXEC CICS {verb}64 CONTAINER", topic),
        options={o: a for o, a in base.options.items() if o != "SET"},
        refused={**base.refused, **({"SET": _SET64} if no_set else {})},
        groups=tuple(g for g in base.groups if "SET" not in g.options + g.any_of)
        + (
            (one_of("INTO", "NODATA", msg=f"{verb}64 CONTAINER needs one of INTO / NODATA (SET is not modelled)"),)
            if no_set
            else ()
        ),
        outcomes=tuple(replace(o, writes=tuple(w for w in o.writes if w != "SET")) for o in base.outcomes),
        runtime_refusals=tuple(r for r in base.runtime_refusals if not r.situation.startswith("SET ")),
        engine=base.engine,  # the scan's resource walker reads the 64-bit verbs as the base verb (cics_resources._CONTAINER_VERBS)
    )


PUT64_CONTAINER = _sixty_four(PUT_CONTAINER, "PUT", "summary-put64-container")
GET64_CONTAINER = _sixty_four(GET_CONTAINER, "GET", "summary-get64-container")


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
    PUT64_CONTAINER,
    GET64_CONTAINER,
)
