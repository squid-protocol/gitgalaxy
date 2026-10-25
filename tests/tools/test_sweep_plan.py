"""#5166 part A: the extraction ReDoS sweeps are deselected only on a pull request that changes no sweep input.

The planner (tests/tools/sweep_plan.py) must never drop a sweep for a PR that touches something a sweep reads, and the
marker (tests/conftest.py) must select exactly the sweeps the workflow deselects.
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sweep_plan as sp

ROOT = Path(__file__).resolve().parents[2]

# one path per family: what a sweep reads
INPUT_PATHS = [
    "gitgalaxy/standards/language_standards/languages/cobol.py",
    "gitgalaxy/core/detector.py",
    "gitgalaxy/galaxyscope.py",
    "gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py",  # under gitgalaxy/ and in the closure (or not listed): an input
    "gitgalaxy/core/cics_macro_level.py",  # under gitgalaxy/, outside the closure but unlisted: an input
    "gitgalaxy/core/README.md",
    "tests/extraction/languages/test_python.py",
    "tests/extraction/languages/_strict_harness.py",
    "tests/extraction/_extraction_harness.py",
    "tests/extraction/how_to_harden_strict_signatures.md",
    "tests/conftest.py",
    "tests/_timing.py",  # a test helper the sweeps import
    "tests/core_engine/test_detector.py",  # a test directory nobody listed: an input
    "pyproject.toml",
    "requirements.txt",
    "ci/requirements/test.txt",
    ".github/workflows/smoke-test.yml",
    ".github/workflows/full-suite-gate.yml",
    "tests/tools/sweep_plan.py",
    "tests/tools/test_sweep_plan.py",
    "setup.cfg",  # unlisted at the root
    "somewhere/new/file.py",
]
# what they provably do not read
NON_INPUT_PATHS = [
    "docs/ci.md",
    "docs/language_status/cobol.md",
    "README.md",
    "CLAUDE.md",
    ".claude/rules/test-writing.md",
    ".github/workflows/det-sweep.yml",
    ".github/dependabot.yml",
    "tests/cobol_mainframe/test_completeness.py",
    "tests/equivalence/some-case/case.json",
    "tests/tools/det_sweep_plan.py",
    "tests/tools/box/heavy-run.sh",
]


@pytest.mark.parametrize("path", INPUT_PATHS)
def test_every_input_family_runs_the_sweeps(path):
    p = sp.plan([path], "pull_request")
    assert p["mode"] == "full" and p["inputs"] == [path]


@pytest.mark.parametrize("path", NON_INPUT_PATHS)
def test_a_non_input_deselects_the_sweeps(path):
    assert sp.plan([path], "pull_request")["mode"] == "none"


def test_all_non_inputs_together_deselect():
    assert sp.plan(NON_INPUT_PATHS, "pull_request")["mode"] == "none"


@pytest.mark.parametrize("path", INPUT_PATHS)
def test_one_input_among_non_inputs_runs_them(path):
    assert sp.plan([*NON_INPUT_PATHS, path], "pull_request")["mode"] == "full"


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch", "merge_group", ""])
def test_every_other_event_runs_the_sweeps(event):
    assert sp.plan(NON_INPUT_PATHS, event)["mode"] == "full"
    assert sp.plan([], event)["mode"] == "full"


def test_the_full_label_runs_the_sweeps():
    assert sp.plan(NON_INPUT_PATHS, "pull_request", ["bug", sp.FULL_LABEL])["mode"] == "full"
    assert sp.plan(NON_INPUT_PATHS, "pull_request", ["bug"])["mode"] == "none"


def test_an_empty_diff_runs_the_sweeps():
    assert sp.plan([], "pull_request")["mode"] == "full"


def test_an_unreadable_diff_runs_the_sweeps(monkeypatch, tmp_path, capsys):
    def boom(base):
        raise RuntimeError("bad revision")

    monkeypatch.setattr(sp, "changed_files", boom)
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["sweep_plan", "--github-output", str(out)])
    assert sp.main() == 0
    assert out.read_text() == "mode=full\n"
    assert "cannot diff" in capsys.readouterr().out


def _pr_list(tmp_path, rows):
    path = tmp_path / "pr-files.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_the_prs_file_list_names_a_rename_twice(tmp_path):
    rows = [{"filename": "docs/a.md", "previous_filename": None},
            {"filename": "docs/new.md", "previous_filename": "gitgalaxy/old.py"}]  # fmt: skip
    assert sp.pr_files(_pr_list(tmp_path, rows), "2") == ["docs/a.md", "docs/new.md", "gitgalaxy/old.py"]


@pytest.mark.parametrize("count", ["3", "", "x"])
def test_a_partial_or_uncounted_pr_list_is_unreadable(tmp_path, count):
    with pytest.raises(RuntimeError):
        sp.pr_files(_pr_list(tmp_path, [{"filename": "docs/a.md"}, {"filename": "docs/b.md"}]), count)


@pytest.mark.parametrize(("rows", "count", "mode"), [
    ([{"filename": "docs/ci.md"}], "1", "none"),
    ([{"filename": "docs/ci.md"}], "2", "full"),  # not the whole list: cannot tell, so the sweeps run
    ([{"filename": "docs/ci.md", "previous_filename": "gitgalaxy/core/x.py"}], "1", "full"),  # renamed from an input
])  # fmt: skip
def test_main_plans_from_the_prs_file_list(monkeypatch, tmp_path, capsys, rows, count, mode):
    monkeypatch.setattr(sys, "argv", ["sweep_plan", "--pr-files", str(_pr_list(tmp_path, rows)),
                                      "--pr-file-count", count])  # fmt: skip
    monkeypatch.setattr(sp, "changed_files", lambda _base: pytest.fail("no git diff when the PR's list is given"))
    assert sp.main() == 0
    assert json.loads(capsys.readouterr().out)["mode"] == mode


def test_main_writes_the_mode_for_the_workflow(monkeypatch, tmp_path):
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["sweep_plan", "--files", "docs/ci.md", "--github-output", str(out)])
    assert sp.main() == 0
    assert out.read_text() == "mode=none\n"
    out.write_text("")
    monkeypatch.setattr(sys, "argv", ["sweep_plan", "--files", "docs/ci.md", "--labels", "x," + sp.FULL_LABEL,
                                      "--github-output", str(out)])  # fmt: skip
    sp.main()
    assert out.read_text() == "mode=full\n"


def test_the_sweeps_import_no_non_input_module():
    """INPUTS name what a sweep reads: a bare import of a module under a NON_INPUT directory would make that wrong."""
    non_input_modules = set()
    for d in ("tests/tools", "tests/cobol_mainframe", "tests/equivalence"):
        non_input_modules |= {p.stem for p in (ROOT / d).glob("*.py")}
    bad = []
    for f in sorted((ROOT / "tests" / "extraction").rglob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = (
                [a.name for a in node.names] if isinstance(node, ast.Import)
                else [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            )  # fmt: skip
            bad += [f"{f.relative_to(ROOT)}: {n}" for n in names if n.split(".")[0] in non_input_modules]
    assert not bad, bad


_RECORDER = """
import json, os
def pytest_collection_finish(session):
    rows = {i.nodeid: i.get_closest_marker("redos_sweep") is not None for i in session.items}
    with open(os.environ["SWEEP_MARKS_OUT"], "w") as fh:
        json.dump(rows, fh)
"""


def _collect(tmp_path, *args):
    """Collect `args` once; the nodeids that survive the run's own -m, each with whether it carries `redos_sweep`."""
    (tmp_path / "sweep_marks_plugin.py").write_text(_RECORDER, encoding="utf-8")
    out = tmp_path / "marks.json"
    env = {
        **os.environ,
        "SWEEP_MARKS_OUT": str(out),
        "PYTHONPATH": f"{tmp_path}{os.pathsep}{os.environ.get('PYTHONPATH', '')}",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *args, "--collect-only", "-q", "-p", "no:cacheprovider", "-p", "sweep_marks_plugin"],
        cwd=ROOT, capture_output=True, text=True, check=False, env=env,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    return json.loads(out.read_text(encoding="utf-8"))


def _sweep_name(nodeid):
    name = nodeid.split("[")[0].split("::")[-1]
    return "redos" in name or "linear_on_pathological" in name


def test_the_marker_is_exactly_the_name_rule_under_extraction(tmp_path):
    rows = _collect(tmp_path, "tests/extraction")  # one collection of the directory
    assert any(rows.values()), "no sweep is marked: the hook did not run"
    for nodeid, marked in rows.items():
        assert marked == _sweep_name(nodeid), nodeid


def test_m_deselects_the_marked_sweeps_and_golden_crucible_stays_out(tmp_path):
    """pytest's own -m must see the marker (the hook is tryfirst); smoke-test.yml's expression on one language file."""
    f = "tests/extraction/languages/test_python.py"
    all_ids = set(_collect(tmp_path, f))
    kept = _collect(tmp_path, f, "-m", "not golden_crucible and not redos_sweep")
    assert any(_sweep_name(n) for n in all_ids), "the file has no sweep: pick another"
    assert set(kept) == {n for n in all_ids if not _sweep_name(n)}
    assert not any(kept.values())


def test_a_test_outside_extraction_is_not_marked(tmp_path):
    rows = _collect(tmp_path, "tests/core_engine/test_prism.py")  # has redos-named tests: they stay always-on
    assert any(_sweep_name(n) for n in rows)
    assert not any(rows.values())


def test_the_workflow_plans_then_deselects_with_golden_crucible_kept():
    yaml = pytest.importorskip("yaml")
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "smoke-test.yml").read_text(encoding="utf-8"))["jobs"]
    job = wf["full-suite-part"]
    names = [s.get("name", "") for s in job["steps"]]
    plan_i = next(i for i, n in enumerate(names) if n.startswith("Plan the ReDoS sweeps"))
    pytest_i = next(i for i, n in enumerate(names) if n.startswith("Golden Record Integration Test"))
    assert plan_i < pytest_i
    plan_step, run_step = job["steps"][plan_i], job["steps"][pytest_i]
    assert plan_step["id"] == "sweeps" and "sweep_plan.py" in plan_step["run"]
    assert '--event "$GITHUB_EVENT_NAME"' in plan_step["run"]
    assert run_step["env"]["SWEEPS"] == "${{ steps.sweeps.outputs.mode }}"
    assert '[ "$SWEEPS" = "none" ]' in run_step["run"]  # only an explicit none deselects
    assert '-m "not golden_crucible and not redos_sweep"' in run_step["run"]
    # #5882: the plan reads the PR's own file list (whole, by count), so the part checks out one commit and fetches
    # no history (an `event == 'pull_request' && 0 || 1` depth was always 1: the plan could never diff)
    assert '"repos/$REPO/pulls/$PR/files"' in plan_step["run"] and '--pr-files "$files"' in plan_step["run"]
    assert '--pr-file-count "$count"' in plan_step["run"] and "git fetch" not in plan_step["run"]
    checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["fetch-depth"] == 1
    # the required aggregate and its needs are unchanged; the matrix gate never deselects
    assert wf["full-suite"]["needs"] == ["tested-tree", "suite-plan", "full-suite-part"]  # #6278
    gate = (ROOT / ".github" / "workflows" / "full-suite-gate.yml").read_text(encoding="utf-8")
    assert "redos_sweep" not in gate and "sweep_plan" not in gate


# the engine parts outside the sweeps' import closure (#5166): a change there keeps no sweep
ENGINE_NON_INPUT_PATHS = [
    "gitgalaxy/tools/cobol_to_java/det/emit.py",
    "gitgalaxy/tools/cobol_to_java/det/copy/DFHAID.cpy",
    "gitgalaxy/tools/cobol_to_java/README.md",
    "gitgalaxy/tools/terabyte_log_scanning/README.md",
    "gitgalaxy/standards/cics/commands/send.py",
    "gitgalaxy/cobol_to_java_controller.py",
    "gitgalaxy/cobol_refractor_controller.py",
]


@pytest.mark.parametrize("path", ENGINE_NON_INPUT_PATHS)
def test_an_engine_part_outside_the_import_closure_deselects_the_sweeps(path):
    assert sp.plan([path], "pull_request")["mode"] == "none"
    assert sp.plan([path], "push")["mode"] == "full"


@pytest.mark.parametrize("path", ["gitgalaxy/core/detector.py", "gitgalaxy/standards/language_standards/x.py"])
def test_an_engine_input_among_engine_non_inputs_runs_the_sweeps(path):
    assert sp.plan([ENGINE_NON_INPUT_PATHS[0], path], "pull_request")["mode"] == "full"


def _sweep_import_closure():
    """gitgalaxy modules the extraction tests import, transitively (function-level imports and parent packages too)."""

    def mod_file(name):
        p = ROOT / Path(*name.split("."))
        if (p / "__init__.py").is_file():
            return p / "__init__.py"
        return p.with_suffix(".py") if p.with_suffix(".py").is_file() else None

    def imports(path, pkg):
        out = set()
        for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                out |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                if n.level:
                    parts = pkg.split(".")
                    m = ".".join(parts[: len(parts) - (n.level - 1)] + ([n.module] if n.module else []))
                else:
                    m = n.module or ""
                out |= {m, *(f"{m}.{a.name}" for a in n.names)}
        return out

    todo = [
        m for f in (ROOT / "tests" / "extraction").rglob("*.py") for m in imports(f, "") if m.startswith("gitgalaxy")
    ]
    seen = set()
    while todo:
        m = todo.pop()
        f = mod_file(m) if m not in seen else None
        if f is None:
            continue
        seen.add(m)
        parts = m.split(".")
        todo += [".".join(parts[:i]) for i in range(1, len(parts))]
        pkg = m if f.name == "__init__.py" else m.rpartition(".")[0]
        todo += [x for x in imports(f, pkg) if x.startswith("gitgalaxy")]
    return {mod_file(m).relative_to(ROOT).as_posix() for m in seen}


def test_no_engine_non_input_is_in_the_sweeps_import_closure():
    """ENGINE_NON_INPUTS name what the sweeps do not import; a module they do import there would make that wrong."""
    closure = _sweep_import_closure()
    assert "gitgalaxy/core/detector.py" in closure  # the walk works
    bad = sorted(f for f in closure if not sp.is_input(f))
    assert not bad, bad
    # every pattern still names something that exists, so a rename cannot leave a dead exception behind
    for pat in sp.ENGINE_NON_INPUTS:
        assert any(
            sp.matches(p.relative_to(ROOT).as_posix(), (pat,)) for p in (ROOT / "gitgalaxy").rglob("*") if p.is_file()
        ), pat


def test_a_pull_request_or_push_ignores_cobol_mainframe_and_nothing_else_does():
    """Ground Truth runs tests/cobol_mainframe/ on a PR and a main push; the parts drop it there only (the nightly and a
    manual run keep it, #5953), via the plan step's env file."""
    yaml = pytest.importorskip("yaml")
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "smoke-test.yml").read_text(encoding="utf-8"))["jobs"]
    job = wf["full-suite-part"]
    plan_step = next(s for s in job["steps"] if s.get("id") == "sweeps")
    run_step = next(s for s in job["steps"] if s.get("name", "").startswith("Golden Record Integration Test"))
    assert '[ "$GITHUB_EVENT_NAME" = "pull_request" ] || [ "$GITHUB_EVENT_NAME" = "push" ]' in plan_step["run"]
    assert "schedule" not in plan_step["run"].split("PYTEST_ADDOPTS")[0].rsplit("if ", 1)[-1]
    assert "PYTEST_ADDOPTS=--ignore=tests/cobol_mainframe" in plan_step["run"]
    assert "cobol_mainframe/test_evidence_components.py" in run_step["run"]  # the older ignore is unchanged
    assert "PYTEST_ADDOPTS" not in run_step["run"]
    gate = (ROOT / ".github" / "workflows" / "full-suite-gate.yml").read_text(encoding="utf-8")
    assert "PYTEST_ADDOPTS" not in gate
    # #5953: the nightly grid drops ubuntu / 3.12 (smoke-test.yml's nightly is that leg); a tag or manual run keeps it
    assert '"$GITHUB_EVENT_NAME" = "schedule" ] || {' in gate
    # post-merge.yml's dispatch (workflow_dispatch on main, no inputs) drops it too; a PR-branch run or full_matrix=true keeps it
    assert '"$GITHUB_REF" = "refs/heads/main" ]' in gate
    assert '"$FULL_MATRIX" != "true" ]; }; then\n' in gate
    assert '.os != "ubuntu-latest" or .["python-version"] != "3.12"' in gate
    gt = yaml.safe_load((ROOT / ".github" / "workflows" / "mainframe-ground-truth.yml").read_text(encoding="utf-8"))
    part = gt["jobs"]["ground-truth-part"]
    assert "fromJSON(needs.plan.outputs.matrix" in part["strategy"]["matrix"]  # #5543: the plan job picks 4 parts or 2
    steps = " ".join(s.get("run", "") for s in part["steps"])
    assert "tests/cobol_mainframe/ " in steps  # the job that now owns the directory still runs all of it
    assert "--splits ${{ matrix.parts }}" in steps  # every layout's groups together are the whole directory


def _pr(number, *paths):
    return {"number": number, "files": [{"path": p} for p in paths]}


def test_replay_counts_the_prs_that_skip_and_the_serial_time_they_save():
    durations = {
        "tests/extraction/languages/test_x.py::test_x_redos_immune[a]": 30.0,
        "tests/extraction/languages/test_x.py::test_x_linear_on_pathological": 30.0,
        "tests/extraction/languages/test_x.py::test_x_branch": 99.0,  # not a sweep by name
        "tests/core_engine/test_y.py::test_y_redos_sweep": 99.0,  # not under extraction: unmarked
    }
    prs = [
        _pr(1, "docs/ci.md"),
        _pr(2, "docs/ci.md", "gitgalaxy/core/detector.py"),
        _pr(3, "tests/tools/det_sweep_plan.py"),
    ]
    out = sp.replay(prs, durations)
    assert (out["prs"], out["skipped"], out["skipped_prs"]) == (3, 2, [1, 3])
    assert out["share"] == 0.667
    assert out["sweep_serial_seconds_per_run"] == 60.0
    assert out["serial_minutes_saved"] == 2.0


def test_replay_treats_a_possibly_truncated_or_empty_file_list_as_full():
    full_page = _pr(1, *[f"docs/{i}.md" for i in range(100)])
    assert sp.replay([full_page, _pr(2)], {})["skipped"] == 0
    assert sp.replay([], {}) == {
        "prs": 0,
        "skipped": 0,
        "share": 0.0,
        "sweep_serial_seconds_per_run": 0.0,
        "serial_minutes_saved": 0.0,
        "skipped_prs": [],
    }


def test_the_seconds_helper_names_the_same_tests_the_marker_does():
    # one rule in two places (tests/conftest.py _is_redos_sweep): the substrings and the directory must agree
    src = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert '"redos" in name or "linear_on_pathological" in name' in src
    assert (
        sp.sweep_seconds({"tests/extraction/a.py::C::test_redos_one[p]": 1.5, "tests/extraction/a.py::test_b": 2})
        == 1.5
    )


def test_replay_failure_exits_nonzero_without_planning(monkeypatch, capsys):
    monkeypatch.setattr(sp, "run_replay", lambda n: (_ for _ in ()).throw(RuntimeError("no gh")))
    monkeypatch.setattr(sys, "argv", ["sweep_plan.py", "--replay", "5"])
    assert sp.main() == 1
    assert "replay failed: no gh" in capsys.readouterr().err


# near misses: a path that only LOOKS like a non-input (sibling prefix, nested copy, other extension) stays an input
NEAR_MISS_INPUT_PATHS = [
    "gitgalaxy/standards/cics_extra.py",  # the CICS exemption is the directory, not the prefix
    "gitgalaxy/tools/cobol_to_java_helper.py",  # the translator exemption is its directory
    "gitgalaxy/cobol_to_java_controller_v2.py",
    "gitgalaxy/tools/terabyte_log_scanning_x/a.py",
    "tests/extraction_extra/test_a.py",
    "requirements-dev.txt",
    "ci/requirements/extra/lock.txt",
]


@pytest.mark.parametrize("path", NEAR_MISS_INPUT_PATHS)
def test_a_near_miss_of_a_non_input_pattern_runs_the_sweeps(path):
    assert sp.plan([path], "pull_request")["mode"] == "full"


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch"])
def test_main_ignores_the_prs_file_list_on_every_other_event(monkeypatch, tmp_path, capsys, event):
    rows = [{"filename": "docs/ci.md"}]
    monkeypatch.setattr(sys, "argv", ["sweep_plan", "--event", event, "--pr-files", str(_pr_list(tmp_path, rows)),
                                      "--pr-file-count", "1"])  # fmt: skip
    assert sp.main() == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "full"


def test_replay_counts_a_pr_with_no_files_key_or_a_nameless_entry_as_full():
    prs = [{"number": 1}, {"number": 2, "files": None}, {"number": 3, "files": [{"additions": 1}]}, _pr(4, "docs/a.md")]
    assert sp.replay(prs, {})["skipped_prs"] == [4]
