"""#5082: proof_reach must not count a det translator's helpers (runProgram, in_X / out_X, ...) as ported-unproven.

The det translator writes, beside the program's paragraphs, entry points a proof does not drive (runProgram, the
handleLink / handleTransaction facades), run-unit plumbing and the contract-DTO codecs. Their text is the translator's,
in every port; nothing a porter wrote is behind them, so a proof that runs the class through runTask / handleCall /
runBatch proves them. The proof is not loosened: only a method of a file marked as a det port, with one of these names,
is one; every other method of it, and every method of an unmarked file, still counts.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from gitgalaxy.core.aperture import DET_PORT_MARKER
from gitgalaxy.tools.cobol_to_java import proof_reach as R

REPO = Path(__file__).resolve().parents[2]
DET = REPO / "gitgalaxy" / "tools" / "cobol_to_java" / "det"
HEADER = f"{DET_PORT_MARKER} COBOL DEMO (DEMO.cbl), translated by rule, statement for statement\n"
CODECS = ["in_DemoDfhcommarea", "out_DemoDfhcommarea", "fill_DemoWsCa", "in_X", "out_PcimmlDfhcommarea"]
HELPERS = sorted(R.DET_HELPERS) + CODECS


def _port(extra: str = "", header: str = HEADER, helper: str = "runProgram") -> str:
    return (
        header
        + f"""package p.service;

public class DemoService {{
    public void runTask(CicsTask task) {{
        step(task);
    }}

    private void step(CicsTask task) {{
        task.sendText("x");
    }}

    public int {helper}() {{
        return other();
    }}

    private int other() {{ return 1 + 1; }}
{extra}}}
"""
    )


def _analyse(tmp_path: Path, text: str) -> dict:
    f = tmp_path / "DemoService.java"
    f.write_text(text, encoding="utf-8")
    return R.analyse([f])["DemoService"]


@pytest.mark.parametrize("helper", HELPERS)
def test_every_det_helper_is_proven_by_the_cells_that_reach_the_class(tmp_path, helper):
    r = _analyse(tmp_path, _port(helper=helper))
    # the helper and what only it calls are never run by runTask, and are not a porter's behaviour either
    assert {m["method"] for m in r["unproven"]} == {helper, "other"}
    assert "other" in r["ported_unproven"], "what a helper calls is not itself a helper"
    assert helper not in r["ported_unproven"]
    assert helper in r["det_helpers"]
    assert {m["method"]: m["det_helper"] for m in r["unproven"]}[helper] is True


@pytest.mark.parametrize("helper", HELPERS)
def test_the_same_method_in_a_file_without_the_marker_still_counts(tmp_path, helper):
    r = _analyse(tmp_path, _port(header="", helper=helper))
    assert helper in r["ported_unproven"] and helper not in r["det_helpers"]


@pytest.mark.parametrize(
    "name", ["executeDemo", "handleCommarea", "onAbendL12", "dispatchL3", "in_", "in_lower", "inX", "run2"]
)
def test_a_method_of_a_det_port_that_is_not_a_helper_still_counts(tmp_path, name):
    r = _analyse(tmp_path, _port(helper=name))
    assert name in r["ported_unproven"] and name not in r["det_helpers"]


def test_a_helper_does_not_make_what_it_calls_proven(tmp_path):
    # a method a porter added to a det port and called from runProgram stays unproven: nothing the proof runs calls it
    r = _analyse(
        tmp_path,
        _port(extra="    private void added() { int x = 1; }\n").replace("return other();", "added(); return other();"),
    )
    assert {"added", "other"} <= set(r["ported_unproven"]) and r["det_helpers"] == ["runProgram"]


def test_a_helper_the_proof_does_reach_is_not_unproven_at_all(tmp_path):
    r = _analyse(tmp_path, _port().replace("step(task);", "step(task); runProgram();"))
    assert "runProgram" not in {m["method"] for m in r["unproven"]} and r["det_helpers"] == []


def test_a_stub_stays_a_stub_and_a_left_as_generated_stays_generated(tmp_path):
    text = _port(helper="handleTransaction").replace("return other();", "return 0;")
    (tmp_path / "gen").mkdir()
    f = tmp_path / "DemoService.java"
    f.write_text(text, encoding="utf-8")
    assert next(m for m in R.analyse([f])["DemoService"]["unproven"] if m["method"] == "handleTransaction")["stub"]
    g = tmp_path / "gen" / "DemoService.java"
    g.write_text(text, encoding="utf-8")
    r = R.analyse([f], generated=[g])["DemoService"]
    assert "handleTransaction" not in r["det_helpers"] and "handleTransaction" not in r["ported_unproven"]


@pytest.mark.parametrize(
    ("text", "det"),
    [
        (HEADER + "class A {}\n", True),
        ("/* licence */\n" + HEADER + "class A {}\n", True),
        ("   " + HEADER + "class A {}\n", True),
        ("class A {}\n" + HEADER, False),  # after code
        ('class A { String s = "\\n' + HEADER.strip() + '"; }\n', False),  # in a string
        ('class A { String s = """\n' + HEADER + '"""; }\n', False),  # in a text block
        ("// see " + DET_PORT_MARKER + " in det/\nclass A {}\n", False),  # the marker is not the line's start
        ("class A {}\n", False),
        ("", False),
    ],
)
def test_only_a_marker_before_any_code_makes_a_det_port(text, det):
    assert R.is_det_port(text) is det


def test_a_constructor_named_like_a_helper_is_not_one(tmp_path):
    r = _analyse(tmp_path, _port(extra="    DemoService() { }\n"))
    assert "DemoService" not in r["det_helpers"]


def test_summary_names_the_helpers(tmp_path):
    f = tmp_path / "DemoService.java"
    f.write_text(_port(), encoding="utf-8")
    line = R.summary(R.analyse([f]))
    assert "det helper(s)" in line and "runProgram" in line and "other" in line


# ---- the list is the translator's ----------------------------------------------------------------------------------
def _emitted() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(DET.glob("*.py")))


@pytest.mark.parametrize("name", sorted(R.DET_HELPERS))
def test_every_listed_helper_is_something_det_emits(name):
    assert re.search(rf"\b{name}\b", _emitted()), f"det/ no longer emits {name}: drop it from DET_HELPERS"


def test_the_codec_names_are_what_det_emits():
    emitted = _emitted()
    for prefix in ("in", "out", "fill"):
        assert f"{prefix}_{{" in emitted or f"{prefix}_{{cls}}" in emitted or f"{prefix}_{{part.cls}}" in emitted, (
            prefix
        )
    assert all(R.is_det_helper_name(n) for n in CODECS)


def test_methods_det_reserves_for_itself_are_helpers_or_proof_entries():
    """METHODS_TAKEN is what a paragraph method may not shadow: each is either a proof root, a helper, or a member
    that is not a method of the port a proof could miss (fields, the clock, ...)."""
    from gitgalaxy.tools.cobol_to_java.det import gen

    methods = {
        "initialState", "perform", "run", "runTask", "runBatch", "runProgram", "handleCall", "handleTransaction",
        "handleLink", "store", "condition", "paragraph", "dd", "cx",
    }  # fmt: skip
    assert methods <= set(gen.METHODS_TAKEN)
    assert {m for m in methods if m not in R.PROOF_ROOTS} <= R.DET_HELPERS


def _det_ports() -> list[Path]:
    out = subprocess.run(
        ["git", "grep", "-l", DET_PORT_MARKER, "--", "*.java"],  # noqa: S607
        cwd=REPO, capture_output=True, text=True, check=False,
    ).stdout.split()  # fmt: skip
    return [REPO / p for p in out]


def test_every_committed_det_port_has_no_unproven_method_but_its_helpers():
    ports = _det_ports()
    assert len(ports) >= 10, "the committed det ports are missing"
    for f in ports:
        for cls, r in R.analyse([f]).items():
            assert r["ported_unproven"] == [], (f.name, cls, r["ported_unproven"])
