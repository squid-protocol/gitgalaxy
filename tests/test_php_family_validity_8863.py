"""PHP keyword-family rules after the #8863 validity pass: each family counts what its contract names."""

import pytest

from gitgalaxy.standards.language_standards.languages import php as php_lang


def _rule(key):
    for obj in vars(php_lang).values():
        if isinstance(obj, dict):
            for v in [obj, *[x for x in obj.values() if isinstance(x, dict)]]:
                if key in v and "bitwise_ops" in v:
                    return v[key]
    raise AssertionError(f"php {key} rule not found")


POSITIVE = {
    "bitwise_ops": [
        "if ($flags & self::MASK) {}",
        "$x = $a | $b;",
        "$mask |= FLAG_A;",
        "$f &= ~FLAG_B;",
        "$n = $x << 2;",
        "$v = $a ^ $b;",
        "$m = ~$mask;",
    ],
    "io": [
        "$h = fopen($path, 'r');",
        "$s = file_get_contents($url);",
        "fputs($h, $line);",
        "$l = fgets($h);",
        "unlink($tmp);",
        "$files = scandir($dir);",
        "$db = new PDO($dsn);",
        "$r = mysqli_query($c, $q);",
        "mkdir($d);",
        "$s = fsockopen($host, 80);",
    ],
    "debug_prints": [
        "echo $x;",
        "print 'hello';",
        "var_dump($x);",
        "print_r($x);",
        "printf('%d', $n);",
        "dd($x);",
    ],
    "time_date_logic": [
        "$t = time();",
        "$d = date('Y-m-d');",
        "$d = gmdate('c');",
        "$t = mktime(0, 0, 0, 1, 1, 2020);",
        "$t = microtime(true);",
        "$t = strtotime($s);",
        "$d = new DateTime($s);",
        "$i = new DateInterval('P1D');",
        "$z = new DateTimeZone('UTC');",
        "$d = date_diff($a, $b);",
    ],
    "decorators": [
        "    #[\\Override]",
        '    #[Route("/x")]',
        "public function g(#[\\SensitiveParameter] $p) {}",
        "#[Attribute(Attribute::TARGET_CLASS)]",
    ],
}
NEGATIVE = {
    "bitwise_ops": [
        "if ($a && $b || $c) {}",
        "function f(&$x) {}",
        "foreach ($xs as &$v) {}",
        "function g(int|string $v) {}",
        "$s = <<<EOT",
        "$ok = $a || $b;",
    ],
    "io": [
        "header('Location: /x');",
        "setcookie('a', 'b');",
        "$v = $_GET['id'];",
        "function f(PDO $db) {}",
        "$x = $this->file($a);",
        "$x = Foo::copy($a);",
    ],
    "debug_prints": [
        "$x->dump($y);",
        "$print = 1;",
        "$re = 'dl|dd|dt';",
        "$s = Foo::print($x);",
    ],
    "time_date_logic": [
        "$x = $this->time();",
        "$x = Foo::date($a);",
        "$time = 5;",
        "public DateTime $created;",
    ],
    "decorators": [
        "$re = '#[0-9]{2,3};';",
        "$re = '#[dj]\\.? F#';",
        "$v = $items[$i];",
        "$w = [1, 2];",
    ],
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


def test_oracle_counts_a_php_parameter_attribute_as_a_decorator():
    """The oracle reads `#[\\SensitiveParameter] $p` as an attribute on the declaration it precedes, like the method's own."""
    pytest.importorskip("tree_sitter_language_pack")
    import sys
    import textwrap
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    import family_oracle_ts as ts  # noqa: E402

    src = textwrap.dedent(
        """\
        <?php
        function one($u, #[\\SensitiveParameter] $p = '') { return $u; }
        #[Pure]
        function two(#[A] $a, #[B] $b) { return $a; }
        function none($u) { $f = function (#[X] $y) { return $y; }; return $u; }
        """
    )
    oracle = ts.get_oracle("php")
    index = oracle.index(src)
    got = {nm: oracle.count(n)[0].get("decorators", 0) for (nm, _ln), n in index.items()}
    assert got["one"] == 1
    assert got["two"] == 3
    assert got["none"] == 0
