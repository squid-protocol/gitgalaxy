import pytest
from gitgalaxy.standards.language_standards.languages.hlo import DEFINITION
from _strict_harness import assert_redos_immune

def test_hlo_calls_out():
    pattern = DEFINITION["rules"]["calls_out"]
    
    assert pattern.groups == 1
    
    # Positives
    assert pattern.findall("calls=%my-computation") == ["my-computation"]
    assert pattern.findall("to_apply={%my-computation}") == ["my-computation"]
    assert pattern.findall("calls = %func.name") == ["func.name"]
    assert pattern.findall("to_apply = {%func}") == ["func"]
    assert pattern.findall("calls=%func_123") == ["func_123"]
    
    # Negatives
    assert pattern.findall("name=%something") == []
    
    # ReDoS check
    assert_redos_immune(pattern, "calls=%" + "a" * 50000 + "!", timeout_sec=2.0)
