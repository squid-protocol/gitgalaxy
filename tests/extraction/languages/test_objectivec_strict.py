"""objectivec strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore


# ==============================================================================
# OBJECTIVE-C: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #601)
# ==============================================================================
OBJC_RULES = LANGUAGE_DEFINITIONS["objective-c"]["rules"]

_OBJC_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x) { y(); }", "NSInteger total = a + b;"),
    ("structural_boundaries", "@interface Foo : NSObject", "@property (nonatomic) int x;"),
    ("safety", "@try { f(); } @catch (NSException *e) {}", "id result = compute();"),
    ("safety_bypasses", "__unsafe_unretained id x;", 'NSString *name = @"hi";'),
    ("high_risk_execution", "abort();", "NSInteger exitCode = 0;"),
    ("io", "NSData *d = [NSData dataWithContentsOfURL:url];", 'NSString *s = [NSString stringWithFormat:@"%d", x];'),
    ("state_mutation", "self.value = 1;", "[self doSomething];"),
    ("dead_code", "// if (debug) { doThing(); }", "// just a note"),
    ("doc", "/** A doc comment */", "/* internal note, not exported */"),
    ("test", "XCTAssertTrue(x);", "BOOL result = checkValue(x);"),
    ("concurrency", "dispatch_async(queue, ^{ });", "dispatch_barrier_async(queue, ^{ });"),
    ("ui_framework", "UIView *v = [[UIView alloc] init];", "NSObject *obj = [[NSObject alloc] init];"),
    ("closures", "^(int x) { return x + 1; }", "void (^completion)(BOOL success);"),
    ("globals", "[UIApplication sharedApplication];", "[UIApplication performSelector:@selector(x)];"),
    ("decorators", "@property (nonatomic, strong) NSString *name;", "@property NSString *name;"),
    ("generics", "NSArray<NSString *> *names;", "if (a < b) {"),
    (
        "comprehensions",
        "[arr enumerateObjectsUsingBlock:^(id obj, NSUInteger idx, BOOL *stop) {}];",
        "[arr objectAtIndex:0];",
    ),
    ("scientific", "double r = sqrt(4.0);", "double r = pow(x, 2.0);"),
    ("reflection_metaprogramming", "objc_msgSend(obj, sel);", "id obj = [MyClass new];"),
    ("ownership", "// @author Jane Doe", "// Reviewed by: Jane Doe"),
    ("planned_debt", "// TODO: refactor this", "// DONE: refactored, no further action"),
    ("fragile_debt", "// HACK: temporary workaround", "// NOTE: applied a clean, permanent fix"),
    ("spec_exposure", "// [SPEC-123] implements the contract", "// [TICKET-456] fix later"),
    ("ssr_boundaries", "WOResponse *r = [context response];", "NSHTTPURLResponse *r = [context response];"),
    ("events", "[center addObserver:self selector:@selector(x) name:nil object:nil];", "[center removeObserver:self];"),
    ("dependency_injection", "[factory initWithDependency:dep];", "[factory create:dep];"),
    ("macros", "#define MAX_SIZE 100", "#import <Foundation/Foundation.h>"),
    ("pointers", "SEL selector = @selector(foo);", "NSInteger total = a + b;"),
    ("memory_alloc", "id obj = [MyClass alloc];", "id obj = [MyClass instance];"),
    ("inline_asm", '__asm__ volatile ("nop");', "int x = 1;"),
    ("telemetry", 'os_log(OS_LOG_DEFAULT, "started");', 'NSLog(@"started");'),
    ("debug_prints", 'NSLog(@"debug value");', 'os_log(OS_LOG_DEFAULT, "debug value");'),
    ("explicit_casts", "(NSString *)obj", 'NSString *name = @"hello";'),
    ("panics_and_aborts", "@throw exception;", "NSException *exception = [NSException new];"),
    ("thread_sleeps", "sleep(1);", "NSInteger sleepDuration = 1;"),
    ("sync_locks", "@synchronized(self) { }", "dispatch_semaphore_signal(sem);"),
    ("immutability_locks", "const int x = 1;", "int x = 1;"),
    ("cleanup", "[obj release];", "[obj retain];"),
    ("encapsulation", "@private\nint _secret;", "@public\nint _secret;"),
    ("listeners", '[self addObserver:self forKeyPath:@"x"];', '[self removeObserver:self forKeyPath:@"x"];'),
    ("test_skip", 'XCTSkip("not ready");', "XCTAssertEqual(a, b);"),
    (
        "serialization_parsing",
        "[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];",
        "[NSString stringWithUTF8String:bytes];",
    ),
    (
        "regex_execution",
        "NSRegularExpression *re = [NSRegularExpression regularExpressionWithPattern:p options:0 error:nil];",
        'NSString *s = [str componentsSeparatedByString:@","];',
    ),
    ("time_date_logic", "NSDate *now = [NSDate date];", "NSCalendar *cal = [NSCalendar currentCalendar];"),
    ("ipc_rpc_bridges", "NSTask *task = [[NSTask alloc] init];", "NSProcessInfo *info = [NSProcessInfo processInfo];"),
    # --- Issue #1072: signature keys with zero _SIMPLE_CASES coverage ---
    ("api", "@property (nonatomic, strong) NSString *name;", "static NSString *name;"),
    ("bitwise_ops", "NSUInteger mask = flags & 0x0F;", "if (a && b) {"),
    ("import", "#import <Foundation/Foundation.h>", "// #import <Foundation/Foundation.h>"),
    # --- Deep Adversarial Cases ---
    ("branch", "@try\n{", "@trycatch"),
    ("branch", "else if (x) {", "something_else"),
    ("branch", "int x = a ? b : c;", "NSString *url = @\"https://try.example.com\";"),
    ("branch", "@finally {", "@finallysomething"),
    ("branch", "    goto label;", "gotofail"),
    
    ("args", ": (NSString *)name", "if (a) {"),
    ("args", ":(id<MyProto>)arg", "while (1) {"),
    ("args", "^(int a, int b) {", "catch (NSException *e) {"),
    ("args", "void my_func(int a, void (*cb)(int)) {", "sizeof(int);"),
    ("args", ":(void(^)(BOOL, NSError *))completion", "__attribute__((unused))"),
    
    ("func_start", "- (void)doThing:(id)arg;", "void(^my_block)(void) = ^{"),
    ("func_start", "- (NSDictionary<NSString *, id> *)doThing {", "@interface Foo"),
    ("func_start", "+ (id<MyProto>)doThing {", "int x = 1;"),
    ("func_start", "static void (*my_func_ptr)(int) {", "struct Node {"),
    ("func_start", "extern \"C\" void my_export_func(void);", "typedef int MyInt;"),
    
    ("class_start", "@interface MyClass // comment", "@interfaceFoo"),
    ("class_start", "@implementation MyClass {", "@implementationBar"),
    ("class_start", "@interface MyClass /* comment */", "my_struct"),
    ("class_start", "@interface MyClass: NSObject", "@class Foo;"),
    ("class_start", "@interface MyClass (Category)", "int my_interface = 1;"),
    
    ("structural_boundaries", "@interface Foo : NSObject", "@interfaceFoo"),
    ("structural_boundaries", "__strong id obj = nil;", "my_strong_var"),
    ("structural_boundaries", "@synthesize prop = _prop;", "@synthesize_it"),
    ("structural_boundaries", "typedef int MyInt;", "my_typedef"),
    ("structural_boundaries", "struct Node {", "my_struct"),
]


@pytest.mark.parametrize("signature,positive,negative", _OBJC_SIMPLE_CASES)
def test_objectivec_signature_positive_and_negative(signature, positive, negative):
    pattern = OBJC_RULES[signature]
    assert pattern is not None, f"objective-c's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"objective-c {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"objective-c {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_objectivec_args_control_flow_shield():
    """args must not hallucinate control-flow statements as method/function signatures."""
    pattern = OBJC_RULES["args"]
    assert pattern.search("- (void)doThing:(NSString *)name;")
    assert pattern.search("^(int x) { return x; }")
    assert pattern.search("myCFunction(int a, int b) {")
    assert not pattern.search("if (x) {"), "args hallucinated on an if statement"
    assert not pattern.search("while (x) {"), "args hallucinated on a while statement"


def test_objectivec_args_redos_immunity():
    pattern = OBJC_RULES["args"]
    poison = "x" * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_objectivec_func_start_handles_vertical_method_signatures():
    """Regression guard for the documented 'Vertical Return Type Shield'."""
    pattern = OBJC_RULES["func_start"]
    assert pattern.search("- (void)doThing;")
    assert pattern.search("-\n(void)\ndoThing;")
    assert pattern.search("static int myCFunction(int a) {")


def test_objectivec_class_start_captures_name():
    pattern = OBJC_RULES["class_start"]
    m = pattern.search("@interface MyClass : NSObject")
    assert m is not None
    assert m.group(1) == "MyClass"


def test_objectivec_import_dependency_capture():
    dep_pattern = OBJC_RULES["_dependency_capture"]
    m = dep_pattern.search("#import <Foundation/Foundation.h>")
    assert m is not None
    assert "Foundation/Foundation.h" in m.groups()

    m2 = dep_pattern.search('#import "MyHeader.h"')
    assert m2 is not None
    assert "MyHeader.h" in m2.groups()


def test_objectivec_args_and_macros_no_false_collision():
    """
    Ambiguity check: args's control-flow exclusion list and macros's
    preprocessor-directive list share the literal "if", but args requires
    a bare `if` (excluded, not matched) while macros requires a `#if`
    preprocessor prefix -- neither can fire on the other's intended input.
    """
    args = OBJC_RULES["args"]
    macros = OBJC_RULES["macros"]
    assert macros.search("#if DEBUG")
    assert not macros.search("if (x) {"), "macros incorrectly matched a bare if statement"
    assert not args.search("if (x) {"), "args incorrectly matched a bare if statement as a function signature"


def test_objectivec_ampersand_dual_classification_is_known_not_a_bug():
    """
    `&foo` (address-of) intentionally triggers both bitwise_ops and pointers
    -- the `&` token is genuinely overloaded in C-family syntax for both
    unary address-of and binary bitwise-AND, and disambiguating requires
    real parsing, not a regex fix. This documents the current, accepted
    dual-classification rather than treating it as a bug.
    """
    bitwise = OBJC_RULES["bitwise_ops"]
    pointers = OBJC_RULES["pointers"]
    assert bitwise.search("&foo"), "bitwise_ops no longer matches address-of syntax"
    assert pointers.search("&foo"), "pointers no longer matches address-of syntax"
    assert bitwise.search("a & b"), "bitwise_ops failed on a real binary AND"
    assert not pointers.search("a & b"), "pointers incorrectly matched a spaced binary AND as address-of"


def test_objectivec_at_prefixed_directives_regression():
    """
    Regression test for a systemic bug found across 9 objective-c
    signatures: an `@`-prefixed directive (@try, @catch, @finally,
    @synchronized, @interface, @implementation, @protocol, @end,
    @synthesize, @dynamic, @class, @import, @throw, @private, @protected,
    @package, @author) was wrapped in a shared \\b(...)\\b group. \\b
    requires a word/non-word transition, but `@` is non-word, so the
    leading \\b could never match once `@` was preceded by anything else
    non-word (a space, a line start) -- which is how @-directives are
    always written. None of these ever actually matched real code.
    """
    r = OBJC_RULES
    assert r["branch"].search("@try { f(); }")
    assert r["safety"].search("@catch (NSException *e) {}")
    assert r["structural_boundaries"].search("@interface Foo : NSObject")
    assert r["structural_boundaries"].search("@end")
    assert r["concurrency"].search("@synchronized(self) { }")
    assert r["sync_locks"].search("@synchronized(self) { }")
    assert r["panics_and_aborts"].search("@throw exception;")
    assert r["encapsulation"].search("@private\nint x;")
    assert r["ownership"].search("@author Jane Doe")


def test_objectivec_trailing_colon_selector_regression():
    """
    Regression test for a related systemic bug: a colon-terminated Obj-C
    selector keyword (enumerateObjectsUsingBlock:, performSelector:,
    inject:, initWithDependency:, addObserver:, observeValueForKeyPath:,
    subscribeNext:) was wrapped with a trailing \\b after the literal `:`.
    `:` is non-word, so that \\b only worked when followed by ANOTHER
    non-word character -- true for a plain identifier argument, but false
    for the equally common `@selector(...)` argument form (since `@` is
    also non-word, no boundary exists between `:` and `@`).
    """
    r = OBJC_RULES
    assert r["comprehensions"].search("[arr enumerateObjectsUsingBlock:^(id o) {}];")
    assert r["safety_bypasses"].search("[obj performSelector:@selector(foo)];"), (
        "performSelector: followed by @selector(...) -- the most common real form -- still didn't match"
    )
    assert r["dependency_injection"].search("[factory inject:@selector(x)];")
    assert r["listeners"].search("[c addObserver:@selector(x)];")


def test_objectivec_globals_bracket_message_regression():
    """
    Regression test: `[UIApplication sharedApplication]` and
    `[NSWorkspace sharedWorkspace]` were wrapped in the shared \\b(...)\\b
    group. `[` and `]` are both non-word, so neither the leading nor
    trailing \\b could ever match once flanked by anything else non-word
    (a space, a semicolon, line start) -- meaning these two alternatives
    never actually matched real code.
    """
    pattern = OBJC_RULES["globals"]
    assert pattern.search("id app = [UIApplication sharedApplication];")
    assert pattern.search("id ws = [NSWorkspace sharedWorkspace];")
