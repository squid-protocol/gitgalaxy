"""#5463: every high_risk_execution alternative declares the languages it is a vector in."""

import pytest

from gitgalaxy.security.security_lens import SecurityLens


@pytest.fixture(scope="module")
def lens():
    return SecurityLens()


def _hits(lens, text, language):
    return lens.scan_content(text, language=language)["counts"]["high_risk_execution"]


# (language, source) pairs that must NOT fire.
CLEAN = [
    ("c", "void f(int x) { require( x > 0 ); }"),
    ("cpp", "void f(int x) { require( x ); }"),
    ("cpp", "auto e2 = asio::require(e, asio::execution::blocking.never);"),
    ("lua", 'local m = require("mod")'),
    ("lua", "local m = require(name)"),
    ("c", 'eval("x");'),
    ("cpp", 'assert("msg" && ok);'),
    ("go", "system(x)"),
    ("rust", 'setTimeout("x")'),
    ("java", "child_process.exec(x)"),
    ("c", "$a($_POST)"),
    ("cpp", "importlib.import_module(x)"),
    ("java", "Assembly.Load(x)"),
    ("c", "__builtins__[x]"),
    ("c", "document.write(x)"),
    ("cpp", "shell_exec(x)"),
    ("java", "BPXBATCH"),
]
# (language, source) pairs that must fire.
FIRES = [
    ("javascript", "const m = require(userInput);"),
    ("typescript", "const m = require(userInput);"),
    ("ruby", "require(path)"),
    ("php", "require($path);"),
    ("javascript", 'eval("x")'),
    ("python", 'eval("x")'),
    ("javascript", 'setTimeout("x", 1)'),
    ("javascript", "document.write(x)"),
    ("php", "shell_exec($c);"),
    ("php", "passthru($c);"),
    ("c", "system(cmd);"),
    ("cpp", "system(cmd);"),
    ("php", 'assert("$x");'),
    ("javascript", "child_process.exec(x)"),
    ("python", "importlib.import_module(x)"),
    ("python", "getattr(__import__('os'), 'system')"),
    ("csharp", "Assembly.Load(bytes);"),
    ("php", "$f($_POST['a']);"),
    ("jcl", "//S1 EXEC PGM=IKJEFT01"),
    ("cobol", "EXEC CICS LINK PROGRAM(PGM) END-EXEC"),
    ("yaml", "run: echo ${{ github.event.issue.title }}"),
    ("javascript", "this['a'+'b'+'c'](x)"),
]


@pytest.mark.parametrize(("language", "text"), CLEAN)
def test_inapplicable_alternative_is_dropped(lens, language, text):
    assert _hits(lens, text, language) == 0


@pytest.mark.parametrize(("language", "text"), FIRES)
def test_applicable_alternative_fires(lens, language, text):
    assert _hits(lens, text, language) >= 1, text


@pytest.mark.parametrize("text", ["require(x)", "eval('x')", "system(x)", 'setTimeout("x")'])
def test_unknown_language_keeps_current_behaviour(lens, text):
    assert _hits(lens, text, None) == 1


def test_minified_fast_screen_is_scoped(lens):
    blob = "a=1;" * 5 + "x" * 400 + " " + ("y" * 400 + "\n") * 5 + " eval(x);"
    assert _hits(lens, blob, None) >= 1
    assert _hits(lens, blob, "c") == 0
