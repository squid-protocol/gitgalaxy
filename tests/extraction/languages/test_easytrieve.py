"""Easytrieve extraction splicing tests."""

import sys
from pathlib import Path

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from gitgalaxy.core.detector import StructuralExtractor


def _splice(code: str):
    return StructuralExtractor("easytrieve", LANGUAGE_DEFINITIONS).splice(code, "")


CODE = """* A comment
JOB INPUT FILEA
  GET FILEA
  IF A = B
    PRINT REPORT-1
  END-IF
  STOP EXECUTE

PROC MY-PROC
  X = 1
  EXIT
END-PROC

MACRO MY-MACRO
  DISPLAY 'HELLO'
END-MACRO
"""

def test_easytrieve_splicing_functions():
    result = _splice(CODE)
    funcs = result["functions"]
    assert len(funcs) == 3
    assert funcs[0]["name"] == "INPUT"
    assert funcs[1]["name"] == "MY-PROC"
    assert funcs[2]["name"] == "MY-MACRO"
    
    # Check lines
    lines = CODE.splitlines()
    assert lines[funcs[0]["start_line"] - 1].startswith("JOB INPUT")
    assert lines[funcs[1]["start_line"] - 1].startswith("PROC MY-PROC")
    assert lines[funcs[2]["start_line"] - 1].startswith("MACRO MY-MACRO")

def test_easytrieve_splicing_no_functions():
    code = "* just a comment\nGET FILEA\n"
    assert _splice(code)["functions"] == []

