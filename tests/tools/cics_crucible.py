"""
#3989: the CICS crucible runner -- gitgalaxy's CICS pipeline measured against cics-crucible.

cics-crucible (squid-protocol/cics-crucible, pinned in tests/_cics_crucible_pin.py) is a set of
small, original, adversarial CICS applications. Each scenario of each case ships a hand-written
expected event log: what IBM CICS would do, from IBM's documentation (the crucible's SPEC.md,
format `cics-crucible/1`). That log is the oracle. This runner puts each case through the
pipeline and compares, cell by cell:

  engine-facts   (case)  the scan recorded the case's programs, CSD transactions, BMS maps, and
                         every CICS command its expected logs show (SEND/RECEIVE MAP, LINK, XCTL,
                         RETURN TRANSID, START, RETRIEVE, CANCEL, READQ/WRITEQ TS, ABEND, the
                         HANDLE ABEND exits taken)
  forge-compile  (case)  refactor, cobol-to-java (target config h2), `mvn compile`
  cobol-stub     (scenario)  the COBOL, translated by tests/tools/equivalence_cics.py and run
                         task by task on the stub runtime (tests/equivalence/cics/ggcics.c)
  java           (scenario)  the generated project's services, each task a CicsTask through
                         runTask(), driven by a generated EquivalenceRunTest -- the services as
                         generated (their runTask bodies are skeletons until ported)
  java-ported    (scenario)  the same, with the case's committed ports laid over the services
                         (tests/cics_crucible/ports/<case>/<PROGRAM>/overlay, each proven by this
                         runner through the porting loop and kept with its provenance.json); a case
                         with no model port runs its deterministic port, tests/cics_crucible/det-ports
  java-facade    (scenario)  #4343: the ported project again, each task entered through the program's
                         deployed entry point -- its Spring facade: handleTransaction, and handleLink for
                         a program a LINK / XCTL reaches -- with the scenario's region joined
                         (CicsTask.join), so the facade's task is the scenario's own task. A program
                         with no facade runs through runTask; the proof report lists, per program, the
                         entry points its passing scenarios ran (`entries`). #4965: each scenario runs a
                         second time through the byte-carrying overload handleTransaction(String, [T,] byte[])
                         where a service has one -- the previous task's RETURN bytes in -- and the bytes
                         lastAnswerBytes() answers (converted from the runtime page, #5053) are what the RETURN's COMMAREA is compared by (a port
                         that passes none answers null: the DTO is compared as before).

Proving one program's port for the porting loop (gitgalaxy/tools/cobol_to_java/port_runner.py):

    port_runner prove <project> --ticket PCWIZ --command "python tests/tools/cics_crucible.py \\
        --cases pc-wizard --sides java-ported --ports <project>/ai_agent_jobs/ports --overlay {port_dir} \\
        --program PCWIZ --report-dir {report_dir} --keep {report_dir}/work"

runs every scenario that runs PCWIZ with the latest port of each of the case's programs, writes a
report.json (per scenario 1/1 or 0/1, and the first divergences as `feedback` for `run --feedback`),
and exits 0 only when every one of them passes.

Both scenario sides are driven the same way (SPEC section 4, terminal tasks): a step starts the
TRANSID and COMMAREA of the previous task's RETURN, or else the transaction id typed as text;
an XCTL runs its target in the same task. Each is compared with the expected log exactly
(tests/tools/cics_crucible_compare.py): a cell passes, fails at its first divergence, or is
`unsupported: <feature>` when the harness cannot model what the scenario needs -- a command the
translator refuses (`Unsupported`), an event CicsTask cannot record, a START-triggered task.

The baseline (tests/cics_crucible/baseline.json) is a ratchet ledger of every cell that does
not pass, with its status and reason. `--ci` fails on a cell not in it, and on a ledgered cell
that now passes (lower the ledger: `--update-baseline`), so the ledger only shrinks. Phase 3 of
#3989 closes the cells; docs/language_status/cics_crucible.md (written with the baseline) groups
them by trap, side, failure reason and missing feature.

#5053: every event that carries a COMMAREA's bytes is compared by those bytes, not the DTO's (a numeric DISPLAY field
holding spaces reads as a number): LINK and XCTL by the event's `area`, a RETURN by `answer_bytes`, a LINKed
program's RETURN `caller_commarea` by `area_bytes` (an XCTL chain's by the first program's kept bytes), START / RETRIEVE
by their data; all in the runtime page, converted to CCSID 037. A program with no bytes overload falls back to the DTO.
Not covered: a CHANNEL's containers (SPEC 6.2 has no container event; seen only through what a program logs).

#4023: a passing proof only proves the paths its scenarios run. The cobol-stub side compiles the COBOL
-ftraceall and traces every task (tests/tools/cobol_coverage.py), so per program the report says how much
the passing scenarios execute -- live paragraphs and sections entered, IF / EVALUATE outcomes taken, HANDLE
labels entered; dead code (the engine's reachability) apart -- lists the live code no scenario reaches (the
scenarios to propose to the crucible), and gives each ported program its claim: "proven on N scenarios,
covering X/Y paragraphs and A/B branches". tests/cics_crucible/coverage.json keeps, per scenario, what it
executed; `--ci` fails when that moves (lost or gained) until `--update-baseline` records it. A port proof
(--report-dir) carries its program's claim from that ledger.

    python tests/tools/cics_crucible.py --ci                    # measure, check the ratchet
    python tests/tools/cics_crucible.py --update-baseline       # record today's cells + the report
    python tests/tools/cics_crucible.py --cases pc-wizard --sides engine-facts java --keep /tmp/w

#4049 (the test-strengthening loop): STRENGTHENED scenarios. A crucible case's scenarios and their expected logs
are the crucible's, written by hand from IBM's documentation. A mutation survivor (#4047) that no scenario reaches
needs more inputs, and the rule of the loop is that a model proposes INPUTS only: the expected result comes from
running the COBOL. So tests/cics_crucible/strengthened/<case>/case.json holds extra scenarios for a case (the
crucible's scenario format, plus a step's `faults`, below), and tests/cics_crucible/strengthened/<case>/expected/
<scenario>.json each one's log as the COBOL produced it on the stub runtime, written by

    python tests/tools/cics_crucible.py --cases pc-wizard --derive-expected      # never by hand

(the log says so in `derived`). `--strengthened` adds them to their cases, so the java-ported side is proven
against them too; a derived log is checked like any other (the cobol-stub side must still reproduce it). They are
held for review: they are not in the baseline or the coverage ledger, and `--ci` / `--update-baseline` refuse
`--strengthened` until a person has approved them.

A scenario's `faults` (#4049) plans CICS conditions, as the equivalence harness's CICS scenarios do
(tests/tools/equivalence_cics.py, FAULT_COMMANDS: which commands, and the IBM conditions each may be given), for
every task of the TRANSID a fault names in `task` -- a terminal step's task or a STARTed one:
[{"task": "PC03", "cmd": "WRITEQ-TS", "queue": "PCLEDGER", "nth": 1, "resp": "INVREQ"}]. Each task counts its own
commands; the stub (faults.cfg) and CicsTask.withFaults read the same plan, and the planned command does nothing
but return the condition. A derived log records the faults that fired; one that never fired refuses the log.

A typed-transid step's `commarea` (#4443) is `{"hex": <the record, in the runtime page>, "length": n}`: the task is
entered directly with the first n bytes (EIBCALEN n), for a program only a RETURN TRANSID otherwise reaches with a
short or odd area. The java plan carries the record decoded through the DTO the facade takes (seeded_step).

Needs: the crucible checkout (CICS_CRUCIBLE_PATH, else ../cics-crucible beside the main gitgalaxy
checkout) at the pin; for cobol-stub, Docker and the GnuCOBOL image (tests/equivalence/
gnucobol.Dockerfile); for forge-compile / java, a JDK 17 and Maven (`--offline` for mvn -o).
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import dataclasses
import datetime
import functools
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from collections.abc import Iterator
from typing import Any

HERE_TOOLS = Path(__file__).resolve().parent
REPO_ROOT = HERE_TOOLS.parents[1]
sys.path.insert(0, str(HERE_TOOLS))
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT))
from maven_exe import JVM_SHORT_RUN_FLAGS, maven_utf8_env, mvn_executable, run_decoded  # noqa: E402

import cics_crucible_compare as cc  # noqa: E402
import cobol_coverage as cov  # noqa: E402
from crucible_shard_plan import CASE_SECONDS, DEFAULT_CASE_SECONDS  # noqa: E402
from _cics_crucible_pin import PATH_ENV, PINNED_REF, pin_mismatch  # noqa: E402
from gitgalaxy.core.ebcdic_codecs import java_charset_name  # noqa: E402

RUNTIME_PAGE = (
    "latin-1"  # #5053: the page the Java runtime's record bytes are in (the stub runtime's; SPEC logs are cp037)
)

LEDGER_DIR = REPO_ROOT / "tests" / "cics_crucible"
BASELINE = LEDGER_DIR / "baseline.json"
COVERAGE = LEDGER_DIR / "coverage.json"  # #4023: the COBOL each passing cobol-stub scenario executes, a ratchet
COVERAGE_FORMAT = "cics-crucible-coverage/1"
REPORT = REPO_ROOT / "docs" / "language_status" / "cics_crucible.md"
BASELINE_FORMAT = "cics-crucible-baseline/1"
STUB_DIR = REPO_ROOT / "tests" / "equivalence" / "cics"
# #4270 slice 3: the reference region's (SPEC section 2) default user -- DFLTUSER's default, nobody signs on -- and its
# terminal's 3270 screen, for ASSIGN USERID / SCRNHT / SCRNWD (the generated Java test states the same)
REGION_USERID = "CICSUSER"
REGION_SCREEN = (24, 80)
# #4904: timeouts for Container docker operations
CONTAINER_START_TIMEOUT = 60  # seconds: ~5-10x normal docker run -d container startup (~2-5s under load)
CONTAINER_EXEC_TIMEOUT = 300  # seconds: hang guard, well above a cobc compile under CI load (~10s) or scenario task run (<1s); bounds runaway loops
CONTAINER_STOP_TIMEOUT = 30  # seconds: ~10x normal docker rm -f (<2s)

# SPEC 6.2: the abend code CICS gives an unhandled condition (the AEIA topic of IBM's abend codes).
CONDITION_ABCODE = {"NOTFND": "AEIM", "LENGERR": "AEIV", "ITEMERR": "AEIZ", "QIDERR": "AEYH", "MAPFAIL": "AEI9",
                    "ENDDATA": "AEI2", "PGMIDERR": "AEI0", "INVREQ": "AEIP", "IOERR": "AEIQ",
                    # #4270: IBM abend codes AEZJ / AEZV ("CONTAINERERR / CHANNELERR condition not handled")
                    "CONTAINERERR": "AEZJ", "CHANNELERR": "AEZV",
                    # #4648: IBM abend code AEY7 ("NOTAUTH condition not handled")
                    # #4951: container browse -- GETNEXT / ENDBROWSE CONTAINER's TOKENERR, ILLOGIC and END
                    "NOTAUTH": "AEY7", "TOKENERR": "AEZL", "ILLOGIC": "AEIU", "END": "AEXK"}  # fmt: skip
SEND_OPTIONS = ("ERASE", "ERASEAUP", "MAPONLY", "DATAONLY", "FREEKB", "ALARM", "FRSET", "CURSOR", "WAIT", "LAST")

# What each scenario side records (see cics_crucible_compare.Capabilities).
# #4001: SEND MAP as BMS sends it -- per field its attribute, data and extended attributes and where
# each comes from, the fields DATAONLY leaves out, and the cursor (cics_bms.send_map)
BMS_KEYS = frozenset({"map", "mapset", "options", "cursor", "fields", "fields.omission"} |
                     {f"fields.{k}" for k in cc.FIELD_KEYS})  # fmt: skip
# #4006 / #4270: what START / RETRIEVE events carry on both sides (the data options only where the program named them)
_START_KEYS = frozenset(
    "transid termid interval time from reqid protect resp resp2 expires rtransid rtermid queue".split()
)
_RETRIEVE_KEYS = frozenset("resp length data rtransid rtermid queue".split())
# #4767 zECS (X37, X38): an `http` task's request body and response, on both sides
_WEB_RECEIVE_KEYS = frozenset("resp resp2 length data".split())
_WEB_SEND_KEYS = frozenset("status statustext mediatype from resp resp2".split())
_WEB_HEADER_KEYS = frozenset("name value resp resp2".split())  # #4767 (X38): a response header the task wrote
# #4767 (X35): a task's client-side WEB OPEN / CONVERSE / CLOSE against a stated origin peer, on both sides
_WEB_CLIENT_KEYS = {
    "WEB-OPEN": frozenset("host scheme resp resp2".split()),
    "WEB-CONVERSE": frozenset("method path status tolength into resp resp2".split()),
    "WEB-CLOSE": frozenset("resp resp2".split()),
}
COBOL_CAPS = cc.Capabilities(
    layer="stub",
    task_keys=frozenset(cc.TASK_KEYS) | {"end"},
    events={
        "SEND-MAP": BMS_KEYS,
        "SEND-TEXT": frozenset({"text", "length", "options"}),
        "SEND-CONTROL": frozenset({"options", "cursor"}),  # #4413
        "RECEIVE-MAP": frozenset({"map", "mapset", "resp"}),
        "RECEIVE": frozenset({"resp", "length", "data"}),
        "RETURN": frozenset(
            {"level", "transid", "commarea", "caller_commarea", "immediate", "channel", "resp", "resp2"}
        ),
        "LINK": frozenset({"target", "length", "commarea", "resp", "resp2"}),
        "XCTL": frozenset({"target", "length", "commarea", "resp", "resp2"}),
        "ABEND": frozenset({"abcode", "cause", "condition", "outcome", "exit"}),
        # #4443 A0b: what ggcics_filecontrol.c's read_event / unlock_event and ggcics.c's rewrite_event record
        "READ": frozenset({"file", "ridfld", "update", "set", "resp", "resp2", "length", "data"}),
        "REWRITE": frozenset({"file", "data", "resp", "resp2"}),
        "UNLOCK": frozenset({"file", "resp", "resp2"}),
        # #6262: what ggcics_filecontrol.c's browse_event and endbr line record (an RBA browse's `rba=` lines: unmodelled)
        "STARTBR": frozenset({"file", "ridfld", "mode", "resp", "resp2"}),
        "READNEXT": frozenset({"file", "ridfld", "set", "resp", "resp2", "length", "data"}),
        "READPREV": frozenset({"file", "ridfld", "set", "resp", "resp2", "length", "data"}),
        "ENDBR": frozenset({"file", "resp", "resp2"}),
        # #6262: what ggcics.c's file_event records for GGCWRIT and ggcics_filecontrol.c's GGCDELT
        "WRITE": frozenset({"file", "ridfld", "data", "resp", "resp2"}),
        "DELETE": frozenset({"file", "ridfld", "generic", "resp", "resp2"}),
        "READQ-TS": frozenset({"queue", "item", "resp", "length", "data"}),
        "WRITEQ-TS": frozenset({"queue", "data", "resp", "item"}),
        # #5079 (X57): what ggcics_transientdata.c's GGCWRTD / GGCRDTD / GGCDLTD record
        "READQ-TD": frozenset({"queue", "resp", "length", "data"}),
        "WRITEQ-TD": frozenset({"queue", "data", "resp"}),
        "DELETEQ-TD": frozenset({"queue", "resp"}),
        "WRITE-OPERATOR": frozenset({"data", "resp"}),  # #4270 zECS (X32)
        "START": _START_KEYS,
        "RETRIEVE": _RETRIEVE_KEYS,
        "CANCEL": frozenset({"reqid", "resp"}),
        "RUN": frozenset({"transid", "resp", "resp2"}),  # #4270
        "WEB-RECEIVE": _WEB_RECEIVE_KEYS,  # #4767 (X37, X38)
        "WEB-SEND": _WEB_SEND_KEYS,
        "WEB-WRITE-HTTPHEADER": _WEB_HEADER_KEYS,
        **_WEB_CLIENT_KEYS,
    },
    ts_queues=True,
    td_queues=True,  # #5079: seeded and read back from the stub's td-<hex> directories
    start_tasks=True,
    http_tasks=True,
)
JAVA_CAPS = cc.Capabilities(
    layer="CicsTask",
    task_keys=frozenset(cc.TASK_KEYS) | {"end"},
    events={
        "SEND-MAP": BMS_KEYS,  # #4001: resolved like the stub's, from what CicsTask.sendMap recorded
        "SEND-TEXT": frozenset({"text", "length", "options"}),
        "SEND-CONTROL": frozenset({"options", "cursor"}),  # #4413
        "RECEIVE": frozenset({"resp", "length", "data"}),
        "RECEIVE-MAP": frozenset({"map", "mapset", "resp"}),  # #4009
        "RETURN": frozenset(
            {"level", "transid", "commarea", "caller_commarea", "immediate", "channel", "resp", "resp2"}
        ),
        "LINK": frozenset({"target", "length", "commarea", "resp", "resp2"}),
        "XCTL": frozenset({"target", "length", "commarea", "resp", "resp2"}),
        "ABEND": frozenset({"abcode", "cause", "condition", "outcome", "exit"}),
        "READQ-TS": frozenset({"queue", "item", "resp", "length", "data"}),
        "WRITEQ-TS": frozenset({"queue", "data", "resp", "item"}),
        # #4443, #6262: what CicsTask.readInto / readSetEvent / rewriteFrom / unlock record
        "READ": frozenset({"file", "ridfld", "update", "set", "resp", "resp2", "length", "data"}),
        "REWRITE": frozenset({"file", "data", "resp", "resp2"}),
        "UNLOCK": frozenset({"file", "resp", "resp2"}),
        # #6262: what CicsTask.startbrEvent / readnextInto / readprevInto / endbrEvent record
        "STARTBR": frozenset({"file", "ridfld", "mode", "resp", "resp2"}),
        "READNEXT": frozenset({"file", "ridfld", "set", "resp", "resp2", "length", "data"}),
        "READPREV": frozenset({"file", "ridfld", "set", "resp", "resp2", "length", "data"}),
        "ENDBR": frozenset({"file", "resp", "resp2"}),
        # #6262: what CicsTask.writeEvent / deleteEvent (and the generic, held, token forms) record
        "WRITE": frozenset({"file", "ridfld", "data", "resp", "resp2"}),
        "DELETE": frozenset({"file", "ridfld", "generic", "resp", "resp2"}),
        "WRITE-OPERATOR": frozenset({"data", "resp"}),  # #4270 zECS (X32)
        "START": _START_KEYS,
        "RETRIEVE": _RETRIEVE_KEYS,
        "CANCEL": frozenset({"reqid", "resp"}),
        "RUN": frozenset({"transid", "resp", "resp2"}),  # #4270
        "WEB-RECEIVE": _WEB_RECEIVE_KEYS,  # #4767 (X37, X38)
        "WEB-SEND": _WEB_SEND_KEYS,
        "WEB-WRITE-HTTPHEADER": _WEB_HEADER_KEYS,
        **_WEB_CLIENT_KEYS,
    },
    ts_queues=True,
    start_tasks=True,
    http_tasks=True,
)


# ---- plumbing ----------------------------------------------------------------------------------
@contextlib.contextmanager
def quiet(log: Path) -> Iterator[None]:
    """Send this process's (and its children's) stdout / stderr to `log`: the scanner, refractor and
    generator print banners that would bury the runner's own output."""
    log.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout.flush()
    sys.stderr.flush()
    saved = os.dup(1), os.dup(2)
    with open(log, "ab") as f:
        os.dup2(f.fileno(), 1)
        os.dup2(f.fileno(), 2)
        try:
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(saved[0], 1)
            os.dup2(saved[1], 2)
            os.close(saved[0])
            os.close(saved[1])


def _tail(text: str, n: int = 12) -> str:
    return "\n".join(text.strip().splitlines()[-n:])


def crucible_path(arg: Path | None) -> Path:
    """--crucible, else $CICS_CRUCIBLE_PATH, else ../cics-crucible beside the main checkout."""
    if arg:
        return arg
    if os.environ.get(PATH_ENV):
        return Path(os.environ[PATH_ENV])
    common = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--git-common-dir"],  # noqa: S603, S607
                            capture_output=True, text=True, check=False).stdout.strip()  # fmt: skip
    main = (
        (Path(common) if Path(common).is_absolute() else REPO_ROOT / common).resolve().parent if common else REPO_ROOT
    )
    return main.parent / "cics-crucible"


def crucible_ref(path: Path) -> str | None:
    """The checkout's tag when HEAD is exactly one (`v0.1.0 (0c942cb8)`), else its commit."""

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True,  # noqa: S603, S607
                              check=False).stdout.strip()  # fmt: skip

    commit = git("rev-parse", "HEAD")
    tag = git("describe", "--tags", "--exact-match", "HEAD") if commit else ""
    return (f"{tag} ({commit[:8]})" if tag else commit) or None


# ---- the case's layouts and maps ---------------------------------------------------------------
def case_context(case: cc.Case) -> cc.Context:
    """The comparison's view of the case: each layout's fields (its COPY members found in the case's
    copy directories, then the harness's DFH stand-ins), and each map's named output fields with
    their lengths."""
    import equivalence_common as common

    dirs = [case.dir / d for d in case.data["sources"]["copy"]] + [STUB_DIR]
    layouts: dict[str, list[dict[str, Any]]] = {}
    for name, spec in case.data["layouts"].items():
        try:
            fields = common.layout_fields(case.dir, spec["source"], spec["record"], copy_dirs=dirs)
        except common.LayoutError as e:
            raise cc.CaseError(f"{case.id}: layout {name}: {e}") from e
        fields = [f for f in fields if f["name"] != "FILLER"]
        if not fields:
            raise cc.CaseError(f"{case.id}: layout {name} ({spec['record']} in {spec['source']}) has no fields")
        layouts[name] = fields
    maps: dict[str, dict[str, int]] = {}
    for name, spec in case.data["maps"].items():
        fields = common.layout_fields(case.dir, spec["copybook"], f"{name}O")
        maps[name] = {f["name"][:-1]: f["bytes"] for f in fields if f["name"].endswith("O")}
    return cc.Context(layouts, maps)


# ---- engine facts ------------------------------------------------------------------------------
def fact_checks(case: cc.Case) -> list[tuple[str, dict[str, Any]]]:
    """What the scan must have recorded: (label, what) per program, CSD transaction, BMS map, and
    each distinct CICS command the expected logs show a program issue."""
    checks: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()

    def add(label: str, what: dict[str, Any]) -> None:
        if label not in seen:
            seen.add(label)
            checks.append((label, what))

    for p in case.programs:
        add(f"program {p}", {"kind": "program", "program": p})
    for t, p in sorted(case.csd["transactions"].items()):
        add(f"transaction {t} -> {p}", {"kind": "transaction", "transid": t, "program": p})
    for m, spec in sorted(case.data["maps"].items()):
        add(f"map {spec['mapset']}.{m}", {"kind": "map", "map": m, "mapset": spec["mapset"]})
    for sid in sorted(case.expected):
        for task in case.expected[sid]["tasks"]:
            for ev in task["events"]:
                kind, prog = ev["event"], ev["program"]
                if kind in ("SEND-MAP", "RECEIVE-MAP"):
                    verb = kind.split("-")[0]
                    add(f"{prog}: {verb} MAP({ev['map']}) MAPSET({ev['mapset']})",
                        {"kind": "resource", "program": prog, "verb": verb, "res": "MAP", "name": ev["map"],
                         "qualifier": ev["mapset"]})  # fmt: skip
                elif kind in ("READQ-TS", "WRITEQ-TS"):
                    verb = kind.split("-")[0]
                    add(f"{prog}: {verb} TS QUEUE({ev['queue']})",
                        {"kind": "resource", "program": prog, "verb": verb, "res": "QUEUE", "name": ev["queue"],
                         "qualifier": "TS"})  # fmt: skip
                elif kind == "READ":
                    add(f"{prog}: READ FILE({ev['file']})",
                        {"kind": "resource", "program": prog, "verb": "READ", "res": "FILE", "name": ev["file"],
                         "qualifier": None})  # fmt: skip
                elif kind in ("LINK", "XCTL"):
                    add(
                        f"{prog}: {kind} PROGRAM({ev['target']})",
                        {"kind": "call", "program": prog, "verb": kind, "target": ev["target"]},
                    )
                elif kind == "RETURN" and ev.get("level") == 1 and ev.get("transid"):
                    add(
                        f"{prog}: RETURN TRANSID({ev['transid']})",
                        {"kind": "call", "program": prog, "verb": "RETURN TRANSID", "target": ev["transid"]},
                    )
                elif kind == "START":
                    add(
                        f"{prog}: START TRANSID({ev['transid']})",
                        {"kind": "task", "program": prog, "verb": "START", "name": ev["transid"]},
                    )
                elif kind in ("RETRIEVE", "CANCEL"):
                    add(f"{prog}: {kind}", {"kind": "task", "program": prog, "verb": kind, "name": None})
                elif kind == "ABEND" and ev["cause"] == "command":
                    add(
                        f"{prog}: ABEND ABCODE({ev['abcode']})",
                        {"kind": "handler", "program": prog, "handler": "ABEND", "value": ev["abcode"]},
                    )
                if kind == "ABEND" and ev.get("outcome") == "exit":
                    ex = ev["exit"]
                    add(
                        f"{ex['program']}: HANDLE ABEND LABEL({ex['label']})",
                        {"kind": "handler", "program": ex["program"], "handler": "HANDLE_ABEND", "value": ex["label"]},
                    )
    return checks


def _has_fact(ir: Any, what: dict[str, Any]) -> bool:
    files = [f for f in ir.files.values() if f.language == "cobol" and what.get("program") in f.program_ids]
    kind = what["kind"]
    if kind == "program":
        return bool(files)
    if kind == "transaction":
        return any(t.transid.upper() == what["transid"] and (t.program or "").upper() == what["program"]
                   for f in ir.files.values() for t in f.transactions)  # fmt: skip
    if kind == "map":
        for f in ir.files.values():
            mapsets = {s.ordinal: (s.name or "").upper() for s in f.screen_fields if s.kind == "mapset"}
            if any(s.kind == "map" and (s.name or "").upper() == what["map"] and mapsets.get(s.parent_ordinal) == what["mapset"]
                   for s in f.screen_fields):  # fmt: skip
                return True
        return False
    for f in files:
        if kind == "resource":
            for r in f.cics_resources:
                qual = r.mapset if r.kind == "MAP" else r.qualifier
                if (r.verb.upper() == what["verb"] and r.kind == what["res"] and what["name"] in r.names
                        and (what["qualifier"] is None or (qual or "").upper() == what["qualifier"])):  # fmt: skip
                    return True
        elif kind == "call":
            if any(c.verb.upper() == what["verb"] and (c.target or "").upper() == what["target"] for c in f.calls):
                return True
        elif kind == "task":
            if any(
                t.verb.upper() == what["verb"] and (what["name"] is None or t.matches(what["name"]))
                for t in f.cics_tasks
            ):
                return True
        elif kind == "handler":
            if any(h.kind == what["handler"] and ((h.target if what["handler"] == "HANDLE_ABEND" else h.condition) or "")
                   .strip("'\"").upper() == what["value"].upper() for h in f.uow_handlers):  # fmt: skip
                return True
    return False


def engine_facts(case: cc.Case, work: Path) -> cc.Verdict:
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

    # A copy outside any git checkout: inside one, the census takes only git-tracked files, so what
    # the scan sees would depend on the checkout's state rather than on the case.
    src = work / case.id
    if src.exists():
        shutil.rmtree(src)
    shutil.copytree(case.dir, src, ignore=shutil.ignore_patterns(".git"))
    try:
        with quiet(work / "scan.log"):
            ir = load_galaxy_ir(scan_to_db(src, work / "scan"))
    except Exception as e:  # noqa: BLE001 -- any scan failure is this cell's verdict
        return cc.Verdict("fail", f"the scan failed: {e}", kind="scan failed")
    checks = fact_checks(case)
    missing = [label for label, what in checks if not _has_fact(ir, what)]
    if not missing:
        return cc.Verdict("pass", f"{len(checks)} facts")
    more = f" (+{len(missing) - 1} more: {'; '.join(missing[1:])})" if len(missing) > 1 else ""
    kind = "not recorded: " + re.sub(r"\(.*?\)", "(..)", missing[0].split(": ", 1)[-1]).split(" -> ")[0]
    return cc.Verdict("fail", f"{len(missing)}/{len(checks)} facts not recorded: {missing[0]}{more}", kind=kind)


# ---- the forge ------------------------------------------------------------------------------------
def maven(project: Path, args: list[str], offline: bool, log: Path) -> tuple[bool, str]:
    import java_target_matrix as jtm

    env = dict(os.environ, JAVA_HOME=jtm._jdk(17) or os.environ.get("JAVA_HOME", ""))
    if env["JAVA_HOME"]:
        env["PATH"] = str(Path(env["JAVA_HOME"]) / "bin") + os.pathsep + env["PATH"]
    cmd = [mvn_executable(env), "-q", "-B", *(["-o"] if offline else []), *args]
    proc = run_decoded(cmd, cwd=project, env=maven_utf8_env(env), check=False)
    log.write_text(proc.stdout + proc.stderr, encoding="utf-8")
    errors = [ln for ln in (proc.stdout + proc.stderr).splitlines() if "ERROR" in ln or "error:" in ln]
    return proc.returncode == 0, "\n".join(errors[:20]) or _tail(proc.stdout + proc.stderr, 20)


def forge(case: cc.Case, work: Path, offline: bool, overlays: list[Path] | None = None,
          cache: Path | None = None) -> tuple[cc.Verdict, Path | None]:  # fmt: skip
    """Refactor + cobol-to-java (config h2, the equivalence harness's) + `mvn compile`. `overlays` (the
    java-ported side) are port overlay trees laid over the generated sources before the compile, in order.
    #4047: `cache` is a directory holding the generated project (before any overlay or compile): the first forge
    fills it, later ones copy it instead of refactoring and generating again (the mutation runs' fast mode)."""
    import java_target_matrix as jtm

    work.mkdir(parents=True, exist_ok=True)
    cached = cache / "project" if cache is not None else None
    try:
        if cached is not None and cached.is_dir():
            project = work / "java_h2"
            shutil.copytree(cached, project, ignore=shutil.ignore_patterns("target"))
        else:
            with quiet(work / "forge.log"):
                clean = jtm.refactor(case.dir, work, scan=True)
                project = jtm.generate(clean, "h2", jtm.MATRIX["h2"], work)
            if cached is not None:
                shutil.copytree(project, cached, ignore=shutil.ignore_patterns("target"))
    except (Exception, SystemExit) as e:  # noqa: BLE001 -- the generator failing is this cell's verdict
        return cc.Verdict(
            "fail", f"generation failed: {e!r} (see {work / 'forge.log'})", kind="generation failed"
        ), None
    for overlay in overlays or []:
        lay_overlay(overlay, project)
    ok, errors = maven(project, ["compile"], offline, work / "compile.log")
    if not ok:
        first = errors.splitlines()[0] if errors else "mvn compile failed"
        return cc.Verdict("fail", f"mvn compile: {first}", kind="does not compile", detail=errors), project
    return cc.Verdict("pass", "compiles"), project


# ---- ports: the porting loop's overlays (#3989) ------------------------------------------------------
# A port is an overlay (gitgalaxy/tools/cobol_to_java/port_runner.py): <KEY>/overlay/service/<Service>.java,
# a tree relative to the generated package root. The committed ones -- proven by this runner, kept as
# regression evidence with their provenance.json -- live under PORTS_DIR/<case>/<KEY>/.
PORTS_DIR = LEDGER_DIR / "ports"
DET_PORTS_DIR = LEDGER_DIR / "det-ports"  # #4767: a case with no model port runs its deterministic port instead
STRENGTHENED_DIR = LEDGER_DIR / "strengthened"  # #4049: scenarios added to a case, their logs from the COBOL
STRENGTHENED_FORMAT = "gitgalaxy/crucible-strengthened/1"


def strengthened_scenarios(case: cc.Case, root: Path = STRENGTHENED_DIR) -> list[dict[str, Any]]:
    """#4049: the case's strengthened scenarios (tests/cics_crucible/strengthened/<case>/case.json), or none."""
    path = root / case.id / "case.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != STRENGTHENED_FORMAT or data.get("case") != case.id:
        raise cc.CaseError(f"{path}: not a {STRENGTHENED_FORMAT} file of case {case.id}")
    taken = {sc["id"] for sc in case.scenarios}
    for sc in data["scenarios"]:
        if sc["id"] in taken:
            raise cc.CaseError(f"{path}: scenario {sc['id']!r} is already one of the case's")
    return list(data["scenarios"])


def add_strengthened(case: cc.Case, root: Path = STRENGTHENED_DIR, expected: bool = True) -> list[str]:
    """#4049: the case with its strengthened scenarios added (and, with `expected`, their derived logs, which must
    exist); their ids."""
    added = strengthened_scenarios(case, root)
    for sc in added:
        if expected:
            ep = root / case.id / "expected" / f"{sc['id']}.json"
            if not ep.is_file():
                raise cc.CaseError(f"{ep}: no derived log; run --derive-expected --cases {case.id}")
            case.expected[sc["id"]] = json.loads(ep.read_text(encoding="utf-8"))
    case.data = {**case.data, "scenarios": [*case.data["scenarios"], *added]}
    return [sc["id"] for sc in added]


def task_faults(sc: dict[str, Any], transid: str) -> list[str]:
    """#4049: the conditions a scenario plans for a task of `transid`, as faults.cfg lines (the equivalence
    harness's format and checks)."""
    import equivalence_cics as ec

    mine = [f for f in sc.get("faults") or [] if f.get("task") == transid]
    return ec.fault_lines({"name": sc["id"], "faults": mine}) if mine else []


def fault_plans(sc: dict[str, Any]) -> dict[str, list[str]]:
    """#4049: {TRANSID: its faults.cfg lines} of a scenario (every fault must name its task)."""
    if any(not f.get("task") for f in sc.get("faults") or []):
        raise cc.CaseError(f"scenario {sc['id']}: every fault names the TRANSID of its `task`")
    return {t: task_faults(sc, t) for t in dict.fromkeys(f["task"] for f in sc.get("faults") or [])}


def _derived(value: Any) -> Any:
    """A cobol-stub actual value as an expected log spells it (SPEC 6.1): an area {length, text | hex}, bytes as
    text when they are printable EBCDIC (blank-padded the same), else {hex}. A value the stub does not model
    cannot be an expectation: refused."""
    if isinstance(value, cc.Unmodelled):
        raise RuntimeError(f"the COBOL side does not model {value.feature}: no expected value can be derived")
    if isinstance(value, cc.RawArea):
        data = cc.to_ebcdic(value)
        return {"length": len(data), **_spelled(data)}
    if isinstance(value, (bytes, bytearray)):
        spelled = _spelled(bytes(value))
        return spelled.get("text", spelled)
    if isinstance(value, dict):
        return {k: _derived(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_derived(v) for v in value]
    return value


def _spelled(data: bytes) -> dict[str, Any]:
    text = data.decode(cc.EBCDIC)
    if text.isprintable() and cc.expected_bytes(text.rstrip(" "), len(data)) == data:
        return {"text": text.rstrip(" ")}
    return {"hex": data.hex().upper()}


def area_layout(case: cc.Case, program: str | None) -> str | None:
    """#4049: the layout a derived COMMAREA is spelled by: the case's layout of the program that holds the area
    (the event's issuer, the task's program), else the case's only layout, else none. A COMP / COMP-3 field's bytes
    are not text: spelled without its layout, the stub's bytes would be transcoded as if they were."""
    layouts = case.data.get("layouts") or {}
    mine = [n for n, spec in layouts.items() if program and Path(spec["source"]).stem.upper() == program]
    return mine[0] if len(mine) == 1 else (next(iter(layouts)) if len(layouts) == 1 else None)


def _derived_area(value: Any, layout: str | None, ctx: cc.Context) -> Any:
    """A COMMAREA as an expected log spells it: by `layout`'s fields where it has one (numbers as numbers, the
    binary ones decoded), else as _derived does."""
    if not isinstance(value, cc.RawArea) or layout is None:
        return _derived(value)
    fields = ctx.layouts[layout]
    data = cc.to_ebcdic(value, fields)
    if max(f["offset"] + f["bytes"] for f in fields) < len(data):
        return _derived(value)  # bytes past the record: no field names them
    out: dict[str, Any] = {}
    for f in fields:
        if f["offset"] + f["bytes"] > len(data):
            continue
        raw = data[f["offset"] : f["offset"] + f["bytes"]]
        if cc._numeric_pic(f.get("pic")):
            num = cc._decode_number(raw, f)
            if not isinstance(num, Decimal):
                return {"length": len(data), "hex": data.hex().upper()}
            out[f["name"]] = str(num)
        else:
            out[f["name"]] = _derived(raw)
    return {"length": len(data), "layout": layout, "fields": out}


def _derived_event(case: cc.Case, e: dict[str, Any], ctx: cc.Context) -> dict[str, Any]:
    lay = area_layout(case, e.get("program"))
    return {
        k: _derived_area(v, lay, ctx) if k in ("commarea", "caller_commarea") else _derived(v) for k, v in e.items()
    }


def derive_expected(case: cc.Case, actual: dict[str, Any], sid: str, fired: dict[str, list[str]],
                    ctx: cc.Context | None = None) -> dict[str, Any]:  # fmt: skip
    """#4049: the expected log of strengthened scenario `sid`: what the COBOL did on the stub runtime."""
    if actual.get("stopped"):
        raise RuntimeError(f"{sid}: the scenario stopped early ({actual['stopped']})")
    ctx = ctx or case_context(case)
    tasks = []
    for n, t in enumerate(actual["tasks"], 1):
        if any(e["event"] == "DRIVER-ERROR" for e in t["events"]):
            raise RuntimeError(f"{sid}: task {n} hit a driver error: the harness cannot run it")
        task = {"seq": n, **{k: _derived(t.get(k)) for k in (*cc.TASK_KEYS, "end")}}
        task["commarea"] = _derived_area(t.get("commarea"), area_layout(case, t.get("program")), ctx)
        task["events"] = [_derived_event(case, e, ctx) for e in t["events"]]
        tasks.append({k: task[k] for k in ("seq", *cc.TASK_KEYS, "events", "end")})
    sc = next(s for s in case.scenarios if s["id"] == sid)
    planned = {ln.split()[0] + " " + ln.split()[1] for lines in fault_plans(sc).values() for ln in lines}
    missing = sorted(planned - {ln.split()[0] + " " + ln.split()[1] for ln in fired.get(sid, [])})
    if missing:
        raise RuntimeError(f"{sid}: planned fault(s) {missing} never fired on the COBOL side")
    log: dict[str, Any] = {
        "format": cc.EXPECTED_FORMAT, "case": case.id, "scenario": sid,
        "derived": {"from": "cobol-stub", "issue": "#4049",
                    "note": "the COBOL program's own run on the stub runtime (tests/equivalence/cics/ggcics.c), "
                    "written by cics_crucible.py --derive-expected; never edited by hand",
                    "faults_fired": fired.get(sid, [])},
        "tasks": tasks,
    }  # fmt: skip
    final = (actual.get("final") or {}).get("ts_queues")
    if final:
        log["final"] = {"ts_queues": {q: [_derived(i) for i in items] for q, items in final.items()}}
    return log


def derive_case(case: cc.Case, work: Path, root: Path = STRENGTHENED_DIR) -> list[str]:
    """#4049: run the case's strengthened scenarios on the COBOL side and write their expected logs; their ids."""
    ids = add_strengthened(case, root, expected=False)
    if not ids:
        return []
    translated = translate_programs(case)
    bad = {p: t for p, t in translated.items() if isinstance(t, Exception)}
    if bad:
        raise RuntimeError(f"{case.id}: the translator refuses {sorted(bad)}: no log can be derived")
    actual = run_cobol(case, translated, ids, case_context(case), work / "cobol")
    fired = {sid: _fired_faults(work / "cobol" / "runs" / sid) for sid in ids}
    out = root / case.id / "expected"
    out.mkdir(parents=True, exist_ok=True)
    for sid in ids:
        log = derive_expected(case, actual[sid], sid, fired, case_context(case))
        (out / f"{sid}.json").write_text(json.dumps(log, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return ids


def _fired_faults(runs: Path) -> list[str]:
    return [ln for f in sorted(runs.glob("*/out/faults.txt")) for ln in f.read_text(encoding="ascii").splitlines()]


def lay_overlay(overlay: Path, project: Path) -> list[str]:
    """Copy an overlay tree's .java files over the generated project; the files laid, relative to it."""
    import equivalence_java as ej

    laid = []
    for f in sorted(overlay.rglob("*.java")):
        dest = project / "src/main/java" / ej.PKG_DIR / f.relative_to(overlay)
        dest.parent.mkdir(parents=True, exist_ok=True)
        ej.keep_generated(dest, project, f.relative_to(overlay).as_posix())  # #4048: proof_reach's `generated`
        shutil.copyfile(f, dest)
        laid.append(dest.relative_to(project).as_posix())
    return laid


def case_overlays(ports: Path) -> dict[str, Path]:
    """{program key: its overlay tree} under a ports directory (<KEY>/overlay, port_runner's layout)."""
    if not ports.is_dir():
        return {}
    return {d.name: d / "overlay" for d in sorted(ports.iterdir()) if (d / "overlay").is_dir()}


# ---- the scenario driver, shared by both sides -----------------------------------------------------
def task_frame(case: cc.Case, n: int, step: dict[str, Any]) -> dict[str, Any]:
    """What the scheduler decides about the task step `n` starts (SPEC section 4)."""
    clock = datetime.datetime.fromisoformat(case.data["clock"]) + datetime.timedelta(seconds=step["at"])
    return {"termid": case.data["terminal"], "at": clock.strftime("%Y-%m-%dT%H:%M:%S"),
            "trigger": {"kind": "terminal", "step": n}, "eibaid": step["aid"],
            "startcode": "TD"}  # fmt: skip  # #4270 slice 3: ASSIGN STARTCODE, "Terminal input or permanent transid"


def scenario_programs(expected: dict[str, Any]) -> list[str]:
    """Every program a scenario runs (a task's first program and each event's issuer), in order."""
    progs = [p for t in expected["tasks"] for p in [t["program"], *(e["program"] for e in t["events"])]]
    return list(dict.fromkeys(progs))


# ---- the Java side --------------------------------------------------------------------------------
_JAVA_TEST = r"""package @PKG@;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import @PKG@.cics.CicsTask;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;

/**
 * #3989: the CICS crucible's Java side -- generated by tests/tools/cics_crucible.py. Each scenario's
 * terminal steps run as tasks through the generated services' runTask(CicsTask): a step starts the
 * TRANSID and COMMAREA of the previous task's RETURN, else the transaction id typed as text; an XCTL
 * runs its target in the same task. Each task's events are written to out/<scenario>.json.
 *
 * #4343: with -Dequivalence.facades=true each task enters through the program's deployed entry point instead -- the
 * service's handleTransaction, and handleLink for a program a LINK / XCTL reaches -- with the scenario's region
 * joined (CicsTask.join), so the facade's task IS the scenario's task: the same events, TS, COMMAREA, screens and
 * abend plumbing. A program with no such facade runs through runTask; out/<scenario>.json says which ran.
 */
@SpringBootTest(properties = {"spring.jpa.show-sql=false"})
class EquivalenceRunTest {

    final Path in = Path.of(System.getProperty("equivalence.in"));
    final Path out = Path.of(System.getProperty("equivalence.out"));
    final ObjectMapper json = new ObjectMapper().findAndRegisterModules();
    final boolean facades = Boolean.getBoolean("equivalence.facades");

    @Autowired
    ApplicationContext context;

    @Test
    void run() throws Exception {
        JsonNode plan = json.readTree(in.resolve("plan.json").toFile());
        for (JsonNode sc : plan.get("scenarios")) {
            String id = sc.get("id").asText();
            json.writeValue(out.resolve(id + ".json").toFile(), new Scenario(plan, sc, false).drive());
            if (facades) {
                // #4965: the same scenario again, each task entered by the byte-carrying handleTransaction overload
                // (the previous RETURN's bytes in, lastAnswerBytes() out) -- written only when some task was
                Scenario again = new Scenario(plan, sc, true);
                Map<String, Object> log = again.drive();
                if (again.usedBytes) {
                    json.writeValue(out.resolve(id + ".bytes.json").toFile(), log);
                }
            }
        }
    }

    static final Comparator<Map<String, Object>> EXPIRY = Comparator
            .comparing((Map<String, Object> r) -> (LocalDateTime) r.get("expires"))
            .thenComparing(r -> (Integer) r.get("issue"));

    /** One scenario, scheduled as SPEC section 4 says -- the same rules as tests/tools/cics_crucible.py's
     *  drive_scenario: when a task ends its STARTs become requests (#4006: a PROTECT one only if it ended
     *  normally; a CANCEL drops one), then expired requests run (earliest first, ties by issue order; one with
     *  a TERMID takes every expired request for its TRANSID and terminal), then the next operator step. */
    class Scenario {
        final JsonNode plan;
        final JsonNode sc;
        final LocalDateTime clock;
        final LocalDateTime until;
        final String terminal;
        final List<Map<String, Object>> tasks = new ArrayList<>();
        final List<Map<String, Object>> requests = new ArrayList<>();
        final CicsTask.TempStorage ts = new CicsTask.TempStorage();  // #4002: shared by every task
        final Map<String, byte[]> tctuas = new LinkedHashMap<>();  // #5079 (X59): a terminal's TCTUA, kept across its tasks
        byte[] cwa;  // #5079 (X59): the region's CWA (SIT WRKAREA), one for every task
        final List<Map<String, Object>> entries = new ArrayList<>();  // #4343: the entry point each program ran by
        int issued;
        String pending;
        Object pendingCa;
        byte[] pendingBytes;  // #4965: the bytes the last RETURN TRANSID passed on (lastAnswerBytes), for the next task
        byte[] inBytes;  // ... handed to the task about to start
        byte[] answered;  // ... and what the task that just ran answered (null: none)
        boolean answeredByBytes;  // the task that just ran was entered by the byte overload (its answer is owed)
        CicsTask.Channel pendingChannel;  // #5005 (X17): the channel the last RETURN TRANSID CHANNEL made available
        CicsTask.Channel inChannel;  // ... handed to the task about to start
        CicsTask.Channel outChannel;  // ... and what the task that just ran returned (null: none)
        Integer pendingLen;  // #4009: the next task's EIBCALEN (null: the whole record)
        Map<String, Object> immediate;  // #4270 (X27): RETURN IMMEDIATE -- the task attached at once, with its trigger
        LocalDateTime now;

        final boolean viaBytes;  // #4965: enter tasks by the byte-carrying handleTransaction where a service has one
        boolean usedBytes;

        Scenario(JsonNode plan, JsonNode sc, boolean viaBytes) {
            this.viaBytes = viaBytes;
            this.plan = plan;
            this.sc = sc;
            this.clock = LocalDateTime.parse(plan.get("clock").asText());
            this.until = sc.hasNonNull("until") ? clock.plusSeconds(sc.get("until").asLong()) : null;
            this.terminal = plan.get("terminal").asText();
            this.now = clock;
            sc.path("ts_queues").fields().forEachRemaining(q -> {
                List<byte[]> items = new ArrayList<>();
                q.getValue().forEach(item -> items.add(HexFormat.of().parseHex(item.asText())));
                ts.seed(q.getKey(), items);
            });
            sc.path("http").forEach(h -> {  // #4767 (X37): an inbound HTTP request, due at its time like a START
                Map<String, Object> r = new LinkedHashMap<>();
                r.put("issue", h.get("index").asInt() - 100000);  // (ahead of a START due at the same time)
                r.put("transid", h.get("transid").asText());
                r.put("expires", clock.plusSeconds(h.get("at").asLong()));
                r.put("kind", "http");
                r.put("http", h);
                requests.add(r);
            });
        }

        Map<String, Object> drive() {
            JsonNode steps = sc.get("steps");
            int next = 0;
            String stopped = null;
            while (true) {
                if (immediate != null) {
                    // #4270 (X27): RETURN IMMEDIATE -- TRANSID's task is attached next, "regardless of any other
                    // transactions enqueued by ATI for this terminal", with no operator step and no EIBAID
                    Map<String, Object> im = immediate;
                    immediate = null;
                    Map<String, Object> trigger = new LinkedHashMap<>();
                    trigger.put("kind", "immediate");
                    trigger.put("task", im.get("task"));
                    trigger.put("event", im.get("event"));
                    Map<String, Object> f = frame(terminal, trigger, null);
                    f.put("startcode", "TD");  // IBM: "appears to the operator as having been started by terminal data"
                    inBytes = (byte[]) im.get("bytes");
                    runOne(f, (String) im.get("transid"), im.get("commarea"), (Integer) im.get("length"), null, List.of());
                    continue;
                }
                List<Map<String, Object>> expired = requests.stream()
                        .filter(r -> !((LocalDateTime) r.get("expires")).isAfter(now)).toList();
                if (!expired.isEmpty()) {
                    Map<String, Object> first = expired.stream().min(EXPIRY).get();
                    List<Map<String, Object>> group = first.get("termid") == null ? List.of(first)
                            : expired.stream().filter(r -> r.get("transid").equals(first.get("transid"))
                                    && first.get("termid").equals(r.get("termid"))).sorted(EXPIRY).toList();
                    requests.removeAll(group);
                    List<CicsTask.StartData> data = new ArrayList<>();  // #4270: a record per START with data options
                    group.forEach(r -> {
                        if (r.get("data") != null || r.get("rtransid") != null || r.get("rtermid") != null
                                || r.get("queue") != null) {
                            data.add(new CicsTask.StartData((byte[]) r.get("data"), (String) r.get("rtransid"),
                                    (String) r.get("rtermid"), (String) r.get("queue")));
                        }
                    });
                    Map<String, Object> trigger = new LinkedHashMap<>();
                    trigger.put("kind", first.getOrDefault("kind", "start"));  // #4270: "run" for a RUN TRANSID child
                    JsonNode http = (JsonNode) first.get("http");  // #4767: an inbound HTTP request's task
                    if (http != null) {
                        trigger.put("request", http.get("index").asInt());
                    } else {
                        trigger.put("task", first.get("task"));
                        trigger.put("event", first.get("event"));
                    }
                    Map<String, Object> f = frame((String) first.get("termid"), trigger, null);
                    // #4270 slice 3: ASSIGN STARTCODE -- "S" a START that "did not pass data in the FROM option", "SD"
                    // one that did; a coalesced group that mixes the two is not stated (refused)
                    long withFrom = group.stream().filter(r -> r.get("data") != null).count();
                    f.put("startcode", http != null ? null : withFrom == group.size() ? "SD" : withFrom == 0 ? "S" : null);
                    if (http != null) {
                        f.put("http_request", http.get("request"));
                    }
                    runOne(f, (String) first.get("transid"), null, null, null, data);
                    continue;
                }
                LocalDateTime nxt = requests.stream().map(r -> (LocalDateTime) r.get("expires"))
                        .min(Comparator.naturalOrder()).orElse(null);
                if (next < steps.size()) {
                    JsonNode step = steps.get(next);
                    LocalDateTime at = clock.plusSeconds(step.get("at").asLong());
                    if (nxt != null && !nxt.isAfter(at)) {
                        now = nxt.isAfter(now) ? nxt : now;
                        continue;
                    }
                    int n = next++;
                    now = at.isAfter(now) ? at : now;
                    String transid = pending;
                    Object commarea = pendingCa;
                    Integer calen = pendingLen;
                    byte[] bytes = pendingBytes;
                    if (transid == null) {
                        bytes = null;
                        String text = step.path("text").asText("").trim();
                        if (text.isEmpty()) {
                            stopped = "step " + n + ": no pending RETURN TRANSID and no transaction id typed";
                            break;
                        }
                        transid = text.split("\\s+")[0];
                        commarea = null;
                        calen = null;
                        if (step.hasNonNull("commarea")) {  // #4443: a direct entry with a COMMAREA of its own
                            JsonNode seed = step.get("commarea");
                            commarea = seedArea(transid, seed.get("dto"));
                            calen = seed.get("length").asInt();
                        }
                    }
                    Map<String, Object> trigger = new LinkedHashMap<>();
                    trigger.put("kind", "terminal");
                    trigger.put("step", n);
                    Map<String, Object> f = frame(terminal, trigger, step.get("aid").asText());
                    f.put("startcode", "TD");  // #4270 slice 3: "Terminal input or permanent transid"
                    inBytes = bytes;
                    inChannel = transid.equals(pending) ? pendingChannel : null;  // not a typed transaction id's
                    runOne(f, transid, commarea, calen, step, List.of());
                    continue;
                }
                if (nxt != null && until != null && nxt.isBefore(until)) {
                    now = nxt.isAfter(now) ? nxt : now;
                    continue;
                }
                break;
            }
            Map<String, Object> log = new LinkedHashMap<>();
            log.put("tasks", tasks);
            log.put("stopped", stopped);
            Map<String, List<String>> queues = new LinkedHashMap<>();
            ts.queues().forEach((q, items) -> queues.put(q, items.stream().map(b -> HexFormat.of().formatHex(b)).toList()));
            log.put("ts_queues", queues);
            log.put("entries", entries);
            return log;
        }

        /** #4443: the DTO a seeded step enters its program with: the plan's JSON as the type of the facade's
         *  handleTransaction(String, T) the program's service declares. */
        Object seedArea(String transid, JsonNode dto) {
            String program = plan.path("transactions").path(transid).asText(null);
            Object service = program == null ? null : service(plan, program);
            if (service == null) {
                throw new IllegalStateException("no generated service for the seeded COMMAREA of " + transid);
            }
            for (Method m : service.getClass().getMethods()) {
                if (m.getName().equals("handleTransaction") && m.getParameterCount() >= 2
                        && m.getParameterTypes()[1] != byte[].class) {
                    try {
                        return json.treeToValue(dto, m.getParameterTypes()[1]);
                    } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
                        throw new IllegalStateException(e);
                    }
                }
            }
            throw new IllegalStateException("handleTransaction of " + program + " takes no COMMAREA to seed");
        }

        Map<String, Object> frame(String termid, Map<String, Object> trigger, String aid) {
            Map<String, Object> f = new LinkedHashMap<>();
            f.put("termid", termid);
            f.put("at", now.format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")));
            f.put("trigger", trigger);
            f.put("eibaid", aid);
            return f;
        }

        void runOne(Map<String, Object> frame, String transid, Object commarea, Integer calen, JsonNode step,
                List<CicsTask.StartData> data) {
            String program = plan.path("transactions").path(transid).asText(null);
            Map<String, Object> task = new LinkedHashMap<>(frame);
            answered = null;
            answeredByBytes = false;
            CicsTask.Channel carried = inChannel;
            inChannel = null;
            outChannel = null;
            task.remove("startcode");
            task.remove("http_request");
            task.put("transid", transid);
            task.put("program", program);
            task.put("commarea", describe(commarea));
            task.put("eibcalen", commarea == null ? Integer.valueOf(0) : calen);
            List<Map<String, Object>> events = new ArrayList<>();
            List<Map<String, Object>> raw = new ArrayList<>();
            String end = "normal";
            Map<String, Object> received = new LinkedHashMap<>();
            String inputError = step == null ? null : input(plan, step, received);
            if (inputError != null) {
                events.add(error(program, inputError));
            } else if (program == null) {
                events.add(error(null, "transaction " + transid + " has no program in the CSD"));
            }
            FacadeRegion region = new FacadeRegion(tasks.size() + 1);
            CicsTask.Programs programs = new CicsTask.Programs() {  // #4004: LINK / XCTL through the services
                public boolean defined(String p) {
                    return listed(plan.path("programs"), p);
                }

                public boolean transaction(String t) {
                    return plan.path("transactions").has(t);
                }

                public boolean terminal(String t) {
                    return terminal.equals(t);
                }

                public void run(String p, CicsTask task) {
                    Object service = service(plan, p);
                    if (service == null) {
                        throw new IllegalStateException("no generated service for program " + p);
                    }
                    if (facades) {
                        region.enter(p, task, service);
                        return;
                    }
                    try {
                        service.getClass().getMethod("runTask", CicsTask.class).invoke(service, task);
                    } catch (InvocationTargetException e) {
                        throw e.getCause() instanceof RuntimeException r ? r : new IllegalStateException(e.getCause());
                    } catch (NoSuchMethodException e) {
                        throw new IllegalStateException("the service of " + p + " has no runTask(CicsTask)");
                    } catch (IllegalAccessException e) {
                        throw new IllegalStateException(e);
                    }
                }
            };
            if (inputError == null && program != null) {
                Map<String, LocalDateTime> unexpired = new LinkedHashMap<>();
                requests.forEach(r -> {
                    if (r.get("reqid") != null && ((LocalDateTime) r.get("expires")).isAfter(now)) {
                        unexpired.putIfAbsent((String) r.get("reqid"), (LocalDateTime) r.get("expires"));
                    }
                });
                CicsTask t = new CicsTask(transid, (String) frame.get("eibaid"), commarea, calen, received)
                        .withTempStorage(ts)
                        .withPrograms(programs).withSnapshot(EquivalenceRunTest.this::snapshot).withClock(now)
                        .withTermid((String) frame.get("termid"))
                        .withStartData(data).withRequests(unexpired)
                        .withRunChild(frame.get("trigger") instanceof Map<?, ?> tr && "run".equals(tr.get("kind")))
                        // #4270 slice 3: ASSIGN STARTCODE / USERID / SCRNHT / SCRNWD (SPEC section 2's region)
                        .withStartcode((String) frame.get("startcode")).withUserid("CICSUSER")
                        .withScreen(24, 80);
                if (carried != null) {
                    t.withChannel(carried);  // #5005: RETURN TRANSID CHANNEL -- the next task's current channel
                }
                if (step != null && step.has("text")) {
                    t.withTerminalInput(step.get("text").asText());
                }
                t.withEndOfChain("LUTYPE2".equals(plan.path("terminal_device").asText()));  // #4413
                if (frame.get("http_request") instanceof JsonNode q) {  // #4767 (X37): the request the task serves
                    List<String[]> headers = new ArrayList<>();
                    q.get("headers").forEach(h -> headers.add(new String[] {h.get(0).asText(), h.get(1).asText()}));
                    t.withHttpRequest(new CicsTask.HttpRequest(q.get("scheme").asText(), q.get("host").asText(),
                            q.get("port").asInt(), q.get("method").asText(), q.get("version").asText(),
                            q.get("path").asText(), q.get("query").asText(), headers,
                            q.hasNonNull("mediatype") ? q.get("mediatype").asText() : null,
                            q.hasNonNull("body") ? q.get("body").asText() : null));
                }
                if (sc.hasNonNull("http_peers")) {  // #4767 (X35): the origin servers the task can reach
                    List<CicsTask.HttpPeer> peers = new ArrayList<>();
                    for (JsonNode p : sc.get("http_peers")) {
                        List<CicsTask.HttpExchange> xs = new ArrayList<>();
                        for (JsonNode x : p.get("exchanges")) {
                            xs.add(new CicsTask.HttpExchange(x.get("method").asText(), x.get("path").asText(),
                                    x.get("query").asText(), x.get("status").asInt(), x.get("statustext").asText(),
                                    x.get("mediatype").asText(), x.get("body").asText()));
                        }
                        peers.add(new CicsTask.HttpPeer(p.get("scheme").asText(), p.get("host").asText(),
                                p.get("port").asInt(), null, null, xs));
                    }
                    t.withHttpPeers(peers);
                }
                if (plan.hasNonNull("twasize") && plan.get("twasize").hasNonNull(transid)) {
                    t.withTwaSize(plan.get("twasize").get(transid).asInt());  // #5079 (X59): TRANSACTION TWASIZE
                }
                if (plan.hasNonNull("wrkarea")) {
                    if (cwa == null) cwa = new byte[plan.get("wrkarea").asInt()];
                    t.withCwa(cwa);  // #5079 (X59): SIT WRKAREA -- one area for the whole region
                }
                if (plan.hasNonNull("userarealen") && frame.get("termid") instanceof String tid
                        && plan.get("userarealen").hasNonNull(tid)) {
                    // #5079 (X59): TYPETERM USERAREALEN -- one area per terminal, the same bytes for each of its tasks
                    t.withTctua(tctuas.computeIfAbsent(tid, k -> new byte[plan.get("userarealen").get(k).asInt()]));
                }
                if (plan.has("urimaps")) {
                    // #4270 zECS (X32): INQUIRE URIMAP -- the URIMAP definitions the case CSD installs, as {name,
                    // transaction, path}, in the CSD's order
                    List<String[]> defs = new ArrayList<>();
                    plan.get("urimaps").forEach(u -> defs.add(new String[] {u.get(0).asText(), u.get(1).asText(),
                            u.get(2).asText()}));
                    t.withUrimaps(defs);
                }
                if (plan.hasNonNull("doctemplates")) {
                    // #4769 zECS (X33): DOCUMENT CREATE TEMPLATE -- the installed DOCTEMPLATEs, name -> the text each yields
                    Map<String, String> templates = new LinkedHashMap<>();
                    plan.get("doctemplates").fields().forEachRemaining(e -> templates.put(e.getKey(), e.getValue().asText()));
                    t.withDoctemplates(templates);
                }
                if (plan.hasNonNull("uctranst")) {
                    t.withUctranst(plan.get("uctranst").asText());  // #4415: INQUIRE TERMINAL UCTRANST
                }
                if (plan.hasNonNull("origin") && frame.get("trigger") instanceof Map<?, ?> otr
                        && "terminal".equals(otr.get("kind"))) {
                    // #4415 slice 2 (X29): INQUIRE ASSOCIATION -- the origin data the case states, for a task that
                    // terminal input started ("Origin data is created when a new request first arrives")
                    JsonNode o = plan.get("origin");
                    t.withOrigin(o.get("applid").asText(), o.get("userid").asText(), o.get("facilname").asText(),
                            o.get("networkid").asText(), o.get("faciltype").asText());
                }
                if (sc.path("fault_plans").has(transid)) {  // #4049: the conditions planned for this TRANSID's tasks
                    List<String> faults = new ArrayList<>();
                    sc.get("fault_plans").get(transid).forEach(f -> faults.add(f.asText()));
                    t.withFaults(faults, null);
                }
                String thrown = null;
                try {
                    if (facades) {
                        try (CicsTask.Joined joined = CicsTask.join(region)) {
                            region.start(t, program, commarea);
                        }
                    } else {
                        t.run(program);
                    }
                } catch (RuntimeException e) {
                    String code = abcode(e);
                    if (code != null) {
                        t.abend(code);
                    } else {
                        thrown = e.getMessage() != null && e instanceof IllegalStateException ? e.getMessage()
                                : "runTask threw " + e;
                    }
                }
                outChannel = t.returnedChannel();
                for (Map<String, Object> e : t.events()) {
                    raw.add(e);
                    Map<String, Object> copy = new LinkedHashMap<>(e);
                    if ("XCTL".equals(e.get("event"))) {
                        copy.put("target", e.get("program"));
                    }
                    copy.put("program", e.getOrDefault("issuer", program));
                    copy.remove("issuer");
                    if (copy.get("screen") != null) {
                        copy.put("screen", screenValues(copy.get("screen")));
                    }
                    for (String k : List.of("commarea", "caller_commarea")) {
                        if (copy.get(k) instanceof Map<?, ?> m) {
                            Map<Object, Object> d = new LinkedHashMap<>(m);
                            d.remove("object");
                            copy.put(k, d);
                        }
                    }
                    if ("ABEND".equals(e.get("event")) && "terminated".equals(e.get("outcome"))) {
                        end = "abend";
                    }
                    if ("RETURN".equals(e.get("event")) && !e.containsKey("level") && e.get("commarea") != null
                            && answered != null) {  // #4965: the bytes lastAnswerBytes() answered for this RETURN
                        copy.put("answer_bytes", java.util.Base64.getEncoder().encodeToString(answered));
                    }
                    events.add(copy);
                }
                if (answeredByBytes && thrown == null && !java.util.Arrays.equals(answered, t.returnedBytes())) {
                    // #4965 (as equivalence_cics.py): the accessor answers the bytes the task's RETURN passed on -- a
                    // facade that stopped assigning them (answers null, or a previous task's) is not proven by the
                    // DTO's bytes the comparison falls back to
                    thrown = "lastAnswerBytes() of " + program + " is not the bytes its RETURN passes on";
                }
                if (thrown != null) {
                    events.add(error(program, thrown));
                    end = "abend";
                }
            }
            task.put("events", events);
            task.put("end", end);
            tasks.add(task);
            ended(raw, "abend".equals(end), terminal.equals(frame.get("termid")));
        }

        /** #4343: the scenario's region, joined while a facade runs: it hands the facade the task the scenario
         *  starts (handleTransaction) or the program level a LINK / XCTL makes (handleLink), and refuses any other
         *  -- a facade that builds a task of its own is not running the path the scenario proves. */
        class FacadeRegion implements CicsTask.Region {
            final int taskNo;
            CicsTask scenarioTask;  // the task the scenario starts
            String scenarioProgram;
            CicsTask top;  // ... until handleTransaction asks the region for it
            Consumer<CicsTask> firstHop;  // the facade's own runTask, for the task's first program
            CicsTask linked;  // the level a LINK / XCTL runs, until handleLink asks for it
            String linkedProgram;
            /** #5053: by program level, the bytes the first program of a LINK's XCTL chain left in the caller's area,
             *  until the chain's RETURN (an XCTL target's, which is not the program that held the area) takes them. */
            final Map<Integer, byte[]> callerLeft = new java.util.HashMap<>();

            FacadeRegion(int taskNo) {
                this.taskNo = taskNo;
            }

            @Override
            public CicsTask transaction(String transid, Object commarea) {
                CicsTask t = top;
                if (t == null || !t.transid().equals(transid) || area(t) != commarea) {
                    throw new IllegalStateException("a facade asked the region for a task of " + transid
                            + " that is not the one the scenario starts");
                }
                top = null;
                return t;
            }

            @Override
            public CicsTask linked(String program, Object commarea) {
                CicsTask t = linked;
                if (t == null || !program.equals(linkedProgram) || area(t) != commarea) {
                    throw new IllegalStateException("a facade asked the region for a level of " + program
                            + " that is not the LINK / XCTL the scenario made");
                }
                linked = null;
                return t;
            }

            @Override
            public CicsTask linked(String program, Object commarea, byte[] bytes) {
                CicsTask t = linked(program, commarea);
                if (t.linkAreaView() != bytes) {  // #5053: the LINK's own area, by address
                    throw new IllegalStateException("a facade handed the region a COMMAREA's bytes of " + program
                            + " that are not the ones the LINK / XCTL made");
                }
                return t;
            }

            @Override
            public void run(CicsTask task, String program, Consumer<CicsTask> self) {
                if (task == scenarioTask && firstHop == null && top == null) {
                    if (!program.equals(scenarioProgram)) {
                        throw new IllegalStateException("handleTransaction of " + scenarioProgram + " ran program "
                                + program);
                    }
                    firstHop = self;
                    task.run(program);
                } else {
                    self.accept(task);
                }
            }

            /** The task's first program, entered through its service's handleTransaction (else runTask). #4965: by
             *  the byte-carrying overload when the service has one -- the previous task's RETURN bytes in, the bytes
             *  this task's RETURN passes on out (lastAnswerBytes()) -- else by the DTO one. */
            void start(CicsTask t, String program, Object commarea) {
                Object service = service(plan, program);
                Method one = facade(service, "handleTransaction", 1, false);
                Method two = facade(service, "handleTransaction", 2, false);
                Method oneB = facade(service, "handleTransaction", 2, true);
                Method twoB = facade(service, "handleTransaction", 3, true);
                if (one == null && two == null && oneB == null && twoB == null) {
                    entry(program, "runTask");
                    t.run(program);
                    return;
                }
                byte[] in = inBytes;
                inBytes = null;
                scenarioTask = t;
                scenarioProgram = program;
                top = t;
                // the DTO overload: (String) for no COMMAREA, else (String, T); the byte one the same with byte[] last
                boolean dtoOne = commarea == null && one != null;
                boolean dtoTwo = !dtoOne && two != null && (commarea == null || two.getParameterTypes()[1].isInstance(commarea));
                boolean bytesOne = commarea == null && oneB != null;
                boolean bytesTwo = !bytesOne && twoB != null
                        && (commarea == null || twoB.getParameterTypes()[1].isInstance(commarea));
                Method used = null;
                entry(program, "handleTransaction");
                if ((bytesOne || bytesTwo) && (viaBytes || !(dtoOne || dtoTwo))) {
                    used = bytesOne ? oneB : twoB;
                    answeredByBytes = true;
                    usedBytes = true;  // even when it throws: the run is the byte overload's, and is compared
                    if (bytesOne) {
                        invoke(oneB, service, t.transid(), in);
                    } else {
                        invoke(twoB, service, t.transid(), commarea, in);
                    }
                } else if (dtoOne) {
                    invoke(one, service, t.transid());
                } else if (dtoTwo) {
                    invoke(two, service, t.transid(), commarea);
                } else {
                    throw new IllegalStateException("handleTransaction of " + program + " cannot take the COMMAREA ("
                            + commarea.getClass().getName() + ") the task starts with");
                }
                if (top != null) {
                    throw new IllegalStateException("handleTransaction of " + program
                            + " did not run its task in the region");
                }
                if (used != null) {
                    Method a0 = null;
                    for (Method m : service.getClass().getMethods()) {
                        if (m.getName().equals("lastAnswerBytes") && m.getParameterCount() == 0) {
                            a0 = m;
                        }
                    }
                    if (a0 == null) {
                        throw new IllegalStateException("handleTransaction (bytes) of " + program
                                + " has no lastAnswerBytes()");
                    }
                    answered = (byte[]) invoke(a0, service);
                }
            }

            /** A program the task runs (#4004): its first program through the facade that asked for the task, any
             *  other -- an XCTL's target, a LINK's -- through its service's handleLink (else runTask). */
            void enter(String p, CicsTask task, Object service) {
                if (task == scenarioTask && firstHop != null) {
                    Consumer<CicsTask> self = firstHop;
                    firstHop = null;
                    self.accept(task);
                    return;
                }
                Method m = facade(service, "handleLink", 1, false);
                if (m == null) {
                    entry(p, "runTask");
                    invoke(method(service, "runTask", 1), service, task);
                    return;
                }
                Object ca = area(task);
                if (ca != null && !m.getParameterTypes()[0].isInstance(ca)) {
                    throw new IllegalStateException("handleLink of " + p + " takes a " + m.getParameterTypes()[0]
                            .getName() + ", the LINK / XCTL passed a " + ca.getClass().getName());
                }
                // #5053: by the byte-carrying overload when the service has one and the LINK / XCTL passed bytes: the
                // COMMAREA's bytes in (by address), the bytes the program left in them out (lastLinkBytes())
                Method mb = facade(service, "handleLink", 2, true);
                byte[] view = task.linkAreaView();
                boolean bytes = viaBytes && mb != null && view != null && ca != null
                        && mb.getParameterTypes()[0].isInstance(ca);
                CicsTask outer = linked;
                String outerProgram = linkedProgram;
                int mark = scenarioTask.events().size();  // #5053: this program's own events start here
                if (task.linkAreaOfCaller()) {
                    callerLeft.remove(task.level());  // a new chain: nothing is left of an earlier one's
                }
                linked = task;
                linkedProgram = p;
                entry(p, "handleLink");
                if (bytes) {
                    usedBytes = true;  // even when it throws: the run is the byte overload's, and is compared
                    invoke(mb, service, ca, view);
                } else {
                    invoke(m, service, ca);
                }
                if (linked == task) {
                    throw new IllegalStateException("handleLink of " + p + " did not run its task in the region");
                }
                linked = outer;
                linkedProgram = outerProgram;
                if (bytes) {
                    linkBytes(p, task, service, view, mark);
                }
                byte[] kept = task.linkAreaOfCaller() ? null : callerLeft.remove(task.level());
                if (kept != null && !tagReturn(task.level(), kept, mark)) {
                    callerLeft.put(task.level(), kept);  // it XCTLed on again: the next target's RETURN takes them
                }
            }

            /** #5053: the bytes the caller sees back, on the RETURN of `level` that this program recorded (from event
             *  `mark` on); false when it recorded none (it XCTLed instead) or one that already has them. */
            boolean tagReturn(int level, byte[] bytes, int mark) {
                List<Map<String, Object>> evs = scenarioTask.events();
                for (int i = evs.size() - 1; i >= mark; i--) {
                    Map<String, Object> e = evs.get(i);
                    if ("RETURN".equals(e.get("event")) && Integer.valueOf(level).equals(e.get("level"))
                            && !e.containsKey("area_bytes")) {
                        e.put("area_bytes", java.util.Base64.getEncoder().encodeToString(bytes));
                        return true;
                    }
                }
                return false;
            }

            /** #5053: lastLinkBytes() answers the bytes the program left in the LINK's COMMAREA when it took them (null
             *  when it did not: its DTO is the COMMAREA) -- a facade that stopped assigning them is not proven by the
             *  DTO's bytes the comparison falls back to. What the caller sees back (the RETURN's caller_commarea) is
             *  then compared by them: those of the program the LINK reached, whose area is the caller's own (an XCTL
             *  target's is a copy of the bytes XCTL passed, so the caller sees the first program's, kept in callerLeft
             *  for the chain's RETURN). */
            void linkBytes(String p, CicsTask task, Object service, byte[] view, int mark) {
                Method a0 = null;
                for (Method m : service.getClass().getMethods()) {
                    if (m.getName().equals("lastLinkBytes") && m.getParameterCount() == 0) {
                        a0 = m;
                    }
                }
                if (a0 == null) {
                    throw new IllegalStateException("handleLink (bytes) of " + p + " has no lastLinkBytes()");
                }
                byte[] left = (byte[]) invoke(a0, service);
                if (!java.util.Arrays.equals(left, task.linkAreaTaken() ? view : null)) {
                    throw new IllegalStateException("lastLinkBytes() of " + p
                            + " is not the bytes its task left in the LINK COMMAREA");
                }
                if (left == null || !task.linkAreaOfCaller()) {
                    return;
                }
                if (!tagReturn(task.level(), left, mark)) {
                    callerLeft.put(task.level(), left);  // #5053: it XCTLed: its target's RETURN is what the caller sees
                }
            }

            void entry(String program, String method) {
                Map<String, Object> e = new LinkedHashMap<>();
                e.put("task", taskNo);
                e.put("program", program);
                e.put("method", method);
                if (!entries.contains(e)) {
                    entries.add(e);
                }
            }
        }

        /** A task ended: its STARTs become requests, its CANCELs drop them, and a terminal task's level-1
         *  RETURN TRANSID decides what the terminal's next input starts. */
        void ended(List<Map<String, Object>> raw, boolean abended, boolean atTerminal) {
            String transid = null;
            Object commarea = null;
            Integer length = null;
            for (int j = 0; j < raw.size(); j++) {
                Map<String, Object> e = raw.get(j);
                if ("START".equals(e.get("event")) && "NORMAL".equals(e.get("resp"))
                        && !(Boolean.TRUE.equals(e.get("protect")) && abended)) {
                    Map<String, Object> r = new LinkedHashMap<>();
                    r.put("issue", ++issued);
                    r.put("transid", e.get("transid"));
                    r.put("termid", e.get("termid"));
                    r.put("expires", LocalDateTime.parse((String) e.get("expires")));
                    r.put("reqid", e.get("reqid"));
                    r.put("data", e.get("from"));
                    for (String k : List.of("rtransid", "rtermid", "queue")) {  // #4270: START's data options
                        r.put(k, e.get(k));
                    }
                    r.put("task", tasks.size());
                    r.put("event", j);
                    requests.add(r);
                } else if ("RUN".equals(e.get("event")) && "NORMAL".equals(e.get("resp"))) {
                    // #4270: a RUN TRANSID child -- attached at once, run once its parent has ended (SPEC 4)
                    Map<String, Object> r = new LinkedHashMap<>();
                    r.put("issue", ++issued);
                    r.put("transid", e.get("transid"));
                    r.put("termid", null);
                    r.put("expires", now);
                    r.put("reqid", null);
                    r.put("data", null);
                    r.put("kind", "run");
                    r.put("task", tasks.size());
                    r.put("event", j);
                    requests.add(r);
                } else if ("CANCEL".equals(e.get("event")) && "NORMAL".equals(e.get("resp"))) {
                    requests.stream().filter(r -> e.get("reqid").equals(r.get("reqid"))
                            && ((LocalDateTime) r.get("expires")).isAfter(now)).findFirst().ifPresent(requests::remove);
                } else if ("RETURN".equals(e.get("event")) && !e.containsKey("level")) {
                    transid = (String) e.get("transid");
                    commarea = e.get("commarea") instanceof Map<?, ?> m ? m.get("object") : null;
                    length = e.get("length") instanceof Integer l ? l : null;
                    if (Boolean.TRUE.equals(e.get("immediate")) && atTerminal && !abended) {  // #4270 (X27)
                        immediate = new LinkedHashMap<>();
                        immediate.put("transid", transid);
                        immediate.put("commarea", commarea);
                        immediate.put("length", length);
                        immediate.put("bytes", abended ? null : answered);
                        immediate.put("task", tasks.size());
                        immediate.put("event", j);
                        transid = null;  // not the terminal's next input
                    }
                }
            }
            if (atTerminal) {
                pending = abended ? null : transid;
                pendingCa = abended || transid == null ? null : commarea;
                pendingLen = abended || transid == null ? null : length;
                pendingBytes = abended || transid == null ? null : answered;
                pendingChannel = abended || transid == null ? null : outChannel;  // #5005 (X17)
            }
        }
    }

    static boolean listed(JsonNode names, String name) {
        for (JsonNode d : names) {
            if (d.asText().equals(name)) {
                return true;
            }
        }
        return false;
    }

    /** A formatted step's fields as the map's screen view model (none sent: MAPFAIL); an error, else null. */
    String input(JsonNode plan, JsonNode step, Map<String, Object> received) {
        if (!step.has("map") || step.get("fields").size() == 0) {
            return null;
        }
        String map = step.get("map").asText();
        String cls = plan.path("screens").path(map).asText(null);
        if (cls == null) {
            return "no generated screen class for map " + map;
        }
        try {
            Map<String, String> values = new LinkedHashMap<>();
            step.get("fields").fields().forEachRemaining(f -> values.put(f.getKey(), f.getValue().asText()));
            received.put(map, Class.forName(cls).getMethod("fromValues", Map.class).invoke(null, values));
            return null;
        } catch (ReflectiveOperationException e) {
            return "cannot build " + cls + " from the step's fields: " + e;
        }
    }

    static Object area(CicsTask task) {
        return task.hasCommarea() ? task.commarea(Object.class) : null;
    }

    /** The service's public method `name` taking `params` parameters (the deployed bean: a proxy's too), or null. */
    static Method method(Object service, String name, int params) {
        if (service == null) {
            return null;
        }
        for (Method m : service.getClass().getMethods()) {
            if (m.getName().equals(name) && m.getParameterCount() == params) {
                return m;
            }
        }
        return null;
    }

    /** #4965: the overload of `name` with `params` parameters that does (bytes) or does not end in the raw
     *  COMMAREA bytes (byte[]): `handleTransaction(String, byte[])` is not the DTO-less `(String, T)`. */
    static Method facade(Object service, String name, int params, boolean bytes) {
        if (service == null) {
            return null;
        }
        for (Method m : service.getClass().getMethods()) {
            if (m.getName().equals(name) && m.getParameterCount() == params
                    && (m.getParameterTypes()[params - 1] == byte[].class) == bytes) {
                return m;
            }
        }
        return null;
    }

    /** Calls a facade: what it throws (an abend, a condition) is thrown as itself. */
    static Object invoke(Method m, Object service, Object... args) {
        try {
            return m.invoke(service, args);
        } catch (InvocationTargetException e) {
            throw e.getCause() instanceof RuntimeException r ? r : new IllegalStateException(e.getCause());
        } catch (IllegalAccessException e) {
            throw new IllegalStateException(e);
        }
    }

    Object service(JsonNode plan, String program) {
        String cls = plan.path("services").path(program).asText(null);
        try {
            return cls == null ? null : context.getBean(Class.forName(cls));
        } catch (ReflectiveOperationException | RuntimeException e) {
            return null;
        }
    }

    static String abcode(Throwable t) {
        if (t == null || !t.getClass().getSimpleName().equals("CicsAbendException")) {
            return null;
        }
        try {
            return String.valueOf(t.getClass().getMethod("getAbcode").invoke(t));
        } catch (ReflectiveOperationException e) {
            return null;
        }
    }

    /** A screen view model's values (ScreenModel.screenValues(); by reflection: a case with no BMS map
     *  has no ScreenModel class). */
    static Object screenValues(Object screen) {
        try {
            return screen.getClass().getMethod("screenValues").invoke(screen);
        } catch (ReflectiveOperationException e) {
            return String.valueOf(screen);
        }
    }

    /** A COMMAREA as an event keeps it (#4004): described now, and the object itself (for the next task). */
    Object snapshot(Object area) {
        if (area == null) {
            return null;
        }
        Map<String, Object> d = new LinkedHashMap<>();
        d.put("class", area.getClass().getName());
        d.put("value", json.valueToTree(area));
        d.put("object", area);
        return d;
    }

    Object describe(Object area) {
        if (area == null) {
            return null;
        }
        Map<String, Object> d = new LinkedHashMap<>();
        d.put("class", area.getClass().getName());
        d.put("value", json.valueToTree(area));
        return d;
    }

    static Map<String, Object> error(String program, String message) {
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("event", "DRIVER-ERROR");
        e.put("program", program);
        e.put("message", message);
        return e;
    }
}
"""


def seeded_step(case: cc.Case, src: Path, step: dict[str, Any]) -> dict[str, Any]:
    """#4443: a step with a `commarea` (see step_commarea) as the Java plan carries it: the record's fields decoded
    through the layout of the DTO the typed transaction's facade takes, as that DTO's JSON, and the length."""
    import equivalence_cics as ec
    import equivalence_java as ej

    spec = step.get("commarea")
    if spec is None:
        return step
    words = (step.get("text") or "").split()
    program = case.csd["transactions"][words[0]]
    service = next(src.rglob(f"{ej._service_class(program)}.java"))
    found = re.search(r"handleTransaction\(String \w+, (\w+) \w+\)", service.read_text(encoding="utf-8"))
    if found is None:
        raise LookupError(f"{service.name} has no handleTransaction(String, DTO) to seed")
    layout = dto_layout(src, found.group(1))
    if layout is None:
        raise LookupError(f"{found.group(1)} has no record layout to seed")
    values = ec.decode_record(bytes.fromhex(spec["hex"]), layout, RUNTIME_PAGE)
    dto = ec.to_java(values, ec.dto_shape(src, found.group(1)))
    return {**step, "commarea": {"dto": dto, "length": spec.get("length", len(bytes.fromhex(spec["hex"])))}}


def java_plan(case: cc.Case, src: Path) -> dict[str, Any]:
    """plan.json for the generated test: transid -> program (the case's CSD), program -> service
    class, map -> screen class (found in the generated sources), and each scenario's steps."""
    import equivalence_cics as ec
    import equivalence_java as ej

    services = {}
    for p in case.programs:
        cls = ej._service_class(p)
        if list(src.rglob(f"{cls}.java")):
            services[p] = f"{ej.PKG}.service.{cls}"
    screens = {}
    for m in case.data["maps"]:
        with contextlib.suppress(RuntimeError):
            cls = ec._generated_class(src, 'String MAP = "' + re.escape(m) + '";')
            screens[m] = f"{ej.PKG}.dto.screen.{cls}"
    # #4002: seeds as EBCDIC hex (SPEC 2: the region's page); #4006: `until` for the scheduler
    scenarios = [{"id": sc["id"], "steps": [seeded_step(case, src, st) for st in sc["steps"]], "until": sc.get("until"), "fault_plans": fault_plans(sc), "http": http_plan(case, sc)[0],
                  "http_peers": origin_peers(case, sc),  # #4767 (X35)
                  "ts_queues": {q: [cc.expected_bytes(i).hex() for i in items]
                                for q, items in ((sc.get("initial") or {}).get("ts_queues") or {}).items()}}
                 for sc in case.scenarios]  # fmt: skip
    return {
        "transactions": case.csd["transactions"],
        "programs": sorted(case.csd["programs"]),  # #4004: LINK's PGMIDERR
        "clock": case.data["clock"],  # #4006: the scheduler's virtual clock and terminal
        "terminal": case.data["terminal"],
        "terminal_device": terminal_device(case),  # #4413: LUTYPE2 raises EOC on RECEIVE
        "uctranst": terminal_uctranst(case),  # #4415: INQUIRE TERMINAL UCTRANST
        "origin": case.data.get("origin"),  # #4415 slice 2: INQUIRE ASSOCIATION's origin data (terminal-started tasks)
        **{k: case.csd[k] for k in ("twasize", "userarealen") if case.csd.get(k)},  # #5079 (X59): only when stated
        **(
            {"wrkarea": case.data["wrkarea"]} if case.data.get("wrkarea") else {}
        ),  # #5079 (X59): SIT WRKAREA, not a CSD resource
        "urimaps": [list(u) for u in case.csd.get("urimaps") or []],  # #4270 zECS (X32): INQUIRE URIMAP's browse
        "doctemplates": case.data.get("doctemplates"),  # #4769 zECS (X33): DOCUMENT CREATE TEMPLATE's text per name
        "services": services,
        "screens": screens,
        "scenarios": scenarios,
    }


def area_env(case: cc.Case, transid: str, ts: str) -> str:
    """#5079 slice 2b (X59): the stub's TWA / TCTUA sizes from the CSD and the CWA's (SIT WRKAREA, case data), only when stated;
    the TCTUA's and the CWA's bytes persist in a file beside the scenario's TS dir, which the next task reads."""
    twa = (case.csd.get("twasize") or {}).get(transid)
    ua = (case.csd.get("userarealen") or {}).get(case.data["terminal"])
    wrk = case.data.get("wrkarea")
    return (
        (f"GGCICS_TWASIZE={twa} " if twa else "")
        + (f"GGCICS_WRKAREA={wrk} GGCICS_CWA=/work/{ts}.cwa " if wrk else "")
        + (f"GGCICS_USERAREALEN={ua} GGCICS_TCTUA=/work/{ts}.tctua " if ua else "")
    )


def terminal_device(case: cc.Case) -> str:
    """#4413: the DEVICE of the case terminal's TYPETERM in the case CSD; the reference region's 3270 logical unit
    (SPEC section 2) when the CSD does not define the terminal."""
    return (case.csd.get("terminals") or {}).get(case.data["terminal"], "3270")


# #4415 (register X26): the terminal's UCTRANST from its TYPETERM's UCTRAN, name for name (IBM, INQUIRE TERMINAL: "The
# value comes from the UCTRAN option of the associated TYPETERM definition")
UCTRAN_TO_UCTRANST = {"YES": "UCTRAN", "NO": "NOUCTRAN", "TRANID": "TRANIDONLY"}


def mapsets_env(case: cc.Case) -> str:
    """#4270 (X31): the case's mapsets and their maps as the stub's $GGCICS_MAPSETS (`MAPSET=MAP,MAP;MAPSET=MAP`), so a
    SEND MAP / RECEIVE MAP for a map its mapset does not hold abends ABM0. The case's `maps` name each map's mapset."""
    held: dict[str, list[str]] = {}
    for m, spec in sorted(case.data["maps"].items()):
        held.setdefault(spec["mapset"], []).append(m)
    return ";".join(f"{ms}={','.join(maps)}" for ms, maps in sorted(held.items()))


def origin_env(case: cc.Case) -> str | None:
    """#4415 slice 2 (X29): the case's stated origin data as the stub's $GGCICS_ORIGIN (applid,userid,facilname,
    networkid,faciltype); None when the case states none (INQUIRE ASSOCIATION is then refused by both runtimes)."""
    o = case.data.get("origin")
    if not o:
        return None
    return ",".join(str(o[k]) for k in ("applid", "userid", "facilname", "networkid", "faciltype"))


def terminal_uctranst(case: cc.Case) -> str | None:
    """The case terminal's UCTRANST, None when the case CSD does not state its TYPETERM's UCTRAN (an INQUIRE TERMINAL
    UCTRANST is then refused by both runtimes, never answered from a guessed default)."""
    return UCTRAN_TO_UCTRANST.get((case.csd.get("uctran") or {}).get(case.data["terminal"], ""))


# A generated contract DTO's field comment (cobol_to_java_transaction_forge): `// WS-CA: PIC X, offset 0, 1 bytes (...)`.
_DTO_LAYOUT = re.compile(
    r"^\s*// ([A-Z0-9][A-Z0-9-]*): PIC (\S+)(?: ([A-Z0-9-]+))?, offset (\d+), (\d+) bytes \(", re.M
)


def dto_layout(src: Path, cls: str) -> list[dict[str, Any]] | None:
    """#3989: a generated DTO's record layout ([{name, pic, usage, offset, bytes}]) from its field comments, or
    None for a composite one (a part's fields are in another class) or one with no commented fields."""
    import equivalence_cics as ec

    path = ec.java_class_file(src, cls)
    if path is None:
        return None
    text = path.read_text(encoding="utf-8")
    if " -> " in text:
        return None
    fields = [{"name": n, "pic": pic, "usage": usage or None, "offset": int(off), "bytes": int(size)}
              for n, pic, usage, off, size in _DTO_LAYOUT.findall(text)]  # fmt: skip
    return fields or None


def dto_bytes(values: dict[str, Any], layout: list[dict[str, Any]] | None) -> tuple[bytes | None, int]:
    """#3989: a DTO's record as EBCDIC bytes, each field encoded by its PICTURE and USAGE (text blank-padded,
    zoned / COMP / COMP-3 numbers), and how many of its leading bytes are known: a null field's bytes are
    not, so the record is known up to the first null field -- enough for a LENGTH that stops short of it (a
    caller's 10-byte version-1 block passed through a callee's 80-byte DTO). (None, 0) when a field will not
    encode."""
    import equivalence_cics as ec

    if not layout:
        return None, 0
    rec = bytearray(b"\x40" * max(f["offset"] + f["bytes"] for f in layout))
    known = len(rec)
    for f in layout:
        v = values.get(f["name"])
        if v is None:
            known = min(known, f["offset"])
            continue
        try:
            rec[f["offset"] : f["offset"] + f["bytes"]] = ec.encode_field(
                v, f["pic"], f["usage"], f["bytes"], cc.EBCDIC
            )
        except (ArithmeticError, ValueError, TypeError, UnicodeError):
            return None, 0
    return bytes(rec), known


def _raw_area(desc: dict[str, Any], length: Any) -> cc.RawArea | None:
    """#3989: a COMMAREA no generated DTO describes (a plain PIC X(n) item), passed as a String of its characters
    or a byte[] of its EBCDIC bytes (Jackson writes those as base64): its bytes, cut to LENGTH when given."""
    value = desc.get("value")
    if desc["class"] == "java.lang.String" and isinstance(value, str):
        data = value.encode(cc.EBCDIC, "replace")
    elif desc["class"] == "[B" and isinstance(value, str):
        data = base64.b64decode(value)
    else:
        return None
    return cc.RawArea(data[:length] if isinstance(length, int) else data, cc.EBCDIC)


def _java_area(desc: dict[str, Any] | None, src: Path, shapes: dict[str, Any],
               length: Any = None) -> Any:  # fmt: skip
    """A DTO the Java side recorded, as field values with the length CicsTask gave it (#4009: a
    LENGTH, or its whole record when none was given), and its record's bytes (#3989); a String or byte[]
    COMMAREA as its bytes (a RawArea)."""
    import equivalence_cics as ec

    if desc is None:
        return None
    cls = desc["class"]
    if cls in ("java.lang.String", "[B"):
        return _raw_area(desc, length)
    if cls not in shapes:
        # qualified: the contract DTO, not the entity of that name (#4011)
        shapes[cls] = (ec.dto_shape(src, cls), dto_layout(src, cls))
    shape, layout = shapes[cls]
    values = ec.from_java(desc["value"], shape)
    data, known = dto_bytes(values, layout)
    return cc.FieldArea(values, cc.FULL if length is None else length, data, known)


def _with_answered_bytes(area: Any, answer: str | None, page: str = RUNTIME_PAGE,
                         layout: list[dict[str, Any]] | None = None) -> Any:  # fmt: skip
    """#4965: the bytes the byte-carrying handleTransaction answered (lastAnswerBytes()) are the RETURN's COMMAREA
    bytes -- every one, a numeric DISPLAY field holding spaces too, which the DTO cannot carry -- so they, not the
    bytes encoded from the DTO, are what the log's hex / text / layout is compared with. #5053: they are in the
    runtime's `page` (a det port writes CobolRecords.charset(), the one run_java sets), the log's in CCSID 037
    (PC-STEP X'31' against X'F1'): converted by the page, DISPLAY bytes through it, binary ones (`layout`) as they are."""
    if answer is None or not isinstance(area, cc.FieldArea):
        return area
    data = cc.to_ebcdic(cc.RawArea(base64.b64decode(answer), page), layout)
    if isinstance(area.length, int) and not isinstance(area.length, bool):
        data = data[: area.length]  # #5053: a LINK's area is its caller's whole storage; the LINK's LENGTH bounds it
    return dataclasses.replace(area, data=data, known=len(data))


def _answered_layout(desc: dict[str, Any] | None, shapes: dict[str, Any]) -> list[dict[str, Any]] | None:
    """The record layout of the DTO class a Java COMMAREA description names (cached by _java_area), if any."""
    return shapes[desc["class"]][1] if desc and desc.get("class") in shapes else None


def java_send_map(screen: Screen, e: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    """#4001: what BMS sends for a CicsTask SEND-MAP event -- the screen's values as each field's
    data (EBCDIC), its subfields' attribute / colour / highlight bytes and lengths -- resolved from
    the map exactly as the stub's symbolic map is."""
    import cics_bms

    values = e.get("screen")
    subs = e.get("subfields") or {}
    program = None
    if values is not None:
        program = {}
        for f in screen.bms.named():
            v, sub = (values or {}).get(f.name), subs.get(f.name) or {}
            data = cics_bms.ebcdic(str(v)) if v not in (None, "") else None
            program[f.name] = cics_bms.ProgramField(length=sub.get("length"), attr=sub.get("attr"),
                                                     color=sub.get("color"), hilight=sub.get("hilight"),
                                                     data=data)  # fmt: skip
    return cics_bms.send_map(screen.bms, program, e.get("options") or [], e.get("cursor"))


def _java_file_event(kind: str, e: dict[str, Any]) -> dict[str, Any]:
    """#4443: a READ / REWRITE / UNLOCK CicsTask recorded, as the log's keys: `update`, `resp2` and `length` only when
    the command carries them. A LENGERR READ asserts its RESP only (SPEC section 2, Files), so its RESP2 is left out."""
    ev: dict[str, Any] = {"file": e.get("file"), "resp": e.get("resp")}
    if e.get("set"):  # #6262: the SET form
        ev["set"] = True
    if kind in ("WRITE", "DELETE"):  # #6262: the key on entry (a DELETE of the held / token record has none)
        if e.get("ridfld") is not None:
            ev["ridfld"] = base64.b64decode(e["ridfld"])
        if e.get("generic"):
            ev["generic"] = True
    if kind in ("STARTBR", "READNEXT", "READPREV"):  # #6262: the key on entry; STARTBR's mode, a browse read's record
        ev["ridfld"] = base64.b64decode(e["ridfld"]) if e.get("ridfld") is not None else None
        if e.get("rba"):  # the RBA browse: as the stub's `rba=` line, the file and RESP; RIDFLD is no key (SPEC 6.2)
            ev["ridfld"] = cc.Unmodelled("an RBA browse's event")
        elif kind == "STARTBR":
            ev["mode"] = e.get("mode")
        else:
            if e.get("length") is not None:
                ev["length"] = e["length"]
            b64 = e.get("data")
            ev["data"] = cc.RawArea(base64.b64decode(b64), cc.EBCDIC) if b64 is not None else None
    if kind == "READ":
        ev["ridfld"] = base64.b64decode(e["ridfld"]) if e.get("ridfld") is not None else None
        if e.get("update"):
            ev["update"] = True
        if e.get("length") is not None:
            ev["length"] = e["length"]
    if kind in ("READ", "REWRITE", "WRITE"):
        b64 = e.get("data")
        ev["data"] = cc.RawArea(base64.b64decode(b64), cc.EBCDIC) if b64 is not None else None
    if (
        e.get("resp2") is not None
        and not e.get("rba")
        and not (kind in ("READ", "READNEXT", "READPREV") and e.get("resp") == "LENGERR")
    ):
        ev["resp2"] = e["resp2"]
    return ev


def java_actual(case: cc.Case, raw: dict[str, Any], src: Path,
                screens: dict[str, Screen] | None = None) -> dict[str, Any]:  # fmt: skip
    """The generated test's output for one scenario -> an actual log for the comparison."""
    shapes: dict[str, Any] = {}
    tasks = []
    for t in raw.get("tasks", []):
        calen = t.get("eibcalen")
        ca = _java_area(t.get("commarea"), src, shapes, calen)
        frame = {k: t.get(k) for k in ("termid", "at", "trigger", "eibaid")}  # #4006: the Java scheduler's
        task: dict[str, Any] = {"transid": t["transid"], "program": t["program"], **frame,
                                "eibcalen": 0 if ca is None else cc.FULL if calen is None else calen,
                                "commarea": ca, "end": t["end"], "events": []}  # fmt: skip
        for e in t["events"]:
            kind = e["event"]
            ev: dict[str, Any] = {"event": kind, "program": e.get("program")}
            if kind == "SEND-MAP":
                ev.update(map=e.get("map"), mapset=e.get("mapset"), options=e.get("options") or [])
                screen = screens.get(ev["map"]) if screens is not None else None
                if screen is None:
                    ev["fields"] = {k: {"data": v} for k, v in (e.get("screen") or {}).items()}
                else:
                    ev["fields"], ev["cursor"] = java_send_map(screen, e)
            elif kind == "SEND-TEXT":  # #4009: the FROM data, its LENGTH and options
                ev.update(text=e.get("text"), length=e.get("length"), options=e.get("options") or [])
            elif kind == "SEND-CONTROL":  # #4413: the options, CURSOR's offset
                ev["options"] = e.get("options") or []
                if e.get("cursor") is not None:
                    ev["cursor"] = {"offset": e["cursor"]}
            elif kind == "RECEIVE":  # #4005: the data as text, the area's bytes in the stub's page
                ev.update(resp=e.get("resp"), length=e.get("length"),
                          data=cc.RawArea(str(e.get("data") or "").encode("latin-1"), "latin-1"))  # fmt: skip
            elif kind in ("READQ-TS", "WRITEQ-TS"):  # #4002: byte[] data arrive as base64, EBCDIC bytes
                b64 = e.get("data")
                data = cc.RawArea(base64.b64decode(b64), cc.EBCDIC) if b64 is not None else None
                ev.update(queue=e.get("queue"), item=e.get("item"), resp=e.get("resp"), data=data)
                if kind == "READQ-TS":
                    ev["length"] = e.get("length")
            elif kind in (
                "READ",
                "REWRITE",
                "WRITE",
                "DELETE",
                "UNLOCK",
                "STARTBR",
                "READNEXT",
                "READPREV",
                "ENDBR",
            ):  # #4443, #6262: byte[] ridfld / data arrive as base64, EBCDIC bytes
                ev.update(_java_file_event(kind, e))
            elif kind == "WRITE-OPERATOR":  # #4270 zECS (X32): the console message, as the text CicsTask recorded
                ev.update(data=cc.RawArea(str(e.get("text") or "").encode("latin-1"), "latin-1"), resp=e.get("resp"))
            elif kind == "RECEIVE-MAP":
                ev.update(map=e.get("map"), mapset=e.get("mapset"), resp=e.get("resp"))
            elif (
                kind == "RETURN" and e.get("resp") is not None
            ):  # a RETURN that failed: IMMEDIATE (X27), or CHANNEL (#5005)
                ev.update(level=e["level"], transid=e.get("transid"), resp=e["resp"], resp2=e.get("resp2"))
                if e.get("channel") is not None:
                    ev["channel"] = e["channel"]
                else:
                    ev["immediate"] = True
            elif kind == "RETURN" and (e.get("level") or 1) > 1:  # #4004: back to the linking program
                # #3989: the caller sees the LINK's LENGTH bytes of it (CicsTask records that LENGTH here)
                # #5053: and, when the program took the LINK's COMMAREA bytes, the bytes lastLinkBytes() answered
                ev.update(level=e["level"], caller_commarea=_with_answered_bytes(
                    _java_area(e.get("caller_commarea"), src, shapes, e.get("length")), e.get("area_bytes"),
                    RUNTIME_PAGE, _answered_layout(e.get("caller_commarea"), shapes)))  # fmt: skip
            elif kind == "RETURN":
                ev.update(level=1, transid=e.get("transid"),
                          commarea=_with_answered_bytes(_java_area(e.get("commarea"), src, shapes, e.get("length")),
                                                        e.get("answer_bytes"), RUNTIME_PAGE,
                                                        _answered_layout(e.get("commarea"), shapes)))  # fmt: skip
                if e.get("immediate"):  # #4270 (X27)
                    ev["immediate"] = True
                if e.get("channel") is not None:  # #5005 (X17): RETURN TRANSID CHANNEL
                    ev["channel"] = e["channel"]
            elif kind == "LINK":
                # #5053: the bytes the caller handed the LINK (the event's `area`, in the runtime page) are the sent
                # COMMAREA's bytes -- a numeric DISPLAY field holding spaces too, which the DTO cannot carry
                ev.update(target=e.get("target"), length=e.get("length"), resp=e.get("resp"), resp2=e.get("resp2"),
                          commarea=_with_answered_bytes(_java_area(e.get("commarea"), src, shapes, e.get("length")),
                                                        e.get("area"), RUNTIME_PAGE,
                                                        _answered_layout(e.get("commarea"), shapes)))  # fmt: skip
            elif kind == "XCTL":  # #4008: LENGTH, RESP, RESP2 (a whole-record DTO's LENGTH is not the log's)
                length = e.get("length")
                ca = _java_area(e.get("commarea"), src, shapes, length)
                if length is None:
                    length = cc.Unmodelled("XCTL LENGTH of a whole-record COMMAREA") if ca is not None else 0
                ca = _with_answered_bytes(
                    ca, e.get("area"), RUNTIME_PAGE, _answered_layout(e.get("commarea"), shapes)
                )  # #5053
                ev.update(target=e.get("target"), commarea=ca, length=length, resp=e.get("resp"), resp2=e.get("resp2"))
            elif kind == "START":  # #4006: FROM data as base64, EBCDIC bytes; REQID only if the program named one
                b64 = e.get("from")
                ev.update({k: e[k] for k in ("transid", "termid", "interval", "time", "reqid", "protect", "resp",
                                              "resp2", "expires", "rtransid", "rtermid", "queue") if k in e})  # fmt: skip
                ev["from"] = cc.RawArea(base64.b64decode(b64), cc.EBCDIC) if b64 is not None else None
            elif kind == "RETRIEVE":
                b64 = e.get("data")
                ev.update(resp=e.get("resp"), length=e.get("length"),
                          data=cc.RawArea(base64.b64decode(b64), cc.EBCDIC) if b64 is not None else None)  # fmt: skip
                ev.update({k: e[k] for k in ("rtransid", "rtermid", "queue") if k in e})  # #4270: only those asked for
            elif kind == "CANCEL":
                ev.update(reqid=e.get("reqid"), resp=e.get("resp"))
            elif kind == "RUN":  # #4270
                ev.update({k: e[k] for k in ("transid", "resp", "resp2") if k in e})
            elif kind == "WEB-RECEIVE":  # #4767 (X38): the body the task read; RESP2 where IBM documents it
                ev.update(_web_receive_event(e.get("resp"), e.get("resp2"), e.get("body")))
            elif kind == "WEB-SEND":  # #4767 (X37): the response the task sent
                ev.update(_web_send_event(e.get("status"), e.get("statustext"), e.get("mediatype"),
                                          str(e.get("body") or "").encode("latin-1"), e.get("resp"), e.get("resp2")))  # fmt: skip
            elif kind == "WEB-HEADER":  # #4767 (X38): CicsTask's name for SPEC's WEB-WRITE-HTTPHEADER
                ev.update(_web_header_event(e.get("name"), e.get("value"), e.get("resp"), e.get("resp2")))
            elif kind in _WEB_CLIENT_KEYS:  # #4767 (X35): the client-side session, as CicsTask recorded it
                ev.update(_web_client_event(kind, e.get("host"), e.get("scheme"), e.get("method"), e.get("path"),
                                            e.get("status"), e.get("tolength"), e.get("into"), e.get("resp"),
                                            e.get("resp2")))  # fmt: skip
            elif kind == "ABEND":  # #4003: cause, condition, outcome and the exit, as CicsTask records them
                ev.update({k: e[k] for k in ("abcode", "cause", "condition", "outcome", "exit") if k in e})
            else:
                ev["message"] = e.get("message")
            task["events"].append(ev)
        tasks.append(task)
    final = {q: [bytes.fromhex(i) for i in items] for q, items in (raw.get("ts_queues") or {}).items()}
    sc = next((s for s in case.scenarios if s["id"] == raw.get("_scenario")), {}) if case is not None else {}
    tasks = http_order(tasks)
    return {"tasks": tasks, "stopped": raw.get("stopped"), "final": {"ts_queues": final},
            **(http_peer_log(case, sc, tasks) if case is not None else {})}  # fmt: skip


class JavaRunError(RuntimeError):
    """The generated test could not run; `detail` is Maven's error lines."""

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail


def run_java(case: cc.Case, project: Path, work: Path, offline: bool, facades: bool = False,
             entries: dict[str, list[dict[str, Any]]] | None = None,
             byte_runs: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:  # fmt: skip
    """Every scenario through the generated services; {scenario: actual log}. Raises RuntimeError when
    the test itself cannot run (the project does not start). #4343: `facades` enters each task through the
    program's deployed entry point; `entries` gets, per scenario, the entry point each program ran by. #4965: each
    facade scenario also runs through the byte-carrying handleTransaction overload; `byte_runs` gets the log of
    those that entered by one."""
    import equivalence_java as ej

    src = project / "src/main/java"
    test = project / "src/test/java" / ej.PKG_DIR / "EquivalenceRunTest.java"
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text(_JAVA_TEST.replace("@PKG@", ej.PKG), encoding="utf-8")
    inputs, out = work / "in", work / "out"
    for d in (inputs, out):
        d.mkdir(parents=True, exist_ok=True)
    (inputs / "plan.json").write_text(json.dumps(java_plan(case, src), indent=1), encoding="utf-8")
    props = f"{JVM_SHORT_RUN_FLAGS} -Dequivalence.in={inputs} -Dequivalence.out={out} {ej.jvm_args(ej.environment('default'))}"  # fmt: skip
    props += f" -Dgitgalaxy.data.charset={java_charset_name(RUNTIME_PAGE)}"  # #5053: the page the answered bytes are in
    if facades:
        props += " -Dequivalence.facades=true"
    ok, errors = maven(project, ["test", "-Dtest=EquivalenceRunTest", "-Dsurefire.failIfNoSpecifiedTests=false",
                                 f"-DargLine={props}"], offline, work / "maven.log")  # fmt: skip
    if not ok:
        raise JavaRunError(f"the Java run failed: {errors.splitlines()[0] if errors else 'mvn test'}", errors)
    result = {}
    screens = case_screens(case)
    for sc in case.scenarios:
        f = out / f"{sc['id']}.json"
        raw = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {"tasks": [], "stopped": "no output"}
        raw["_scenario"] = sc["id"]
        if entries is not None:
            entries[sc["id"]] = raw.get("entries") or []
        result[sc["id"]] = java_actual(case, raw, src, screens)
        fb = out / f"{sc['id']}.bytes.json"  # #4965: the byte-carrying overload's run, when a task entered by it
        if byte_runs is not None and fb.is_file():
            braw = json.loads(fb.read_text(encoding="utf-8"))
            braw["_scenario"] = sc["id"]
            byte_runs[sc["id"]] = java_actual(case, braw, src, screens)
    return result


# ---- the async scheduler and channel hand-off (#4950, X18) --------------------------------------
_EXEC_CICS = re.compile(r"\bEXEC\s+CICS\b(.*?)\bEND-EXEC\b", re.I | re.S)


def async_refusals(source: str) -> list[str]:
    """The async-CICS members of one program the runner does not model, by name (X18; empty when it uses none).

    The runner runs a RUN TRANSID child as SPEC section 4 says (after its parent has ended) and has no CHILD or channel
    event in the log (section 6.2), so a program whose result turns on the region's scheduler or on a channel handed
    to a started or run task cannot be compared. A parent that never waits and RUNs a child is not listed."""
    text = "\n".join(ln for ln in source.splitlines() if not (len(ln) > 6 and ln[6] in "*/"))
    cmds = [" ".join(m.group(1).upper().split()) for m in _EXEC_CICS.finditer(text)]
    out: list[str] = []

    def has(cmd: str, *words: str) -> bool:
        return any(c.split(" ")[0] == cmd and all(re.search(rf"\b{w}\b", c) for w in words) for c in cmds)

    for verb in ("START", "RUN"):
        if has(verb, "CHANNEL"):
            out.append(f"scheduler: {verb} CHANNEL (the channel copy handed to the task is not modelled, X18)")
    if has("FETCH"):
        waits = any(c.startswith("FETCH ") and not re.search(r"\bNOSUSPEND\b", c) for c in cmds)
        out.append("scheduler: " + ("a waiting FETCH (child dispatch at a wait" if waits else "FETCH NOSUSPEND (no child schedule")
                   + " is not modelled, X18)")  # fmt: skip
    if has("FREE", "CHILD"):
        out.append("scheduler: FREE CHILD (no child schedule is modelled, X18)")
    if has("RUN") and (has("DELAY") or any(c.startswith("FETCH ") for c in cmds)):
        out.append(
            "scheduler: a parent that waits (DELAY or FETCH) with a RUN child (dispatch at the wait is not modelled, X18)"
        )
    return list(dict.fromkeys(out))


def case_async_refusals(case: cc.Case) -> list[str]:
    """async_refusals over every COBOL source of the case."""
    out: list[str] = []
    for rel in case.data["sources"]["cobol"]:
        out.extend(async_refusals((case.dir / rel).read_text(encoding="utf-8")))
    return list(dict.fromkeys(out))


# ---- the COBOL side ------------------------------------------------------------------------------
def translate_programs(case: cc.Case) -> dict[str, Any]:
    """{program: (translated source, takes a COMMAREA) or the Unsupported the translator raised}."""
    import equivalence_cics as ec

    out: dict[str, Any] = {}
    for rel in case.data["sources"]["cobol"]:
        prog = Path(rel).stem.upper()
        try:
            out[prog] = ec.translate((case.dir / rel).read_text(encoding="utf-8"))
        except ec.Unsupported as e:
            out[prog] = e
    return out


def _eib_datetime(when: datetime.datetime) -> tuple[str, str]:
    """EIBDATE 0CYYDDD and EIBTIME 0HHMMSS as the driver reads them."""
    day = when.timetuple().tm_yday
    return f"{when.year - 1900:03d}{day:03d}".rjust(7, "0")[-7:], "0" + when.strftime("%H%M%S")


@dataclasses.dataclass
class Screen:
    """One map (#4001): its BMS definition and its symbolic map's input (L, F, I) and output (C, H,
    O) fields by name."""

    bms: Any  # cics_bms.BmsMap
    inp: dict[str, dict[str, Any]]
    out: dict[str, dict[str, Any]]

    @property
    def size(self) -> int:
        return max((f["offset"] + f["bytes"] for f in [*self.inp.values(), *self.out.values()]), default=0)

    def program_fields(self, data: bytes) -> dict[str, Any]:
        """The symbolic map's bytes (the stub's page, latin-1) -> what the program left per field:
        attribute, colour and highlight bytes as they are (EBCDIC: see DFHBMSCA.cpy), data transcoded."""
        import cics_bms

        def raw(f: dict[str, Any] | None) -> bytes | None:
            return None if f is None or f["offset"] >= len(data) else data[f["offset"] : f["offset"] + f["bytes"]]

        def byte(f: dict[str, Any] | None) -> int | None:
            b = raw(f)
            return b[0] if b else None

        out = {}
        for bf in self.bms.named():
            n = bf.name
            length = raw(self.inp.get(f"{n}L"))
            text = raw(self.out.get(f"{n}O"))
            out[n] = cics_bms.ProgramField(
                length=int.from_bytes(length, "big", signed=True) if length else None,
                attr=byte(self.inp.get(f"{n}F")), color=byte(self.out.get(f"{n}C")),
                hilight=byte(self.out.get(f"{n}H")),
                data=cc.to_ebcdic(cc.RawArea(text, "latin-1")) if text is not None else None)  # fmt: skip
        return out

    def send(self, data: bytes | None, options: list[str], cursor: int | None) -> tuple[dict[str, Any], Any]:
        import cics_bms

        program = self.program_fields(data) if data else None
        return cics_bms.send_map(self.bms, program, options, cursor)

    def receive_input(self, typed: dict[str, str]) -> bytes:
        """RECEIVE MAP INTO's bytes for the fields the terminal transmitted: nulls elsewhere; each
        transmitted field's length and data, justified as its DFHMDF JUSTIFY says; a field sent
        empty (erased with ERASE EOF) has length 0 and the DFHBMEOF flag X'80'."""
        import cics_bms

        buf = bytearray(self.size)
        by_name = {f.name: f for f in self.bms.named()}
        for name, text in typed.items():
            bf, lf, ff, df = (
                by_name.get(name),
                self.inp.get(f"{name}L"),
                self.inp.get(f"{name}F"),
                self.inp.get(f"{name}I"),
            )
            if bf is None or lf is None or df is None:
                raise cc.CaseError(f"map {self.bms.name} has no input field {name}")
            buf[lf["offset"] : lf["offset"] + 2] = len(text).to_bytes(2, "big", signed=True)
            if not text:
                if ff is not None:
                    buf[ff["offset"]] = 0x80
                continue
            value = cics_bms.received_value(bf, text).encode("latin-1")
            buf[df["offset"] : df["offset"] + df["bytes"]] = value[: df["bytes"]]
        return bytes(buf)


_SCREENS: dict[Path, dict[str, Screen]] = {}


def case_screens(case: cc.Case) -> dict[str, Screen]:
    """Each map of the case with its BMS definition and symbolic map layout (#4001), read once per case."""
    if case.dir not in _SCREENS:
        _SCREENS[case.dir] = _read_screens(case)
    return _SCREENS[case.dir]


def _read_screens(case: cc.Case) -> dict[str, Screen]:
    import cics_bms
    import equivalence_common as common

    bms = cics_bms.load_maps([case.dir / p for p in case.data["sources"].get("bms", [])])
    out = {}
    for name, spec in case.data["maps"].items():
        if name not in bms:
            raise cc.CaseError(f"{case.id}: map {name} is in no BMS source")
        lay = {r: {f["name"]: f for f in common.layout_fields(case.dir, spec["copybook"], f"{name}{r}")} for r in "IO"}
        out[name] = Screen(bms[name], lay["I"], lay["O"])
    return out


def _key_ebcdic(rid_hex: str) -> bytes:
    """A key the stub logged as hex, in the log's CCSID 037. The program's text is ASCII; an X'FF' (HIGH-VALUES) is no
    text and stays X'FF' on both legs (#6262: a READPREV from the end), where latin-1 would make it X'DF'."""
    raw = bytes.fromhex(rid_hex)
    return b"".join(b"\xff" if b == 0xFF else bytes([b]).decode("latin-1").encode(cc.EBCDIC) for b in raw)


def _cobol_events(out: Path, program: str, screens: dict[str, Screen] | None = None) -> list[dict[str, Any]]:
    """The stub's events.txt -> events as SPEC 6.2 spells them (runtime bytes kept as RawArea). Each line
    names its issuing program (`pgm=`, #4004); `program` stands in where one does not."""
    import equivalence_cics as ec

    names = {v: k for k, v in ec.DFHRESP.items() if k != "DSIDERR"}
    events: list[dict[str, Any]] = []
    log = out / "events.txt"
    for line in log.read_text(encoding="latin-1").splitlines() if log.is_file() else []:
        seq, _, rest = line.partition(" ")
        verb, _, args = rest.partition(" ")
        blob = out / f"{seq}.bin"
        data = blob.read_bytes() if blob.is_file() else b""

        def arg(key: str) -> str:
            m = re.search(rf"\b{key}=(\S*)", args)
            return m.group(1) if m else ""

        m = re.search(r"\bopts=(.*)$", args)
        opts = m.group(1).split() if m else []
        issuer = arg("pgm") or program
        ev: dict[str, Any] = {"event": verb, "program": issuer}
        if verb == "SEND-MAP":
            ev.update(map=arg("map"), mapset=arg("mapset"), options=[o for o in opts if o in SEND_OPTIONS])
            screen = (screens or {}).get(ev["map"])
            if screen is not None:  # #4001: what BMS sends, resolved from the symbolic map and the BMS source
                cur = int(arg("cursor") or -1)
                ev["fields"], ev["cursor"] = screen.send(data if int(arg("len") or 0) else None, ev["options"],
                                                         cur if cur >= 0 else None)  # fmt: skip
        elif verb == "SEND-TEXT":
            text = cc.to_ebcdic(cc.RawArea(data, "latin-1"))
            ev.update(text=text, length=int(arg("len") or 0), options=[o for o in opts if o in SEND_OPTIONS])
        elif verb == "SEND-CONTROL":  # #4413
            ev["options"] = [o for o in opts if o in SEND_OPTIONS]
            cur = int(arg("cursor") or -1)
            if cur >= 0:
                ev["cursor"] = {"offset": cur}
        elif verb == "RECEIVE-MAP":
            ev.update(map=arg("map"), mapset=arg("mapset"), resp=names.get(int(arg("resp") or 0), arg("resp")))
        elif verb == "RECEIVE":  # #4005: `len` is LENGTH after the command, the blob what went INTO
            ev.update(resp=names.get(int(arg("resp") or 0), arg("resp")), length=int(arg("len") or 0),
                      data=cc.RawArea(data, "latin-1"))  # fmt: skip
        elif verb == "READQ-TS":  # #4002: length and data only where the command sets them (NORMAL, LENGERR)
            n = int(arg("len") or -1)
            item = arg("item")
            ev.update(queue=bytes.fromhex(arg("queue")).decode("latin-1"), item=item if item == "NEXT" else int(item),
                      resp=names.get(int(arg("resp") or 0), arg("resp")), length=n if n >= 0 else None,
                      data=cc.RawArea(data, "latin-1") if n >= 0 else None)  # fmt: skip
        elif verb == "WRITEQ-TS":
            resp = names.get(int(arg("resp") or 0), arg("resp"))
            ev.update(queue=bytes.fromhex(arg("queue")).decode("latin-1"), data=cc.RawArea(data, "latin-1"), resp=resp,
                      item=int(arg("item")) if resp == "NORMAL" else None)  # fmt: skip
        elif verb == "READQ-TD":  # #5079 (X57): the queue in hex; length and data only where a record was read
            n = int(arg("len") or -1)
            ev.update(queue=bytes.fromhex(arg("queue")).decode("latin-1"),
                      resp=names.get(int(arg("resp") or 0), arg("resp")), length=n if n >= 0 else None,
                      data=cc.RawArea(data, "latin-1") if n >= 0 else None)  # fmt: skip
        elif verb == "WRITEQ-TD":  # #5079 (X57): the queue in plain text; the record is logged whatever the answer
            ev.update(queue=arg("queue"), data=cc.RawArea(data, "latin-1"),
                      resp=names.get(int(arg("resp") or 0), arg("resp")))  # fmt: skip
        elif verb == "DELETEQ-TD":  # #5079 (X57)
            ev.update(queue=arg("queue"), resp=names.get(int(arg("resp") or 0), arg("resp")))
        elif verb == "WRITE-OPERATOR":  # #4270 zECS (X32): the text sent, in the stub's page
            ev.update(data=cc.RawArea(data, "latin-1"), resp=names.get(int(arg("resp") or 0), arg("resp")))
        elif verb == "RECEIVE-REFUSED":  # #4413
            ev = {"event": "DRIVER-ERROR", "program": issuer,
                  "message": "RECEIVE NOTRUNCATE leaving data retained on an LUTYPE2 terminal: EOC is not documented"}  # fmt: skip
        elif verb == "AID-REFUSED":  # #4414: what IBM's HANDLE AID does not say
            ev = {"event": "DRIVER-ERROR", "program": issuer,
                  "message": "HANDLE AID: a key deactivated while ANYKEY has a label" if arg("deactivated") else
                             "a HANDLE AID label and a condition on one input command: which CICS takes first is "
                             "not documented"}  # fmt: skip
        elif verb == "RECEIVE-WAIT":
            ev = {"event": "DRIVER-ERROR", "program": issuer,
                  "message": "a second terminal RECEIVE in one task waits for input no scenario step gives"}  # fmt: skip
        elif verb == "START":  # #4006: INTERVAL or TIME as given (hhmmss), REQID only if the program named one
            resp = names.get(int(arg("resp") or 0), arg("resp"))
            when = "time" if re.search(r"\btime=", args) else "interval"  # #4270: empty for an AFTER / AT out of range
            ev.update(transid=arg("transid"), termid=arg("termid") or None, **{when: arg(when) or None},
                      **({"reqid": arg("reqid")} if arg("reqid") else {}),
                      protect=arg("protect") == "1", resp=resp, expires=arg("expires") if resp == "NORMAL" else None,
                      **{"from": cc.RawArea(data, "latin-1") if arg("area") == "1" else None})  # fmt: skip
            if resp == "INVREQ" and arg("resp2") not in ("", "0"):  # #4270: RESP2 4 / 5 / 6, which IBM documents
                ev["resp2"] = int(arg("resp2"))
            ev.update(_named(args, ("rtransid", "rtermid", "queue")))
        elif verb == "RETRIEVE":
            n = int(arg("len") or -1)
            into = arg("into") != "0"  # #4270: a RETRIEVE with no INTO sets no LENGTH and moves no data
            ev.update(resp=names.get(int(arg("resp") or 0), arg("resp")), length=n if n >= 0 and into else None,
                      data=cc.RawArea(data, "latin-1") if n >= 0 and into else None)  # fmt: skip
            ev.update(_named(args, ("rtransid", "rtermid", "queue")))
        elif verb == "CANCEL":
            ev.update(reqid=arg("reqid"), resp=names.get(int(arg("resp") or 0), arg("resp")))
        elif verb == "WEB-RECEIVE":  # #4767 (X38): LENGERR 16 returned nothing (no data)
            ev.update(_web_receive_event(int(arg("resp") or 0), int(arg("resp2") or 0),
                                         None if arg("resp2") == "16" else data.decode("latin-1")))  # fmt: skip
        elif (
            verb == "WEB-SEND"
        ):  # #4767 (X37): the media type and status text in hex ('-': not given), the body in the blob

            def hx(k: str) -> str | None:
                return None if arg(k) in ("", "-") else bytes.fromhex(arg(k)).decode("latin-1")

            ev.update(_web_send_event(int(arg("status")), hx("stext"), hx("media"), data, int(arg("resp") or 0),
                                      int(arg("resp2") or 0)))  # fmt: skip
        elif verb == "WEB-HEADER":  # #4767 (X38): the stub's name for SPEC's WEB-WRITE-HTTPHEADER (hex fields)
            ev.update(_web_header_event(bytes.fromhex(arg("name")).decode("latin-1"),
                                        bytes.fromhex(arg("value")).decode("latin-1"), int(arg("resp") or 0),
                                        int(arg("resp2") or 0)))  # fmt: skip
        elif verb in _WEB_CLIENT_KEYS:  # #4767 (X35): hex fields ('-': none), the response the peer gave

            def hx2(k: str) -> str | None:
                return None if arg(k) in ("", "-") else bytes.fromhex(arg(k)).decode("latin-1")

            ev.update(_web_client_event(verb, hx2("host"), arg("scheme") or None, arg("method") or None, hx2("path"),
                                        int(arg("status")) if arg("status") else None,
                                        int(arg("tolen")) if arg("tolen") else None, hx2("into"),
                                        int(arg("resp") or 0), int(arg("resp2") or 0)))  # fmt: skip
        elif verb == "RUN":  # #4270: RUN TRANSID; RESP2 where IBM documents it (not NORMAL)
            resp = names.get(int(arg("resp") or 0), arg("resp"))
            ev.update(
                transid=arg("transid"), resp=resp, **({"resp2": int(arg("resp2") or 0)} if resp != "NORMAL" else {})
            )
        elif verb == "NOPROGRAM":
            ev = {"event": "DRIVER-ERROR", "program": arg("target"),
                  "message": f"{arg('target')} is not a translated program of the case"}  # fmt: skip
        elif verb == "LINK":  # #4004: RESP2 only where the command is not NORMAL (SPEC 6.2: where IBM documents it)
            resp = names.get(int(arg("resp") or 0), arg("resp"))
            ev.update(target=arg("target"), length=int(arg("len") or 0),
                      commarea=cc.RawArea(data, "latin-1") if arg("area") == "1" else None, resp=resp,
                      resp2=int(arg("resp2") or 0) if resp != "NORMAL" else None)  # fmt: skip
        elif verb in ("READ", "REWRITE", "UNLOCK"):  # #4443 A0b: SPEC 6.2 keys only where the command carries them
            ev.update(file=arg("file"), resp=names.get(int(arg("resp") or 0), arg("resp")))
            if verb == "READ":
                ev["ridfld"] = arg("key").encode(cc.EBCDIC)
                if arg("upd"):
                    ev["update"] = True
                if arg("set"):  # #6262
                    ev["set"] = True
                if arg("len"):
                    ev["length"] = int(arg("len"))
                ev["data"] = cc.RawArea(data, "latin-1") if ev["resp"] == "NORMAL" else None
            elif verb == "REWRITE":
                ev["data"] = cc.RawArea(data, "latin-1")
            # SPEC section 2 asserts LENGERR's RESP only
            if arg("resp2") and not (verb == "READ" and ev["resp"] == "LENGERR"):
                ev["resp2"] = int(arg("resp2"))
        elif verb in (
            "STARTBR",
            "READNEXT",
            "READPREV",
            "ENDBR",
        ):  # #6262: SPEC 6.2 keys only where the command carries them
            ev.update(file=arg("file"), resp=names.get(int(arg("resp") or 0), arg("resp")))
            if arg("rba"):  # the RBA browse (#4213) has no Java-leg event: its RIDFLD is a fullword, not a key
                ev["ridfld"] = cc.Unmodelled("an RBA browse's event")
            elif verb != "ENDBR":
                ev["ridfld"] = _key_ebcdic(arg("rid"))
            if verb == "STARTBR" and not arg("rba"):
                ev["mode"] = arg("mode")
            if verb in ("READNEXT", "READPREV") and not arg("rba"):
                if arg("set"):  # #6262
                    ev["set"] = True
                if arg("len"):
                    ev["length"] = int(arg("len"))
                ev["data"] = cc.RawArea(data, "latin-1") if ev["resp"] in ("NORMAL", "DUPKEY") else None
            if arg("resp2") and not (verb != "STARTBR" and verb != "ENDBR" and ev["resp"] == "LENGERR"):
                ev["resp2"] = int(arg("resp2"))
        elif verb in ("WRITE", "DELETE"):  # #6262: SPEC 6.2 keys only where the command carries them
            ev.update(file=arg("file"), resp=names.get(int(arg("resp") or 0), arg("resp")))
            if re.search(r"\brid=", args):  # a DELETE of the held or the token's record has no RIDFLD
                ev["ridfld"] = _key_ebcdic(arg("rid"))
            if verb == "WRITE":
                ev["data"] = cc.RawArea(data, "latin-1")
            elif arg("generic"):
                ev["generic"] = True
            if arg("resp2"):
                ev["resp2"] = int(arg("resp2"))
        elif verb in ("RETURN", "END"):
            level = int(arg("level") or 1)
            ev = {"event": "RETURN", "program": issuer, "level": level}
            if arg("resp"):  # #4270 (X27): a RETURN IMMEDIATE that failed (GGCRETI) -- it went on in the program
                ev.update(transid=arg("transid"), resp=names.get(int(arg("resp")), arg("resp")),
                          resp2=int(arg("resp2") or 0))  # fmt: skip
                if arg("channel"):  # #5005 (X17): or a RETURN CHANNEL below the highest level (GGCRETC)
                    ev["channel"] = arg("channel")
                else:
                    ev["immediate"] = True
            elif level == 1:
                ev.update(transid=arg("transid") or None, commarea=cc.RawArea(data, "latin-1") if data else None)
                if arg("immediate"):  # #4270 (X27)
                    ev["immediate"] = True
                if arg("channel"):  # #5005 (X17)
                    ev["channel"] = arg("channel")
            else:  # #4004: the LINK COMMAREA as the linking program now sees it (len -1: the LINK had none)
                ev["caller_commarea"] = cc.RawArea(data, "latin-1") if int(arg("len") or -1) >= 0 else None
        elif verb == "XCTL":  # #4008: RESP2 only where the command is not NORMAL (SPEC 6.2)
            has = arg("area") == "1" if arg("area") else bool(data)
            resp = names.get(int(arg("resp") or 0), arg("resp"))
            ev.update(target=arg("program"), length=int(arg("len") or 0), commarea=cc.RawArea(data, "latin-1") if has else None,
                      resp=resp, resp2=int(arg("resp2") or 0) if resp != "NORMAL" else None)  # fmt: skip
        elif verb == "ABEND":  # #4003: its cause, and which exit took it (program.label), if one did
            ev.update(abcode=arg("abcode"), cause=arg("cause"), outcome=arg("outcome"))
            if arg("condition"):
                cond = names.get(int(arg("condition")), arg("condition"))
                ev["condition"] = cond
                if ev["abcode"] != CONDITION_ABCODE.get(cond):
                    ev["abcode"] = cc.Unmodelled(f"ABEND code of an unhandled {cond}")
            if arg("exit"):
                exit_program, _, label = arg("exit").partition(".")
                ev["exit"] = {"program": exit_program, "label": label}
        events.append(ev)
    return events


def seed_ts(root: Path, queues: dict[str, list[Any]]) -> None:
    """#4002: a scenario's `initial` TS queues in the stub's store (ggcics.c): a directory per queue named
    by the name's hex, its items as 000001.bin, ... in the stub's page (latin-1; SPEC 6.1 text or hex is
    EBCDIC)."""
    root.mkdir(parents=True, exist_ok=True)
    for name, items in queues.items():
        d = root / name.encode("latin-1").hex().upper()
        d.mkdir(exist_ok=True)
        for n, item in enumerate(items, 1):
            (d / f"{n:06d}.bin").write_bytes(cc.expected_bytes(item).decode(cc.EBCDIC).encode("latin-1"))


def seed_td(root: Path, queues: dict[str, list[Any]]) -> None:
    """#5079 (X57): a scenario's `initial` TD queues in the stub's store (ggcics_transientdata.c td_dir): td-<hex of the
    name>/000001.bin, ... (no `head` file: the first record is the head), in the stub's page as seed_ts does."""
    root.mkdir(parents=True, exist_ok=True)
    for name, items in queues.items():
        d = root / ("td-" + name.encode("latin-1").hex().upper())
        d.mkdir(exist_ok=True)
        for n, item in enumerate(items, 1):
            (d / f"{n:06d}.bin").write_bytes(cc.expected_bytes(item).decode(cc.EBCDIC).encode("latin-1"))


def read_td(root: Path) -> dict[str, list[bytes]]:
    """#5079 (X57): every intrapartition TD queue the stub's store holds, the records not yet read (from `head` on) as
    EBCDIC bytes (the `final` state). A queue DELETEQ TD removed is absent: the comparison reads it as empty."""
    out: dict[str, list[bytes]] = {}
    for d in sorted(root.iterdir()) if root.is_dir() else []:
        if not d.name.startswith("td-") or not d.is_dir():
            continue
        head = (d / "head").read_text(encoding="ascii").split() if (d / "head").is_file() else []
        items, n = [], int(head[0]) if head else 1
        while (d / f"{n:06d}.bin").is_file():
            items.append(cc.to_ebcdic(cc.RawArea((d / f"{n:06d}.bin").read_bytes(), "latin-1")))
            n += 1
        out[bytes.fromhex(d.name[3:]).decode("latin-1")] = items
    return out


def seed_files(case: cc.Case, work: Path, sid: str) -> str:
    """#4443: the case's seeded files for the stub -- `data/<FILE>.dat` (one record per line, SPEC 2) as fixed-length
    records in `runs/<scenario>/files/<FILE>`, and the files.cfg text naming them (`FILE path reclen keyoff keylen`). The key is the
    leading bytes the case's RIDFLD names, so its length is the RIDFLD length of the expected READ events; a file no
    expected READ names is left out (the stub answers FILENOTFOUND, as before)."""
    keylen: dict[str, int] = {}
    for log in case.expected.values():
        for task in log.get("tasks") or []:
            for ev in task.get("events") or []:
                if ev.get("event") in ("READ", "STARTBR", "READNEXT", "READPREV") and isinstance(ev.get("ridfld"), str):
                    keylen.setdefault(ev["file"], len(ev["ridfld"]))
    rel = f"runs/{sid}/files"
    root = work / rel
    cfg = ""
    for name in sorted(case.csd.get("files") or ()):
        seed = case.dir / "data" / f"{name}.dat"
        if name not in keylen or not seed.is_file():
            continue
        lines = seed.read_bytes().splitlines()
        if not lines or len({len(x) for x in lines}) != 1:
            continue
        root.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(b"".join(lines))
        cfg += f"{name} /work/{rel}/{name} {len(lines[0])} 0 {keylen[name]}\n"
    return cfg


def read_ts(root: Path) -> dict[str, list[bytes]]:
    """#4002: every TS queue in the stub's store, its items as EBCDIC bytes (the `final` state)."""
    out: dict[str, list[bytes]] = {}
    for d in sorted(root.iterdir()) if root.is_dir() else []:
        if d.name.startswith("td-"):
            continue  # an intrapartition TD queue lives beside the TS queues (ggcics.c td_dir): read_td reads it
        items, n = [], 1
        while (d / f"{n:06d}.bin").is_file():
            items.append(cc.to_ebcdic(cc.RawArea((d / f"{n:06d}.bin").read_bytes(), "latin-1")))
            n += 1
        out[bytes.fromhex(d.name).decode("latin-1")] = items
    return out


class Container:
    """One long-lived GnuCOBOL container per case: `docker exec` per task, not `docker run`."""

    def __init__(self, work: Path) -> None:
        import equivalence_common as common

        user = ["--user", f"{os.getuid()}:{os.getgid()}"] if hasattr(os, "getuid") else []  # files stay the caller's
        try:
            proc = subprocess.run(["docker", "run", "-d", "--rm", *user, "-v", f"{work}:/work", common.IMAGE,  # noqa: S603, S607
                                   "sleep", "infinity"], capture_output=True, text=True, check=False,
                                  timeout=CONTAINER_START_TIMEOUT)  # fmt: skip
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"docker run timed out after {CONTAINER_START_TIMEOUT}s: cannot start the GnuCOBOL container"
            ) from exc
        if proc.returncode != 0:
            raise RuntimeError(f"cannot start the GnuCOBOL container: {_tail(proc.stderr, 3)}")
        self.id = proc.stdout.strip()

    def sh(self, script: str) -> subprocess.CompletedProcess[str]:
        try:
            import equivalence_common as common

            bounded = common.guarded(f"bash -c {shlex.quote(script)}", CONTAINER_EXEC_TIMEOUT - 10)  # see guarded()
            return subprocess.run(["docker", "exec", self.id, "bash", "-c", bounded],  # noqa: S603, S607
                                  capture_output=True, text=True, check=False,
                                  timeout=CONTAINER_EXEC_TIMEOUT)  # fmt: skip
        except subprocess.TimeoutExpired as exc:
            self.close()  # clean up container on timeout so nothing is orphaned
            raise RuntimeError(f"docker exec timed out after {CONTAINER_EXEC_TIMEOUT}s: {_tail(script, 3)}") from exc

    def close(self) -> None:
        try:
            subprocess.run(
                ["docker", "rm", "-f", self.id],
                capture_output=True,
                check=False,  # noqa: S603, S607
                timeout=CONTAINER_STOP_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            pass


def run_cobol(case: cc.Case, programs: dict[str, tuple[str, bool]], scenarios: list[str], ctx: cc.Context,
              work: Path, coverage: dict[str, dict[str, "cov.Hits"]] | None = None) -> dict[str, dict[str, Any]]:  # fmt: skip
    """Compile the case's translated programs, its dispatcher and task driver with the stub into one
    executable, then drive each scenario's terminal steps as tasks (#4004: one process per task, in which
    a LINK runs a new level and an XCTL its target at the same level); {scenario: actual}. #4023: compiled
    -ftraceall, each task traced; `coverage` gets {scenario: {program: what it executed}}."""
    import equivalence_cics as ec
    import equivalence_common as common

    work.mkdir(parents=True, exist_ok=True)
    src = work / "src"
    src.mkdir(exist_ok=True)
    for d in case.data["sources"]["copy"]:
        if not (case.dir / d).is_dir():
            continue  # a case with no copybooks declares a directory git cannot carry empty (hc-dcounters)
        for p in (case.dir / d).iterdir():
            if p.is_file():
                shutil.copy(p, src / p.name)
    for p in STUB_DIR.iterdir():
        shutil.copy(p, src / p.name)
    for prog, (text, _has_ca) in programs.items():
        (src / f"{prog}.cbl").write_text(text, encoding="latin-1")
    (src / "GGTASK.cbl").write_text(ec.task_driver(), encoding="ascii")
    (src / "GGCRUN.cbl").write_text(ec.task_dispatcher({p: ca for p, (_t, ca) in programs.items()}), encoding="ascii")
    common.comp5_layout_guard(src)  # #4751: a 1- or 2-digit COMP-5 is one byte in GnuCOBOL, a halfword on z/OS (C16)
    units = " ".join(f"src/{p}.cbl" for p in ["GGTASK", "GGCRUN", *programs])
    compile_lines = ["set -e", "cd /work", "mkdir -p bin",
                     f"cobc -x -std=ibm -fsign=EBCDIC -fstatic-call {cov.TRACE_FLAG} -I /work/src -o bin/task {units} src/ggcics.c"]  # fmt: skip
    box = Container(work)
    try:
        proc = box.sh("\n".join(compile_lines))
        (work / "compile.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(f"cobc: {_tail(proc.stdout + proc.stderr, 3)}")
        actual = {sid: run_scenario(case, next(s for s in case.scenarios if s["id"] == sid), box, work)
                  for sid in scenarios}  # fmt: skip
    finally:
        box.close()
    if coverage is not None:
        coverage.update(scenario_hits(case, programs, scenarios, work))
    return actual


def _epoch(when: datetime.datetime) -> int:
    """A virtual time as the stub's clock counts it (seconds, the naive time read as UTC)."""
    import calendar

    return calendar.timegm(when.timetuple())


def _named(args: str, keys: tuple[str, ...]) -> dict[str, str]:
    """#4270: the stub's `key=<hex>` values (RTRANSID / RTERMID / QUEUE, each only when the command named it),
    decoded and trimmed."""
    out = {}
    for k in keys:
        m = re.search(rf"\b{k}=([0-9A-Fa-f]*)(?:\s|$)", args)
        if m:
            out[k] = bytes.fromhex(m.group(1)).decode("latin-1").rstrip()
    return out


def _record(r: dict[str, Any]) -> dict[str, Any] | None:
    """#4270: a START request's data record -- FROM's bytes and RTRANSID / RTERMID / QUEUE -- or None when it gave
    none of them (IBM, EXEC CICS RETRIEVE: such a START stores no data, RETRIEVE gets ENDDATA)."""
    rec = {k: r.get(k) for k in ("data", "rtransid", "rtermid", "queue")}
    return rec if any(v is not None for v in rec.values()) else None


# ---- #4767 zECS (X37, X38): an inbound HTTP request is a task ---------------------------------------------
def _resp_name(code: Any) -> Any:
    import equivalence_cics as ec

    return {v: k for k, v in ec.DFHRESP.items() if k != "DSIDERR"}.get(code, code) if isinstance(code, int) else code


def _web_receive_event(resp: Any, resp2: Any, body: str | None) -> dict[str, Any]:
    """The WEB-RECEIVE event of SPEC 6.2 from what either side recorded: LENGTH is the bytes returned, `data` None when
    LENGERR 16 returned nothing; RESP2 only where IBM documents it (a condition)."""
    ev: dict[str, Any] = {"resp": _resp_name(resp), "length": None if body is None else len(body),
                          "data": None if body is None else cc.RawArea(body.encode("latin-1"), "latin-1")}  # fmt: skip
    if resp2:
        ev["resp2"] = resp2
    return ev


def _web_send_event(status: Any, statustext: str | None, mediatype: str | None, body: bytes, resp: Any,
                    resp2: Any) -> dict[str, Any]:  # fmt: skip
    """The WEB-SEND event of SPEC 6.2 from what either side recorded (FROM's bytes in the stub's page)."""
    ev: dict[str, Any] = {"status": status, "statustext": statustext, "mediatype": mediatype,
                          "from": cc.RawArea(body, "latin-1"), "resp": _resp_name(resp)}  # fmt: skip
    if resp2:
        ev["resp2"] = resp2
    return ev


def _web_header_event(name: Any, value: Any, resp: Any, resp2: Any) -> dict[str, Any]:
    """#4767 (X38): the WEB-WRITE-HTTPHEADER event of SPEC 6.2 from what either side recorded (a header is recorded only
    when the command is NORMAL). Both runtimes name the event WEB-HEADER; SPEC's name replaces it here."""
    ev: dict[str, Any] = {"event": "WEB-WRITE-HTTPHEADER", "name": name, "value": value, "resp": _resp_name(resp)}
    if resp2:
        ev["resp2"] = resp2
    return ev


def _web_client_event(kind: str, host: str | None, scheme: str | None, method: str | None, path: str | None,
                      status: int | None, tolength: int | None, into: str | None, resp: Any,
                      resp2: Any) -> dict[str, Any]:  # fmt: skip
    """#4767 (X35): the WEB-OPEN / WEB-CONVERSE / WEB-CLOSE event of SPEC 6.2 from what either side recorded: only the
    keys SPEC names (the host and request details the runtimes also record stay out), RESP2 only where IBM documents it,
    `into` the bytes INTO got (None when none)."""
    ev: dict[str, Any] = {"resp": _resp_name(resp)}
    if kind == "WEB-OPEN":
        ev.update(host=host, scheme=scheme)
    elif kind == "WEB-CONVERSE":
        ev.update(method=method, path=path, status=status, tolength=tolength,
                  into=cc.RawArea(into.encode("latin-1"), "latin-1") if into else None)  # fmt: skip
    if resp2:
        ev["resp2"] = resp2
    return ev


def origin_peers(case: cc.Case, sc: dict[str, Any]) -> list[dict[str, Any]] | None:
    """#4767 (X35): the origin servers a scenario's task reaches, as `equivalence_cics.http_peers` states them: SPEC names
    a peer by `host` and scripts only its responses, so each exchange's method, path and query are the ones the
    scenario's expected log gives the WEB-CONVERSE (on the host the preceding WEB-OPEN opened), and its response the
    peer's next scripted one. Both runtimes still refuse a request the peer states no response to, so a task whose
    request differs from the expected one fails. None when the case states no origin peer."""
    by_host = {p["host"]: p for p in (case.data.get("peers") or {}).values() if p.get("host")}
    if not by_host:
        return None
    peers: dict[tuple[str, str], dict[str, Any]] = {}
    given: dict[str, int] = {}
    cur: dict[str, Any] | None = None
    for t in case.expected[sc["id"]]["tasks"]:
        for e in t["events"]:
            if e["event"] == "WEB-OPEN" and e.get("host") in by_host:
                scheme = e.get("scheme") or "HTTP"
                cur = peers.setdefault((scheme, e["host"]), {"scheme": scheme, "host": e["host"],
                                                             "port": 443 if scheme == "HTTPS" else 80, "urimap": None,
                                                             "path": None, "exchanges": []})  # fmt: skip
            elif e["event"] == "WEB-CONVERSE" and cur is not None:
                script = by_host[cur["host"]]["responses"]
                k = given[cur["host"]] = given.get(cur["host"], -1) + 1
                if k < len(script):
                    r = script[k]
                    cur["exchanges"].append({"method": e["method"], "path": e["path"], "query": e.get("query") or "",
                                             "status": r["status"], "statustext": r.get("statustext") or "",
                                             "mediatype": r.get("mediatype") or "", "body": r.get("body") or ""})  # fmt: skip
    return list(peers.values()) or None


def server_urimap_matches(case: cc.Case, req: dict[str, Any]) -> list[str]:
    """The installed `USAGE(SERVER)` URIMAPs an inbound request matches (SPEC section 2, HTTP peer; IBM, URIMAP resource
    definitions): SCHEME the request's, HOST equal or the single `*`, PATH equal or ending in `*` as a prefix, STATUS
    enabled. The names, in the CSD's order."""
    out = []
    for u in case.csd.get("server_urimaps") or []:
        path = u["path"]
        if (u["scheme"] == req["scheme"].upper() and u["status"] == "ENABLED" and u["host"] in ("*", req["host"])
                and (req["path"] == path or (path.endswith("*") and req["path"].startswith(path[:-1])))):  # fmt: skip
            out.append(u["name"])
    return out


def http_plan(case: cc.Case, sc: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """The scenario's `requests` as the tasks they start: ([{index, at, transid, peer, request}] -- `request` the
    stated request as both runtimes take it (equivalence_cics.http_request) --, why the scenario cannot run). A
    request naming a peer the case does not state, or matching no or more than one server URIMAP, is a defined failure
    (`http-peer`): the case is invalid."""
    plan: list[dict[str, Any]] = []
    peers = case.data.get("peers") or {}
    for i, r in enumerate(sc.get("requests") or []):
        if r.get("peer") not in peers:
            return [], f"http-peer: request {i} names peer {r.get('peer')!r}, which the case does not state"
        if (r.get("mediatype") is None) != (r.get("body") is None):
            return [], f"http-peer: request {i} states a body without its media type (or the reverse)"
        hits = server_urimap_matches(case, r)
        if len(hits) != 1:
            return (
                [],
                f"http-peer: request {i} matches {len(hits)} server URIMAPs ({', '.join(hits) or 'none'}), not one",
            )
        uri = next(u for u in case.csd["server_urimaps"] if u["name"] == hits[0])
        transid = uri["transaction"]
        if transid not in case.csd["transactions"]:
            return [], f"http-peer: request {i}: URIMAP {hits[0]} names no installed transaction"
        req = {"scheme": r["scheme"].upper(), "host": r["host"], "port": 80, "method": r["method"],
               "version": "HTTP/1.1", "path": r["path"], "query": r.get("query") or "",
               "headers": [[k, v] for k, v in (r.get("headers") or {}).items()],  # SPEC 2: a name -> value object
               "mediatype": r.get("mediatype"), "body": r.get("body")}  # fmt: skip
        plan.append({"index": i, "at": r["at"], "transid": transid, "peer": r["peer"], "request": req})
    return plan, None


def http_order(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """An ACTION(EVENTUAL) WEB SEND is recorded after the task's other events (the stub and CicsTask send it as the task
    ends); SPEC 6.2 logs the response where the command is issued, so an `http` task's WEB-SEND is moved ahead of the
    RETURN it trails."""
    for t in tasks:
        evs = t["events"]
        if (t.get("trigger") or {}).get("kind") == "http" and evs and evs[-1]["event"] == "WEB-SEND":
            at = next((i for i, e in enumerate(evs) if e["event"] == "RETURN" and (e.get("level") or 1) == 1), None)
            if at is not None:
                evs.insert(at, evs.pop())
    return tasks


def http_peer_log(case: cc.Case, sc: dict[str, Any], tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """{"http_peer": why} when an `http` task's response is not the one its client peer states (SPEC section 2): each peer
    states one response per request it sends, in order; the task must send exactly one `WEB-SEND`, equal to it in status,
    media type and body. A response with no stated counterpart or a second response is the `http-peer` failure. {} when
    every response is the peer's."""
    peers = case.data.get("peers") or {}
    seen: dict[str, int] = {}
    for t in tasks:
        trig = t.get("trigger") or {}
        if trig.get("kind") != "http":
            continue
        i = trig["request"]
        peer = sc["requests"][i]["peer"]
        k = seen[peer] = seen.get(peer, -1) + 1
        sent = [e for e in t["events"] if e["event"] == "WEB-SEND"]
        where = f"request {i} (peer {peer})"
        if len(sent) != 1:
            return {"http_peer": f"{where}: the task sent {len(sent)} responses, SPEC allows exactly one"}
        stated = peers[peer]["responses"]
        if k >= len(stated):
            return {"http_peer": f"{where}: the task answered, the peer states no response #{k + 1}"}
        got = {"status": sent[0]["status"], "mediatype": sent[0]["mediatype"],
               "body": sent[0]["from"].data.decode("latin-1"),
               "headers": sorted((e["name"], e["value"]) for e in t["events"] if e["event"] == "WEB-WRITE-HTTPHEADER")}  # fmt: skip
        want_all = {"headers": {}, **stated[k]}  # a peer that states no headers expects none (SPEC section 2)
        want_all["headers"] = sorted(want_all["headers"].items())  # a header written twice is two headers
        for key, want in want_all.items():
            if got.get(key) != want:
                return {"http_peer": f"{where}: response {key} {got.get(key)!r}, the peer states {want!r}"}
    return {}


def step_commarea(step: dict[str, Any]) -> bytes | None:
    """#4443: the COMMAREA a typed-transid step enters with (a direct entry into a program that is otherwise only
    reached through a RETURN TRANSID): `commarea: {"hex": ..., "length": n}` is the first n bytes of the hex record,
    so a short EIBCALEN needs no neighbour program passing one. None: the task starts with no COMMAREA."""
    spec = step.get("commarea")
    if spec is None:
        return None
    data = bytes.fromhex(spec["hex"])
    return data[: spec.get("length", len(data))]


def drive_scenario(case: cc.Case, sc: dict[str, Any], run_one: Any) -> tuple[list[dict[str, Any]], str | None]:
    """The scheduler of SPEC section 4, for either side: (tasks in dispatch order, why it stopped early).

    `run_one(frame, transid, commarea, step, data, requests)` runs one task and returns it (its `events` as
    SPEC 6.2 spells them, its `end`): `frame` is what the scheduler decided (termid, at, trigger, eibaid),
    `data` the FROM data its RETRIEVEs get (expiry order), `requests` the unexpired interval-control
    requests (for CANCEL). When a task ends, its STARTs become requests (#4006: a PROTECT one only if the
    task ended normally; a CANCEL removes one); then, in order: expired requests (earliest expiry first,
    ties by issue order; one with a TERMID takes every expired request for its TRANSID and terminal), then
    the next operator step once its time has come. Virtual time jumps to the next expiry or step; after the
    last step, requests keep running until none expires before `until`."""
    clock = datetime.datetime.fromisoformat(case.data["clock"])
    until = clock + datetime.timedelta(seconds=sc["until"]) if sc.get("until") is not None else None
    terminal = case.data["terminal"]
    tasks: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    issued = 0
    pending: str | None = None
    pending_ca: bytes | None = None
    immediate: dict[str, Any] | None = None  # #4270 (X27): a RETURN IMMEDIATE's task, attached before anything else
    now = clock
    steps = list(enumerate(sc["steps"]))
    plan, why = http_plan(case, sc)  # #4767 (X37): the inbound HTTP requests, due like START requests
    if why:
        return tasks, why
    for h in plan:
        requests.append({"issue": h["index"] - 100000, "transid": h["transid"], "termid": None, "reqid": None,
                         "expires": clock + datetime.timedelta(seconds=h["at"]), "data": None, "kind": "http",
                         "task": None, "event": None, "http": h})  # fmt: skip

    def ended(task: dict[str, Any], at: datetime.datetime) -> None:
        nonlocal issued, pending, pending_ca, immediate
        for j, e in enumerate(task["events"]):
            if (
                e["event"] == "START"
                and e.get("resp") == "NORMAL"
                and not (e.get("protect") and task["end"] != "normal")
            ):
                issued += 1
                requests.append({"issue": issued, "transid": e["transid"], "termid": e.get("termid"),
                                 "expires": datetime.datetime.fromisoformat(e["expires"]), "reqid": e.get("reqid"),
                                 "data": e["from"].data if e.get("from") is not None else None,
                                 **{k: e.get(k) for k in ("rtransid", "rtermid", "queue")},  # #4270
                                 "task": len(tasks), "event": j})  # fmt: skip
            elif e["event"] == "RUN" and e.get("resp") == "NORMAL":  # #4270: a RUN TRANSID child, attached at once
                issued += 1
                requests.append({"issue": issued, "transid": e["transid"], "termid": None, "expires": at,
                                 "reqid": None, "data": None, "kind": "run", "task": len(tasks), "event": j})  # fmt: skip
            elif e["event"] == "CANCEL" and e.get("resp") == "NORMAL":
                r = next((r for r in requests if r["reqid"] == e["reqid"] and r["expires"] > at), None)
                if r is not None:
                    requests.remove(r)
        if task.get("termid") == terminal:  # the terminal's next input starts this task's RETURN TRANSID
            last = next((e for e in reversed(task["events"])
                         if e["event"] == "RETURN" and e.get("level") == 1 and e.get("resp") is None), None)  # fmt: skip
            pending = last["transid"] if last is not None and task["end"] == "normal" else None
            pending_ca = last["commarea"].data if pending and last is not None and last["commarea"] else None
            if pending and last.get("immediate"):  # #4270 (X27): the next task is not the terminal's next input
                immediate = {
                    "transid": pending,
                    "commarea": pending_ca,
                    "task": len(tasks),
                    "event": task["events"].index(last),
                }
                pending, pending_ca = None, None

    def run(frame: dict[str, Any], transid: str, commarea: bytes | None, step: dict[str, Any] | None,
            data: list[Any], at: datetime.datetime) -> None:  # fmt: skip
        unexpired = [(r["reqid"], _epoch(r["expires"])) for r in requests if r["reqid"] and r["expires"] > at]
        task = run_one(frame, transid, commarea, step, data, unexpired)
        tasks.append(task)
        ended(task, at)

    while True:
        if immediate is not None:  # #4270 (X27): attached at once, ahead of the expired requests and the next step
            im, immediate = immediate, None
            frame = {"termid": terminal, "at": now.strftime("%Y-%m-%dT%H:%M:%S"),
                     "trigger": {"kind": "immediate", "task": im["task"], "event": im["event"]},
                     "eibaid": None, "startcode": "TD"}  # fmt: skip
            run(frame, im["transid"], im["commarea"], None, [], now)
            continue
        expired = [r for r in requests if r["expires"] <= now]
        if expired:
            first = min(expired, key=lambda r: (r["expires"], r["issue"]))
            group = [first]
            if first["termid"]:
                group = sorted((r for r in expired if (r["transid"], r["termid"]) == (first["transid"], first["termid"])),
                               key=lambda r: (r["expires"], r["issue"]))  # fmt: skip
            for r in group:
                requests.remove(r)
            with_from = sum(r["data"] is not None for r in group)  # #4270 slice 3: ASSIGN STARTCODE (S / SD)
            frame = {"termid": first["termid"], "at": now.strftime("%Y-%m-%dT%H:%M:%S"),
                     "trigger": {"kind": first.get("kind", "start"), "task": first["task"], "event": first["event"]},
                     "eibaid": None, "startcode": "SD" if with_from == len(group) else "S" if not with_from else None}  # fmt: skip
            if first.get("kind") == "http":  # #4767: the request's task: no terminal, no STARTCODE it states
                frame["trigger"] = {"kind": "http", "request": first["http"]["index"]}
                frame["startcode"] = None
                frame["http_request"] = first["http"]["request"]
            run(frame, first["transid"], None, None, [_record(r) for r in group if _record(r) is not None], now)
            continue
        nxt = min((r["expires"] for r in requests), default=None)
        if steps:
            n, step = steps[0]
            at = clock + datetime.timedelta(seconds=step["at"])
            if nxt is not None and nxt <= at:
                now = max(now, nxt)
                continue
            steps.pop(0)
            now = max(now, at)
            transid, commarea = pending, pending_ca
            if transid is None:
                words = (step.get("text") or "").split()
                if not words:
                    return tasks, f"step {n}: no pending RETURN TRANSID and no transaction id typed"
                transid, commarea = words[0], step_commarea(step)
            run(task_frame(case, n, step), transid, commarea, step, [], now)
            continue
        if nxt is not None and until is not None and nxt < until:
            now = max(now, nxt)
            continue
        return tasks, None


def _expects_undefined_td_queue(case: cc.Case) -> bool:
    """#5079 (X57): a case whose oracle log has a TD command answered QIDERR (queue not in the CSD) while its CSD defines no
    TDQUEUE at all: the stub then needs an empty tdqueues.cfg (absent, it takes every queue as defined)."""
    return any(
        str(e.get("event", "")).endswith("-TD") and e.get("resp") == "QIDERR"
        for log in case.expected.values()
        for t in log["tasks"]
        for e in t["events"]
    )


def run_scenario(case: cc.Case, sc: dict[str, Any], box: "Container", work: Path) -> dict[str, Any]:
    """One scenario on the stub, scheduled as SPEC section 4 says (drive_scenario)."""
    ts = f"runs/{sc['id']}/ts"  # #4002: the region's TS queues, shared by every task of the scenario
    seed_ts(work / ts, (sc.get("initial") or {}).get("ts_queues") or {})
    seed_td(work / ts, (sc.get("initial") or {}).get("td_queues") or {})  # #5079
    count = iter(range(1000))
    origin = origin_peers(case, sc)
    files_cfg = seed_files(case, work, sc["id"])  # #4443
    carried: list[Path | None] = [
        None
    ]  # #5005 (X17): the channel the terminal's last RETURN CHANNEL left for its next task

    def run_one(frame: dict[str, Any], transid: str, commarea: bytes | None, step: dict[str, Any] | None,
                data: list[Any], requests: list[tuple[str, int]]) -> dict[str, Any]:  # fmt: skip
        rel = f"runs/{sc['id']}/{next(count):02d}"
        if origin is not None:  # #4767 (X35): each task process is told the origin servers (not a log key)
            frame = {**frame, "http_peers": origin}
        terminal = frame.get("termid") == case.data["terminal"]
        channel = carried[0] if (frame.get("trigger") or {}).get("kind") == "terminal" else None
        task = run_task(case, box, work, rel, ts, transid, frame, commarea, step, data, requests,
                        task_faults(sc, transid), files_cfg, channel)  # fmt: skip
        if terminal:  # as drive_scenario's pending RETURN: only a normal end passes it on
            saved = work / rel / "out" / "return_channel.cfg"
            carried[0] = saved if task["end"] == "normal" and saved.is_file() else None
        return task

    tasks, stopped = drive_scenario(case, sc, run_one)
    return {"tasks": tasks, "stopped": stopped, "final": {"ts_queues": read_ts(work / ts), "td_queues": read_td(work / ts)},
            **http_peer_log(case, sc, tasks)}  # fmt: skip


def run_task(case: cc.Case, box: "Container", work: Path, rel: str, ts: str, transid: str, frame: dict[str, Any],
             commarea: bytes | None, step: dict[str, Any] | None, data: list[Any] | None = None,
             requests: list[tuple[str, int]] | None = None,
             faults: list[str] | None = None, files_cfg: str = "",
             channel: Path | None = None) -> dict[str, Any]:  # fmt: skip
    """One task in one process: its inputs in `rel` (the COMMAREA, the terminal's input -- a step's text or
    map fields -- the EIB, the CSD's programs and transactions, #4006: the START data it RETRIEVEs and the
    unexpired requests a CANCEL searches, the virtual clock), then the stub's events as the task's."""
    program = case.csd["transactions"].get(transid)
    startcode = frame.get("startcode")  # #4270 slice 3: ASSIGN STARTCODE (the scheduler's; not a log key)
    http_req = frame.get("http_request")  # #4767 (X37): the request an `http` task serves (not a log key)
    http_peers = frame.get("http_peers")  # #4767 (X35): the origin servers the task can reach (not a log key)
    frame = {k: v for k, v in frame.items() if k not in ("startcode", "http_request", "http_peers")}
    task: dict[str, Any] = {"transid": transid, "program": program, **frame, "eibcalen": len(commarea or b""),
                            "commarea": cc.RawArea(commarea, "latin-1") if commarea else None,
                            "events": [], "end": "normal"}  # fmt: skip
    if program is None:
        task["events"].append({"event": "DRIVER-ERROR", "program": None,
                               "message": f"transaction {transid} has no program in the CSD"})  # fmt: skip
        task["end"] = "abend"
        return task
    d = work / rel
    (d / "out").mkdir(parents=True, exist_ok=True)
    (d / "files.cfg").write_text(files_cfg, encoding="ascii")
    (d / "programs.cfg").write_text("".join(f"{p}\n" for p in sorted(case.csd["programs"])), encoding="ascii")
    (d / "transactions.cfg").write_text("".join(f"{t}\n" for t in sorted(case.csd["transactions"])), encoding="ascii")
    (d / "terminals.cfg").write_text(f"{case.data['terminal']}\n", encoding="ascii")
    if case.csd.get("tdqueues") or _expects_undefined_td_queue(
        case
    ):  # #5079 (X57): the CSD's TDQUEUEs; one it lacks is QIDERR
        (d / "tdqueues.cfg").write_text("".join(f"{q} {w}\n" for q, w in sorted((case.csd.get("tdqueues") or {}).items())),
                                        encoding="ascii")  # fmt: skip
    # #4270 zECS (X32): the URIMAP definitions the case CSD installs, `NAME TRANSACTION PATH` ('-': no transaction)
    (d / "urimaps.cfg").write_text("".join(f"{n} {t or '-'} {p}\n" for n, t, p in case.csd.get("urimaps") or []),
                                   encoding="ascii")  # fmt: skip
    if (
        case.data.get("doctemplates") is not None
    ):  # #4769 zECS (X33): `NAME TEXT-IN-HEX` ('-': empty), the text in latin-1
        (d / "doctemplates.cfg").write_text("".join(f"{n} {t.encode('latin-1').hex().upper() or '-'}\n"
                                                    for n, t in case.data["doctemplates"].items()), encoding="ascii")  # fmt: skip
    (d / "requests.cfg").write_text("".join(f"{r} {e}\n" for r, e in requests or []), encoding="ascii")
    for i, item in enumerate(data or [], 1):  # #4270: a record's FROM data, and its other data options beside it
        rec = item if isinstance(item, dict) else {"data": item}
        if rec.get("data") is not None:
            (d / f"retrieve_{i:03d}.bin").write_bytes(rec["data"])
        named = {k: rec[k] for k in ("rtransid", "rtermid", "queue") if rec.get(k) is not None}
        if named or rec.get("data") is None:
            (d / f"retrieve_{i:03d}.opt").write_text(
                f"from={int(rec.get('data') is not None)}"
                + "".join(f" {k}={v.encode('latin-1').hex()}" for k, v in named.items())
                + "\n",
                encoding="ascii",
            )
    if commarea:
        (d / "commarea.in").write_bytes(commarea)
    if channel is not None:  # #5005 (X17): the channel the previous task RETURNed, its current channel (GGCCHIN)
        shutil.copy(channel, d / "channel.cfg")
    if http_req is not None:
        import equivalence_cics as ec

        (d / "webreq.cfg").write_text(ec.http_request_cfg(http_req, RUNTIME_PAGE), encoding="ascii")
    if http_peers:
        import equivalence_cics as ec

        (d / "http.cfg").write_text(ec.http_peers_cfg(http_peers, RUNTIME_PAGE), encoding="ascii")
    step = step or {}
    if faults:  # #4049: the conditions the scenario plans for this task's TRANSID
        (d / "faults.cfg").write_text("".join(x + "\n" for x in faults), encoding="ascii")
    if step.get("text") is not None:  # SPEC 5: typed on a cleared screen, read from position 0
        (d / "terminal.in").write_bytes(step["text"].encode("latin-1"))
    screens = case_screens(case)
    if step.get("map") and step.get("fields"):
        m = step["map"]
        (d / f"receive_{m}.bin").write_bytes(screens[m].receive_input(step["fields"]))  # #4001: as BMS delivers it
    when = datetime.datetime.fromisoformat(frame["at"])
    eib_date, eib_time = _eib_datetime(when)
    aid = "DFH" + frame["eibaid"] if frame.get("eibaid") else ""
    (d / "eib.in").write_text(f"{transid:<4} {aid:<8} {eib_date} {eib_time} {program:<8} {frame.get('termid') or '':<4}\n",
                              encoding="ascii")  # fmt: skip
    box.sh(f"cd /work && {cov.trace_env(f'/work/{rel}/{cov.TRACE_NAME}')}"
           f"GGCICS_DIR=/work/{rel} GGCICS_OUT=/work/{rel}/out EIBIN=/work/{rel}/eib.in "
           f"{'GGCICS_LU2=1 ' if terminal_device(case) == 'LUTYPE2' else ''}"  # #4413: EOC on RECEIVE
           f"GGCICS_URIMAPS=/work/{rel}/urimaps.cfg "  # #4270 zECS (X32)
           f"{f'GGCICS_WEBREQ=/work/{rel}/webreq.cfg ' if http_req is not None else ''}"  # #4767 (X37)
           f"{f'GGCICS_HTTP=/work/{rel}/http.cfg ' if http_peers else ''}"  # #4767 (X35)
           f"{f'GGCICS_DOCTEMPLATES=/work/{rel}/doctemplates.cfg ' if case.data.get('doctemplates') is not None else ''}"  # #4769 (X33)
           f"{f'GGCICS_UCTRANST={terminal_uctranst(case)} ' if terminal_uctranst(case) else ''}"  # #4415
           f"{f'GGCICS_ORIGIN={origin_env(case)} ' if origin_env(case) and (frame.get('trigger') or {}).get('kind') == 'terminal' else ''}"  # #4415 slice 2
           f"GGCICS_MAPSETS='{mapsets_env(case)}' "  # #4270 (X31): ABM0 for a map its mapset does not hold
           f"{'GGCICS_RUNCHILD=1 ' if (frame.get('trigger') or {}).get('kind') == 'run' else ''}"  # #4270
           f"{f'GGCICS_STARTCODE={startcode} ' if startcode else ''}GGCICS_USERID={REGION_USERID} "  # #4270 slice 3
           f"GGCICS_FACILITY={frame.get('termid') or ''} GGCICS_SCREEN='{REGION_SCREEN[0]} {REGION_SCREEN[1]}' "
           f"{area_env(case, transid, ts)}"  # #5079 slice 2b (X59): TWASIZE / USERAREALEN
           f"GGCICS_TS=/work/{ts} GGCICS_NOW={frame['at']} COB_CURRENT_DATE='{when.strftime('%Y/%m/%d %H:%M:%S')}.00' ./bin/task "
           f"> /work/{rel}/stdout.txt 2>&1")  # fmt: skip
    task["events"] = _cobol_events(d / "out", program, screens)
    http_order([task])
    if any((e["event"] == "ABEND" and e.get("outcome") == "terminated") or e["event"] == "DRIVER-ERROR"
           for e in task["events"]):  # fmt: skip
        task["end"] = "abend"
    return task


# ---- #4023: COBOL coverage -------------------------------------------------------------------------------
def case_inventories(case: cc.Case) -> dict[str, "cov.Inventory"]:
    """{program: its paragraphs, dead paragraphs, branch points} for each COBOL source, read as the crucible has it."""
    return {Path(rel).stem.upper(): _inventory(case.dir / rel, case.dir, f"cases/{case.trap}/{case.id}/{rel}")
            for rel in case.data["sources"]["cobol"]}  # fmt: skip


@functools.lru_cache(maxsize=None)
def _inventory(path: Path, root: Path, label: str) -> "cov.Inventory":
    return cov.inventory(path, root, "utf-8", label=label)


def _line_map(case: cc.Case, prog: str, compiled: str) -> "cov.LineMap":
    rel = next(r for r in case.data["sources"]["cobol"] if Path(r).stem.upper() == prog)
    return cov.LineMap((case.dir / rel).read_text(encoding="utf-8"), compiled)


def scenario_hits(case: cc.Case, programs: dict[str, tuple[str, bool]], scenarios: list[str],
                  work: Path) -> dict[str, dict[str, "cov.Hits"]]:  # fmt: skip
    """{scenario: {program: the paragraphs it entered and the branch outcomes it took}}, from the traces of the
    scenario's tasks (runs/<scenario>/NN/trace.txt), each line mapped back to the crucible's source."""
    invs = case_inventories(case)
    maps = {p: _line_map(case, p, text) for p, (text, _ca) in programs.items() if p in invs}
    out: dict[str, dict[str, cov.Hits]] = {}
    for sid in scenarios:
        traces = sorted((work / "runs" / sid).glob(f"*/{cov.TRACE_NAME}"))
        events = [e for t in traces for e in cov.read_trace(t.read_bytes(), "latin-1")]
        out[sid] = {p: cov.hits(invs[p], events, m, f"{p}.cbl") for p, m in maps.items()}
    return out


def case_coverage(case: cc.Case, programs: dict[str, tuple[str, bool]], got: dict[str, dict[str, "cov.Hits"]],
                  cells: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:  # fmt: skip
    """Per program: what each scenario that runs it executed (only a scenario whose cobol-stub cell passes: the
    path the expected log confirms), the summary over them all, and -- when the case has ported scenarios -- its
    port's claim: the scenarios its java-ported cell passes on, and how much of the program those run."""
    invs = case_inventories(case)

    def status(sid: str, side: str) -> str | None:
        return cells.get(cc.cell_id(case.id, sid, side), {}).get("status")

    out: dict[str, dict[str, Any]] = {}
    for prog in sorted(p for p in programs if p in invs):
        inv, blind = invs[prog], cov.untraceable(invs[prog], _line_map(case, prog, programs[prog][0]))
        runs = [sc["id"] for sc in case.scenarios if sc["id"] in got and status(sc["id"], "cobol-stub") == "pass"
                and (prog in scenario_programs(case.expected[sc["id"]]) or got[sc["id"]][prog].units)]  # fmt: skip
        merged = cov.Hits()
        for sid in runs:
            merged = merged.merge(got[sid][prog])
        # the ledger keeps what the summary counts: live units, outcomes of live traceable branch points
        rec: dict[str, Any] = {"scenarios": {sid: cov.counted(inv, got[sid][prog], blind).as_dict() for sid in runs},
                               "summary": cov.summary(inv, merged, blind)}  # fmt: skip
        if any(status(sid, "java-ported") for sid in runs):
            proven = [sid for sid in runs if status(sid, "java-ported") == "pass"]
            port = cov.Hits()
            for sid in proven:
                port = port.merge(got[sid][prog])
            rec["port"] = {"scenarios": proven, "claim": cov.claim(cov.summary(inv, port, blind), len(proven))}
        out[prog] = rec
    return out


# ---- one case -> its cells -------------------------------------------------------------------------
@dataclasses.dataclass
class PortOptions:
    """The java-ported side's ports: `ports` a directory of <KEY>/overlay trees (default: the case's committed
    ones, `root`/<case>), `overlays` more trees laid last, `program` only the scenarios running it (a proof
    of one program's port), and `actual` collects each measured cell's actual log (the proof's feedback)."""

    ports: Path | None = None
    forge_cache: Path | None = None  # #4047: forge()'s `cache`
    root: Path = PORTS_DIR  # <case>/<KEY>/overlay: where each case's committed ports are, unless `ports` is given
    det_root: Path | None = DET_PORTS_DIR  # the det-port-only fallback (None: off); never read when `ports` is given
    overlays: list[Path] = dataclasses.field(default_factory=list)
    program: str | None = None
    actual: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    entries: dict[str, list[dict[str, Any]]] = dataclasses.field(default_factory=dict)  # #4343: java-facade's


def det_port_overlays(case_id: str, dest: Path, root: Path = DET_PORTS_DIR) -> dict[str, Path]:
    """#4767: the overlays of a case's committed deterministic port (tests/cics_crucible/det-ports/<case>), each with
    the runtime it compiles with. The models' ports win: a case with one never reaches this."""
    import cics_crucible_det as det

    return case_overlays(det.ports_dir(case_id, dest, root))


def measure_ported(case: cc.Case, work: Path, offline: bool, opts: PortOptions,
                   put: Any, sides: tuple[str, ...] = ("java-ported",)) -> None:  # fmt: skip
    """The java-ported side: the generated project with the case's ports laid over it, scenario by scenario; and
    the java-facade side (#4343): the same project, each task entered through its program's facade."""
    ported = case_overlays(opts.ports if opts.ports is not None else opts.root / case.id)
    if not ported and opts.ports is None and opts.det_root is not None and (opts.det_root / case.id).is_dir():
        ported = det_port_overlays(case.id, work / "det-ports", opts.det_root)
    trees = [*ported.values(), *opts.overlays]
    scenarios = [sc for sc in case.scenarios
                 if opts.program is None or opts.program in scenario_programs(case.expected[sc["id"]])]  # fmt: skip
    needs = {sc["id"]: cc.blockers(case.expected[sc["id"]], JAVA_CAPS, sc) for sc in scenarios}
    if not scenarios:
        return
    if not trees:
        for side in sides:
            for sc in scenarios:
                put(sc["id"], side, cc.Verdict("fail", "no port of any of its programs", needs[sc["id"]], "not ported"))
        return
    verdict, project = forge(case, work / "forge-ported", offline, trees, opts.forge_cache)
    if verdict.status != "pass" or project is None:
        for side in sides:
            for sc in scenarios:
                put(sc["id"], side, cc.Verdict("fail", f"the ported project: {verdict.reason}", needs[sc["id"]],
                                               "ported project does not compile", verdict.detail))  # fmt: skip
        return
    for side in sides:
        facades = side == "java-facade"
        got: dict[str, list[dict[str, Any]]] = {}
        byte_runs: dict[str, dict[str, Any]] = {}
        try:
            actual = run_java(case, project, work / side, offline, facades, got, byte_runs)
        except RuntimeError as e:
            detail = getattr(e, "detail", "")
            for sc in scenarios:
                put(sc["id"], side, cc.Verdict("fail", str(e), needs[sc["id"]], "the Java run failed", detail))
            continue
        for sc in scenarios:
            v = cc.compare(case.expected[sc["id"]], actual[sc["id"]], JAVA_CAPS, case_context(case), sc)
            if v.status == "pass" and sc["id"] in byte_runs:  # #4965: and through the byte overload, the same
                vb = cc.compare(case.expected[sc["id"]], byte_runs[sc["id"]], JAVA_CAPS, case_context(case), sc)
                if vb.status != "pass":
                    vb.reason = f"through handleTransaction(.., byte[]): {vb.reason}"
                    v = vb
            cid = cc.cell_id(case.id, sc["id"], side)
            opts.actual[cid] = actual[sc["id"]]
            if facades:
                opts.entries[cid] = got.get(sc["id"], [])
            put(sc["id"], side, v)


def measure_case(case: cc.Case, sides: set[str], work: Path, offline: bool,
                 ports: PortOptions | None = None,
                 coverage: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:  # fmt: skip
    """Every cell of one case: {cell id: {case, trap, scenario, side, status, reason, features, kind}}. #4023:
    `coverage` gets the case's COBOL coverage (case_coverage) when the cobol-stub side runs."""
    cells: dict[str, dict[str, Any]] = {}

    def put(scenario: str, side: str, v: cc.Verdict) -> None:
        cells[cc.cell_id(case.id, scenario, side)] = {"case": case.id, "trap": case.trap, "scenario": scenario,
                                                      "side": side, **v.as_dict()}  # fmt: skip

    work.mkdir(parents=True, exist_ok=True)
    disabled = sorted(case.csd.get("disabled") or ())
    if (
        disabled
    ):  # #4768 (X34): every program the region defines is ENABLED (INQUIRE PROGRAM STATUS); DISABLED not modelled
        why = [f"csd: program {p} defined STATUS(DISABLED) (not modelled, X34)" for p in disabled]
        for side in sorted(sides - {"engine-facts", "forge-compile"}):
            for sc in case.scenarios:
                put(sc["id"], side, cc.not_run(why, []))
        return cells
    async_why = case_async_refusals(case)
    if async_why:  # #4950 (X18): the SPEC section 4 schedule is the only one the runner has; named, never compared
        for side in sorted(sides - {"engine-facts", "forge-compile"}):
            for sc in case.scenarios:
                put(sc["id"], side, cc.not_run(async_why, []))
        sides = sides & {"engine-facts", "forge-compile"}
    ctx = case_context(case)
    if "engine-facts" in sides:
        put("*", "engine-facts", engine_facts(case, work / "facts"))
    project = None
    if sides & {"forge-compile", "java"}:
        verdict, project = forge(case, work / "forge", offline)
        if "forge-compile" in sides:
            put("*", "forge-compile", verdict)
        if verdict.status != "pass":
            project = None
    if "java" in sides:
        needs = {sc["id"]: cc.blockers(case.expected[sc["id"]], JAVA_CAPS, sc) for sc in case.scenarios}
        runnable = [sc["id"] for sc in case.scenarios]
        if runnable and project is None:
            for sid in runnable:
                put(sid, "java", cc.Verdict("fail", "the generated project does not compile", needs[sid],
                                            "generated project does not compile"))  # fmt: skip
        elif runnable:
            try:
                actual = run_java(case, project, work / "java", offline)
            except RuntimeError as e:
                actual = None
                for sid in runnable:
                    put(sid, "java", cc.Verdict("fail", str(e), needs[sid], "the Java run failed"))
            for sid in runnable if actual else []:
                sc = next(s for s in case.scenarios if s["id"] == sid)
                put(
                    sid,
                    "java",
                    _kind_java(cc.compare(case.expected[sid], actual[sid], JAVA_CAPS, ctx, sc), actual[sid]),
                )
    ported_sides = tuple(sd for sd in ("java-ported", "java-facade") if sd in sides)
    if ported_sides:
        measure_ported(case, work, offline, ports or PortOptions(), put, ported_sides)
    if "cobol-stub" in sides:
        translated = translate_programs(case)
        runnable, programs = [], {p: t for p, t in translated.items() if not isinstance(t, Exception)}
        for sc in case.scenarios:
            exp = case.expected[sc["id"]]
            needs = cc.blockers(exp, COBOL_CAPS, sc)
            refused = [f"translator: {f}" for p in scenario_programs(exp) if isinstance(translated.get(p), Exception)
                       for f in translated[p].features]  # fmt: skip
            refused = list(dict.fromkeys(refused))
            if refused:
                put(sc["id"], "cobol-stub", cc.not_run(refused, needs))
            else:
                runnable.append(sc["id"])
        got: dict[str, dict[str, cov.Hits]] = {}
        if runnable:
            try:
                actual = run_cobol(case, programs, runnable, ctx, work / "cobol", got)
            except RuntimeError as e:
                actual = None
                for sid in runnable:
                    put(sid, "cobol-stub", cc.Verdict("fail", str(e), cc.blockers(case.expected[sid], COBOL_CAPS),
                                                      "the COBOL run failed"))  # fmt: skip
            for sid in runnable if actual else []:
                sc = next(s for s in case.scenarios if s["id"] == sid)
                put(sid, "cobol-stub", cc.compare(case.expected[sid], actual[sid], COBOL_CAPS, ctx, sc))
        if coverage is not None and got:
            coverage[case.id] = case_coverage(case, programs, got, cells)
    return cells


def _kind_java(v: cc.Verdict, actual: dict[str, Any]) -> cc.Verdict:
    """Name the commonest Java failure for what it is: the generated runTask is a stub that records nothing."""
    if v.status == "fail" and not any(t["events"] for t in actual.get("tasks", [])):
        v.kind = "runTask records no events (the generated stub: PROCEDURE DIVISION not ported)"
    return v


def _measure_dir(d: Path, sides: set[str], work: Path, offline: bool, ports: PortOptions | None,
                 strengthened: bool) -> tuple[dict[str, Any], dict[str, Any], PortOptions | None]:  # fmt: skip
    """One case of `measure`: its cells, its coverage entry, and `ports` with what it collected (#5882: a --jobs
    worker's answer, so the parent merges exactly what a sequential run would have gathered)."""
    case = cc.load_case(d)
    if strengthened:  # #4049
        add_strengthened(case)
    coverage: dict[str, Any] = {}
    return measure_case(case, sides, work / case.id, offline, ports, coverage), coverage, ports


def measure(crucible: Path, only: set[str] | None, sides: set[str], work: Path, offline: bool,
            ports: PortOptions | None = None, strengthened: bool = False, jobs: int = 1) -> dict[str, Any]:  # fmt: skip
    """#5882: `jobs` > 1 measures that many cases at once, each in its own process (quiet() redirects a whole
    process's output); the results and the printed per-case lines are the sequential run's, in case order."""
    cells: dict[str, dict[str, Any]] = {}
    coverage: dict[str, Any] = {}
    dirs = cc.discover(crucible, only)
    if not dirs:
        raise SystemExit(f"no cases under {crucible}/cases" + (f" matching {sorted(only)}" if only else ""))
    pool = None
    if jobs > 1 and len(dirs) > 1:
        import concurrent.futures
        import multiprocessing

        pool = concurrent.futures.ProcessPoolExecutor(
            min(jobs, len(dirs)), mp_context=multiprocessing.get_context("spawn")
        )
        pending = [pool.submit(_measure_dir, d, sides, work, offline, ports, strengthened) for d in dirs]
    for i, d in enumerate(dirs):
        print(f"{d.name} ...", flush=True)
        if pool is None:
            got, cov_part, _ = _measure_dir(d, sides, work, offline, ports, strengthened)
        else:
            got, cov_part, theirs = pending[i].result()
            if ports is not None and theirs is not None:
                ports.actual.update(theirs.actual)
                ports.entries.update(theirs.entries)
        cells.update(got)
        coverage.update(cov_part)
        by = Counter(f"{c['side']}:{c['status']}" for c in got.values())
        print("   " + ", ".join(f"{k} {n}" for k, n in sorted(by.items())), flush=True)
    if pool is not None:
        pool.shutdown()
    oracle = None
    if "cobol-stub" in sides:  # #4309: the GnuCOBOL the COBOL side ran on, checked against the pin
        import equivalence_oracle  # noqa: PLC0415 -- beside equivalence_common, imported as it is

        oracle = equivalence_oracle.checked()
    return {"crucible_ref": crucible_ref(crucible), "oracle": oracle, "cells": dict(sorted(cells.items())),
            "coverage": dict(sorted(coverage.items()))}  # fmt: skip


# ---- shards (#5498) -----------------------------------------------------------------------------------
# CASE_SECONDS (seconds per case on a hosted runner; run 39142662150, 2026-10-18: 1215 s over 43 cases) lives in
# crucible_shard_plan.py, which also sizes the shard count and timeout (#5919). Only the balance depends on it.


def parse_shard(text: str) -> tuple[int, int]:
    """'i/N' -> (i, N), 1-based."""
    try:
        i, n = (int(x) for x in text.split("/"))
    except ValueError:
        raise SystemExit(f"--shard {text!r}: expected i/N, e.g. 2/4") from None
    if not 1 <= i <= n:
        raise SystemExit(f"--shard {text!r}: need 1 <= i <= N")
    return i, n


def shard_plan(case_ids: list[str], n: int) -> list[list[str]]:
    """Partition the case ids into n shards, deterministically and balanced by CASE_SECONDS (heaviest first into the
    lightest shard). Every id lands in exactly one shard; the plan depends only on the ids and the weights."""
    bins: list[tuple[int, list[str]]] = [(0, []) for _ in range(n)]
    for cid in sorted(case_ids, key=lambda c: (-CASE_SECONDS.get(c, DEFAULT_CASE_SECONDS), c)):
        k = min(range(n), key=lambda j: (bins[j][0], len(bins[j][1]), j))
        bins[k] = (bins[k][0] + CASE_SECONDS.get(cid, DEFAULT_CASE_SECONDS), bins[k][1] + [cid])
    return [sorted(b[1]) for b in bins]


def restrict(baseline: dict[str, Any], coverage: dict[str, Any], cases: set[str]) -> tuple[dict, dict]:
    """The two ledgers cut to one shard's cases (cell ids are case/scenario/side, coverage keys case/program)."""
    base = {**baseline, "cells": {k: v for k, v in baseline.get("cells", {}).items() if k.split("/")[0] in cases}}
    cov = {**coverage, "programs": {k: v for k, v in coverage.get("programs", {}).items() if k.split("/")[0] in cases}}
    return base, cov


def merge_shards(parts: list[dict[str, Any]], all_cases: list[str]) -> tuple[dict[str, Any], list[str]]:
    """(results, errors): the shards' results.json merged into one run. Errors: a shard missing or repeated, shards cut
    for different N, a case in two shards, a case in none, a case a shard claims but did not measure."""
    errors: list[str] = []
    totals = {p["shard"]["total"] for p in parts if "shard" in p}
    if len(totals) != 1 or any("shard" not in p for p in parts):
        return {}, [f"SHARDS: results are not all from one sharded run (totals {sorted(totals)})"]
    total = totals.pop()
    seen = sorted(p["shard"]["index"] for p in parts)
    if seen != list(range(1, total + 1)):
        errors.append(f"SHARDS: have shards {seen}, need 1..{total}")
    owner: dict[str, int] = {}
    cells: dict[str, Any] = {}
    coverage: dict[str, Any] = {}
    for p in parts:
        i = p["shard"]["index"]
        measured = {cid.split("/")[0] for cid in p["cells"]}
        for case in p["shard"]["cases"]:
            if case in owner:
                errors.append(f"SHARDS: case {case} is in shard {owner[case]} and shard {i}")
            owner[case] = i
            if case not in measured:
                errors.append(f"SHARDS: case {case} is in shard {i} but has no cells in its results")
        for case in sorted(measured - set(p["shard"]["cases"])):
            errors.append(f"SHARDS: shard {i} measured {case}, which is not in its plan")
        cells.update(p["cells"])
        coverage.update(p.get("coverage", {}))
    for case in sorted(set(all_cases) - set(owner)):
        errors.append(f"SHARDS: case {case} is in no shard")
    for case in sorted(set(owner) - set(all_cases)):
        errors.append(f"SHARDS: shard plan names {case}, which is not under the crucible")
    first = parts[0]
    merged = {"crucible_ref": first.get("crucible_ref"), "oracle": first.get("oracle"),
              "cells": dict(sorted(cells.items())), "coverage": dict(sorted(coverage.items()))}  # fmt: skip
    return merged, errors


# ---- the ratchet ------------------------------------------------------------------------------------
def read_baseline(path: Path = BASELINE) -> dict[str, Any]:
    if not path.is_file():
        return {"format": BASELINE_FORMAT, "crucible_ref": None, "cells": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != BASELINE_FORMAT:
        raise SystemExit(f"{path}: format {data.get('format')!r}, expected {BASELINE_FORMAT!r}")
    return data


def baseline_of(results: dict[str, Any]) -> dict[str, Any]:
    """The ledger for these results: every cell that does not pass, with its status and reason."""
    cells = {cid: {"status": c["status"], "reason": " ".join(c["reason"].split())[:300]}
             for cid, c in results["cells"].items() if c["status"] != "pass"}  # fmt: skip
    return {"format": BASELINE_FORMAT, "crucible_ref": results.get("crucible_ref"),
            "note": "#3989: the CICS crucible cells that do not pass yet -- a ratchet (tests/tools/cics_crucible.py). "
                    "CI fails on a cell not listed here, and on a listed cell that now passes: regenerate with "
                    "--update-baseline, which only ever shrinks this as phase 3 lands.",
            "cells": dict(sorted(cells.items()))}  # fmt: skip


def write_baseline(results: dict[str, Any], path: Path = BASELINE) -> None:
    """One cell per line, sorted: two phase-3 PRs that each remove cells touch different lines."""
    base = baseline_of(results)
    head = {k: v for k, v in base.items() if k != "cells"}
    lines = (
        ["{"] + [f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}," for k, v in head.items()] + [' "cells": {']
    )
    rows = [f"  {json.dumps(cid)}: {json.dumps(c, ensure_ascii=False)}" for cid, c in base["cells"].items()]
    lines += [",\n".join(rows), " }", "}"] if rows else [" }", "}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ratchet(results: dict[str, Any], baseline: dict[str, Any], complete: bool) -> tuple[list[str], list[str]]:
    """(errors, notes). Errors: a failing cell the ledger does not list (a regression, or a new cell);
    a ledgered cell that now passes (lower the ledger); on a complete run, a ledgered cell that was not
    measured at all (the crucible moved: re-baseline). Notes: a ledgered cell whose status or reason moved."""
    errors: list[str] = []
    notes: list[str] = []
    known = baseline.get("cells", {})
    for cid, c in results["cells"].items():
        if c["status"] == "pass":
            if cid in known:
                errors.append(f"NOW PASSES, still ledgered: {cid} -- remove it (--update-baseline)")
            continue
        if cid not in known:
            errors.append(f"NEW {c['status'].upper()}: {cid}: {c['reason']}")
        elif known[cid]["status"] != c["status"]:
            notes.append(f"{cid}: was {known[cid]['status']}, now {c['status']}: {c['reason']}")
    if complete:
        for cid in sorted(set(known) - set(results["cells"])):
            errors.append(f"STALE: {cid} is ledgered but was not measured -- re-baseline (--update-baseline)")
    return errors, notes


def coverage_of(results: dict[str, Any]) -> dict[str, Any]:
    """#4023: the coverage ledger for these results -- per case/program its live paragraphs and branch outcomes,
    and per passing scenario the ones it executed. Sets, not counts: a change that loses one path and gains
    another is caught."""
    progs = {f"{case}/{prog}": {"live": r["summary"]["paragraphs"]["live"],
                                "outcomes": r["summary"]["branches"]["total"], "scenarios": r["scenarios"]}
             for case, per in results.get("coverage", {}).items() for prog, r in per.items()}  # fmt: skip
    return {"format": COVERAGE_FORMAT, "crucible_ref": results.get("crucible_ref"),
            "note": "#4023: the COBOL each passing cobol-stub scenario executes (live paragraphs and sections entered; "
                    "branch outcomes as LINE:OUTCOME of the crucible's source) -- a ratchet (tests/tools/cics_crucible.py "
                    "--ci). Regenerate with --update-baseline.",
            "programs": dict(sorted(progs.items()))}  # fmt: skip


def read_coverage(path: Path = COVERAGE) -> dict[str, Any]:
    if not path.is_file():
        return {"format": COVERAGE_FORMAT, "programs": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != COVERAGE_FORMAT:
        raise SystemExit(f"{path}: format {data.get('format')!r}, expected {COVERAGE_FORMAT!r}")
    return data


def write_coverage(results: dict[str, Any], path: Path = COVERAGE) -> None:
    path.write_text(json.dumps(coverage_of(results), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def coverage_ratchet(results: dict[str, Any], ledger: dict[str, Any], complete: bool) -> list[str]:
    """#4023: errors -- a scenario that no longer executes a paragraph or branch outcome it did (a crucible or
    harness change shrank what a proof proves), one that executes more (ratchet it in), a program whose live
    code moved, a program not in the ledger; on a complete run, a ledgered program not measured."""
    errors: list[str] = []
    known = ledger.get("programs", {})
    now = coverage_of(results)["programs"]
    for key, rec in now.items():
        old = known.get(key)
        if old is None:
            errors.append(f"COVERAGE NEW: {key} is not in the coverage ledger -- record it (--update-baseline)")
            continue
        if (old["live"], old["outcomes"]) != (rec["live"], rec["outcomes"]):
            errors.append(f"COVERAGE INVENTORY MOVED: {key}: {old['live']} live paragraphs / {old['outcomes']} branch "
                          f"outcomes, now {rec['live']} / {rec['outcomes']} -- re-baseline (--update-baseline)")  # fmt: skip
        for sid in sorted(set(old["scenarios"]) | set(rec["scenarios"])):
            a, b = old["scenarios"].get(sid, {}), rec["scenarios"].get(sid, {})
            for kind in ("units", "outcomes"):
                lost = sorted(set(a.get(kind, [])) - set(b.get(kind, [])))
                gained = sorted(set(b.get(kind, [])) - set(a.get(kind, [])))
                if lost:
                    errors.append(f"COVERAGE LOST: {key} scenario {sid}: {kind} {', '.join(lost)}")
                if gained:
                    errors.append(f"COVERAGE GAINED: {key} scenario {sid}: {kind} {', '.join(gained)} -- ratchet it "
                                  "in (--update-baseline)")  # fmt: skip
    if complete:
        for key in sorted(set(known) - set(now)):
            errors.append(f"COVERAGE STALE: {key} is in the coverage ledger but was not measured -- re-baseline")
    return errors


def ledger_claim(case: str, program: str, scenarios: list[str], ledger: dict[str, Any] | None = None) -> str | None:
    """#4023: a port's claim from the committed coverage ledger -- the scenarios it proved on, and how much of the
    program those execute (None: the program is not in the ledger)."""
    rec = (ledger if ledger is not None else read_coverage()).get("programs", {}).get(f"{case}/{program}")
    if rec is None:
        return None
    got = cov.Hits()
    for sid in scenarios:
        if sid in rec["scenarios"]:
            got = got.merge(cov.Hits.from_dict(rec["scenarios"][sid]))
    return (f"proven on {len(scenarios)} scenario{'' if len(scenarios) == 1 else 's'}, covering "
            f"{len(got.units)}/{rec['live']} paragraphs and {len(got.outcomes)}/{rec['outcomes']} branches")  # fmt: skip


# ---- the report ---------------------------------------------------------------------------------------
# #3989 phase 3: each missing feature belongs to one piece of harness work; a cell is unlocked (it gets a
# pass / fail verdict instead of `unsupported`) when every group its features fall in is done.
FEATURE_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("RECEIVE MAP recorded as an event", ("RECEIVE-MAP",)),
    ("terminal RECEIVE (unformatted input)", ("RECEIVE event", "RECEIVE")),
    ("TS queues: READQ / WRITEQ TS, seeding, final state", ("READQ", "WRITEQ", "TS queue")),
    ("condition machinery: HANDLE / IGNORE CONDITION, PUSH / POP HANDLE, abend exits, ASSIGN ABCODE",
     ("HANDLE CONDITION", "IGNORE CONDITION", "PUSH HANDLE", "POP HANDLE", "ASSIGN", "ABEND ")),
    ("HANDLE AID", ("HANDLE AID",)),
    ("LINK: levels, by-reference COMMAREA, PGMIDERR", ("LINK", "RETURN caller_commarea")),
    ("interval control: START / RETRIEVE / CANCEL and started tasks", ("START", "RETRIEVE", "CANCEL")),
    ("BMS output fidelity: attributes, cursor, data origin, DATAONLY, extended attributes", ("SEND-MAP",)),
    ("SEND TEXT length and options", ("SEND-TEXT",)),
    ("XCTL LENGTH / RESP / RESP2", ("XCTL",)),
]  # fmt: skip


def feature_group(feature: str) -> str:
    """The piece of harness work a feature (`translator: READQ TS`, `stub: WRITEQ-TS event`) belongs to."""
    what = feature.split(": ", 1)[-1]
    for name, prefixes in FEATURE_GROUPS:
        if any(what == p or what.startswith(p if p.endswith(" ") else p + " ") or what.startswith(p + "-")
               for p in prefixes):  # fmt: skip
            return name
    return what


def unlock_order(cells: list[dict[str, Any]]) -> list[tuple[str, int, int, int]]:
    """[(group, cells needing it, cells it alone unlocks, cells unlocked by it and every group above)],
    greedily ordered: each row is the group that unlocks the most unsupported cells given the rows above
    (ties: the one more unsupported cells need, then by name)."""
    blocked = [{feature_group(f) for f in c["features"]} for c in cells if c["status"] == "unsupported"]
    needing = Counter(g for c in cells if c["status"] != "pass" for g in {feature_group(f) for f in c["features"]})
    stuck = Counter(g for gs in blocked for g in gs)
    alone = Counter(next(iter(gs)) for gs in blocked if len(gs) == 1)
    done: set[str] = set()
    rows, total = [], 0

    def gain(g: str) -> int:
        return sum(1 for gs in blocked if gs <= done | {g} and not gs <= done)

    while len(done) < len(needing):
        best = max(sorted(set(needing) - done), key=lambda g: (gain(g), stuck[g]))
        step = gain(best)
        done.add(best)
        total += step
        rows.append((best, needing[best], alone.get(best, 0), total))
    return rows


def report_md(results: dict[str, Any]) -> str:
    cells = list(results["cells"].values())
    lines = ["# CICS crucible: where the pipeline stands", "",
             "<!-- Generated by tests/tools/cics_crucible.py --update-baseline; do not edit by hand. -->", "",
             f"Measured against [cics-crucible](https://github.com/squid-protocol/cics-crucible) at "
             f"`{results.get('crucible_ref') or PINNED_REF}` (tests/_cics_crucible_pin.py). Epic #3989. "
             "Each case of the crucible is a small CICS application whose scenarios carry a hand-written "
             "expected event log, derived from IBM's documentation. Here is how the pipeline's output compares "
             "with those logs, cell by cell. A cell is one side of one scenario: **engine-facts** (per case: the scan "
             "recorded its programs, transactions, maps and CICS commands), **forge-compile** (per case: the "
             "generated Spring Boot project compiles), **cobol-stub** (the COBOL on the harness's stub CICS "
             "runtime), **java** (the generated services, task by task through `CicsTask`), **java-ported** (the "
             "same, with each case's committed ports laid over the services: tests/cics_crucible/ports, the porting "
             "loop's proven overlays, #3989) and **java-facade** (the ported services again, each task entered "
             "through its program's deployed entry point -- the Spring facade handleTransaction, or handleLink for a "
             "program a LINK / XCTL reaches -- whose task joins the scenario's region, #4343). A cell passes, "
             "fails at its first divergence from the log, or is *unsupported*: the harness cannot model "
             "something the scenario needs yet. The comparison is exact (SPEC 6).", "",
             "Every cell that does not pass is ledgered in `tests/cics_crucible/baseline.json`, and CI "
             "(`cics-crucible.yml`) holds the ledger as a ratchet.", "",
             "## Cells by side", "", "| side | pass | fail | unsupported | total |", "|---|---|---|---|---|"]  # fmt: skip
    for side in cc.SIDES:
        mine = [c for c in cells if c["side"] == side]
        if mine:
            n = Counter(c["status"] for c in mine)
            lines.append(f"| {side} | {n['pass']} | {n['fail']} | {n['unsupported']} | {len(mine)} |")
    n = Counter(c["status"] for c in cells)
    lines += [f"| **all** | **{n['pass']}** | **{n['fail']}** | **{n['unsupported']}** | **{len(cells)}** |", "",
              "## By trap and case", "", "Pass counts per side (scenario sides: passing / scenarios).", "",
              "| trap | case | " + " | ".join(cc.SIDES) + " |", "|---|---|" + "---|" * len(cc.SIDES)]  # fmt: skip
    by_case: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for c in cells:
        by_case[(c["trap"], c["case"])].append(c)
    for (trap, case), mine in sorted(by_case.items()):
        row = []
        for side in cc.SIDES:
            s = [c for c in mine if c["side"] == side]
            if not s:
                row.append("--")
            elif side in cc.CASE_SIDES:
                row.append({"pass": "pass", "fail": "**fail**", "unsupported": "unsupported"}[s[0]["status"]])
            else:
                row.append(f"{sum(c['status'] == 'pass' for c in s)} / {len(s)}")
        lines.append(f"| {trap} | `{case}` | " + " | ".join(row) + " |")
    lines += coverage_md(results)
    lines += ["", "## Harness work, in the order that unlocks the most cells", "",
              "Each missing feature belongs to a piece of harness work (below: the features themselves). A cell is "
              "*unlocked* when every piece its features need is done: it then gets a pass or fail verdict rather "
              "than `unsupported`. **needs** counts the cells that do not pass and need the piece, **alone** the "
              "unsupported cells it unlocks by itself, and **cumulative** the unsupported cells unlocked by it and "
              "every row above it (rows are chosen greedily).", ""]  # fmt: skip
    for side in ("cobol-stub", "java", "java-ported", "java-facade"):
        mine = [c for c in cells if c["side"] == side]
        rows = unlock_order(mine)
        if not rows:
            continue
        stuck = sum(c["status"] == "unsupported" for c in mine)
        lines += [f"### {side} ({stuck} unsupported)", "", "| # | harness work | needs | alone | cumulative |",
                  "|---|---|---|---|---|"]  # fmt: skip
        lines += [f"| {i} | {g} | {n} | {a} | {t} |" for i, (g, n, a, t) in enumerate(rows, 1)]
        lines.append("")
    lines += ["## Unsupported features, by how many cells need them", "",
              "Each feature a cell needs that its side does not model (`translator:` the COBOL translator refuses "
              "the command; `stub:` the stub runtime does not record it; `CicsTask:` the generated Java runtime "
              "does not; `scheduler:` the task driver).", ""]  # fmt: skip
    for side in ("cobol-stub", "java", "java-ported", "java-facade"):
        blocks = Counter(f for c in cells if c["side"] == side and c["status"] != "pass" for f in c["features"])
        if not blocks:
            continue
        lines += [f"### {side}", "", "| feature | cells | harness work |", "|---|---|---|"]
        lines += [f"| {f} | {k} | {feature_group(f)} |" for f, k in sorted(blocks.items(), key=lambda x: (-x[1], x[0]))]
        lines.append("")
    lines += ["## Failure reasons, grouped", "", "| side | reason | cells |", "|---|---|---|"]
    kinds = Counter((c["side"], c["kind"] or c["reason"]) for c in cells if c["status"] == "fail")
    for (side, kind), k in sorted(kinds.items(), key=lambda x: (cc.SIDES.index(x[0][0]), -x[1], x[0][1])):
        lines.append(f"| {side} | {kind} | {k} |")
    lines += ["", "## Every cell that does not pass", "", "| cell | status | first divergence / reason |",
              "|---|---|---|"]  # fmt: skip
    for cid, c in results["cells"].items():
        if c["status"] != "pass":
            reason = " ".join(c["reason"].split()).replace("|", "\\|")
            lines.append(f"| `{cid}` | {c['status']} | {reason[:400]} |")
    return "\n".join(lines) + "\n"


def coverage_md(results: dict[str, Any]) -> list[str]:
    """#4023: the report's coverage section -- per program, how much of it the passing scenarios execute, its
    port's claim, and the live code no scenario reaches (each a scenario to propose to the crucible)."""
    per = results.get("coverage") or {}
    if not per:
        return []
    lines = ["", "## COBOL coverage", "",
             ("Each cobol-stub scenario runs the COBOL compiled with `-ftraceall` (tests/tools/cobol_coverage.py, "
             "#4023). Per program: the live paragraphs and sections the passing scenarios enter, out of all the live "
             "ones, and the branch outcomes they take (IF true / false; each EVALUATE arm, and no arm when there is "
             "no WHEN OTHER) in live code. Code that nothing can reach (the engine's reachability: PERFORM, GO TO, "
             "fall-through, HANDLE labels) is dead, and is listed apart. A port's claim counts only the scenarios "
             "its java-ported cell passes on. `tests/cics_crucible/coverage.json` holds what each scenario executes, "
             "and CI holds it as a ratchet."), "",
             "| case | program | scenarios | paragraphs | branches | HANDLE labels | dead | port |",
             "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for case, progs in per.items():
        for prog, r in progs.items():
            s = r["summary"]
            p, b, h = s["paragraphs"], s["branches"], s["handler_labels"]
            port = r["port"]["claim"] if r.get("port") else "--"
            lines.append(f"| `{case}` | {prog} | {len(r['scenarios'])} | {p['covered']}/{p['live']} | "
                         f"{b['covered']}/{b['total']} | {h['covered']}/{h['total']} | {len(p['dead'])} | {port} |")  # fmt: skip
    gaps = [(case, prog, r["summary"]) for case, progs in per.items() for prog, r in progs.items()
            if cov.gaps_md(r["summary"]) or r["summary"]["paragraphs"]["dead"]
            or r["summary"]["paragraphs"].get("unread")]  # fmt: skip
    if gaps:
        lines += ["", "### Live code no scenario reaches", "",
                  ("Each item is a scenario to propose: a crucible PR adds it with a hand-written, doc-cited expected "
                  "log, like every other. Dead code is not a gap: nothing can reach it."), ""]  # fmt: skip
        for case, prog, s in gaps:
            lines += [f"#### `{case}` {prog}", "", *cov.gaps_md(s)]
            if s["paragraphs"]["dead"]:
                lines.append(f"- dead: {', '.join(f'`{n}`' for n in s['paragraphs']['dead'])}")
            if s["paragraphs"].get("unread"):
                lines.append(
                    "- **entered, but the engine does not read it as a unit** (an engine defect): "
                    + ", ".join(f"`{n}`" for n in s["paragraphs"]["unread"])
                )
            if s["paragraphs"].get("dead_but_executed"):
                lines.append(
                    "- **dead to the engine, yet a scenario entered it** (a reachability defect): "
                    + ", ".join(f"`{n}`" for n in s["paragraphs"]["dead_but_executed"])
                )
            lines += [
                f"- not counted: {u['kind']} at line {u['line']} ({u['why']})" for u in s["branches"]["unresolvable"]
            ]
            lines.append("")
    return lines


# ---- a proof for the porting loop (port_runner prove --command) -----------------------------------------
_WHERE = re.compile(r"^task (\d+)(?: \([^)]*\))?(?: event (\d+))?")


def _plain(value: Any) -> Any:
    """An actual log's value as JSON: an area as its fields or bytes, anything else as it is."""
    if isinstance(value, cc.FieldArea):
        return {"length": value.length if isinstance(value.length, int) else str(value.length), "fields": value.fields}
    if isinstance(value, cc.RawArea):
        return {"length": len(value.data), "text": value.data.decode(value.encoding, "replace")}
    if isinstance(value, cc.Unmodelled):
        return f"<{value.feature}>"
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _note_free(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _note_free(v) for k, v in value.items() if k != "note"}
    if isinstance(value, list):
        return [_note_free(v) for v in value]
    return value


def proof_feedback(case: cc.Case, cells: dict[str, dict[str, Any]], actual: dict[str, dict[str, Any]]) -> str:
    """What a porter needs to see of a failed proof, per scenario that does not pass: its inputs, the first
    divergence from the expected log (the expected event there), what the port recorded in that task, and any
    compile or run errors. The expected logs themselves stay the oracle: only the diverging event is shown."""
    out: list[str] = []
    for cid, cell in cells.items():
        if cell["status"] == "pass":
            continue
        sc = next(x for x in case.scenarios if x["id"] == cell["scenario"])
        exp = case.expected[sc["id"]]
        out += [f"### Scenario `{sc['id']}` ({cell['status']})", "", sc.get("summary", ""), "",
                "Operator steps (SPEC section 5):", "```json", json.dumps(_note_free(sc["steps"]), indent=1), "```",
                f"First divergence: {cell['reason']}"]  # fmt: skip
        if cell.get("detail"):
            out += ["", "```", cell["detail"][-6000:], "```"]
        m = _WHERE.match(cell["reason"])
        log = actual.get(cid)
        if m and log is not None:
            t = int(m.group(1))
            exp_task = exp["tasks"][t - 1] if t <= len(exp["tasks"]) else None
            got_task = log["tasks"][t - 1] if t <= len(log["tasks"]) else None
            if exp_task is not None:
                head = {k: exp_task.get(k) for k in ("seq", "transid", "program", "eibaid", "eibcalen", "commarea")}
                out += ["", f"Task {t} as expected (without its events):", "```json",
                        json.dumps(_note_free(head), indent=1), "```"]  # fmt: skip
                if m.group(2):
                    n = int(m.group(2))
                    if n <= len(exp_task["events"]):
                        out += [f"Expected event {n}:", "```json",
                                json.dumps(_note_free(exp_task["events"][n - 1]), indent=1), "```"]  # fmt: skip
            if got_task is not None:
                out += [f"What the port recorded in task {t}:", "```json",
                        json.dumps(_plain(got_task.get("events", [])), indent=1, default=str), "```"]  # fmt: skip
        out.append("")
    return "\n".join(out)


def write_proof(report_dir: Path, case: cc.Case, results: dict[str, Any], opts: PortOptions) -> bool:
    """report.json for `port_runner prove`: per scenario 1/1 or 0/1, the verdicts, and the feedback a next
    attempt is given. Proven when every java-ported cell of the program's scenarios passes -- and, when the
    java-facade side ran (#4343), every java-facade cell too: the scenario entered through the deployed entry
    points. `entries` lists the facades of the program that its passing java-facade scenarios ran."""
    cells = {cid: c for cid, c in results["cells"].items() if c["side"] in ("java-ported", "java-facade")}
    proven = any(c["side"] == "java-ported" for c in cells.values()) and all(c["status"] == "pass"
                                                                          for c in cells.values())  # fmt: skip
    ported = sorted(case_overlays(opts.ports if opts.ports is not None else opts.root / case.id))
    outputs: dict[str, dict[str, int]] = {}
    for c in cells.values():
        o = outputs.setdefault(c["scenario"], {"equal": 1, "records": 1})
        o["equal"] &= int(c["status"] == "pass")
    by_method: dict[str, list[str]] = {}
    for cid, c in cells.items():
        if c["side"] != "java-facade" or c["status"] != "pass":
            continue
        for e in opts.entries.get(cid, []):
            if e.get("program") == opts.program and e.get("method") != "runTask":
                by_method.setdefault(e["method"], [])
                if c["scenario"] not in by_method[e["method"]]:
                    by_method[e["method"]].append(c["scenario"])
    report = {"format": "cics-crucible-proof/1", "case": case.id, "program": opts.program,
              "crucible_ref": results.get("crucible_ref"), "oracle": results.get("oracle"), "ports": ported,
              "overlays": [str(o) for o in opts.overlays], "proven": proven,
              "outputs": outputs,
              "entries": [{"method": m, "scenarios": sorted(sids)} for m, sids in sorted(by_method.items())],
              "cells": {cid: {k: c.get(k) for k in ("status", "reason", "kind")} for cid, c in cells.items()},
              "feedback": proof_feedback(case, cells, opts.actual)}  # fmt: skip
    if opts.program and proven:  # #4023: how much of the program the proof's scenarios execute
        report["claim"] = ledger_claim(case.id, opts.program, sorted(outputs))
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "report.json").write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")
    return proven


# ---- CLI ------------------------------------------------------------------------------------------------
def hold_ratchets(
    results: dict[str, Any], sides: set[str], custom: bool, complete: bool, cases: set[str] | None = None
) -> int:
    """--ci: print the ratchet errors, return the exit status. `cases` cuts both ledgers to one shard's cases."""
    baseline, ledger = read_baseline(), read_coverage()
    if cases is not None:
        baseline, ledger = restrict(baseline, ledger, cases)
    errors, notes = ratchet(results, baseline, complete)
    if "cobol-stub" in sides and not custom:
        errors += coverage_ratchet(results, ledger, complete)
    for line in notes:
        print(f"note: {line}")
    for line in errors:
        print(line)
    if errors:
        print(f"\n{len(errors)} ratchet error(s). If intended, run with --update-baseline and commit "
              "tests/cics_crucible/baseline.json, tests/cics_crucible/coverage.json and "
              "docs/language_status/cics_crucible.md.")  # fmt: skip
    return 1 if errors else 0


def merge_main(args: argparse.Namespace, crucible: Path) -> int:
    """#5498: one run from its shards' --out dirs: the completeness check, the whole 710-cell report, the full ratchet."""
    parts = [json.loads((d / "results.json").read_text(encoding="utf-8")) for d in args.merge]
    results, errors = merge_shards(parts, [d.name for d in cc.discover(crucible)])
    for line in errors:
        print(line)
    if errors:
        return 1
    n = Counter(c["status"] for c in results["cells"].values())
    print(f"CICS crucible: {n['pass']} pass, {n['fail']} fail, {n['unsupported']} unsupported "
          f"({len(results['cells'])} cells, {len(parts)} shards)")  # fmt: skip
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "results.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
        (args.out / "report.md").write_text(report_md(results), encoding="utf-8")
    return hold_ratchets(results, set(cc.SIDES), False, True) if args.ci else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--crucible", type=Path, help=f"the cics-crucible checkout (default: ${PATH_ENV}, else ../cics-crucible)"
    )
    ap.add_argument("--cases", nargs="+", help="case ids to run (default: all)")
    ap.add_argument("--sides", nargs="+", choices=cc.SIDES, default=list(cc.SIDES))
    ap.add_argument("--keep", type=Path, help="keep the work tree here (default: a temporary directory)")
    ap.add_argument("--out", type=Path, help="write results.json and report.md here")
    ap.add_argument("--offline", action="store_true", help="run Maven offline (mvn -o)")
    ap.add_argument(
        "--ci", action="store_true", help="fail on a cell the baseline does not list, or a listed one that passes"
    )
    ap.add_argument("--update-baseline", action="store_true", help="write the baseline and the report from this run")
    ap.add_argument("--shard", metavar="i/N", help="#5498: run only shard i of N (a balanced partition of the cases); "
                    "--ci then holds the ledgers cut to those cases. Merge the shards' --out dirs with --merge")  # fmt: skip
    ap.add_argument("--merge", type=Path, nargs="+", metavar="DIR", help="#5498: merge the --out dirs of every shard of "
                    "one run, check each case ran in exactly one, and hold the whole ratchet (with --ci)")  # fmt: skip
    ap.add_argument("--ports", type=Path, help="java-ported: a directory of <KEY>/overlay port trees (port_runner's "
                    "ai_agent_jobs/ports) instead of the committed tests/cics_crucible/ports/<case>")  # fmt: skip
    ap.add_argument("--overlay", type=Path, action="append", default=[],
                    help="java-ported: one more overlay tree, laid last (port_runner prove's {port_dir})")  # fmt: skip
    ap.add_argument("--program", help="java-ported: only the scenarios that run this program (a proof of its port)")
    ap.add_argument("--report-dir", type=Path, help="write a proof report.json here (port_runner prove's "
                    "{report_dir}); the exit status is then whether every java-ported cell passes")  # fmt: skip
    ap.add_argument("--forge-cache", type=Path, help="#4047: a directory holding the generated project, filled by the "
                    "first run and copied by later ones (the mutation runs' fast mode); java-ported only")  # fmt: skip
    ap.add_argument("--jobs", type=int, default=1, help="#5882: measure this many cases at once (one process each)")
    ap.add_argument("--strengthened", action="store_true",
                    help="#4049: add each case's strengthened scenarios (tests/cics_crucible/strengthened)")  # fmt: skip
    ap.add_argument("--derive-expected", action="store_true", help="#4049: run the strengthened scenarios of the "
                    "--cases on the COBOL side and write their expected logs (the COBOL decides them)")  # fmt: skip
    args = ap.parse_args(argv)
    crucible = crucible_path(args.crucible).resolve()
    if not (crucible / "SPEC.md").is_file():
        print(f"no cics-crucible checkout at {crucible} (set {PATH_ENV} or pass --crucible)", file=sys.stderr)
        return 2
    problem = pin_mismatch(crucible)
    if problem:
        print(problem, file=sys.stderr)
        return 2
    if args.merge:
        return merge_main(args, crucible)
    if args.derive_expected:
        work = (args.keep or Path(tempfile.mkdtemp(prefix="cics_crucible_derive_"))).resolve()
        for d in cc.discover(crucible, set(args.cases) if args.cases else None):
            case = cc.load_case(d)
            ids = derive_case(case, work / case.id)
            print(f"{case.id}: {len(ids)} expected log(s) derived from the COBOL: {', '.join(ids) or '-'}")
        return 0
    if args.strengthened and (args.ci or args.update_baseline):
        print("--strengthened scenarios are held for review: not in the baseline or the --ci ratchet", file=sys.stderr)
        return 2
    ported = PortOptions(ports=args.ports.resolve() if args.ports else None,
                         overlays=[o.resolve() for o in args.overlay], program=args.program,
                         forge_cache=args.forge_cache.resolve() if args.forge_cache else None)  # fmt: skip
    custom = bool(args.ports or args.overlay or args.program)
    complete = not args.cases and set(args.sides) == set(cc.SIDES) and not custom
    if args.update_baseline and not complete:
        print("--update-baseline records every cell with the committed ports: run it without --cases / --sides / "
              "--ports / --overlay / --program", file=sys.stderr)  # fmt: skip
        return 2
    if (custom or args.report_dir) and (not args.cases or len(args.cases) != 1):
        print(
            "--ports / --overlay / --program / --report-dir prove one case's ports: give one --cases", file=sys.stderr
        )
        return 2
    shard: dict[str, Any] | None = None
    if args.shard:
        if args.cases or args.update_baseline or custom or args.strengthened:
            print("--shard cuts a whole run: not with --cases / --update-baseline / --ports / --overlay / --program "
                  "/ --strengthened", file=sys.stderr)  # fmt: skip
            return 2
        index, total = parse_shard(args.shard)
        plan = shard_plan([d.name for d in cc.discover(crucible)], total)
        shard = {"index": index, "total": total, "cases": plan[index - 1]}
        print(f"shard {index}/{total}: {len(shard['cases'])} cases: {' '.join(shard['cases'])}", flush=True)
        args.cases = shard["cases"]
    work = args.keep or Path(tempfile.mkdtemp(prefix="cics_crucible_"))
    results = measure(crucible, set(args.cases) if args.cases else None, set(args.sides), work.resolve(), args.offline,
                      ported, args.strengthened, args.jobs)  # fmt: skip
    if shard:
        results["shard"] = shard
    n = Counter(c["status"] for c in results["cells"].values())
    print(f"CICS crucible: {n['pass']} pass, {n['fail']} fail, {n['unsupported']} unsupported "
          f"({len(results['cells'])} cells)")  # fmt: skip
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "results.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
        (args.out / "report.md").write_text(report_md(results), encoding="utf-8")
    if args.report_dir:
        case = cc.load_case(cc.discover(crucible, set(args.cases))[0])
        if args.strengthened:
            add_strengthened(case)
        proven = write_proof(args.report_dir, case, results, ported)
        print(f"proof: {'PROVEN' if proven else 'not proven'} ({args.report_dir / 'report.json'})")
        return 0 if proven else 1
    if args.update_baseline:
        write_baseline(results)
        write_coverage(results)
        REPORT.write_text(report_md(results), encoding="utf-8")
        print(f"baseline: {len(baseline_of(results)['cells'])} cells ledgered; coverage: "
              f"{len(coverage_of(results)['programs'])} programs; report: {REPORT.relative_to(REPO_ROOT)}")  # fmt: skip
        return 0
    if args.ci:
        return hold_ratchets(results, set(args.sides), custom, complete, set(shard["cases"]) if shard else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
