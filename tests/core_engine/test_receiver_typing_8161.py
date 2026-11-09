"""#8161 (X3): receiver typing for C++, Go, Rust and TypeScript/JavaScript. A receiver's class is read from the
calling unit's parameters, locals and constructions and from the file's struct/class fields
(core/receiver_types.py), so `x.m()` takes the resolver's `typed` step to that class's method where two classes
in view define `m`. A name bound with no readable type (or two different ones) stays untyped."""

import pytest

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.receiver_types import receiver_types
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _parse(lang: str, code: str) -> dict:
    return StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")


def _types(lang: str, code: str) -> dict[str, dict[str, str]]:
    return {f["name"]: f.get("calls_out_receiver_types") or {} for f in _parse(lang, code)["functions"]}


def _sites(lang: str, files: dict[str, str], edges=None, aliases=None):
    parsed_files = []
    for path, code in files.items():
        parsed = _parse(lang, code)
        parsed_files.append(
            {"path": path, "lang_id": lang, "functions": parsed["functions"], "classes": parsed.get("classes", [])}
        )
    sites, _ = resolve_calls(parsed_files, edges, namespace_aliases=aliases)
    return {(s["src_name"], s["callee"]): (s["step"], s["dst_path"], s["dst_line"]) for s in sites}


RUST = (
    "pub struct Engine { cfg: Config, other: Box<Other> }\n"  # 1
    "pub struct Config { n: u8 }\n"  # 2
    "pub struct Other;\n"  # 3
    "impl Config {\n    pub fn load(&self) -> u8 {\n        1\n    }\n}\n"  # 4-8
    "impl Other {\n    pub fn load(&self) -> u8 {\n        2\n    }\n}\n"  # 9-13
    "impl Engine {\n"  # 14
    "    pub fn new() -> Self { Engine { cfg: Config { n: 0 }, other: Box::new(Other) } }\n"  # 15
    "    pub fn run(&self, a: &Config, b: &mut Other) -> u8 {\n"  # 16
    "        let c = Config { n: 1 };\n"
    "        let d: Other = make();\n"
    "        let e = Self::new();\n"
    "        let f = Config::new_with(2).build();\n"
    "        a.load(); b.load(); c.load(); d.load(); e.start(); f.load();\n"
    "        self.cfg.load(); self.other.load();\n"
    "        0\n"
    "    }\n"
    "    pub fn start(&self) -> u8 { 3 }\n"  # 25
    "}\n"
)


def test_rust_receivers_are_typed_from_parameters_lets_and_fields():
    types = _types("rust", RUST)["run"]
    assert types["a"] == "Config" and types["b"] == "Other"
    assert types["c"] == "Config" and types["d"] == "Other" and types["e"] == "Self"
    assert types["self.cfg"] == "Config" and types["self.other"] == "Other"  # a `Box<T>` field derefs to T
    assert types["f"] == ""  # `Config::new_with(2).build()` is whatever `build` returns


def test_rust_typed_receivers_resolve_to_their_types_method():
    sites = _sites("rust", {"src/e.rs": RUST})
    # several receivers name `load`: the most confident step wins, and it is `typed`
    assert sites[("run", "load")][0] == "typed"
    assert sites[("run", "start")] == ("typed", "src/e.rs", 25)  # `Self::new()` is the caller's own type


def test_rust_loop_and_closure_bindings_stay_untyped():
    code = "fn f(xs: Vec<Config>) {\n    let x = Config { n: 1 };\n    for x in xs.iter() { x.load(); }\n}\n"
    assert receiver_types("rust", code, {"x"}, {}) == {"x": ""}


@pytest.mark.parametrize(
    ("decl", "typ"),
    [
        ("x := &Config{n: 1}", "Config"),
        ("x := Config{}", "Config"),
        ("var x Config", "Config"),
        ("var x *Config = other", "Config"),
        ("x := new(Config)", "Config"),
        ("x := NewConfig()", ""),
        ("x, err := load()", ""),
        ("var x []Config", ""),
    ],
)
def test_go_locals(decl, typ):
    code = f"func f(other *Config) {{\n\t{decl}\n\tx.Load()\n}}\n"
    assert receiver_types("go", code, {"x"}, {}) == {"x": typ}


def test_go_grouped_parameters_and_struct_fields():
    code = "func f(a, b *Config, c pkg.Other) {\n\ta.Load()\n}\n"
    assert receiver_types("go", code, {"a", "b", "c"}, {}) == {"a": "Config", "b": "Config", "c": "pkg.Other"}
    fields = 'type E struct {\n\tcfg, alt *Config `json:"cfg"`\n\tio.Reader\n\tm map[string]int\n}\n'
    parsed = {
        f["name"]: f
        for f in _parse("go", "package e\n\n" + fields + "\nfunc (e *E) R() { e.cfg.Load() }\n")["functions"]
    }
    assert parsed["R"]["calls_out_receiver_types"] == {"self.cfg": "Config"}


def test_go_a_package_qualified_type_resolves_in_that_package_only():
    files = {
        "a/a.go": "package a\n\ntype Ctx struct{}\n\nfunc (c *Ctx) Next() {}\n",
        "b/b.go": "package b\n\ntype Ctx struct{}\n\nfunc (c *Ctx) Next() {}\n",
        "m/m.go": 'package m\n\nimport "example.com/x/a"\n\nfunc H(c *a.Ctx) {\n\tc.Next()\n}\n',
    }
    sites = _sites("go", files, [{"src": "m/m.go", "dst": "a/a.go"}], {"m/m.go": {"a": "a/a.go"}})
    assert sites[("H", "Next")] == ("typed", "a/a.go", 5)


TS = (
    "export class Config { load(): number { return 1; } }\n"
    "export class Other { load(): number { return 2; } }\n"
    "export class Engine {\n"
    "  private cfg: Config;\n"
    "  constructor(private readonly other: Other) { this.cfg = new Config(); }\n"
    "  run(c: Config, d?: Other | undefined): number {\n"
    "    const x = new Other();\n"
    "    let y: Config = make();\n"
    "    for (const z of zs) { z.load(); }\n"
    "    c.load(); d.load(); x.load(); y.load();\n"
    "    this.cfg.load(); this.other.load();\n"
    "    return 0;\n"
    "  }\n"
    "}\n"
)


def test_typescript_receivers_are_typed_from_annotations_new_and_fields():
    types = _types("typescript", TS)["run"]
    assert {k: types.get(k) for k in ("c", "d", "x", "y", "z", "this.cfg", "this.other")} == {
        "c": "Config",
        "d": "Other",
        "x": "Other",
        "y": "Config",
        "z": "",
        "this.cfg": "Config",
        "this.other": "Other",
    }
    assert _sites("typescript", {"src/e.ts": TS})[("run", "load")][0] == "typed"


CPP = (
    "class Config {\n public:\n  int load() const {\n    return 1;\n  }\n};\n"
    "class Other {\n public:\n  int load() const {\n    return 2;\n  }\n};\n"
    "class Engine {\n"
    " public:\n"
    "  int run(const Config& a, Other* b);\n"
    "  int start() { return 3; }\n"
    " private:\n"
    "  Config cfg_;\n"
    "  std::unique_ptr<Other> other_;\n"
    "};\n"
    "int Engine::run(const Config& a, Other* b) {\n"
    "  Config c;\n"
    "  auto d = Other(1);\n"
    "  auto e = std::make_unique<Engine>();\n"
    "  auto f = build();\n"
    "  Other arr[4];\n"
    "  a.load(); b->load(); c.load(); d.load(); e->start(); f.load(); arr[0].load();\n"
    "  cfg_.load(); this->other_->load();\n"
    "  return 0;\n"
    "}\n"
)


def test_cpp_receivers_are_typed_from_declarations_auto_and_fields():
    types = _types("cpp", CPP)["Engine::run"]
    assert {k: types.get(k) for k in ("a", "b", "c", "d", "e", "f", "cfg_", "this.other_")} == {
        "a": "Config",
        "b": "Other",
        "c": "Config",
        "d": "Other",
        "e": "Engine",
        "f": "build",  # a call's name: the resolver keeps it only if it is a class
        "cfg_": "Config",  # a bare field name: the implicit `this`
        "this.other_": "Other",  # a `unique_ptr<T>` reaches T's methods
    }
    sites = _sites("cpp", {"src/e.cpp": CPP})
    assert sites[("Engine::run", "load")][0] == "typed"
    assert sites[("Engine::run", "start")] == ("typed", "src/e.cpp", 16)


def test_an_untyped_receiver_keeps_the_old_ladder():
    code = "fn f(x: u8) {\n    let y = compute();\n    y.load();\n}\n"
    assert receiver_types("rust", code, {"y", "z"}, {}) == {"y": ""}
