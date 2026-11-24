"""Which PL/I files the answer key reads moves and procedure extents for (cobol_answer_key.pli_moves_files).

DSF ships 1,473 PL/I files, so its key reads a seeded sample. The first draw (25 files, seed 3491) was blind-reviewed, so
widening the sample must keep those files and add a second draw, never re-draw from scratch."""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cobol_answer_key as ak  # noqa: E402

DSF_KEY = Path(__file__).resolve().parent / "answer_key" / "dsf.json"


def _names(n):
    return [f"src/P{i:04d}.pli" for i in range(n)]


def test_widening_keeps_the_reviewed_first_draw_and_adds_a_second():
    files = _names(1473)
    chosen = ak.pli_moves_files(files)
    first_draw = random.Random(ak.PLI_MOVES_SEED).sample(sorted(files), ak.PLI_MOVES_BASE)
    assert len(chosen) == ak.PLI_MOVES_SAMPLE == 150
    assert set(first_draw) <= set(chosen)  # the reviewed files are never dropped
    assert len(set(chosen) - set(first_draw)) == ak.PLI_MOVES_SAMPLE - ak.PLI_MOVES_BASE
    assert chosen == sorted(chosen) and len(chosen) == len(set(chosen))


def test_the_draw_is_deterministic_and_independent_of_input_order():
    files = _names(1473)
    assert ak.pli_moves_files(files) == ak.pli_moves_files(list(reversed(files)))


def test_a_corpus_of_at_most_the_sample_size_keys_every_file():
    for n in (3, 25, 26, 149, 150):
        assert ak.pli_moves_files(_names(n)) == sorted(_names(n))


def test_draft_pli_moves_records_the_scope_and_drafts_every_chosen_file(tmp_path):
    for name in _names(160):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("P: PROC;\n  DCL X FIXED;\n  X = 1;\nEND P;\n", encoding="utf-8")
    drafted, scope = ak.draft_pli_moves(tmp_path)
    assert len(drafted) == 150
    assert scope == {
        "files": 160,
        "keyed": 150,
        "seed": ak.PLI_MOVES_SEED,
        "base": 25,
        "extension_seed": ak.PLI_MOVES_EXTENSION_SEED,
        "sample": 150,
    }
    assert all(not e["pli_moves_validated"] and e["verification"]["status"] == "draft" for e in drafted.values())


def test_a_small_corpus_has_no_seed_in_its_scope(tmp_path):
    for name in _names(4):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("P: PROC;\n  X = 1;\nEND P;\n", encoding="utf-8")
    _, scope = ak.draft_pli_moves(tmp_path)
    assert scope == {"files": 4, "keyed": 4, "seed": None}


def test_the_committed_dsf_key_agrees_with_its_own_scope():
    key = json.loads(DSF_KEY.read_text(encoding="utf-8"))
    scope = key["pli_moves_scope"]
    assert scope["keyed"] == len(key["pli_moves"])
    assert scope["files"] == 1473
    # the units the key reads are the moves files plus the named witnesses
    assert set(key["pli_moves"]) <= set(key["pli_units"])
