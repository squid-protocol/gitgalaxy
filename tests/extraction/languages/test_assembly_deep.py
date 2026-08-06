import sys
from pathlib import Path
import pytest

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

ASM_RULES = LANGUAGE_DEFINITIONS["assembly"]["rules"]

_ASM_DEEP_CASES = [
    # branch
    ("branch", "\tje .L1", "\tmov eax, ebx"),
    ("branch", "\tBNE label", "\tmov eax, ebx"),
    ("branch", "\tcall [rax+8]", "\tmov eax, ebx"),
    ("branch", "\tcbz x0, label", "\tmov x0, x1"),
    ("branch", "\ttbnz x0, #3, label", "\tmov x0, x1"),
    ("branch", "\tloop .retry", "\tmov eax, ebx"),
    ("branch", "\tblr x19", "\tmov eax, ebx"),
    
    # args
    
    
    
    
    
    
    
    
    # func_start
    ("func_start", "_start:\n", "\tmov eax, ebx"),
    ("func_start", "@main_loop:\n", "\tmov eax, ebx"),
    ("func_start", "?MyFunc@@YAHXZ:\n", "\tmov eax, ebx"),
    ("func_start", "my_func: ; comment", "\tmov eax, ebx"),
    ("func_start", "  valid_func : \n", "\tmov eax, ebx"),
    # Negative cases for func_start
    ("func_start", "\tmov eax, ebx", ".L123:\n"),
    ("func_start", "\tmov eax, ebx", "1:\n"),
    ("func_start", "\tmov eax, ebx", "\t.text:\n"),
    
    # class_start
    ("class_start", "my_struc struc", "\tmov eax, ebx"),
    ("class_start", "\t.struct my_struct", "\tmov eax, ebx"),
    ("class_start", "STRUCT my_struct", "\tmov eax, ebx"),
    ("class_start", "my_struct\tSTRUCT", "\tmov eax, ebx"),
    # Negative for class_start
    ("class_start", "\tmov eax, ebx", "my_struc\nstruc"),
    
    # structural_boundaries
    ("structural_boundaries", "\tmovabs rax, 0x123", "\tjmp foo"),
    ("structural_boundaries", "\tmovzx eax, byte ptr [ebx]", "\tjmp foo"),
    ("structural_boundaries", "\tldrb w0, [x1]", "\tjmp foo"),
    ("structural_boundaries", "\tstp x0, x1, [sp]", "\tjmp foo"),
    ("structural_boundaries", "\tinc qword ptr [rax]", "\tjmp foo"),
    ("structural_boundaries", "\tvmovdqu ymm0, ymm1", "\tjmp foo"),
]

@pytest.mark.parametrize("signature,positive,negative", _ASM_DEEP_CASES)
def test_assembly_signature_deep(signature, positive, negative):
    pattern = ASM_RULES[signature]
    assert pattern is not None
    if positive != "\tmov eax, ebx":
        assert pattern.search(positive), f"assembly {signature!r} failed to match positive case: {positive!r}"
    if negative != "\tmov eax, ebx":
        assert not pattern.search(negative), f"assembly {signature!r} incorrectly matched negative case: {negative!r}"
