"""crucible_case (new, check-hand-derived) and crucible_events (the hand-traced log constructors)."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crucible_case as ccase
import crucible_events as ev


def _crucible() -> Path | None:
    p = os.environ.get("CICS_CRUCIBLE_PATH")
    return Path(p) if p and (Path(p) / "schema" / "expected.schema.json").is_file() else None


# ---- events -----------------------------------------------------------------------------------------------------
def test_event_checks_its_keys():
    with pytest.raises(ValueError, match="missing"):
        ev.event("WRITEQ-TS", "P", queue="Q", data=ev.text_area("X", 1), resp="NORMAL")
    with pytest.raises(ValueError, match="unknown"):
        ev.event("CANCEL", "P", reqid="R", resp="NORMAL", item=1)
    with pytest.raises(ValueError, match="unknown event"):
        ev.event("ASSIGN", "P")  # SPEC 6.2: ASSIGN is not an event


def test_start_spells_from_and_orders_keys():
    e = ev.start("GTX", "GT32", "2026-03-02T10:00:10", from_=ev.text_area("ORDER", 10), interval="000010")
    assert list(e) == ["event", "program", "transid", "termid", "from", "protect", "resp", "expires", "interval"]
    assert e["from"] == {"length": 10, "text": "ORDER"} and e["protect"] is False


def test_values_and_helpers():
    assert ev.text_area("AB   ", 5) == {"length": 5, "text": "AB"}
    with pytest.raises(ValueError):
        ev.text_area("TOO LONG", 3)
    assert ev.hex_area("c1c2", 2) == {"length": 2, "hex": "C1C2"}
    with pytest.raises(ValueError):
        ev.hex_area("C1C", 2)
    assert ev.Clock("2026-03-02T10:00:00").at(75) == "2026-03-02T10:01:15"
    assert ev.abend_for("P", "INVREQ") == {
        "event": "ABEND",
        "program": "P",
        "abcode": "AEIP",
        "cause": "condition",
        "outcome": "terminated",
        "condition": "INVREQ",
    }
    assert ev.return_("P") == {"event": "RETURN", "program": "P", "level": 1, "transid": None, "commarea": None}
    assert ev.return_("P", level=2, caller_commarea=None)["level"] == 2


def test_expected_and_write_case(tmp_path):
    t = ev.task(
        1, "GT31", "GTX", "2026-03-02T10:00:00", ev.terminal(0), [ev.return_("GTX")], termid="T001", eibaid="ENTER"
    )
    with pytest.raises(ValueError, match="seq"):
        ev.expected("c", "s", [dict(t, seq=2)])
    log = ev.expected("c", "s", [t], final_ts={"Q": ["A"]})
    case = {"format": ev.FORMAT_CASE, "scenarios": [{"id": "s"}]}
    with pytest.raises(ValueError, match="one expected log per scenario"):
        ev.write_case(tmp_path, case, {"s": log, "t": log})
    written = ev.write_case(tmp_path, case, {"s": log})
    assert [p.name for p in written] == ["case.json", "s.json"]
    assert json.loads((tmp_path / "expected" / "s.json").read_text())["final"] == {"ts_queues": {"Q": ["A"]}}


def test_events_table_matches_the_crucible_schema():
    crucible = _crucible()
    if crucible is None:
        pytest.skip("no cics-crucible checkout (CICS_CRUCIBLE_PATH)")
    schema = json.loads((crucible / "schema" / "expected.schema.json").read_text())
    table = {}
    for alt in schema["$defs"]["event"]["oneOf"]:
        props, req = alt["properties"], alt["required"]
        table[props["event"]["const"]] = (
            {k for k in req if k not in ("event", "program")},
            {k for k in props if k not in req and k != "note"},
        )
    assert table == {k: (set(r), set(o)) for k, (r, o) in ev.EVENTS.items()}


def test_every_committed_event_round_trips():
    crucible = _crucible()
    if crucible is None:
        pytest.skip("no cics-crucible checkout (CICS_CRUCIBLE_PATH)")
    n = 0
    for log in crucible.glob("cases/*/*/expected/*.json"):
        for task in json.loads(log.read_text())["tasks"]:
            for e in task["events"]:
                keys = {("from_" if k == "from" else k): v for k, v in e.items() if k not in ("event", "program")}
                assert ev.event(e["event"], e["program"], **keys) == e, log
                n += 1
    assert n > 100


# ---- new --------------------------------------------------------------------------------------------------------
def test_new_scaffolds_a_case(tmp_path):
    crucible = tmp_path / "cc"
    crucible.mkdir()
    (crucible / "SPEC.md").write_text("spec")
    gen = tmp_path / "scratch" / "gen.py"
    assert ccase.main(["new", "ghost-tasks/gt-demo", "--programs", "GTDEMO,gtdem2", "--transids", "GT91,GT92",
                       "--crucible", str(crucible), "--gen", str(gen)]) == 0  # fmt: skip
    d = crucible / "cases" / "ghost-tasks" / "gt-demo"
    case = json.loads((d / "case.json").read_text())
    assert case["sources"]["cobol"] == ["src/GTDEMO.cbl", "src/GTDEM2.cbl"]
    assert case["sources"]["csd"] == ["csd/gt-demo.csd"] and case["scenarios"][0]["steps"][0]["text"] == "GT91"
    csd = (d / "csd" / "gt-demo.csd").read_text()
    assert "DEFINE TRANSACTION(GT92) GROUP(CRUCGT) PROGRAM(GTDEM2)" in csd and "ATI(YES) TTI(YES)" in csd
    prog = (d / "src" / "GTDEMO.cbl").read_text()
    assert "PROGRAM-ID. GTDEMO." in prog and all(len(ln) <= 72 for ln in prog.splitlines())
    notes = (d / "NOTES.md").read_text()
    assert all(f"## {s}" in notes for s in ccase.NOTES_SECTIONS) and re.search(r"https://(?:www\.)?ibm\.com/", notes)
    assert (d / "expected").is_dir() and (d / "copy").is_dir()
    assert ccase.hand_derived_problems(gen.read_text()) == []
    subprocess.run([sys.executable, str(gen), str(d)], check=True)  # noqa: S603
    log = json.loads((d / "expected" / "happy-path.json").read_text())
    assert log["format"] == ev.FORMAT_EXPECTED and log["tasks"][0]["events"][-1]["event"] == "RETURN"
    with pytest.raises(SystemExit, match="taken"):
        ccase.main(["new", "hex-attributes/gt-demo", "--programs", "X", "--crucible", str(crucible)])


def test_new_refuses_bad_names_and_a_gen_inside_the_crucible(tmp_path):
    crucible = tmp_path / "cc"
    crucible.mkdir()
    (crucible / "SPEC.md").write_text("spec")
    with pytest.raises(SystemExit, match="trap"):
        ccase.main(["new", "no-such-trap/x", "--programs", "A", "--crucible", str(crucible)])
    with pytest.raises(SystemExit, match="bad program"):
        ccase.main(["new", "ghost-tasks/x", "--programs", "TOOLONGNAME", "--crucible", str(crucible)])
    with pytest.raises(SystemExit, match="scratch"):
        ccase.main(["new", "ghost-tasks/x", "--programs", "A", "--crucible", str(crucible),
                    "--gen", str(crucible / "gen.py")])  # fmt: skip


def test_scaffold_validates_in_a_real_crucible(tmp_path):
    crucible = _crucible()
    if crucible is None:
        pytest.skip("no cics-crucible checkout (CICS_CRUCIBLE_PATH)")
    root = tmp_path / "cc"
    for sub in ("tools", "schema"):
        shutil.copytree(crucible / sub, root / sub)
    (root / "SPEC.md").write_text((crucible / "SPEC.md").read_text())
    gen = tmp_path / "gen.py"
    assert ccase.main(["new", "ghost-tasks/gt-demo", "--programs", "GTDEMO", "--crucible", str(root),
                       "--gen", str(gen)]) == 0  # fmt: skip
    subprocess.run([sys.executable, str(gen), str(root / "cases/ghost-tasks/gt-demo")], check=True)  # noqa: S603
    res = subprocess.run([sys.executable, "-I", str(root / "tools" / "validate.py")], cwd=root,  # noqa: S603
                         capture_output=True, text=True, check=False)  # fmt: skip
    assert res.returncode == 0, res.stdout + res.stderr


# ---- check-hand-derived -----------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("src", "why"),
    [
        ("import gitgalaxy.tools.cobol_to_java.det.program as P", "imports gitgalaxy"),
        ("from equivalence_cics import run", "imports equivalence_cics"),
        ("import subprocess", "can run an implementation"),
        ("import os\nos.system('java X')", "calls os.system"),
        ("import os\nos.execv('/bin/x', [])", "calls os.execv"),
        ("exec(open('x').read())", "calls exec"),
        ("from . import helper", "relative import"),
        ("import importlib", "can run an implementation"),
    ],
)
def test_check_hand_derived_flags(src, why):
    problems = ccase.hand_derived_problems(src, "s.py")
    assert problems and why in problems[0]


def test_check_hand_derived_accepts_a_formatter(tmp_path, capsys):
    ok = tmp_path / "gen.py"
    ok.write_text("import json, sys\nfrom pathlib import Path\nimport crucible_events as ev\nprint(json.dumps({}))\n")
    bad = tmp_path / "bad.py"
    bad.write_text("import cics_crucible\n")
    assert ccase.main(["check-hand-derived", str(ok)]) == 0
    assert ccase.main(["check-hand-derived", str(ok), str(bad)]) == 1
    assert "bad.py:1: imports cics_crucible" in capsys.readouterr().out
