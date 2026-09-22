from gitgalaxy.standards.language_standards.languages.mlir import DEFINITION
from _strict_harness import assert_redos_immune

def test_mlir_calls_out():
    pattern = DEFINITION["rules"]["calls_out"]
    
    assert pattern.groups == 1
    
    # Positives
    assert pattern.findall("call @callee(...)") == ["callee"]
    assert pattern.findall("func.call @callee(...)") == ["callee"]
    assert pattern.findall("call @my.func$name()") == ["my.func$name"]
    
    # Negatives
    assert pattern.findall("return %val") == []
    assert pattern.findall("arith.addi %a, %b") == []
    
    # ReDoS check
    assert_redos_immune(pattern, "call @" + "a" * 50000 + "!", timeout_sec=2.0)
