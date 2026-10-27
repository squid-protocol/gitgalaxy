"""
#6266 (gzdoom): a computed-goto label macro is no function, and a constructor's initializer span ends at its body.

`OP(CLSS):\n{ .. }` in a VM exec loop read as a constructor with an initializer list (the colon, then the body's brace).
A constructor `Box(int n = {}) : a(n)\n{ Init(0); }` lost the call in its body: the span ran to the end of the unit, so
`Init(0)` was taken for an initializer entry. Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _units(code: str) -> dict:
    functions = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


def test_a_call_in_the_body_after_an_initializer_list_is_kept():
    code = "Rng::Rng(bool client)\n: crc(0), bClient(client)\n{\n\tif (bClient)\n\t{\n\t\tnext = list;\n\t}\n\tInit(0);\n}\n"
    assert "Init" in _units(code)["Rng::Rng"]["calls_out_to"]  # the resolver, not the detector, drops `crc`


def test_a_brace_default_argument_does_not_end_the_initializer_span():
    code = "Box::Box(Opts o = {}, int n = 1)\n: Base(n), m(o)\n{\n\tgo();\n}\n"
    calls = _units(code)["Box::Box"]["calls_out_to"]
    assert "go" in calls
    assert "Base" in calls


@pytest.mark.parametrize(
    "label_body", ["{\n\t\tdo_it();\n\t}", "\n\t\tif (x) { do_it(); }", "\n#if 0\n\t\tskip();\n#endif"]
)
def test_a_label_macro_before_a_body_is_not_a_function(label_body):
    code = "int Exec(int x)\n{\n\tswitch (x)\n\t{\n\tOP(CLSS):\n\t" + label_body + "\n\t}\n\treturn 0;\n}\n"
    assert "OP" not in _units(code)
