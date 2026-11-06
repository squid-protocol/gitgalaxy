"""#4108 slice 23: go and java carry no alternation member that starts with a non-word char behind a leading `\\b`
(`\\b(?:a|\\.b\\()` can never match `.b(` after whitespace or punctuation). Structural guard plus behaviour pins."""

import re

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

WORDISH = re.compile(r"(\\[wbdsWDS]|[A-Za-z0-9_(\[]|[^\x00-\x7f])")
# Shared across every language (_shared_patterns.py, `@todo`): one sweep for all languages, not a go/java slice.
SHARED = {"planned_debt", "fragile_debt"}


def _compiled(lang):
    for key, val in LANGUAGE_DEFINITIONS[lang]["rules"].items():
        for p in val if isinstance(val, (list, tuple)) else [val]:
            if getattr(p, "pattern", None):
                yield key, p.pattern


def _bad_alternatives(pattern):
    """Top-level alternatives of every `\\b(...)` group that begin with a literal non-word char."""
    bad = []
    for m in re.finditer(r"\\b\((?:\?:)?", pattern):
        i = m.end()
        depth, j, cur, alts = 1, i, i, []
        while j < len(pattern) and depth:
            c = pattern[j]
            if c == "\\":
                j += 2
                continue
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            elif c == "|" and depth == 1:
                alts.append(pattern[cur:j])
                cur = j + 1
            j += 1
        alts.append(pattern[cur : j - 1])
        bad += [a for a in alts if a and not WORDISH.match(a) and not a.startswith("?")]
    return bad


@pytest.mark.parametrize("lang", ["go", "java"])
def test_no_nonword_first_alternative_behind_leading_boundary(lang):
    offenders = {
        (k, tuple(_bad_alternatives(p))) for k, p in _compiled(lang) if k not in SHARED and _bad_alternatives(p)
    }
    assert not offenders


def test_guard_detects_the_defect_shape():
    assert _bad_alternatives(r"\b(?:a|\.b\()") == [r"\.b\("]
    assert not _bad_alternatives(r"\b(?:a|b)\b|\.b\(")


GO_RE = LANGUAGE_DEFINITIONS["go"]["rules"]["regex_execution"]
GO_TIME = LANGUAGE_DEFINITIONS["go"]["rules"]["time_date_logic"]
JAVA_RE = LANGUAGE_DEFINITIONS["java"]["rules"]["regex_execution"]


@pytest.mark.parametrize(
    "line", ["ok := re.MatchString(s)", "\tx.MatchString(s)", "(re).MatchString(s)", "f().MatchString(s)"]
)
def test_go_matchstring_fires(line):
    assert GO_RE.search(line)


@pytest.mark.parametrize("line", ["MatchStringer(s)", "x := regexp.MustCompile(p)"])
def test_go_regex_boundaries(line):
    assert bool(GO_RE.search(line)) == ("MustCompile" in line)


@pytest.mark.parametrize("line", ["t := time.Now()", "\tx(time.Now())", "time.Sleep(d)"])
def test_go_time_fires(line):
    assert GO_TIME.search(line)


@pytest.mark.parametrize("line", ["s.matches(re)", "f().matches(x)", "  .matches(x)", "Pattern.compile(p)"])
def test_java_matches_fires(line):
    assert JAVA_RE.search(line)


def test_java_matches_no_fire():
    assert not JAVA_RE.search("rematchesx(s)")
