"""Go regex_execution: `.MatchString` must fire after `)` / `]`, not only after a word char (#4108)."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

RULE = LANGUAGE_DEFINITIONS["go"]["rules"]["regex_execution"]


@pytest.mark.parametrize(
    "text",
    [
        "ok := re.MatchString(s)",
        "ok := regexp.MustCompile(`a`).MatchString(s)",
        "ok := pats[0].MatchString(s)",
        "re := regexp.Compile(p)",
    ],
)
def test_fires(text):
    assert RULE.search(text)


@pytest.mark.parametrize("text", ["x.MatchStrings(s)", "xregexp.Compilex(p)", "y := MatchString(s)"])
def test_no_fire(text):
    assert not RULE.search(text)
