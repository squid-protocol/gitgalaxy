import sys
from pathlib import Path

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

import pytest  # noqa: E402
from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_valid_dependency_match,
    assert_valid_match,
)

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402

APEX_RULES = LANGUAGE_DEFINITIONS["apex"]["rules"]


def test_apex_func_start():
    valid = [
        ("public static void TargetFunc()", "TargetFunc"),
        ("void TargetFunc();", "TargetFunc"),
        ("trigger TargetFunc on Account", "TargetFunc"),
        ("@isTest static void TargetFunc()", "TargetFunc"),
        ("@AuraEnabled(cacheable=true) public static List<Account> TargetFunc()", "TargetFunc"),
        ("@RemoteAction global static String TargetFunc(String id)", "TargetFunc"),
        ("public TargetFunc()", "TargetFunc"),
        ("private override void TargetFunc()", "TargetFunc"),
        ("public virtual void TargetFunc()", "TargetFunc"),
        ("public Map<String, List<String>> TargetFunc()", "TargetFunc"),
        ("public void TargetFunc   (", "TargetFunc"),
    ]
    invalid = [
        ("public class TargetFunc", None),
        ("public String myProp { get; set; }", None),
        ("public String myProp { get { return 'a'; } set; }", None),
        ("delete TargetFunc", None),
        ('String s = "public void TargetFunc() {";', None),
        ("// public void TargetFunc() {", None),
        ("Map<String, Integer> TargetFunc = new Map<String, Integer>();", None),
        ("if (TargetFunc() != null)", None),
    ]
    pathological = [
        ("@future(callout=true) public   static   void   TargetFunc   (", "TargetFunc"),
        (
            "@isTest(SeeAllData=true) @future(callout=true) @AuraEnabled(cacheable=true) public static void TargetFunc (",
            "TargetFunc",
        ),
        ("public   Map<String,   List<Map<Id, Account>>>   TargetFunc   (", "TargetFunc"),
        ("@isTest @TestVisible @AuraEnabled @future @RemoteAction public static void TargetFunc(", "TargetFunc"),
        ("public List<String>[][][] TargetFunc()", "TargetFunc"),
        ("trigger  TargetFunc  on  Account(", "TargetFunc"),
        ("global  static  Map<String,  List<Map<Id,  Map<String, Account>>>>  TargetFunc  (", "TargetFunc"),
        ("@ReadOnly @RemoteAction public   static   void   TargetFunc       (", "TargetFunc"),
        ("public   List   <   String   >   TargetFunc   (", "TargetFunc"),
        (
            "public with sharing void TargetFunc(",
            "TargetFunc",
        ),  # wait, with sharing is for classes, not methods. But as pathological parser test it's fine if it ignores it or passes it. Actually, `with sharing` is not an allowed modifier in func_start, so the regex won't match it if it's there. Oh, `(?:public...){0,5}` does not include `with sharing`. So this might fail if it's invalid syntax in Apex anyway.
    ]
    # Let me remove the "with sharing" method test, as it's invalid Apex and the regex shouldn't match it.
    pathological.pop()
    pathological.extend(
        [
            ("public override global static Map<String, Integer> TargetFunc(", "TargetFunc"),
            ("public   void   TargetFunc   (", "TargetFunc"),
            (
                "@AuraEnabled(cacheable=true) @RemoteAction @TestVisible @InvocableMethod(label='test' description='test') public static void TargetFunc(",
                "TargetFunc",
            ),
        ]
    )

    xfail_invalid = [
        ("TargetFunc(a, b);", None),  # Bare call ambiguity
    ]
    for payload, expected in valid + pathological:
        assert_valid_match(APEX_RULES["func_start"], payload, expected, "apex.func_start")
    for payload, _ in invalid:
        assert_invalid_no_match(APEX_RULES["func_start"], payload, "apex.func_start")
    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="Bare-call ambiguity"))


def test_apex_class_start():
    valid = [
        ("public class TargetEntity {", "TargetEntity"),
        ("class TargetEntity {", "TargetEntity"),
        ("global abstract class TargetEntity implements Base", "TargetEntity"),
        ("public interface TargetEntity", "TargetEntity"),
        ("public enum TargetEntity {", "TargetEntity"),
        ("public with sharing class TargetEntity {", "TargetEntity"),
        ("public without sharing class TargetEntity {", "TargetEntity"),
        ("public inherited sharing class TargetEntity {", "TargetEntity"),
    ]
    invalid = [
        ("TargetEntity obj = new TargetEntity();", None),
        ("delete TargetEntity;", None),
        ("public void classMethod()", None),
        ('String s = "public class TargetEntity {";', None),
        ("// public class TargetEntity {", None),
        (
            "public class TargetEntity;",
            None,
        ),  # Should match if the syntax permits it, but Apex doesn't use semi-colons for class decls
    ]
    pathological = [
        ("@isTest public   with   sharing   class   TargetEntity   extends   Base", "TargetEntity"),
        (
            "@RestResource(urlMapping='/api/*') global   with   sharing   class   TargetEntity   implements   Interface1,   Interface2",
            "TargetEntity",
        ),
        (
            "@isTest(SeeAllData=true) @TestVisible public   virtual   with   sharing   class   TargetEntity   extends   Base   implements   Int1,   Int2   {",
            "TargetEntity",
        ),
        (
            "global   abstract   without   sharing   class   TargetEntity   implements   Callable<String>   {",
            "TargetEntity",
        ),
        (
            "@JsonAccess(serializable='always' deserializable='always') public   class   TargetEntity   extends   Base<String, Integer>",
            "TargetEntity",
        ),
        ("public   interface   TargetEntity   extends   BaseInterface", "TargetEntity"),
        ("public   enum   TargetEntity   {", "TargetEntity"),
        ("@NamespaceAccessible @Deprecated public   inherited   sharing   class   TargetEntity", "TargetEntity"),
        ("@SuppressWarnings('PMD.AvoidGlobalModifier') global   class   TargetEntity   {", "TargetEntity"),
        ("public   class   TargetEntity   implements   Iterable<String>", "TargetEntity"),
    ]
    for payload, expected in valid + pathological:
        assert_valid_match(APEX_RULES["class_start"], payload, expected, "apex.class_start")
    for payload, _ in invalid:
        assert_invalid_no_match(APEX_RULES["class_start"], payload, "apex.class_start")


def test_apex_args():
    valid = [
        ("public void TargetFunc(String a, Integer b) {", "TargetFunc"),
        ("trigger TargetFunc on Account (before insert) {", "TargetFunc"),
        ("trigger TargetFunc on Account(before insert, after insert, before update) {", "TargetFunc"),
        ("public TargetFunc(Map<String, List<String>> a) {", "TargetFunc"),
        ("public void TargetFunc(Map<Id, Account> oldMap, List<Contact> newContacts) {", "TargetFunc"),
    ]
    invalid = [
        ("if (a == b) {", None),
        ('String s = "public void TargetFunc(String a) {";', None),
    ]
    pathological = [
        (
            "public   static   Map<Id, Account>   TargetFunc   (   List<Account> accounts,   Map<Id, Contact> contacts )",
            "TargetFunc",
        ),
        ("trigger   TargetFunc   on   Account   (   before   insert   )   {", "TargetFunc"),
        ("public   void   TargetFunc   (   Map<String, List<Map<Id, SObject>>> complexArg )", "TargetFunc"),
        ("public   void   TargetFunc   (   Map<String,   List<Map<Id,   SObject>>> complexArg )", "TargetFunc"),
        (
            "@isTest public static void TargetFunc(   List<String> arg1,   Map<Id, List<Contact>> arg2,   Set<Id> arg3 ) {",
            "TargetFunc",
        ),
        ("global static List<Id> TargetFunc(   List<Map<String, Object>> inputList ) {", "TargetFunc"),
        (
            "trigger TargetFunc on Account (   before insert,   before update,   before delete,   after insert,   after update,   after delete,   after undelete ) {",
            "TargetFunc",
        ),
        (
            "public TargetFunc(   String arg1,   Integer arg2,   Boolean arg3,   Id arg4,   Object arg5,   SObject arg6,   Blob arg7 ) {",
            "TargetFunc",
        ),
        ("public override void TargetFunc(   Map<Id, SObject> oldItems,   Map<Id, SObject> newItems ) {", "TargetFunc"),
        ("private void TargetFunc(   List<String>[   ]   [   ]   arg1 ) {", "TargetFunc"),
    ]
    xfail_invalid = [
        ("TargetFunc(a, b);", None),  # Bare call ambiguity
    ]
    for payload, expected in valid + pathological:
        assert_valid_match(APEX_RULES["args"], payload, expected, "apex.args")
    for payload, _ in invalid:
        assert_invalid_no_match(APEX_RULES["args"], payload, "apex.args")
    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="Bare-call ambiguity"))


def test_apex_dependency_capture():
    valid = [
        ("Type.forName('MyClass')", "MyClass"),
        ("Type.forName('namespace.MyClass')", "namespace.MyClass"),
        ("Type.forName('namespace', 'MyClass')", "MyClass"),  # Can also match 'namespace', but 'MyClass' is fine
        ("Type.forName ( 'MyClass' )", "MyClass"),
        ("Type.forName( 'ns' , 'Class' )", "Class"),
        ('Type.forName("MyClass")', "MyClass"),
    ]
    invalid = [
        ("Type.forName()", None),
        ("Type.forName(var)", None),
        ("Type.forName('ns', var)", None),
        ("String s = 'MyClass';", None),
    ]
    pathological = [
        ("Type   .   forName   (   'MyClass'   )", "MyClass"),
        ("Type.forName ( 'namespace' , 'MyClass' )", "MyClass"),
        ("Type.forName   (   'MyClass'   )", "MyClass"),
        ('Type.forName("namespace", "MyClass")', "MyClass"),
    ]
    xfail_invalid = [
        ("String s = 'Type.forName(\\'MyClass\\')';", None),  # Class 3 String literal bypass
        ("// Type.forName('MyClass')", None),  # Class 3 Comment bypass
        ("/* Type.forName('MyClass') */", None),  # Class 3 Comment bypass
    ]
    for payload, expected in valid + pathological:
        assert_valid_dependency_match(APEX_RULES["_dependency_capture"], payload, expected, "apex._dependency_capture")
    for payload, _ in invalid:
        assert_invalid_no_match(APEX_RULES["_dependency_capture"], payload, "apex._dependency_capture")
    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="Unshielded mode B bypass"))
