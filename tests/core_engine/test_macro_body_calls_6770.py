"""#6770: a unit that invokes a function-like macro gets the calls the macro's body makes, as the compiler's expansion
gives them (`Z_ChangeTag(p, t)` -> `Z_ChangeTag2`, `I_Error`; `FTOM(x)` -> `FixedMul`). The table is repo-wide, like the
#5563 macro table, and only the C-family lanes read it."""

import json
import os
import sqlite3
import subprocess
import sys

import pytest

from gitgalaxy.core import detector as det


def _table(code):
    return {k: v for k, v in det.c_repo_macro_body_calls([code]).items() if v}


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("#define A(p, t) B(p, t, __FILE__)\n", {"A": {"B"}}),
        ("#define A(p) do { B(p); C(p); } while (0)\n", {"A": {"B", "C"}}),
        ("#define A(p) \\\n  B(p); \\\n  C(p)\n", {"A": {"B", "C"}}),  # a continued body
        ("#define A(f, x) f(x)\n", {}),  # a parameter called is no named callee
        ("#define A(x) ((x) * sizeof(int))\n", {}),  # sizeof and a cast are no calls
        ('#define A(x) puts("B(x) C(")\n', {"A": {"puts"}}),  # a string holds no call
        ("#define A(x) (s)->cb(x)\n#define D(x) s.cb(x)\n", {}),  # a member call has no callee name
        ("#define A(n) pre_##n(1) + post##_x(2)\n", {}),  # a pasted name is no fixed callee
        ("#define A(x) A(x, 1)\n", {}),  # the macro's own name is the wrapper idiom, not a callee
        ("#define A 1\n#define B B_impl()\n", {}),  # an object-like macro is no use-site call
        ("#define A(x) B(x)\n#define A(x) C(x)\n", {}),  # variants that disagree record nothing
        ("#define A(x) B(x)\n#define A(y) B(y)\n", {"A": {"B"}}),  # variants that agree record it
        ("#define DEF(n) static int n(void) { return B(); }\n", {}),  # a signature macro is a definition
    ],
)
def test_macro_body_call_table(code, expected):
    assert {k: set(v) for k, v in _table(code).items()} == expected


def test_a_macro_two_files_define_differently_records_nothing():
    assert det.c_repo_macro_body_calls(["#define A(x) B(x)\n", "#define A(x) C(x)\n"]) == {}
    table = det.c_repo_macro_body_calls(["#define A(x) B(x)\n#define D(x) A(x)\n", "#define D(x) E(x)\n"])
    assert table == {"A": frozenset({"B"}), "D": frozenset()}  # D is still known as a macro
    assert set(det.c_repo_macro_body_calls(["#define A(x) B(x)\n", "int z;\n"])["A"]) == {"B"}


def test_expansion_follows_macros_that_call_macros_and_survives_a_cycle():
    table = {"A": frozenset({"B", "real"}), "B": frozenset({"C"}), "C": frozenset({"A", "deep"})}
    assert set(det._macro_expansion_callees(["A"], table)) == {"real", "deep"}
    assert det._macro_expansion_callees(["plain"], table) == []


def test_a_macro_a_body_invokes_is_expanded_never_listed():
    """micropython `ATB_GET_KIND(b)` -> `BLOCK_SHIFT(b)`: a macro that calls nothing adds no callee of its own."""
    table = det.c_repo_macro_body_calls(
        ["#define SHIFT(b) (2 * (b))\n#define KIND(b) (load(b) >> SHIFT(b))\n#define CHECK(o) assert(KIND(o))\n"]
    )
    assert det._macro_expansion_callees(["CHECK"], table) == ["assert", "load"]


C_SOURCE = """\
#include "z.h"
void Z_ChangeTag2(void *p, int t, const char *f, int l) { }
void I_Error(const char *m) { }
void FixedMul(int a, int b) { }
void plain(void) { }
void tagged(void *p)
{
    Z_ChangeTag(p, 2);
}
void scaled(int x)
{
    int y = FTOM(x);
    (void)y;
}
void untouched(void)
{
    plain();
}
"""
C_HEADER = """\
#define Z_ChangeTag(p, t) \\
    do { if ((p) == 0) I_Error("bad"); Z_ChangeTag2(p, t, __FILE__, __LINE__); } while (0)
#define FTOM(x) FixedMul(x, 65536)
"""


def _scan(tmp_path, files):
    src = tmp_path / "repo"
    src.mkdir()
    for name, text in files.items():
        (src / name).write_text(text)
    out = tmp_path / "out"
    env = {
        **os.environ,
        "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER",
        "GITGALAXY_DISABLE_GIT_HISTORY": "1",
        "GALAXYSCOPE_MAX_WORKERS": "1",
    }
    code = "import sys; from gitgalaxy.galaxyscope import main; sys.argv = ['galaxyscope', *sys.argv[1:]]; main()"
    done = subprocess.run(
        [sys.executable, "-c", code, str(src), "--db-only", "--output", str(out)],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    dbs = list(out.glob("*.db"))
    assert dbs, done.stderr[-2000:]
    con = sqlite3.connect(dbs[0])
    try:
        return {
            name: set(json.loads(blob or "[]"))
            for name, blob in con.execute("select func_name, calls_out_to from function_data")
        }
    finally:
        con.close()


def test_a_scan_gives_the_caller_the_macro_bodys_calls(tmp_path):
    calls = _scan(tmp_path, {"run.c": C_SOURCE, "z.h": C_HEADER})
    assert {"Z_ChangeTag2", "I_Error"} <= calls["tagged"]
    assert "FixedMul" in calls["scaled"]
    assert calls["untouched"] == {"plain"}
    assert "FixedMul" not in calls["tagged"] and "I_Error" not in calls["scaled"]


def test_a_scan_with_no_macro_define_expands_nothing(tmp_path):
    calls = _scan(tmp_path, {"run.c": C_SOURCE})
    assert not {"Z_ChangeTag2", "I_Error", "FixedMul"} & (calls["tagged"] | calls["scaled"])


def test_the_cpp_lane_reads_the_table_too(tmp_path):
    calls = _scan(tmp_path, {"run.cpp": C_SOURCE, "z.h": C_HEADER})
    assert {"Z_ChangeTag2", "I_Error"} <= calls["tagged"] and "FixedMul" in calls["scaled"]


# #6266: a function named like a macro (a debug-allocator wrapper, an alias for a native-resolution variant) holds
# the macro's name only in its own header, which no expansion reaches; a recursive use of the name still does.
NAMED_AS_MACRO_SOURCE = """\
#include "alloc.h"
void *M_Malloc_Dbg(unsigned n, const char *f, int l) { return 0; }
void *M_Malloc(unsigned n)
{
    return 0;
}
void *M_Calloc(unsigned n)
{
    return M_Calloc(n - 1);
}
void *caller(unsigned n)
{
    return M_Malloc(n);
}
"""
NAMED_AS_MACRO_HEADER = """\
#define M_Malloc(s) M_Malloc_Dbg(s, __FILE__, __LINE__)
#define M_Calloc(s) M_Malloc_Dbg(s, __FILE__, __LINE__)
"""


@pytest.mark.parametrize("ext", ["c", "cpp"])
def test_a_function_named_like_a_macro_is_not_expanded_at_its_own_header(tmp_path, ext):
    calls = _scan(tmp_path, {f"run.{ext}": NAMED_AS_MACRO_SOURCE, "alloc.h": NAMED_AS_MACRO_HEADER})
    assert "M_Malloc_Dbg" not in calls["M_Malloc"]
    assert "M_Malloc_Dbg" in calls["M_Calloc"]
    assert "M_Malloc_Dbg" in calls["caller"]
