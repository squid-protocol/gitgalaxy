"""#4203 (estate-crucible H-0028): in free-format COBOL a paragraph name may start in column 1,
so its own hyphen can sit in column 7. func_start's optional fixed-format margin (cols 1-6 +
the column-7 indicator) took `LOOKUP` as a sequence number and recorded the unit as `RATE`:
`\\b` before `RATE` held because a hyphen is not a regex word character, although it is a COBOL
name character. A name now starts only where no name character precedes it."""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
_FUNC_START = LANGUAGE_DEFINITIONS["cobol"]["rules"]["func_start"]

MODRATE = """\
>>SOURCE FORMAT FREE
IDENTIFICATION DIVISION.
PROGRAM-ID. MODRATE.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 WS-FOUND PIC X.
PROCEDURE DIVISION.
MAIN-PARA.
    PERFORM LOOKUP-RATE
    PERFORM ABCDEF-GHIJ
    GOBACK.
LOOKUP-RATE.
    MOVE 'Y' TO WS-FOUND.
ABCDEF-GHIJ.
    MOVE 'N' TO WS-FOUND.
"""


def _names(src: str) -> list[str]:
    st = _PRISM.split_streams(src, "cobol")
    out = StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(
        code_stream=st["code_stream"],
        comment_stream=st["comment_stream"],
        raw_content=src,
        positional_comment_stream=_PRISM.split_positional_comment_stream(src, "cobol"),
    )
    return [f["name"] for f in out["functions"] if f["name"] != "__global_context__"]


def test_a_column_1_paragraph_keeps_its_whole_name():
    assert _names(MODRATE) == ["MAIN-PARA", "LOOKUP-RATE", "ABCDEF-GHIJ"]


def test_the_fixed_format_margin_still_comes_off():
    got = {t: [m.group(1) for m in _FUNC_START.finditer(t)] for t in (
        "000100 LOOKUP-RATE.\n",  # sequence number + blank indicator
        "064100DDEBUG-LINE-A.\n",  # debug indicator glued to the name
        "TargetFunc.\n",  # the greedy-margin trap the old `\\b` guarded
        "       MAIN-PARA SECTION.\n",
    )}  # fmt: skip
    assert got == {
        "000100 LOOKUP-RATE.\n": ["LOOKUP-RATE"],
        "064100DDEBUG-LINE-A.\n": ["DEBUG-LINE-A"],
        "TargetFunc.\n": ["TargetFunc"],
        "       MAIN-PARA SECTION.\n": ["MAIN-PARA"],
    }
