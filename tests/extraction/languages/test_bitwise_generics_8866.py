"""#8866: a `>>` that closes a generic argument list is not a bitwise shift."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

GENERIC_LANGS = {
    "java": [
        "Map<String, List<String>> generics(Map<String, List<String>> m) { return m; }",
        "List<List<String>> x = new ArrayList<List<String>>();",
        "Map<String, List<List<String>>> deep() { return null; }",
    ],
    "rust": [
        "fn generics(m: HashMap<String, Vec<String>>) -> HashMap<String, Vec<String>> { m }",
        "let v: Vec<Vec<u8>> = Vec::<Vec<u8>>::new();",
    ],
    "typescript": [
        "function generics(m: Map<string, Array<string>>): Map<string, Array<string>> { return m; }",
        "const x = new Map<string, Array<string>>();",
    ],
    "csharp": [
        "Dictionary<string, List<string>> Generics(Dictionary<string, List<string>> m) { return m; }",
        "var x = new Dictionary<string, List<string>>();",
    ],
}

# (source, expected count of shift operators)
SHIFTS = [
    ("int s(int a) { return a << 2; }", 1),
    ("int s(int a) { return a >> 2; }", 1),
    ("int s(int a) { return a>>2; }", 1),
    ("int s(int a) { return (a) >> b; }", 1),
    ("int s(int a) { a >>= 2; return a; }", 1),
    ("int s(int a) { return arr[0] >> 3; }", 1),
]


def _rule(lang):
    return LANGUAGE_DEFINITIONS[lang]["rules"]["bitwise_ops"]


@pytest.mark.parametrize("lang", sorted(GENERIC_LANGS))
def test_closing_generics_are_not_shifts(lang):
    for src in GENERIC_LANGS[lang]:
        assert _rule(lang).findall(src) == [], src


@pytest.mark.parametrize("lang", sorted(GENERIC_LANGS))
@pytest.mark.parametrize(("src", "n"), SHIFTS)
def test_real_shifts_still_count(lang, src, n):
    assert len(_rule(lang).findall(src)) == n, src


@pytest.mark.parametrize("lang", sorted(GENERIC_LANGS))
def test_generic_and_shift_in_one_function(lang):
    src = "Map<String, List<String>> m = f(a >> 2, b << 1);"
    assert len(_rule(lang).findall(src)) == 2


def test_java_unsigned_shift_counts_but_nested_generic_does_not():
    r = _rule("java")
    assert len(r.findall("int s(int a) { return a >>> 2; }")) == 1
    assert r.findall("Map<String, List<List<String>>> m;") == []
