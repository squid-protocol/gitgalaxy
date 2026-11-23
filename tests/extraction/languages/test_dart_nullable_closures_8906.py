"""#8906: Dart `branch` ignores nullable `T?` / `?.`; `closures` ignores a declaration's `=>`;
`bitwise_ops` ignores a generic's closing `>>` (#8866 shape)."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

RULES = LANGUAGE_DEFINITIONS["dart"]["rules"]


def _n(rule, src):
    return len(RULES[rule].findall(src))


@pytest.mark.parametrize(
    ("src", "n"),
    [
        ("int? nullable(int? a) { return a; }", 0),
        ("int chain(Foo? a) { return a?.x; }", 0),
        ("int opt(Foo? a) { return a?.x ?? 1; }", 1),
        ("int idx(List<int>? a) { return a?[0]; }", 0),
        ("void c(Foo? a) { a?..b(); }", 0),
        ("List<int?> f(Map<String, int>? m) { return []; }", 0),
        ("void Function(int)? cb;", 0),
        ("var l = [...?other];", 0),
        ("int t(bool a) { return a ? 1 : 2; }", 1),
        ("var v = isDark\n    ? A()\n    : B();", 1),
        ("x ??= 3;", 1),
        ("int realIf(int a) { if (a > 1) { return 1; } return 0; }", 1),
    ],
)
def test_branch_counts_ternary_and_coalesce_only(src, n):
    assert _n("branch", src) == n, src


@pytest.mark.parametrize(
    "src",
    [
        "int arrow(int a) => a + 1;",
        "int get x => _x;",
        "Vec operator +(Vec o) => _add(o);",
        "Future<void> run() async => work();",
        "var s = switch (x) { 1 => 'a', _ => 'b' };",
        "case Foo() => 1;",
    ],
)
def test_declaration_arrow_is_not_a_closure(src):
    assert _n("closures", src) == 0, src


@pytest.mark.parametrize(
    "src",
    [
        "var f = (x) => x + 1;",
        "list.map((x) => x * 2);",
        "foo(a, (b) => b);",
        "Function f() { return (x) => x; }",
        "button.onTap(() { go(); });",
        "run(() async { await go(); });",
        "run(() async => await go());",
    ],
)
def test_function_expression_is_a_closure(src):
    assert _n("closures", src) == 1, src


def test_closures_stay_bounded_on_unclosed_parens():
    from time import process_time

    t = process_time()
    RULES["closures"].findall("x = (" * 4000)
    assert process_time() - t < 3.0


@pytest.mark.parametrize(
    "src",
    [
        "List<List<int>> generics(List<List<int>> m) { return m; }",
        "Map<String, List<List<int>>> deep() { return {}; }",
    ],
)
def test_closing_generics_are_not_shifts(src):
    assert _n("bitwise_ops", src) == 0, src


@pytest.mark.parametrize(
    ("src", "n"),
    [
        ("int s(int a) { return a << 2; }", 1),
        ("int s(int a) { return a >> 2; }", 1),
        ("int s(int a) { return a>>2; }", 1),
        ("int s(int a) { return a >>> 2; }", 1),
        ("int s(int a) { a >>= 2; return a; }", 1),
        ("List<List<int>> m = f(a >> 2, b << 1);", 2),
    ],
)
def test_real_shifts_still_count(src, n):
    assert _n("bitwise_ops", src) == n, src
