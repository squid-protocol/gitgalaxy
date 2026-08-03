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
        ("trigger TargetFunc on Account", "TargetFunc"),
        ("@isTest static void TargetFunc()", "TargetFunc"),
        ("@AuraEnabled(cacheable=true) public static List<Account> TargetFunc()", "TargetFunc"),
        ("@RemoteAction global static String TargetFunc(String id)", "TargetFunc"),
        ("public TargetFunc()", "TargetFunc"),
        ("private override void TargetFunc()", "TargetFunc"),
        ("public virtual void TargetFunc()", "TargetFunc"),
        ("public Map<String, List<String>> TargetFunc()", "TargetFunc"),
        ("public void TargetFunc \n (", "TargetFunc"),
    ]
    invalid = [
        ("public class TargetFunc", None),
        ("delete TargetFunc", None),
        ("String s = \"public void TargetFunc() {\";", None),
        ("// public void TargetFunc() {", None),
        ("Map<String, Integer> TargetFunc = new Map<String, Integer>();", None),
        ("if (TargetFunc() != null)", None),
    ]
    pathological = [
        ("@future(callout=true)\npublic \n static \n void \n TargetFunc \n (", "TargetFunc"),
        ("@isTest(SeeAllData=true)\n@future(callout=true)\n@AuraEnabled(cacheable=true)\npublic\nstatic\nvoid\nTargetFunc\n(", "TargetFunc"),
        ("public \n Map<String, \n List<Map<Id, Account>>> \n TargetFunc \n (", "TargetFunc"),
        ("@isTest\n@TestVisible\n@AuraEnabled\n@future\n@RemoteAction\npublic static void TargetFunc(", "TargetFunc"),
        ("public List<String>[][][] TargetFunc()", "TargetFunc"),
        ("trigger\n\tTargetFunc\n\ton\n\tAccount(", "TargetFunc"),
        ("global\n\tstatic\n\tMap<String,\n\tList<Map<Id,\n\tMap<String, Account>>>>\n\tTargetFunc\n\t(", "TargetFunc"),
        ("@ReadOnly\n@RemoteAction\npublic \n static \n void \n TargetFunc \n \n \n (", "TargetFunc"),
        ("public \n List \n < \n String \n > \n TargetFunc \n (", "TargetFunc"),
        ("public\nwith\nsharing\nvoid\nTargetFunc(", "TargetFunc"), # wait, with sharing is for classes, not methods. But as pathological parser test it's fine if it ignores it or passes it. Actually, `with sharing` is not an allowed modifier in func_start, so the regex won't match it if it's there. Oh, `(?:public...){0,5}` does not include `with sharing`. So this might fail if it's invalid syntax in Apex anyway.
    ]
    # Let me remove the "with sharing" method test, as it's invalid Apex and the regex shouldn't match it.
    pathological.pop()
    pathological.extend([
        ("public\noverride\nglobal\nstatic\nMap<String, Integer>\nTargetFunc(", "TargetFunc"),
        ("public \n void \n TargetFunc \n (", "TargetFunc"),
        ("@AuraEnabled(cacheable=true)\n@RemoteAction\n@TestVisible\n@InvocableMethod(label='test' description='test')\npublic static void TargetFunc(", "TargetFunc"),
    ])

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
        ("String s = \"public class TargetEntity {\";", None),
        ("// public class TargetEntity {", None),
        ("public class TargetEntity;", None),  # Should match if the syntax permits it, but Apex doesn't use semi-colons for class decls
    ]
    pathological = [
        ("@isTest\npublic \n with \n sharing \n class \n TargetEntity \n extends \n Base", "TargetEntity"),
        ("@RestResource(urlMapping='/api/*')\nglobal \n with \n sharing \n class \n TargetEntity \n implements \n Interface1, \n Interface2", "TargetEntity"),
        ("@isTest(SeeAllData=true)\n@TestVisible\npublic \n virtual \n with \n sharing \n class \n TargetEntity \n extends \n Base \n implements \n Int1, \n Int2 \n {", "TargetEntity"),
        ("global \n abstract \n without \n sharing \n class \n TargetEntity \n implements \n Callable<String> \n {", "TargetEntity"),
        ("@JsonAccess(serializable='always' deserializable='always')\npublic \n class \n TargetEntity \n extends \n Base<String, Integer>", "TargetEntity"),
        ("public \n interface \n TargetEntity \n extends \n BaseInterface", "TargetEntity"),
        ("public \n enum \n TargetEntity \n {", "TargetEntity"),
        ("@NamespaceAccessible\n@Deprecated\npublic \n inherited \n sharing \n class \n TargetEntity", "TargetEntity"),
        ("@SuppressWarnings('PMD.AvoidGlobalModifier')\nglobal \n class \n TargetEntity \n {", "TargetEntity"),
        ("public \n class \n TargetEntity \n implements \n Iterable<String>", "TargetEntity"),
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
        ("String s = \"public void TargetFunc(String a) {\";", None),
    ]
    pathological = [
        ("public \n static \n Map<Id, Account> \n TargetFunc \n (\n  List<Account> accounts,\n  Map<Id, Contact> contacts\n)", "TargetFunc"),
        ("trigger \n TargetFunc \n on \n Account \n ( \n before \n insert \n ) \n {", "TargetFunc"),
        ("public \n void \n TargetFunc \n (\n  Map<String, List<Map<Id, SObject>>> complexArg\n)", "TargetFunc"),
        ("public \n void \n TargetFunc \n (\n  Map<String,\n  List<Map<Id,\n  SObject>>> complexArg\n)", "TargetFunc"),
        ("@isTest\npublic static void TargetFunc(\n  List<String> arg1,\n  Map<Id, List<Contact>> arg2,\n  Set<Id> arg3\n) {", "TargetFunc"),
        ("global\nstatic\nList<Id>\nTargetFunc(\n  List<Map<String, Object>> inputList\n) {", "TargetFunc"),
        ("trigger TargetFunc on Account (\n  before insert,\n  before update,\n  before delete,\n  after insert,\n  after update,\n  after delete,\n  after undelete\n) {", "TargetFunc"),
        ("public TargetFunc(\n  String arg1,\n  Integer arg2,\n  Boolean arg3,\n  Id arg4,\n  Object arg5,\n  SObject arg6,\n  Blob arg7\n) {", "TargetFunc"),
        ("public override void TargetFunc(\n  Map<Id, SObject> oldItems,\n  Map<Id, SObject> newItems\n) {", "TargetFunc"),
        ("private void TargetFunc(\n  List<String>[\n  ]\n  [\n  ]\n  arg1\n) {", "TargetFunc"),
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
        ("Type.forName('namespace', 'MyClass')", "MyClass"), # Can also match 'namespace', but 'MyClass' is fine
        ("Type.forName ( 'MyClass' )", "MyClass"),
        ("Type.forName(\n'ns'\n,\n'Class'\n)", "Class"),
        ("Type.forName(\"MyClass\")", "MyClass"),
    ]
    invalid = [
        ("Type.forName()", None),
        ("Type.forName(var)", None),
        ("Type.forName('ns', var)", None),
        ("String s = 'MyClass';", None),
    ]
    pathological = [
        ("Type \n . \n forName \n ( \n 'MyClass' \n )", "MyClass"),
        ("Type.forName\n(\n'namespace'\n,\n'MyClass'\n)", "MyClass"),
        ("Type.forName   (   'MyClass'   )", "MyClass"),
        ("Type.forName(\"namespace\", \"MyClass\")", "MyClass"),
    ]
    xfail_invalid = [
        ("String s = 'Type.forName(\\'MyClass\\')';", None), # Class 3 String literal bypass
        ("// Type.forName('MyClass')", None), # Class 3 Comment bypass
        ("/* Type.forName('MyClass') */", None), # Class 3 Comment bypass
    ]
    for payload, expected in valid + pathological:
        assert_valid_dependency_match(APEX_RULES["_dependency_capture"], payload, expected, "apex._dependency_capture")
    for payload, _ in invalid:
        assert_invalid_no_match(APEX_RULES["_dependency_capture"], payload, "apex._dependency_capture")
    for payload, _ in xfail_invalid:
        pytest.param(payload, None, marks=pytest.mark.xfail(reason="Unshielded mode B bypass"))
