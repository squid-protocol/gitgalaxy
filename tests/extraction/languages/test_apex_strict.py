"""apex strict structural-signature coverage.

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


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# CROSS-LANGUAGE REDOS SWEEP: "BARE IDENTIFIER BEFORE ARROW" FAMILY
# ==============================================================================
# All found by a systematic ReDoS sweep across every language's compiled
# patterns (not just the ones with an existing historical-bug comment):
# an unbounded identifier/word-run quantifier with no preceding \b anchor,
# immediately followed by a required-but-often-absent literal suffix
# (=>, ->, __c.getInstance, etc.). Because the leading character class has
# no boundary anchor, the engine retries the greedy-then-backtrack match at
# EVERY position in a long run of matching characters -- O(n^2) total, not
# exponential, but still a real DoS risk on a single pathologically long
# line (e.g. minified/obfuscated code). All bounded with numeric clamps
# instead of possessive quantifiers (`*+`), since those aren't available
# until Python 3.11 and this package supports 3.9+.


def test_apex_globals_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["apex"]["rules"]["globals"]
    assert_redos_immune(pattern, "x" * 40000, timeout_sec=3.0)
    assert pattern.search("MyObject__c.getInstance()")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# CROSS-LANGUAGE SWEEP: `@`-PREFIXED LEADING-\b BOUNDARY BUGS
# ==============================================================================
# Found while investigating dart's `test_skip` (`@Ignore` never matched) and
# broadening the earlier find_symbolic_boundary_bugs.py-style sweep to also
# check the START of each \b(...)\b alternative, not just the end. `@` is a
# non-word character, so a shared LEADING \b before a `@`-prefixed
# alternative can only fire when a word character immediately precedes the
# `@` -- never true for how annotations/attributes/decorators are actually
# written (always preceded by whitespace or a line start). This silently
# blinded 10 already-"closed" or partially-fixed languages to nearly all of
# their annotation-based structural signatures. Each language's own
# dedicated closure PR already covers this signature; these are targeted
# regressions for the specific alternatives found broken, bundled together
# the same way the earlier ReDoS (#631) and symbolic-\b (#637) cross-language
# sweeps were.


def test_apex_suppresswarnings_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["apex"]["rules"]
    assert r["safety_bypasses"].search("@SuppressWarnings('PMD')")
    assert r["test_skip"].search("@SuppressWarnings('PMD')")


# ==============================================================================
# APEX: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #573, part of epic #518)
# ==============================================================================
APEX_RULES = LANGUAGE_DEFINITIONS["apex"]["rules"]

_APEX_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    # Deepened cases (Issue #1074)
    # branch
    ("branch", "if \n (x == 1) {", "Integer x = 1;"),
    ("branch", "else if(y != 2)", "elseVar = 5;"),
    ("branch", "switch on account.Industry {", "Integer switchCount = 0;"),
    ("branch", "when 'Agriculture' {", "whenMethod();"),
    ("branch", "try {", "tryVar = 1;"),
    ("branch", "catch (Exception e) {", "catchVar = 1;"),
    ("branch", "finally {", "finalVar = 1;"),
    ("branch", "do {", "doMethod();"),

    # args
    ("args", "public static List<Id> getIds(Map<Id, Account> accMap, Boolean flag) {", "System.debug(map, true);"),
    ("args", "global override Database.QueryLocator start(Database.BatchableContext BC)", "Id x = start();"),
    ("args", "@AuraEnabled(cacheable=true) public static List<Account> getAccounts(String name)", "public class Foo {"),
    ("args", "@RestResource(urlMapping='/Account/*/details/(.*)') global static void doThing(String id) {", "System.debug('public void doThing()');"),
    ("args", "trigger MyTrigger on Account (before insert, after update) {", "for (Integer i = 0; i < 10; i++) {"),
    ("args", "public void noArgs()", "class noArgs {"),
    ("args", "private static Map<Id, List<Contact>> complex(Map<String, Map<Id, SObject>> nested, Boolean flag) {", "String x = 'x';"),

    # func_start
    ("func_start", "public void doThing() {", "public class Foo {"),
    ("func_start", "global static List<Account> getAccounts() {", "global class AccountService {"),
    ("func_start", "private \n void \n helperMethod \n () {", "private String varName;"),
    ("func_start", "@AuraEnabled\npublic static String performAction(Id recId)", "@AuraEnabled public Integer count;"),
    ("func_start", "override protected Database.QueryLocator start(Database.BatchableContext BC)", "override class MyBatch {"),
    ("func_start", "@AuraEnabled(cacheable=true) public static List<Account> getAccounts() {", "if (true) {"),
    ("func_start", "@RestResource(urlMapping='/Account/*/details/(.*)') global static void doThing() {", "public interface Foo {"),
    ("func_start", "trigger MyTrigger on Account (before insert) {", "catch (Exception e) {"),
    ("func_start", "public virtual List<Map<String, Object>> complexReturn() {", "return complexReturn;"),

    # class_start
    ("class_start", "public class Foo {", "public void doThing() {"),
    ("class_start", "global with sharing class SecureService implements BaseService {", "global void doSharing() {"),
    ("class_start", "private virtual abstract class BaseHelper", "private String baseVar;"),
    ("class_start", "@isTest\nprivate class MyTestClass {", "@isTest static void testMethod() {"),
    ("class_start", "@RestResource(urlMapping='/Account/*/details/(.*)') global class Foo {", "String className = 'Foo';"),
    ("class_start", "public \n without \n sharing \n class \n Foo \n extends \n Bar {", "System.debug('class');"),
    ("class_start", "public enum Status {", "public void Status() {"),
    ("class_start", "global interface IService {", "global void IService() {"),

    # structural_boundaries
    ("structural_boundaries", "public class Foo {", "Integer x = 1;"),
    ("structural_boundaries", "trigger AccountTrigger on Account (before insert)", "AccountTrigger handler = new AccountTrigger();"),
    ("structural_boundaries", "public interface IService {", "String classVar = 'x';"),
    ("structural_boundaries", "public enum Status {", "Integer enumVal = 1;"),
    ("structural_boundaries", "final Integer x = 1;", "finalize();"),
    ("structural_boundaries", "transient String x;", "transientMethod();"),
    ("structural_boundaries", "class Foo implements Bar", "implementsMethod();"),
    ("structural_boundaries", "class Foo extends Bar", "extendsMethod();"),
    ("structural_boundaries", "public virtual class Foo", "virtualMethod();"),
    ("structural_boundaries", "public abstract class Foo", "abstractMethod();"),
    ("structural_boundaries", "return x;", "String returnVar = 'x';"),

    ("safety", "try {", "Integer x = 1;"),
    ("safety_bypasses", "without sharing", "with sharing"),
    ("high_risk_execution", "delete records;", "insert records;"),
    ("io", "[SELECT Id FROM Account]", "Integer x = 1;"),
    ("api", "global class Foo {", "public class Foo {"),
    ("state_mutation", "insert acc;", "System.debug('hi');"),
    ("dead_code", "// public class Foo", "// just a note"),
    ("doc", "/** Doc */", "// just a note"),
    ("test", "@isTest", "Integer x = 1;"),
    ("concurrency", "@future", "Integer x = 1;"),
    ("ui_framework", "PageReference pr = ApexPages.currentPage();", "Integer x = 1;"),
    ("globals", "UserInfo.getUserId();", "Integer x = 1;"),
    ("decorators", "@AuraEnabled", "Integer x = 1;"),
    ("generics", "List<Account> accs;", "Integer x = 1;"),
    ("comprehensions", "for (Account a : [SELECT Id FROM Account]) {", "for (Integer i=0;i<10;i++) {"),
    ("scientific", "Math.abs(x);", "Integer x = 1;"),
    ("reflection_metaprogramming", "Type.forName('Foo');", "Integer x = 1;"),
    ("import", "MyUtil.Helper();", "System.debug('x');"),
    ("ownership", "Author: Jane Doe", "Integer x = 1;"),
    ("planned_debt", "// TODO: fix this", "// done"),
    ("fragile_debt", "// HACK: workaround", "// clean"),
    ("spec_exposure", "[SPEC-123]", "// just a note"),
    ("ssr_boundaries", "RestRequest req = RestContext.request;", "Integer x = 1;"),
    ("events", "EventBus.publish(event);", "Integer x = 1;"),
    ("dependency_injection", "Injector.inject();", "Integer x = 1;"),
    ("memory_alloc", "new Account();", "Integer x = 1;"),
    ("telemetry", "Logger.info('msg');", "System.debug('msg');"),
    ("debug_prints", "System.debug('hi');", "Logger.info('hi');"),
    ("explicit_casts", "(String)obj", "(x)"),
    ("panics_and_aborts", "throw new MyException();", "Integer x = 1;"),
    ("bitwise_ops", "x = a & b;", "x = a && b;"),
    ("sync_locks", "[SELECT Id FROM Account FOR UPDATE]", "[SELECT Id FROM Account]"),
    ("immutability_locks", "final Integer MAX = 10;", "Integer x = 1;"),
    ("cleanup", "emptyRecycleBin();", "Integer x = 1;"),
    ("encapsulation", "private Integer x;", "public Integer x;"),
    ("listeners", "trigger MyTrigger on Account (before insert) {", "public class Foo {"),
    ("test_skip", "Test.setMock(HttpCalloutMock.class, mock);", "Integer x = 1;"),
]


@pytest.mark.parametrize("signature,positive,negative", _APEX_SIMPLE_CASES)
def test_apex_signature_positive_and_negative(signature, positive, negative):
    pattern = APEX_RULES[signature]
    assert pattern is not None, f"apex's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"apex {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"apex {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_apex_dependency_capture_extracts_type_and_namespace():
    pattern = APEX_RULES["_dependency_capture"]
    m = pattern.search("Type.forName('MyNamespace.MyClass')")
    assert m and m.group(1) == "MyNamespace.MyClass" and m.group(2) is None

    m2 = pattern.search("Type.forName('MyClass', 'MyNamespace')")
    assert m2 and m2.group(1) == "MyClass" and m2.group(2) == "MyNamespace"


def test_apex_func_start_excludes_structural_headers_and_control_keywords():
    """
    func_start's negative lookahead excludes class/interface/enum headers as
    well as control-flow keywords (if/for/while/switch/catch) that could
    otherwise look like a bare function-call-shaped signature line.
    """
    func_start = APEX_RULES["func_start"]
    for excluded_line in (
        "public class Foo {",
        "public interface Foo {",
        "public enum Foo {",
        "if (x) {",
        "for (;;) {",
        "while (x) {",
        "switch (x) {",
        "catch (Exception e) {",
    ):
        assert not func_start.search(excluded_line), f"func_start incorrectly matched {excluded_line!r}"


def test_apex_func_start_stacked_decorators_and_modifiers():
    """
    Real Apex methods often stack multiple annotations and modifiers before
    the signature (e.g. @AuraEnabled + @TestVisible + public static). The
    {0,5} bounded repetition groups must tolerate this and still anchor the
    capture on the actual method name.
    """
    func_start = APEX_RULES["func_start"]
    m = func_start.search("@AuraEnabled\n@TestVisible\npublic static void doThing() {")
    assert m and m.group(1) == "doThing"


def test_apex_func_start_trigger_form():
    func_start = APEX_RULES["func_start"]
    m = func_start.search("trigger MyTrigger on Account (before insert) {")
    assert m and m.group(2) == "MyTrigger"


def test_apex_class_start_sharing_modifiers():
    """
    with/without/inherited sharing are modifier keywords that can precede
    the class keyword and must not be captured as part of the class name.
    """
    class_start = APEX_RULES["class_start"]
    m = class_start.search("public with sharing class Foo {")
    assert m and m.group(1) == "Foo"

    m2 = class_start.search("public without sharing class Foo implements Bar {")
    assert m2 and m2.group(1) == "Foo"


def test_apex_func_start_vs_generics_no_false_collision():
    """
    Known ambiguity pattern from the issue template (already found in C#:
    deeply nested generic return types triggering catastrophic backtracking
    on func_start). Confirms apex's func_start/generics don't cross-fire on
    each other's realistic inputs, and that func_start survives a long
    generic-shaped type chain without pathological backtracking.
    """
    func_start = APEX_RULES["func_start"]
    generics = APEX_RULES["generics"]

    type_decl = "List<Account> accs = new List<Account>();"
    assert generics.search(type_decl)
    assert not func_start.search(type_decl)

    method_decl = "public void doThing() {"
    assert func_start.search(method_decl)
    assert not generics.search(method_decl)

    assert_redos_immune(func_start, "List<" + "Account, " * 50000, timeout_sec=3.0)


def test_apex_safety_bypasses_security_enforced_negative_lookahead():
    """
    safety_bypasses flags a raw Database.query(...) call as a sharing-bypass
    risk UNLESS it explicitly declares WITH SECURITY_ENFORCED -- the
    negative lookahead exists specifically to not flag the safe form.
    """
    safety_bypasses = APEX_RULES["safety_bypasses"]
    secure = "List<Account> accs = Database.query('SELECT Id FROM Account WITH SECURITY_ENFORCED');"
    insecure = "List<Account> accs = Database.query('SELECT Id FROM Account');"
    assert not safety_bypasses.search(secure), "Database.query with WITH SECURITY_ENFORCED must not be flagged"
    assert safety_bypasses.search(insecure), "a bare Database.query without SECURITY_ENFORCED must be flagged"


def test_apex_bitwise_ops_vs_branch_double_char_no_false_collision():
    """
    bitwise_ops uses lookaround to exclude doubled &&/|| (logical operators,
    branch's territory) from the single-character bitwise alternatives.
    A line using only && must fire branch, not bitwise_ops.
    """
    branch = APEX_RULES["branch"]
    bitwise_ops = APEX_RULES["bitwise_ops"]

    logical_only = "if (a && b) {"
    assert branch.search(logical_only)
    assert not bitwise_ops.search(logical_only), "pure && must not be misclassified as a bitwise op"

    single_amp = "x = a & b;"
    assert bitwise_ops.search(single_amp), "a genuine single & bitwise op must still match"


def test_apex_safety_bypasses_and_test_skip_suppresswarnings_intentional_double_classification():
    """
    Ambiguity sweep finding: `@SuppressWarnings` legitimately fires both
    safety_bypasses (silences a type-safety/lint warning) and test_skip
    (silences a test-quality warning) -- both true simultaneously, an
    intentional double-classification (Rule 1: semantic intent over keyword
    matching), not a false collision. See also the pre-existing leading-
    boundary regression test for this same annotation.
    """
    line = "@SuppressWarnings('PMD.ExcessiveParameterList')"
    assert APEX_RULES["safety_bypasses"].search(line)
    assert APEX_RULES["test_skip"].search(line)


def test_apex_lexical_family_block_comment_does_not_confuse_structural_rules():
    """
    Lexical-family audit: apex is `standard_block` (real /* */ block
    comments plus // line comments), unlike positional_anchored languages.
    Confirms a preceding block comment containing a structural keyword
    doesn't fool a structural rule at the raw-regex level (the real
    comment-stripping happens upstream in prism.py, not in these rules).
    """
    branch = APEX_RULES["branch"]
    stray = "/* not real code, just a note */\nif (x == 1) {"
    assert branch.search(stray), "branch should still see the real if-statement after a preceding block comment"


def test_apex_redos_immunity_sweep():
    """
    ReDoS immunity sweep across apex's rules with unbounded-looking
    quantifiers (adversarial "never closes" payloads at n=100000 against
    the rules whose quantifiers scale with input length).
    """
    assert_redos_immune(APEX_RULES["func_start"], "public static " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["class_start"], "public " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["args"], "void foo(" + "a," * 50000, timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["decorators"], "@" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["safety_bypasses"], "Database.query(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["globals"], "a" * 100000 + "__c.getInstance", timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["generics"], "List<" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["import"], "a" * 100000 + ".B", timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["dead_code"], "//" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["explicit_casts"], "(" + "A" * 100000, timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["memory_alloc"], "new " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["state_mutation"], "a" * 100000 + "=", timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["events"], "trigger a on " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["ownership"], "Author: " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["_dependency_capture"], "Type.forName(" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["comprehensions"], "for(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(APEX_RULES["high_risk_execution"], "'" + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert APEX_RULES["func_start"].search("public void doThing() {")
    assert APEX_RULES["class_start"].search("public class Foo {")
    assert APEX_RULES["safety_bypasses"].search("without sharing")
