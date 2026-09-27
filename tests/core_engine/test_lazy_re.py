"""#3914: the language registry's rules compile on first use (`_lazy_re`), not at import.

Importing the registry compiled ~2,200 rules -- 2.3 s of `import gitgalaxy.galaxyscope` -- for every
process that scans, although a scan uses the rules of the languages it meets. A `LazyPattern` is a
duck-typed `re.Pattern` that compiles when first used; the detector compiles its languages' rules
into real patterns, so the per-file hot path is unchanged.
"""

import copy
import pickle
import re
import subprocess
import sys

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS, _lazy_re
from gitgalaxy.standards.language_standards._lazy_re import LazyPattern, is_pattern, materialize


def _lazy_rules():
    for lang, definition in LANGUAGE_DEFINITIONS.items():
        for key, value in definition.get("rules", {}).items():
            if isinstance(value, LazyPattern):
                yield lang, key, value


def test_importing_the_registry_compiles_no_rule():
    code = (
        "from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS as L, _lazy_re as z\n"
        "rules = [v for d in L.values() for v in d.get('rules', {}).values() if isinstance(v, z.LazyPattern)]\n"
        "print(len(rules), sum(v._compiled is not None for v in rules))\n"
    )
    total, compiled = map(int, subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                              check=True).stdout.split())  # fmt: skip
    assert total > 2000 and compiled == 0


def test_every_rule_still_compiles():
    """A broken regex used to fail the import; lazily, it would fail only when its language is first
    scanned. This keeps the failure in CI, for every rule of every language."""
    broken = []
    for lang, key, rule in _lazy_rules():
        try:
            rule.compiled()
        except re.error as e:
            broken.append(f"{lang}.{key}: {e}")
    assert not broken


def test_a_lazy_pattern_is_a_pattern_until_it_matters():
    lazy = _lazy_re.compile(r"(?i)^func_(\w+)", re.M)
    eager = re.compile(r"(?i)^func_(\w+)", re.M)
    assert isinstance(lazy, LazyPattern) and lazy._compiled is None
    assert lazy.pattern == eager.pattern and lazy._compiled is None  # reading the source compiles nothing
    assert lazy.flags == eager.flags  # includes the inline (?i) and re.UNICODE, as the compiler sets them
    assert lazy.search("x\nFUNC_go").group(1) == "go" and lazy.groups == 1
    assert lazy == eager and hash(lazy) == hash(eager)
    assert is_pattern(lazy) and is_pattern(eager) and not is_pattern(r"^func")
    assert _lazy_re.compile(eager) is eager and _lazy_re.compile(lazy) is lazy  # as re.compile does
    assert _lazy_re.IGNORECASE == re.IGNORECASE and _lazy_re.escape("a.b") == r"a\.b"  # the rest is `re`


def test_it_travels_as_its_source():
    lazy = _lazy_re.compile(r"\bCALL\s+(\w+)", re.I)
    lazy.search("call x")  # compiled in this process...
    clone = pickle.loads(pickle.dumps(lazy))
    assert clone._compiled is None and clone == lazy  # ...but a spawned worker compiles only what it uses
    assert copy.copy(lazy) is lazy and copy.deepcopy({"r": lazy})["r"] is lazy  # as a compiled pattern does


def test_materialize_compiles_in_place_and_leaves_the_rest_alone():
    lazy = _lazy_re.compile(r"a+")
    plain = ("x", frozenset({"y"}))
    assert isinstance(materialize(lazy), re.Pattern)
    assert materialize(plain) is plain  # nothing to compile: the same object
    nested = materialize({"k": [lazy, "s"], "t": (lazy,)})
    assert isinstance(nested["k"][0], re.Pattern) and nested["k"][1] == "s" and isinstance(nested["t"][0], re.Pattern)


@pytest.mark.parametrize("lang, embedded", [("html", "javascript"), ("python", None)])
def test_the_detector_runs_on_real_patterns(lang, embedded):
    """The detector's `isinstance(p, re.Pattern)` checks and its hot path see compiled rules -- for its
    own language when it is built, and for a language it switches into mid-file."""
    from gitgalaxy.core.detector import StructuralExtractor, _compiled_rules

    defs = copy.deepcopy(LANGUAGE_DEFINITIONS)
    extractor = StructuralExtractor(lang, defs)
    assert not any(isinstance(v, LazyPattern) for v in extractor.primary_rules.values())
    if embedded:
        rules = _compiled_rules(defs[embedded])
        assert rules is defs[embedded]["rules"]  # compiled in place, once
        assert not any(isinstance(v, LazyPattern) for v in rules.values())


def test_a_forked_pool_inherits_every_claimant_compiled(monkeypatch):
    """#3929: forked workers share the parent's memory, so the parent compiles the scan's languages
    once before the fork -- every claimant of each extension, because the lens scores an ambiguous
    `.h` with c's and objective-c's rules alike (each of curl's 12 workers compiled
    objective-c for itself). Under spawn nothing is compiled: the workers' state comes from pickles."""
    from gitgalaxy import galaxyscope

    defs = copy.deepcopy(LANGUAGE_DEFINITIONS)
    assert galaxyscope._active_languages(defs, {".h": 3}) == {"plaintext", "markdown", "c"}
    claimants = galaxyscope._active_languages(defs, {".h": 3}, every_claimant=True)
    assert {"c", "objective-c"} <= claimants

    monkeypatch.setattr(galaxyscope.multiprocessing, "get_start_method", lambda allow_none=False: "spawn")
    galaxyscope._precompile_for_fork(defs, {".h": 3})
    assert any(isinstance(v, LazyPattern) for v in defs["objective-c"]["rules"].values())

    monkeypatch.setattr(galaxyscope.multiprocessing, "get_start_method", lambda allow_none=False: "fork")
    galaxyscope._precompile_for_fork(defs, {".h": 3})
    for lang in ("c", "objective-c"):
        assert not any(isinstance(v, LazyPattern) for v in defs[lang]["rules"].values()), lang
    assert any(isinstance(v, LazyPattern) for v in defs["python"]["rules"].values())  # not a claimant
