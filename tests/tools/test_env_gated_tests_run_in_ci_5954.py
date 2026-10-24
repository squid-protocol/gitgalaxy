"""#5954: a test gated on EQUIVALENCE_E2E / CICS_CRUCIBLE_PATH proves nothing unless some workflow sets that variable
for the pytest run that reaches it. cics-crucible.yml `runner-tests` sets EQUIVALENCE_E2E (for tests/cics_crucible) and equivalence-e2e.yml (for tests/cobol_mainframe)
and CICS_CRUCIBLE_PATH (for the four files that read the checkout). This guard lists every gated file, requires each to be covered by a workflow or be
named in UNCOVERED below, and fails when a listed file becomes covered (or disappears), so the list only shrinks."""

import re
from pathlib import Path

from gitgalaxy.core.source_text import read_source

REPO = Path(__file__).resolve().parents[2]
TESTS = REPO / "tests"
WORKFLOWS = REPO / ".github" / "workflows"

READ = r"environ(?:\.get\(|\[)\s*[\"']"
E2E_READ = re.compile(READ + "EQUIVALENCE_E2E")
PATH_READ = re.compile(r"environ(?:\.get\(|\[)\s*(?:runner\.PATH_ENV|[\"']CICS_CRUCIBLE_PATH)")

# Gated files no workflow reaches yet. Shrink-only. equivalence-e2e.yml runs the rest of tests/cobol_mainframe (and
# test_zos_probes) under EQUIVALENCE_E2E; these five also need a Db2 container, so the shard `--ignore`s them (#5954).
UNCOVERED_E2E = frozenset(
    {
        "tests/cobol_mainframe/test_equivalence_db2_rows.py",
        "tests/cobol_mainframe/test_regional_options.py",
        "tests/cobol_mainframe/test_sql_dynamic.py",
        "tests/cobol_mainframe/test_sql_unit_of_work.py",
        "tests/cobol_mainframe/test_sql_whenever.py",
    }
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
    """(test paths a pytest run reaches under EQUIVALENCE_E2E, those it reaches under CICS_CRUCIBLE_PATH)."""
    e2e, path, ignored = [], [], []
    env_lines = ((r"\s*EQUIVALENCE_E2E\s*:\s*[\"']?1", e2e), (r"\s*(?:-\s*)?CICS_CRUCIBLE_PATH\s*:", path))
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        lines = wf.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            for rx, reached in env_lines:
                if re.match(rx, line):
                    for later in lines[i + 1 : i + 15]:
                        if "pytest" in later:
                            words = later.split()
                            reached += re.findall(
                                r"\btests/[\w./-]*", " ".join(w for w in words if not w.startswith("--"))
                            )
                            ignored += [w.split("=", 1)[1] for w in words if w.startswith("--ignore=")]
                            break
    # an --ignore'd file is not reached (a directory a pytest line names minus the files it ignores, e.g. the Db2 ones)
    return [r.rstrip("/") for r in e2e], [r.rstrip("/") for r in path], [r.rstrip("/") for r in ignored]


def _reached(rel, reached, ignored=()):
    return rel not in ignored and any(rel == r or rel.startswith(r + "/") for r in reached)


def test_every_env_gated_test_is_reached_by_a_workflow_or_listed():
    e2e, path = _gated()
    reached, reached_path, ignored = _workflow_coverage()
    unlisted_e2e = sorted(f for f in e2e if not _reached(f, reached, ignored) and f not in UNCOVERED_E2E)
    unlisted_path = sorted(f for f in path if not _reached(f, reached_path) and f not in UNCOVERED_PATH)
    assert not unlisted_e2e, f"gated on EQUIVALENCE_E2E, set by no workflow for this path (#5954): {unlisted_e2e}"
    assert not unlisted_path, f"gated on CICS_CRUCIBLE_PATH, set by no workflow (#5954): {unlisted_path}"


def test_the_uncovered_lists_only_shrink():
    e2e, path = _gated()
    reached, reached_path, ignored = _workflow_coverage()
    stale_e2e = sorted(f for f in UNCOVERED_E2E if f not in e2e or _reached(f, reached, ignored))
    stale_path = sorted(f for f in UNCOVERED_PATH if f not in path or _reached(f, reached_path))
    assert not stale_e2e, f"now covered or no longer gated: drop from UNCOVERED_E2E: {stale_e2e}"
    assert not stale_path, f"now covered or no longer gated: drop from UNCOVERED_PATH: {stale_path}"


def test_the_runner_tests_job_is_seen_as_covering_cics_crucible():
    reached, reached_path, ignored = _workflow_coverage()
    assert "tests/cics_crucible" in reached
    assert "tests/tools/test_crucible_case.py" in reached_path


def test_the_e2e_shards_are_seen_as_covering_the_cobol_tests_but_not_the_db2_ones():
    reached, _, ignored = _workflow_coverage()
    assert "tests/cobol_mainframe" in reached and "tests/tools/test_zos_probes.py" in reached
    assert set(ignored) >= UNCOVERED_E2E
    assert _reached("tests/cobol_mainframe/test_det_funcs.py", reached, ignored)
    assert not _reached("tests/cobol_mainframe/test_sql_whenever.py", reached, ignored)


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
