import pytest
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

M4_RULES = LANGUAGE_DEFINITIONS["m4"]["rules"]

def test_spec_exposure():
    pattern = M4_RULES["spec_exposure"]
    assert pattern.search("[SPEC-123]")
    assert pattern.search("[audit]")
    
    # Should these match?
    print("special:", bool(pattern.search("[special]")))
    print("specific:", bool(pattern.search("[specific]")))
    print("inspector:", bool(pattern.search("[inspector]")))

test_spec_exposure()
