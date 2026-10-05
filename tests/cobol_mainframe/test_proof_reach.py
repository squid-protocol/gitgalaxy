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
        report = R.analyse([_port_dir(p["case"], p["program"])])
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
    assert "case_gap" not in verdicts
    # 37 when #4255 counted them. The 8 in hc-abend-link and hc-perform-range left with their ports' changes (their
    # handlers now run, #4325). #4342 took 14 more with the code they sat in: COMEN01C's 9 and COACTVWC's 1 were in
    # data-driven dispatchers no proof called, which runTask now XCTLs through; CSUTLDTC's 4 were in executeCsutldtc,
    # which is gone. The last 15 sat in the crucible ports' old facades, which #4343 regenerated
    # (tests/tools/port_surface.py) and now proves through the java-facade side. Every crucible port then changed, and
    # its recorded mutation run judged other code: all 17 were stale until re-run.
    #
    # The re-run (13 of the 17: every crucible port but the four PC* ones, which #4427 is changing and which are
    # re-run after it merges; seed 0, 24 mutants each, cics-crucible v0.2.0) leaves 7 flagged survivors:
    #   3 unreachable: dead helpers no code calls (CASUB writeqTsCatraceL22, HCQREAD writeqTsHcworkL37 and
    #     readqTsHcworkL57), the kind #4255 counted;
    #   4 harness_gap: a mutant inside a facade body (CASUB handleLink, CAXB / GTSTART / GTWORK handleTransaction).
    #     mutation_crucible.py proves mutants on the java-ported side only (`--sides java-ported`), which enters by
    #     runTask; the java-facade side is the one that runs these bodies, and it kills all four (checked by hand:
    #     DRIVER-ERROR, "a facade asked the region for ..."). They are the mutation runner's gap, not a case gap; they
    #     stay in the score's denominator and are pinned here until mutation_crucible.py runs both sides.
    #   0 case_gap: a new input cannot reach code the proof cannot run.
    crucible = {(p["case"], p["program"]) for p in json.loads(SCORES.read_text(encoding="utf-8"))["ports"]
                if p["case"].startswith("crucible:")}  # fmt: skip
    stale = {prog for c, prog in crucible if not _mutated_port_is_current(c, prog)}
    # only the ports not yet re-run are stale: their survivors are skipped until the next run judges them again
    assert crucible and stale == {"PCCONF", "PCWIZ", "PCMENU", "PCDETL"}
    assert len(flagged) == 7 and verdicts.count("unreachable") == 3
    assert sorted((prog, s["id"]) for prog, s in flagged if s["verdict"] == "harness_gap") == [
        ("CASUB", "bff70321ae"),
        ("CAXB", "3ff94f8814"),
        ("GTSTART", "3bd8d9e93f"),
        ("GTWORK", "ddb532b76e"),
    ]
    assert not {prog for prog, _ in flagged} & {"COACTVWC", "COMEN01C", "CSUTLDTC"}


def test_the_re_run_crucible_ports_keep_their_measured_floor():
    """The 13 crucible ports re-run after #4343 (seed 0, 24 mutants each): exact counts, so a regeneration that moves
    a port's mutants shows up as a stale record here, not as a silent change. Killed / survived per port, and the
    estate's harness gaps (the four facade mutants the java-ported-only mutation runner cannot kill)."""
    expected = {
        "CALINK": (19, 3), "CASUB": (14, 10), "CAXA": (17, 4), "CAXB": (14, 9), "GTSTART": (14, 8),
        "GTWORK": (18, 3), "GTSHOW": (19, 5), "GTTERM": (13, 8), "HCMAIN": (10, 13), "HCSUB": (18, 6),
        "HCQREAD": (10, 11), "HXATTR": (21, 2), "HXEXT": (14, 8),
    }  # fmt: skip
    ports = {p["program"]: p for p in json.loads(SCORES.read_text(encoding="utf-8"))["ports"]}
    for prog, (killed, survived) in expected.items():
        t = ports[prog]["total"]
        assert (t["killed"], t["survived"]) == (killed, survived), prog
        assert t["untriaged"] == 0 and _mutated_port_is_current(ports[prog]["case"], prog), prog
    assert sum(ports[p]["total"]["harness_gap"] for p in expected) == 4
    assert sum(k for k, _ in expected.values()) == 201 and sum(s for _, s in expected.values()) == 90


@pytest.mark.parametrize("case,program", sorted(FACADES))
def test_the_facades_the_crucible_enters_by_are_reached(case, program):
    report = R.analyse([_port_dir(case, program)], roots=(*R.PROOF_ROOTS, *FACADES[(case, program)]))
    (cls,) = report
    unproven = {m["method"] for m in report[cls]["unproven"]}
    assert not FACADES[(case, program)] & unproven and "runTask" not in unproven
