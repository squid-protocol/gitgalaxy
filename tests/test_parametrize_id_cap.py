"""A raw bytes parameter must not put its payload in the node id (#7280: 40k-character ids broke Windows)."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _conftest():
    spec = importlib.util.spec_from_file_location("suite_conftest_7280", Path(__file__).with_name("conftest.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_long_bytes_value_gets_a_short_stable_distinct_id():
    c = _conftest()
    a, b = b"\x00" * 10000, b"\x00" * 9999 + b"\x01"
    ida, idb = c.pytest_make_parametrize_id(a), c.pytest_make_parametrize_id(b)
    assert len(ida) < 200 and ida == c.pytest_make_parametrize_id(a) and ida != idb
    assert c.pytest_make_parametrize_id(bytearray(a)) == ida
    assert c.pytest_make_parametrize_id(b"short") is None


def test_a_node_id_over_the_cap_fails_collection():
    c = _conftest()
    bad = SimpleNamespace(nodeid="t.py::x[" + "a" * 5000 + "]")
    with pytest.raises(pytest.UsageError):
        c.pytest_collection_modifyitems([bad])
