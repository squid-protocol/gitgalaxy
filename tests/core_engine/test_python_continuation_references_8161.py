"""#8161 (Y5): a function used as a value at the start of a continuation line (Black's
`register(\n    handler,\n)`, a multi-line default) is a reference, like the same name on one line."""

import pytest

from gitgalaxy.core.detector import _python_references


@pytest.mark.parametrize(
    "text",
    [
        "    return register(\n        handler_fn,\n    )\n",
        "    return register(\n        handler_fn\n    )\n",
        "    return register(a,\n        handler_fn)\n",
        "    x = functools.partial(\n        handler_fn\n    )\n",
        "    return register(\n        cb=handler_fn,\n    )\n",
    ],
)
def test_reference_on_a_continuation_line(text):
    assert ("handler_fn", "") in _python_references(text, {"register", "partial"}, "t")


def test_method_reference_on_a_continuation_line():
    text = "        return register(\n            self.on_done,\n        )\n"
    assert ("on_done", "self") in _python_references(text, {"register"}, "t")


@pytest.mark.parametrize(
    "text",
    [
        # a statement on its own line is no value position
        "    x = 1\n    handler_fn\n",
        # after a line ending in `:` (a block opener), never a reference
        "    if ready:\n        handler_fn\n",
    ],
)
def test_a_name_on_its_own_line_is_still_no_reference(text):
    assert ("handler_fn", "") not in _python_references(text, set(), "t")
