"""
Dart extraction hardening (epic #813, issue #828). See
tests/extraction/how_to_harden_extraction.md for the methodology.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_valid_dependency_match,
    assert_valid_match,
)

DART_RULES = LANGUAGE_DEFINITIONS["dart"]["rules"]

# -------------------------------------------------------------------------
# 1. CLASS START RULES
# -------------------------------------------------------------------------
CLASS_START_CASES = {
    "valid": [
        ("class SimpleClass {", "SimpleClass"),
        ("abstract class AbstractClass {", "AbstractClass"),
        ("sealed class SealedClass {", "SealedClass"),
        ("base class BaseClass {", "BaseClass"),
        ("interface class InterfaceClass {", "InterfaceClass"),
        ("final class FinalClass {", "FinalClass"),
        ("mixin class MixinClass {", "MixinClass"),
        ("abstract base class AbstractBaseClass {", "AbstractBaseClass"),
        ("class GenericClass<T, U extends List<T>> {", "GenericClass"),
        ("class ExtendsClass extends BaseClass with MixinA, MixinB implements InterfaceA {", "ExtendsClass"),
        ("@Annotation('test')\nclass AnnotatedClass {", "AnnotatedClass"),
        ("@pragma('vm:prefer-inline')\n@JsonSerializable()\nclass MultiAnnotated {", "MultiAnnotated"),
        ("class\nWeirdSpacing\n<T>\nextends\nBase\n{", "WeirdSpacing"),
        ("abstract   interface \t class \n WeirdSpaceClass {", "WeirdSpaceClass"),
        ("class /* inline comment */ CommentedClass {", "CommentedClass"),
        ("extension StringExt on String {", "StringExt"),
        ("extension type Id(int value) {", "Id"),
        ("extension type const ConstId(int value) {", "ConstId"),
    ],
    "invalid": [
        "var my_class_start = true;",
        "Map<String, dynamic> fakeClass = {};",
        "void classLikeFunction() {",
        "String a = 'class Foo {';",
        "print(\"class Foo {\");",
        "// class Foo {",
        "/* class Foo { */",
        "/// class Foo {",
    ],
    "xfail_invalid": [
        "var query = '''\nclass FakeClass {\n''';",
    ],
}

@pytest.mark.parametrize("payload,expected", CLASS_START_CASES["valid"])
def test_dart_class_start_valid(payload, expected):
    assert_valid_match(DART_RULES["class_start"], payload, expected, "dart.class_start")

@pytest.mark.parametrize("payload", CLASS_START_CASES["invalid"])
def test_dart_class_start_invalid(payload):
    assert_invalid_no_match(DART_RULES["class_start"], payload, "dart.class_start")

@pytest.mark.parametrize("payload", CLASS_START_CASES["xfail_invalid"])
@pytest.mark.xfail(reason="String/comment lookalikes lack AST block shielding", strict=True)
def test_dart_class_start_xfail_invalid(payload):
    assert_invalid_no_match(DART_RULES["class_start"], payload, "dart.class_start")


# -------------------------------------------------------------------------
# 2. FUNCTION START RULES
# -------------------------------------------------------------------------
FUNC_START_CASES = {
    "valid": [
        ("void main() {", "main"),
        ("Future<Map<String, List<int>>> complexReturn() async {", "complexReturn"),
        ("Map<String, Function(int, String)> extremelyNested() {", "extremelyNested"),
        ("T id<T>(T value) {", "id"),
        ("List<T> getItems<T extends Item>() {", "getItems"),
        ("(int, String) getRecord() {", "getRecord"),
        ("({int x, int y}) getNamedRecord() {", "getNamedRecord"),
        ("operator +(OtherClass other) {", "operator +"),
        ("operator ==(Object other) {", "operator =="),
        ("operator []=(int index, T value) {", "operator []="),
        ("int get myProperty =>", "myProperty"),
        ("set myProperty(String value) {", "myProperty"),
        ("MyClass() {", "MyClass"),
        ("MyClass.named() {", "MyClass.named"),
        ("factory MyClass.fromJson(Map<String, dynamic> json) {", "MyClass.fromJson"),
        ("@override\nvoid foo() {", "foo"),
        ("Stream<int> countStream(int to) async* {", "countStream"),
        ("Future<\n  Map<\n    String,\n    List<int>\n  >\n> weirdSpacing() {", "weirdSpacing"),
        ("const ThemeData.raw({ int a = 1 }) {", "ThemeData.raw"),
    ],
    "invalid": [
        "var x = functionStart;",
        "typedef IntFunc = int Function();",
        "var myFunc = () {};",
        "String s = \"Future<int> foo() { \";",
        "// void main() {",
        # Issue #1417: Return-type shield (should not wander across `) {` and match body calls)
        "    T? result,\n  ) {\n    Navigator.of(context).popUntilWithResult<T>(predicate, result);",
        "  ) {\n    Identifier.method(foo);",
        # Issue #1421: bare `?` before ternary call, and whole call expression as return type
        "iconTheme ??= isDark\n        ? IconThemeData(color: kDefaultIconLightColor)\n        : IconThemeData(color: kDefaultIconDarkColor);",
        "ErrorSummary('setState() called after dispose(): $this'),\n  ErrorDescription(...)",
        "const int x = 5;",
        "const MyClass x;",
        "implements AutofillClient {",
        "with AutomaticKeepAliveClientMixin {",
        "extends ContextAction<T> {",
    ],
    "xfail_invalid": [
        "print('void main() {');",
        "/* \n void main() { \n */",
    ],
}

@pytest.mark.parametrize("payload,expected", FUNC_START_CASES["valid"])
def test_dart_func_start_valid(payload, expected):
    assert_valid_match(DART_RULES["func_start"], payload, expected, "dart.func_start")

@pytest.mark.parametrize("payload", FUNC_START_CASES["invalid"])
def test_dart_func_start_invalid(payload):
    assert_invalid_no_match(DART_RULES["func_start"], payload, "dart.func_start")

@pytest.mark.parametrize("payload", FUNC_START_CASES["xfail_invalid"])
@pytest.mark.xfail(reason="String/comment lookalikes lack AST block shielding", strict=True)
def test_dart_func_start_xfail_invalid(payload):
    assert_invalid_no_match(DART_RULES["func_start"], payload, "dart.func_start")

def test_dart_slicer_bug_2_and_4():
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    splicer = StructuralExtractor("dart", LANGUAGE_DEFINITIONS)

    # Bug 2: colon-initializer, no-braced-body constructor
    bug2_code = "LabeledGlobalKey(this._debugLabel) : super.constructor();\nvoid nextMethod() {}"
    blocks, _ = splicer._slice_by_braces(bug2_code, "dart", DART_RULES, 0, {})
    assert len(blocks) == 2, "Bug 2: Should find exactly 2 functions (the constructor and nextMethod)"
    assert blocks[0]["name"] == "LabeledGlobalKey"
    assert bug2_code[blocks[0]["start_idx"]:blocks[0]["end_idx"]].strip() == "LabeledGlobalKey(this._debugLabel) : super.constructor();"
    assert blocks[1]["name"] == "nextMethod"

    # Bug 4: multi-line bare call-site invocation used as a list-literal element
    bug4_code = "[\nContextMenuButtonItem(\n  type: ContextMenuButtonType.copy,\n  onPressed: null,\n),\n]"
    blocks, _ = splicer._slice_by_braces(bug4_code, "dart", DART_RULES, 0, {})
    assert len(blocks) == 0, "Bug 4: Should exclude the list-element bare call via Invocation Shield"


def test_dart_slicer_multi_initializer_constructor():
    # Regression case found during independent verification of the original bug-2 fix: a
    # colon-initializer list is not always a single initializer ending at the first `;`/`{` --
    # Dart allows multiple comma-separated initializers (`: a = b, assert(c);`), same as
    # flutter/theme_data.dart's real `ThemeData.raw` constructor. The first fix attempt reused
    # the params-end scanner (which correctly stops at a top-level `,` for Bug 4's list-element
    # detection) for this scan too, so it wrongly stopped at the first initializer's own comma
    # and rejected the whole constructor. The initializer-list scan must skip top-level commas
    # instead, since they never mean "list element" once past a confirmed `:`.
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    splicer = StructuralExtractor("dart", LANGUAGE_DEFINITIONS)

    bodyless_multi_init = (
        "class Foo {\n"
        "  const Foo.raw({\n"
        "    required this.a,\n"
        "  }) : b = a, assert(a != null);\n"
        "\n"
        "  void nextMethod() {}\n"
        "}\n"
    )
    blocks, _ = splicer._slice_by_braces(bodyless_multi_init, "dart", DART_RULES, 0, {})
    names = [b["name"] for b in blocks]
    assert "Foo.raw" in names, "multi-initializer bodyless constructor must still be found"
    assert "nextMethod" in names

    bodied_multi_init = (
        "class Foo {\n"
        "  Foo(this.a) : b = a, assert(a != null) {\n"
        "    print(a);\n"
        "  }\n"
        "}\n"
    )
    blocks, _ = splicer._slice_by_braces(bodied_multi_init, "dart", DART_RULES, 0, {})
    assert [b["name"] for b in blocks] == ["Foo"], "multi-initializer constructor WITH a body must still be found"


# -------------------------------------------------------------------------
# 3. ARGUMENTS RULES
# -------------------------------------------------------------------------
ARGS_CASES = {
    "valid": [
        ("TargetFunc() {", "()"),
        ("TargetFunc(int a) {", "(int a)"),
        ("TargetFunc(int a, String b) {", "(int a, String b)"),
        ("TargetFunc({required int a, String b = 'default'}) {", "({required int a, String b = 'default'})"),
        ("TargetFunc([int a = 1, int b = 2]) {", "([int a = 1, int b = 2])"),
        ("TargetFunc([List<int> x = const [1, 2, 3]]) {", "([List<int> x = const [1, 2, 3]])"),
        ("TargetFunc({Map<String, dynamic> config = const {'key': 'value'}}) {", "({Map<String, dynamic> config = const {'key': 'value'}})",),
        ("TargetFunc(Map<String, List<Map<int, String>>> crazyNested) {", "(Map<String, List<Map<int, String>>> crazyNested)"),
        ("TargetFunc(void Function(int, String) cb, {required bool Function() test}) {", "(void Function(int, String) cb, {required bool Function() test})"),
        ("TargetFunc((int, String) recordArg) {", "((int, String) recordArg)"),
        ("TargetFunc({({int x, int y}) point}) {", "({({int x, int y}) point})"),
        ("TargetFunc(\n  int a,\n  {\n    required String b,\n  }\n) {", "(\n  int a,\n  {\n    required String b,\n  }\n)"),
        ("TargetFunc(  int   a  , \n String   b ) {", "(  int   a  , \n String   b )"),
    ],
    "invalid": [
        "print('(int a)');",
        "// (int a, String b)",
        "/* (int a) */",
        "String str = '(nested(parens))';",
    ],
    "xfail_invalid": [
    ],
}

@pytest.mark.parametrize("payload,expected", ARGS_CASES["valid"])
def test_dart_args_valid(payload, expected):
    assert_valid_match(DART_RULES["args"], payload, expected, "dart.args")

@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_dart_args_invalid(payload):
    assert_invalid_no_match(DART_RULES["args"], payload, "dart.args")

@pytest.mark.parametrize("payload", ARGS_CASES["xfail_invalid"])
@pytest.mark.xfail(reason="String/comment lookalikes lack AST block shielding", strict=True)
def test_dart_args_xfail_invalid(payload):
    assert_invalid_no_match(DART_RULES["args"], payload, "dart.args")

# -------------------------------------------------------------------------
# 4. DEPENDENCY CAPTURE RULES
# -------------------------------------------------------------------------
DEPENDENCY_CAPTURE_CASES = {
    "valid": [
        ("import 'package:foo/foo.dart';", "package:foo/foo.dart"),
        ("import 'dart:async';", "dart:async"),
        ("import 'dart:math' as math;", "dart:math"),
        ("import 'relative_file.dart';", "relative_file.dart"),
        ("import '../parent_dir/file.dart';", "../parent_dir/file.dart"),
        ("import 'package:bar/bar.dart' hide Baz;", "package:bar/bar.dart"),
        ("import 'package:baz/baz.dart' show A, B;", "package:baz/baz.dart"),
        ("import 'package:foo/foo.dart' deferred as fooLib;", "package:foo/foo.dart"),
        ("export 'package:qux/qux.dart';", "package:qux/qux.dart"),
        ("export 'src/internal.dart' show InternalClass;", "src/internal.dart"),
        ("import \n  'package:multiline/multiline.dart'\n  as ml;", "package:multiline/multiline.dart"),
        ("import \t 'package:tab/tab.dart';", "package:tab/tab.dart"),
        ("import \"package:double_quotes/double_quotes.dart\";", "package:double_quotes/double_quotes.dart"),
        ("part 'foo.g.dart';", "foo.g.dart"),
        ("part of 'foo.dart';", "foo.dart"),
        ("part of my_library_name;", "my_library_name"),
    ],
    "invalid": [
        "var import_string = 'import';",
        "print('import \\'package:foo.dart\\';');",
        "String a = \"import 'dart:io';\";",
    ],
    "xfail_invalid": [
        "// import 'package:test/test.dart';",
        "/* \n import 'package:foo/foo.dart'; \n */",
    ],
}

@pytest.mark.parametrize("payload,expected", DEPENDENCY_CAPTURE_CASES["valid"])
def test_dart_dependency_capture_valid(payload, expected):
    assert_valid_dependency_match(DART_RULES["_dependency_capture"], payload, expected, "dart._dependency_capture")

@pytest.mark.parametrize("payload", DEPENDENCY_CAPTURE_CASES["invalid"])
def test_dart_dependency_capture_invalid(payload):
    assert_invalid_no_match(DART_RULES["_dependency_capture"], payload, "dart._dependency_capture")

@pytest.mark.parametrize("payload", DEPENDENCY_CAPTURE_CASES["xfail_invalid"])
@pytest.mark.xfail(reason="String/comment lookalikes lack AST block shielding", strict=True)
def test_dart_dependency_capture_xfail_invalid(payload):
    assert_invalid_no_match(DART_RULES["_dependency_capture"], payload, "dart._dependency_capture")
