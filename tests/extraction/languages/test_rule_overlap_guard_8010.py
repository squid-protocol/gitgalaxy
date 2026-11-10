"""gitgalaxy#8010 durable guard: two keyword rules matching the identical span must be listed here.

A shared span makes the two signals co-occur by definition, so every pair is either `intended` or `review`
(open, see docs/rule_overlap_dispositions.md). A new shared span fails the test; so does a listed pair that no
longer reproduces (remove it: the leak was fixed). Probes are one snippet per language covering the class table.
"""

from __future__ import annotations

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS as LD

_SKIP = ("calls_out", "dependency", "indent", "design_", "core_var")

PROBES = {
    "c": 'typedef struct s {int a;} t;\nsize_t n = sizeof(int);\nchar *p = &n; p->a = 1;\nassert(n); snprintf(b,4,"x");\n',
    "python": "async def f():\n    await g()\n    pass\ntry:\n    f()\nexcept ValueError:\n    pass\n",
    "php": "<?php\nexit(1); die('x'); require 'a.php'; require_once 'b.php'; $a = $b ?? 1; echo $x;\n",
    "typescript": "export class A extends B { }\nexport function f<T extends U>(x: T) {}\n"
    "await g(); const a = b ?? c; setTimeout(f, 1); export const stub = 1;\n",
    "javascript": "export default x;\nawait g(); const a = b ?? c; setTimeout(f, 1); el.on('x', h);\n",
    "rust": '#[cfg(test)]\nmod t { #[test] fn a() {} }\nfn f<T>() where T: X { panic!("x"); }\n'
    "macro_rules! m { () => {} }\n#[doc(hidden)]\npub fn g() {}\n",
    "csharp": "var a = b ?? c; var d = e?.f; Func<int> g = () => 1; int Get() => 1;\n"
    "Interlocked.Increment(ref x); lock(o) {}\nawait t;\n",
    "go": 'os.Exit(1)\nexec.Command("ls")\n',
}

# (language, token, rules). `intended` = both readings are true; `review` = open question, not yet decided.
INTENDED = {
    ("python", "await", "concurrency+structural_boundaries"),
    ("php", "require", "import+structural_boundaries"),
    ("php", "require_once", "import+structural_boundaries"),
    ("php", "??", "branch+safety"),
    ("typescript", "export", "api+structural_boundaries"),
    ("typescript", "await", "concurrency+structural_boundaries"),
    ("typescript", "??", "branch+safety"),
    ("javascript", "export", "api+structural_boundaries"),
    ("javascript", "await", "concurrency+structural_boundaries"),
    ("javascript", "??", "branch+safety"),
    ("rust", "where", "generics+structural_boundaries"),
    ("rust", "#[cfg(test)]", "decorators+test"),
    ("csharp", "??", "branch+safety"),
    ("csharp", "?.", "branch+safety"),
    ("csharp", "await", "concurrency+structural_boundaries"),
    ("csharp", "Interlocked", "concurrency+sync_locks"),
    # #2878 C1/C1b: aborts and spawns are high-risk execution and also their own signal.
    ("rust", "panic!", "high_risk_execution+panics_and_aborts"),
    ("go", "os.Exit", "high_risk_execution+panics_and_aborts"),
    ("go", "exec.Command", "high_risk_execution+ipc_rpc_bridges"),
}
REVIEW = {
    ("c", "typedef", "api+structural_boundaries"),
    ("typescript", "setTimeout", "concurrency+thread_sleeps+time_date_logic"),
    ("typescript", "stub", "planned_debt+test_skip"),
    ("javascript", "setTimeout", "concurrency+thread_sleeps+time_date_logic"),
    ("javascript", "on", "events+listeners"),
    ("rust", "macro_rules!", "macros+reflection_metaprogramming"),
    ("rust", "#[doc(hidden)]", "decorators+doc"),
}
# Leaks fixed under #8010 / #8011: these must stay single-owner.
FIXED_LEAKS = {"size_t", "pass", "exit", "die"}


def _shared(lang: str) -> set[tuple[str, str, str]]:
    text = PROBES[lang]
    spans: dict[tuple[int, int], set[str]] = {}
    for key, rule in LD[lang]["rules"].items():
        if not hasattr(rule, "finditer") or any(s in key for s in _SKIP):
            continue
        for m in rule.finditer(text):
            if m.end() > m.start():
                spans.setdefault((m.start(), m.end()), set()).add(key)
    return {(lang, text[a:b], "+".join(sorted(ks))) for (a, b), ks in spans.items() if len(ks) > 1}


@pytest.mark.parametrize("lang", sorted(PROBES))
def test_shared_spans_are_all_listed(lang):
    listed = {e for e in INTENDED | REVIEW if e[0] == lang}
    found = _shared(lang)
    assert found - listed == set(), "new shared span: decide intended or leak (fix the rule)"
    assert listed - found == set(), "listed pair no longer reproduces: drop it from the table"
    assert not {e[1] for e in found} & FIXED_LEAKS
