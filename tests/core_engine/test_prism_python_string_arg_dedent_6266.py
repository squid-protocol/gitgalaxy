"""
#6266: a multi-line Python string that is a call argument (`execute('''..\\n''', (id,))`)
left its closing line's tail at column 0 once PRISM blanked the span, and the
indentation slicer read it as a dedent that ended the enclosing def (mood's
`map_state_to_cobol` kept 6 of ~100 lines, dropping its calls). Run through the real
PRISM config, as a scan does.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _code(src, lang="python"):
    return Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams(src, lang)["code_stream"]


def _funcs(code):
    return {f["name"]: f for f in StructuralExtractor("python", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]}


@pytest.mark.parametrize("quote", ['"""', "'''"])
def test_a_string_argument_does_not_end_the_def(quote):
    src = (
        "class X:\n"
        "    def run(self, sid):\n"
        f"        cur.execute({quote}\n"
        "            SELECT 1\n"
        f"        {quote}, (sid,))\n"
        "        self.after()\n"
        "        return {}\n"
        "\n"
        "    def after(self):\n"
        "        pass\n"
    )
    code = _code(src)
    assert code.count("\n") == src.count("\n")  # the line numbers still hold
    funcs = _funcs(code)
    assert funcs["run"]["loc"] >= 6  # reaches `return {}`, not the `execute(` line
    assert funcs["after"]["start_line"] == 9


def test_a_docstring_and_a_closing_only_line_are_still_blank():
    src = 'def f():\n    """doc\n    more\n    """\n    return 1\n'
    code = _code(src)
    assert code.split("\n")[2:4] == ["", ""]  # nothing follows a docstring: no filler
