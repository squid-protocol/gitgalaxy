"""
Regression tests for Level-2 call-graph resolution outlier fixes (C++ and Kotlin):
- C++: cross-file free-function overload sets across `#include` closure, multi-word
  trailing return types (`-> long long`), and lowercase `using`/`typedef` alias receiver typing.
- Kotlin: `companion object` methods owned by enclosing class (`CodeBlock.of(...)`),
  unique-class receiver typing (`_is_unique_class`), file-scoped return-type chains,
  and primary-constructor class inheritance (`class Sub(...) : Base(...)`).
"""

from gitgalaxy.core.call_resolver import class_alias_tables_full, resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _parse(lang: str, path: str, code: str) -> dict:
    res = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, path)
    return {
        "path": path,
        "lang_id": lang,
        "functions": res["functions"],
        "classes": res["classes"],
    }


def test_cpp_cross_file_free_function_overloads():
    core_h = "namespace fmt {\nvoid emit_msg(int a, int b, int c) { }\n}\n"
    color_h = "namespace fmt {\nvoid emit_msg(int a) { }\nvoid caller() { emit_msg(1, 2, 3); }\n}\n"
    files = [_parse("cpp", "include/fmt/core.h", core_h), _parse("cpp", "include/fmt/color.h", color_h)]
    edges = [{"src": "include/fmt/color.h", "dst": "include/fmt/core.h"}]
    sites, _ = resolve_calls(files, edges)
    hit = next(s for s in sites if s["src_name"] == "caller" and s["callee"] == "emit_msg")
    assert hit["dst_path"] == "include/fmt/core.h"
    assert hit["step"] == "import"


def test_cpp_multiword_trailing_return_type_extracted():
    code = (
        "struct Chrono {\n"
        "  auto tm_year() const noexcept -> long long { return 2026; }\n"
        "  auto tm_count() const noexcept -> unsigned int { return 1; }\n"
        "};\n"
    )
    funcs = {f["name"] for f in _parse("cpp", "chrono.h", code)["functions"]}
    assert "tm_year" in funcs
    assert "tm_count" in funcs


def test_cpp_lowercase_using_alias_receiver_typing():
    core_h = (
        "template <typename Char>\n"
        "class basic_string_view {\n"
        "public:\n"
        "  const Char* begin() const { return nullptr; }\n"
        "};\n"
        "using string_view = basic_string_view<char>;\n"
    )
    user_cc = "void use(string_view sv) {\n  sv.begin();\n}\n"
    names, foreign, alias_map = class_alias_tables_full([("core.h", core_h)])
    assert alias_map.get("string_view") == "basic_string_view"
    files = [_parse("cpp", "core.h", core_h), _parse("cpp", "user.cc", user_cc)]
    edges = [{"src": "user.cc", "dst": "core.h"}]
    sites, _ = resolve_calls(files, edges, class_aliases=names, foreign_aliases=foreign, class_alias_targets=alias_map)
    hit = next(s for s in sites if s["src_name"] == "use" and s["callee"] == "begin")
    assert hit["step"] == "typed"
    assert hit["dst_path"] == "core.h"


def test_kotlin_companion_object_inheritance_and_return_type_chain():
    base_kt = 'open class TypeName {\n  open fun tag(): String { return "base" }\n}\n'
    sub_kt = (
        "class ClassName internal constructor(\n"
        "  val name: String\n"
        ") : TypeName() {\n"
        "  override fun tag(): String { return super.tag() }\n"
        "  class Builder {\n"
        '    fun build(): ClassName { return ClassName("x") }\n'
        "  }\n"
        "  companion object {\n"
        "    fun builder(): Builder { return Builder() }\n"
        "  }\n"
        "}\n"
    )
    caller_kt = "fun make(c: ClassName): ClassName {\n  c.tag()\n  return ClassName.builder().build()\n}\n"
    f_base = _parse("kotlin", "TypeName.kt", base_kt)
    f_sub = _parse("kotlin", "ClassName.kt", sub_kt)
    f_caller = _parse("kotlin", "Caller.kt", caller_kt)

    cls = next(c for c in f_sub["classes"] if c["name"] == "ClassName")
    assert "TypeName" in cls["inheritance"]

    builder_fn = next(f for f in f_sub["functions"] if f["name"] == "builder")
    assert builder_fn.get("parent_class_name") == "ClassName"

    edges = [
        {"src": "ClassName.kt", "dst": "TypeName.kt"},
        {"src": "Caller.kt", "dst": "ClassName.kt"},
        {"src": "Caller.kt", "dst": "TypeName.kt"},
    ]
    sites, _ = resolve_calls([f_base, f_sub, f_caller], edges)

    super_hit = next(
        s for s in sites if s["src_path"] == "ClassName.kt" and s["src_name"] == "tag" and s["callee"] == "tag"
    )
    assert super_hit["step"] == "class"
    assert super_hit["dst_path"] == "TypeName.kt"

    qual_hit = next(s for s in sites if s["src_name"] == "make" and s["callee"] == "builder")
    assert qual_hit["step"] == "qualified"
    assert qual_hit["dst_path"] == "ClassName.kt"

    typed_hit = next(s for s in sites if s["src_name"] == "make" and s["callee"] == "tag")
    assert typed_hit["step"] == "typed"
    assert typed_hit["dst_path"] == "ClassName.kt"

    chain_hit = next(s for s in sites if s["src_name"] == "make" and s["callee"] == "build")
    assert chain_hit["step"] == "typed"
    assert chain_hit["dst_path"] == "ClassName.kt"


def test_cpp_variadic_pack_overloads_and_decltype_trailing_return():
    hdr = (
        "namespace fmt {\n"
        "template <typename... T>\n"
        "void print(FILE* f, format_string<T...> fmt, T&&... args) { }\n"
        "template <typename... T>\n"
        "void print(format_string<T...> fmt, T&&... args) { }\n"
        "template <typename R>\n"
        "auto join(R&& r, string_view sep)\n"
        "    -> join_view<decltype(range_begin(r)),\n"
        "                 decltype(range_end(r))> {\n"
        "  return {};\n"
        "}\n"
        "}\n"
    )
    src = 'void run(int x) {\n  fmt::print("{}", x, 1);\n}\n'
    f_hdr = _parse("cpp", "include/fmt/core.h", hdr)
    f_src = _parse("cpp", "src/app.cc", src)
    assert "join" in {f["name"] for f in f_hdr["functions"]}
    edges = [{"src": "src/app.cc", "dst": "include/fmt/core.h"}]
    sites, _ = resolve_calls([f_hdr, f_src], edges)
    hit = next(s for s in sites if s["src_name"] == "run" and s["callee"] == "print")
    assert hit["step"] == "import"
    assert hit["dst_line"] == 4


def test_kotlin_bodyless_interface_signature_extension_and_object_import():
    iface_kt = (
        "interface ClassInspector {\n"
        "  fun containerData(c: Container, name: String, parent: String?): Int\n"
        "}\n"
        "fun ClassInspector.containerData(name: String, parent: String?): Int {\n"
        "  return 1\n"
        "}\n"
    )
    util_kt = (
        "internal object ClassInspectorUtil {\n"
        "  fun filterOutNullabilityAnnotations(xs: List<Int>): List<Int> { return xs }\n"
        "}\n"
    )
    annot_kt = (
        "interface Annotatable {\n"
        "  interface Builder<out T : Builder<T>> {\n"
        "    fun addAnnotations(xs: List<Int>): T { return this as T }\n"
        "  }\n"
        "}\n"
    )
    file_kt = (
        "class FileSpec {\n"
        "  class Builder : Annotatable.Builder<Builder> {\n"
        "    override fun addAnnotations(xs: List<Int>): Builder = super.addAnnotations(xs)\n"
        "  }\n"
        "}\n"
    )
    caller_kt = (
        "fun work(ci: ClassInspector, xs: List<Int>) {\n"
        '  ci.containerData("a", null)\n'
        "  filterOutNullabilityAnnotations(xs)\n"
        "}\n"
    )
    f_iface = _parse("kotlin", "ClassInspector.kt", iface_kt)
    f_util = _parse("kotlin", "ClassInspectorUtil.kt", util_kt)
    f_annot = _parse("kotlin", "Annotatable.kt", annot_kt)
    f_file = _parse("kotlin", "FileSpec.kt", file_kt)
    f_caller = _parse("kotlin", "Caller.kt", caller_kt)

    sig_fn = next(f for f in f_iface["functions"] if f["start_line"] == 2)
    assert sig_fn.get("def_shape") == "signature"

    edges = [
        {"src": "Caller.kt", "dst": "ClassInspector.kt"},
        {"src": "Caller.kt", "dst": "ClassInspectorUtil.kt"},
        {"src": "FileSpec.kt", "dst": "Annotatable.kt"},
    ]
    sites, _ = resolve_calls([f_iface, f_util, f_annot, f_file, f_caller], edges)

    cd_hit = next(s for s in sites if s["src_name"] == "work" and s["callee"] == "containerData")
    assert cd_hit["dst_path"] == "ClassInspector.kt"
    assert cd_hit["dst_line"] == 4

    obj_hit = next(s for s in sites if s["src_name"] == "work" and s["callee"] == "filterOutNullabilityAnnotations")
    assert obj_hit["step"] == "import"
    assert obj_hit["dst_path"] == "ClassInspectorUtil.kt"

    super_hit = next(s for s in sites if s["src_path"] == "FileSpec.kt" and s["callee"] == "addAnnotations")
    assert super_hit["step"] == "class"
    assert super_hit["dst_path"] == "Annotatable.kt"
