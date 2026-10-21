"""DOOM-rosetta (#5619): zero drift of the pinned DOOM ports against ``tests/golden_doom_rosetta``.

Opt-in: ``pytest -m doom_rosetta`` fetches each port at its manifest SHA (never committed), rescans it with the
engine and diffs the measurements against the golden; a failure names the port, the file and the field. Bless with
``tests/tools/doom_rosetta_check.py --update --yes``. ``DOOM_ROSETTA_PORTS=a,b`` narrows the run (the CI shards),
``DOOM_SPEEDRUN_WORK`` moves the clone cache (outside the repo). It skips itself unless the marker expression selects
it, because ``smoke-test.yml`` replaces ``addopts`` with its own ``-m`` and would otherwise run all of it.
The unmarked tests at the bottom are fast and always run.
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import doom_rosetta_check as check  # noqa: E402
import doom_speedrun  # noqa: E402

PORTS = doom_speedrun.read_manifest()
NAMES = [r["name"] for r in PORTS]
ONLY = [n for n in os.environ.get("DOOM_ROSETTA_PORTS", "").split(",") if n]


def _selected(config):
    expr = config.getoption("markexpr", "") or ""
    return "doom_rosetta" in expr and "not doom_rosetta" not in expr


@pytest.mark.doom_rosetta
@pytest.mark.parametrize("row", [r for r in PORTS if not ONLY or r["name"] in ONLY], ids=lambda r: r["name"])
def test_port_matches_golden(row, request):
    if not _selected(request.config):
        pytest.skip("opt-in: run with `pytest -m doom_rosetta`")
    assert shutil.which("ctags"), "Universal Ctags is required on PATH (the functions check)"
    work = Path(os.environ.get("DOOM_SPEEDRUN_WORK", doom_speedrun.DEFAULT_WORK))
    report, golden = check.check_port(row, work)
    assert not report, f"\n{report}\n(bless an intended change with tests/tools/doom_rosetta_check.py --update --yes)"
    assert golden["summary"]["expected_fails_met"], (
        f"{row['name']} fails {golden['summary']['fails']!r}, the manifest expects {row['expected_fails']!r}"
    )


def test_every_manifest_port_has_a_golden_and_no_other_does():
    on_disk = {p.name.removesuffix(".json.gz") for p in check.GOLDEN_DIR.glob("*.json.gz")}
    assert on_disk == set(NAMES)


def test_manifest_expected_fails_are_known_checks():
    known = {"coverage", "language", "functions", "typosquat", "credentials", "health"}
    for row in PORTS:
        assert set((row["expected_fails"] or "").split()) <= known, row["name"]


def _golden(files, **summary):
    return {"sha": "a", "summary": {"fails": "", **summary}, "files": files, "exclusions": {"x/y.c": "vendor"}}


def test_func_hash_ignores_order_and_carries_no_names():
    a = [("f", 3, 5, 1), ("g", 9, 2, 1)]
    assert check.func_hash(a) == check.func_hash(a[::-1])
    assert check.func_hash(a) != check.func_hash([("f", 3, 5, 2), ("g", 9, 2, 1)])  # complexity moved
    assert len(check.func_hash(a)) == 16


def test_diff_names_the_file_and_the_field():
    old = _golden({"a.c": ["c", 10, 2, 0, "h1"], "b.c": ["c", 5, 1, 0, "h2"]}, functions=3)
    new = _golden({"a.c": ["c", 10, 3, 0, "h9"], "c.c": ["c", 1, 0, 0, "h3"]}, functions=4)
    new["exclusions"] = {}
    lines = check.diff_golden(old, new)
    assert "summary.functions: 3 -> 4" in lines
    assert "file a.c: functions 2 -> 3, func_hash 'h1' -> 'h9'" in lines
    assert "file added: c.c" in lines and "file removed: b.c" in lines
    assert "exclusion removed: x/y.c" in lines
    assert check.diff_golden(old, old) == []


def test_report_caps_long_diffs():
    text = check.format_report("p", [f"l{i}" for i in range(100)], limit=5)
    assert "100 difference(s)" in text and "95 more" in text


def test_golden_write_is_byte_stable(tmp_path, monkeypatch):
    monkeypatch.setattr(check, "GOLDEN_DIR", tmp_path)
    golden = _golden({"a.c": ["c", 1, 1, 0, "h"]})
    check.write_golden("p", golden)
    first = (tmp_path / "p.json.gz").read_bytes()
    check.write_golden("p", golden)
    assert (tmp_path / "p.json.gz").read_bytes() == first
    assert check.read_golden("p") == golden
    assert check.read_golden("absent") is None
