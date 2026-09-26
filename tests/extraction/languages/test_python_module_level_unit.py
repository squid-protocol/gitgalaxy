"""
Python module-level code as a `__global_context__` unit.

Python (Mode C) sliced only `def`s, so the code a module runs at import -- `app = FastAPI()`,
`@app.post("/items")`, `setup_logging()`, `if __name__ == "__main__": main()` -- was recorded
nowhere, and a web app's route registration with it. The slicer now emits Mode D's synthetic
`__global_context__` bucket for it: every sliced unit's span and each `class Name` header's name
are blanked out, the rest is scanned for calls. It is a synthetic slice (#2691): out of the
function population, and it adds no impact.
"""

import copy

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_APP = (
    "from fastapi import FastAPI\n"
    "app = FastAPI()\n"
    "setup_logging()\n"
    "\n"
    "class Item(BaseModel):\n"
    "    name: str = Field(default='x')\n"
    "    def total(self):\n"
    "        return compute(self)\n"
    "\n"
    "@app.post('/items')\n"
    "def create_item(item: Item):\n"
    "    return save(item)\n"
    "\n"
    "if __name__ == '__main__':\n"
    "    main()\n"
)


def _functions(code, definitions=LANGUAGE_DEFINITIONS, lang="python"):
    return {f["name"]: f for f in StructuralExtractor(lang, definitions).splice(code, "")["functions"]}


def test_module_level_calls_become_a_synthetic_unit():
    funcs = _functions(_APP)
    module = funcs["__global_context__"]
    assert module["is_synthetic_slice"] is True
    assert module["calls_only"] is True and module["impact"] == 0.0
    assert module["calls_out_to"] == ["FastAPI", "setup_logging", "Field", "post", "main"]
    assert module["calls_out_qualifiers"]["post"] == ["app"]
    assert module["calls_out_receiver_types"] == {"app": "FastAPI"}


def test_unit_bodies_and_class_headers_are_not_module_calls():
    module = _functions(_APP)["__global_context__"]
    for inner in ("compute", "save", "Item", "total", "create_item"):
        assert inner not in module["calls_out_to"]
    assert _functions(_APP)["create_item"]["calls_out_to"] == ["save"]


def test_a_file_of_only_definitions_has_no_module_unit():
    code = "def a():\n    return b()\n\n\ndef b():\n    return 1\n"
    assert "__global_context__" not in _functions(code)


def test_embedded_python_gets_it_too():
    assert "__global_context__" in _functions("run()\n\ndef f():\n    return 1\n", lang="embedded_python")


def test_the_module_unit_adds_no_impact():
    # A calls-only bucket: the file's summed function impact is what it was without it.
    off = copy.deepcopy(LANGUAGE_DEFINITIONS)
    off["python"]["module_level_unit"] = False
    on_ex = StructuralExtractor("python", LANGUAGE_DEFINITIONS)
    off_ex = StructuralExtractor("python", off)
    on = on_ex._slice_by_indentation(_APP, on_ex.primary_rules, 0, {}, "python")
    without = off_ex._slice_by_indentation(_APP, off_ex.primary_rules, 0, {}, "python")
    assert on[1] == without[1]
    assert len(on[0]) == len(without[0]) + 1
