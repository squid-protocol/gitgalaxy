"""
#3313 step 3: the per-file half of the idiom-wrapper channel, run through the
real detector (PRISM code stream -> splice -> extract_wrapper_facts), so the
spans, branch counts and `calls_out_to` are the engine's own.
"""

import re

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.core.wrapper_extractor import _standalone_spans, extract_wrapper_facts, is_method_definition
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards.identifiers import ID_CONTINUE


def _facts(lang, source):
    code = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams(source, lang)["code_stream"]
    extractor = StructuralExtractor(lang, LANGUAGE_DEFINITIONS)
    functions = extractor.splice(code, "")["functions"]
    return extract_wrapper_facts(
        lang,
        LANGUAGE_DEFINITIONS[lang],
        code,
        source,
        functions,
        lambda block: extractor._apply_literal_shield(block, lang),
    )


def _cands(facts):
    return {c["name"]: c for c in facts["candidates"]}


WRF = """\
subroutine wrf_error_fatal (string)
   character (len=*) :: string
   print *,string
   stop
end subroutine wrf_error_fatal

subroutine init_domain (n)
   integer :: n
   if (n < 0) then
      call wrf_error_fatal('negative domain')
   end if
   call wrf_error_fatal('done')
end subroutine init_domain
"""


def test_a_print_and_stop_helper_is_a_branchless_aligned_candidate():
    facts = _facts("fortran", WRF)
    wrapper = _cands(facts)["wrf_error_fatal"]
    assert (wrapper["hits"], wrapper["branches"], wrapper["aligned"], wrapper["method"]) == (
        ["debug_prints", "panics_and_aborts"],
        0,
        True,
        False,
    )
    assert facts["calls"]["wrf_error_fatal"] == 2
    assert facts["defined"] == {"init_domain": 1, "wrf_error_fatal": 1}


C_ALLOC = """\
#include <stdlib.h>
#define xfree(p) free(p)
#define SAFE_FREE(p) do { xfree(p); (p) = NULL; } while (0)
#define NOT_ALLOC(x) ((x) + 1)

static void *
xmalloc(size_t n)
{
    void *p = malloc(n);
    if (!p) abort();
    return p;
}

int main(void)
{
    char *b = xmalloc(4);
    puts("xmalloc(8) in a string is not a call");
    SAFE_FREE(b);
    return 0;
}
"""


def test_c_candidates_macros_and_the_literal_shield():
    facts = _facts("c", C_ALLOC)
    xmalloc = _cands(facts)["xmalloc"]
    assert "memory_alloc" in xmalloc["hits"]
    assert xmalloc["branches"] >= 1, "the NULL guard is a branch (memory_alloc's filter allows it)"
    assert xmalloc["aligned"], "the name is on line 2 after a return-type line"
    assert facts["calls"]["xmalloc"] == 1, "the string's `xmalloc(8)` is shielded"
    macros = {m["name"]: m for m in facts["macros"]}
    assert macros["xfree"]["hits"] == ["memory_alloc"]
    assert macros["SAFE_FREE"]["called"] == ["xfree"]
    assert "NOT_ALLOC" not in macros, "no rule hit and no call: nothing a wrapper could be"


def test_a_language_without_a_preprocessor_records_no_macros():
    facts = _facts("python", "def log_it(message):\n    print(message)\n\n\ndef main():\n    log_it('x')\n")
    assert facts["macros"] == []
    assert _cands(facts)["log_it"]["hits"] == ["debug_prints"]
    # #3361: `print` is a call (#3327 C2), so its site is counted too. Nothing in
    # the repo defines it, so the resolver never turns it into a wrapper row.
    assert facts["calls"] == {"log_it": 1, "print": 1}


def test_a_project_wrapper_named_like_a_builtin_is_visible():
    # #3361: `log` used to sit in the global calls_out ignore set, so a project's
    # own `log()` wrapper had no call sites. Built-ins are calls now, and the
    # resolver credits the site to the repo's definition.
    from gitgalaxy.core.wrapper_resolver import resolve_wrappers

    src = "def log(message):\n    print(message)\n\n\ndef main():\n    log('x')\n    log('y')\n"
    facts = _facts("python", src)
    assert facts["calls"]["log"] == 2
    rows = resolve_wrappers([{"path": "app.py", "lang_id": "python", "wrapper_facts": facts}])
    assert [(r["name"], r["rule"], r["call_sites"]) for r in rows] == [("log", "debug_prints", 2)]


def test_a_positional_language_has_no_wrapper_facts():
    assert _facts("jcl", "//J JOB\n//S EXEC PGM=IEFBR14\n") is None


def test_method_definitions_by_shape():
    assert is_method_definition("go", "func (cr *connReader) lock() {", "lock")
    assert not is_method_definition("go", "func lock(l *mutex) {", "lock")
    assert is_method_definition("python", "def log(self, msg):", "log")
    assert not is_method_definition("python", "def log(msg):", "log")
    assert is_method_definition("lua", "function M.log(msg)", "log")
    assert is_method_definition("cpp", "void Logger::log(const char *m) {", "log")


def test_a_macro_parameter_is_not_a_callee():
    """micropython's `#define EMIT_ARG(fun, ...)` calls its ARGUMENT `fun(`, not a
    function named fun -- the crucible scan's first draft linked it to one."""
    src = "#define EMIT_ARG(fun, ...) (fun(x), note_emit(x))\nint main(void) { return 0; }\n"
    macros = {m["name"]: m for m in _facts("c", src)["macros"]}
    assert macros["EMIT_ARG"]["called"] == ["note_emit"]


def test_a_qualified_method_call_is_not_a_callee():
    """`arr.push(x)` is a call on arr, never a link to a wrapper named push."""
    src = "function addAntecedent(arr, x) {\n  arr.push(x);\n  helper(x);\n}\n"
    cand = _cands(_facts("javascript", src))["addAntecedent"]
    assert cand["callees"] == ["helper"]


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("foo(foo) foo_bar xfoo foo$ foo", "foo"),  # ASCII neighbours, `$` and `_` continue a name
        ("foo", "foo"),  # the name is the whole text
        ("foofoo foo", "foo"),  # overlapping candidates: only the standalone one
        ("fo foo", "foo"),
        ("a" + chr(0x0301) + "b b" + chr(0x0301), "b"),  # a combining mark continues a name (UAX #31)
        ("b" + chr(0x1D7D8) + " b", "b"),  # an astral digit continues a name
        ("", "foo"),
    ],
)
def test_standalone_spans_match_the_per_name_regex(text, name):
    """The str.find scan is the lookaround regex it replaced, name by name (#5531)."""
    pat = re.compile("(?<![" + ID_CONTINUE + "$])" + re.escape(name) + "(?![" + ID_CONTINUE + "$])")
    assert _standalone_spans(text, name) == [m.span() for m in pat.finditer(text)]


def test_pattern_compiles_do_not_grow_with_the_function_count(monkeypatch):
    """Each function used to compile two ID_CONTINUE patterns (15 s for 3,900 C functions, over the 60 s fuse on a
    loaded runner): the big-class compiles for 1,000 more functions must stay near zero. (Small per-name patterns
    elsewhere, e.g. the detector's `_name_boundary_pattern`, are cheap and not counted.)"""
    compiles = []
    real = re._compiler.compile
    monkeypatch.setattr(
        re._compiler, "compile", lambda *a, **k: (len(str(a[0])) > 1000 and compiles.append(a[0])) or real(*a, **k)
    )

    def run(n):
        src = "".join(f"static int fn_{i}(int a)\n{{\n    return g(a + {i});\n}}\n\n" for i in range(n))
        assert len(_facts("c", src + "int g(int a) { return a; }\n")["defined"]) == n + 1
        return len(compiles)

    run(50)  # warm: the detector's own lazy patterns
    base = len(compiles)
    assert run(1050) - base < 100


def test_no_core_function_builds_a_per_name_unicode_class_pattern():
    """A pattern built per call from `re.escape(name)` plus the huge ID_CONTINUE / ID_START class overflows re's
    512-entry cache; compile once at module level and match with `str.find` (#5531)."""
    import ast
    from pathlib import Path

    core = Path(__file__).resolve().parents[2] / "gitgalaxy" / "core"
    offenders = []
    for path in sorted(core.glob("*.py")):
        for func in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names = {n.id for n in ast.walk(func) if isinstance(n, ast.Name)}
            escapes = any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "escape"
                for n in ast.walk(func)
            )
            if escapes and names & {"ID_CONTINUE", "ID_START"}:
                offenders.append(f"{path.name}:{func.name}")
    assert not offenders, offenders
