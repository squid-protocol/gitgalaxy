"""C# keyword-family rules after the #8863 validity pass: each family counts what its contract names."""

import sys
import textwrap
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards.languages import csharp as cs_lang

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import family_oracle_ts


def _rule(key):
    for obj in vars(cs_lang).values():
        if isinstance(obj, dict):
            for v in [obj, *[x for x in obj.values() if isinstance(x, dict)]]:
                if key in v and "bitwise_ops" in v:
                    return v[key]
    raise AssertionError(f"csharp {key} rule not found")


POSITIVE = {
    "closures": [
        "var ys = xs.Select(x => x + 1);",
        "xs.Where((a, b) => a > b)",
        "Func<int> f = () => 1;",
        "Run(static @this => @this.Go());",
        "var g = async (e) => await Log(e);",
        "cb: x => x,",
        "            oldSolution => Update(oldSolution),",
        "button.Click += delegate { Go(); };",
        "var h = delegate (int a) { return a; };",
        "return x => x * 2;",
    ],
    "decorators": [
        "    [Fact]",
        "    [Theory, InlineData(1)]",
        "bool TryGet([NotNullWhen(true)] out T? value)",
        "void F(int a, [NotNull] ref string s)",
    ],
    "bitwise_ops": [
        "if ((flags & Mask.A) != 0) {}",
        "x = a | b;",
        "mask |= Flags.Value;",
        "f &= ~Flag.A;",
        "n = x << 2;",
        "var v = a ^ b;",
        "var r = first |\n    second;",
    ],
    "regex_execution": [
        "var m = Regex.Split(s, p);",
        "if (rx.IsMatch(s)) {}",
        "foreach (var m in rx.EnumerateMatches(s)) {}",
    ],
    "time_date_logic": [
        "var d = DateTime.Today;",
        "var t = DateTime.Parse(s);",
        "var d = new DateTime(2020, 1, 1);",
        "var e = Stopwatch.GetTimestamp();",
    ],
    "io": [
        "using var s = new FileStream(p, FileMode.Open);",
        "var r = await client.GetAsync(url);",
        "await s.CopyToAsync(o);",
    ],
}
NEGATIVE = {
    "closures": [
        "public int F(int a) => a + 1;",
        "public string Name => _name;",
        "get => _x;",
        '    "always" => true,',
        "    _ => throw new Exception(),",
        "    SyntaxKind.Foo => 1,",
        "    Foo f => f.Bar,",
        "internal bool G<T>(T t) => t != null;",
    ],
    "decorators": [
        "                [PowerToysModule.Settings] = new ModuleInfo(a),",
        "var v = items[i];",
        "var w = new[] { 1, 2 };",
    ],
    "bitwise_ops": [
        "if (a && b || c) {}",
        "var t = members[^1];",
        "var s = xs[..^2];",
        "var d = new ConcurrentDictionary<(int A, int B), OneOrMany<(int C, int D)>>();",
        "var l = new List<List<int>>();",
        "var p = &value;",
        "where T : struct, IFoo",
    ],
    "regex_execution": ["var x = Regexes.Count;", "var r = other.Match;"],
    "time_date_logic": ["public DateTime Created { get; set; }", "void F(Stopwatch w) {}"],
    "io": ["var n = Path.GetFileName(p);", "var e = Path.Combine(a, b);", "var f = new FileSpec(x);"],
}


@pytest.mark.parametrize(
    ("key", "line"), [(k, line) for k, lines in POSITIVE.items() for line in lines], ids=lambda v: str(v)[:30]
)
def test_contract_forms_count(key, line):
    assert _rule(key).search(line)


@pytest.mark.parametrize(
    ("key", "line"), [(k, line) for k, lines in NEGATIVE.items() for line in lines], ids=lambda v: str(v)[:30]
)
def test_other_constructs_do_not_count(key, line):
    assert not _rule(key).search(line)


def _count(src, name, key):
    oracle = family_oracle_ts.get_oracle("csharp")
    index = oracle.index(textwrap.dedent(src))
    node = next(n for (nm, _line), n in index.items() if nm == name)
    return oracle.count(node)[0].get(key, 0)


def test_oracle_counts_a_parameter_attribute():
    src = "class C { bool TryGet([NotNullWhen(true)] out int v) { v = 0; return true; } }\n"
    assert _count(src, "TryGet", "decorators") == 1
    assert _count("class C { bool Get(out int v) { v = 0; return true; } }\n", "Get", "decorators") == 0
