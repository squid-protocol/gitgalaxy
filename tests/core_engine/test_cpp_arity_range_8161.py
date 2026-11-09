"""#8161 (P5): a C++ overload is chosen by the range of counts it accepts, not only its parameter count. A default
argument lowers the fewest (it is written on the header declaration, which the out-of-line definition does not
repeat, so the class carries it: `method_arities`), and a variadic (`...`, a pack) has no most."""

from gitgalaxy.core.call_resolver import CONFIDENT_RESOLUTIONS, resolve_calls
from gitgalaxy.core.detector import StructuralExtractor, _cpp_arity_range
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

HEADER = (
    "#pragma once\n"
    "struct Printer {\n"
    "  void emit(int a, int b = 0);\n"
    "  void emit(const char* s);\n"
    "  void log(const char* fmt, ...);\n"
    "  void log(int level);\n"
    "  void put(int v);\n"
    "  void put(int v, int w) { (void)v; (void)w; }\n"
    "};\n"
)
SOURCE = (
    '#include "ov.h"\n'
    "void Printer::emit(int a, int b) {}\n"  # 2
    "void Printer::emit(const char* s) {}\n"  # 3
    "void Printer::log(const char* fmt, ...) {}\n"  # 4
    "void Printer::log(int level) {}\n"  # 5
    "void Printer::put(int v) {}\n"  # 6
    "void two(Printer& p) { p.emit(1, 2); }\n"
    "void one(Printer& p) { p.emit(1); }\n"
    'void many(Printer& p) { p.log("%d %d", 1, 2); }\n'
    "void single(Printer& p) { p.put(1); }\n"
    "struct Box { void fill(int a, int b = 1); void fill(const char* s, int n, int m); };\n"
    "void Box::fill(int a, int b) {}\n"  # 12
    "void Box::fill(const char* s, int n, int m) {}\n"
    "void by_default(Box& b) { b.fill(1); }\n"
)


def _sites():
    files = []
    for path, code in (("src/ov.h", HEADER), ("src/ov.cpp", SOURCE)):
        p = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")
        files.append({"path": path, "lang_id": "cpp", "functions": p["functions"], "classes": p["classes"]})
    sites, _ = resolve_calls(files, [{"src": "src/ov.cpp", "dst": "src/ov.h"}])
    return {(s["src_name"], s["callee"]): s for s in sites}


def test_the_header_declarations_ranges_ride_on_the_class():
    (cls,) = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(HEADER, "")["classes"]
    assert cls["method_arities"] == {"emit": [[1, 2, 2]], "log": [[1, None, 2]]}


def test_a_default_argument_and_a_variadic_widen_the_definitions_range():
    sites = _sites()
    # one argument: the exact one-parameter emit(const char*) wins the count (#3835); that the call means
    # emit(int, int = 0) only the argument's type tells (follow-up: C++ argument types)
    assert sites[("one", "emit")]["dst_line"] == 3
    assert sites[("two", "emit")]["dst_line"] == 2  # only the two-parameter overload takes two
    assert sites[("many", "log")]["dst_line"] == 4  # three arguments reach only the variadic
    assert sites[("many", "log")]["resolution"] in CONFIDENT_RESOLUTIONS
    assert sites[("single", "put")]["dst_line"] == 6
    assert sites[("by_default", "fill")]["dst_line"] == 12  # no exact count: the default decides


def test_arity_range_of_a_parameter_list():
    assert _cpp_arity_range("int a, int b = 0") == (1, 2, 2)
    assert _cpp_arity_range("const char* fmt, ...") == (1, None, 2)
    assert _cpp_arity_range("Ts&&... xs") == (0, None, 1)
    assert _cpp_arity_range("void") == (0, 0, 0)
    assert _cpp_arity_range("std::map<int, int> m = {}, bool f = a == b") == (0, 2, 2)
    assert _cpp_arity_range("int x") == (1, 1, 1)
    assert _cpp_arity_range("format_string<T...> fmt, T&&... args") == (1, None, 2)  # `<T...>` is no pack
