"""#8913: an Ada nested subprogram ends at its own `end Name;`; the parent keeps the lines after it.

Mode A used to run every unit to the next `func_start` match, so a parent lost its tail (and its
decisions) and the last nested subprogram took it."""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


def _functions(src):
    st = _PRISM.split_streams(src, "ada")
    out = StructuralExtractor("ada", LANGUAGE_DEFINITIONS).splice(
        code_stream=st["code_stream"],
        comment_stream=st["comment_stream"],
        raw_content=src,
        positional_comment_stream=_PRISM.split_positional_comment_stream(src, "ada"),
    )
    return {f["name"]: f for f in out["functions"]}


def _branch(f):
    return f["branch"]


ISSUE = """\
procedure C4 is
   procedure Inner is
   begin
      null;
   end Inner;
begin
   if X > 1 then
      Inner;
   end if;
end C4;
"""


def test_issue_case_parent_keeps_its_if():
    fns = _functions(ISSUE)
    assert _branch(fns["C4"]) == 1
    assert _branch(fns["Inner"]) == 0
    assert fns["Inner"]["end_line"] == 5
    assert fns["C4"]["end_line"] == 10


def test_two_siblings_and_two_levels():
    src = """\
procedure P is
   procedure A is
      procedure Deep is
      begin
         if X then
            null;
         end if;
      end Deep;
   begin
      null;
   end A;
   function B return Integer is
   begin
      return 1;
   end B;
begin
   while Y loop
      null;
   end loop;
end P;
"""
    fns = _functions(src)
    assert _branch(fns["Deep"]) == 1
    assert _branch(fns["A"]) == 0
    assert _branch(fns["B"]) == 0
    assert _branch(fns["P"]) == 1


@pytest.mark.parametrize("end_label", ["END INNER;", "end Inner ;", "end Pkg.Inner;"])
def test_end_label_spellings(end_label):
    src = ISSUE.replace("end Inner;", end_label)
    fns = _functions(src)
    assert _branch(fns["C4"]) == 1
    assert _branch(fns["Inner"]) == 0


def test_unlabelled_end_keeps_the_greedy_body():
    src = (
        "procedure A is\nbegin\n   if X then\n      null;\n   end if;\nend;\nprocedure B is\nbegin\n   null;\nend B;\n"
    )
    fns = _functions(src)
    assert _branch(fns["A"]) == 1
    assert _branch(fns["B"]) == 0


def test_flat_subprograms_unchanged():
    src = "procedure A is\nbegin\n   if X then\n      null;\n   end if;\nend A;\nprocedure B is\nbegin\n   null;\nend B;\n"
    fns = _functions(src)
    assert _branch(fns["A"]) == 1
    assert _branch(fns["B"]) == 0
