"""#6501: the graph-accuracy plan -- each changed file maps to the gates it can move, and no toolchain runs without a gate.

Both directions: a gate whose inputs changed is never skipped (shared adapters, core, the corpus list, an unknown
language_standards file all plan every gate), and a language with no gate installs nothing.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TOOLS))
import graph_accuracy_plan as gap  # noqa: E402

CORPUS = gap.corpus_languages()
LANG = gap.LANG_DIR
SPAN, IMPORT, ALL = gap.SPAN, gap.IMPORT, set(gap.ALL)


def gates(*files):
    return set(gap.plan(list(files), "pull_request", CORPUS)["gates"])


@pytest.mark.parametrize(
    ("lang", "expected"),
    [
        ("haskell", {IMPORT, SPAN}),
        ("dart", {IMPORT, SPAN}),
        ("swift", {IMPORT, SPAN}),
        ("powershell", {IMPORT, SPAN}),
        ("tcl", {IMPORT, SPAN}),
        ("fortran", {IMPORT, SPAN}),
        ("matlab", {IMPORT, SPAN}),
        ("cobol", {SPAN}),
        ("objectivec", {IMPORT, SPAN}),  # corpus key is `objective-c`
        ("python", {IMPORT, SPAN, "call-python"}),
        ("typescript", {IMPORT, SPAN, "call-typescript"}),
        ("javascript", {IMPORT, SPAN, "call-javascript"}),
        ("java", {IMPORT, SPAN, "call-java"}),
        ("rust", {IMPORT, SPAN, "call-rust"}),
        ("go", {IMPORT, SPAN, "call-go"}),
        ("c", {IMPORT, SPAN, "call-c"}),
        ("cpp", {IMPORT, SPAN, "call-cpp"}),
    ],
)
def test_a_language_standard_selects_its_own_gates(lang, expected):
    assert gates(f"{LANG}{lang}.py") == expected


@pytest.mark.parametrize("lang", ["haskell", "dart", "swift", "powershell", "tcl", "fortran", "matlab", "cobol", "pli"])
def test_a_language_without_a_call_gate_needs_no_toolchain(lang):
    sel = gap.resolve(gap.wrap(gates(f"{LANG}{lang}.py")))
    assert [k for k in gap.TOOLCHAINS if sel[k] == "true"] == []
    assert sel["crucible"] == "true"  # span anchoring reads language-crucible


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (gap.T + "scip_callgraph.py", {"call-java", "call-rust"}),
        (gap.T + "clang_callgraph.py", {"call-c", "call-cpp"}),
        (gap.T + "ts_callgraph.js", {"call-typescript", "call-javascript"}),
        (gap.T + "go_callgraph/main.go", {"call-go"}),
        (gap.T + "span_anchor_audit.py", {SPAN}),
        (gap.T + "import_graph_accuracy.py", {IMPORT}),
        ("tests/span_anchor_baseline.json", {SPAN}),
        ("tests/import_graph_accuracy_baseline.json", {IMPORT}),
        ("tests/call_graph_resolution_baseline.json", {"call-python"}),
        ("tests/call_graph_resolution_cpp_baseline.json", {"call-cpp"}),
        (gap.T + "call_graph_resolution.py", set(gap.CALL)),
        (gap.T + "callgraph_refs.py", set(gap.CALL)),
    ],
)
def test_a_gates_own_tool_or_baseline_selects_that_gate(path, expected):
    assert gates(path) == expected


@pytest.mark.parametrize("path", sorted(gap.EVERYTHING))
def test_shared_inputs_select_every_gate(path):
    assert gates(path) == ALL


@pytest.mark.parametrize(
    "path",
    [
        "gitgalaxy/standards/language_standards/identifiers.py",
        "gitgalaxy/standards/language_standards/_shared_patterns.py",
        "gitgalaxy/standards/language_standards/languages/__init__.py",
        "gitgalaxy/standards/language_standards/new_registry_file.json",
    ],
)
def test_an_unknown_or_shared_language_standards_file_selects_every_gate(path):
    assert gates(path) == ALL


@pytest.mark.parametrize(
    "path",
    ["docs/graph_accuracy.md", "README.md", ".claude/rules/x.md", "tests/tools/test_foo.py", "gitgalaxy/tools/x.py"],
)
def test_a_file_no_gate_reads_selects_nothing(path):
    p = gap.plan([path], "pull_request", CORPUS)
    assert p["gates"] == []
    assert gap.resolve(gap.wrap(p["gates"]))["any"] == "false"


def test_a_mixed_change_is_the_union():
    assert gates(f"{LANG}haskell.py", gap.T + "scip_callgraph.py", "README.md") == {
        IMPORT,
        SPAN,
        "call-java",
        "call-rust",
    }


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch"])
def test_other_events_and_an_empty_diff_run_everything(event):
    assert set(gap.plan(["README.md"], event, CORPUS)["gates"]) == ALL
    assert set(gap.plan([], "pull_request", CORPUS)["gates"]) == ALL


def test_resolve_failed_plan_runs_everything_and_unknown_gate_too():
    for planned in ("", ",bogus,"):
        sel = gap.resolve(planned)
        assert sel["gates"] == gap.wrap(gap.ALL)
        assert all(sel[k] == "true" for k in gap.TOOLCHAINS)


def test_resolve_switches():
    sel = gap.resolve(",call-c,")
    assert (sel["clang"], sel["node"], sel["java"], sel["rust"], sel["go"]) == ("true",) + ("false",) * 4
    assert (sel["import_corpus"], sel["crucible"]) == ("true", "false")
    assert gap.resolve(",call-python,")["import_corpus"] == "false"


def test_wrapped_gates_do_not_match_by_prefix():
    assert ",call-c," not in gap.wrap(["call-cpp"])


# -- the workflow agrees with the planner


@pytest.fixture(scope="module")
def workflow():
    yaml = pytest.importorskip("yaml")
    text = (ROOT / ".github/workflows/graph-accuracy-audit.yml").read_text(encoding="utf-8")
    return text, yaml.safe_load(text)


def test_every_gate_the_lanes_run_is_a_planned_gate(workflow):
    run = next(s["run"] for s in workflow[1]["jobs"]["graph-accuracy-audit"]["steps"] if "lanes" in s.get("name", ""))
    named = {re.sub(r"-\d$", "", n) for n in re.findall(r"\bgate ([a-z][\w-]*) python", run)}  # import-graph-N: subsets
    assert named == ALL  # span anchoring is the merge gate
    assert "want span-anchoring" in run


def test_every_gate_runs_in_exactly_one_lane_slot(workflow):
    run = next(s["run"] for s in workflow[1]["jobs"]["graph-accuracy-audit"]["steps"] if "lanes" in s.get("name", ""))
    body = run[: run.index("\nwait\n")]  # the lanes, before the span-anchoring merge gate
    gates = re.findall(r"\bgate ([a-z][\w-]*) python", body)
    shards = re.findall(r"run_gate (span-shard-[01]) python", body)
    assert sorted(gates) == sorted(
        [f"call-{n}" for n in ("c", "cpp", "go", "java", "javascript", "python", "rust", "typescript")]
        + [f"import-graph-{n}" for n in (1, 2, 3)]
    )  # a rebalance neither drops nor doubles a gate
    assert sorted(shards) == ["span-shard-0", "span-shard-1"]
    assert body.count(") &") == 4


def test_the_import_graph_subsets_cover_every_language_exactly_once(workflow):
    run = next(s["run"] for s in workflow[1]["jobs"]["graph-accuracy-audit"]["steps"] if "lanes" in s.get("name", ""))
    subsets = [m.split() for m in re.findall(r'^\s*IG\d="([^"]+)"', run, re.M)]
    assert len(subsets) == 3
    langs = sorted(lang for sub in subsets for lang in sub)
    tree = ast.parse((TOOLS / "import_graph_accuracy.py").read_text(encoding="utf-8"))
    all_langs = next(
        ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "LANGS"
    )
    assert langs == sorted(all_langs)  # no gap (an unmeasured language) and no overlap (a double run)
    for n in (1, 2, 3):
        assert f"import_graph_accuracy.py $IG{n} " in run


def test_every_toolchain_step_is_gated_on_a_planned_switch(workflow):
    steps = workflow[1]["jobs"]["graph-accuracy-audit"]["steps"]
    heavy = {"TypeScript": "node", "JDK": "java", "scip-java": "java", "Rust": "rust", "cargo": "rust", "Go 1.24": "go"}
    for key, switch in heavy.items():
        hit = [s for s in steps if key in s.get("name", "")]
        assert hit, key
        for s in hit:
            assert f"steps.sel.outputs.{switch} == 'true'" in s.get("if", ""), s["name"]
    assert set(heavy.values()) <= set(gap.TOOLCHAINS)


def test_the_check_name_is_unchanged_and_still_reports_after_a_failed_plan(workflow):
    jobs = workflow[1]["jobs"]
    assert set(jobs) == {"plan", "graph-accuracy-audit"}
    job = jobs["graph-accuracy-audit"]
    assert job["needs"] == ["plan"]
    assert "always()" in job["if"]
    assert "github.event.pull_request.draft" in jobs["plan"]["if"]


def test_the_filter_triggers_on_the_planners_own_files(workflow):
    paths = workflow[1][True]["pull_request"]["paths"]
    for f in (gap.T + "graph_accuracy_plan.py", gap.T + "change_classifier.py"):
        assert f in paths


def test_every_file_the_planner_maps_is_matched_by_the_workflow_filter():
    paths = gap._workflow_paths()
    owned = [*gap.EVERYTHING, *gap.OWNERS]
    missing = [p for p in owned if not gap._glob(p if not p.endswith("/") else p + "x", paths)]
    assert missing == []


def test_replay_counts_before_and_after():
    prs = [
        {"number": 1, "files": [{"path": f"{LANG}haskell.py"}]},
        {"number": 2, "files": [{"path": "docs/graph_accuracy.md"}]},
        {"number": 3, "files": [{"path": f"{LANG}c.py"}, {"path": "docs/x.md"}]},
        {"number": 4, "files": [{"path": "gitgalaxy/core/detector.py"}]},
    ]
    r = gap.replay(prs, CORPUS)
    assert (r["prs"], r["ran_before"], r["runs_now"]) == (4, 3, 3)
    assert r["gates_per_triggered_pr"] == {1: 2, 3: 3, 4: len(gap.ALL)}


def test_cli_writes_the_gates_output(tmp_path):
    out = tmp_path / "out"
    proc = subprocess.run(
        [
            sys.executable,
            str(TOOLS / "graph_accuracy_plan.py"),
            "--files",
            f"{LANG}dart.py",
            "--github-output",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "dart.py" in proc.stdout
    assert out.read_text() == "gates=,import-graph,span-anchoring,\n"
