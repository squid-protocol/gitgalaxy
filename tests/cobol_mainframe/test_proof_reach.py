"""#4255: which of a port's methods its proof can run.

The equivalence harness and the CICS crucible drive a port only through runTask / handleCall / runBatch; the mutation
scores of #4047 found survivors in methods the models kept beside them (executeX, handleLink, onAbendLnn, dispatchXLnn,
generated TS helpers). proof_reach finds those methods from the Java alone; the porting tickets now ask for the proof
entry point only, and port_runner prove logs what the proof cannot reach.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_java import proof_reach as R

REPO = Path(__file__).resolve().parents[2]
SCORES = REPO / "docs" / "language_status" / "mutation_scores.json"

SERVICE = """package p.service;

public class DemoService {

    private static final Logger log = LoggerFactory.getLogger(DemoService.class);
    private static final Map<String, Integer> WIDTHS = widths();   // runs whenever the class is used
    private final OtherService otherService;

    public DemoService(OtherService otherService) {
        this.otherService = otherService;
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public String handleTransaction(String transid, String request) {
        log.info("Demo: handleTransaction");
        return null;
    }

    public void runTask(CicsTask task) {
        String s = "not a call: unused() { }";   // a string is not code
        // nor is a comment: unused();
        helper(task);
        list.sort(Comparator.comparing(this::keyOf));
        otherService.serve(1);
        new Runnable() {
            @Override
            public void run() { inner(); }
        }.run();
    }

    private void helper(CicsTask task) {
        if (task.hasCommarea()) {
            task.sendText("x");
        }
    }

    private String keyOf(String x) { return x; }

    private void inner() { }

    private static Map<String, Integer> widths() { return Map.of(); }

    /** Another program LINKed / XCTLed to this one. */
    public String handleLink(String request) {
        log.info("Demo: handleLink");
        return unused(request);
    }

    private String unused(String r) {
        return r.trim();
    }

    protected int writeqTsDemoL22(String record) {
        return tempStorage.writeItem("DEMO", record);
    }

    static final class Cmp implements Comparator<String> {
        @Override
        public int compare(String a, String b) { return a.compareTo(b); }
    }
}
"""

OTHER = """package p.service;

public class OtherService {
    public void runTask(CicsTask task) { }

    public void serve(int n) { work(n); }

    private void work(int n) { }

    public void neverServed() { work(2); }
}
"""


def _report(tmp_path: Path, files: dict[str, str], generated: dict[str, str] | None = None) -> dict:
    for name, text in files.items():
        (tmp_path / "port" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "port" / name).write_text(text, encoding="utf-8")
    gen = []
    for name, text in (generated or {}).items():
        (tmp_path / "gen" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "gen" / name).write_text(text, encoding="utf-8")
        gen.append(tmp_path / "gen" / name)
    return R.analyse([tmp_path / "port"], generated=gen)


def test_the_proof_reaches_runTask_and_what_it_calls_only(tmp_path):
    r = _report(tmp_path, {"DemoService.java": SERVICE, "OtherService.java": OTHER})
    demo = r["DemoService"]
    assert demo["roots"] == ["runTask"]
    unproven = {m["method"]: m for m in demo["unproven"]}
    # handleLink's own body and the helper only it calls; the stub handler; the TS helper nothing calls
    assert set(unproven) == {"handleTransaction", "handleLink", "unused", "writeqTsDemoL22"}
    assert unproven["handleTransaction"]["stub"] and not unproven["handleLink"]["stub"]
    assert unproven["handleLink"]["line"] == 44 and unproven["handleLink"]["visibility"] == "public"
    assert demo["ported_unproven"] == ["handleLink", "unused", "writeqTsDemoL22"]
    # a call through a field typed as another analysed service reaches that service's method
    assert [m["method"] for m in r["OtherService"]["unproven"]] == ["neverServed"]


def test_methods_unchanged_from_the_generated_service_are_not_counted_as_ported(tmp_path):
    generated = SERVICE.replace("return unused(request);", "return null;")
    r = _report(tmp_path, {"DemoService.java": SERVICE}, {"DemoService.java": generated})
    unproven = {m["method"]: m for m in r["DemoService"]["unproven"]}
    assert unproven["writeqTsDemoL22"]["generated"] and not unproven["handleLink"]["generated"]
    # unused() is the generated file's too: only handleLink's changed body is the port's own
    assert r["DemoService"]["ported_unproven"] == ["handleLink"]
    assert "left as generated: handleTransaction, unused, writeqTsDemoL22" in R.summary(r)


def test_a_class_without_a_proof_entry_point_is_not_reported(tmp_path):
    assert _report(tmp_path, {"Dto.java": "public class Dto { public int x() { return 1; } }"}) == {}


def test_the_cli_exits_1_on_ported_unproven_methods_when_strict(tmp_path, capsys):
    (tmp_path / "DemoService.java").write_text(SERVICE, encoding="utf-8")
    assert R.main([str(tmp_path)]) == 0
    assert "proven through runTask only" in capsys.readouterr().out
    assert R.main([str(tmp_path), "--strict"]) == 1
    capsys.readouterr()
    assert R.main([str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["DemoService"]["roots"] == ["runTask"]


def _port_dir(case: str, program: str) -> Path:
    case = case.split(":")[-1]
    eq = REPO / "tests" / "equivalence" / case / "port"
    return eq if eq.is_dir() else REPO / "tests" / "cics_crucible" / "ports" / case / program / "overlay"


# The examples #4255 names that runTask still never runs, and the port each sits in. #4343: CASUB's handleLink is the
# deployed entry point the facade proof enters by (FACADES below), not runTask.
NAMED = {
    ("ca-link-lengths", "CASUB"): {"handleLink", "writeqTsCatraceL22"},
    ("hc-abend-link", "HCSUB"): {"readqTsHcnoneL37"},
}
# #4343: the facades the crucible's java-facade side enters each port by (the evidence records' entry_points): with
# them as roots, the deployed entry point is reached, and so is the runTask it runs.
FACADES = {
    ("ca-link-lengths", "CASUB"): {"handleLink"},
    ("ca-link-lengths", "CALINK"): {"handleTransaction"},
    ("hx-extended-cursor", "HXEXT"): {"handleTransaction"},
}
# Named by #4255 too, and run by the proof since: runTask takes each handled condition / abend through the handler
# the port defines for it (the evidence records' ported_unproven methods, #4316 follow-up), and (#4342) its
# data-driven XCTL through the dispatcher the generator writes for it.
NOW_REACHED = {
    ("carddemo-acctview", "COACTVWC"): {"dispatchCdemoToProgramL349"},
    ("hc-abend-link", "HCMAIN"): {"onAbendL26", "onConditionQiderrL25"},
    ("hc-abend-link", "HCSUB"): {"onAbendL32"},
    ("hc-perform-range", "HCQREAD"): {
        "onConditionQiderrL25",
        "onConditionItemerrL25",
        "onConditionErrorL25",
        "onConditionItemerrL56",
        "current",
    },
}
# #4342: methods with no COBOL behaviour behind them, which the generator no longer writes: gone from the ports. A batch
# executeX of a CICS / CALLed program, the handler of a HANDLE ABEND CANCEL, and a screen's render / submit that no
# controller calls (ui.flavour none).
REMOVED = {
    ("carddemo-dateutil", "CSUTLDTC"): {"executeCsutldtc"},
    ("carddemo-cardview", "COCRDSLC"): {"executeCocrdslc", "onAbendL871", "renderCcrdsla", "submitCcrdsla"},
    ("carddemo-acctview", "COACTVWC"): {"executeCoactvwc", "onAbendL930", "renderCactvwa", "submitCactvwa"},
    # #4343: the crucible ports' facades regenerated (tests/tools/port_surface.py): the executeX #4255 named, and the
    # helpers only they ran; render / submit that rebuilt screens outside runTask
    ("ca-link-lengths", "CASUB"): {"executeCasub"},
    ("hc-abend-link", "HCMAIN"): {"executeHcmain", "bridgeHcsub", "seed"},
    ("gt-start-retrieve", "GTWORK"): {"executeGtwork"},
    ("hx-attr-bytes", "HXATTR"): {"executeHxattr", "renderHxm1", "submitHxm1"},
    ("hx-extended-cursor", "HXEXT"): {"executeHxext", "submitHxm2"},
    ("pc-wizard", "PCWIZ"): {"executePcwiz", "renderPcm1", "submitPcm1", "renderPcm2", "returnedCommarea"},
}


@pytest.mark.parametrize("case,program", sorted(NAMED))
def test_the_committed_ports_keep_the_entry_points_the_issue_names(case, program):
    report = R.analyse([_port_dir(case, program)])
    (cls,) = report
    unproven = {m["method"] for m in report[cls]["unproven"]}
    assert NAMED[(case, program)] <= unproven
    assert "runTask" not in unproven and "handleCall" not in unproven


@pytest.mark.parametrize("case,program", sorted(REMOVED))
def test_the_ports_have_no_method_the_generator_no_longer_writes(case, program):
    (unit,) = [R.parse_java(p) for p in R.java_files([_port_dir(case, program)])]
    assert not REMOVED[(case, program)] & {m.name for m in unit.methods}


@pytest.mark.parametrize("case,program", sorted(NOW_REACHED))
def test_the_ports_handlers_are_run_by_the_proof(case, program):
    report = R.analyse([_port_dir(case, program)])
    (cls,) = report
    assert not NOW_REACHED[(case, program)] & {m["method"] for m in report[cls]["unproven"]}


def _mutated_port_is_current(case: str, program: str) -> bool:
    """Whether the port is still the one #4047's mutation run judged: the evidence record's `mutation.inputs.port`
    (the port digest at the run's commit) against the port its proof ran on (`inputs.port`). A survivor's line and its
    triage describe the mutated code; once the port changed, the next mutation run triages it again."""
    case = case.split(":")[-1]
    eq = REPO / "tests" / "equivalence" / case / "evidence.json"
    rec_path = eq if eq.is_file() else REPO / "tests" / "cics_crucible" / "ports" / case / program / "evidence.json"
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    judged = ((rec.get("mutation") or {}).get("inputs") or {}).get("port", {}).get("sha256")
    return judged is None or judged == rec["inputs"]["port"]["sha256"]


def _flagged_survivors() -> list[tuple[str, dict]]:
    out = []
    for p in json.loads(SCORES.read_text(encoding="utf-8"))["ports"]:
        if not _mutated_port_is_current(p["case"], p["program"]):
            continue
        port = _port_dir(p["case"], p["program"])
        if not port.is_dir():  # a generated port (port_from) is written at proof time, none is committed
            continue
        report = R.analyse([port])
        spans = [(Path(r["files"][0]).name, m) for r in report.values() for m in r["unproven"]]
        for s in p["survivors"]:
            file, line = s["at"].rsplit(":", 1)
            if any(Path(file).name == f and m["line"] <= int(line) <= m["end"] for f, m in spans):
                out.append((p["program"], s))
    return out


def test_every_survivor_in_code_no_proof_runs_was_triaged_as_out_of_the_proofs_reach():
    """The check agrees with #4047's hand triage: a survivor in a method the proof cannot reach was never a case gap
    (a new input cannot reach it), and the check finds the entry-point survivors #4255 counts."""
    flagged = _flagged_survivors()
    verdicts = [s["verdict"] for _, s in flagged]
    assert "case_gap" not in verdicts and "harness_gap" not in verdicts
    # 37 when #4255 counted them. The 8 in hc-abend-link and hc-perform-range left with their ports' changes (their
    # handlers now run, #4325). #4342 took 14 more with the code they sat in: COMEN01C's 9 and COACTVWC's 1 were in
    # data-driven dispatchers no proof called, which runTask now XCTLs through; CSUTLDTC's 4 were in executeCsutldtc,
    # which is gone. The last 15 sat in the crucible ports' old facades, which #4343 regenerated
    # (tests/tools/port_surface.py) and now proves through the java-facade side. Every crucible port then changed, and
    # its recorded mutation run judged other code: all 17 were stale until re-run.
    #
    # The re-run (13 of the 17: every crucible port but the four PC* ones, which #4427 changed and #4443 re-ran
    # afterwards, below; seed 0, 24 mutants each, cics-crucible v0.2.0, mutants proven on the java-ported AND
    # java-facade sides) leaves 3 flagged survivors, all unreachable: dead helpers no code calls (CASUB
    # writeqTsCatraceL22, HCQREAD writeqTsHcworkL37 and readqTsHcworkL57), the kind #4255 counted. No case_gap and no
    # harness_gap: a mutant inside a facade body survived on the java-ported side alone (4 of them), and the java-facade
    # side, which runs those bodies, now kills them.
    crucible = {(p["case"], p["program"]) for p in json.loads(SCORES.read_text(encoding="utf-8"))["ports"]
                if p["case"].startswith("crucible:")}  # fmt: skip
    stale = {prog for c, prog in crucible if not _mutated_port_is_current(c, prog)}
    # only the ports not yet re-run are stale (the four PCIMM*; the PC* four were re-run in #4443): their survivors are skipped until the next run judges them again
    assert crucible and stale == {"PCIMMA", "PCIMMB", "PCIMML", "PCIMMS"}
    # #4870 re-ran the same 13 after the byte-carrying handleTransaction overload joined every region facade (seed 0, 24
    # mutants each; the added code moved the sample): 7 flagged survivors, all unreachable -- 4 in that overload
    # (CALINK, CAXA x2, GTSTART: the crucible entered by handleTransaction(String, T) only), HCQREAD's overload name
    # literal, and the dead helpers CASUB writeqTsXatrace and HCQREAD readqTsHcwork.
    # #4965 made the crucible's java-facade side run every scenario through that overload too (the previous RETURN's
    # bytes in, lastAnswerBytes() out, compared with the instrument's bytes), and re-ran those 4 ports: the overload
    # literal (HCQREAD) and CAXA's accessor mutant died, 5 flagged survivors remain. The dead helpers stay unreachable;
    # the 3 `lastAnswerBytes = task.returnedBytes()` deletions (CALINK, CAXA, GTSTART) are re-triaged equivalent, not
    # unreachable: their programs RETURN TRANSID with no COMMAREA, so the bytes they answer are null either way.
    # #4048 judged the PCIMM* crucible ports (on their own service code, not the shared cobolrt runtime), CBSA INQACC /
    # UPDACC and GenApp LGAPVS01 / LGICDB01 / LGUPDB01: 9 more flagged survivors, all unreachable. PCIMMA / PCIMML /
    # PCIMMS mutated runProgram and the byte-carrying handleTransaction overloads (the crucible does not enter by
    # them), LGAPVS01 the writeKsdspoly guard; LGICDB01 / LGUPDB01 sit in methods proof_reach lists as unproven.
    # #4047 scored six CardDemo CICS ports (signon, tranview, userlist, useradd, userdel, adminmenu): 8 more flagged
    # survivors, all unreachable: the program name literal in the facade's region.run / region.linked, which the proof
    # does not call (the proof drives runTask), as in COMEN01C's.
    # The PCIMM* ports changed with the ARITH(EXTEND) stop (#4706) and were re-proved, so their recorded mutation run
    # judges older code and their 3 flagged survivors are skipped until the next run: 19 flagged, 16 unreachable.
    # #5053 resurfaced the 14 CardDemo / CBSA / GenApp ports with the handleLink byte overload and lastLinkBytes()
    # (a new facade body their recorded mutation run never judged), so their 14 flagged survivors are skipped too until
    # the next run: the 5 left are the crucible ports' (3 equivalent, 2 unreachable dead helpers).
    # #4443 re-ran PCCONF, PCWIZ, PCMENU and PCDETL (seed 0, 24 mutants each) with their new strengthened scenarios:
    # one more flagged survivor, none a case gap: PCCONF's `d.getPcBack()` null-arm literal, in code the proof does not
    # run (unreachable).
    # #4047 then scored seven more CardDemo CICS ports (billpay, cardlist, cardview, report, tranadd, tranlist, userupd):
    # 12 more flagged survivors, all unreachable: the facade's byte-carrying handleLink overload, lastLinkBytes() and the
    # program-name literal in region.run / region.linked, which no proof calls.
    # #4049 re-recorded the four menu-family ports (adminmenu, useradd, userdel, tranview; seed 0, 100 mutants each) after
    # #5387's scenarios and the port regeneration (mutants moved, so their stale-record skip ended): 19 more flagged
    # survivors, all unreachable: the facade's lastLinkBytes() and the program-name literal in region.run / region.linked.
    # #4047 re-ran the three GenApp ports (LGAPVS01, LGICDB01, LGUPDB01; seed 0, 150 mutants each), ending their #5053
    # stale-record skip: 21 more flagged survivors, all unreachable: the facade entry (region.linked / run /
    # lastLinkBytes), LGAPVS01's writeKsdspoly helper and the EIBCALEN = 0 branch (the case always links a COMMAREA).
    # #4054 then adopted LGSTSQ's port (it refuses a WRITEQ LENGTH past WRITE-MSG, X6) and re-proved LGAPVS01 against it:
    # LGAPVS01's committed mutation score is now stale on its port, so its 8 flagged survivors are skipped again
    # (#5053) until it is re-run (seed 0, 150): 58 -> 50. LGSTSQ's own first mutation run adds 8 (the facade entry
    # handleLink / lastLinkBytes and the two dead EXEC CICS helpers), all unreachable: 50 -> 58.
    # #4054 then adopted LGAPDB01's port (model-written, proven on attempt 1) and scored it (seed 0, 150 mutants): 5 more
    # flagged survivors, all unreachable: the facade's byte-carrying handleLink / lastLinkBytes() and the dead EXEC CICS
    # ABEND helpers no code calls. 58 -> 63.
    # #4054 then adopted LGUPVS01's port (proven on attempt 1), scored it (seed 0, 150) and re-ran LGAPVS01 on the LGSTSQ
    # port (ending its stale-record skip again): 13 more flagged survivors, all unreachable: the facade entry
    # (handleLink / lastLinkBytes), the EIBCALEN = 0 branch and the dead ABEND helpers. 63 -> 76.
    # #4047 then re-recorded the five LINKed-program ports in one JVM per proof: 15 more flagged survivors (INQACC's 8
    # among them, its stale-record skip ended), all in code no proof runs, so all unreachable. 76 -> 91.
    # #4506 then fixed CARDDEMO BILLPAY's store() modulus (digits + scale, found by the typed-BMS generated case): its
    # recorded mutation run judges the old port, so its 2 flagged survivors are skipped until it is re-run. 91 -> 89.
    # #4443 re-ran CARDDEMO COMEN01C and COACTVWC (seed 0, 150 mutants each; their records judged older ports, so their
    # survivors were skipped), ending the skip: 6 more flagged survivors, all unreachable: the facade's lastLinkBytes()
    # and the program-name literal in region.run / region.linked. 89 -> 95.
    # #4049 slice 2 re-recorded COUSR00C (the hand port, full enumeration of 510 mutants; its record judged an older port,
    # so its survivors were skipped): 14 more flagged survivors, all unreachable: the facade's handleLink / lastLinkBytes(),
    # the 2-argument handleTransaction, the program-name literal in region.run / region.linked, the lastAnswerBytes
    # assignment and the four browse helpers' repository-method literals. 95 -> 109.
    # #6072 re-ran COACTVWC on its hand port with the abend path (seed 0, 150 mutants): one fewer flagged survivor than
    # #4443's 6 (the facade's lastLinkBytes(); the program-name literal in region.run / region.linked), all unreachable. 109 -> 108.
    # #4049 re-ran UPDACC on its hand port (all 139 mutants, seed 0; its record judged an older port, so its survivors
    # were skipped): 6 more flagged survivors, all unreachable: the facade's two-argument handleLink / lastLinkBytes()
    # and the program-name literals in region.run / region.linked. 108 -> 114.
    # #4049 (CSUTLDTC Julian) changed the dateutil port that CORPT00C and COTRN02C CALL, and re-proved both: their
    # recorded mutation runs judged the older callee, so their 2 flagged survivors (both unreachable) are skipped until
    # the next run. 114 -> 112.
    # #4049 re-ran both (CORPT00C 59/87 caught, COTRN02C 70/91, 100 mutants each, seed 0): the 2 return. 112 -> 114.
    # #5252 re-proved the LGSTSQ, LGAPVS01 and LGUPVS01 ports (X6 padding, the WRITE-ERROR-MESSAGE fixes): their committed
    # mutation runs, and the LGAPDB01 / LGUPDB01 ones whose proofs LINK them, judge the older code, so their 40 flagged
    # survivors (all unreachable) are skipped until those five are re-run. 114 -> 74.
    assert len(flagged) == 74 and verdicts.count("unreachable") == 71 and verdicts.count("equivalent") == 3
    assert not {prog for prog, _ in flagged} & {"CSUTLDTC"}
    assert {prog for prog, _ in flagged} & {"COACTVWC", "COMEN01C"} == {"COACTVWC", "COMEN01C"}


def test_the_re_run_crucible_ports_keep_their_measured_floor():
    """The 13 crucible ports re-run after #4343 (seed 0, 24 mutants each): exact counts, so a regeneration that moves
    a port's mutants shows up as a stale record here, not as a silent change. Killed / survived per port, and the
    harness gaps (none: the facade bodies are proven on the java-facade side too)."""
    expected = {
        "CALINK": (15, 7),
        "CASUB": (16, 8),
        "CAXA": (16, 5),
        "CAXB": (20, 3),
        "GTSTART": (19, 3),
        "GTWORK": (20, 1),
        "GTSHOW": (17, 6),
        "GTTERM": (17, 4),
        "HCMAIN": (14, 9),
        "HCSUB": (18, 6),
        "HCQREAD": (14, 7),
        "HXATTR": (17, 5),
        "HXEXT": (20, 3),
    }  # fmt: skip  (#4870 re-ran after the byte-carrying facade overload, #4965 re-ran CALINK, CAXA, GTSTART, HCQREAD, #4443 re-ran all 13 with the strengthened scenarios, then CAXB's `visits-past-nine` and the three direct-entry scenarios: measured)
    ports = {p["program"]: p for p in json.loads(SCORES.read_text(encoding="utf-8"))["ports"]}
    for prog, (killed, survived) in expected.items():
        t = ports[prog]["total"]
        assert (t["killed"], t["survived"]) == (killed, survived), prog
        assert t["untriaged"] == 0 and _mutated_port_is_current(ports[prog]["case"], prog), prog
    assert sum(ports[p]["total"]["harness_gap"] for p in expected) == 0
    assert sum(k for k, _ in expected.values()) == 223 and sum(s for _, s in expected.values()) == 67


def test_the_pc_ports_re_run_in_4443_keep_their_measured_floor():
    """#4443 item 2: PCDETL, PCMENU (pc-aid-menu) and PCCONF, PCWIZ (pc-wizard), seed 0, 24 mutants each, against the
    strengthened scenarios (three new for pc-wizard, one for pc-aid-menu, expected logs derived from the COBOL). Killed /
    survived per port; every survivor is equivalent or unreachable (no case gap, no harness gap), so the adjusted score
    is 100%. PCCONF and PCWIZ each had one stillborn mutant (javac refused it)."""
    expected = {"PCDETL": (15, 9), "PCMENU": (16, 8), "PCCONF": (15, 8), "PCWIZ": (16, 7)}
    ports = {p["program"]: p for p in json.loads(SCORES.read_text(encoding="utf-8"))["ports"]}
    for prog, (killed, survived) in expected.items():
        t = ports[prog]["total"]
        assert (t["killed"], t["survived"]) == (killed, survived), prog
        assert t["case_gap"] == t["harness_gap"] == t["untriaged"] == 0, prog
        assert t["equivalent"] + t["unreachable"] == survived, prog
        assert _mutated_port_is_current(ports[prog]["case"], prog), prog


@pytest.mark.parametrize("case,program", sorted(FACADES))
def test_the_facades_the_crucible_enters_by_are_reached(case, program):
    report = R.analyse([_port_dir(case, program)], roots=(*R.PROOF_ROOTS, *FACADES[(case, program)]))
    (cls,) = report
    unproven = {m["method"] for m in report[cls]["unproven"]}
    assert not FACADES[(case, program)] & unproven and "runTask" not in unproven
