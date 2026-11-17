"""#8322: the five Run B not-proven programs each carry one cause on our side, and the fix commit named for it is real.

The page `docs/language_status/blind1_run_b_causes.md` is the record; this pins its table: the set of programs, one cause
each from `trial.OUR_CAUSES`, every cited fix commit an ancestor of HEAD that the frozen engine does not contain, and
every blocker row present in port_blockers.md.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.source_text import read_source

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import trial  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "language_status" / "blind1_run_b_causes.md"
BLOCKERS = ROOT / "docs" / "language_status" / "port_blockers.md"
FROZEN = "5e4575d77"
PROGRAMS = {"HCIMDB01", "HCIPDB01", "HCITDB01", "HCIVDB01", "HCMADB02"}
ROW = re.compile(r"^\| `(?P<prog>[A-Z0-9]+)` \|(?P<what>.*)\|(?P<fixes>[^|]*)\| (?P<row>P\d+) \|$", re.M)
SHA = re.compile(r"`([0-9a-f]{9})`")


def _rows():
    rows = list(ROW.finditer(read_source(PAGE).text))
    return [(m["prog"], m["fixes"], m["row"]) for m in rows]


def _git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=False)


def test_the_page_names_exactly_the_five_programs_once():
    progs = [p for p, _, _ in _rows()]
    assert sorted(progs) == sorted(PROGRAMS)


def test_every_program_has_a_cause_on_our_side():
    text = read_source(PAGE).text
    assert "**`engine`**" in text
    assert "engine" in trial.OUR_CAUSES


def test_every_blocker_row_exists():
    blockers = read_source(BLOCKERS).text
    for prog, _, row in _rows():
        assert re.search(rf"^\| {row} \|", blockers, re.M), f"{prog}: {row} is not in port_blockers.md"


def test_every_cited_fix_is_after_the_frozen_engine():
    if _git("rev-parse", "--git-dir").returncode != 0 or _git("cat-file", "-e", FROZEN).returncode != 0:
        pytest.skip("needs the git history with the frozen engine commit")
    for prog, fixes, _ in _rows():
        shas = SHA.findall(fixes)
        assert shas, f"{prog}: no fix commit cited"
        for sha in shas:
            assert _git("merge-base", "--is-ancestor", sha, "HEAD").returncode == 0, f"{prog}: {sha} not in HEAD"
            assert _git("merge-base", "--is-ancestor", sha, FROZEN).returncode != 0, (
                f"{prog}: {sha} is in the frozen engine"
            )
