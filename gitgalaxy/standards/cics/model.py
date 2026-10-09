# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The CICS command spec's model (#4270, docs/language_status/cics_command_spec.md section 2.1).

Frozen dataclasses, standard library only. Every value is checked when it is built (`__post_init__`), so a typo in
an option or condition name fails at import time, not in a consumer. The spec says what WE model; it is never the
oracle (section 6): no crucible log is ever derived from it."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

Kind = Literal[
    "area_in",  # a data area the command reads
    "area_out",  # a data area the command writes
    "area_inout",  # a data area it reads and writes back
    "value",  # a data value (a number, a length)
    "name",  # a name: a transid, a channel, a container ...
    "hhmmss",  # a packed hhmmss time / interval
    "pointer",  # a pointer reference (SET)
    "flag",  # a bare option, no argument
    "label",  # a paragraph name
    "cvda",  # a CICS-value data area
]
KINDS = frozenset(Kind.__args__)  # type: ignore[attr-defined]
HOSTS = frozenset({"cobol", "pli"})
_NAME = re.compile(r"^[A-Z][A-Z0-9]*$")
_REGISTER = re.compile(r"^X\d+$")

# Named state a command reads or changes (section 4): a vocabulary, not a model. Each entry says what it is; the
# semantics stay hand-written in each runtime, and the crucible proves them.
STATES: Mapping[str, str] = {
    "channel_scope": "the channels in the program's scope and its current channel (IBM: 'Scope of a channel')",
    "interval_requests": "the task's START requests not yet expired, by REQID, and the data a started task RETRIEVEs",
    "virtual_clock": "the region's clock, which decides when a START request expires",
    "child_tasks": "the RUN TRANSID child tasks a task started",
    "terminal": "the task's principal facility: its terminal and that terminal's screen",
    "handle_table": "the HANDLE CONDITION / IGNORE CONDITION table every command that can raise a condition consults",
}


def _name(value: str, what: str) -> None:
    if not _NAME.match(value):
        raise ValueError(f"{what} {value!r}: not an upper-case CICS name")


@dataclass(frozen=True)
class Doc:
    """An IBM documentation topic: its title as IBM shows it and its URL (checked by hand, not cited as a source)."""

    title: str
    url: str

    def __post_init__(self) -> None:
        if not self.url.startswith("https://www.ibm.com/docs/"):
            raise ValueError(f"{self.title}: not an IBM documentation URL ({self.url})")


@dataclass(frozen=True)
class Arg:
    """What an option takes."""

    kind: Kind
    width: int | None = None  # a name's characters, an area's bytes
    binary: bool = False  # a halfword / fullword binary area (ASSIGN SCRNHT)
    inout_unless_literal: bool = False  # FLENGTH / LENGTH: in-out for a data area, in only for a literal
    hosts: tuple[str, ...] = ("cobol", "pli")  # the rare option one host language lacks (section 5)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown argument kind {self.kind!r}")
        if self.width is not None and self.width < 1:
            raise ValueError(f"width {self.width}")
        if not self.hosts or set(self.hosts) - HOSTS:
            raise ValueError(f"hosts {self.hosts}")


@dataclass(frozen=True)
class Refusal:
    """Why an option of a modelled command is refused when translating, word for word as the user sees it.

    `whole`: today's translator shows this reason in place of every other refused option's (START / RUN / RETURN
    CHANNEL, any refused CANCEL option), so it carries its own subject; else the message shows `OPTION: why`."""

    why: str
    register: str | None = None
    whole: bool = False

    def __post_init__(self) -> None:
        if not self.why or self.why != self.why.strip():
            raise ValueError(f"refusal reason {self.why!r}")
        if self.register is not None and not _REGISTER.match(self.register):
            raise ValueError(f"register {self.register!r}")


@dataclass(frozen=True)
class RuntimeRefusal:
    """A situation a runtime refuses while running (it raises / stops rather than guess). PR 1 records each side's
    text as it is today (the static part of the message): the two runtimes' texts differ until PR 5 shares them."""

    situation: str
    register: str | None = None
    java: str | None = None  # in CicsTask (CICS_TASK_JAVA) or DetCics.java
    c: str | None = None  # in tests/equivalence/cics/ggcics.c

    def __post_init__(self) -> None:
        if self.java is None and self.c is None:
            raise ValueError(f"{self.situation}: refused by no runtime")
        if self.register is not None and not _REGISTER.match(self.register):
            raise ValueError(f"register {self.register!r}")


@dataclass(frozen=True)
class Outcome:
    """One (condition, RESP2) a command can end with."""

    condition: str  # a DFHRESP name (checked against resp.DFHRESP by Command)
    resp2: int | None  # None: not stated (IBM documents none, or the entry does not state it yet: PR 6); runtimes set 0
    when: str  # what causes it, in IBM's words where they exist
    writes: tuple[str, ...] = ()  # the output options written with this outcome (the others are left alone)
    raised_by: tuple[str, ...] = ()  # the options that can raise it (empty: the command itself)

    def __post_init__(self) -> None:
        _name(self.condition, "condition")
        if self.resp2 is not None and self.resp2 < 0:
            raise ValueError(f"{self.condition} RESP2 {self.resp2}")


@dataclass(frozen=True)
class Abend:
    """An abend CICS itself raises for a command (no condition: RESP, RESP2 and HANDLE CONDITION do not see it)."""

    code: str  # the 4-character abend code (IBM, CICS abend codes)
    when: str  # what causes it, in IBM's words where they exist

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Z0-9]{4}", self.code):
            raise ValueError(f"abend code {self.code!r}")


GroupKind = Literal["required", "one_of", "at_most_one", "requires"]


@dataclass(frozen=True)
class Group:
    """A rule between options, with the message the translator raises today (`{}`: the part it fills in).

    required: `options[0]` must be given. one_of: exactly one of `options`. at_most_one: none or one of `options`.
    requires: any of `options` needs one of `any_of` (`both_ways`: and each of `any_of` needs one of `options`)."""

    kind: GroupKind
    options: tuple[str, ...]
    msg: str
    any_of: tuple[str, ...] = ()
    both_ways: bool = False

    def __post_init__(self) -> None:
        if self.kind not in ("required", "one_of", "at_most_one", "requires"):
            raise ValueError(f"group kind {self.kind!r}")
        if not self.options or (self.kind == "requires") != bool(self.any_of):
            raise ValueError(f"group {self.kind} {self.options} {self.any_of}")
        for o in self.options + self.any_of:
            _name(o, "group option")


def required(option: str, msg: str) -> Group:
    return Group("required", (option,), msg)


def one_of(*options: str, msg: str) -> Group:
    return Group("one_of", options, msg)


def at_most_one(*options: str, msg: str) -> Group:
    return Group("at_most_one", options, msg)


def requires(options: tuple[str, ...], any_of: tuple[str, ...], msg: str, both_ways: bool = False) -> Group:
    return Group("requires", options, msg, any_of=any_of, both_ways=both_ways)


@dataclass(frozen=True)
class Fact:
    """A fact the runtime cannot know; whoever runs the task states it (CicsTask.withX, $GGCICS_X)."""

    name: str
    java: str | None  # the CicsTask method that states it (None: the runtime has it another way)
    env: str  # the stub's environment variable
    region_default: str | None  # the reference region's value (cics-crucible SPEC 2); None: stated per task
    options: tuple[str, ...]  # the options that read it
    values: tuple[str, ...] = ()  # its documented values, when IBM lists them

    def __post_init__(self) -> None:
        if not self.env.startswith("GGCICS_"):
            raise ValueError(f"fact {self.name}: env {self.env!r}")


@dataclass(frozen=True)
class EngineFacts:
    """What the engine's scanners lift out of the command today (gitgalaxy/core/cics_resources.py, cics_tasks.py)."""

    resource: str | None = None  # a resource row's kind: CONTAINER
    access: str | None = None  # its direction: read / write / delete / move
    task_verb: str | None = None  # a cics_tasks row's verb
    target_option: str | None = None  # the option naming the task's target (TRANSID)
    handle_option: str | None = None  # the option naming its handle, cics_tasks' "token" (REQID, CHILD)
    channel_option: str | None = None  # the option naming who receives a channel it hands on (TRANSID)
    edge: str | None = None  # an edge kind the engine does not emit yet (LOAD: "load", PR 8b, after the trial)


@dataclass(frozen=True)
class Impl:
    """Where the hand-written semantics live: a pointer, not a contract (section 3.3). Each name is checked to
    resolve: the translator's Python attribute, the Java method in CICS_TASK_JAVA, the C symbol in ggcics.c and the
    harness's function in tests/tools/equivalence_cics.py."""

    translator: str
    java: str
    c: str
    harness: str


@dataclass(frozen=True)
class Command:
    """One EXEC CICS command as we model it."""

    key: str  # the form det/cics.py's OPTIONS uses: "GET CONTAINER"
    ibm: Doc
    status: Literal["modelled", "refused", "engine-only"]
    # status "refused" (a name-only entry) / "engine-only": why the translator refuses the whole command
    why: str | None = None
    options: Mapping[str, Arg] = field(default_factory=dict)  # the options it honours
    # every option is checked by the command's own handler, not against `options` (HANDLE CONDITION's options are
    # conditions, HANDLE AID's attention keys)
    open_options: bool = False
    refused: Mapping[str, Refusal] = field(default_factory=dict)  # the options it refuses, by name
    default_refusal: Refusal | None = None  # an option in neither table (None: refused with no reason)
    groups: tuple[Group, ...] = ()
    outcomes: tuple[Outcome, ...] = ()
    abends: tuple[Abend, ...] = ()  # the abends it can end the task with, whatever RESP / HANDLE CONDITION say
    runtime_refusals: tuple[RuntimeRefusal, ...] = ()
    state: tuple[str, ...] = ()
    facts: tuple[Fact, ...] = ()
    engine: EngineFacts | None = None
    impl: Impl | None = None
    register: str | None = None  # its X-register entry (docs/language_status/oracle_assumptions.md)
    event: str | None = None  # the cics-crucible SPEC 6.2 event it records: a name only (section 6)

    def __post_init__(self) -> None:
        if self.status not in ("modelled", "refused", "engine-only"):
            raise ValueError(f"{self.key}: status {self.status!r}")
        if (self.status == "modelled") == (self.why is not None):
            raise ValueError(f"{self.key}: a whole-command reason is for a refused / engine-only command only")
        if self.why is not None and (not self.why or self.why != self.why.strip()):
            raise ValueError(f"{self.key}: reason {self.why!r}")
        if self.status == "refused" and (self.options or self.refused or self.groups or self.outcomes):
            raise ValueError(f"{self.key}: a name-only entry has a name, a URL and a reason only")
        for word in self.key.split():
            _name(word, f"{self.key}: command word")
        for o in list(self.options) + list(self.refused):
            _name(o, f"{self.key}: option")
        both = set(self.options) & set(self.refused)
        if both:
            raise ValueError(f"{self.key}: {sorted(both)} both honoured and refused")
        known = set(self.options) | set(self.refused)
        for g in self.groups:
            missing = [o for o in g.options + g.any_of if o not in known]
            if missing:
                raise ValueError(f"{self.key}: group names {missing}, not options of the command")
        for oc in self.outcomes:
            for o in oc.writes + oc.raised_by:
                if o not in self.options:
                    raise ValueError(f"{self.key} {oc.condition}: {o} is not an option it honours")
        unknown_state = [s for s in self.state if s not in STATES]
        if unknown_state:
            raise ValueError(f"{self.key}: unknown state {unknown_state} (add it to model.STATES)")
        for f in self.facts:
            missing = [o for o in f.options if o not in self.options]
            if missing:
                raise ValueError(f"{self.key}: fact {f.name} read by {missing}, not options it honours")
        if self.register is not None and not _REGISTER.match(self.register):
            raise ValueError(f"{self.key}: register {self.register!r}")

    def group(self, kind: GroupKind, option: str) -> Group:
        """The command's `kind` rule whose options start with `option` (the translator raises its message)."""
        for g in self.groups:
            if g.kind == kind and g.options[0] == option:
                return g
        raise KeyError(f"{self.key}: no {kind} group of {option}")

    def refusal(self, option: str) -> Refusal | None:
        """The refusal of an option the command does not honour: its own, else the default."""
        return self.refused.get(option, self.default_refusal)

    def refusal_message(self, bad: list[str]) -> str:
        """The translator's message for these options refused together (det/cics.py check_options, today's form):
        `KEY A B: option not modelled (A: why; B: why)`; a `whole` reason stands alone; an option with no reason is
        named but not explained."""
        reasons = [(o, self.refusal(o)) for o in bad]
        whole = next((r for _o, r in reasons if r is not None and r.whole), None)
        why = whole.why if whole is not None else "; ".join(f"{o}: {r.why}" for o, r in reasons if r is not None)
        return f"{self.key} {' '.join(bad)}: option not modelled" + (f" ({why})" if why else "")

    def whole_message(self, verb: str) -> str:
        """The translator's message for the whole command refused (a name-only or engine-only entry), `verb` as the
        program wrote it: `EXEC CICS VERB not modelled (why)`."""
        return f"EXEC CICS {verb} not modelled ({self.why})"
