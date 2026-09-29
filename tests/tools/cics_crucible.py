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
                         runTask(), driven by a generated EquivalenceRunTest

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

    python tests/tools/cics_crucible.py --ci                    # measure, check the ratchet
    python tests/tools/cics_crucible.py --update-baseline       # record today's cells + the report
    python tests/tools/cics_crucible.py --cases pc-wizard --sides engine-facts java --keep /tmp/w

Needs: the crucible checkout (CICS_CRUCIBLE_PATH, else ../cics-crucible beside the main gitgalaxy
checkout) at the pin; for cobol-stub, Docker and the GnuCOBOL image (tests/equivalence/
gnucobol.Dockerfile); for forge-compile / java, a JDK 17 and Maven (`--offline` for mvn -o).
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from collections.abc import Iterator
from typing import Any, Optional

HERE_TOOLS = Path(__file__).resolve().parent
REPO_ROOT = HERE_TOOLS.parents[1]
sys.path.insert(0, str(HERE_TOOLS))
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT))

import cics_crucible_compare as cc  # noqa: E402
from _cics_crucible_pin import PATH_ENV, PINNED_REF, pin_mismatch  # noqa: E402

LEDGER_DIR = REPO_ROOT / "tests" / "cics_crucible"
BASELINE = LEDGER_DIR / "baseline.json"
REPORT = REPO_ROOT / "docs" / "language_status" / "cics_crucible.md"
BASELINE_FORMAT = "cics-crucible-baseline/1"
STUB_DIR = REPO_ROOT / "tests" / "equivalence" / "cics"

# SPEC 6.2: the abend code CICS gives an unhandled condition (the AEIA topic of IBM's abend codes).
CONDITION_ABCODE = {"NOTFND": "AEIM", "LENGERR": "AEIV", "ITEMERR": "AEIZ", "QIDERR": "AEYH", "MAPFAIL": "AEI9",
                    "ENDDATA": "AEI2", "PGMIDERR": "AEI0", "INVREQ": "AEIP"}  # fmt: skip
SEND_OPTIONS = ("ERASE", "ERASEAUP", "MAPONLY", "DATAONLY", "FREEKB", "ALARM", "FRSET", "CURSOR", "WAIT", "LAST")

# What each scenario side records (see cics_crucible_compare.Capabilities).
COBOL_CAPS = cc.Capabilities(
    layer="stub",
    task_keys=frozenset(cc.TASK_KEYS) | {"end"},
    events={
        "SEND-MAP": frozenset({"map", "mapset", "options"}),  # fields: BMS output resolution is not modelled
        "SEND-TEXT": frozenset({"text", "length", "options"}),
        "RECEIVE-MAP": frozenset({"map", "mapset", "resp"}),
        "RECEIVE": frozenset({"resp", "length", "data"}),
        "RETURN": frozenset({"level", "transid", "commarea", "caller_commarea"}),
        "LINK": frozenset({"target", "length", "commarea", "resp", "resp2"}),
        "XCTL": frozenset({"target", "length", "commarea", "resp"}),
        "ABEND": frozenset({"abcode", "cause", "condition", "outcome", "exit"}),
        "READ": frozenset({"file", "ridfld", "resp"}),
        "READQ-TS": frozenset({"queue", "item", "resp", "length", "data"}),
        "WRITEQ-TS": frozenset({"queue", "data", "resp", "item"}),
        "START": frozenset(
            {"transid", "termid", "interval", "time", "from", "reqid", "protect", "resp", "resp2", "expires"}
        ),
        "RETRIEVE": frozenset({"resp", "length", "data"}),
        "CANCEL": frozenset({"reqid", "resp"}),
    },
    ts_queues=True,
    start_tasks=True,
)
JAVA_CAPS = cc.Capabilities(
    layer="CicsTask",
    task_keys=frozenset(cc.TASK_KEYS) | {"end"},
    events={
        "SEND-MAP": frozenset({"map", "fields", "fields.data"}),
        "SEND-TEXT": frozenset({"text", "length", "options"}),
        "RECEIVE": frozenset({"resp", "length", "data"}),
        "RECEIVE-MAP": frozenset({"map", "mapset", "resp"}),  # #4009
        "RETURN": frozenset({"level", "transid", "commarea", "caller_commarea"}),
        "LINK": frozenset({"target", "length", "commarea", "resp", "resp2"}),
        "XCTL": frozenset({"target", "commarea"}),
        "ABEND": frozenset({"abcode", "cause", "condition", "outcome", "exit"}),
        "READQ-TS": frozenset({"queue", "item", "resp", "length", "data"}),
        "WRITEQ-TS": frozenset({"queue", "data", "resp", "item"}),
        "START": frozenset(
            {"transid", "termid", "interval", "time", "from", "reqid", "protect", "resp", "resp2", "expires"}
        ),
        "RETRIEVE": frozenset({"resp", "length", "data"}),
        "CANCEL": frozenset({"reqid", "resp"}),
    },
    ts_queues=True,
    start_tasks=True,
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


def crucible_path(arg: Optional[Path]) -> Path:
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


def crucible_ref(path: Path) -> Optional[str]:
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
    cmd = ["mvn", "-q", "-B", *(["-o"] if offline else []), *args]
    proc = subprocess.run(cmd, cwd=project, env=env, capture_output=True, text=True, check=False)  # noqa: S603
    log.write_text(proc.stdout + proc.stderr, encoding="utf-8")
    errors = [ln for ln in (proc.stdout + proc.stderr).splitlines() if "ERROR" in ln or "error:" in ln]
    return proc.returncode == 0, "\n".join(errors[:6]) or _tail(proc.stdout + proc.stderr, 6)


def forge(case: cc.Case, work: Path, offline: bool) -> tuple[cc.Verdict, Optional[Path]]:
    """Refactor + cobol-to-java (config h2, the equivalence harness's) + `mvn compile`."""
    import java_target_matrix as jtm

    work.mkdir(parents=True, exist_ok=True)
    try:
        with quiet(work / "forge.log"):
            clean = jtm.refactor(case.dir, work, scan=True)
            project = jtm.generate(clean, "h2", jtm.MATRIX["h2"], work)
    except (Exception, SystemExit) as e:  # noqa: BLE001 -- the generator failing is this cell's verdict
        return cc.Verdict(
            "fail", f"generation failed: {e!r} (see {work / 'forge.log'})", kind="generation failed"
        ), None
    ok, errors = maven(project, ["compile"], offline, work / "compile.log")
    if not ok:
        first = errors.splitlines()[0] if errors else "mvn compile failed"
        return cc.Verdict("fail", f"mvn compile: {first}", kind="does not compile"), project
    return cc.Verdict("pass", "compiles"), project


# ---- the scenario driver, shared by both sides -----------------------------------------------------
def task_frame(case: cc.Case, n: int, step: dict[str, Any]) -> dict[str, Any]:
    """What the scheduler decides about the task step `n` starts (SPEC section 4)."""
    clock = datetime.datetime.fromisoformat(case.data["clock"]) + datetime.timedelta(seconds=step["at"])
    return {"termid": case.data["terminal"], "at": clock.strftime("%Y-%m-%dT%H:%M:%S"),
            "trigger": {"kind": "terminal", "step": n}, "eibaid": step["aid"]}  # fmt: skip


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
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;

/**
 * #3989: the CICS crucible's Java side -- generated by tests/tools/cics_crucible.py. Each scenario's
 * terminal steps run as tasks through the generated services' runTask(CicsTask): a step starts the
 * TRANSID and COMMAREA of the previous task's RETURN, else the transaction id typed as text; an XCTL
 * runs its target in the same task. Each task's events are written to out/<scenario>.json.
 */
@SpringBootTest(properties = {"spring.jpa.show-sql=false"})
class EquivalenceRunTest {

    final Path in = Path.of(System.getProperty("equivalence.in"));
    final Path out = Path.of(System.getProperty("equivalence.out"));
    final ObjectMapper json = new ObjectMapper().findAndRegisterModules();

    @Autowired
    ApplicationContext context;

    @Test
    void run() throws Exception {
        JsonNode plan = json.readTree(in.resolve("plan.json").toFile());
        for (JsonNode sc : plan.get("scenarios")) {
            json.writeValue(out.resolve(sc.get("id").asText() + ".json").toFile(), new Scenario(plan, sc).drive());
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
        int issued;
        String pending;
        Object pendingCa;
        Integer pendingLen;  // #4009: the next task's EIBCALEN (null: the whole record)
        LocalDateTime now;

        Scenario(JsonNode plan, JsonNode sc) {
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
        }

        Map<String, Object> drive() {
            JsonNode steps = sc.get("steps");
            int next = 0;
            String stopped = null;
            while (true) {
                List<Map<String, Object>> expired = requests.stream()
                        .filter(r -> !((LocalDateTime) r.get("expires")).isAfter(now)).toList();
                if (!expired.isEmpty()) {
                    Map<String, Object> first = expired.stream().min(EXPIRY).get();
                    List<Map<String, Object>> group = first.get("termid") == null ? List.of(first)
                            : expired.stream().filter(r -> r.get("transid").equals(first.get("transid"))
                                    && first.get("termid").equals(r.get("termid"))).sorted(EXPIRY).toList();
                    requests.removeAll(group);
                    List<byte[]> data = new ArrayList<>();
                    group.forEach(r -> {
                        if (r.get("data") != null) {
                            data.add((byte[]) r.get("data"));
                        }
                    });
                    Map<String, Object> trigger = new LinkedHashMap<>();
                    trigger.put("kind", "start");
                    trigger.put("task", first.get("task"));
                    trigger.put("event", first.get("event"));
                    runOne(frame((String) first.get("termid"), trigger, null), (String) first.get("transid"), null,
                            null, null, data);
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
                    if (transid == null) {
                        String text = step.path("text").asText("").trim();
                        if (text.isEmpty()) {
                            stopped = "step " + n + ": no pending RETURN TRANSID and no transaction id typed";
                            break;
                        }
                        transid = text.split("\\s+")[0];
                        commarea = null;
                        calen = null;
                    }
                    Map<String, Object> trigger = new LinkedHashMap<>();
                    trigger.put("kind", "terminal");
                    trigger.put("step", n);
                    runOne(frame(terminal, trigger, step.get("aid").asText()), transid, commarea, calen, step, List.of());
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
            return log;
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
                List<byte[]> data) {
            String program = plan.path("transactions").path(transid).asText(null);
            Map<String, Object> task = new LinkedHashMap<>(frame);
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
                        .withRetrieveData(data).withRequests(unexpired);
                if (step != null && step.has("text")) {
                    t.withTerminalInput(step.get("text").asText());
                }
                String thrown = null;
                try {
                    t.run(program);
                } catch (RuntimeException e) {
                    String code = abcode(e);
                    if (code != null) {
                        t.abend(code);
                    } else {
                        thrown = e.getMessage() != null && e instanceof IllegalStateException ? e.getMessage()
                                : "runTask threw " + e;
                    }
                }
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
                    events.add(copy);
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
                }
            }
            if (atTerminal) {
                pending = abended ? null : transid;
                pendingCa = abended || transid == null ? null : commarea;
                pendingLen = abended || transid == null ? null : length;
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
    scenarios = [{"id": sc["id"], "steps": sc["steps"], "until": sc.get("until"),
                  "ts_queues": {q: [cc.expected_bytes(i).hex() for i in items]
                                for q, items in ((sc.get("initial") or {}).get("ts_queues") or {}).items()}}
                 for sc in case.scenarios]  # fmt: skip
    return {
        "transactions": case.csd["transactions"],
        "programs": sorted(case.csd["programs"]),  # #4004: LINK's PGMIDERR
        "clock": case.data["clock"],  # #4006: the scheduler's virtual clock and terminal
        "terminal": case.data["terminal"],
        "services": services,
        "screens": screens,
        "scenarios": scenarios,
    }


def _java_area(desc: Optional[dict[str, Any]], src: Path, shapes: dict[str, Any],
               length: Any = None) -> Optional[cc.FieldArea]:  # fmt: skip
    """A DTO the Java side recorded, as field values with the length CicsTask gave it (#4009: a
    LENGTH, or its whole record when none was given)."""
    import equivalence_cics as ec

    if desc is None:
        return None
    cls = desc["class"]
    if cls not in shapes:
        shapes[cls] = ec.dto_shape(src, cls)  # qualified: the contract DTO, not the entity of that name (#4011)
    return cc.FieldArea(ec.from_java(desc["value"], shapes[cls]), cc.FULL if length is None else length)


def java_actual(case: cc.Case, raw: dict[str, Any], src: Path) -> dict[str, Any]:
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
                ev["map"] = e.get("map")
                ev["fields"] = {k: {"data": v} for k, v in (e.get("screen") or {}).items()}
            elif kind == "SEND-TEXT":  # #4009: the FROM data, its LENGTH and options
                ev.update(text=e.get("text"), length=e.get("length"), options=e.get("options") or [])
            elif kind == "RECEIVE":  # #4005: the data as text, the area's bytes in the stub's page
                ev.update(resp=e.get("resp"), length=e.get("length"),
                          data=cc.RawArea(str(e.get("data") or "").encode("latin-1"), "latin-1"))  # fmt: skip
            elif kind in ("READQ-TS", "WRITEQ-TS"):  # #4002: byte[] data arrive as base64, EBCDIC bytes
                b64 = e.get("data")
                data = cc.RawArea(base64.b64decode(b64), cc.EBCDIC) if b64 is not None else None
                ev.update(queue=e.get("queue"), item=e.get("item"), resp=e.get("resp"), data=data)
                if kind == "READQ-TS":
                    ev["length"] = e.get("length")
            elif kind == "RECEIVE-MAP":
                ev.update(map=e.get("map"), mapset=e.get("mapset"), resp=e.get("resp"))
            elif kind == "RETURN" and (e.get("level") or 1) > 1:  # #4004: back to the linking program
                ev.update(level=e["level"], caller_commarea=_java_area(e.get("caller_commarea"), src, shapes))
            elif kind == "RETURN":
                ev.update(level=1, transid=e.get("transid"),
                          commarea=_java_area(e.get("commarea"), src, shapes, e.get("length")))  # fmt: skip
            elif kind == "LINK":
                ev.update(target=e.get("target"), length=e.get("length"), resp=e.get("resp"), resp2=e.get("resp2"),
                          commarea=_java_area(e.get("commarea"), src, shapes, e.get("length")))  # fmt: skip
            elif kind == "XCTL":
                ev.update(target=e.get("target"), commarea=_java_area(e.get("commarea"), src, shapes))
            elif kind == "START":  # #4006: FROM data as base64, EBCDIC bytes; REQID only if the program named one
                b64 = e.get("from")
                ev.update({k: e[k] for k in ("transid", "termid", "interval", "time", "reqid", "protect", "resp",
                                              "expires") if k in e})  # fmt: skip
                ev["from"] = cc.RawArea(base64.b64decode(b64), cc.EBCDIC) if b64 is not None else None
            elif kind == "RETRIEVE":
                b64 = e.get("data")
                ev.update(resp=e.get("resp"), length=e.get("length"),
                          data=cc.RawArea(base64.b64decode(b64), cc.EBCDIC) if b64 is not None else None)  # fmt: skip
            elif kind == "CANCEL":
                ev.update(reqid=e.get("reqid"), resp=e.get("resp"))
            elif kind == "ABEND":  # #4003: cause, condition, outcome and the exit, as CicsTask records them
                ev.update({k: e[k] for k in ("abcode", "cause", "condition", "outcome", "exit") if k in e})
            else:
                ev["message"] = e.get("message")
            task["events"].append(ev)
        tasks.append(task)
    final = {q: [bytes.fromhex(i) for i in items] for q, items in (raw.get("ts_queues") or {}).items()}
    return {"tasks": tasks, "stopped": raw.get("stopped"), "final": {"ts_queues": final}}


def run_java(case: cc.Case, project: Path, work: Path, offline: bool) -> dict[str, dict[str, Any]]:
    """Every scenario through the generated services; {scenario: actual log}. Raises RuntimeError when
    the test itself cannot run (the project does not start)."""
    import equivalence_java as ej

    src = project / "src/main/java"
    test = project / "src/test/java" / ej.PKG_DIR / "EquivalenceRunTest.java"
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text(_JAVA_TEST.replace("@PKG@", ej.PKG), encoding="utf-8")
    inputs, out = work / "in", work / "out"
    for d in (inputs, out):
        d.mkdir(parents=True, exist_ok=True)
    (inputs / "plan.json").write_text(json.dumps(java_plan(case, src), indent=1), encoding="utf-8")
    props = f"-Dequivalence.in={inputs} -Dequivalence.out={out} {ej.jvm_args(ej.environment('default'))}"
    ok, errors = maven(project, ["test", "-Dtest=EquivalenceRunTest", "-Dsurefire.failIfNoSpecifiedTests=false",
                                 f"-DargLine={props}"], offline, work / "maven.log")  # fmt: skip
    if not ok:
        raise RuntimeError(f"the Java run failed: {errors.splitlines()[0] if errors else 'mvn test'}")
    result = {}
    for sc in case.scenarios:
        f = out / f"{sc['id']}.json"
        raw = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {"tasks": [], "stopped": "no output"}
        raw["_scenario"] = sc["id"]
        result[sc["id"]] = java_actual(case, raw, src)
    return result


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


def _cobol_events(out: Path, program: str) -> list[dict[str, Any]]:
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
        elif verb == "SEND-TEXT":
            text = cc.to_ebcdic(cc.RawArea(data, "latin-1"))
            ev.update(text=text, length=int(arg("len") or 0), options=[o for o in opts if o in SEND_OPTIONS])
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
        elif verb == "RECEIVE-WAIT":
            ev = {"event": "DRIVER-ERROR", "program": issuer,
                  "message": "a second terminal RECEIVE in one task waits for input no scenario step gives"}  # fmt: skip
        elif verb == "START":  # #4006: INTERVAL or TIME as given (hhmmss), REQID only if the program named one
            resp = names.get(int(arg("resp") or 0), arg("resp"))
            ev.update(transid=arg("transid"), termid=arg("termid") or None,
                      **({"time": arg("time")} if arg("time") else {"interval": arg("interval")}),
                      **({"reqid": arg("reqid")} if arg("reqid") else {}),
                      protect=arg("protect") == "1", resp=resp, expires=arg("expires") if resp == "NORMAL" else None,
                      **{"from": cc.RawArea(data, "latin-1") if arg("area") == "1" else None})  # fmt: skip
        elif verb == "RETRIEVE":
            n = int(arg("len") or -1)
            ev.update(resp=names.get(int(arg("resp") or 0), arg("resp")), length=n if n >= 0 else None,
                      data=cc.RawArea(data, "latin-1") if n >= 0 else None)  # fmt: skip
        elif verb == "CANCEL":
            ev.update(reqid=arg("reqid"), resp=names.get(int(arg("resp") or 0), arg("resp")))
        elif verb == "NOPROGRAM":
            ev = {"event": "DRIVER-ERROR", "program": arg("target"),
                  "message": f"{arg('target')} is not a translated program of the case"}  # fmt: skip
        elif verb == "LINK":  # #4004: RESP2 only where the command is not NORMAL (SPEC 6.2: where IBM documents it)
            resp = names.get(int(arg("resp") or 0), arg("resp"))
            ev.update(target=arg("target"), length=int(arg("len") or 0),
                      commarea=cc.RawArea(data, "latin-1") if arg("area") == "1" else None, resp=resp,
                      resp2=int(arg("resp2") or 0) if resp != "NORMAL" else None)  # fmt: skip
        elif verb == "READ":
            ev.update(file=arg("file"), ridfld=arg("key").encode(cc.EBCDIC),
                      resp=names.get(int(arg("resp") or 0), arg("resp")))  # fmt: skip
        elif verb in ("RETURN", "END"):
            level = int(arg("level") or 1)
            ev = {"event": "RETURN", "program": issuer, "level": level}
            if level == 1:
                ev.update(transid=arg("transid") or None, commarea=cc.RawArea(data, "latin-1") if data else None)
            else:  # #4004: the LINK COMMAREA as the linking program now sees it (len -1: the LINK had none)
                ev["caller_commarea"] = cc.RawArea(data, "latin-1") if int(arg("len") or -1) >= 0 else None
        elif verb == "XCTL":
            area = cc.RawArea(data, "latin-1") if data else None
            ev.update(target=arg("program"), length=int(arg("len") or 0), commarea=area, resp="NORMAL")
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


def read_ts(root: Path) -> dict[str, list[bytes]]:
    """#4002: every TS queue in the stub's store, its items as EBCDIC bytes (the `final` state)."""
    out: dict[str, list[bytes]] = {}
    for d in sorted(root.iterdir()) if root.is_dir() else []:
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
        proc = subprocess.run(["docker", "run", "-d", "--rm", *user, "-v", f"{work}:/work", common.IMAGE,  # noqa: S603, S607
                               "sleep", "infinity"], capture_output=True, text=True, check=False)  # fmt: skip
        if proc.returncode != 0:
            raise RuntimeError(f"cannot start the GnuCOBOL container: {_tail(proc.stderr, 3)}")
        self.id = proc.stdout.strip()

    def sh(self, script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["docker", "exec", self.id, "bash", "-c", script],  # noqa: S603, S607
                              capture_output=True, text=True, check=False)  # fmt: skip

    def close(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.id], capture_output=True, check=False)  # noqa: S603, S607


def run_cobol(case: cc.Case, programs: dict[str, tuple[str, bool]], scenarios: list[str], ctx: cc.Context,
              work: Path) -> dict[str, dict[str, Any]]:  # fmt: skip
    """Compile the case's translated programs, its dispatcher and task driver with the stub into one
    executable, then drive each scenario's terminal steps as tasks (#4004: one process per task, in which
    a LINK runs a new level and an XCTL its target at the same level); {scenario: actual}."""
    import equivalence_cics as ec

    work.mkdir(parents=True, exist_ok=True)
    src = work / "src"
    src.mkdir(exist_ok=True)
    for d in case.data["sources"]["copy"]:
        for p in (case.dir / d).iterdir():
            if p.is_file():
                shutil.copy(p, src / p.name)
    for p in STUB_DIR.iterdir():
        shutil.copy(p, src / p.name)
    for prog, (text, _has_ca) in programs.items():
        (src / f"{prog}.cbl").write_text(text, encoding="latin-1")
    (src / "GGTASK.cbl").write_text(ec.task_driver(), encoding="ascii")
    (src / "GGCRUN.cbl").write_text(ec.task_dispatcher({p: ca for p, (_t, ca) in programs.items()}), encoding="ascii")
    units = " ".join(f"src/{p}.cbl" for p in ["GGTASK", "GGCRUN", *programs])
    compile_lines = ["set -e", "cd /work", "mkdir -p bin",
                     f"cobc -x -std=ibm -fsign=EBCDIC -fstatic-call -I /work/src -o bin/task {units} src/ggcics.c"]  # fmt: skip
    box = Container(work)
    try:
        proc = box.sh("\n".join(compile_lines))
        (work / "compile.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(f"cobc: {_tail(proc.stdout + proc.stderr, 3)}")
        return {sid: run_scenario(case, next(s for s in case.scenarios if s["id"] == sid), box, work)
                for sid in scenarios}  # fmt: skip
    finally:
        box.close()


def _epoch(when: datetime.datetime) -> int:
    """A virtual time as the stub's clock counts it (seconds, the naive time read as UTC)."""
    import calendar

    return calendar.timegm(when.timetuple())


def drive_scenario(case: cc.Case, sc: dict[str, Any], run_one: Any) -> tuple[list[dict[str, Any]], Optional[str]]:
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
    pending: Optional[str] = None
    pending_ca: Optional[bytes] = None
    now = clock
    steps = list(enumerate(sc["steps"]))

    def ended(task: dict[str, Any], at: datetime.datetime) -> None:
        nonlocal issued, pending, pending_ca
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
                                 "task": len(tasks), "event": j})  # fmt: skip
            elif e["event"] == "CANCEL" and e.get("resp") == "NORMAL":
                r = next((r for r in requests if r["reqid"] == e["reqid"] and r["expires"] > at), None)
                if r is not None:
                    requests.remove(r)
        if task.get("termid") == terminal:  # the terminal's next input starts this task's RETURN TRANSID
            last = next((e for e in reversed(task["events"]) if e["event"] == "RETURN" and e.get("level") == 1), None)
            pending = last["transid"] if last is not None and task["end"] == "normal" else None
            pending_ca = last["commarea"].data if pending and last is not None and last["commarea"] else None

    def run(frame: dict[str, Any], transid: str, commarea: Optional[bytes], step: Optional[dict[str, Any]],
            data: list[bytes], at: datetime.datetime) -> None:  # fmt: skip
        unexpired = [(r["reqid"], _epoch(r["expires"])) for r in requests if r["reqid"] and r["expires"] > at]
        task = run_one(frame, transid, commarea, step, data, unexpired)
        tasks.append(task)
        ended(task, at)

    while True:
        expired = [r for r in requests if r["expires"] <= now]
        if expired:
            first = min(expired, key=lambda r: (r["expires"], r["issue"]))
            group = [first]
            if first["termid"]:
                group = sorted((r for r in expired if (r["transid"], r["termid"]) == (first["transid"], first["termid"])),
                               key=lambda r: (r["expires"], r["issue"]))  # fmt: skip
            for r in group:
                requests.remove(r)
            frame = {"termid": first["termid"], "at": now.strftime("%Y-%m-%dT%H:%M:%S"),
                     "trigger": {"kind": "start", "task": first["task"], "event": first["event"]}, "eibaid": None}  # fmt: skip
            run(frame, first["transid"], None, None, [r["data"] for r in group if r["data"] is not None], now)
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
                transid, commarea = words[0], None
            run(task_frame(case, n, step), transid, commarea, step, [], now)
            continue
        if nxt is not None and until is not None and nxt < until:
            now = max(now, nxt)
            continue
        return tasks, None


def run_scenario(case: cc.Case, sc: dict[str, Any], box: "Container", work: Path) -> dict[str, Any]:
    """One scenario on the stub, scheduled as SPEC section 4 says (drive_scenario)."""
    ts = f"runs/{sc['id']}/ts"  # #4002: the region's TS queues, shared by every task of the scenario
    seed_ts(work / ts, (sc.get("initial") or {}).get("ts_queues") or {})
    count = iter(range(1000))

    def run_one(frame: dict[str, Any], transid: str, commarea: Optional[bytes], step: Optional[dict[str, Any]],
                data: list[bytes], requests: list[tuple[str, int]]) -> dict[str, Any]:  # fmt: skip
        rel = f"runs/{sc['id']}/{next(count):02d}"
        return run_task(case, box, work, rel, ts, transid, frame, commarea, step, data, requests)

    tasks, stopped = drive_scenario(case, sc, run_one)
    return {"tasks": tasks, "stopped": stopped, "final": {"ts_queues": read_ts(work / ts)}}


def run_task(case: cc.Case, box: "Container", work: Path, rel: str, ts: str, transid: str, frame: dict[str, Any],
             commarea: Optional[bytes], step: Optional[dict[str, Any]], data: Optional[list[bytes]] = None,
             requests: Optional[list[tuple[str, int]]] = None) -> dict[str, Any]:  # fmt: skip
    """One task in one process: its inputs in `rel` (the COMMAREA, the terminal's input -- a step's text or
    map fields -- the EIB, the CSD's programs and transactions, #4006: the START data it RETRIEVEs and the
    unexpired requests a CANCEL searches, the virtual clock), then the stub's events as the task's."""
    import equivalence_cics as ec
    import equivalence_common as common

    program = case.csd["transactions"].get(transid)
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
    (d / "files.cfg").write_text("", encoding="ascii")
    (d / "programs.cfg").write_text("".join(f"{p}\n" for p in sorted(case.csd["programs"])), encoding="ascii")
    (d / "transactions.cfg").write_text("".join(f"{t}\n" for t in sorted(case.csd["transactions"])), encoding="ascii")
    (d / "terminals.cfg").write_text(f"{case.data['terminal']}\n", encoding="ascii")
    (d / "requests.cfg").write_text("".join(f"{r} {e}\n" for r, e in requests or []), encoding="ascii")
    for i, item in enumerate(data or [], 1):
        (d / f"retrieve_{i:03d}.bin").write_bytes(item)
    if commarea:
        (d / "commarea.in").write_bytes(commarea)
    step = step or {}
    if step.get("text") is not None:  # SPEC 5: typed on a cleared screen, read from position 0
        (d / "terminal.in").write_bytes(step["text"].encode("latin-1"))
    if step.get("map") and step.get("fields"):
        m = step["map"]
        spec = case.data["maps"][m]
        fields = common.layout_fields(case.dir, spec["copybook"], f"{m}I")
        (d / f"receive_{m}.bin").write_bytes(
            ec.map_input(fields, {f"{k}I": v for k, v in step["fields"].items()}, "latin-1")
        )
    when = datetime.datetime.fromisoformat(frame["at"])
    eib_date, eib_time = _eib_datetime(when)
    aid = "DFH" + frame["eibaid"] if frame.get("eibaid") else ""
    (d / "eib.in").write_text(f"{transid:<4} {aid:<8} {eib_date} {eib_time} {program:<8} {frame.get('termid') or '':<4}\n",
                              encoding="ascii")  # fmt: skip
    box.sh(f"cd /work && GGCICS_DIR=/work/{rel} GGCICS_OUT=/work/{rel}/out EIBIN=/work/{rel}/eib.in "
           f"GGCICS_TS=/work/{ts} GGCICS_NOW={frame['at']} COB_CURRENT_DATE='{when.strftime('%Y/%m/%d %H:%M:%S')}.00' ./bin/task "
           f"> /work/{rel}/stdout.txt 2>&1")  # fmt: skip
    task["events"] = _cobol_events(d / "out", program)
    if any((e["event"] == "ABEND" and e.get("outcome") == "terminated") or e["event"] == "DRIVER-ERROR"
           for e in task["events"]):  # fmt: skip
        task["end"] = "abend"
    return task


# ---- one case -> its cells -------------------------------------------------------------------------
def measure_case(case: cc.Case, sides: set[str], work: Path, offline: bool) -> dict[str, dict[str, Any]]:
    """Every cell of one case: {cell id: {case, trap, scenario, side, status, reason, features, kind}}."""
    cells: dict[str, dict[str, Any]] = {}

    def put(scenario: str, side: str, v: cc.Verdict) -> None:
        cells[cc.cell_id(case.id, scenario, side)] = {"case": case.id, "trap": case.trap, "scenario": scenario,
                                                      "side": side, **v.as_dict()}  # fmt: skip

    work.mkdir(parents=True, exist_ok=True)
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
        if runnable:
            try:
                actual = run_cobol(case, programs, runnable, ctx, work / "cobol")
            except RuntimeError as e:
                actual = None
                for sid in runnable:
                    put(sid, "cobol-stub", cc.Verdict("fail", str(e), cc.blockers(case.expected[sid], COBOL_CAPS),
                                                      "the COBOL run failed"))  # fmt: skip
            for sid in runnable if actual else []:
                sc = next(s for s in case.scenarios if s["id"] == sid)
                put(sid, "cobol-stub", cc.compare(case.expected[sid], actual[sid], COBOL_CAPS, ctx, sc))
    return cells


def _kind_java(v: cc.Verdict, actual: dict[str, Any]) -> cc.Verdict:
    """Name the commonest Java failure for what it is: the generated runTask is a stub that records nothing."""
    if v.status == "fail" and not any(t["events"] for t in actual.get("tasks", [])):
        v.kind = "runTask records no events (the generated stub: PROCEDURE DIVISION not ported)"
    return v


def measure(crucible: Path, only: Optional[set[str]], sides: set[str], work: Path, offline: bool) -> dict[str, Any]:
    cells: dict[str, dict[str, Any]] = {}
    dirs = cc.discover(crucible, only)
    if not dirs:
        raise SystemExit(f"no cases under {crucible}/cases" + (f" matching {sorted(only)}" if only else ""))
    for d in dirs:
        case = cc.load_case(d)
        print(f"{case.id} ...", flush=True)
        got = measure_case(case, sides, work / case.id, offline)
        cells.update(got)
        by = Counter(f"{c['side']}:{c['status']}" for c in got.values())
        print("   " + ", ".join(f"{k} {n}" for k, n in sorted(by.items())), flush=True)
    return {"crucible_ref": crucible_ref(crucible), "cells": dict(sorted(cells.items()))}


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
             "runtime) and **java** (the generated services, task by task through `CicsTask`). A cell passes, "
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
              "| trap | case | engine-facts | forge-compile | cobol-stub | java |", "|---|---|---|---|---|---|"]  # fmt: skip
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
    lines += ["", "## Harness work, in the order that unlocks the most cells", "",
              "Each missing feature belongs to a piece of harness work (below: the features themselves). A cell is "
              "*unlocked* when every piece its features need is done: it then gets a pass or fail verdict rather "
              "than `unsupported`. **needs** counts the cells that do not pass and need the piece, **alone** the "
              "unsupported cells it unlocks by itself, and **cumulative** the unsupported cells unlocked by it and "
              "every row above it (rows are chosen greedily).", ""]  # fmt: skip
    for side in ("cobol-stub", "java"):
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
    for side in ("cobol-stub", "java"):
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


# ---- CLI ------------------------------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
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
    args = ap.parse_args(argv)
    crucible = crucible_path(args.crucible).resolve()
    if not (crucible / "SPEC.md").is_file():
        print(f"no cics-crucible checkout at {crucible} (set {PATH_ENV} or pass --crucible)", file=sys.stderr)
        return 2
    problem = pin_mismatch(crucible)
    if problem:
        print(problem, file=sys.stderr)
        return 2
    complete = not args.cases and set(args.sides) == set(cc.SIDES)
    if args.update_baseline and not complete:
        print("--update-baseline records every cell: run it without --cases / --sides", file=sys.stderr)
        return 2
    work = args.keep or Path(tempfile.mkdtemp(prefix="cics_crucible_"))
    results = measure(crucible, set(args.cases) if args.cases else None, set(args.sides), work.resolve(), args.offline)
    n = Counter(c["status"] for c in results["cells"].values())
    print(f"CICS crucible: {n['pass']} pass, {n['fail']} fail, {n['unsupported']} unsupported "
          f"({len(results['cells'])} cells)")  # fmt: skip
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "results.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
        (args.out / "report.md").write_text(report_md(results), encoding="utf-8")
    if args.update_baseline:
        write_baseline(results)
        REPORT.write_text(report_md(results), encoding="utf-8")
        print(f"baseline: {len(baseline_of(results)['cells'])} cells ledgered; report: {REPORT.relative_to(REPO_ROOT)}")
        return 0
    if args.ci:
        errors, notes = ratchet(results, read_baseline(), complete)
        for line in notes:
            print(f"note: {line}")
        for line in errors:
            print(line)
        if errors:
            print(f"\n{len(errors)} ratchet error(s). If intended, run with --update-baseline and commit "
                  "tests/cics_crucible/baseline.json and docs/language_status/cics_crucible.md.")  # fmt: skip
        return 1 if errors else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
