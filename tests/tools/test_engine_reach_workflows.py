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
