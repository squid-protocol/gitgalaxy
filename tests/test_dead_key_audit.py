import ast

from dead_key_audit import KeyVisitor, find_dead_keys, ALLOWLIST


def _visit(source: str) -> KeyVisitor:
    tree = ast.parse(source)
    visitor = KeyVisitor("synthetic.py")
    visitor.visit(tree)
    return visitor


# ==============================================================================
# TEST 1: READ DETECTION
# ==============================================================================
def test_detects_get_and_pop_and_subscript_reads():
    v = _visit(
        "x.get('a')\n"
        "x.get('b', 1)\n"
        "x.pop('c')\n"
        "y = x['d']\n"
    )
    assert set(v.reads.keys()) == {"a", "b", "c", "d"}


def test_variable_keyed_reads_are_invisible_not_guessed():
    """A read keyed by a variable can't be resolved to a literal -- must be silently skipped, not misattributed."""
    v = _visit("k = 'a'\nx.get(k)\n")
    assert v.reads == {}


# ==============================================================================
# TEST 2: WRITE DETECTION
# ==============================================================================
def test_detects_subscript_store_and_dict_literal_and_setdefault_writes():
    v = _visit(
        "x['a'] = 1\n"
        "y = {'b': 1, 'c': 2}\n"
        "x.setdefault('d', [])\n"
        "x.update(e=1)\n"
        "z = dict(f=1)\n"
    )
    assert v.writes == {"a", "b", "c", "d", "e", "f"}


# ==============================================================================
# TEST 3: F-STRING PREFIX WRITES (#325 -- the sec_{key} shape)
# ==============================================================================
def test_fstring_templated_subscript_write_is_a_prefix_write():
    v = _visit('sec_key = "reflection_metaprogramming"\nx[f"sec_{sec_key}"] = 1\n')
    assert v.prefix_writes == {"sec_"}
    assert v.writes == set()


def test_fstring_templated_setdefault_is_a_prefix_write():
    v = _visit('x.setdefault(f"sec_{k}", [])\n')
    assert v.prefix_writes == {"sec_"}


def test_fstring_templated_dictcomp_key_is_a_prefix_write():
    v = _visit('d = {f"sec_{k}": v for k, v in items}\n')
    assert v.prefix_writes == {"sec_"}


def test_fstring_with_no_leading_literal_yields_no_prefix():
    """f"{x}_suffix" has no usable leading literal -- must not fabricate a prefix."""
    v = _visit('x[f"{k}_suffix"] = 1\n')
    assert v.prefix_writes == set()


# ==============================================================================
# TEST 4: find_dead_keys() end-to-end (read/write cross-reference)
# ==============================================================================
def test_find_dead_keys_flags_read_without_any_write(tmp_path, monkeypatch):
    _write_scan_root(tmp_path, "mod.py", "x.get('orphan_key')\n")
    monkeypatch.setattr("dead_key_audit.SCAN_ROOTS", [tmp_path])

    dead = find_dead_keys()
    assert "orphan_key" in dead


def test_find_dead_keys_does_not_flag_a_read_with_a_matching_write(tmp_path, monkeypatch):
    _write_scan_root(tmp_path, "mod.py", "x.get('k')\nx['k'] = 1\n")
    monkeypatch.setattr("dead_key_audit.SCAN_ROOTS", [tmp_path])

    dead = find_dead_keys()
    assert "k" not in dead


def test_find_dead_keys_honors_prefix_writes_across_files(tmp_path, monkeypatch):
    """A read of "sec_foo" must be covered by a DIFFERENT file's f"sec_{...}" write."""
    _write_scan_root(tmp_path, "producer.py", 'k = "foo"\nx[f"sec_{k}"] = 1\n')
    _write_scan_root(tmp_path, "consumer.py", "y.get('sec_foo')\n")
    monkeypatch.setattr("dead_key_audit.SCAN_ROOTS", [tmp_path])

    dead = find_dead_keys()
    assert "sec_foo" not in dead


def test_find_dead_keys_respects_the_allowlist(tmp_path, monkeypatch):
    allowlisted_key = next(iter(ALLOWLIST))
    _write_scan_root(tmp_path, "mod.py", f"x.get('{allowlisted_key}')\n")
    monkeypatch.setattr("dead_key_audit.SCAN_ROOTS", [tmp_path])

    dead = find_dead_keys()
    assert allowlisted_key not in dead


def _write_scan_root(tmp_path, filename: str, source: str) -> None:
    (tmp_path / filename).write_text(source, encoding="utf-8")
