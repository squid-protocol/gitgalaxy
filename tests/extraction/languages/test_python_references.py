"""
Reference edges (Python): `references_to` / `references_qualifiers`.

A function name used as a value -- `Depends(get_db)`, `key=sort_key`, `callback=self.on_done`,
`return wrapper` -- is a link a framework or caller will invoke later. The detector records
candidates; the resolver keeps only confident, scoped links to a function. Variables must not be
candidates: the function's parameters and locals (tuple targets included), a nested function's
parameters, an enclosing function's bindings (closures) and the module's own variables.
"""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _refs(code: str, lang: str = "python") -> dict[str, list[str]]:
    out = {}
    for f in StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]:
        out[f["name"]] = f.get("references_to", [])
    return out


def test_value_positions_are_references():
    code = (
        "def endpoint(q: str, db=Depends(get_db)):\n"
        "    items = sorted(rows_, key=sort_key)\n"
        "    register(callback=self.on_done, errback=on_error)\n"
        "    handler = on_event\n"
        "    return wrapper\n"
    )
    assert _refs(code)["endpoint"] == ["get_db", "rows_", "sort_key", "on_done", "on_error", "on_event", "wrapper"]


def test_variables_are_not_references():
    code = (
        "app = FastAPI()\n"
        "def run(a, b: Sequence[Depends] = None):\n"
        "    subtype, shape = split()\n"
        "    for item in things:\n        pass\n"
        "    with open(p) as fh:\n        pass\n"
        "    use(a, b, shape, item, fh, app)\n"
        "    x = data[1:limit]\n"
        "    if a == other_value:\n        pass\n"
    )
    # `for item in things` and `data[...]` are not value positions; `open(p)` is (a
    # free name the resolver will drop unless it is a function in scope)
    assert _refs(code)["run"] == ["p"]


def test_nested_parameters_and_closure_variables_are_not_references():
    code = (
        "def acquire(self, timeout=None):\n"
        "    def _try_lock():\n        use(timeout, helper)\n"
        "    def merged(app):\n        run(app)\n"
        "    return merged\n"
    )
    refs = _refs(code)
    assert refs["_try_lock"] == ["helper"]
    assert "app" not in refs["acquire"] and "timeout" not in refs["acquire"]
    assert "merged" in refs["acquire"]


def test_called_names_and_the_module_unit_carry_no_references():
    code = "x = register(handler)\n\ndef run():\n    go(step)\n    step()\n"
    refs = _refs(code)
    assert refs["run"] == []
    assert refs["__global_context__"] == []


def test_languages_without_the_flag_record_nothing():
    code = "function run() {\n  register(handler);\n}\n"
    assert _refs(code, "javascript")["run"] == []
