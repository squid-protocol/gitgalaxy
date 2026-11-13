"""#8161 (R3): Rust's `Self::f()` is the caller's own type (like `self.f()`), and `super::f()` names the
parent MODULE, not a parent class: the parent module's file (`mod.rs` / `<dir>.rs` / `lib.rs`), or the
caller's own file for an inline `mod tests`."""

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _sites(files: dict[str, str]):
    parsed_files = []
    for path, code in files.items():
        parsed = StructuralExtractor("rust", LANGUAGE_DEFINITIONS).splice(code, "")
        parsed_files.append(
            {"path": path, "lang_id": "rust", "functions": parsed["functions"], "classes": parsed.get("classes", [])}
        )
    sites, _ = resolve_calls(parsed_files)
    return {(s["src_name"], s["callee"]): (s["step"], s["dst_path"], s["dst_name"]) for s in sites}


def test_self_type_call_reaches_the_associated_function():
    code = (
        "pub struct C { r: f64 }\n"
        "impl C {\n"
        "    pub fn grow(&mut self) { self.r = Self::double(self.r); }\n"
        "    fn double(x: f64) -> f64 { x * 2.0 }\n"
        "}\n"
    )
    sites = _sites({"src/shapes.rs": code})
    assert sites[("grow", "double")] == ("class", "src/shapes.rs", "double")


def test_super_call_reaches_the_parent_module_file():
    files = {
        "src/net/mod.rs": "pub mod wire;\npub fn reached_by_super() -> u8 { 1 }\n",
        "src/net/wire.rs": "pub fn send_bytes() -> u8 {\n    super::reached_by_super()\n}\n",
        # a sibling module's function of the same name is not the parent's
        "src/net/other.rs": "pub fn reached_by_super() -> u8 { 2 }\n",
    }
    sites = _sites(files)
    assert sites[("send_bytes", "reached_by_super")] == ("import", "src/net/mod.rs", "reached_by_super")


def test_super_call_from_an_inline_test_module_is_its_own_file():
    code = (
        "pub fn helper() -> u8 { 1 }\n"
        "#[cfg(test)]\nmod tests {\n    #[test]\n    fn t() {\n        assert_eq!(super::helper(), 1);\n    }\n}\n"
    )
    sites = _sites({"src/util.rs": code, "src/other.rs": "pub fn helper() -> u8 { 2 }\n"})
    assert sites[("t", "helper")] == ("file", "src/util.rs", "helper")
