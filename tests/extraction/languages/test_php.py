import sys
from pathlib import Path

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

import pytest
from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

PHP_RULES = LANGUAGE_DEFINITIONS["php"]["rules"]


def test_php_func_start():
    valid = [
        ("function foo()", "foo"),
        ("public static function bar()", "bar"),
        ("function &baz()", "baz"),
        ("#[Attr]\npublic function getApi()", "getApi"),
        ("#[Attr1, Attr2('val')]\n#[Attr3]\nfunction multiAttr()", "multiAttr"),
        ("function foo(): string", "foo"),
        ("function foo(): int|false", "foo"),
        ("function foo(): \\A&\\B", "foo"),
        ("function foo(): (A&B)|C", "foo"),
        ("function\t \n weirdSpace \n ( )", "weirdSpace"),
        ("function foo(): \n    array|\n    null", "foo"),
        ("function & myFunc()", "myFunc"),
        (
            "#[Attr]\n    public static fUnCtIoN /* case insensitivity test */ extract_me (\n"
            "        #[Inject] \n"
            "        public readonly (A&B)|C &$var1 = new DefaultClass(\n"
            '            "string with ) and , inside", \n'
            "            ['array', 'with', 'function() {}']\n"
            "        ),\n"
            "        int|float $var2 = (1 + (2 * 3)),\n"
            "        ...$variadic,\n"
            "    ) : (X&Y)|Z {",
            "extract_me",
        ),
        (
            "function\n    \n        spaced_out_func\n    (\n        \n        $arg1\n        ,\n        $arg2\n        \n    )\n    :\n    void",
            "spaced_out_func",
        ),
    ]

    invalid = [
        ("$functionName();", None),
        ("$obj->functionCall();", None),
        ("$obj?->functionCall();", None),
        ("$function = true;", None),
    ]

    xfail_invalid = [
        # Un-AST shielded lookalikes
        ("// function commentedOut()", None),
        ("/* \n function inComment() \n */", None),
        ("public /* wtf */ function /* inline */ commentFunc()", None),
        ("$str = 'function foo() {';", None),
        ('$str = "public function bar()\\n";', None),
        ("function fake_func_heredoc() {}", None),
        ("function ( $with_args ) {", None),
        ("function commentFunc(int $x) {}", None),
        ("function not_php() {}", None),
        ("function() use ($x)", None),
    ]

    for payload, expected in valid:
        assert_valid_match(PHP_RULES["func_start"], payload, expected, "php.func_start")

    for payload, _ in invalid:
        assert_invalid_no_match(PHP_RULES["func_start"], payload, "php.func_start")

    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="No block shielding"))


def test_php_class_start():
    valid = [
        ("class SimpleClass", "SimpleClass"),
        ("abstract class AbstractClass", "AbstractClass"),
        ("final class FinalClass", "FinalClass"),
        ("readonly class ReadOnlyClass", "ReadOnlyClass"),
        ("final readonly class StrictClass", "StrictClass"),
        ("interface LoggerInterface", "LoggerInterface"),
        ("trait ReusableTrait", "ReusableTrait"),
        ("enum Suit", "Suit"),
        ("enum Status: int", "Status"),
        ("class Child extends ParentClass", "Child"),
        ("class Worker implements Runnable, Serializable", "Worker"),
        ("class Complex extends Base implements A, B", "Complex"),
        ("#[AllowDynamicProperties]\nclass DynamicClass", "DynamicClass"),
        ("class Multiline\n    extends Base\n    implements \n        InterfaceA,\n        InterfaceB", "Multiline"),
        (
            "#[\\\n    \\Attribute1,\n"
            "    \\Attribute2('string containing \"class Fake {\" to break regex'),\n"
            "    \\Attribute3(fn($x) => $x),\n"
            "    \\Attribute4(new class { public function inner() {} })\n"
            "]\n"
            "final readonly class\n"
            "/* sneaky block comment */\n"
            "DeviousClass \n"
            "extends \\Some\\Base\\Class \n"
            "implements \n"
            "    \\Interface1, \n"
            "    \\Interface2",
            "DeviousClass",
        ),
        ("class\n    \n    SpacedOutClass", "SpacedOutClass"),
    ]

    invalid = [
        ("$className::class;", None),
        ("$class = class_exists('Foo');", None),
    ]

    xfail_invalid = [
        ("// class Foo", None),
        ("$obj = new class extends Base {};", None),  # Can't name anonymous classes
        ("$obj = new class($a) implements Foo {};", None),
        ("class /* evil */ Foo /* extends */ extends Bar", None),
        ("$s = 'class Foo {}';", None),
        ("$class = 'MyClass';", None),
        ("class FakeClassHeredoc {", None),
        ("class NotPhpClass {}", None),
        ("class RealClass {}", None),
        ("class NotAnotherClass {}", None),
        ("class ClassInArray {}", None),
    ]

    for payload, expected in valid:
        assert_valid_match(PHP_RULES["class_start"], payload, expected, "php.class_start")

    for payload, _ in invalid:
        assert_invalid_no_match(PHP_RULES["class_start"], payload, "php.class_start")

    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="No block shielding"))


def test_php_args():
    valid = [
        ("function foo()", "()"),
        ("function foo($a, $b)", "($a, $b)"),
        ("function foo(\\DateTime $date, array $options)", "(\\DateTime $date, array $options)"),
        ("function foo(int|float $number, string|null $text)", "(int|float $number, string|null $text)"),
        ("function foo(int $a = 1, string $b = 'default')", "(int $a = 1, string $b = 'default')"),
        ("function foo(array $config = ['key' => 'value'])", "(array $config = ['key' => 'value'])"),
        ("function foo($param = self::DEFAULT_VALUE)", "($param = self::DEFAULT_VALUE)"),
        ("function foo(string ...$strings)", "(string ...$strings)"),
        ("function foo(array &$data, &$flag)", "(array &$data, &$flag)"),
        (
            "function foo(public int $id, private readonly string $name, protected ?float $val = null)",
            "(public int $id, private readonly string $name, protected ?float $val = null)",
        ),
        (
            "function foo(#[SensitiveParameter] string $password, #[Attr('val')] int $x)",
            "(#[SensitiveParameter] string $password, #[Attr('val')] int $x)",
        ),
        (
            "function foo(\n    int $x,\n    // some comment\n    /* inline */ string $y = \n    'default'\n)",
            "(\n    int $x,\n    // some comment\n    /* inline */ string $y = \n    'default'\n)",
        ),
        ("function foo($arr = [1, [2, 3], 'foo' => ['bar']])", "($arr = [1, [2, 3], 'foo' => ['bar']])"),
        ("function foo($callback = function($x) { return $x; })", "($callback = function($x) { return $x; })"),
        ("function foo(int $a, string $b,)", "(int $a, string $b,)"),
        ("function foo( (A&B)|C $obj )", "( (A&B)|C $obj )"),
        (
            "function extract_me (\n"
            "        #[Inject] \n"
            "        public readonly (A&B)|C &$var1 = new DefaultClass(\n"
            '            "string with ) and , inside", \n'
            "            ['array', 'with', 'function() {}']\n"
            "        ),\n"
            "        int|float $var2 = (1 + (2 * 3)),\n"
            "        ...$variadic,\n"
            "    )",
            "(\n"
            "        #[Inject] \n"
            "        public readonly (A&B)|C &$var1 = new DefaultClass(\n"
            '            "string with ) and , inside", \n'
            "            ['array', 'with', 'function() {}']\n"
            "        ),\n"
            "        int|float $var2 = (1 + (2 * 3)),\n"
            "        ...$variadic,\n"
            "    )",
        ),
    ]

    invalid = [
        ("($array[$index])", None),
        ("($a + $b * (2 - $c))", None),
        ("myFunction($a, $b);", None),
    ]

    xfail_invalid = [
        ("('($a, $b)')", None),
        (
            "function deeply_nested_args(\n"
            "    $a = [[[['function func_in_array() {}', \"class ClassInArray {}\"]]]],\n"
            "    $b = array(array(array('use Deep\\Dep;'))),\n"
            "    $c = fn($x) => (fn($y) => $y)($x)\n"
            ")",
            None,
        ),
    ]

    for payload, expected in valid:
        assert_valid_match(PHP_RULES["args"], payload, expected, "php.args")

    for payload, _ in invalid:
        assert_invalid_no_match(PHP_RULES["args"], payload, "php.args")

    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="No block shielding"))


def test_php_dependency_capture_statement_anchor():
    """#3609: only a whole-word `require`/`include`/`use` in statement position
    starts a capture, and the captured expression stays on its line."""
    from gitgalaxy.galaxyscope import extract_raw_imports

    php = LANGUAGE_DEFINITIONS["php"]
    capture = PHP_RULES["_dependency_capture"]
    real = {
        "include_once ABSPATH . 'wp-admin/includes/admin.php';": "ABSPATH . 'wp-admin/includes/admin.php'",
        "$config = require __DIR__ . '/cfg.php';": "__DIR__ . '/cfg.php'",
        "return require 'x.php';": "x.php",
        "if ( ! defined('X') ) require_once 'y.php';": "y.php",
        "} else include 'e.php';": "e.php",
        "@include 'z.php';": "z.php",
        "<?php require 'first.php';": "first.php",
    }
    for payload, token in real.items():
        assert extract_raw_imports(capture, payload, php) == {token}, payload
    junk = [
        "$a = array( 'require' => 1, 'require_once' => 2 );",  # array keys
        "$this->include($x);",  # method named include
        "Foo::include('x');",  # static method named include
        "$required = true;",
        "$msg = 'please include the file; thanks';",  # prose in a string
        "echo 'a file that should have been included here; ok';",
        "$path = 'wp-includes/formatting.php'; $x = 1;",  # `includes/` path
        "$f = function () use ($x) { return $x; };",  # closure use
        "$m = $mode; // required\n$x = include_path();",
    ]
    for payload in junk:
        assert extract_raw_imports(capture, payload, php) == set(), payload
    # One line only: an unterminated include never swallows the next lines.
    assert extract_raw_imports(capture, "include $a\n$b = 1;\n", php) == set()


def test_php_dependency_capture_redos_immunity():
    """#3609: the keyword's blanks, the expression and its trailing blanks are
    bounded, so a long blank run or a long unterminated line stays linear."""
    capture = PHP_RULES["_dependency_capture"]
    for payload in ["require " + " " * 100000, "require (" + " " * 100000, "require " + "a " * 50000]:
        assert_redos_immune(capture, payload, timeout_sec=3.0)


def test_php_dependency_capture():
    valid = [
        ("require 'vendor/autoload.php';", "vendor/autoload.php"),
        ("require('file.php');", "file.php"),
        ("require_once $configFile;", "$configFile"),
        ('include "templates/header.php";', "templates/header.php"),
        ("include_once(__DIR__ . '/config.php');", "__DIR__ . '/config.php'"),
        ("use App\\Services\\UserService;", "App\\Services\\UserService"),
        ("use App\\Models\\User as UserModel;", "App\\Models\\User"),
        ("use function array_map;", "array_map"),
        ("use const PHP_VERSION;", "PHP_VERSION"),
        ("use App\\Http\\{Request, Response};", "App\\Http\\{Request, Response}"),
        ("use App\\Helpers\\{function debug, const DEBUG_MODE};", "App\\Helpers\\{function debug, const DEBUG_MODE}"),
        ("use Notifiable, HasFactory;", "Notifiable, HasFactory"),
        ("require dirname(__FILE__) . '/../bootstrap.php';", "dirname(__FILE__) . '/../bootstrap.php'"),
        (
            "use App\\Models\\\n    {\n        User,\n        Post\n    };",
            "App\\Models\\\n    {\n        User,\n        Post\n    }",
        ),
        ("require_once /* load it */ 'file.php';", "file.php"),
        (
            "uSe \\Vendor\\Package\\{\n"
            "    ClassA,\n"
            "    SubNamespace\\ClassB as AliasB,\n"
            "    fUnCtIoN func_c,\n"
            "    const CONST_D,\n"
            "};",
            "\\Vendor\\Package\\{\n"
            "    ClassA,\n"
            "    SubNamespace\\ClassB as AliasB,\n"
            "    fUnCtIoN func_c,\n"
            "    const CONST_D,\n"
            "}",
        ),
    ]

    invalid = [
        ("namespace App\\Http;", None),
        ("function($x) use ($y, &$z) {", None),
        ("use SomeTrait, AnotherTrait {", None),
        ("AnotherTrait::method as alias;", None),
    ]

    xfail_invalid = [
        ("// require 'test.php';", None),
        ("$str = 'require \"foo.php\";';", None),
        ("$str = 'use App\\\\Foo;';", None),
        ("use Fake\\Dependency\\Nowdoc;", None),
    ]

    for payload, expected in valid:
        assert_valid_dependency_match(PHP_RULES["_dependency_capture"], payload, expected, "php._dependency_capture")

    for payload, _ in invalid:
        assert_invalid_no_match(PHP_RULES["_dependency_capture"], payload, "php._dependency_capture")

    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="No block shielding"))
