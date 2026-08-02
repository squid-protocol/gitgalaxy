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
    ]

    invalid = [
        ("$className::class;", None),
        ("$class = class_exists('Foo');", None),
    ]

    xfail_invalid = [
        ("// class Foo", None),
        ("$obj = new class extends Base {};", None), # Can't name anonymous classes
        ("$obj = new class($a) implements Foo {};", None),
        ("class /* evil */ Foo /* extends */ extends Bar", None),
        ("$s = 'class Foo {}';", None),
        ("$class = 'MyClass';", None),
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
        ("function foo(public int $id, private readonly string $name, protected ?float $val = null)", "(public int $id, private readonly string $name, protected ?float $val = null)"),
        ("function foo(#[SensitiveParameter] string $password, #[Attr('val')] int $x)", "(#[SensitiveParameter] string $password, #[Attr('val')] int $x)"),
        ("function foo(\n    int $x,\n    // some comment\n    /* inline */ string $y = \n    'default'\n)", "(\n    int $x,\n    // some comment\n    /* inline */ string $y = \n    'default'\n)"),
        ("function foo($arr = [1, [2, 3], 'foo' => ['bar']])", "($arr = [1, [2, 3], 'foo' => ['bar']])"),
        ("function foo($callback = function($x) { return $x; })", "($callback = function($x) { return $x; })"),
        ("function foo(int $a, string $b,)", "(int $a, string $b,)"),
        ("function foo( (A&B)|C $obj )", "( (A&B)|C $obj )"),
    ]

    invalid = [
        ("($array[$index])", None),
        ("($a + $b * (2 - $c))", None),
        ("myFunction($a, $b);", None),
    ]

    xfail_invalid = [
        ("('($a, $b)')", None),
    ]

    for payload, expected in valid:
        assert_valid_match(PHP_RULES["args"], payload, expected, "php.args")

    for payload, _ in invalid:
        assert_invalid_no_match(PHP_RULES["args"], payload, "php.args")
        
    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="No block shielding"))


def test_php_dependency_capture():
    valid = [
        ("require 'vendor/autoload.php';", "vendor/autoload.php"),
        ("require('file.php');", "file.php"),
        ("require_once $configFile;", "$configFile"),
        ("include \"templates/header.php\";", "templates/header.php"),
        ("include_once(__DIR__ . '/config.php');", "__DIR__ . '/config.php'"),
        ("use App\\Services\\UserService;", "App\\Services\\UserService"),
        ("use App\\Models\\User as UserModel;", "App\\Models\\User"),
        ("use function array_map;", "array_map"),
        ("use const PHP_VERSION;", "PHP_VERSION"),
        ("use App\\Http\\{Request, Response};", "App\\Http\\{Request, Response}"),
        ("use App\\Helpers\\{function debug, const DEBUG_MODE};", "App\\Helpers\\{function debug, const DEBUG_MODE}"),
        ("use Notifiable, HasFactory;", "Notifiable, HasFactory"),
        ("require dirname(__FILE__) . '/../bootstrap.php';", "dirname(__FILE__) . '/../bootstrap.php'"),
        ("use App\\Models\\\n    {\n        User,\n        Post\n    };", "App\\Models\\\n    {\n        User,\n        Post\n    }"),
        ("require_once /* load it */ 'file.php';", "file.php"),
    ]

    invalid = [
        ("namespace App\\Http;", None),
        ("function($x) use ($y, &$z) {", None),
    ]
    
    xfail_invalid = [
        ("// require 'test.php';", None),
        ("$str = 'require \"foo.php\";';", None),
        ("$str = 'use App\\\\Foo;';", None),
    ]

    for payload, expected in valid:
        assert_valid_dependency_match(PHP_RULES["_dependency_capture"], payload, expected, "php._dependency_capture")

    for payload, _ in invalid:
        assert_invalid_no_match(PHP_RULES["_dependency_capture"], payload, "php._dependency_capture")
        
    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="No block shielding"))
