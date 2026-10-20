"""#5633: three shapes that hid calls from `calls_out_to`.

1. A prefix `--` (decrement) was read as a `--` line comment by the literal shield, blanking the rest
   of its line: `--vars[ReadVar()];`, `for (;; --i, x.f())`. Every `//`-comment language with a `--`
   operator is covered.
2. Java `synchronized (X.class) {` / `try (R r = open()) {` matched the bare-name `name(...) {` branch
   of `func_start`, so the block became a unit and its calls left the enclosing method.
3. C# `a > F(x) ||` on a multi-line condition matched as `<type> F(`, carving a phantom unit named
   `Fixed.FromInt` out of the middle of the method (managed-doom `PathTraversal.cs:71`)."""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _calls(lang: str, code: str) -> dict[str, list[str]]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f["calls_out_to"] for f in functions}


_HEADS = {
    "c": "int f(void) {",
    "cpp": "int f(void) {",
    "kotlin": "fun f() {",
    "javascript": "function f() {",
    "typescript": "function f(): void {",
    "php": "function f() {",
}


def _wrap(lang: str, body: str) -> str:
    if lang in _HEADS:
        return f"{_HEADS[lang]}\n{body}\n}}\n"
    return f"class A {{\n  void f() {{\n{body}\n  }}\n}}\n"


DECREMENT_LANGS = ("c", "cpp", "java", "kotlin", "csharp", "javascript", "typescript", "groovy", "php")


@pytest.mark.parametrize("lang", DECREMENT_LANGS)
@pytest.mark.parametrize(
    "stmt",
    [
        "\t--vars[ReadVar()];",
        "\tx = --vars[ReadVar()];",
        "\t--n; ReadVar();",
        "\t--a, ReadVar();",
        "\tfor (; n > 0; --n, rel.ReadVar()) {}",
    ],
)
def test_call_after_a_prefix_decrement_is_kept(lang, stmt):
    assert _calls(lang, _wrap(lang, stmt))["f"] == ["ReadVar"]


@pytest.mark.parametrize("lang", ("c", "cpp", "java"))
def test_prefix_increment_and_a_real_comment_still_behave(lang):
    body = "\t++vars[ReadVar()]; // --not_a_call(1)\n\t/* --also_not(2) */ Other();"
    assert _calls(lang, _wrap(lang, body))["f"] == ["ReadVar", "Other"]


JAVA_SYNC = """\
class A {
  static A get() {
    synchronized (A.class) {
      if (e == null) {
        try {
          e = new A();
        } catch (Exception x) {
          Logger.getLogger(A.class.getName()).log(1, null, x);
          throw new Error(x);
        }
      }
      return e;
    }
  }
  void h() {
    synchronized (this) { foo(); }
    try (Res r = open(1)) { bar(); }
  }
}
"""


def test_java_synchronized_and_try_with_resources_are_not_units():
    calls = _calls("java", JAVA_SYNC)
    assert set(calls) == {"get", "h"}
    assert calls["get"] == ["A", "getLogger", "getName", "log", "Error"]
    assert calls["h"] == ["foo", "open", "bar"]


def test_java_synchronized_method_modifier_is_still_a_method():
    src = "class A {\n  synchronized void g() { qux(); }\n  public static synchronized A get() { return mk(); }\n}\n"
    assert _calls("java", src) == {"g": ["qux"], "get": ["mk"]}


CSHARP = """\
class P {
    private bool AddLineIntercepts(LineDef line)
    {
        int s1;
        if (trace.Dx > Fixed.FromInt(16) ||
            trace.Dy < -Fixed.FromInt(16))
        {
            s1 = Geometry.PointOnDivLineSide(line.X, trace);
        }
        else
        {
            s1 = Geometry.PointOnLineSide(trace.X, line);
        }
        return true;
    }
}
"""


def test_csharp_comparison_operand_call_is_not_a_unit():
    calls = _calls("csharp", CSHARP)
    assert list(calls) == ["AddLineIntercepts"]
    assert calls["AddLineIntercepts"] == ["FromInt", "PointOnDivLineSide", "PointOnLineSide"]
