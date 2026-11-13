"""gitgalaxy#8010: a token counted by two keyword rules makes their co-occurrence definitional.
Pins the leaks removed here; the TS `extends` / generics leak is pinned with #8011's TS change."""

from __future__ import annotations

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS as LD


def _hits(lang: str, rule: str, text: str) -> list[str]:
    return [m.group(0).strip() for m in LD[lang]["rules"][rule].finditer(text)]


def test_c_size_t_is_not_a_safety_site():
    assert _hits("c", "safety", "size_t n = strlen(s);") == []
    assert _hits("c", "safety", 'assert(n > 0); snprintf(b, 4, "x");') == ["assert", "snprintf"]
    assert "size_t" in _hits("c", "pointers", "size_t n;")  # still a pointer-arithmetic type there


@pytest.mark.parametrize("lang", ["python", "embedded_python"])
def test_python_bare_pass_is_not_a_bypass(lang):
    assert _hits(lang, "safety_bypasses", "class A:\n    pass\n") == []
    assert _hits(lang, "safety_bypasses", "def f():\n    pass\n") == []


@pytest.mark.parametrize("lang", ["python", "embedded_python"])
@pytest.mark.parametrize(
    "text",
    [
        "try:\n    f()\nexcept:\n    pass\n",
        "try:\n    f()\nexcept ValueError:\n    pass\n",
        "try:\n    f()\nexcept OSError: pass\n",
    ],
)
def test_python_swallowed_exception_is_one_bypass_site(lang, text):
    hits = _hits(lang, "safety_bypasses", text)
    assert len(hits) == 1 and hits[0].startswith("except") and hits[0].endswith("pass")


def test_php_exit_and_die_are_aborts_not_prints():
    assert _hits("php", "debug_prints", "exit(1); die('x');") == []
    assert _hits("php", "panics_and_aborts", "exit(1); die('x');") == ["exit", "die"]
    assert _hits("php", "debug_prints", "echo $x; var_dump($y);") == ["echo", "var_dump"]


def test_csharp_arrow_is_a_closure_not_a_structural_boundary():
    for text in ("x => x + 1", "int Get() => 1;"):
        assert _hits("csharp", "structural_boundaries", text) == []
        assert _hits("csharp", "closures", text) == ["=>"]
    assert _hits("csharp", "structural_boundaries", "return x; class A {}") == ["return", "class"]


def test_intended_abort_tokens_stay_high_risk_execution():
    """The abort/spawn overlaps are decided intended (#2878 C1): each token must keep both owners."""
    assert "panic!" in _hits("rust", "high_risk_execution", 'panic!("x");')
    assert "panic!" in _hits("rust", "panics_and_aborts", 'panic!("x");')
    for tok in ("os.Exit", "exec.Command"):
        assert tok in _hits("go", "high_risk_execution", f"{tok}(1)")
    assert "os.Exit" in _hits("go", "panics_and_aborts", "os.Exit(1)")
