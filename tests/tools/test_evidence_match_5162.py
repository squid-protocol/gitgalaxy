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


def _old_linked_ports(case):
    """The per-LINKed-program glob + case.json read equivalence_target did before the index was built once."""
    data = ev._case_json(case)
    ports = [data.get("port_from", case), *data.get("uses_ports", [])]
    for extra in data.get("programs", []):
        prog = extra["program"].upper()
        for other in sorted(p.parent.name for p in ev.CASES.glob("*/case.json")):
            if (
                other not in ports
                and (ev.CASES / other / "port").is_dir()
                and ev._case_json(other).get("program", "").upper() == prog
            ):
                ports.append(other)
    return ports


def test_linked_program_ports_are_the_same_as_the_per_program_scan():
    linked = [
        p.parent.name for p in sorted(ev.CASES.glob("*/case.json")) if ev._case_json(p.parent.name).get("programs")
    ]
    assert linked
    for case in linked:
        want = [f"tests/equivalence/{c}/port/**" for c in _old_linked_ports(case)]
        assert ev.equivalence_target(case).specs["port"]["paths"] == want
