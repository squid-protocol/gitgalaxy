"""#5954: a test gated on EQUIVALENCE_E2E / CICS_CRUCIBLE_PATH proves nothing unless some workflow sets that variable
for the pytest run that reaches it. cics-crucible.yml `runner-tests` sets EQUIVALENCE_E2E (for tests/cics_crucible) and equivalence-e2e.yml (for tests/cobol_mainframe)
and CICS_CRUCIBLE_PATH (for the four files that read the checkout). This guard lists every gated file, requires each to be covered by a workflow or be
named in UNCOVERED below, and fails when a listed file becomes covered (or disappears), so the list only shrinks."""

import re
import sys
from pathlib import Path

from gitgalaxy.core.source_text import read_source

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_e2e_select  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SELECTOR = "tests/tools/equivalence_e2e_select.py"  # a shard step that runs it passes its output to pytest
TESTS = REPO / "tests"
WORKFLOWS = REPO / ".github" / "workflows"

READ = r"environ(?:\.get\(|\[)\s*[\"']"
E2E_READ = re.compile(READ + "EQUIVALENCE_E2E")
PATH_READ = re.compile(r"environ(?:\.get\(|\[)\s*(?:runner\.PATH_ENV|[\"']CICS_CRUCIBLE_PATH)")

# Gated files no workflow reaches yet. Shrink-only. equivalence-e2e.yml runs tests/cobol_mainframe (and test_zos_probes)
# under EQUIVALENCE_E2E: the shards `--ignore` the five files that also need a Db2 container, its `db2` job names them (#5954).
UNCOVERED_E2E: frozenset[str] = frozenset()
DB2_FILES = (
    "tests/cobol_mainframe/test_equivalence_db2_rows.py",
    "tests/cobol_mainframe/test_regional_options.py",
    "tests/cobol_mainframe/test_sql_dynamic.py",
    "tests/cobol_mainframe/test_sql_unit_of_work.py",
    "tests/cobol_mainframe/test_sql_whenever.py",
)
UNCOVERED_PATH: frozenset[str] = frozenset()  # slice 2: cics-crucible.yml runner-tests sets CICS_CRUCIBLE_PATH
# What a gated file says it needs, read from the `reason=` of its skip marks (the same wording a skipped run prints).
NEEDS = {
    "docker": re.compile(r"Docker"),
    "jdk_maven": re.compile(r"JDK|Maven"),
    "db2": re.compile(r"Db2"),
    "crucible_checkout": re.compile(r"cics-crucible checkout|CICS_CRUCIBLE_PATH"),
}
REASON = re.compile(r"(?:reason=|skip\()\s*f?\"([^\"]*)\"")
DOCSTRING = re.compile(r'\A\s*"""(.*?)"""', re.S)
DOC = REPO / "docs" / "ci_env_gated_tests.md"
# Reads CICS_CRUCIBLE_PATH only from its own monkeypatched sandbox, not from the runner's environment.
NOT_GATED = frozenset({"test_crucible_pins.py"})


def _gated():
    e2e, path = set(), set()
    for f in TESTS.rglob("test_*.py"):
        if f.name == Path(__file__).name or f.name in NOT_GATED:
            continue
        text = read_source(f).text
        rel = f.relative_to(REPO).as_posix()
        if E2E_READ.search(text):
            e2e.add(rel)
        if PATH_READ.search(text):
            path.add(rel)
    return e2e, path


def needs_of(text):
    """The environment a file's skip reasons and module docstring name: a subset of NEEDS."""
    doc = DOCSTRING.match(text)
    reasons = " ".join(REASON.findall(text) + ([doc.group(1)] if doc else []))
    return frozenset(k for k, rx in NEEDS.items() if rx.search(reasons))


def _workflow_coverage():
    """(the EQUIVALENCE_E2E pytest runs as [(test paths, --ignore'd paths)], paths a run reaches under CICS_CRUCIBLE_PATH)."""
    runs, path = [], []
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        lines = wf.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            is_e2e = re.match(r"\s*EQUIVALENCE_E2E\s*:\s*[\"']?1", line)
            if not is_e2e and not re.match(r"\s*(?:-\s*)?CICS_CRUCIBLE_PATH\s*:", line):
                continue
            for j, later in enumerate(lines[i + 1 : i + 15]):
                if "pytest" in later:
                    words = later.split()
                    named = re.findall(r"\btests/[\w./-]*", " ".join(w for w in words if not w.startswith("--")))
                    if any(SELECTOR in ln for ln in lines[i + 1 : i + 1 + j]):  # #6664: the files the selector prints
                        named += equivalence_e2e_select.select(REPO)
                    if is_e2e:
                        ignored = [w.split("=", 1)[1].rstrip("/") for w in words if w.startswith("--ignore=")]
                        runs.append(([r.rstrip("/") for r in named], ignored))
                    else:
                        path += [r.rstrip("/") for r in named]
                    break
    return runs, path


def _reached(rel, reached, ignored=()):
    return rel not in ignored and any(rel == r or rel.startswith(r + "/") for r in reached)


def _reached_e2e(rel, runs):
    """Some pytest run names the file (or its directory) and does not `--ignore` it: an ignored file is not reached."""
    return any(_reached(rel, named, ignored) for named, ignored in runs)


def test_every_env_gated_test_is_reached_by_a_workflow_or_listed():
    e2e, path = _gated()
    runs, reached_path = _workflow_coverage()
    unlisted_e2e = sorted(f for f in e2e if not _reached_e2e(f, runs) and f not in UNCOVERED_E2E)
    unlisted_path = sorted(f for f in path if not _reached(f, reached_path) and f not in UNCOVERED_PATH)
    assert not unlisted_e2e, f"gated on EQUIVALENCE_E2E, set by no workflow for this path (#5954): {unlisted_e2e}"
    assert not unlisted_path, f"gated on CICS_CRUCIBLE_PATH, set by no workflow (#5954): {unlisted_path}"


def test_the_uncovered_lists_only_shrink():
    e2e, path = _gated()
    runs, reached_path = _workflow_coverage()
    stale_e2e = sorted(f for f in UNCOVERED_E2E if f not in e2e or _reached_e2e(f, runs))
    stale_path = sorted(f for f in UNCOVERED_PATH if f not in path or _reached(f, reached_path))
    assert not stale_e2e, f"now covered or no longer gated: drop from UNCOVERED_E2E: {stale_e2e}"
    assert not stale_path, f"now covered or no longer gated: drop from UNCOVERED_PATH: {stale_path}"


def test_the_runner_tests_job_is_seen_as_covering_cics_crucible():
    runs, reached_path = _workflow_coverage()
    assert any("tests/cics_crucible" in named for named, _ in runs)
    assert "tests/tools/test_crucible_case.py" in reached_path


def test_the_e2e_shards_ignore_the_db2_files_and_the_db2_job_runs_them():
    runs, _ = _workflow_coverage()
    shards = [r for r in runs if any(p.startswith("tests/cobol_mainframe/") for p in r[0])]
    assert shards and "tests/tools/test_zos_probes.py" in shards[0][0]
    assert set(shards[0][1]) >= set(DB2_FILES)
    assert _reached_e2e("tests/cobol_mainframe/test_det_funcs.py", runs)
    for f in DB2_FILES:
        assert not _reached(f, *shards[0]), f"the shards must leave {f} to the db2 job"
        assert any(f in named and f not in ignored for named, ignored in runs), f"no pytest run names {f}"


# #6664: files with no EQUIVALENCE_E2E read whose tests ground-truth skips ("no JDK 17", a jar) and the shards run:
# measured from junit outcomes of runs 40225533892 / 40225536142. The selector keeps them through their skip reasons.
JDK_ONLY = (
    "tests/cobol_mainframe/test_no_jcl_batch_controller.py",
    "tests/cobol_mainframe/test_mvs_oracle_5856.py",
    "tests/cobol_mainframe/test_generated_record_layer.py",
    "tests/cobol_mainframe/test_key_collation.py",
    "tests/cobol_mainframe/test_decimal_comma.py",
)


def test_the_e2e_selector_keeps_the_gated_and_tool_skipped_files_and_drops_the_rest():
    picked = set(equivalence_e2e_select.select(REPO))
    e2e, _ = _gated()
    mainframe_gated = {f for f in e2e if f.startswith("tests/cobol_mainframe/") and f not in DB2_FILES}
    assert mainframe_gated <= picked, sorted(mainframe_gated - picked)
    assert set(JDK_ONLY) <= picked, sorted(set(JDK_ONLY) - picked)
    # ground-truth runs these with the same result: 82 s and 65 s of the 1810 s the shards ran twice
    assert (
        not {"tests/cobol_mainframe/test_assess.py", "tests/cobol_mainframe/test_refraction_differential.py"} & picked
    )
    assert not set(DB2_FILES) & picked


def test_every_uncovered_file_states_what_it_needs():
    """A gated file whose skip reasons name no environment cannot be scheduled into a workflow: reword its reason."""
    nameless = sorted(f for f in UNCOVERED_E2E | UNCOVERED_PATH if not needs_of(read_source(REPO / f).text))
    assert not nameless, f"skip reason names no Docker / JDK / Db2 / crucible checkout (#5954): {nameless}"


def test_the_inventory_page_lists_every_uncovered_file_under_its_needs():
    page = read_source(DOC).text
    for f in sorted(UNCOVERED_E2E | UNCOVERED_PATH):
        row = next((ln for ln in page.splitlines() if f"`{f}`" in ln), None)
        assert row, f"{f} is not in {DOC.relative_to(REPO)}"
        for need in needs_of(read_source(REPO / f).text):
            assert need in row, f"{f}: the page row does not name {need}"


def _deselected():
    """[(file, test function)] for every `--deselect=path::test` in equivalence-e2e.yml."""
    text = read_source(WORKFLOWS / "equivalence-e2e.yml").text
    ids = re.findall(r"--deselect=?\s*['\"]?(tests/[\w./-]+)::(\w+)", text)
    return sorted(set(ids))


def test_every_deselected_e2e_test_exists_and_is_listed_on_the_inventory_page():
    """A --deselect keeps a failing gated test out of CI: it must name a live test (a renamed one deselects nothing
    and its replacement runs unseen) and stay on the page until its defect is fixed."""
    deselected = _deselected()
    assert len(deselected) >= 2, "the --deselect parse found fewer ids than the workflow carries"
    page = read_source(DOC).text
    for rel, name in deselected:
        assert re.search(rf"^\s*(?:async\s+)?def {name}\(", read_source(REPO / rel).text, re.M), (
            f"{rel}::{name} is gone"
        )
        assert name in page, f"{rel}::{name} is deselected in equivalence-e2e.yml but not on {DOC.relative_to(REPO)}"
