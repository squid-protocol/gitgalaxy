"""TypeScript keyword-family rules after the #8863 validity pass: each family counts what its contract names."""

import sys
import textwrap
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards.languages import typescript as ts_lang

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import family_oracle_ts


def _rule(key):
    for obj in vars(ts_lang).values():
        if isinstance(obj, dict):
            for v in [obj, *[x for x in obj.values() if isinstance(x, dict)]]:
                if key in v and "bitwise_ops" in v:
                    return v[key]
    raise AssertionError(f"typescript {key} rule not found")


POSITIVE = {
    "io": [
        "const t = await fs.promises.readFile(p, 'utf8');",
        "fs.readFileSync(p)",
        "const r = await fetch(url);",
        "readFile(p, cb)",
        "createWriteStream(out)",
        "const x = new XMLHttpRequest();",
        "localStorage.getItem('k')",
    ],
    "closures": [
        "xs.map(x => x + 1)",
        "xs.map((x, i) => f(x, i))",
        "const f = () => { run(); };",
        "const g = async (e: Error) => log(e);",
        "setTimeout(function () { run(); }, 1)",
    ],
    "decorators": ["  @Input() name: string;", "constructor(@Inject(TOKEN) private t: T) {}", "  @memoize"],
    "thread_sleeps": ["await sleep(100);", "setTimeout(() => go(), 5);", "await delay(2)", "Atomics.wait(a, 0, 0)"],
    "bitwise_ops": [
        "if (flags & TypeFlags.Object) {}",
        "x = a | b;",
        "mask |= SymbolFlags.Value;",
        "f &= ~Flag.A;",
        "n = x << 2;",
        "h = (a ^ b) >>> 3;",
        "return getObjectFlags(type) & ObjectFlags.Reference;",
    ],
}
NEGATIVE = {
    "io": [
        "const p = path.join(a, b);",
        "const d = path.dirname(f);",
        "this.fsProvider = x;",
        "const profile = 1;",
        "function readFile(p: string) {",
    ],
    "closures": [
        "function f(cb: (a: number) => void) {",
        "  containingMessageChain?: () => Chain | undefined,",
        "const x = a >= b;",
        "function named(a: number) {",
    ],
    "decorators": ["const k = `__@${id}@`;", "a = b ? c : d;", "// @ts-ignore", "email.send('a@b.c')"],
    "thread_sleeps": ["get delay(): number {", "set delay(v: number) {", "const d = this.delayMs;", "run(delay);"],
    "bitwise_ops": [
        "let x: Identifier | undefined;",
        "type A = B | C;",
        "function f(a: string | number) {",
        "let y: Left & Right;",
        "if (a && b || c) {}",
        "const n: Foo | null = null;",
    ],
}


@pytest.mark.parametrize(
    ("key", "line"), [(k, line) for k, lines in POSITIVE.items() for line in lines], ids=lambda v: str(v)[:30]
)
def test_contract_forms_count(key, line):
    assert _rule(key).search(line)


@pytest.mark.parametrize(
    ("key", "line"), [(k, line) for k, lines in NEGATIVE.items() for line in lines], ids=lambda v: str(v)[:30]
)
def test_other_constructs_do_not_count(key, line):
    assert not _rule(key).search(line)


def test_closure_rule_skips_the_units_own_leading_arrow():
    rx = _rule("closures")
    assert not rx.search("(fa, f) => pipe(fa, map(f))")
    assert rx.search("(fa, f) => pipe(fa, map(f, (x) => x))")


def _count(src, name, key):
    oracle = family_oracle_ts.get_oracle("typescript")
    index = oracle.index(textwrap.dedent(src))
    node = next(n for (nm, _line), n in index.items() if nm == name)
    return oracle.count(node)[0].get(key, 0)


def test_oracle_reads_a_doc_above_an_exported_function():
    assert _count("/** @internal */\nexport function f(a: number) { return a; }\n", "f", "doc") == 1
    assert _count("/** doc */\nexport const g = (a: number) => a;\n", "g", "doc") == 1
    assert _count("// plain\nexport function h() {}\n", "h", "doc") == 0


def test_oracle_counts_a_parameter_decorator():
    src = "class C { constructor(@Inject(T) private t: number) {} }\n"
    assert _count(src, "constructor", "decorators") == 1
