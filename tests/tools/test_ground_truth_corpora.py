"""#5543 (b): a busy-layout part scans only the corpora its pytest share reads; the ledger-gate part scans all."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))
import ground_truth_corpora as gc  # noqa: E402

NAMES = gc.corpus_names()
COMPLETENESS = "tests/cobol_mainframe/test_completeness.py::test_pinned_corpus_completeness"
REFRACTION = "tests/cobol_mainframe/test_refraction_differential.py::test_full_corpus_no_new_unexplained"
LINEAGE = "tests/cobol_mainframe/test_template_file_lineage_4771.py::test_zecs_003_file_op_reaches_the_zc_id_file_store"
OTHER = "tests/cobol_mainframe/test_det_layout.py::test_something"


def test_a_per_corpus_test_reads_only_the_corpus_in_its_id():
    for base in (COMPLETENESS, REFRACTION):
        for name in NAMES:
            assert gc.corpora_for([f"{base}[{name}]", OTHER], NAMES) == [name]


def test_a_fixed_reader_names_its_corpus_and_a_mixed_share_is_the_union_in_manifest_order():
    assert gc.corpora_for([LINEAGE], NAMES) == ["zecs"]
    ids = [f"{COMPLETENESS}[{NAMES[3]}]", f"{COMPLETENESS}[{NAMES[1]}]", LINEAGE, OTHER]
    assert gc.corpora_for(ids, NAMES) == [n for n in NAMES if n in {NAMES[3], NAMES[1], "zecs"}]


def test_a_share_with_no_reader_scans_nothing():
    assert gc.corpora_for([OTHER, "tests/cobol_mainframe/test_a.py::test_b[x]"], NAMES) == []
    assert gc.corpora_for([f"{REFRACTION.split('::')[0]}::test_excerpt_no_new_unexplained[CardDemo]"], NAMES) == []


@pytest.mark.parametrize(
    "ids", [[], ["", "collected 3 items", "no tests ran"], [f"{COMPLETENESS}[not-a-corpus]"], [COMPLETENESS]]
)
def test_nothing_to_go_by_or_an_unplaceable_id_scans_every_corpus(ids):
    assert gc.corpora_for(ids, NAMES) == NAMES


def test_the_cli_scans_all_for_the_gate_part_and_when_the_file_is_missing(tmp_path, capsys):
    done = tmp_path / "collected.txt"
    done.write_text(f"{LINEAGE}\n\n1 test collected\n", encoding="utf-8")
    assert gc.main(["--collected", str(done)]) == 0
    assert capsys.readouterr().out.split() == ["zecs"]
    assert gc.main(["--all", "--collected", str(done)]) == 0
    assert capsys.readouterr().out.split() == NAMES
    assert gc.main(["--collected", str(tmp_path / "absent.txt")]) == 0
    assert capsys.readouterr().out.split() == NAMES


def test_every_test_module_that_scans_a_corpus_is_in_the_readers_table():
    """A new reader of a scan DB left out of READERS would pay a cold scan inside its test (the time ratchet fails it)."""
    call = re.compile(r"\b(?:mc|MC|mainframe_corpus)\.(?:scan|score)\(")
    found = {
        p.name for p in (ROOT / "tests" / "cobol_mainframe").glob("*.py") if call.search(p.read_text(encoding="utf-8"))
    }
    assert found == set(gc.READERS)
    for module, funcs in gc.READERS.items():
        text = (ROOT / "tests" / "cobol_mainframe" / module).read_text(encoding="utf-8")
        for func in funcs:
            assert f"def {func}(" in text, f"{module}: {func} is gone: update READERS"


def test_the_workflow_scans_by_share_except_in_the_gate_part():
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "mainframe-ground-truth.yml").read_text(encoding="utf-8"))
    steps = {s.get("name"): s for s in doc["jobs"]["ground-truth-part"]["steps"]}
    names = list(steps)
    listing, scan = steps["List this part's tests"], steps["Scan the pinned corpora in parallel"]
    assert "matrix.group != 1" in listing["if"] and listing["continue-on-error"] is True
    assert "--group ${{ matrix.group }}" in listing["run"] and "--splits ${{ matrix.parts }}" in listing["run"]
    assert "ground_truth_corpora.py ${{ matrix.group == 1 && '--all' || '' }}" in scan["run"]
    assert names.index("Fetch the pinned corpora") < names.index("List this part's tests") < names.index(scan["name"])
    gate = steps["Gate against the ground-truth ledger"]
    assert "matrix.group == 1" in gate["if"]  # the gate scores every corpus, so its part must have scanned them all
