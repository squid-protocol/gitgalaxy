"""#8868 Batch B: the C, Go and Rust rules count what their contracts name and no more."""

import pytest

from gitgalaxy.standards.language_standards.languages import c as c_lang
from gitgalaxy.standards.language_standards.languages import go as go_lang
from gitgalaxy.standards.language_standards.languages import javascript as js_lang
from gitgalaxy.standards.language_standards.languages import rust as rust_lang
from gitgalaxy.standards.language_standards.languages import typescript as ts_lang


def _rule(mod, name):
    for obj in vars(mod).values():
        if isinstance(obj, dict):
            if name in obj and "thread_sleeps" in obj:
                return obj[name]
            for v in obj.values():
                if isinstance(v, dict) and name in v and "thread_sleeps" in v:
                    return v[name]
    raise AssertionError(f"{mod.__name__}: {name} not found")


@pytest.mark.parametrize("line", ["abort();", "exit(1);", "_exit(2);", "_Exit(1);"])
def test_c_abort_forms_count(line):
    assert _rule(c_lang, "panics_and_aborts").search(line)


@pytest.mark.parametrize("line", ["return -1;", "assert(x > 0);", "return err;"])
def test_c_error_returns_and_assert_are_not_aborts(line):
    assert not _rule(c_lang, "panics_and_aborts").search(line)


@pytest.mark.parametrize("line", ["http.Get(url)", "http.Post(u, t, b)", 'net.Listen("tcp", a)', 'net.Dial("tcp", a)'])
def test_go_network_calls_are_io(line):
    assert _rule(go_lang, "io").search(line)


@pytest.mark.parametrize("line", ["fs::write(p, b)", "fs::read_to_string(p)", "fs::create_dir_all(p)"])
def test_rust_fs_calls_are_io(line):
    assert _rule(rust_lang, "io").search(line)


def test_rust_fs_needs_a_path_head():
    assert not _rule(rust_lang, "io").search("self.fs::new")


# --- Batch C -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line", ["f := func(x int) {", "go func() {", "return func(a int) error {", "h := func(a, b int) (int, error) {"]
)
def test_go_function_literals_are_closures(line):
    assert _rule(go_lang, "closures").search(line)


@pytest.mark.parametrize("line", ["func (s *Server) Handle() {", "func main() {", "func Run(cb func(int) error) {"])
def test_go_declarations_are_not_closures(line):
    assert not _rule(go_lang, "closures").search(line)


@pytest.mark.parametrize(
    "line", ["xs.iter().map(|x| x + 1)", "spawn(move || {", "let f = |a, b| a + b;", "run(|| work())", "f(|| { 1 })"]
)
def test_rust_closures(line):
    assert _rule(rust_lang, "closures").search(line)


@pytest.mark.parametrize("line", ["let m = a | b | c;", "x.bits() | y"])
def test_rust_bit_or_is_not_a_closure(line):
    assert not _rule(rust_lang, "closures").search(line)


@pytest.mark.parametrize(
    "line", ["if a && b {", "ok = x || y", "f(a)\n    || g(b)", "while it.next().is_some() && n > 0 {"]
)
def test_rust_booleans_count_as_short_circuit(line):
    assert _rule(rust_lang, "short_circuit").search(line)


@pytest.mark.parametrize(
    "line", ["spawn(|| work())", "let f = move || 1;", "let r: &&str = x;", "xs.filter(|&&x| x > 0)"]
)
def test_rust_closure_and_reference_forms_are_not_short_circuit(line):
    assert not _rule(rust_lang, "short_circuit").search(line)


@pytest.mark.parametrize("mod", [js_lang, ts_lang])
def test_timers_are_waits_not_clock_values(mod):
    assert not _rule(mod, "time_date_logic").search("setTimeout(f, 10); setInterval(g, 5)")
    assert _rule(mod, "time_date_logic").search("Date.now()")
    assert _rule(mod, "thread_sleeps").search("setImmediate(f)")


def test_ts_io_needs_an_operative_form():
    r = _rule(ts_lang, "io")
    assert r.search("fs.readFileSync(p)") and r.search("fetch(url)")
    assert not r.search("const sql = 'select 1'; const database = path;")


# --- JavaScript closures (#8868) ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "xs.map(x => x + 1)",
        "xs.map((a, b) => a + b)",
        "setTimeout(() => { go(); }, 5)",
        "run(function (err) {",
        "return function () {",
        "(function () { init(); })();",
        "p.then(async (r) => r.json())",
    ],
)
def test_js_anonymous_callables_are_closures(line):
    assert _rule(js_lang, "closures").search(line)


@pytest.mark.parametrize(
    "line",
    [
        "ajaxSetup: function( target, settings ) {",
        "jQuery.fn.extend = function() {",
        "Foo.prototype.emit = function (particle) {",
        "jQuery[ method ] = function( url ) {",
        "run: async function (x) {",
        "function named(a) {",
        "class A { m(a) { return a; } }",
        "if (a >= b) {",
    ],
)
def test_js_own_header_and_declarations_are_not_closures(line):
    assert not _rule(js_lang, "closures").search(line)
