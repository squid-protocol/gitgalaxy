"""#9328: C++ constructor and receiver typing through `using X = Y<..>` aliases stays linked to the aliased class."""

from __future__ import annotations

from gitgalaxy.core.call_resolver import class_alias_tables_full, resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_CORE = """
template <typename Char> class basic_string_view {
 public:
  auto begin() const -> const Char* { return data_; }
  auto end() const -> const Char* { return data_; }
 private:
  const Char* data_;
};
using string_view = basic_string_view<char>;
"""

_USER = """
#include "core.h"
class emphasis {
 public:
  auto begin() const -> const char* { return buf; }
  char buf[4];
};
void use_alias(emphasis e) {
  auto reset_color = string_view("x");
  auto a = reset_color.begin();
}
void use_declarator() {
  string_view sv2("y");
  auto b = sv2.end();
}
"""


def _sites() -> list[dict]:
    files = {"core.h": _CORE, "color.h": _USER}
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
        [{"src": "color.h", "dst": "core.h"}],
        class_aliases=ca,
        foreign_aliases=fa,
        class_alias_targets=cat,
    )
    return sites


def _one(sites: list[dict], caller: str, callee: str) -> dict:
    hits = [s for s in sites if s["src_name"] == caller and s["callee"] == callee]
    assert len(hits) == 1, hits
    return hits[0]


def test_alias_named_ctor_call_links_to_the_aliased_class():
    s = _one(_sites(), "use_alias", "string_view")
    assert s["dst_path"] == "core.h"


def test_auto_alias_receiver_does_not_land_on_another_class_method():
    s = _one(_sites(), "use_alias", "begin")
    assert (s["dst_path"], s["dst_line"]) == ("core.h", 4)


def test_alias_declarator_receiver_types_through_the_alias():
    s = _one(_sites(), "use_declarator", "end")
    assert (s["dst_path"], s["dst_line"]) == ("core.h", 5)
