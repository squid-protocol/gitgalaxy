"""#4731: the evidence fingerprints per component -- a change stales only the records that use the component.

Cheap: hashing and JSON on a throwaway copy of the files, no Docker. The components and who uses them are
tests/tools/evidence.py COMPONENTS (+ the generator's det modules and runtime classes); these tests move one
component's bytes and ask which targets go stale, with the rule evidence.status applies to a record.
"""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import evidence as ev  # noqa: E402

REPO = ev.REPO_ROOT


def _find(pred):
    return next(t for t in ev.targets() if pred(t))


BATCH = _find(lambda t: t.kind == "batch" and not t.db2)
CALL = _find(lambda t: t.kind == "call")
ONLINE = _find(lambda t: t.kind == "cics" and not t.db2 and not t.programs)
DB2_ONLINE = _find(lambda t: t.kind == "cics" and t.db2)
LINKING = _find(lambda t: t.kind == "cics" and t.programs)
CRUCIBLE = _find(lambda t: t.kind == "crucible")
EQUIVALENCE = [t for t in ev.targets() if t.kind != "crucible"]
ALL = ev.targets()


class Tree:
    """The repo's files with some bytes appended: what compute_inputs sees after an edit to them."""

    def __init__(self, *paths: str, replace: dict[str, bytes] | None = None):
        self.edits = {**(replace or {}), **{p: (REPO / p).read_bytes() + b"\n// edited\n" for p in paths}}

    def read(self, p: str) -> bytes:
        return self.edits[p] if p in self.edits else (REPO / p).read_bytes()


_STORED: dict[str, dict] = {}


def specs(t, tree: Tree | None = None) -> dict:
    return ev.spec_inputs(t, ev._files_now(), tree.read if tree else None)


def stale_after(t, *paths: str) -> list[str]:
    """The inputs of a record proven on the tree as it is that are stale once `paths` change."""
    stored = _STORED.setdefault(t.key, specs(t))
    return ev.changed(stored, specs(t, Tree(*paths)), ev.COMPONENT_INPUTS)


def stale_set(*paths: str) -> set[str]:
    return {t.key for t in ALL if stale_after(t, *paths)}


def keys(pred) -> set[str]:
    return {t.key for t in ALL if pred(t)}


# ---- the partition is exact ----------------------------------------------------------------------------------------
def test_the_components_partition_each_input():
    """No file escapes: every file the whole-input fingerprint covers is in some component, so a change to it moves the
    component fingerprints of the targets that use that component (representatives of each kind, a crucible port among
    them, which uses everything it has)."""
    reps = (CRUCIBLE, LINKING, DB2_ONLINE, ONLINE, BATCH, CALL)
    for name in ev.COMPONENT_INPUTS:
        every = {p for t in reps for p in ev._match(ev._files_now(), t.specs[name]["paths"], t.specs[name]["exclude"])}
        for path in sorted(every):
            moved = False
            for t in reps:
                before = _STORED.setdefault(t.key, specs(t))[name]
                if path in ev._match(ev._files_now(), t.specs[name]["paths"], t.specs[name]["exclude"]):
                    after = specs(t, Tree(path))[name]
                    assert before["sha256"] != after["sha256"]
                    moved |= before["components"] != after["components"]
            assert moved, f"{path} is in no component any kind of target uses"


def test_a_target_that_uses_a_component_holds_exactly_its_files():
    """compute_inputs stores components for the three inputs only; the whole-input fingerprint is unchanged by them."""
    inputs = ev.compute_inputs(ONLINE)
    for name in ev.COMPONENT_INPUTS:
        assert inputs[name]["components"] and all(len(v) == 64 for v in inputs[name]["components"].values())
    for name in ("port", "case"):
        assert "components" not in inputs[name]


def test_the_whole_input_digest_does_not_depend_on_components():
    """A record's `digest` (what an approval signs) is over the whole-input fingerprints, as before #4731."""
    inputs = ev.compute_inputs(ONLINE)
    assert inputs["digest"] == ev.json_sha256({k: inputs[k]["sha256"] for k in ev.INPUTS})


# ---- the acceptance cases ---------------------------------------------------------------------------------------------
def test_a_cics_stub_change_stales_no_batch_case():
    stale = stale_set("tests/equivalence/cics/ggcics.c")
    assert stale == keys(lambda t: t.kind in ("cics",)), sorted(stale)
    assert not any(k in stale for k in keys(lambda t: t.kind in ("batch", "call")))
    # ... and the CICS harness module: online, call (its COMMAREA encoding), crucible and (were there one) a batch Db2 case that
    # imports it for SQL faults; no plain batch case
    stale = stale_set("tests/tools/equivalence_cics.py")
    assert BATCH.key not in stale and ONLINE.key in stale and CRUCIBLE.key in stale


def test_a_detsql_change_stales_only_db2_cases_that_use_it():
    path = "gitgalaxy/tools/cobol_to_java/det/cobolrt/sql/DetSql.java"
    stale = stale_set(path)
    # the runtime ships with a det translation: a case that LINKs programs (cbsa-inqacc is Db2 and does), a crucible
    # port, or a port that names it. A Db2 case that neither LINKs nor names it has no DetSql to be stale on.
    assert stale == keys(lambda t: t.programs or t.kind == "crucible"), sorted(stale)
    assert stale <= keys(lambda t: t.db2 or t.programs or t.kind == "crucible") and DB2_ONLINE.key in stale
    assert BATCH.key not in stale and CALL.key not in stale and ONLINE.key not in stale
    # the Db2 layer of the oracle and the harness: Db2 cases (and a crucible port, which uses everything)
    assert stale_set("tests/equivalence/db2/ggsql.c") == keys(lambda t: t.db2)  # (a crucible port has no oracle input)
    assert stale_set("tests/tools/equivalence_db2.py") == keys(lambda t: t.db2 or t.kind == "crucible")


def test_a_shared_cobol_java_change_stales_every_case_that_ships_the_runtime():
    path = "gitgalaxy/tools/cobol_to_java/det/cobolrt/Cobol.java"
    stale = stale_set(path)
    assert stale == keys(lambda t: t.programs or t.kind == "crucible") | {
        t.key for t in ALL if "generator" in stale_after(t, path)
    }
    # a case that LINKs programs (their det translation ships the runtime) and a crucible port: stale
    assert LINKING.key in stale and CRUCIBLE.key in stale
    # a port that names the runtime ships it: stale (checked in the next test); one that does not, and does not LINK, is not
    assert ONLINE.key not in stale and BATCH.key not in stale


def test_a_port_that_names_a_runtime_class_uses_it():
    """The runtime classes a port's own Java names (comments aside) are its, with whatever they name in turn."""
    port = next(p for p in ev.port_files(BATCH) if p.endswith(".java"))
    text = (REPO / port).read_bytes() + b"\nclass X { void f() { DetSql.unitOfWork(null); } }\n"
    tree = Tree(replace={port: text})
    plain = specs(BATCH)["generator"]["components"]
    names = specs(BATCH, tree)["generator"]["components"]
    sql = "generator:cobolrt/sql/DetSql.java"
    assert sql not in plain and sql in names
    assert "generator:cobolrt/Field.java" in names  # DetSql names Field, Cobol: the closure
    comment = (REPO / port).read_bytes() + b"\n// DetSql is not used here\n/* DetSql */\n"
    assert sql not in specs(BATCH, Tree(replace={port: comment}))["generator"]["components"]


def test_a_det_module_change_stales_the_cases_that_import_it_or_translate_with_it():
    """program.py / sql.py / refine.py: the det translator's drivers -- run only for a case that LINKs programs (the
    harness imports no more of det than cics / cvda / source and what those import). gen.py: imported by det.cics, so
    by every case that uses the CICS harness -- not by a plain batch run."""
    base = "gitgalaxy/tools/cobol_to_java/det/"
    for mod in ("program", "sql", "refine"):
        stale = stale_set(f"{base}{mod}.py")
        assert stale == keys(lambda t: t.programs or t.kind == "crucible"), (mod, sorted(stale))
    gen = stale_set(f"{base}gen.py")
    assert gen == keys(lambda t: t.programs or t.kind == "crucible" or t.kind in ("cics", "call") or t.db2)
    assert BATCH.key not in gen
    assert BATCH.key in stale_set(f"{base}source.py")  # det.source: equivalence_common, any case


def test_a_forge_or_core_change_stales_everything():
    """The proof generates the whole estate with the controller's forges: no case is spared a forge change."""
    for p in (
        "gitgalaxy/tools/cobol_to_java/cobol_to_java_transaction_forge.py",
        "tests/tools/equivalence_common.py",
        "tests/tools/equivalence.py",
        "tests/equivalence/gnucobol.Dockerfile",
    ):
        want = {t.key for t in ALL if (t.kind != "crucible" or not p.endswith("Dockerfile"))}
        assert stale_set(p) == want, p


def test_an_unrelated_edit_stales_nothing():
    assert stale_set("tests/tools/evidence_report.py") == set()


def test_a_crucible_port_uses_every_component():
    inputs = ev.compute_inputs(CRUCIBLE)
    for name in ("harness", "generator"):
        for c in ev.COMPONENTS:
            if c.input == name:
                assert c.name in inputs[name]["components"], c.name
    assert any(k.startswith("generator:cobolrt/") for k in inputs["generator"]["components"])


# ---- backward compatible --------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ev.COMPONENT_INPUTS)
def test_a_record_without_components_keeps_the_whole_input_comparison(name):
    now = ev.compute_inputs(ONLINE)
    legacy = copy.deepcopy(now)
    for n in ev.COMPONENT_INPUTS:
        del legacy[n]["components"]
    assert ev.changed(legacy, now, ev.COMPONENT_INPUTS) == []
    legacy[name]["sha256"] = "0" * 64
    assert ev.changed(legacy, now, ev.COMPONENT_INPUTS) == [name]


def test_a_changed_whole_input_with_every_used_component_equal_is_current():
    """An edit to a component this target does not use moves the whole fingerprint and no component it holds."""
    stored = ev.compute_inputs(BATCH)
    now = copy.deepcopy(stored)
    now["oracle"]["sha256"] = "1" * 64  # (the cics stub changed: not in BATCH's components)
    assert ev.changed(stored, now, ev.COMPONENT_INPUTS) == []
    now["oracle"]["components"]["oracle:core"] = "2" * 64  # a used one
    assert ev.changed(stored, now, ev.COMPONENT_INPUTS) == ["oracle"]


def test_a_component_the_record_does_not_hold_counts_as_changed():
    stored = ev.compute_inputs(BATCH)
    now = copy.deepcopy(stored)
    now["harness"]["sha256"] = "1" * 64
    now["harness"]["components"]["harness:new"] = "3" * 64
    assert ev.changed(stored, now, ev.COMPONENT_INPUTS) == ["harness"]


def test_status_names_the_components_and_keeps_the_meaning_of_stale():
    t = ONLINE
    rec = ev.load(t)
    assert rec is not None
    rec = copy.deepcopy(rec)
    now = ev.compute_inputs(t, rec.get("differences"))
    rec["inputs"] = now
    rec["proof"] = {**rec["proof"], "verdict": "proven", "inputs_digest": now["digest"]}
    rec["reach"] = {**rec["reach"], "unproven": [m for m in rec["reach"]["unproven"] if m["kind"] != "ported_unproven"],
                    "port_sha256": ev.tree_sha256(ev.port_files(t))}  # fmt: skip
    assert ev.status(rec, t)["stale"] == []
    rec["inputs"]["oracle"]["sha256"] = "0" * 64
    rec["inputs"]["oracle"]["components"]["oracle:cics-stub"] = "0" * 64
    st = ev.status(rec, t)
    assert st["status"] == "stale" and st["stale"] == ["oracle"] and st["blocking"] == []
    assert st["stale_components"] == {"oracle": ["oracle:cics-stub"]}
    assert "stale: oracle changed since the proof" in st["reasons"]


def test_validate_checks_the_components():
    rec = copy.deepcopy(ev.load(ONLINE))
    rec["inputs"]["harness"]["components"] = {"harness:core": "not a sha"}
    assert any("components" in e for e in ev.validate(rec))


# ---- the committed records ---------------------------------------------------------------------------------------------
def test_every_committed_component_fingerprint_is_a_set_the_tree_could_produce():
    """A record that holds components holds only components of its input today (a renamed component is a re-proof)."""
    for t in ALL:
        rec = ev.load(t)
        for name in ev.COMPONENT_INPUTS:
            held = ((rec or {}).get("inputs") or {}).get(name, {}).get("components")
            if held is None:
                continue
            known = ev.compute_inputs(t)[name]["components"]
            assert set(held) <= set(known) | {c for c in held if c.startswith(("generator:", "harness:", "oracle:"))}


def test_the_declared_unused_paths_are_not_imported_by_the_code_that_runs():
    """The guard under the 'unused' rules: a plain batch run (equivalence.py with no Db2) must not import
    equivalence_cics / equivalence_call / cics_crucible at module level, nor the module-level code of equivalence_db2
    on its own -- the lazy imports it has are inside the Db2 / call / cics branches the table names."""
    import ast

    tools = REPO / "tests" / "tools"
    top = ast.parse((tools / "equivalence.py").read_text(encoding="utf-8"))
    imported = {a.name for n in top.body if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module for n in top.body if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {"equivalence_cics", "equivalence_call", "cics_crucible", "cics_crucible_compare"}, imported
    java = ast.parse((tools / "equivalence_java.py").read_text(encoding="utf-8"))
    imported = {a.name for n in java.body if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module for n in java.body if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {"equivalence_cics", "equivalence_call", "equivalence_db2", "cics_crucible"}, imported
