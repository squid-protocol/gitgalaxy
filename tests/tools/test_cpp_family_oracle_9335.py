"""#9335: the C++ family oracle's `io` and `bitwise_ops` readings (a stream insertion or `(Type)&x` cast is not bitwise; a member
call, `std::bind` or a qualified socket verb is not io)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


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


def test_oracle_reads_attribute_on_a_local_declaration_as_a_decorator():
    n, tokens = _oracle_counts("void f() {\n[[maybe_unused]] auto x = 1;\n}\n")
    assert n.get("decorators") == 1
    assert tokens["decorators"]["[[maybe_unused]]"] == 1


def test_oracle_does_not_read_a_standalone_attribute_statement_as_a_decorator():
    n, _ = _oracle_counts("void f(int a) {\nswitch (a) {\ncase 1:\n[[fallthrough]];\ndefault:;\n}\n}\n")
    assert n.get("decorators", 0) == 0
