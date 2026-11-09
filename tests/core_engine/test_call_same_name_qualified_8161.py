"""#8161 (X1): a call spelled like its own unit is recursion only through the unit's own receiver
(bare, `self`, `this`, the Go receiver variable). Any other receiver or scope names another unit:
`super().m()` in `m`, `w.next.Close()` in `Close`, `self.repo.save()` in `save`, `Base::Put(k)` in
`Put`. The detector keeps such a call with only its foreign qualifiers; the resolver links it (or
prunes it when it still lands on the unit itself)."""

import pytest

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor, _call_qualifier
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _scan(lang: str, path: str, code: str):
    parsed = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")
    file = {"path": path, "lang_id": lang, "functions": parsed["functions"], "classes": parsed.get("classes", [])}
    sites, _ = resolve_calls([file])
    edges = [(s["src_name"], s["src_line"], s["dst_name"], s["dst_line"]) for s in sites if s["dst_name"]]
    return file, edges


def _unit(file, name: str, line: int):
    return next(fn for fn in file["functions"] if fn["name"] == name and fn["start_line"] == line)


PY = (
    "class Repo:\n"  # 1
    "    def save(self, x):\n"  # 2
    "        return x\n"
    "\n"
    "class Base:\n"  # 5
    "    def __init__(self):\n"  # 6
    "        self.n = 1\n"
    "\n"
    "    def save(self, x):\n"  # 9
    "        return x\n"
    "\n"
    "class Kid(Base):\n"  # 12
    "    def __init__(self):\n"  # 13
    "        super().__init__()\n"
    "\n"
    "    def save(self, x):\n"  # 16
    "        return super(Kid, self).save(x)\n"
    "\n"
    "    def again(self, x):\n"  # 19
    "        return self.again(x)\n"
)


def test_python_super_call_of_the_same_name_reaches_the_parent():
    file, edges = _scan("python", "a.py", PY)
    assert ("__init__", 13, "__init__", 6) in edges
    assert ("save", 16, "save", 9) in edges
    assert _unit(file, "save", 16)["calls_out_qualifiers"]["save"] == ["super"]
    # `self.again()` in `again` is the unit itself: still recursion
    assert "again" not in _unit(file, "again", 19)["calls_out_to"]


def test_python_delegation_through_an_attribute_is_kept():
    code = "class Svc:\n    def save(self, x):\n        return self.repo.save(x)\n"
    file, _ = _scan("python", "a.py", code)
    assert _unit(file, "save", 2)["calls_out_qualifiers"]["save"] == ["self.repo"]


def test_go_wrapper_delegate_is_kept_and_own_receiver_is_recursion():
    code = (
        "package p\n\n"
        "type Inner struct{}\n\n"
        "func (i *Inner) Close() error {\n\treturn nil\n}\n\n"  # 5
        "type W struct {\n\tnext *Inner\n}\n\n"
        "func (w *W) Close() error {\n\treturn w.next.Close()\n}\n\n"  # 13
        "func (w *W) Again() error {\n\treturn w.Again()\n}\n"  # 17
    )
    file, edges = _scan("go", "a.go", code)
    assert _unit(file, "Close", 13)["calls_out_qualifiers"]["Close"] == ["w.next"]
    assert ("Close", 13, "Close", 5) in edges
    assert "Again" not in _unit(file, "Again", 17)["calls_out_to"]


TS = (
    "export function readonly(x: unknown): unknown {\n"  # 1
    "  return x;\n"
    "}\n"
    "export function optional(x: unknown): unknown {\n"  # 4
    "  return x;\n"
    "}\n"
    "export const proto = {\n"
    "  readonly() {\n"  # 8
    "    return readonly(this);\n"
    "  },\n"
    "};\n"
    "class P {\n"
    "  run(): number {\n"  # 13
    "    return 1;\n"
    "  }\n"
    "}\n"
    "class Q extends P {\n"
    "  run(): number {\n"  # 18
    "    return super.run() + 1;\n"
    "  }\n"
    "}\n"
    "export function make(inst: any): void {\n"
    "  inst.optional = () => optional(inst);\n"  # 23
    "}\n"
    "export const rec = (n: number): number => rec(n - 1);\n"  # 25
)


@pytest.mark.parametrize("lang,path", [("typescript", "a.ts"), ("javascript", "a.js")])
def test_ts_js_super_and_member_same_name_calls(lang, path):
    code = TS
    if lang == "javascript":
        code = code.replace(": unknown", "").replace(": number", "").replace(": any", "").replace(": void", "")
    _, edges = _scan(lang, path, code)
    assert ("run", 18, "run", 13) in edges  # super.run() in run
    assert ("readonly", 8, "readonly", 1) in edges  # object-literal method -> the free function
    assert ("optional", 23, "optional", 4) in edges  # `inst.optional = () => optional(inst)`
    # a plain arrow binding calling itself is recursion
    assert not [e for e in edges if e[0] == "rec"]


def test_java_super_call_of_the_same_name_reaches_the_parent():
    code = (
        "class P {\n    int run(int a) { return a; }\n}\n"
        "class Q extends P {\n    int run(int a) { return super.run(a) + 1; }\n}\n"
    )
    _, edges = _scan("java", "A.java", code)
    assert ("run", 5, "run", 2) in edges


def test_rust_delegate_through_a_field_is_kept():
    code = (
        "struct Repo;\nimpl Repo {\n    fn save(&self, x: i32) -> i32 { x }\n}\n"
        "struct Svc { repo: Repo }\nimpl Svc {\n    fn save(&self, x: i32) -> i32 { self.repo.save(x) }\n}\n"
    )
    file, edges = _scan("rust", "a.rs", code)
    assert _unit(file, "save", 7)["calls_out_qualifiers"]["save"] == ["self.repo"]
    assert ("save", 7, "save", 3) in edges


def test_cpp_base_class_call_of_the_same_name():
    code = (
        "class Base {\n public:\n  virtual void Put(int k) {}\n};\n"
        "class Derived : public Base {\n public:\n  void Put(int k) override { Base::Put(k); }\n};\n"
    )
    _, edges = _scan("cpp", "a.cpp", code)
    assert ("Put", 7, "Put", 3) in edges


@pytest.mark.parametrize(
    "text,qualifier",
    [
        ("super().m(", "super"),
        ("super(Kid, self).m(", "super"),
        ("x.super().m(", "<expr>"),
        ("f().m(", "<expr>"),
        ("self.repo.m(", "self.repo"),
    ],
)
def test_call_qualifier_names_python_super(text, qualifier):
    assert _call_qualifier(text, len(text) - 2) == qualifier
