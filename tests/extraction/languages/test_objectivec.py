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
            # #2214: untyped return types without parentheses
            ("- unsigned char next_input_block\n{", "next_input_block"),
            ("- void appendEndBlock\n{", "appendEndBlock"),
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
        # #2773: every payload here now carries the `-`/`+` method-declaration
        # lead the rule requires. A bare selector span on its own is a MESSAGE
        # SEND, not a parameter surface, and is asserted invalid below.
        "valid": [
            ("- (void):(int)a", None),
            ("- (void)withString:(NSString *)str", None),
            ("- (void)andBlock:(void (^)(int, BOOL))block", None),
            ("- (void)generics:(NSArray<__kindof UIView *> *)views", None),
            ("- (void)cppRef:(const std::vector<int>&)ref", None),
            ("- (void)multiBlock:(void (^) (void (^)(BOOL)))nestedBlock", None),
            ("- (void)arrayArg:(int[])array", None),
            ("- (void):   (   id <  MyProtocol >  )  arg", None),
            ("- (void):\n(int)\narg", None),
            ("- (void)crazySpacing   :   (   NSString *   )   arg", None),
            ("- (void)argWithAttr:(int)__attribute__((unused))a", None),
            ("- (void)nullability:(nonnull NSString *)str", None),
            # #1335: older, still-valid untyped keyword-message style
            # (defaults to `id`) -- language-crucible/data/objective-c/
            # worldwideweb/HyperManager.m has ~20 of these in one file.
            # Untyped style also omits the return type entirely.
            ("- back:sender", None),
            ("+ help:sender", None),
            ("+ setManager:aManager", None),
            ("-closeOthers:sender", None),
            # Mixed typed + untyped segments in the same signature.
            ("- (id)doThing:(int)x withOther:y", None),
            # Multi-line vertical signature, and func_start's own leading
            # macro / __attribute__ prefixes.
            ("- (void)newParent:(Anchor *)p\n              tag:(const char *)t", None),
            ("NS_AVAILABLE - (void)modern:(int)x", None),
            ("__attribute__((deprecated)) - (void)old:(int)x", None),
            # Block literals keep their own parameter list.
            ("^(int x, BOOL y) { return; }", None),
            # A plain C declaration whose parameter list opens with a real type.
            ("int equivalent(const char *s, const char *t) {", None),
            ("static void reset(MyStruct *state);", None),
            ("void teardown(void);", None),
        ],
        "invalid": [
            "case 1:",
            "default:",
            # #2773: message SENDS. Every one of these matched before the fix
            # -- 120 of the 277 false hits on the crucible corpus were this
            # shape (`[store setVersion:V]`, `[list objectAt:i]`).
            "[store setVersion:ANCHOR_CURRENT_VERSION];",
            "return [self addObject:self];",
            "id found = [list objectAt:i];",
            "[self loadAnchor:nodeAnchor Diagnostic:diag];",
            # A message send at true line start, inside a method body.
            "    [self setNode:node];",
            # #2773: the string-literal hole the issue asked for a negative
            # test on. Prism strips comments from the code stream but NOT
            # strings, so `@"status: ok"` used to score an argument.
            'NSString *s = @"status: ok";',
            '@":(int)a"',
            "// :(int)a",
            # A ternary's `:` read as an untyped selector segment.
            "return (condition) ? a : b;",
            "self.property = condition ? a : b;",
            # A goto label followed by a statement.
            "label: statement;",
            # A superclass declaration's colon.
            "@interface Anchor:Object",
            # #2773: bare CALL statements. The plain-C arm accepted any
            # `name(...)` followed by `{`/`;` -- 146 of the false hits.
            "XCTAssert(kit);",
            "NSAssert(value);",
            "os_log(msg);",
            "free(conn);",
            "abort();",
            "exit(payload);",
            'printf("new Anchor %i named `%s\'\\n", self, tag);',
            # A capitalised first argument used to satisfy the PascalCase
            # typedef fallback the c/cpp rules share; a parameter NAME is now
            # required after the type token.
            "StrAllocCopy(Address, tag);",
            'HTParse(anAddress, "", PARSE_ANCHOR);',
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


def test_objc_args_body_lookalikes_no_longer_match_the_rule_itself():
    """
    #2773 closes what #1335 could only shield.

    Recognising the untyped `label:name` keyword-message shape (see the
    "valid" cases above, e.g. `- back:sender`) used to make the regex match,
    in isolation, every body-only shape that is lexically identical to a real
    untyped parameter:
    - a keyword-message SEND (`[self TargetFunc:a withB:b];`) -- Objective-C
      deliberately spells a method's signature and its call site the same way
    - a C goto label followed by a statement (`label: statement;`)
    - a ternary's true-branch expression read as a label
      (`cond ? isOn : isOff` -- "isOn" IS a syntactically valid label)
    - the same shape inside a comment or a STRING (`@":(int)a"`)

    detector.py's `_slice_by_braces` bounds the per-function args search to the
    method's own signature text (`_calculate_block_metrics`'s
    `args_search_text`, and test_objectivec_args_body_lookalikes_excluded_by_
    signature_bound in tests/core_engine/test_detector.py), which made these
    unreachable for one metric only -- `avg_func_args`. The FILE-level
    `struct_args` count has no such bound: it is the raw rule count over the
    whole code stream, and on language-crucible/data/objective-c it was reading
    378 where only 101 declarations exist. Anchoring the selector arm to a
    `-`/`+` method-declaration lead removes the ambiguity from the rule itself,
    so the shield is now belt-and-braces rather than the only defence.

    The string case is the one the pipeline never shielded at all: prism strips
    comments from the code stream, but strings count like ordinary code text
    for every signal (#2535), so `@"status: ok"` really was an `args` hit.
    """
    args = OBJC_RULES["args"]
    assert args.search("[self TargetFunc:a withB:b];") is None
    assert args.search("label: statement;") is None
    assert args.search("return (condition) ? a : b;") is None
    assert args.search("self.property = condition ? a : b;") is None
    assert args.search("// :(int)a") is None
    assert args.search('@":(int)a"') is None
    assert args.search('NSString *s = @"status: ok";') is None
    # ...while the declarations those shapes were confused with still match.
    assert args.search("- (void)TargetFunc:(int)a withB:(int)b {") is not None
    assert args.search("- back:sender") is not None


def test_objc_args_known_limitation_line_leading_selector_in_a_string():
    """
    #2773's residue, kept explicit rather than left implied: the `-`/`+` lead
    is a LEXICAL anchor, so a multi-line string literal whose continuation line
    happens to begin with `- ` followed by a selector-shaped span still matches
    in isolation. Objective-C has no multi-line string literal, so the only way
    to write one is an explicit `\\`-continued C string -- vanishingly rare, and
    zero occurrences across both corpora. Documented, not silently ignored.
    """
    args = OBJC_RULES["args"]
    assert args.search('char *usage = "line one\\\n- setThing:value";') is not None


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
