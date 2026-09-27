import json
import sys
import types
import math
from unittest.mock import patch

from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import count_tokens, trim_ticket


def test_token_counter():
    text = "hello world"
    b, t, c = count_tokens(text)
    assert b == 11
    assert t > 0
    assert c in ("tiktoken(o200k_base)", "bytes/4")


@patch("gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets._TIKTOKEN_ENCODING", None)
@patch("gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets._TIKTOKEN_TRIED", False)
def test_token_counter_fallback(monkeypatch):
    """Offline (tiktoken's first use downloads its encoding) or not installed at all: bytes / 4."""
    offline = types.ModuleType("tiktoken")
    offline.get_encoding = lambda name: (_ for _ in ()).throw(OSError("offline"))
    monkeypatch.setitem(sys.modules, "tiktoken", offline)
    text = "hello world"
    b, t, c = count_tokens(text)
    assert b == 11
    assert t == math.ceil(11 / 4)
    assert c == "bytes/4"


def test_trim_ticket_under_budget():
    ticket = {"facts": {"sections": {"screen_bindings": {"facts": [{"map": "TEST", "fields": [1, 2, 3]}]}}}}
    original = json.dumps(ticket, indent=2, sort_keys=True)
    trim_ticket(ticket, 10**9)
    assert json.dumps(ticket, indent=2, sort_keys=True) == original
    assert "trimmed" not in ticket


def test_trim_ticket_over_budget():
    ticket = {"facts": {"sections": {"screen_bindings": {"facts": [{"map": "TEST", "fields": [1, 2, 3]}]}}}}
    trim_ticket(ticket, 1)
    assert "trimmed" in ticket
    assert ticket["trimmed"][0]["section"] == "facts.screen_bindings"
    assert ticket["facts"]["sections"]["screen_bindings"]["facts"][0]["fields"] == "Reference: TestScreen (3 fields)"


def test_still_over_budget_after_trimming_is_recorded():
    ticket = {
        "rules": ["x" * 4000],
        "facts": {"sections": {"screen_bindings": {"facts": [{"map": "M", "fields": [1]}]}}},
    }
    trim_ticket(ticket, 10)
    assert ticket["over_budget"]["budget"] == 10 and ticket["over_budget"]["tokens"] > 10
    assert ticket["rules"] == ["x" * 4000]  # the rules are never trimmed


@patch("gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets._TIKTOKEN_ENCODING", None)
@patch("gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets._TIKTOKEN_TRIED", False)
def test_token_counter_without_tiktoken_installed(monkeypatch):
    monkeypatch.setitem(sys.modules, "tiktoken", None)  # `import tiktoken` raises ImportError
    assert count_tokens("hello world")[2] == "bytes/4"
