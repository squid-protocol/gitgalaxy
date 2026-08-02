import re

name_pat = r"(?:[^\W\d]\w*[=!?]?|\[\]=?|<<|>>|<=>|===?|!=|=~|!~|<=?|>=?|[+\-*/%&|^~`!])"
prefix_pat = r"(?:(?:[^\W\d]\w*(?:::[^\W\d]\w*)*\.|self\.)[ \t\n]*)?"
func_start = re.compile(
    r'^[ \t]*(?:def[ \t\n]+' + prefix_pat + r'|define_method[ \t\n]*\(?[ \t\n]*[:\'"]?)(' + name_pat + r')(?=[ \t\n]*[)(]|[\'"]?[ \t\n]*(?:\{|do)|[ \t\n]|$)',
    re.M,
)

funcs = [
    "def foo",
    "def self.class_method",
    "def Module::NestedClass.method",
    "def method_name?",
    "def destructive_method!",
    "def []",
    "def []=(key, val)",
    "def <<(item)",
    "def ==(other)",
    "def =~(other)",
    "def `(cmd)",
    "def foo = 'one-liner'",
    "def foo() = 42",
    "def \n crazy_whitespace \n ()",
    "def\ttabbed_method",
    "def ಠ_ಠ",
]

print("FUNC_START VALID")
for t in funcs:
    m = func_start.search(t)
    print(f"{t!r} -> {m.group(1) if m else None}")


class_start = re.compile(
    r"^[ \t]*(?:class|module)\s+([^\W\d]\w*(?:::[^\W\d]\w*)*|<<\s*self|<<\s*@[a-zA-Z_]\w*)(?:\s*<\s*([^\W\d]\w*(?:::[^\W\d]\w*)*))?",
    re.M,
)

classes = [
    "class Foo",
    "class Foo < Bar",
    "class Module::NestedClass",
    "class << self",
    "class << @object",
    "class Foo<Bar",
    "class \n Foo \n < \n Bar",
    "class Foo; end",
    "class  ಠ_ಠ < Object",
]

print("\nCLASS_START VALID")
for t in classes:
    m = class_start.search(t)
    print(f"{t!r} -> {m.group(1) if m else None}")


TOKEN = r"(?:[^()\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")"
args_pat = r"\bdef\s+" + prefix_pat + name_pat + r"\s*\(((?:" + TOKEN + r"|\((?:" + TOKEN + r"|\(" + TOKEN + r"*\))*\))*)\)|\bdo\s*\|([^|]*)\||\{\s*\|([^|]*)\||->\s*\(((?:" + TOKEN + r"|\((?:" + TOKEN + r"|\(" + TOKEN + r"*\))*\))*)\)"
args = re.compile(args_pat, re.M)

arg_cases = [
    "def foo()",
    "def foo(a)",
    "def foo(a, b)",
    "def foo(a = 1, b = 'str')",
    "def foo(*args)",
    "def foo(**kwargs)",
    "def foo(&block)",
    "def foo(a, b=1, *c, d:, e: 2, **f, &g)",
    "def foo(...)",
    "def foo(*, **)",
    "def foo(a, \n b)",
    "def foo(a = { x: 1, y: 'foo(bar)' })",
    "def foo(a = lambda { |x| x.foo })",
    "def foo(a = %w[one two three])",
    "def foo(a: 1, b: 'def foo')",
    'def foo(a="\\\"")',
    'def foo(a = ")", b = 2)',
    "def foo(a = <<-EOF\n  multiline\nEOF\n)",
]

print("\nARGS VALID")
for t in arg_cases:
    m = args.search(t)
    # The groups will be:
    # 1: def args
    # 2: do block args
    # 3: brace block args
    # 4: lambda args
    res = m.group(1) or m.group(2) or m.group(3) or m.group(4) if m else None
    print(f"{t!r} -> {res}")


dependency_capture = re.compile(
    r"\b(?:require|require_relative|load|autoload)\b[ \t\n(]*(?:['\"]([^'\"]+)['\"]|%[qQwW]\W([^ \t\n\W]+)\W)|\b(?:include|extend)\b[ \t\n(]+([^\W\d]\w*(?:::[^\W\d]\w*)*)",
    re.M,
)

deps = [
    "require 'json'",
    'require "net/http"',
    "require_relative 'my_lib'",
    "include Enumerable",
    "extend ActiveSupport::Concern",
    "require('openssl')",
    "require %q(foo)",
    "require %Q{bar}",
    "require %W[baz].first",
    "require \n 'foo'",
    "include(Foo::Bar)",
    "require 'foo' # comment",
    'require_relative"foo"',
]

print("\nDEPENDENCY_CAPTURE VALID")
for t in deps:
    m = dependency_capture.search(t)
    res = m.group(1) or m.group(2) or m.group(3) if m else None
    print(f"{t!r} -> {res}")
