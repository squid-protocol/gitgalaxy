"""#7155: negative control for the generated-docs gate. Its `check` and `main` are fed renderers that must turn it red.

The page renderers are stubbed, so this proves the gate's decision, not the job around it.
"""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import generated_docs as gd  # noqa: E402


def _flaky():
    _flaky.calls += 1
    return f"render {_flaky.calls}"


def _boom():
    raise RuntimeError("source no longer parses")


def test_generated_docs_check_goes_red_on_a_failing_or_non_deterministic_renderer(tmp_path):
    _flaky.calls = 0
    clean = {"docs/ok.md": lambda: "same every time"}
    assert gd.check(tmp_path, clean) == []  # positive control: a stable renderer is green
    assert (tmp_path / "docs" / "ok.md").read_text(encoding="utf-8") == "same every time"
    problems = gd.check(None, {"docs/raises.md": _boom})
    assert any("does not render" in p and "docs/raises.md" in p for p in problems)
    problems = gd.check(None, {"docs/flaky.md": _flaky})
    assert any("not deterministic" in p for p in problems)
    assert gd.check(None, {**clean, "docs/raises.md": _boom}) != []  # one bad page among good ones still fails


def test_generated_docs_main_exits_1_on_a_bad_page_and_0_on_good_ones(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(gd, "PAGES", {"docs/ok.md": lambda: "x"})
    assert gd.main(["check", "--out", str(tmp_path)]) == 0
    monkeypatch.setattr(gd, "PAGES", {"docs/ok.md": lambda: "x", "docs/bad.md": _boom})
    assert gd.main(["check", "--out", str(tmp_path)]) == 1
    assert "docs/bad.md: does not render" in capsys.readouterr().err
