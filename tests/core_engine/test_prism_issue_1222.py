from gitgalaxy.core.prism import Prism


def test_issue_1222_apostrophe_in_comment_does_not_swallow_code():
    """
    Regression test for Issue #1222.
    Ensures that an apostrophe inside a comment (e.g. doesn't)
    does not false-open a string literal and swallow the rest of the file.
    """
    # Mocking standard_block language which JS uses.
    lang_defs = {
        "javascript": {
            "lexical_family": "standard_block",
        }
    }

    config = {"lexical_families": {"standard_block": {"delimiters": ["//", "/*", "*/"]}}}

    prism = Prism(config, lang_defs)

    code = """
class Test {
    constructor() {
        this.index = 0;
        // Create something if it doesn't exist
        if (!document.getElementById('test')) {
            this.test = 1;
        }
    }

    otherMethod() {
        return 42;
    }
}
"""

    result = prism.split_streams(code, "javascript")

    # We should still be able to find otherMethod in the code_stream!
    assert "otherMethod" in result["code_stream"], "Code after apostrophe in comment was swallowed!"  # noqa: S101
    assert "this.test = 1;" in result["code_stream"], "Code after apostrophe in comment was swallowed!"  # noqa: S101
