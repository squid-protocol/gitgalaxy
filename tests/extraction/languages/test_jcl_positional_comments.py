"""jcl's `//*` comment statements get a line-aligned positional comment surface.

The positional stream feeds the function-grain comment rules (a TODO inside a step is that
step's planned debt) and header-comment detection. jcl used to contribute a blank stream, so
every jcl step read as uncommented. JES3 control verbs (`//*MAIN`) stay code.
"""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

JOB = """//PAYROLL  JOB (ACCT),'NIGHTLY',CLASS=A
//*  Step 1 sorts the payroll extract by employee id.
//SORT01   EXEC PGM=SORT
//*  TODO: replace this hardcoded dataset name
//SORTIN   DD DSN=PROD.PAYROLL.EXTRACT,DISP=SHR
//*MAIN CLASS=BATCH
//STEP02   EXEC PGM=PAYCALC
"""


def _prism():
    return Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


def test_comment_statements_keep_their_lines_and_jes3_verbs_do_not():
    raw = JOB.split("\n")
    pos = _prism().split_positional_comment_stream(JOB, "jcl").split("\n")
    assert len(pos) == len(raw)
    kept = {i + 1: line for i, line in enumerate(pos) if line}
    assert kept == {2: raw[1], 4: raw[3]}, "only the two //* comment statements, verbatim, at their own lines"


def test_a_todo_inside_a_step_is_that_steps_planned_debt():
    prism = _prism()
    streams = prism.split_streams(JOB, "jcl")
    result = StructuralExtractor("jcl", LANGUAGE_DEFINITIONS).splice(
        streams["code_stream"],
        streams["comment_stream"],
        raw_content=JOB,
        positional_comment_stream=prism.split_positional_comment_stream(JOB, "jcl"),
    )
    debt = {f["name"]: f.get("hit_vector", {}).get("planned_debt", 0) for f in result["functions"]}
    assert debt == {"SORT01": 1, "STEP02": 0}
