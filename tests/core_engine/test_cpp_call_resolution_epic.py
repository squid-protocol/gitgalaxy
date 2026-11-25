"""Tests for C++ Level-2 call-graph resolution improvements."""

from __future__ import annotations

from gitgalaxy.core.call_resolver import CONFIDENT_RESOLUTIONS, class_alias_tables_full, resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.return_types import extract_expr_chain
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _scan_cpp(files: dict[str, str], deps: list[dict[str, str]] | None = None) -> list[dict]:
    ext = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS)
    parsed = []
    for path, code in files.items():
        res = ext.splice(code, path)
        res["path"] = path
        res["lang_id"] = "cpp"
        parsed.append(res)
    ca, fa, cat = class_alias_tables_full(files.items())
    sites, _ = resolve_calls(
        parsed,
        deps or [],
        class_aliases=ca,
        foreign_aliases=fa,
        class_alias_targets=cat,
    )
    return sites


def _site(sites: list[dict], src_name: str, callee: str) -> dict:
    matches = [s for s in sites if s["src_name"] == src_name and s["callee"] == callee]
    assert len(matches) == 1, f"Expected 1 site for {src_name} -> {callee}, got {matches}"
    return matches[0]


def test_cpp_cross_dir_ctor_linking():
    files = {
        "include/mylib/os.h": """
class Pipe {
 public:
  Pipe();
};
""",
        "src/os.cc": """
#include "mylib/os.h"
Pipe::Pipe() {}
""",
        "test/os_test.cc": """
#include "mylib/os.h"
void make_pipe() {
  Pipe();
}
""",
    }
    deps = [
        {"src": "src/os.cc", "dst": "include/mylib/os.h"},
        {"src": "test/os_test.cc", "dst": "include/mylib/os.h"},
    ]
    sites = _scan_cpp(files, deps)
    s = _site(sites, "make_pipe", "Pipe")
    assert s["resolution"] in CONFIDENT_RESOLUTIONS
    assert s["dst_path"] == "src/os.cc"
    assert s["dst_name"] == "Pipe::Pipe"


def test_cpp_using_alias_ctor():
    files = {
        "buf.h": """
template <typename T>
class basic_memory_buffer {
 public:
  basic_memory_buffer() {}
};
using memory_buffer = basic_memory_buffer<char>;
""",
        "use.cc": """
#include "buf.h"
void run() {
  auto b = memory_buffer();
}
""",
    }
    sites = _scan_cpp(files, [{"src": "use.cc", "dst": "buf.h"}])
    s = _site(sites, "run", "memory_buffer")
    assert s["resolution"] in CONFIDENT_RESOLUTIONS
    assert s["dst_name"] == "basic_memory_buffer"


def test_cpp_const_member_overload_disambiguation():
    files = {
        "buf.h": """
class Buffer {
 public:
  char* data() { return nullptr; }
  const char* data() const { return nullptr; }
};
void read_only(const Buffer& b) {
  b.data();
}
void read_write(Buffer& b) {
  b.data();
}
""",
    }
    sites = _scan_cpp(files)
    s_const = _site(sites, "read_only", "data")
    s_mut = _site(sites, "read_write", "data")
    assert s_const["resolution"] in CONFIDENT_RESOLUTIONS
    assert s_mut["resolution"] in CONFIDENT_RESOLUTIONS
    assert s_const["dst_line"] != s_mut["dst_line"]


def test_cpp_header_fields_and_one_hop_struct_field_chain():
    files = {
        "os.h": """
class Handle {
 public:
  int fd() { return 0; }
};
class File {
 public:
  int descriptor() { return 0; }
  Handle fdopen(const char* mode) { return Handle(); }
};
struct Pipe {
  File read_end;
};
class Redirect {
 private:
  File original_;
 public:
  void restore();
};
""",
        "os.cc": """
#include "os.h"
void Redirect::restore() {
  original_.descriptor();
}
void check_pipe(Pipe& p) {
  p.read_end.descriptor();
  p.read_end.fdopen("r").fd();
}
""",
    }
    sites = _scan_cpp(files, [{"src": "os.cc", "dst": "os.h"}])
    s_restore = _site(sites, "Redirect::restore", "descriptor")
    assert s_restore["resolution"] in CONFIDENT_RESOLUTIONS
    assert s_restore["dst_name"] == "descriptor"

    s_desc = _site(sites, "check_pipe", "descriptor")
    assert s_desc["resolution"] in CONFIDENT_RESOLUTIONS
    assert s_desc["dst_name"] == "descriptor"

    s_fd = _site(sites, "check_pipe", "fd")
    assert s_fd["resolution"] in CONFIDENT_RESOLUTIONS
    assert s_fd["dst_name"] == "fd"


def test_cpp_template_chain_and_expected_wrapper_alias():
    expr = 'fmt::scan<std::string>("foo", "{}")->value()'
    assert extract_expr_chain(expr, expr.index("value"), (".", "->", "::")) == "fmt.scan()"
    files = {
        "scan.h": """
class ScanData {
 public:
  int item() const { return 1; }
};
class ScanError {};
template <typename T, typename E>
class expected {
 public:
  const T* operator->() const { return nullptr; }
};
using scan_result = expected<ScanData, ScanError>;
namespace ns {
template <typename T>
auto scan(const char* s) -> scan_result {
  return scan_result();
}
}
""",
        "scan_test.cc": """
#include "scan.h"
void run() {
  ns::scan<int>("42")->item();
}
""",
    }
    sites = _scan_cpp(files, [{"src": "scan_test.cc", "dst": "scan.h"}])
    s = _site(sites, "run", "item")
    assert s["resolution"] in CONFIDENT_RESOLUTIONS
    assert s["dst_name"] == "item"


def test_cpp_free_function_header_default_arities():
    files = {
        "util.h": """
class BufferedFile {};
auto open_buffered_file(void* fp = nullptr) -> BufferedFile;
""",
        "util.cc": """
#include "util.h"
BufferedFile open_buffered_file(void* fp) {
  return BufferedFile();
}
""",
        "other_test.cc": """
#include "util.h"
class RawFile {};
RawFile open_buffered_file(int& fd) {
  return RawFile();
}
void caller() {
  open_buffered_file();
}
""",
    }
    deps = [
        {"src": "util.cc", "dst": "util.h"},
        {"src": "other_test.cc", "dst": "util.h"},
    ]
    sites = _scan_cpp(files, deps)
    s = _site(sites, "caller", "open_buffered_file")
    assert s["resolution"] in CONFIDENT_RESOLUTIONS
    assert s["dst_path"] == "util.cc"


def test_cpp_char_width_and_arg0_kind_overload_narrowing():
    files = {
        "fmt.h": """
template <typename... T>
void my_fmt(format_string<T...> fmt, T&&... args) {}
template <typename... T>
void my_fmt(wformat_string<T...> fmt, T&&... args) {}
template <typename... T>
void my_fmt(locale_ref loc, format_string<T...> fmt, T&&... args) {}
template <typename S, typename... T, FMT_ENABLE_IF(is_compiled_string<S>::value)>
void my_fmt(const S& s, T&&... args) {}
""",
        "use.cc": """
#include "fmt.h"
void call_narrow() {
  my_fmt("hello {}", 1);
}
void call_wide() {
  my_fmt(L"hello {}", 1);
}
void call_compiled() {
  my_fmt(FMT_COMPILE("hello {}"), 1);
}
void call_udl_not_plain_str() {
  my_fmt("hello {}"_cf);
}
""",
    }
    sites = _scan_cpp(files, [{"src": "use.cc", "dst": "fmt.h"}])
    s_n = _site(sites, "call_narrow", "my_fmt")
    s_w = _site(sites, "call_wide", "my_fmt")
    s_c = _site(sites, "call_compiled", "my_fmt")
    assert s_n["resolution"] in CONFIDENT_RESOLUTIONS
    assert s_w["resolution"] in CONFIDENT_RESOLUTIONS
    assert s_c["resolution"] in CONFIDENT_RESOLUTIONS
    assert len({s_n["dst_line"], s_w["dst_line"], s_c["dst_line"]}) == 3
    # UDL string literal must not be classified as a plain "str" arg0
    ext = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS)
    parsed_use = ext.splice(files["use.cc"], "use.cc")
    udl_fn = next(f for f in parsed_use["functions"] if f["name"] == "call_udl_not_plain_str")
    assert udl_fn["calls_out_arg0_kinds"]["my_fmt"] == ["other"]
