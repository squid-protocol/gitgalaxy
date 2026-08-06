import pytest
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

M4_RULES = LANGUAGE_DEFINITIONS["m4"]["rules"]

_ADVERSARIAL_CASES = [
    # func_start
    ("func_start", "define(`foo', `bar')", "some_cmd define(`foo', `bar')"),
    ("func_start", "\tAC_DEFUN([macro], [])", "dnl AC_DEFUN([macro])"),
    ("func_start", "  m4_define ( [foo], [bar] )", "# m4_define([foo])"),
    ("func_start", "AC_DEFUN_ONCE([foo])", "AC_DEFUN_ONCE_EXTRA([foo])"),
    ("func_start", "AU_DEFUN([foo], [bar])", "echo AU_DEFUN"),
    ("func_start", "m4_defun([foo], [bar])", "m4_defun_not"),
    
    # args
    ("args", "$1", "$"),
    ("args", "$123", "${123}"),
    ("args", "$*", "$a"),
    ("args", "$#", "$$"),
    ("args", "$0", "$_"),

    # branch
    ("branch", "AS_IF([test], [true])", "AS_IF_SUFFIX"),
    ("branch", "ifelse(A, B, C)", "my_ifelse()"),
    ("branch", "m4_case([$1], [a], [b])", "m4_case_X"),
    ("branch", "m4_ifval([$1], [yes])", "m4_ifvalue"),
    ("branch", "AS_CASE([$x], [y], [z])", "HAS_CASE"),
    
    # structural_boundaries
    ("structural_boundaries", "divert(-1)", "divert_text"),
    ("structural_boundaries", "m4_divert(1)", "m4_divert_text"),
    ("structural_boundaries", "AC_REQUIRE([foo])", "AC_REQUIRE_CPP"),
    ("structural_boundaries", "undivert(1)", "undiverted"),
    ("structural_boundaries", "m4_require([foo])", "m4_requirements"),
]

@pytest.mark.parametrize("signature,positive,negative", _ADVERSARIAL_CASES)
def test_m4_adversarial(signature, positive, negative):
    pattern = M4_RULES[signature]
    assert pattern is not None
    assert pattern.search(positive), f"Failed positive: {positive}"
    if negative:
        assert not pattern.search(negative), f"Failed negative: {negative}"
