# Design: one declarative CICS command spec (#4270)

**Status: design accepted with the owner's decisions (2026-10-06, section 9); PR 1 (the package, its CLI and the
transitional equality tests) merged (#4589); PR 2 (the translator reads the spec; 45 full entries, 206 name-only) in
review.** All line numbers are against origin/main `b6c3e4ea8`.

Every #4270 slice teaches the det port one more EXEC CICS command by writing the same facts about that command
again in five to seven places, in three languages. The engine pulls CICS facts out of the same commands with its own
verb tables, and PL/I CICS gets nothing beyond those tables. This page proposes **one declarative command spec**.
For each command it holds the options, argument kinds and directions, option groups, conditions with RESP / RESP2,
the state the command touches, the facts the runner must state, refusals with their reasons and the IBM topic. The
engine, the translator, both runtimes, the equivalence harness and the X-register checks all read it. It is **not**
the oracle: the cics-crucible's hand-traced logs never come from it (section 6).

## 1. What a slice duplicates today

### 1.1 Per command: the four merged slices

| slice | PR | files touched | lines + / - |
|---|---|---:|---:|
| 1 channels / containers | #4575 | 12 | 1021 / 27 |
| 2 START / RETRIEVE / CANCEL / RUN | #4578 | 15 | 1245 / 121 |
| 3 ASSIGN STARTCODE / USERID / FACILITY / SCRNHT / SCRNWD | #4582 | 10 | 386 / 28 |
| 4 SEND TEXT TERMINAL | #4583 | 6 | 119 / 2 |

Every slice touched `det/cics.py`, `oracle_assumptions.md`, `det_port_design.md` and the det tests. The three
slices that changed runtime behaviour also touched both runtimes (`cobol_to_java_transaction_forge.py`'s
`CICS_TASK_JAVA`, `ggcics.c`) and the stub's translator (`tests/tools/equivalence_cics.py`). This is how one
command, **GET CONTAINER**, is encoded today:

| fact | where (file:line) |
|---|---|
| allowed options | `det/cics.py:167` (`OPTIONS["GET CONTAINER"]`); `tests/tools/equivalence_cics.py:720-724` (`_CONTAINER_OPTIONS["GET"]`, a second hand copy) |
| why SET / INTOCCSID / ... are refused | `det/cics.py:200-217` (`_REFUSED_WHY`); the harness refuses the same options with **no** reason (`equivalence_cics.py:735`); the X17 prose (`oracle_assumptions.md:641-650`) |
| "one of INTO / NODATA" | `det/cics.py:1096-1097`; `equivalence_cics.py:767-768` |
| FLENGTH in-out, set back only on NORMAL / LENGERR | `det/cics.py:1098-1103` (translator); `cobol_to_java_transaction_forge.py:1172-1190` (CicsTask); `ggcics.c:1819-1840` (GGCGETC); X17 prose |
| conditions + RESP2 (CHANNELERR 2, INVREQ 4, CONTAINERERR 10, LENGERR 11) | CicsTask `getContainer` (`forge:1172-1190`); `ggcics.c:1829-1838`; X17 prose; translator docstring `det/cics.py:1066-1077` |
| RESP numbers (CONTAINERERR 110, CHANNELERR 122) | `det/cics.py:20-40` (`DFHRESP`, 104 names); `equivalence_cics.py:46-63` (a second full table); `DetCics.java:372-430` (`condition` / `resp`, 43 cases); forge `respName` (`:2375-2398`, 19 cases); `ggcics.c:86-89` (enum, 14 names) |
| default abend (AEZJ / AEZV) | forge `abcodeFor` (`:2402-2415`); `ggcics.c:1236-1250`; `tests/tools/cics_crucible.py:136-139` (`CONDITION_ABCODE`); X17 prose |
| engine fact (resource CONTAINER, access read, qualifier CHANNEL) | `gitgalaxy/core/cics_resources.py:113` (`_CONTAINER_VERBS`), `:128` (`_RECORD_CLAUSES`), `:130` (`_NOISE`) |

So 8 facts sit in 18 places, and each place is a hand-written copy of IBM's documentation.

### 1.2 Copies across the whole surface

| table | copies | count / drift found |
|---|---:|---|
| DFHRESP name -> number | 5 (2 Python, 2 Java, 1 C) | 104 / 104 / 43 / 19 / 14 entries; the comment at `det/cics.py:36-37` already says it must "agree on every shared name" with the harness's table |
| condition -> default abend code | 3 implementation copies + 1 oracle copy | runtimes and runner have 10 entries; `crucible_events.ABEND_FOR` (`:59-68`) has 8, without AEZJ / AEZV. That gap is **correct** for the oracle side (section 6), but nothing reports it |
| options per command | 2 + engine | translator `OPTIONS` (43 commands); harness lists for containers, interval control (`:369-371`), ASSIGN (`:222-223`), SEND TEXT (`:427`) |
| refusal reasons | 3 translator tables (16 + 18 + 22) + 5 special cases inside `check_options` (`det/cics.py:310-325`) | the harness refuses the same options with a bare name; the X-register lists them a third time in prose |
| RESP2 per condition | runtime Java, C, prose; sometimes the translator | ASSIGN's INVREQ RESP2 5 is computed **in the translator** (`det/cics.py:666`), not in CicsTask (`assignTerminalResp`, forge `:546-548`, returns RESP only), while ggcics computes it in the stub |
| facts the runner states | 3 | CicsTask `withStartcode` / `withUserid` / `withScreen` (forge `:506-520`); `$GGCICS_STARTCODE` etc. (`ggcics.c:1457-1485`); the runner wires both (`cics_crucible.py:904`, `:2042`, `REGION_USERID` `:133`) |
| EXEC option parsers | 4 | `det/cics.py:341` `parse_exec`; `equivalence_cics.py:97` `_options`; `core/cics_resources.py:192` `_options`; `cics_census.py:111` `commands` (`fact_ownership.md` shows that the engine and the translator agree 100% on the censused verbs) |
| engine verb tables | 4 modules | `cics_resources.py:100-147`, `cics_tasks.py:69-89`, `mainframe_boundary.py:287-338`, `jcics.py` / `hlasm_cics.py` |

Refusal sites: 64 `raise CicsError` in `det/cics.py`, 87 `raise Unsupported` in `equivalence_cics.py` and 25
`refuse(` in `ggcics.c`. Not one of them shares its text with a refusal on another side.

**PL/I.** `cics_census.py --pli` counts PL/I programs, and the engine reads PL/I EXEC CICS through the COBOL reader
(`mainframe_boundary.py:2392`). But no engine table knows **LOAD / RELEASE**: `LOAD` does not appear in
`cics_resources.py`, `cics_tasks.py` or `mainframe_boundary.py`. A LOAD-heavy PL/I estate therefore shows no edges
from its programs to the modules and tables they load.

## 2. The format: Python data (frozen dataclasses)

The spec lives at **`gitgalaxy/standards/cics/`**, a neutral, data-only package that the engine owns and ships.
`model.py` holds the dataclasses and `commands/*.py` holds one module per command family (`containers.py`,
`interval.py`, `assign.py`, ...). `resp.py` holds DFHRESP and the default abend codes. Every consumer imports it
directly: the engine walkers, the translator, the runtime generators and the harness. There are no per-consumer
copies and no drift test between copies. A spec change is reviewed as a translator change (no CODEOWNERS entry:
the owner is the only maintainer). Later siblings follow the same pattern: `standards/sql/`, intrinsic functions
and file status.

| | YAML | JSON | **Python data** |
|---|---|---|---|
| engine is "0 dependencies" (`pyproject.toml:37-44`: PyYAML is lazy and optional) | needs PyYAML or a hand loader | fine | fine |
| comments that quote IBM next to each value (today's convention) | yes | no | yes |
| checked when built (unknown key, wrong kind, a typo in a condition name) | needs a schema | needs a schema | dataclass `__post_init__` + mypy + import time |
| shared values (`_RESP`, `_FILE`, `_LOGICAL_MESSAGE`) | anchors | no | ordinary constants |
| readable by non-Python consumers | yes | yes | through the committed generated Java / C (`cics_spec regen`) and `emit --json` |

The only consumers outside Python are the Java runtime and the C stub. Both get **generated, committed** tables
(section 3), so a neutral file format buys nothing. A JSON export (`emit --json`) exists for tooling and review, and
is never committed.

### 2.1 The model

```python
# gitgalaxy/standards/cics/model.py (sketch; each field is checked in __post_init__)
Kind = Literal["area_in", "area_out", "area_inout",   # a data area: read / written / both
               "value", "name", "hhmmss", "pointer", "flag", "label", "cvda"]

@dataclass(frozen=True)
class Arg:
    kind: Kind
    width: int | None = None        # a name's 1-16 characters, a fullword ...
    inout_unless_literal: bool = False   # FLENGTH / LENGTH: in-out for a data area, in-only for a literal

@dataclass(frozen=True)
class Outcome:
    condition: str                  # a DFHRESP name (checked against resp.DFHRESP)
    resp2: int | None               # None: IBM documents none
    when: str                       # the IBM sentence, quoted
    writes: tuple[str, ...] = ()    # the output options written with this outcome (else left alone)

@dataclass(frozen=True)
class Refusal:
    why: str                        # the reason the user sees, word for word, on every side
    register: str | None = None     # "X17"
    at: Literal["translate", "run"] = "translate"

@dataclass(frozen=True)
class Fact:                         # a fact the runtime cannot know; whoever runs the task states it
    name: str                       # "startcode"
    java: str                       # "withStartcode"
    env: str                        # "GGCICS_STARTCODE"
    region_default: str | None      # the reference region's (cics-crucible SPEC 2) value, None: per task

@dataclass(frozen=True)
class Command:
    key: str                        # "GET CONTAINER": the form OPTIONS uses today
    ibm: Doc                        # topic title + verified URL
    status: Literal["modelled", "refused", "engine-only"]
    options: Mapping[str, Arg]                      # the options it honours
    refused: Mapping[str, Refusal] = {}             # options it refuses, by name
    default_refusal: str = "not modelled (no corpus program uses it)"
    groups: tuple[Group, ...] = ()                  # one_of / at_most_one / requires (2.2)
    outcomes: tuple[Outcome, ...] = ()              # every (condition, RESP2) it can raise
    runtime_refusals: tuple[Refusal, ...] = ()      # situations refused while running (at="run")
    state: tuple[str, ...] = ()                     # named state it reads or changes (section 4)
    facts: tuple[Fact, ...] = ()
    engine: EngineFacts | None = None               # what the scanner lifts out (3.1)
    impl: Impl | None = None                        # where the hand-written semantics live (3.3)
    register: str | None = None                     # its X-register entry
    event: str | None = None                        # the SPEC 6.2 event it records (a name only, section 6)
```

`Group` has three forms. `one_of("INTO", "NODATA")` requires exactly one, `at_most_one(...)` allows none or one,
and `requires("HOURS", any_of=("AFTER", "AT"))` makes one option depend on another. Each carries the message the
translator raises today.

### 2.2 Worked entry 1: GET CONTAINER (slice 1, #4575)

```python
GET_CONTAINER = Command(
    key="GET CONTAINER", status="modelled", register="X17", event=None,  # no event: a breadcrumb shows it
    ibm=Doc("EXEC CICS GET CONTAINER (CHANNEL)", url=...),               # verified in PR 1
    options={
        "CONTAINER": Arg("name", width=16),
        "CHANNEL":   Arg("name", width=16),     # omitted: the current channel
        "INTO":      Arg("area_out"),
        "FLENGTH":   Arg("area_inout", inout_unless_literal=True),
        #  in: "the length of the data to be read"; out: "the length of the data in the container"
        "NODATA":    Arg("flag"),
        **RESP_OPTIONS,                          # RESP / RESP2 area_out, NOHANDLE flag
    },
    refused={**CODEPAGE_REFUSALS,                # INTOCCSID / INTOCODEPAGE / CONVERTST -> X17's reason
             "SET": Refusal("the address of CICS's copy of the data (a pointer) is not modelled", "X17"),
             "BYTEOFFSET": Refusal("a partial GET is not modelled (no corpus program uses it)", "X17")},
    groups=(one_of("INTO", "NODATA", msg="GET CONTAINER needs one of INTO / NODATA"),),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "FLENGTH")),
        Outcome("LENGERR", 11, "the data is longer than INTO: truncated", writes=("INTO", "FLENGTH")),
        Outcome("CHANNELERR", 2, "the channel is not in the program's scope"),
        Outcome("INVREQ", 4, "no CHANNEL and no current channel"),
        Outcome("CONTAINERERR", 10, "the channel has no such container"),
    ),
    runtime_refusals=(
        Refusal("a channel an XCTL left behind: its scope is not documented", "X17", at="run"),
        Refusal("a blank name, or one with an embedded blank (IBM's illegal-character rules)", "X17", at="run"),
        Refusal("GET CONTAINER FLENGTH below zero", "X17", at="run"),
    ),
    state=("channel_scope",),
    engine=EngineFacts(resource="CONTAINER", access="read", name_option="CONTAINER",
                       qualifier_option="CHANNEL", record_option="INTO"),
    impl=Impl(translator="Cics.container", java="CicsTask.getContainer", c="GGCGETC",
              harness="_container_command"),
)
```

This one entry replaces `OPTIONS["GET CONTAINER"]`, `_CONTAINER_OPTIONS["GET"]`, three `_REFUSED_WHY` keys, the
INTO / NODATA check on both sides and the `settable` regex (now `inout_unless_literal`). It also replaces the
`writes` rule that says FLENGTH is set back only on NORMAL / LENGERR, the RESP2 list (prose today), the engine's
container row shape and the X17 option list (now checked, see 3.5).

### 2.3 Worked entry 2: START (slice 2, #4578)

```python
START = Command(
    key="START", status="modelled", register="X18", event="START",
    ibm=Doc("EXEC CICS START", url=...),
    options={
        "TRANSID": Arg("name", width=4), "TERMID": Arg("name", width=4), "REQID": Arg("name", width=8),
        "FROM": Arg("area_in"), "LENGTH": Arg("value"), "FLENGTH": Arg("value"),
        "INTERVAL": Arg("hhmmss"), "TIME": Arg("hhmmss"), "AFTER": Arg("flag"), "AT": Arg("flag"),
        "HOURS": Arg("value"), "MINUTES": Arg("value"), "SECONDS": Arg("value"),
        "PROTECT": Arg("flag"),
        "RTRANSID": Arg("name", width=4), "RTERMID": Arg("name", width=4), "QUEUE": Arg("name", width=8),
        **RESP_OPTIONS,
    },
    refused={
        "CHANNEL": Refusal("START CHANNEL: a started task's channel is not modelled (no corpus program uses it)", "X18"),
        "SYSID": REMOTE, "NOCHECK": Refusal("less error checking for a START on a remote system ...", "X18"),
        "USERID": Refusal("a started task's user (surrogate security) is not modelled", "X18"),
        "ATTACH": ..., "BREXIT": ..., "FMH": ...,   # today's _REFUSED_WHY text, word for word
    },
    groups=(
        required("TRANSID", msg="START without TRANSID"),
        at_most_one("INTERVAL", "TIME", "AFTER", "AT", msg="START {}: one expiry option"),
        requires(("HOURS", "MINUTES", "SECONDS"), any_of=("AFTER", "AT"), both_ways=True,
                 msg="START {}: HOURS / MINUTES / SECONDS go with AFTER / AT"),
        at_most_one("LENGTH", "FLENGTH"), requires(("LENGTH", "FLENGTH"), any_of=("FROM",),
                                                 msg="START LENGTH without FROM"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=()),
        Outcome("INVREQ", 4, "hours out of range"), Outcome("INVREQ", 5, "minutes out of range"),
        Outcome("INVREQ", 6, "seconds out of range"),
        Outcome("LENGERR", None, "LENGTH is not greater than zero, or past 32763"),
        Outcome("TRANSIDERR", None, "the transaction is not defined"),
        Outcome("TERMIDERR", None, "the terminal is not defined"),
        Outcome("IOERR", None, "A START operation uses a REQID name that exists ... only when FROM is also used"),
    ),
    runtime_refusals=(Refusal("START REQID of a request that exists, without FROM: not settled", "X18", at="run"),),
    state=("interval_requests", "virtual_clock"),
    engine=EngineFacts(task_verb="START", target_option="TRANSID", token_option="REQID",
                       record_option="FROM", timing=TIMING, channel_option="CHANNEL"),
    impl=Impl(translator="Cics.start", java="CicsTask.StartRequest/issueStart", c="GGCSTRT",
              harness="_interval_command"),
)
```

The order in which the out-of-range checks run (`issueStart`, forge `:802-813`) is **not** in the spec. It is
behaviour that X18 records as ASSUMED, and it stays code in both runtimes, which the crucible proves (section 4).

### 2.4 Worked entry 3: ASSIGN (slice 3, #4582), stated facts and per-option results

```python
ASSIGN = Command(
    key="ASSIGN", status="modelled", register="X19",
    ibm=Doc("EXEC CICS ASSIGN", url="https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-assign"),
    options={
        "APPLID": Arg("area_out", width=8), "SYSID": Arg("area_out", width=4),
        "ABCODE": Arg("area_out", width=4), "PROGRAM": Arg("area_out", width=8),
        "INVOKINGPROG": Arg("area_out", width=8), "CHANNEL": Arg("area_out", width=16),
        "STARTCODE": Arg("area_out", width=2), "USERID": Arg("area_out", width=8),
        "FACILITY": Arg("area_out", width=4),
        "SCRNHT": Arg("area_out", width=2, binary=True), "SCRNWD": Arg("area_out", width=2, binary=True),
        **RESP_OPTIONS,
    },
    refused=ASSIGN_REFUSED,          # the 18 entries of today's _ASSIGN_REFUSED_WHY, moved as they are
    outcomes=(
        Outcome("NORMAL", 0, "", writes=ALL_OUTPUTS),
        Outcome("INVREQ", 5, "The task is not associated with a terminal; or the task has no principal facility",
                writes=(), raised_by=("FACILITY", "SCRNHT", "SCRNWD")),   # X19: no area written on INVREQ
    ),
    facts=(
        Fact("startcode", java="withStartcode", env="GGCICS_STARTCODE", region_default=None,
             values=("TD", "S", "SD"), options=("STARTCODE",)),
        Fact("userid", java="withUserid", env="GGCICS_USERID", region_default="CICSUSER", options=("USERID",)),
        Fact("facility", java="(task terminal)", env="GGCICS_FACILITY", region_default=None,
             options=("FACILITY",)),
        Fact("screen", java="withScreen", env="GGCICS_SCREEN", region_default="24 80",
             options=("SCRNHT", "SCRNWD")),
    ),
    runtime_refusals=(Refusal("ASSIGN STARTCODE in a RUN TRANSID child task: IBM lists no code for it", "X19",
                              at="run"),),
    impl=Impl(translator="Cics.assign", java="CicsTask.assign*", c="GGCASGN", harness="_handle"),
)
```

`raised_by` records which options can raise a condition. That fact now lives in three hard-coded tuples: the
translator (`det/cics.py:659`), the harness (`equivalence_cics.py:243`) and the prose. `Fact` puts the stated-fact contract into the spec for the
first time: the runner (`cics_crucible.py`) builds `.withX(...)` and `GGCICS_X=` from it, and a runtime refuses an
unstated fact with the same text on both sides.

## 3. What each consumer reads

| consumer | reads | generated or table-driven | stays hand-written |
|---|---|---|---|
| engine (`cics_resources`, `cics_tasks`, `mainframe_boundary`, `jcics`, `hlasm_cics`) | `engine`, `options` (bare flags worth keeping), RESP noise | **table-driven** at import: `_FILE_VERBS`, `_CONTAINER_VERBS`, `_TASK_VERBS`, `_CHANNEL_VERBS`, `_FLAGS`, `_NOISE` are built from the spec | name resolution, STRING patterns, JCICS object tracking |
| det translator (`det/cics.py`) | `options`, `refused`, `groups`, `outcomes`, `Arg.kind`, `DFHRESP` | **table-driven**: `OPTIONS`, every `*_REFUSED_WHY`, `check_options` (one generic loop, no per-verb `if`), group checks, `DFHRESP`, `settable` | the per-command Java it emits (`Cics.container`, `Cics.start`, ...) |
| Java runtime (`CICS_TASK_JAVA`, `DetCics.java`) | `DFHRESP`, abend codes, `facts`, `runtime_refusals` texts | **generated and committed**: one `CicsSpec.java` (RESP / abend switches, refusal constants) that `DetCics.condition` / `resp`, `respName` and `abcodeFor` delegate to | channel scope, the start scheduler, browses: all semantics |
| C stub (`ggcics.c`) | the same | **generated and committed** `tests/equivalence/cics/ggcics_spec.h` (DFHRESP enum, `condition_abcode`, refusal strings) | GGC* entry points |
| stub translator (`equivalence_cics.py`) | `options`, `refused`, `groups`, `DFHRESP` | **table-driven** refusals and their reasons (it gains the reasons it lacks today) | GG-FLAGS marshalling per command |
| crucible runner (`cics_crucible.py`) | `facts`, `CONDITION_ABCODE` | **table-driven** fact wiring | the scheduler |
| X-register | `register`, `refused`, `runtime_refusals` | **checked, not generated**: `cics_spec check-register` fails when an option the spec refuses under Xnn is missing from Xnn's "Refused by name" text, or the text names one the spec does not refuse | all prose and IBM quotes |
| census (`cics_census.py`) | `status`, `refused` | classifies each option it counts as modelled, refused (with the reason) or unknown | |

### 3.1 Generated or table-driven: the rule

**Tables are generated. Semantics are not.** The generated Java and C files are committed. `cics_spec regen`
rewrites them, and a drift test fails, ratchet-style, when one is stale. The tables are small and rarely conflict,
reviewers see the Java / C diff, and committed ports and evidence can be reproduced from the repo alone. A value-to-value mapping (a RESP number, an abend code, an option set,
a refusal text) is generated or table-driven on every side. Anything with control flow stays hand-written in each
runtime: what happens to a container on APPEND, when a request expires, how a browse moves. The reasons:

1. Today's bugs are drift between copies of tables (`ABEND_FOR` 8 vs 10, the harness with no reasons, RESP2 5 in the
   translator), not semantic errors that one generated implementation would fix.
2. The two runtimes are **independent implementations**, and their agreement on a hand-traced log is the evidence.
   Generating both from one model would turn two witnesses into one.

### 3.2 Conformance: implementations versus the claim

PR 6 adds a run-time check in `cics_crucible.py` and `equivalence.py`. Every `(command, RESP, RESP2)` a side records
must appear in that command's `outcomes`, and every run-time refusal text must match a `runtime_refusals` entry. An
undeclared outcome fails the cell with "undeclared outcome", which is a bug in the spec or in the runtime. This
checks implementations against what we **claim** to model. It does not check them against what IBM says, which
stays the crucible's job.

### 3.3 `impl`: a pointer, not a contract

`Impl` names where the hand-written semantics live. A test checks that each name resolves: the Python attribute
exists, the Java method appears in `CICS_TASK_JAVA`, the C symbol appears in `ggcics.c`. This lets the census, the
slice skill and a reviewer jump from a command to its four implementations.

## 4. Semantics that do not fit a table

HANDLE CONDITION / IGNORE / PUSH / POP, HANDLE AID, file BROWSE (STARTBR / READNEXT / READPREV / RESETBR / ENDBR,
the RBA browse), channel scope across LINK / XCTL, the interval scheduler, SYNCPOINT backout and RETURN TRANSID are
state machines. The spec does **not** get a transition language. Instead:

- **State is named, not modelled.** `state=("browse[file]",)` on STARTBR / READNEXT / ENDBR, `("handle_table",)`
  on HANDLE / PUSH / POP and on every command that can raise, and `("channel_scope",)`. A named state is a
  vocabulary entry in `model.py` with a one-line meaning and the IBM topic. The census and the slice skill use it to
  say which commands share state ("a slice that adds RESETBR touches `browse[file]`: re-prove the browse cases").
- **Outcomes that depend on state are still enumerated.** For example, READNEXT with no STARTBR is INVREQ with its
  RESP2. `when` says in prose which state causes it, and the conformance check (3.2) holds both runtimes to the
  list.
- **Commands that only manipulate state** (HANDLE CONDITION, IGNORE, HANDLE AID) declare `options=CONDITIONS` or
  `AID_KEYS`, generated from `DFHRESP` and `DFHAID`, plus their refusals (IGNORE CONDITION ERROR, X16). Their
  translator handlers (`conditions`, `handle_aid_`) and the generated `outcome()` call stay code.
- **Why not a state-machine DSL:** it would be a third executable model of CICS. A third model is the thing most
  likely to be "used to generate expected logs, just this once" (section 6). It would also need its own proof.

## 5. PL/I and COBOL share the spec

The spec describes the **command**, not the host language. EXEC CICS is one grammar in both: options, conditions,
RESP / RESP2 and refusals are identical. What differs is the front end:

| | COBOL | PL/I |
|---|---|---|
| block end | `END-EXEC` | `;` (the engine closes it with END-EXEC, `core/pli_calls.py:13`) |
| `area_out` / `area_inout` | a data item, its PIC / USAGE | a variable, its DCL (`CHAR(n)`, `FIXED BIN(31)`) |
| implied LENGTH / FLENGTH | `LENGTH OF` the item | the declared size (open question 5) |
| `pointer` (SET) | `ADDRESS OF` / POINTER | `PTR`, `ADDR()`: central to PL/I, so LOAD / SET refusals matter more there |

Each front end maps `Arg.kind` to its own type system. The spec has one optional `hosts=("cobol", "pli")` field for
the rare option that exists in one language only. What PL/I gets at once, with no PL/I translator:

1. **Engine facts.** The spec has full `LOAD` / `RELEASE` entries (`PROGRAM`, `SET` pointer, `HOLD`) with
   `EngineFacts(edge="load", target_option="PROGRAM")` from PR 2. The engine emits the new load edges only in PR 8b,
   one engine batch **after the blind 4th-estate trial**: the golden master regen and score shifts are unwanted during
   the pre-freeze. PL/I and COBOL programs then gain load edges to the modules and tables they load, the gap named in
   1.2.
2. **The census.** `cics_census.py --pli` classifies PL/I options against the same spec, so we can measure how far a
   PL/I front end would get before anyone writes one.
3. **A PL/I det front end later** reads the same `options` / `groups` / `refused` and needs only its own `Arg.kind`
   mapping and emitters.

## 6. The crucible stays independent

The crucible's rule (AGENTS.md rules 2-3, `crucible_events.py`'s docstring) is that an expected log is traced by
hand from IBM's documentation and never derived from an implementation. The spec is an implementation artifact:
it says what **we** model. These rules keep it out of the oracle:

1. **No import.** `crucible_events.py` and every log-writing script import only the stdlib and `crucible_events`.
   `check-hand-derived` already rejects any other import. PR 1 adds a test that names `gitgalaxy.standards.cics`
   explicitly in the denied set, so a future allow-list cannot let it through.
2. **The oracle keeps its own tables.** `crucible_events.ABEND_FOR` and `EVENTS` mirror cics-crucible SPEC 6.2 and
   stay hand-maintained there. The spec's `event` field is a **name only**, so the spec never states an event's keys
   or values.
3. **Disagreement is a finding, not a sync.** A report-only test (`cics_spec cross-check-oracle`) lists where the
   spec and the oracle's tables differ. Today it would list AEZJ / AEZV, which are missing from `ABEND_FOR`. A person
   settles each difference against IBM's documentation and fixes whichever side is wrong, in its own repo. Neither
   side is ever generated from the other.
4. **Nothing the oracle needs comes from the spec.** A crucible case's NOTES.md quotes IBM directly. The spec's
   `ibm` URL is a convenience for implementers and is never cited as a source.
5. **The conformance check (3.2) does not replace the oracle.** "Every outcome is declared" can pass while the
   outcome is wrong. Only the hand-traced log catches that.

## 7. Migration: small PRs, identical verdicts at each step

"Identical verdicts" is the bar for every PR before PR 8b:

- the det survey's holes, deduplicated and without line numbers (`cics_census.py compare`), are byte-identical before
  and after;
- every `CicsError` message is unchanged, and so is every `Unsupported` message except PR 3's intended change, which
  adds the reasons and is rebaselined once;
- `pr_gates.py --ratchets` and the full gate pass;
- when a runtime changes, `proof_sweep.py --det-only --skip-db2` and `cics_crucible.py` give the same cells as the
  baseline.

Each PR is "Part of #4270".

| PR | content | consumers changed | verdict check |
|---|---|---|---|
| **1** | `gitgalaxy/standards/cics/` model + `resp.py` (DFHRESP, abend codes) + entries for the slice 1-4 commands, with today's text word for word; `cics_spec` CLI (`emit`, `check`, `regen`); **transitional equality tests** asserting the spec equals each existing copy (both Python DFHRESP tables, the Java switches scraped from `CICS_TASK_JAVA` / `DetCics.java`, the C enum, `OPTIONS`, the `*_REFUSED_WHY` tables, `_CONTAINER_OPTIONS`, the harness's refused tuples), each deleted in the PR that makes its copy import the spec; the crucible import-denial test | none | unit tests only |
| **2** | full entries for the other 34 `OPTIONS` commands (PR 1 has the 9 of slices 1-4) + LOAD / RELEASE (45 in all); **name-only refusal entries** (name, IBM URL, reason) for the other CICS application (API) commands, 206 of them (counted in PR 2: IBM's CICS TS 6.x command summary lists 336 API topics, 259 command names once the device / role variants are one name; 44 have full entries, 9 are forms of a modelled command; see `commands/api.py`), with no SPI / system-programming commands, so an unknown verb gets a specific reason; the translator imports `OPTIONS`, every refusal table, `check_options` (the five special cases become per-command `refused` entries), groups and `DFHRESP` from the spec | translator | messages unchanged except a whole-verb refusal now naming its reason (rebaselined); survey compare identical in translated / holes counts; ratchets |
| 3 | `equivalence_cics.py` refusals / options / DFHRESP from the spec. `Unsupported` carries the same reason as `CicsError`, the one intended change: one rebaseline of message snapshots, with feature keys and verdicts unchanged | stub translator | feature keys identical; cobol-stub cells identical |
| 4 | **generated, committed** runtime tables: `CicsSpec.java` (delegated to by `DetCics` condition / resp, `respName`, `abcodeFor`) and `ggcics_spec.h`; `cics_spec regen` + a drift test that fails on a stale file (ratchet-style, in `pr_gates.py --ratchets`) | both runtimes | `proof_sweep --det-only`; crucible cells identical |
| 5 | `Fact` wiring in `cics_crucible.py`; refusals of unstated facts share their text | runner, both runtimes | crucible cells identical |
| 6 | outcome conformance check (3.2), report-only for one week, then an undeclared `(RESP, RESP2)` fails the crucible cell; the spec-vs-oracle cross-check (section 6 rule 3) in CI, report-only | harness, CI | must find 0 undeclared outcomes on the current baseline before it gates |
| 7 | `check-register` in `pr_gates.py`; the slice skill's checklist says "spec entry first", with full entries only where the blocker ranking (`cics_census.py blockers`, #4587) calls for a command | docs, skill | — |
| 8a | engine walkers import their verb tables from the spec (same rows; may land before the trial) | engine | fact_crosscheck ledger identical |
| 8b | **after the blind 4th-estate trial**, one engine batch of new edge kinds: LOAD, START TRANSID, MQ queues, dynamic CALL (golden master regenerated with `crucible_check.py --update --yes` + `scope_check.py --expect`) | engine | golden diff and score shifts reviewed |

PRs 1-2 are the first two: PR 1 changes no behaviour and makes every existing copy provably equal to the spec. PR 2
then removes the largest source of drift, the translator's tables. Each later slice adds a spec entry and deletes a
table edit.

**After migration, one slice** consists of: a spec entry (options, refusals, groups, outcomes, facts, register), the
translator emitter, the two runtime semantics, the hand-traced crucible case and the X-register prose. It no longer
needs edits to OPTIONS, the harness lists, the DFHRESP / abend switches or the fact wiring. Measured on slices 1-3,
that removes roughly 15-25% of each slice's diff and every place two copies can disagree.

## 8. Risks

- **Message drift breaks survey comparisons.** `cics_census.py compare` deduplicates holes by text. PR 2 must
  reproduce every option-level message exactly (the equality tests from PR 1 are the safety net); the only text
  changes are whole-verb refusals gaining their name-only entry's reason (PR 2) and the stub's reasons (PR 3), each
  rebaselined once.
- **A stale committed generated file.** It is mitigated by the drift test in the ratchets, a "generated from
  gitgalaxy/standards/cics by `cics_spec regen`, do not edit" banner, and generating only switches and constants.
- **The spec becomes the oracle by accident.** Section 6's rules 1-3 are tests, not conventions. Nothing in the spec
  is shaped like an expected log.
- **Over-modelling.** A field nobody reads goes stale. Every field in `model.py` must have a consumer in sections
  3-5 before it is added. `state` and `impl` are the weakest and could drop to comments if the census and skill do
  not use them.
- **Engine import cost and the "0 dependencies" claim.** The spec is about 2-3k lines of frozen data, imported lazily
  by the CICS walkers only. It is stdlib only.
- **Cross-repo.** cics-crucible's schema and `validate.py` do not change. Only the report in section 6 rule 3 looks
  at both repos.

## 9. Decisions (2026-10-06)

1. **Location: `gitgalaxy/standards/cics/`.** It is a neutral, data-only package that the engine owns and ships, and
   every consumer imports it directly. There are no separate engine tables and no drift test between copies. No
   CODEOWNERS entry (the owner is the only maintainer). Siblings (`standards/sql/`, intrinsic functions, file
   status) follow the same pattern later.
2. **Generated runtime tables are committed**: the Java RESP / abend switches with the refusal constants, and C
   `ggcics_spec.h`. A regenerate command and a ratchet-style drift test fail when a file is stale.
3. **The stub's refusal text matches the translator's.** `Unsupported` carries the same reason as `CicsError`. The
   messages change and the verdicts do not, at the cost of one rebaseline of message snapshots.
4. **Coverage.** The 43 modelled commands and LOAD / RELEASE (45) get full entries. The other CICS application (API)
   commands, 206 (PR 2's count of IBM's command summary; this page said "about 125" before), get name-only refusal entries (name, IBM URL, reason). SPI / system-programming commands are
   left out. A name-only entry becomes a full one only when the blocker ranking (`cics_census.py blockers`, #4587)
   calls for that command.
5. **New engine edge kinds wait.** LOAD, START TRANSID, MQ queues and dynamic CALL come as one engine batch (PR 8b)
   **after the blind 4th-estate trial**. PR 8a (same rows, ledger identical) may go before it. The `hosts` field
   stays, since it costs little.
6. **The conformance check gates.** After the report-only week, an undeclared `(RESP, RESP2)` fails a crucible cell.
7. **The spec-vs-oracle cross-check runs in CI, report-only.** The missing AEZJ / AEZV in `ABEND_FOR` stay the
   crucible's own decision.

## 10. Rough effort

Agent-days, each PR with its proofs:

| PR | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8a | 8b |
|---|---|---|---|---|---|---|---|---|---|
| days | 1.5 | 3 | 1 | 2 | 0.5 | 1 | 0.5 | 1 | 2 |

That totals about 12.5 agent-days. PR 2 grows by the 206 name-only entries, PR 4 by the committed files and their
drift test, and PR 8b by its wider edge batch, which comes after the trial. PRs 1-2 deliver most of the value: about
4.5 days.
