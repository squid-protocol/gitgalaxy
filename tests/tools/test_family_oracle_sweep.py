# ruff: noqa: S101
"""#8863: the pinned-crucible sweep that fills the validity grid's pinned cells."""

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS.parents[1]))
sys.path.insert(0, str(TOOLS.parent))
sys.path.insert(0, str(TOOLS))
import family_oracle as fo  # noqa: E402
import family_oracle_sweep as sweep  # noqa: E402

BASELINE = json.loads(fo.BASELINE.read_text(encoding="utf-8"))


def test_the_label_names_the_current_pin():
    assert sweep.corpus_label() == f"language-crucible {sweep._crucible_pin.PINNED_TAG}"


def test_a_pinned_crucible_cell_carries_the_current_pin():
    """A cell measured on `language-crucible vX` while the pin is vY is a stale claim: rerun the sweep after a pin bump."""
    stale = [
        (lang, fam, cell["corpus"])
        for lang, fams in BASELINE["cells"].items()
        for fam, cell in fams.items()
        if cell["pinned"] and cell["corpus"] != sweep.corpus_label()
    ]
    assert not stale, f"rerun tests/tools/family_oracle_sweep.py --write after the pin bump: {stale[:5]}"


def test_every_baseline_language_is_swept():
    assert set(BASELINE["cells"]) <= set(sweep.languages())


def test_an_alias_is_not_a_grid_column():
    assert "bash" not in sweep.languages()
    assert sweep.languages()[0] == "python"


def test_the_scan_is_the_golden_masters_scan(tmp_path):
    cmd = sweep.scan_command(Path("/c/data"), tmp_path)
    assert cmd[:2] == ["galaxyscope", str(Path("/c/data"))]
    assert {"--db-only", "--file-speed", "--splicing-speed"} <= set(cmd)
    assert cmd[-1].startswith(str(tmp_path))


def test_a_missing_checkout_is_a_clear_error(tmp_path):
    with pytest.raises(SystemExit, match="not found"):
        sweep.crucible_data({"LANGUAGE_CRUCIBLE_PATH": str(tmp_path)})


def _cell(corpus, *, pinned, status="ok", n=50):
    return {"corpus": corpus, "pinned": pinned, "status": status, "n_oracle": n}


def test_a_newer_pin_replaces_an_older_pinned_cell_even_with_nothing_to_say():
    old = _cell("language-crucible v1.7.0", pinned=True, status="over-counts")
    assert not fo._keeps_old(old, _cell("language-crucible v1.8.0", pinned=True, status="no-instances", n=0))


def test_an_unpinned_cell_still_cannot_displace_a_pinned_one():
    assert fo._keeps_old(_cell("language-crucible v1.8.0", pinned=True), _cell("redis", pinned=False))
