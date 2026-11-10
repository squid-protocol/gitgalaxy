"""#8161 (Y2): reading a Python `@property` / `@cached_property` runs its getter, wherever the read stands: a
chain (`self.conn.batches`), a condition, a subscript, a call receiver, a value. The detector records every
attribute read off `self` / `cls`; the resolver keeps one as a `call` edge only when it reaches a getter through
the class (most reads are data attributes, which get no row)."""

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

CODE = (
    "import functools\n"
    "class Hook:\n"
    "    def __init__(self):\n"
    "        self.name = 'x'\n"
    "    @property\n"
    "    def conn(self):\n"  # 6
    "        return 1\n"
    "    @conn.setter\n"
    "    def conn(self, v):\n"
    "        pass\n"
    "    @functools.cached_property\n"
    "    def res(self):\n"  # 12
    "        return {}\n"
    "    def helper(self):\n"  # 14
    "        return 2\n"
    "    def chain(self):\n"
    "        return self.conn.batches\n"
    "    def cond(self):\n"
    "        if self.conn:\n"
    "            return self.res['k']\n"
    "    def value(self):\n"
    "        return self.conn\n"
    "    def data(self):\n"
    "        return self.name\n"
    "    def method_value(self):\n"
    "        return self.helper\n"
    "    def assign(self):\n"
    "        self.conn = 3\n"
)


def _rows():
    p = StructuralExtractor("python", LANGUAGE_DEFINITIONS).splice(CODE, "")
    sites, _ = resolve_calls(
        [{"path": "h.py", "lang_id": "python", "functions": p["functions"], "classes": p["classes"]}]
    )
    return {(s["src_name"].rsplit(".", 1)[-1], s["callee"], s["kind"]): s for s in sites}


def test_property_reads_in_every_position_are_getter_calls():
    rows = _rows()
    assert rows[("chain", "conn", "call")]["dst_line"] == 6
    assert rows[("cond", "conn", "call")]["dst_line"] == 6
    assert rows[("cond", "res", "call")]["dst_line"] == 12  # a subscript of a cached_property
    assert rows[("value", "conn", "call")]["dst_line"] == 6
    assert ("value", "conn", "reference") not in rows  # the value read is the getter's call, not a reference


def test_data_attributes_and_assignments_get_no_call():
    rows = _rows()
    assert not any(k[0] in ("data", "assign") for k in rows)
    assert ("method_value", "helper", "reference") in rows  # a plain method read as a value stays a reference
    assert ("method_value", "helper", "call") not in rows
