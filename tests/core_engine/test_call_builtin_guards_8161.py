"""#8161 (X2): built-in and standard-library guards.

- Go's predeclared functions (`len`, `append`, ...) never link to a repo METHOD of that name, and only a
  same-package free function shadows one.
- A bare Go call reaches free functions only: a method (`func (t *T) f(`) is `member`-shaped.
- A standard-library / interface method name on an UNTYPED receiver (Go `x.Close()`, Rust `v.len()`,
  C++ `v.size()`) is the ambiguous `receiver` guess, never a confident link to the repo's one.
"""

import pytest

from gitgalaxy.core.call_resolver import RESOLUTION_OF_STEP, resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _scan(lang: str, files: dict[str, str]):
    parsed_files = []
    for path, code in files.items():
        parsed = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")
        parsed_files.append(
            {"path": path, "lang_id": lang, "functions": parsed["functions"], "classes": parsed.get("classes", [])}
        )
    sites, _ = resolve_calls(parsed_files)
    return parsed_files, sites


def _site(sites, src: str, callee: str):
    return next(s for s in sites if s["src_name"] == src and s["callee"] == callee)


GO = {
    "p/chunk.go": (
        "package p\n\n"
        "type memChunk struct{ prev *memChunk }\n\n"
        "func (mc *memChunk) len() int { return 1 }\n\n"
        "func (mc *memChunk) append(v int) {}\n\n"
        "type Cfg struct{}\n\n"
        "func (c *Cfg) Load() error { return nil }\n"
    ),
    "p/use.go": (
        "package p\n\n"
        'import "sync/atomic"\n\n'
        "type S struct{ ready atomic.Bool }\n\n"
        "func Count(xs []int) int {\n\tys := append(xs, 1)\n\treturn len(ys)\n}\n\n"
        "func (s *S) Ready() bool { return s.ready.Load() }\n"
    ),
    "q/q.go": (
        "package q\n\n"
        "func min(a, b int) int { return a }\n\n"
        "func Use(a, b int) int {\n\treturn min(a, b)\n}\n\n"
        "type T struct{}\n\n"
        "func (t *T) Run() {}\n"
    ),
    "q/r.go": "package q\n\nfunc Other() {\n\tRun()\n}\n",
}


def test_go_builtins_never_reach_a_method_of_that_name():
    _, sites = _scan("go", GO)
    for callee in ("len", "append"):
        site = _site(sites, "Count", callee)
        assert site["dst_name"] is None
        assert site["step"] == "none"


def test_go_same_package_free_function_shadows_a_builtin():
    _, sites = _scan("go", GO)
    site = _site(sites, "Use", "min")
    assert (site["dst_path"], site["dst_name"], site["step"]) == ("q/q.go", "min", "file")


def test_go_methods_are_member_shaped_and_bare_calls_skip_them():
    files, sites = _scan("go", GO)
    shapes = {fn["name"]: fn.get("def_shape") for f in files for fn in f["functions"]}
    assert shapes["len"] == shapes["Run"] == shapes["Ready"] == "member"
    assert shapes["Count"] is None
    # `Run()` in package q names no free function: the method `(*T).Run` is not its target
    assert not [s for s in sites if s["src_name"] == "Other" and s["dst_name"]]


def test_go_std_interface_method_on_an_untyped_receiver_is_ambiguous():
    _, sites = _scan("go", GO)
    site = _site(sites, "Ready", "Load")
    assert site["step"] == "receiver"
    assert RESOLUTION_OF_STEP[site["step"]] == "ambiguous"


@pytest.mark.parametrize(
    "lang,path,code,callee",
    [
        (
            "rust",
            "a.rs",
            "struct V;\nimpl V {\n    fn len(&self) -> usize { 0 }\n}\nfn f(v: Vec<u8>) -> usize {\n    v.len()\n}\n",
            "len",
        ),
        (
            "cpp",
            "a.cpp",
            (
                "#include <vector>\nclass Buf {\n public:\n  int size() const { return 0; }\n};\n"
                "int f(const std::vector<int>& v) { return v.size(); }\n"
            ),
            "size",
        ),
    ],
)
def test_std_method_name_on_an_untyped_receiver_is_ambiguous(lang, path, code, callee):
    _, sites = _scan(lang, {path: code})
    site = _site(sites, "f", callee)
    assert site["step"] == "receiver"
