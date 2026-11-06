"""
#4108 slice 21: an Erlang module call (`:rpc.call`, `:gen_tcp.send`, `:ets.insert`, ...) starts with a colon, so a
leading `\\b` before it needs a word character on its left and misses after a space, `(` or `=`. Each rule below
must fire on the atom in those positions, and must not fire inside a longer name (`foo:ets.insert`, `a::math`).
"""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

RULES = LANGUAGE_DEFINITIONS["elixir"]["rules"]

CASES = [
    ("ipc_rpc_bridges", ":rpc.call(n, M, :f, [])"),
    ("ipc_rpc_bridges", "x = :gen_tcp.connect(h, 1, [])"),
    ("io", "(:gen_udp.open(1))"),
    ("io", "  :file.read_file(p)"),
    ("io", "x = :gen_tcp.send(s, d)"),
    ("high_risk_execution", "x = :os.cmd('ls')"),
    ("state_mutation", "x = :ets.insert(t, {1})"),
    ("state_mutation", "(:persistent_term.put(k, v))"),
    ("globals", "x = :persistent_term.get(k)"),
    ("scientific", "y = :math.sqrt(2)"),
    ("events", "x = :telemetry.execute([:a], %{}, %{})"),
    ("sync_locks", "x = :global.set_lock({a, b})"),
    ("sync_locks", ":pg.join(g, self())"),
    ("thread_sleeps", "x = :timer.sleep(100)"),
]


@pytest.mark.parametrize(("rule", "src"), CASES)
def test_erlang_atom_call_fires(rule, src):
    assert RULES[rule].search(src), (rule, src)


@pytest.mark.parametrize(
    ("rule", "src"),
    [
        ("ipc_rpc_bridges", "foo:rpc.call(x)"),
        ("io", "a::file.read(x)"),
        ("state_mutation", "x:ets.insert(t, 1)"),
        ("scientific", "a::math"),
        ("high_risk_execution", "x:os.cmd(1)"),
    ],
)
def test_erlang_atom_inside_longer_name_does_not_fire(rule, src):
    assert not RULES[rule].search(src), (rule, src)
