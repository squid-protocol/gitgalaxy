"""#6278 slice 4: the engine subtrees a heavy PR gate provably does not import are negated in its `paths:` filter.

Reach is derived from the import closure of the gate's entry modules (over-approximate: every import statement counts,
function-local ones too). A negated path inside the closure, or a closure file the filter no longer triggers on, fails.
Real changed-file lists pin both directions.
"""

import ast
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import workflow_inputs as wi  # noqa: E402

ROOT = TOOLS.parents[1]
SCAN_ENTRY = ("gitgalaxy.galaxyscope", "gitgalaxy.tools.cobol_to_cobol.galaxy_ir", "gitgalaxy.core.ebcdic_codecs")
# the translator, its det runtime and the controllers: det/copy (stand-in copybooks, read by a scan) is not among them
TRANSLATOR = (
    "gitgalaxy/tools/cobol_to_java/aaa.py",
    "gitgalaxy/tools/cobol_to_java/det/aaa.py",
    "gitgalaxy/tools/cobol_to_java/det/cobolrt/aaa.java",
    "gitgalaxy/cobol_to_java_controller.py",
    "gitgalaxy/cobol_refractor_controller.py",
)
# the other standalone tools are NOT here: galaxyscope imports supply_chain_security and network_auditing modules
STANDALONE = ("gitgalaxy/tools/terabyte_log_scanning/aaa.py",)
ENGINE = (
    "gitgalaxy/core/detector.py",
    "gitgalaxy/standards/language_standards/identifiers.py",
    "gitgalaxy/galaxyscope.py",
)


def paths_of(name):
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    on = doc.get("on", doc.get(True))
    return on["pull_request"]["paths"]


def closure(entries):
    seen, todo = {}, list(entries)
    while todo:
        mod = todo.pop()
        base = ROOT / mod.replace(".", "/")
        p = next((c for c in (base / "__init__.py", base.with_suffix(".py")) if c.exists()), None)
        if mod in seen or p is None:
            continue
        seen[mod] = p
        parts = mod.split(".")
        todo += [".".join(parts[:i]) for i in range(1, len(parts))]
        pkg = parts if p.name == "__init__.py" else parts[:-1]
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                todo += [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                b = (
                    ".".join(pkg[: len(pkg) - (n.level - 1)] + ([n.module] if n.module else []))
                    if n.level
                    else n.module
                )
                if b:
                    todo += [b] + [f"{b}.{a.name}" for a in n.names]
    return {p.relative_to(ROOT).as_posix() for m, p in seen.items() if m.startswith("gitgalaxy")}


# workflow -> (entry modules it runs, files its filter must not trigger on, files it must trigger on)
GATES = {
    "unicode-gauntlet.yml": (SCAN_ENTRY, TRANSLATOR, STANDALONE + ENGINE),
    "rosetta-audit.yml": (SCAN_ENTRY, TRANSLATOR, STANDALONE + ENGINE),
    "ports-compile.yml": (
        (*SCAN_ENTRY, "gitgalaxy.cobol_to_java_controller", "gitgalaxy.cobol_refractor_controller"),
        STANDALONE,
        TRANSLATOR + ENGINE,
    ),
    "fact-crosscheck.yml": (
        (*SCAN_ENTRY, "gitgalaxy.tools.cobol_to_java.det.cics", "gitgalaxy.tools.cobol_to_java.det.layout"),
        STANDALONE,
        TRANSLATOR + ENGINE,
    ),
}


@pytest.mark.parametrize("name", sorted(GATES))
def test_the_filter_skips_only_what_the_entry_never_imports(name):
    entries, skipped, kept = GATES[name]
    paths = paths_of(name)
    reach = closure(entries)
    assert len(reach) > 50, "the import walk found almost nothing"
    assert not [f for f in reach if not wi.triggers(paths, f)], "imported by the gate but not a trigger"
    assert not [f for f in skipped if wi.triggers(paths, f)], "a path the gate should not trigger on does"
    assert all(wi.triggers(paths, f) for f in kept)


@pytest.mark.parametrize("name", ["unicode-gauntlet.yml", "rosetta-audit.yml"])
def test_scan_only_gates_skip_a_translator_only_pr_but_keep_the_stand_in_copybooks(name):
    paths = paths_of(name)
    assert not any(wi.triggers(paths, f) for f in TRANSLATOR)
    assert wi.triggers(paths, "gitgalaxy/tools/cobol_to_java/det/copy/CEEIGZCT.cpy")
    assert wi.triggers(paths, f".github/workflows/{name}")


@pytest.mark.parametrize("name", sorted(GATES))
def test_the_gate_still_triggers_on_its_own_inputs(name):
    paths = paths_of(name)
    assert wi.triggers(paths, "pyproject.toml")
    assert wi.triggers(paths, f".github/workflows/{name}")


# the Java compile gate: the generator's two package READMEs are prose to it (the classifier lists only test readers)
JAVA_READMES = ("gitgalaxy/tools/cobol_to_java/README.md", "gitgalaxy/tools/cobol_to_cobol/README.md")


def test_java_compile_skips_the_generator_readmes_but_keeps_every_generator_input():
    paths = paths_of("java-compile.yml")
    assert not any(wi.triggers(paths, f) for f in JAVA_READMES)
    assert all(wi.triggers(paths, f) for f in TRANSLATOR)
    assert wi.triggers(paths, "gitgalaxy/tools/cobol_to_java/det/copy/CEEIGZCT.cpy")
    assert wi.triggers(paths, "gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py")
    assert wi.triggers(paths, "tests/tools/java_target_matrix.py")


def test_the_readmes_java_compile_skips_are_not_read_by_the_generator():
    cc = pytest.importorskip("change_classifier")
    refs = cc.load()
    for f in JAVA_READMES:
        assert all(r.startswith("tests/") for r in cc.readers_of(f, refs)), f


def test_cics_crucible_skips_the_standalone_tool_and_generator_readmes_but_keeps_every_input():
    paths = paths_of("cics-crucible.yml")
    reach = closure((*SCAN_ENTRY, "gitgalaxy.cobol_to_java_controller", "gitgalaxy.tools.cobol_to_java.det.cics"))
    assert not [f for f in reach if not wi.triggers(paths, f)], "imported by the gate but not a trigger"
    assert not any(wi.triggers(paths, f) for f in STANDALONE + JAVA_READMES)
    assert all(wi.triggers(paths, f) for f in TRANSLATOR + ENGINE)
    assert wi.triggers(paths, "tests/tools/cics_crucible.py")
    assert wi.triggers(paths, ".github/workflows/cics-crucible.yml")


def test_muninn_triggers_on_every_area_a_secret_or_workflow_scanner_reads():
    """Muninn (gitleaks, semgrep, zizmor, checkov ...) reads engine, workflow and agent files; it skips tests and docs."""
    paths = paths_of("muninn.yml")
    cc = pytest.importorskip("change_classifier")
    for f, area in (
        ("gitgalaxy/core/detector.py", "engine"),
        (".github/workflows/ci.yml", "workflow"),
        (".claude/rules/x.md", "agent-config"),
    ):
        assert cc.area(f) == area and wi.triggers(paths, f), f
    for f, area in (("docs/ci.md", "test-read-doc"), ("tests/tools/test_x.py", "test-tooling")):
        assert cc.area(f) in (area, "prose") and not wi.triggers(paths, f), f


# built, not spelled: a literal .md path would make the classifier list this test as that page's reader
ENGINE_PROSE = tuple(f"gitgalaxy/{d}.{ext}" for d, ext in (("core/README", "md"), ("standards/how_to_add_a_language", "md")))


@pytest.mark.parametrize("name", ["unicode-gauntlet.yml", "rosetta-audit.yml", "ports-compile.yml"])
def test_scan_and_compile_gates_skip_engine_prose_but_keep_code_and_copybooks(name):
    """No gate here reads a .md under gitgalaxy/ (tests do, and the suite plan runs those); a code or copybook file still triggers."""
    paths = paths_of(name)
    assert not any(wi.triggers(paths, f) for f in ENGINE_PROSE)
    assert all(wi.triggers(paths, f) for f in ENGINE)
    assert wi.triggers(paths, "gitgalaxy/tools/cobol_to_java/det/copy/CEEIGZCT.cpy")


def test_engine_prose_is_never_imported_or_opened_by_a_gate_entry():
    reach = closure((*SCAN_ENTRY, "gitgalaxy.cobol_to_java_controller", "gitgalaxy.cobol_refractor_controller"))
    assert not [f for f in reach if f.endswith(".md")]


# #6278 item 4: every PR workflow on the checklist decides from the changed files what it runs. Each is one of three
# shapes, and a workflow that drifts back to an unconditional PR run (or loses its negations) fails here by name.
PLAN_GATED = {  # always starts (required or shared check), a plan step skips the install and the audit
    "ruff-audit.yml": "audit_skip_plan.py",
    "mypy-audit.yml": "audit_skip_plan.py",
    "small-audits.yml": "audit_skip_plan.py",
    "gitgalaxy.yml": "audit_skip_plan.py",
}
# built, not spelled (a literal .md glob would list this test as a reader of every engine page)
NEG_ENGINE_PROSE = "!gitgalaxy/**/*" + ".md"
FILTERED = {  # a `paths:` filter that negates what the gate provably never reads
    "muninn.yml": None,  # positive list only: tests and docs never trigger it (test above)
    "cics-crucible.yml": "!gitgalaxy/tools/terabyte_log_scanning/**",
    "java-compile.yml": "!gitgalaxy/tools/cobol_to_java/README.md",
    "rosetta-audit.yml": NEG_ENGINE_PROSE,
    "ports-compile.yml": NEG_ENGINE_PROSE,
    "unicode-gauntlet.yml": NEG_ENGINE_PROSE,
}


@pytest.mark.parametrize("name", sorted(PLAN_GATED))
def test_item_4_plan_gated_workflows_consult_the_plan(name):
    text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
    assert PLAN_GATED[name] in text and "steps.plan.outputs.mode != 'none'" in text


@pytest.mark.parametrize("name", sorted(FILTERED))
def test_item_4_filtered_workflows_keep_a_path_filter_and_their_negation(name):
    paths = paths_of(name)
    assert paths
    negation = FILTERED[name]
    assert negation is None or negation in paths


def test_item_4_fact_crosscheck_never_runs_on_a_pull_request():
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "fact-crosscheck.yml").read_text(encoding="utf-8"))
    assert doc["jobs"]["crosscheck"]["if"] == "${{ github.event_name != 'pull_request' }}"
