"""#9335: C++ keyword-family validity on the pinned crucible: `decorators` (an attribute that precedes a declaration, not a
`[[fallthrough]];` statement), `panics_and_aborts` and `thread_sleeps` (call form, not a bare word), `bitwise_ops` (a shift or mask,
not a stream insertion, a destructor name or a reference declarator), and the oracle's `io` / `bitwise` readings."""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_TOOLS = str(Path(__file__).resolve().parents[2] / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
_RULES = LANGUAGE_DEFINITIONS["cpp"]["rules"]


def _fires(rule: str, src: str) -> bool:
    return bool(_RULES[rule].search(_PRISM.split_streams(src, "cpp")["code_stream"]))


@pytest.mark.parametrize(
    "src",
    [
        "[[nodiscard]] int f();",
        "[[maybe_unused]] auto x = g();",
        "struct [[deprecated]] S {};",
        "[[gnu::always_inline]] void f();",
    ],
)
def test_attribute_before_a_declaration_counts(src):
    assert _fires("decorators", src), src


@pytest.mark.parametrize("src", ["case 1:\n    f();\n    [[fallthrough]];\ncase 2:", "[[likely]];"])
def test_statement_attribute_does_not_count(src):
    assert not _fires("decorators", src), src


@pytest.mark.parametrize(
    "src",
    [
        "void f() { throw std::runtime_error(m); }",
        "void f() { std::terminate(); }",
        "void f() { abort(); }",
        "void f() { std::exit(1); }",
        "void f() { exit(2); }",
        "void f() { ::_Exit(3); }",
        "void f() { quick_exit(0); }",
        "void f() { longjmp(env, 1); }",
    ],
)
def test_exit_in_call_form_counts(src):
    assert _fires("panics_and_aborts", src), src


@pytest.mark.parametrize(
    "src",
    [
        "bool exit = false;\nexit = true;",
        "while (!exit) { step(); }",
        "span.exit();",
        "p->abort();",
        "int should_exit_now = 1;",
        "// we never abort here",
        'auto m = "leaked at exit (run with -v)";',
    ],
)
def test_bare_exit_word_does_not_count(src):
    assert not _fires("panics_and_aborts", src), src


@pytest.mark.parametrize(
    "src",
    [
        "void f() { sleep(1); }",
        "void f() { usleep(500); }",
        "void f() { Sleep(10000); }",
        "void f() { SleepEx(5, TRUE); }",
        "void f() { std::this_thread::sleep_for(std::chrono::seconds(1)); }",
        "void f() { std::this_thread::sleep_until(t); }",
        "void f() { delay(20); }",
    ],
)
def test_sleep_calls_count(src):
    assert _fires("thread_sleeps", src), src


@pytest.mark.parametrize(
    "src",
    [
        'auto a = "--frame-delay";',
        "int delay = 3;",
        "timer.delay(5);",
        "int sleep_time = 3;",
    ],
)
def test_sleep_words_do_not_count(src):
    assert not _fires("thread_sleeps", src), src


@pytest.mark.parametrize(
    "src",
    [
        "x = a ^ b;",
        "x ^= m;",
        "x = ~mask;",
        "y = f(~0u);",
        "return ~x;",
        "x <<= 2;",
        "auto m = 1 << n;",
        "auto m = x << 3;",
        "auto m = (uint64_t(v)) << SLOT_BITS;",
        "y = x >> 8;",
        "if (flags & PROPERTY_USAGE_STORAGE) {}",
        "auto b = (int)get_mask() & 0x7;",
        "if (wParam&PM_REMOVE) {}",
        "auto k = Mod::META | Mod::CTRL | Key::KEY_5;",
        "auto k = FLAG_A | FLAG_B;",
        "x |= y;",
        "x &= y;",
    ],
)
def test_bitwise_forms_count(src):
    assert _fires("bitwise_ops", src), src


@pytest.mark.parametrize(
    "src",
    [
        'LOG_DEBUG(L"offset " << offset << L" is past the end");',
        's<<L"isHidden=\\""<<this->isHidden;',
        'std::cout << "hi" << std::endl;',
        "std::cin >> n;",
        "std::vector<std::vector<int>> grid;",
        "Foo::~Foo() {\n}",
        "virtual ~Foo();",
        "p->~String();",
        "for (const String &extension : extensions) {}",
        "Ref<A> &r = x;",
        "if (a && b) {}",
        "if (a || b) {}",
        "auto f = [&](int x) { return x; };",
        "foo(&x, &y);",
        "if (a && FLAG_ON) {}",
        "if (a || FLAG_ON) {}",
    ],
)
def test_non_bitwise_forms_do_not_count(src):
    assert not _fires("bitwise_ops", src), src


# --- the oracle's readings (tests/tools/family_oracle_specs_c.py) -------------------------------------------------------------


def _oracle_counts(src: str):
    pytest.importorskip("tree_sitter_language_pack")
    import family_oracle_specs_c as c
    import family_oracle_ts as fts

    c.register()
    oracle = fts.get_oracle("cpp")
    funcs = oracle.index(src)
    assert funcs, "no function indexed"
    n, tokens = oracle.count(next(iter(funcs.values())))
    return n, tokens


@pytest.mark.parametrize(
    "body",
    [
        'LOG(L"x " << n << L" y");',
        's << L"a" << b;',
        "auto p = (WPARAM)&func;",
    ],
)
def test_oracle_does_not_read_insertion_or_cast_as_bitwise(body):
    n, _ = _oracle_counts("void f() {\n" + body + "\n}\n")
    assert n.get("bitwise", 0) == 0, body


@pytest.mark.parametrize("body", ["auto m = a & MASK;", "auto s = x << 3;", "auto k = A | B;"])
def test_oracle_still_reads_shifts_and_masks(body):
    n, _ = _oracle_counts("void f() {\n" + body + "\n}\n")
    assert n.get("bitwise", 0) == 1, body


@pytest.mark.parametrize(
    "body",
    [
        "auto cb = std::bind(f, 1);",
        "w.connect(sig, cb);",
        "obj->write(buf, n);",
        "Object::connect(a, b);",
        "auto c = fn.bind(x);",
    ],
)
def test_oracle_io_ignores_members_and_signals(body):
    n, _ = _oracle_counts("void f() {\n" + body + "\n}\n")
    assert n.get("io", 0) == 0, body


@pytest.mark.parametrize(
    "body",
    [
        "int s = socket(AF_INET, SOCK_STREAM, 0);",
        "connect(s, addr, len);",
        "auto f = FileAccess::open(p, m);",
        "::bind(s, a, l);",
    ],
)
def test_oracle_io_keeps_free_and_file_calls(body):
    n, _ = _oracle_counts("void f() {\n" + body + "\n}\n")
    assert n.get("io", 0) == 1, body


@pytest.mark.parametrize("src", ["auto f = FileAccess::open(p, FileAccess::READ);", "DirAccess::open(path);"])
def test_static_open_is_io(src):
    assert _fires("io", src), src


@pytest.mark.parametrize("src", ["auto f = obj.open(p);", "foo::open_all(x);", "x = lower::open(a);"])
def test_other_open_is_not_io(src):
    assert not _fires("io", src), src
