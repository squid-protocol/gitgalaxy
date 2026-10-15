"""#5162: evidence._match (compiled alternation + memo) selects exactly what the per-pattern fnmatch loop did."""

import fnmatch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence as ev


def _old(files, pats, exc):
    def hit(p, ps):
        return any(p == x or fnmatch.fnmatchcase(p, x) for x in ps)

    return [p for p in files if hit(p, pats) and not hit(p, exc)]


FILES = ("a/b.cbl", "a/c.py", "a/[x].txt", "d/e/f.cbl", "README.md")


def test_match_equals_the_fnmatch_loop():
    for pats, exc in [(["a/*"], []), (["*.cbl"], ["d/*"]), (["a/[x].txt"], []), ([], []), (["nope"], ["a/*"])]:
        assert ev._match(FILES, pats, exc) == _old(FILES, pats, exc)


def test_every_target_spec_matches_as_before():
    files = ev._files_now()
    for t in ev.targets():
        for spec in t.specs.values():
            assert ev._match(files, spec["paths"], spec["exclude"]) == _old(files, spec["paths"], spec["exclude"])


def test_match_result_is_a_fresh_list():
    a = ev._match(FILES, ["a/*"], [])
    a.clear()
    assert ev._match(FILES, ["a/*"], [])
