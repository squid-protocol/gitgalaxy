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


# The examples #4255 names, and the port each sits in.
NAMED = {
    ("carddemo-acctview", "COACTVWC"): {"dispatchCdemoToProgramL349"},
    ("carddemo-dateutil", "CSUTLDTC"): {"executeCsutldtc"},
    ("ca-link-lengths", "CASUB"): {"executeCasub", "handleLink", "writeqTsCatraceL22"},
    ("hc-abend-link", "HCMAIN"): {"executeHcmain", "bridgeHcsub"},
    ("hc-abend-link", "HCSUB"): {"readqTsHcnoneL37"},
    ("gt-start-retrieve", "GTWORK"): {"executeGtwork"},
}
# Named by #4255 too, and run by the proof since: runTask takes each handled condition / abend through the handler
# the port defines for it (the evidence records' ported_unproven methods, #4316 follow-up).
NOW_REACHED = {
    ("hc-abend-link", "HCMAIN"): {"onAbendL26", "onConditionQiderrL25"},
    ("hc-abend-link", "HCSUB"): {"onAbendL32"},
    ("hc-perform-range", "HCQREAD"): {"onConditionQiderrL25", "onConditionItemerrL25", "onConditionErrorL25",
                                      "onConditionItemerrL56", "current"},
}


@pytest.mark.parametrize("case,program", sorted(NAMED))
def test_the_committed_ports_keep_the_entry_points_the_issue_names(case, program):
    report = R.analyse([_port_dir(case, program)])
    (cls,) = report
    unproven = {m["method"] for m in report[cls]["unproven"]}
    assert NAMED[(case, program)] <= unproven
    assert "runTask" not in unproven and "handleCall" not in unproven


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
    assert "case_gap" not in verdicts and "harness_gap" not in verdicts
    # 37 when #4255 counted them; the 8 in hc-abend-link and hc-perform-range left with their ports' changes (their
    # handlers now run), until the next mutation run judges those ports again
    assert verdicts.count("unreachable") >= 29
