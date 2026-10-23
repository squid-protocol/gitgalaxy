"""#3073: the combined-alternation candidate finder never misses a rule that really matches."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import combined_alternation_parity as cap  # noqa: E402

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402


def test_overlapping_literals_are_not_consumed():
    # A plain `ab|bc` alternation eats the 'b' of 'ab' and never reports 'bc' in 'abc'.
    rules = {"r_ab": re.compile(r"abx?"), "r_bc": re.compile(r"bcd")}
    finder = cap.CandidateFinder(rules)
    missed, _widened, cands = cap.check_text(rules, finder, "abcd")
    assert not missed
    assert cands == {"r_ab", "r_bc"}


def test_same_start_literals_all_credited():
    # 'ab' and 'abc' start at one position; the longer rule is widened to a candidate, never lost.
    rules = {"short": re.compile(r"abq"), "long": re.compile(r"abcdef")}
    finder = cap.CandidateFinder(rules)
    missed, widened, cands = cap.check_text(rules, finder, "abcdef")
    assert not missed and "long" in cands
    assert widened <= {"short"}


def test_case_insensitive_rule_matches_folded_text():
    rules = {"ci": re.compile(r"select\s+from", re.I), "cs": re.compile(r"SELECT")}
    finder = cap.CandidateFinder(rules)
    for text in ("Select  From t", "select from", "SELECT 1", "nothing here"):
        missed, _w, _c = cap.check_text(rules, finder, text)
        assert not missed, text
    assert cap.CandidateFinder({"ci": rules["ci"]}).candidates("nothing here") == set()


def test_ungated_rule_is_always_a_candidate():
    rules = {"any": re.compile(r"\w")}
    assert cap.CandidateFinder(rules).candidates("zzz") == {"any"}


def test_registry_rules_have_no_missed_candidates_on_keyword_samples():
    text = "\n".join(
        ["def f(x): return x", "class A { void m() { if (a) { b(); } } }", "SELECT * FROM T; // TODO fix", "import os"]
    )
    for lang, defn in LANGUAGE_DEFINITIONS.items():
        rules = cap._rules_of(defn)
        if not rules:
            continue
        finder = cap.CandidateFinder(rules)
        missed, _w, _c = cap.check_text(rules, finder, text)
        assert not missed, (lang, missed)


def test_time_rules_reports_every_stage_and_splits_the_residual():
    rules = {f"r{i}": re.compile(f"tok{i}x?") for i in range(8)}
    finder = cap.CandidateFinder(rules)
    t = cap.time_rules(rules, finder, ["tok1 tok2 tok3", "nothing"])
    assert set(t) == {"gate_s", "finder_s", "sweep_s", "top5_s", "residual_s"}
    assert all(v >= 0.0 for v in t.values())
    assert abs(t["top5_s"] + t["residual_s"] - t["sweep_s"]) < 1e-9
