"""
Receiver types (Python): the local evidence the call resolver's `typed` step reads.

`calls_out_receiver_types` maps a receiver the function calls methods on to the class
this same function shows it to be -- `app = FastAPI()`, `def f(ch: Channel)`,
`with Session() as s`, `self.parser = mod.Parser()`. A receiver with conflicting
evidence, also assigned from a non-call, or bound by a `for` loop is left out rather
than guessed. Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _types(code: str, lang: str = "python") -> dict[str, dict[str, str]]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f.get("calls_out_receiver_types", {}) for f in functions}


def test_constructor_assignment_annotation_and_with():
    code = (
        "def run(ch: Channel, n):\n"
        "    app = FastAPI()\n"
        "    self.parser = mod.Parser(n)\n"
        "    with Session(cfg) as s:\n"
        "        s.commit()\n"
        "    app.post('/')\n"
        "    ch.getHost()\n"
        "    self.parser.feed(n)\n"
    )
    assert _types(code)["run"] == {"app": "FastAPI", "ch": "Channel", "self.parser": "Parser", "s": "Session"}


def test_only_receivers_the_function_calls_methods_on():
    code = "def run():\n    app = FastAPI()\n    other = Thing()\n    app.get('/')\n"
    assert _types(code)["run"] == {"app": "FastAPI"}


def test_conflicting_or_non_call_evidence_is_blanked():
    code = (
        "def run(flag):\n"
        "    a = Foo()\n    a = Bar()\n"
        "    b = Foo()\n    b = other\n"
        "    for c in items:\n        c.go()\n"
        "    c = Foo()\n"
        "    a.m()\n    b.m()\n    c.m()\n"
    )
    # "" = bound here with no single known class: no type, and it hides a module-level one
    assert _types(code)["run"] == {"a": "", "b": "", "c": ""}


def test_annotated_assignment_uses_the_annotation():
    code = "def run():\n    x: Store = make_store()\n    x.save()\n"
    assert _types(code)["run"] == {"x": "Store"}


def test_comparison_and_augmented_assignment_are_not_evidence():
    code = "def run(x: Store):\n    if x == Other():\n        pass\n    x += 1\n    x.save()\n"
    assert _types(code)["run"] == {"x": "Store"}


def test_languages_without_the_flag_record_nothing():
    code = "function run() {\n  const app = new App();\n  app.start();\n}\n"
    assert _types(code, "javascript")["run"] == {}
    assert LANGUAGE_DEFINITIONS["python"].get("calls_out_receiver_types") is True
    assert "calls_out_receiver_types" not in LANGUAGE_DEFINITIONS["python"]["rules"]
