"""#8161 (R1/R2): a Rust `impl` block owns the methods inside it (`impl X` and `impl Tr for X` -> X; a
blanket `impl<T: B> Tr for T` -> Tr), and a tuple or unit struct's span ends at its `;` instead of
stealing the next block's methods. With owners, `Type::f()` reaches that type's method, `Vec::new()`
reaches nothing in the repo, and a bare call or a module path reaches free functions only."""

import pytest

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _parse(code: str) -> dict:
    return StructuralExtractor("rust", LANGUAGE_DEFINITIONS).splice(code, "")


def _owners(code: str) -> dict[str, str | None]:
    return {f["name"]: f.get("parent_class_name") for f in _parse(code)["functions"]}


def _sites(files: dict[str, str], edges=None):
    parsed_files = []
    for path, code in files.items():
        parsed = _parse(code)
        parsed_files.append(
            {"path": path, "lang_id": "rust", "functions": parsed["functions"], "classes": parsed.get("classes", [])}
        )
    sites, _ = resolve_calls(parsed_files, edges)
    return {(s["src_name"], s["callee"]): (s["step"], s["dst_path"], s["dst_name"], s["dst_line"]) for s in sites}


@pytest.mark.parametrize(
    ("header", "owner"),
    [
        ("impl Circle", "Circle"),
        ("impl<T: Clone> Stack<T>", "Stack"),
        ("impl From<u8> for Circle", "Circle"),
        ("impl<'a> std::fmt::Display for &'a mut shapes::Circle", "Circle"),
        ("unsafe impl Send for Circle", "Circle"),
        ("impl<T: std::fmt::Debug> Describe for T", "Describe"),
        ("impl<F> Run for F\nwhere\n    F: Fn() -> u8,", "Run"),
        ("impl Describe for [u8]", "Describe"),
        ("impl dyn Describe", "Describe"),
    ],
)
def test_an_impl_block_owns_its_methods(header, owner):
    code = f"pub struct Circle {{ r: f64 }}\n\n{header} {{\n    fn first(&self) -> u8 {{\n        1\n    }}\n}}\n\npub fn free() {{}}\n"
    owners = _owners(code)
    assert owners["first"] == owner
    assert owners["free"] is None


def test_a_unit_or_tuple_struct_does_not_own_the_next_impl():
    code = (
        "pub struct Unit;\n\n"
        "pub struct Bytes([u8; 4]);\n\n"
        "impl b::Thing {\n    pub fn owned_by_whom(&self) -> u8 {\n        1\n    }\n}\n\n"
        "pub struct Wrapper<T>(T) where T: Copy;\n\n"
        "pub fn after() -> u8 {\n    2\n}\n"
    )
    parsed = _parse(code)
    owners = {f["name"]: f.get("parent_class_name") for f in parsed["functions"]}
    assert owners == {"owned_by_whom": "Thing", "after": None}
    assert {c["name"]: c["method_count"] for c in parsed["classes"]} == {"Unit": 0, "Bytes": 0, "Wrapper": 0}


def test_type_path_calls_reach_the_type_method_and_std_types_reach_nothing():
    code = (
        "pub struct Other;\n"
        "impl Other {\n    pub fn new() -> Self {\n        Other\n    }\n}\n"
        "pub fn make() -> u8 {\n"
        "    let o = Other::new();\n"
        "    let v: Vec<u8> = Vec::new();\n"
        "    0\n}\n"
    )
    sites = _sites({"src/b.rs": code})
    assert sites[("make", "new")] == ("qualified", "src/b.rs", "new", 3)


def test_a_std_type_path_is_no_repo_method():
    code = (
        "pub struct Other;\n"
        "impl Other {\n    pub fn new() -> Self {\n        Other\n    }\n}\n"
        "pub fn make() -> Vec<u8> {\n    Vec::new()\n}\n"
    )
    assert _sites({"src/b.rs": code})[("make", "new")][0] == "none"


def test_a_bare_call_never_reaches_an_impl_method():
    # a closure called by name is not the `add` method of the same file (a confident wrong link before)
    code = (
        "pub struct Circle;\n"
        "impl Circle {\n    pub fn add(&self, x: u8) -> u8 {\n        x\n    }\n}\n"
        "pub fn closures() -> u8 {\n    let add = |x: u8| x + 1;\n    add(1)\n}\n"
    )
    assert _sites({"src/shapes.rs": code})[("closures", "add")][0] == "none"


def test_an_imported_free_function_beats_a_same_file_method():
    files = {
        "src/p.rs": "pub fn parse(x: u8) -> u8 {\n    x\n}\n",
        "src/q.rs": (
            "use crate::p::parse;\n"
            "pub struct Foo;\n"
            "impl Foo {\n    pub fn parse(&self, x: u8) -> u8 {\n        x\n    }\n}\n"
            "pub fn g() -> u8 {\n    parse(1)\n}\n"
        ),
    }
    edges = [{"src": "src/q.rs", "dst": "src/p.rs"}]
    assert _sites(files, edges)[("g", "parse")] == ("import", "src/p.rs", "parse", 1)


def test_self_reaches_the_own_type_not_a_same_file_test_helper():
    code = (
        "pub struct Parser;\n"
        "impl Parser {\n"
        "    fn expect(&self) -> u8 {\n        1\n    }\n"
        "    fn run(&self) -> u8 {\n        self.expect()\n    }\n"
        "}\n"
        "#[cfg(test)]\nmod tests {\n    fn expect() -> u8 {\n        2\n    }\n}\n"
    )
    assert _sites({"src/parser.rs": code})[("run", "expect")] == ("class", "src/parser.rs", "expect", 3)


def test_a_module_path_reaches_a_free_function_not_a_method():
    files = {
        "src/walk.rs": "pub fn scan() -> u8 {\n    1\n}\n",
        "src/main.rs": (
            "mod walk;\n"
            "pub struct WorkerState;\n"
            "impl WorkerState {\n    pub fn scan(&self) -> u8 {\n        2\n    }\n}\n"
            "pub fn go() -> u8 {\n    walk::scan()\n}\n"
            "pub fn ext() {\n    std::mem::scan();\n}\n"
        ),
    }
    edges = [{"src": "src/main.rs", "dst": "src/walk.rs"}]
    sites = _sites(files, edges)
    assert sites[("go", "scan")] == ("import", "src/walk.rs", "scan", 1)
    assert sites[("ext", "scan")][0] == "none"
