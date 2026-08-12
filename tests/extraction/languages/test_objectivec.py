# ruff: noqa: S101
"""
Objective-C/C++ extraction hardening (epic #813, issue #830). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for Objective-C in one file: func_start,
args, class_start, _dependency_capture.
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
    assert_pathological_match,
    assert_valid_dependency_match,
    assert_valid_match,
)

OBJC_RULES = LANGUAGE_DEFINITIONS["objective-c"]["rules"]

OBJECTIVEC_ADVERSARIAL_TESTS = {
    "func_start": {
        "valid": [
            ("- (void)standardMethod;", "standardMethod"),
            ("+ (instancetype)sharedInstance;", "sharedInstance"),
            ("-(id<MyProtocol>)methodWithProtocol:(id)arg;", "methodWithProtocol"),
            ("  \t  -   (  void * ) crazySpaces : ( int ) a ;", "crazySpaces"),
            ("-\n(void)\nnewlines\n:\n(int)x;", "newlines"),
            ("- (void (^)(int, NSString *))methodReturningBlock:(NSString *)arg;", "methodReturningBlock"),
            (
                "- (NSMapTable<NSString *, NSSet<id<NSCopying>> *> *)complexGenerics:(NSArray<__kindof UIView *> *)views;",
                "complexGenerics",
            ),
            ("- (void (^) (void (^)(BOOL)))nestedBlocks;", "nestedBlocks"),
            (
                "- (void (*)(int, float))methodReturningFunctionPointer:(int[])arrayArg;",
                "methodReturningFunctionPointer",
            ),
            ("- (void)methodWithAttribute __attribute__((deprecated));", "methodWithAttribute"),
            ("- (void)methodWithMacro:(NSString *)string NS_AVAILABLE_IOS(8_0);", "methodWithMacro"),
            ("UI_APPEARANCE_SELECTOR - (UIColor *)appearanceColor;", "appearanceColor"),
            ("- (nullable id)methodWithNullability:(nonnull NSString *)string;", "methodWithNullability"),
            ("static inline void c_style_func(int a, float b) {", "c_style_func"),
            ('extern "C" void cpp_c_func(void) {', "cpp_c_func"),
            ("void* function_returning_pointer(char** arg) {", "function_returning_pointer"),
            ("NS_INLINE void inlineFunction(void) {", "inlineFunction"),
            ("__attribute__((always_inline)) void attrFunction(void) {", "attrFunction"),
            # #1336: bodyless C-style prototypes (terminated by `;`, not `{...}`) --
            # e.g. language-crucible/data/objective-c/worldwideweb/HyperText.h's
            # `extern void write_rtf_header(NXStream* rtfStream);`. The regex still
            # matches the name correctly here (it's syntactically function-shaped) --
            # detector.py's pipeline is what now explicitly excludes these from
            # func_start's scope (a prototype has no body to score), rather than the
            # old behavior of finding them only by accident via a later, unrelated
            # `{` and attributing that block's span as a bogus body. See
            # test_objectivec_bodyless_c_style_prototype_excluded_not_misattributed
            # in tests/core_engine/test_detector.py for the pipeline-level assertion.
            ("extern void write_rtf_header(NXStream* rtfStream);", "write_rtf_header"),
            ("static int helper_prototype(int x);", "helper_prototype"),
            ("- (std::vector<std::shared_ptr<MyNamespace::MyClass>>)getVector;", "getVector"),
            ("- (const std::map<std::string, std::vector<int>>&)getMap;", "getMap"),
            ("template <typename T> void cppTemplateFunction(T arg) {", "cppTemplateFunction"),
            (
                "- (instancetype)initWithVeryLongArgument:(NSString *)arg1 andAnotherVeryLongArgument:(NSString *)arg2 andYetAnother:(NSNumber *)arg3 andBlock:(void (^)(NSArray<NSString *> * _Nullable, NSError * _Nullable))completionHandler;",
                "initWithVeryLongArgument",
            ),
        ],
        "invalid": [
            "// - (void)commentedMethod;",
            "/// - (void)docStringMethod;",
            'NSString *str = @"- (void)stringMethod;";',
            'char *c_str = "+ (id)cStringMethod;";',
            'NSString *edgeCase = @"\\" - (void)escapedStringMethod;";',
            "@property (nonatomic, copy) void (^blockProperty)(int, NSString *);",
            "@property (readonly) id<NSCopying> (*functionPointerProperty)(int);",
            "void (^myBlock)(int) = ^(int x) { return x; };",
            "int a = b - (c + d);",
            "a - (b) * c;",
            "NS_ASSUME_NONNULL_BEGIN",
            "MY_MACRO_CALL(a, b);",
            "XCTAssertEqual(a, b);",
            "if (condition) {",
            "for (int i = 0; i < 10; ++i) {",
            "WHILE_MACRO(x) {",
            "switch (x) {",
            # #1336: the C-style alternative's identifier capture has no exclusion
            # shield against bare two-token call/return statements (the leading word
            # satisfies the loop as a fake "return type") -- these used to match at
            # the regex level too, only ever staying harmless because detector.py's
            # brace-only fallback silently dropped them when no `{` followed nearby.
            # Now that detector.py accepts a bare `;` terminator for this
            # alternative (mirroring the `-`/`+` method form), a "not a function"
            # keyword shield in the regex itself must reject these outright.
            "return foo(x);",
            "return computeValue(a, b);",
            "else doSomething(x);",
            "goto cleanup(x);",
        ],
        "pathological": [
            ("- \n ( \n NSDictionary<NSString *, NSArray<NSNumber *> *> * \n ) \n TargetFunc \n :", "TargetFunc")
        ],
    },
    "class_start": {
        "valid": [
            ("@interface MyClass : NSObject <Protocol1, Protocol2>", "MyClass"),
            ("@implementation MyClass", "MyClass"),
            ("@protocol MyProtocol <NSObject>", "MyProtocol"),
            ("@   interface   MyClass   :   NSObject", "MyClass"),
            ("@interface MyClass ()", "MyClass"),
            ("@interface MyClass (CategoryName)", "MyClass"),
            ("@implementation MyClass (CategoryName)", "MyClass"),
            ("@interface MyClass<ObjectType: id<NSCopying>> : NSObject", "MyClass"),
            ("@interface Container<__covariant T> : NSObject", "Container"),
            ("@implementation MyClass {\n    int _ivar;\n    NSString* _str;\n}", "MyClass"),
            ("@interface \n MyClass \n : \n NSObject", "MyClass"),
            ("@interface MyClass ()\n<Protocol1, Protocol2>\n@end", "MyClass"),
        ],
        "invalid": [
            "// @interface FakeClass",
            'NSString *classStr = @"@implementation FakeClass";',
            "/* @protocol FakeProtocol */",
            "@class ForwardDeclaredClass;",
            "@property (strong) id<MyProtocol> protocolProperty;",
            "@end",
        ],
        "pathological": [("@interface \\\n MyClass \\\n : NSObject", "MyClass")],
    },
    "args": {
        "valid": [
            (":(int)a", None),
            ("withString:(NSString *)str", None),
            ("andBlock:(void (^)(int, BOOL))block", None),
            ("generics:(NSArray<__kindof UIView *> *)views", None),
            ("cppRef:(const std::vector<int>&)ref", None),
            ("multiBlock:(void (^) (void (^)(BOOL)))nestedBlock", None),
            ("arrayArg:(int[])array", None),
            (":   (   id <  MyProtocol >  )  arg", None),
            (":\n(int)\narg", None),
            ("crazySpacing   :   (   NSString *   )   arg", None),
            ("argWithAttr:(int)__attribute__((unused))a", None),
            ("nullability:(nonnull NSString *)str", None),
        ],
        "invalid": [
            "label: statement;",
            "case 1:",
            "default:",
            "return (condition) ? a : b;",
            "self.property = condition ? a : b;",
        ],
        "pathological": [],
    },
    "_dependency_capture": {
        "valid": [
            ("#import <Foundation/Foundation.h>", "Foundation/Foundation.h"),
            ('#import "MyHeader.h"', "MyHeader.h"),
            ("@import Foundation;", "Foundation"),
            ("@import UIKit.UIView;", "UIKit.UIView"),
            ("#include <vector>", "vector"),
            ('#  import   "WeirdSpacing.h"', "WeirdSpacing.h"),
            ("#import\t<TabSpacing/TabSpacing.h>", "TabSpacing/TabSpacing.h"),
            ("@\timport\tFoundation\t;", "Foundation"),
            ('#import \\\n "EscapedNewline.h"', "EscapedNewline.h"),
        ],
        "invalid": [
            '// #import "Fake.h"',
            "/* @import Foundation; */",
            'NSString *importStr = @"#import <Fake/Fake.h>";',
            "#ifndef IMPORT_GUARD",
            "#define import something",
            "#pragma mark - Imports",
            '#error "Don\'t import this"',
            "#include MACRO_HEADER_FILE",
        ],
        "pathological": [],
    },
}


# ==============================================================================
# FUNC_START
# ==============================================================================
@pytest.mark.parametrize("payload,expected_name", OBJECTIVEC_ADVERSARIAL_TESTS["func_start"]["valid"])
def test_objc_func_start_valid(payload, expected_name):
    assert_valid_match(OBJC_RULES["func_start"], payload, expected_name, "objective-c.func_start")


@pytest.mark.parametrize("payload", OBJECTIVEC_ADVERSARIAL_TESTS["func_start"]["invalid"])
def test_objc_func_start_invalid(payload):
    assert_invalid_no_match(OBJC_RULES["func_start"], payload, "objective-c.func_start")


@pytest.mark.parametrize("payload,expected_name", OBJECTIVEC_ADVERSARIAL_TESTS["func_start"]["pathological"])
def test_objc_func_start_pathological(payload, expected_name):
    assert_pathological_match(OBJC_RULES["func_start"], payload, expected_name, "objective-c.func_start")


def test_objc_func_start_known_limitation_comment_lookalike_shielded_by_pipeline():
    """
    Documents that in isolation, the regex matches function-shaped text inside
    multiline comments (e.g., `/* \\n - (void)method; \\n */`). However, Obj-C is in
    the `standard_block` lexical family, which strips block comments BEFORE the
    regex is applied. So this is not a live pipeline bug.
    """

    func_start = OBJC_RULES["func_start"]
    code = "/* \n - (void)multilineCommentMethod; \n */"
    assert func_start.search(code) is not None, "isolated regex still matches"


# ==============================================================================
# CLASS_START
# ==============================================================================
@pytest.mark.parametrize("payload,expected_name", OBJECTIVEC_ADVERSARIAL_TESTS["class_start"]["valid"])
def test_objc_class_start_valid(payload, expected_name):
    assert_valid_match(OBJC_RULES["class_start"], payload, expected_name, "objective-c.class_start")


@pytest.mark.parametrize("payload", OBJECTIVEC_ADVERSARIAL_TESTS["class_start"]["invalid"])
def test_objc_class_start_invalid(payload):
    assert_invalid_no_match(OBJC_RULES["class_start"], payload, "objective-c.class_start")


@pytest.mark.parametrize("payload,expected_name", OBJECTIVEC_ADVERSARIAL_TESTS["class_start"]["pathological"])
def test_objc_class_start_pathological(payload, expected_name):
    assert_pathological_match(OBJC_RULES["class_start"], payload, expected_name, "objective-c.class_start")


# ==============================================================================
# ARGS
# ==============================================================================
@pytest.mark.parametrize("payload,expected_name", OBJECTIVEC_ADVERSARIAL_TESTS["args"]["valid"])
def test_objc_args_valid(payload, expected_name):
    assert_valid_match(OBJC_RULES["args"], payload, expected_name, "objective-c.args")


@pytest.mark.parametrize("payload", OBJECTIVEC_ADVERSARIAL_TESTS["args"]["invalid"])
def test_objc_args_invalid(payload):
    assert_invalid_no_match(OBJC_RULES["args"], payload, "objective-c.args")


def test_objc_args_known_limitation_comment_string_lookalike_shielded_by_pipeline():
    """
    Documents that args regex matches inside comments/strings in isolation
    (e.g., `// :(int)a` or `@\":(int)a\"`).
    In the real pipeline, the `standard_block` lexical family strips comments
    and strings before matching, so these are safely shielded.
    """
    args = OBJC_RULES["args"]
    assert args.search("// :(int)a") is not None
    assert args.search('@":(int)a"') is not None


# ==============================================================================
# DEPENDENCY
# ==============================================================================
@pytest.mark.parametrize("payload,expected_path", OBJECTIVEC_ADVERSARIAL_TESTS["_dependency_capture"]["valid"])
def test_objc_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(
        OBJC_RULES["_dependency_capture"], payload, expected_path, "objective-c._dependency_capture"
    )


@pytest.mark.parametrize("payload", OBJECTIVEC_ADVERSARIAL_TESTS["_dependency_capture"]["invalid"])
def test_objc_dependency_capture_invalid(payload):
    assert_invalid_no_match(OBJC_RULES["_dependency_capture"], payload, "objective-c._dependency_capture")
