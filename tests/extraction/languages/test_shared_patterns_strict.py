from gitgalaxy.standards.language_standards._shared_patterns import CALLS_OUT_C_STYLE

from _strict_harness import assert_redos_immune

def test_calls_out_c_style_strict():
    """
    Epic #3264: Validate the universal C-style invocation pattern.
    """
    assert CALLS_OUT_C_STYLE is not None
    
    # 1. Valid matches
    assert CALLS_OUT_C_STYLE.findall("foo()") == ["foo"]
    assert CALLS_OUT_C_STYLE.findall("foo (  )") == ["foo"]
    assert CALLS_OUT_C_STYLE.findall("my_func(x, y)") == ["my_func"]
    assert CALLS_OUT_C_STYLE.findall("Class.method(") == ["method"]
    
    # 2. ReDoS immunity
    # Create a long string that ALMOST matches but fails at the end.
    # The pattern is: \b([a-zA-Z_]\w*)\s*\(
    # Adversarial payload: a valid identifier, followed by 10,000 spaces, but NO parenthesis.
    payload = "foo" + (" " * 10000) + "x"
    assert_redos_immune(CALLS_OUT_C_STYLE, payload)
    
    # Another payload: 10,000 valid identifier characters, then a space, then no parenthesis
    payload2 = "a" * 10000 + " " + "x"
    assert_redos_immune(CALLS_OUT_C_STYLE, payload2)
