"""
TypeScript extraction hardening (epic #813, issue #815). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for typescript in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the four old
monolithic dict files (test_function_extraction_strict.py,
test_args_extraction_strict.py, test_class_extraction_strict.py,
test_dependency_extraction_strict.py) -- typescript's entries were removed
from those four when this file was added.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# tests/ has no __init__.py anywhere in this repo, so a dotted
# `tests.extraction._extraction_harness` import only works by accident
# locally (e.g. `python -m pytest` from the repo root happens to put the
# root on sys.path) and fails in CI, which invokes the `pytest` console
# script directly. Insert this file's parent (tests/extraction/) onto
# sys.path instead, so the harness imports as a plain top-level module.
_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

TS_RULES = LANGUAGE_DEFINITIONS["typescript"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("public async TargetFunc<T>() {", "TargetFunc"),
        ("export const TargetFunc = (req): Res =>", "TargetFunc"),
        ("function TargetFunc<T, U>(", "TargetFunc"),
        # Syntax-era / feature coverage
        ("function* TargetFunc() {", "TargetFunc"),  # generator
        ("async function* TargetFunc() {", "TargetFunc"),  # async generator
        ("export default function TargetFunc() {}", "TargetFunc"),  # default export
        ("abstract class Foo {\n  abstract TargetFunc(): void;\n}", "TargetFunc"),  # abstract method, no body
        ("interface Foo {\n  TargetFunc(x: number): void;\n}", "TargetFunc"),  # interface method signature
        ("namespace Foo {\n  export function TargetFunc() {}\n}", "TargetFunc"),  # namespaced export
        ("function TargetFunc(this: Window, x: number) {", "TargetFunc"),  # explicit `this` parameter
        (
            "class Foo {\n  private readonly TargetFunc = (x: number) => x * 2;\n}",
            "TargetFunc",
        ),  # private readonly arrow class field
        (
            "@Component({ selector: 'app-root' })\nexport class AppComponent {\n  TargetFunc() {}\n}",
            "TargetFunc",
        ),  # decorated Angular component method
        (
            "export const TargetFunc: React.FC<Props> = ({ a, b }) => {",
            "TargetFunc",
        ),  # typed-arrow assignment with explicit type annotation (was a real bug, now fixed)
    ],
    "invalid": [
        "class TargetFunc implements Interface",
        "interface TargetFunc",
        "type Foo = (a: T) => R;",  # type alias -- was a real bug, now fixed
        "export type Foo = (a: T) => R;",
        "class Foo {\n  @Input() TargetFunc: string;\n}",  # decorated field, not a method
        "type TargetFunc = () => void;",
        "if (this.TargetFunc as unknown as boolean) {",
        # NOTE: string-literal lookalikes (`let query = "function Foo() {";`) are
        # NOT tested here as an invalid case -- func_start's own regex has no
        # way to know it's inside a string (that's Prism's/detector.py's job).
        # The real fix (matching against shielded code) lives in
        # detector.py's _slice_by_braces and is tested at that level in
        # test_detector.py::test_detector_js_ts_string_literal_no_longer_hallucinated_as_function.
    ],
    "pathological": [
        ("export \n default \n async \n function \n TargetFunc \n < \n T \n , \n U \n > \n (", "TargetFunc"),
        (
            "@Injectable()\n@Component({\n  selector: 'x',\n  template: '',\n})\nexport class Foo {\n  @HostListener('click')\n  TargetFunc() {}\n}",
            "TargetFunc",
        ),  # stacked class + method decorators
        (
            "function TargetFunc<T extends Record<string, number>>(x: T) {",
            "TargetFunc",
        ),  # one-level-nested generic bound (the established idiom's actual
        # supported depth -- see the known-limitation test below for why
        # this doesn't extend to 2+ levels)
        (
            "export \n const \n TargetFunc \n : \n React.FC<Props> \n = \n ( \n { \n a, \n b \n } \n ) \n => \n {",
            "TargetFunc",
        ),  # typed arrow assignment split across every plausible boundary
        (
            "async \n function \n * \n TargetFunc \n ( \n ) \n {",
            "TargetFunc",
        ),  # async generator split vertically
        (
            "public \n static \n readonly \n TargetFunc \n = \n async \n ( \n x: number \n ) \n : \n Promise<void> \n => \n {",
            "TargetFunc",
        ),  # deeply modifier-stacked static async arrow field
        (
            "export \n abstract \n class \n Foo \n { \n abstract \n TargetFunc \n ( \n x: number \n ) \n : \n void \n ; \n }",
            "TargetFunc",
        ),  # abstract method split vertically
        (
            "interface Foo {\n  TargetFunc<T extends unknown>(x: T): Promise<T[]>;\n}",
            "TargetFunc",
        ),  # generic interface method with generic return type
        (
            "class Foo {\n  #TargetFunc() {}\n}",
            "TargetFunc",
        ),  # private field method (ECMAScript private syntax)
        (
            "export default class {\n  TargetFunc() {}\n}",
            "TargetFunc",
        ),  # anonymous default-exported class with a method
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_typescript_func_start_valid(payload, expected_name):
    assert_valid_match(TS_RULES["func_start"], payload, expected_name, "typescript.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_typescript_func_start_invalid(payload):
    assert_invalid_no_match(TS_RULES["func_start"], payload, "typescript.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_typescript_func_start_pathological(payload, expected_name):
    assert_pathological_match(TS_RULES["func_start"], payload, expected_name, "typescript.func_start")


def test_typescript_func_start_known_limitation_bare_call_at_line_start():
    """
    Documents a known, NOT-fixed limitation (not silently ignored): a bare
    call statement written at true line start with no preceding modifier
    keyword (e.g. a Jest/Mocha `it('...', () => {...})` block) is
    structurally indistinguishable, to a single-pass regex with no scope
    tracking, from a real class-member method signature written the same
    way. Both are `IDENT(...)` at true line start. Fixing this would need
    either scope-awareness (is this inside a class/interface body?) this
    engine doesn't have, or a terminator requirement that would reintroduce
    the exact same "extraction gauntlet expects bare fragments to match"
    conflict that #789 (csharp) hit -- see how_to_add_a_language.md and this
    issue's own findings. Recorded here so a future pass doesn't rediscover
    this and spend time on a fix that was already deliberately deferred.
    """
    func_start = TS_RULES["func_start"]
    jest_block = "describe('suite', () => {\n  it('does the thing', () => {\n    TargetFunc();\n  });\n});"
    assert func_start.search(jest_block), "documents current (accepted) behavior: this does match"


def test_typescript_func_start_string_literal_lookalike_still_matches_at_regex_level():
    """
    Companion to the known-limitation test above: documents that func_start's
    OWN regex still matches a string-literal lookalike when tested in
    isolation (as this file does) -- the real fix for this lives in
    detector.py's _slice_by_braces (matching against shielded code), not in
    the regex itself, and is verified at that level, not here. See
    test_detector.py::test_detector_js_ts_string_literal_no_longer_hallucinated_as_function.
    """
    func_start = TS_RULES["func_start"]
    assert func_start.search('let query = "function Foo() {";'), (
        "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"
    )


def test_typescript_func_start_redos_immunity():
    """
    ReDoS sweep for the type-annotation-skip zone added to the assignment
    alternative (epic #813/#815): bounded to `{0,200}` and excludes `=`/`;`/
    `{`, so an unterminated `IDENT: <garbage>` payload must resolve linearly.
    """
    func_start = TS_RULES["func_start"]
    assert_redos_immune(func_start, "Foo: " + "a" * 100000, timeout_sec=3.0)
    assert func_start.search("const Foo: React.FC<Props> = (p) => {"), "sanity: real case still matches"


def test_typescript_func_start_known_limitation_function_type_annotation_with_own_arrow():
    """
    Documents a known, NOT-fixed limitation in the type-annotation-skip zone
    added for the React.FC-style fix above: the skip zone excludes `=` (so it
    can't cross the real assignment), but a function-TYPE annotation can
    contain its own `=>` (e.g. `const Foo: (x: number) => void = (x) => {`),
    whose `=` is the first character of that `=>`. The skip zone stops one
    character too early there, so the lookahead's subsequent `=`-search
    matches the type's own arrow instead of the real assignment, and the
    whole alternative fails to anchor to `Foo` (the engine then finds a
    later, unintended match instead -- e.g. anchoring to `void`). Excluding
    `=` more narrowly (allow it only as part of a literal `=>`) is possible
    but was judged not worth the added pattern complexity/risk for this
    pass -- recorded here rather than silently accepted so a future pass
    can decide deliberately, not rediscover it.
    """
    func_start = TS_RULES["func_start"]
    m = func_start.search("const Foo: (x: number) => void = (x) => {")
    assert m and m.group(0) != "Foo", "documents current (accepted) behavior: Foo itself is not what matches here"


def test_typescript_func_start_known_limitation_generic_nesting_beyond_one_level():
    """
    Documents a known, NOT-fixed limitation shared by every "Rule 11"
    one-level-nesting fix in this codebase: the idiom
    `<(?:[^<>]|<[^<>]*>)*>` handles exactly one level of self-nesting, not
    arbitrary depth. A 2+-level-nested generic bound
    (`Record<string, Array<Map<string, number>>>`, three levels deep) breaks
    the same way the original flat `<[^>]*>` broke on one level. True
    arbitrary-depth support would need real recursive matching, which
    Python's `re` module doesn't support without switching to the third-
    party `regex` package -- judged out of scope for this pass given how
    rare 3+-level-deep generic bounds are in real code relative to the
    1-level case this fix targets.
    """
    func_start = TS_RULES["func_start"]
    assert not func_start.search("function TargetFunc<T extends Record<string, Array<Map<string, number>>>>(x: T) {"), (
        "documents current (accepted) behavior: 2+-level nesting is not supported"
    )


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("function TargetFunc<T>(val: T): T {", "TargetFunc"),
        ("public TargetFunc(private id: string) {", "TargetFunc"),
        ("constructor(private readonly logger: Logger, public id: string) {", None),
        ("function foo(a: Record<string, (x: number) => void>) {", None),  # nested-paren generic param (Rule 11)
        ("function foo({ a, b = 1, ...rest }: Props) {", None),  # destructured param w/ default and rest
    ],
    "invalid": [
        "return TargetFunc<string>(val);",
        "catch (e: any) {",
    ],
    "pathological": [
        (
            # NOTE: expected_name is None here (not "TargetFunc") deliberately --
            # args' own alternatives don't all reliably anchor to the enclosing
            # function name (e.g. a nested callback parameter's own `=>` can
            # win the leftmost-match race over the outer `function ... (`
            # alternative when the outer parameter list contains nested
            # parens). args' job is proving a parameter block is captured
            # without ReDoS, not name-anchoring -- the original monolithic
            # test suite this was migrated from never actually checked the
            # name for args either (this file's own `assert_pathological_match`
            # would otherwise now enforce that check where the old harness
            # silently didn't).
            "export \n function \n TargetFunc \n < \n T extends Record<string, any> \n > \n (\n  config: Partial<T>,\n  callback: (err: Error | null) => void\n) \n {",
            None,
        ),
        (
            "constructor(\n  @Inject(TOKEN) private readonly service: FooService,\n  @Optional() private bar?: BarService,\n) {",
            None,
        ),  # Angular DI-decorated constructor params, vertical
        (
            "function foo(\n  a: Map<string, Array<Record<string, number>>>,\n  b: (x: number, y: number) => Promise<void>,\n) {",
            None,
        ),  # deeply nested generic + function-type param, vertical
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_typescript_args_valid(payload, expected_name):
    assert_valid_match(TS_RULES["args"], payload, expected_name, "typescript.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_typescript_args_invalid(payload):
    assert_invalid_no_match(TS_RULES["args"], payload, "typescript.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_typescript_args_pathological(payload, expected_name):
    assert_pathological_match(TS_RULES["args"], payload, expected_name, "typescript.args")


def test_typescript_args_known_limitation_bare_call_at_line_start():
    """
    Same fundamental ambiguity as func_start's own known-limitation test
    above, for the `args` rule: a bare call statement at true line start
    (`TargetFunc(a, b);`) is structurally identical to a bare method
    signature and is not excluded. Documented, not silently ignored.
    """
    args = TS_RULES["args"]
    assert args.search("TargetFunc(a, b);"), "documents current (accepted) behavior: this does match"


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("export class TargetEntity {", "TargetEntity"),
        ("export default abstract class TargetEntity", "TargetEntity"),
        ("enum TargetEntity {", "TargetEntity"),
        ("export abstract class TargetEntity<T> implements Bar<T>, Baz {", "TargetEntity"),
        ("@Injectable()\nexport class TargetEntity {", "TargetEntity"),  # decorated Angular service
        ("class TargetEntity extends Bar<Baz<Qux>> {", "TargetEntity"),  # nested generic in extends clause
    ],
    "invalid": [
        "const a = class {}",
        "classyFunction()",
        "import { TargetEntity } from 'foo'",
        "type TargetEntity = { a: string };",
        "const TargetEntity = class {};",
    ],
    "pathological": [
        ("export \n default \n abstract \n class \n TargetEntity \n extends \n BaseEntity", "TargetEntity"),
        (
            "export \n class \n TargetEntity \n < \n T \n extends \n Comparable<T> \n > \n extends \n Base<T> \n implements \n Foo, \n Bar \n {",
            "TargetEntity",
        ),  # nested generic bound + extends + implements, vertically split (the real bug this fixed)
        (
            "@Entity()\n@Table({ name: 'targets' })\nexport class TargetEntity {",
            "TargetEntity",
        ),  # stacked class decorators (TypeORM-style)
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_typescript_class_start_valid(payload, expected_name):
    assert_valid_match(TS_RULES["class_start"], payload, expected_name, "typescript.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_typescript_class_start_invalid(payload):
    assert_invalid_no_match(TS_RULES["class_start"], payload, "typescript.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_typescript_class_start_pathological(payload, expected_name):
    assert_pathological_match(TS_RULES["class_start"], payload, expected_name, "typescript.class_start")


def test_typescript_class_start_nested_generic_extends_regression():
    """
    Regression test for a real bug (epic #813/#815): the generic step-over
    between the class name and the extends/implements check was flat
    (`<[^>]*>`), truncating at the FIRST `>` -- a one-level-nested generic
    bound (`class Foo<T extends Comparable<T>> extends Bar {`, a realistic
    bounded-generic pattern) left a stray `>` unconsumed right before the
    real `extends` clause, silently losing the ENTIRE extends/implements
    capture (group 2) even though the class name itself (group 1) still
    matched fine -- an easy bug to miss since the primary capture looked
    correct.
    """
    old_pattern_group2_lost = TS_RULES["class_start"].groups == 2  # sanity the rule still has both groups
    assert old_pattern_group2_lost

    class_start = TS_RULES["class_start"]
    m = class_start.search("class Foo<T extends Comparable<T>> extends Bar {")
    assert m and m.group(1) == "Foo", "class name capture regressed"
    assert m.group(2) and "Bar" in m.group(2), "extends clause still lost behind a nested generic bound"


def test_typescript_class_start_redos_immunity():
    """ReDoS sweep for the widened one-level-nesting generic step-over."""
    class_start = TS_RULES["class_start"]
    assert_redos_immune(class_start, "class Foo<" + "a" * 100000, timeout_sec=3.0)
    assert class_start.search("class Foo<T extends Comparable<T>> extends Bar {")


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ('import type { Node } from "./ast/node";', "./ast/node"),
        ('export * from "../utils";', "../utils"),
        ('import * as fs from "fs";', "fs"),  # namespace import
        ('import Foo, { Bar, Baz } from "./foo";', "./foo"),  # default + named import
        ('const x = await import("./dynamic-module");', "./dynamic-module"),  # dynamic import()
        ('import "./side-effect-only";', "./side-effect-only"),  # side-effect-only import -- was a real bug, now fixed
        ('export { Foo } from "./foo";', "./foo"),  # re-export
    ],
    "invalid": [
        'let from_path = "x";',
        'let fromPath = "not/a/real/import";',
    ],
    "pathological": [
        (
            "import \n type \n { \n  ASTNode \n } \n from \n '@typescript-eslint/parser'",
            "@typescript-eslint/parser",
        ),
        (
            'import \n "./side-effect-only-vertical"',
            "./side-effect-only-vertical",
        ),  # the new bare-import alternative, vertically split
        (
            'export \n * \n from \n "../deeply/nested/relative/path"',
            "../deeply/nested/relative/path",
        ),
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_typescript_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(
        TS_RULES["_dependency_capture"], payload, expected_path, "typescript._dependency_capture"
    )


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_typescript_dependency_capture_invalid(payload):
    assert_invalid_no_match(TS_RULES["_dependency_capture"], payload, "typescript._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_typescript_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        TS_RULES["_dependency_capture"], payload, expected_path, "typescript._dependency_capture"
    )


def test_typescript_dependency_capture_side_effect_import_regression():
    """
    Regression test for a real bug (epic #813/#815): side-effect-only
    imports (`import "./styles.css";`, extremely common for CSS/polyfill
    imports with no bound name) have no `from` keyword and no parens at all
    -- neither of the two original alternatives (the `from`-requiring one,
    the `require`/`import(...)`-parenthesized one) matched them, so this
    entire common import style produced zero dependency-graph edges.
    """
    old_pattern_group_count = 2  # the two original alternatives, before the fix added a third
    pattern = TS_RULES["_dependency_capture"]
    assert pattern.groups > old_pattern_group_count, "the new bare-import alternative's group should be present"

    m = pattern.search('import "./styles.css";')
    assert m and any(g and "./styles.css" in g for g in m.groups()), "side-effect-only import still not captured"

    # Real forms using the other two alternatives must still work.
    m2 = pattern.search('import { Foo } from "./foo";')
    assert m2 and any(g and "./foo" in g for g in m2.groups())


def test_typescript_dependency_capture_redos_immunity():
    """ReDoS sweep for the new bare-import alternative."""
    pattern = TS_RULES["_dependency_capture"]
    assert_redos_immune(pattern, 'import "' + "a" * 100000, timeout_sec=3.0)
    assert pattern.search('import "./real-path";')
