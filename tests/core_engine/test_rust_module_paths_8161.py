"""#8161 (R4): a Rust call through a module path resolves through the crate's module tree, not only through a
file edge whose stem matches: `crate::util::f()` from a nested file, `super::m::f()`, `self::m::f()`, a
workspace crate's `engine::f()` from an integration test, and `m::f()` where `m` only re-exports `f`
(`pub use`). A module path that names no file module (`std::mem::swap`) still reaches nothing in the repo."""

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

FILES = {
    "src/lib.rs": "pub mod net;\npub mod util;\nmod api;\n\npub fn root_fn() -> u8 {\n    1\n}\n",
    "src/util.rs": "pub fn only_in_util() -> u8 {\n    2\n}\n\npub fn swap() {}\n",
    "src/net/mod.rs": "pub mod wire;\npub mod codec;\n",
    "src/net/codec.rs": "pub fn encode() -> u8 {\n    3\n}\n",
    "src/net/wire.rs": (
        "pub fn send_bytes() -> u8 {\n"
        "    crate::util::only_in_util() + super::codec::encode() + crate::root_fn()\n"
        "}\n\n"
        "pub fn ext() {\n    std::mem::swap();\n}\n"
    ),
    "src/api/mod.rs": "mod inner;\npub use self::inner::exported;\n\npub fn local() -> u8 {\n    self::inner::exported()\n}\n",
    "src/api/inner.rs": "pub fn exported() -> u8 {\n    4\n}\n",
    "src/user.rs": "pub fn via_reexport() -> u8 {\n    crate::api::exported()\n}\n",
    "engine/src/lib.rs": "pub fn compute() -> u8 {\n    5\n}\n",
    "app/tests/it.rs": "#[test]\nfn integration() {\n    assert_eq!(engine::compute(), 5);\n}\n",
}
# the import graph's re-export edge (`pub use self::inner::exported`): api/mod.rs -> api/inner.rs
IMPORTS = [{"src": "src/api/mod.rs", "dst": "src/api/inner.rs"}]


def _sites():
    parsed_files = []
    for path, code in FILES.items():
        parsed = StructuralExtractor("rust", LANGUAGE_DEFINITIONS).splice(code, "")
        parsed_files.append({"path": path, "lang_id": "rust", "functions": parsed["functions"], "classes": []})
    sites, _ = resolve_calls(parsed_files, IMPORTS)
    return {(s["src_name"], s["callee"]): (s["step"], s["dst_path"]) for s in sites}


def test_a_crate_path_reaches_the_module_file():
    sites = _sites()
    assert sites[("send_bytes", "only_in_util")] == ("import", "src/util.rs")
    assert sites[("send_bytes", "root_fn")] == ("import", "src/lib.rs")


def test_a_super_path_reaches_the_sibling_module_file():
    assert _sites()[("send_bytes", "encode")] == ("import", "src/net/codec.rs")


def test_a_self_path_reaches_a_child_module_file():
    assert _sites()[("local", "exported")] == ("import", "src/api/inner.rs")


def test_a_reexporting_module_reaches_the_function_it_re_exports():
    assert _sites()[("via_reexport", "exported")] == ("import", "src/api/inner.rs")


def test_a_workspace_crate_path_reaches_its_lib():
    assert _sites()[("integration", "compute")] == ("import", "engine/src/lib.rs")


def test_an_external_module_path_reaches_nothing():
    assert _sites()[("ext", "swap")][0] == "none"
