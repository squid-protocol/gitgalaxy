"""#8858: Python regex_execution also counts methods called on a compiled pattern."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

RULE = LANGUAGE_DEFINITIONS["python"]["rules"]["regex_execution"]


def _n(src):
    return len(RULE.findall(src))


def test_issue_reproduction_finditer_on_compiled_pattern():
    src = 'import re\nPAT = re.compile("a+")\n\ndef f(s):\n    return [m.group(0) for m in PAT.finditer(s)]\n'
    assert _n("return [m.group(0) for m in PAT.finditer(s)]") == 1
    assert _n(src) == 2  # the compile and the finditer


def test_issue_reproduction_fullmatch_on_compiled_pattern():
    assert _n("return PAT.fullmatch(s)") == 1


@pytest.mark.parametrize("name", ["finditer", "fullmatch", "findall", "subn", "match", "search"])
def test_method_forms_count(name):
    assert _n(f"x = PAT.{name}(s)") == 1
    assert _n(f"x = self._pat.{name} (s)") == 1
    assert _n(f"x = re.compile('a').{name}(s)") == 2


@pytest.mark.parametrize(
    "name", ["compile", "search", "match", "fullmatch", "sub", "subn", "findall", "finditer", "split"]
)
def test_module_forms_count_once(name):
    assert _n(f"x = re.{name}('a', s)") == 1


@pytest.mark.parametrize(
    "src",
    [
        "research(x)",
        "matched = 1",
        "x = PAT.match",
        "x = PAT.search + 1",
        "pre.match",
        "def search(self): pass",
        "x = obj.researcher(s)",
        "x = obj.rematch(s)",
        "x = refinditer(s)",
    ],
)
def test_non_regex_shapes_do_not_count(src):
    assert _n(src) == 0
