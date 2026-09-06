# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
The `state_mutation` contract (#2765, docs/state_mutation_rule_contract.md), held
across every corpus language in one place.

    One hit is a statement that writes a new value into state that already
    exists: a re-assignment (plain, compound or ++), an in-place update of a
    container or structure, or a write through a mutable cell or reference.

The per-language strict suites keep their one positive/negative pair per signal;
this module pins the contract's corollaries, which are exactly the shapes the
46-language audit found the old rules disagreeing on:

  1. a declaration is not a write, even a mutable one, even with an initializer
  2. a type, modifier or annotation naming mutable state is not a write
  3. a read, a bind, a cast is not a write
  4. one statement is one hit, and a token another rule owns for the same
     construct is not a second signal

Each language lists (positives, negatives). A positive must match at least once;
a negative must not match at all. `COUNTS` pins corollary 4 (exact hit counts).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strict_harness import assert_redos_immune  # type: ignore


def _rule(lang):
    return LANGUAGE_DEFINITIONS[lang]["rules"]["state_mutation"]


# lang -> (positives, negatives)
CASES = {
    # --- corollary 1: a declaration is not a write ---------------------------------
    "c": (
        [
            "x = 5;",
            "*result = NULL;",
            "p->next = q;",
            "arr[i] = 0;",
            "items++;",
            "items--;",
            "for (i = 0; i < n; i++) {",
            "x += 2;",
        ],
        [
            "int x = 5;",
            "PyThreadState *tstate = _PyThreadState_GET();",
            'const char *note = "text";',
            'fprintf(fp, "------------\\n");',
            "if (x == 5)",
            "if (a != b)",
            "x <= y",
            "static const Type valid[] = {",
        ],
    ),
    "cpp": (
        ["x = 5;", "ip += 3;", "N = N->next();", "std::swap(a, b);", "v.push_back(x);", "*p = &x;"],
        [
            "int *p = &x;",
            "mutable int held;",
            "std::move(items);",
            "std::atomic<int> counter;",
            "if (a && b) {",
            "auto& r = x;",
        ],
    ),
    "objective-c": (
        ["counter = 1;", "self.value = 1;", "items++;", '[self setName:@"x"];'],
        ['NSString *note = @"text";', "NXRun * r = theRuns->runs;", "if (x == y)", "[self doSomething];"],
    ),
    "go": (
        [
            "items = 1",
            "x, y = y, x",
            "w.closeAfterReply = true",
            "n++",
            "ch <- v",
            "delete(m, k)",
            "atomic.AddInt32(&n, 1)",
            "x, _ = f()",
        ],
        ['note := "text"', "var x = 5", "_ = shape", "if x == 5 {", "v := <-ch"],
    ),
    "rust": (
        ["x = 2;", "*p = 5;", "count += 1;", "v.push(x);", "cell.borrow_mut();", "self.len = 0;"],
        [
            "let mut x = 1;",
            "let x = 1;",
            "fn f(&mut self, v: &mut Vec<u8>) {",
            "Cell::new(0)",
            "RefCell::new(0)",
            "AtomicUsize::new(0)",
            '#[cfg(feature = "x")]',
            "match x { A => 1, }",
        ],
    ),
    "kotlin": (
        ["count = 1", "this.field = value", "field = maxRequests", "list.add(x)", "i++"],
        [
            "var count = 0",
            "val count = 0",
            "val list: MutableList<Int> = mutableListOf()",
            "AtomicInteger(0)",
            "if (a == b)",
            "foo(\n    a = 1,\n    b = 2,\n)",
        ],
    ),
    "scala": (
        ["count = 1", "isErroneous = true", "buf += x", "map.put(k, v)"],
        [
            "var count = 0",
            "val count = 0",
            "import scala.collection.mutable.ArrayBuffer",
            "new AtomicInteger(0)",
            "x => x + 1",
            "case Foo => 1",
        ],
    ),
    "swift": (
        ["count = 1", "self.result = result", "headers[name] = value", "items.append(x)", "total += 1"],
        [
            "var count = 0",
            "let count = 0",
            "func f(_ x: inout Int)",
            "mutating func bump() {",
            "@State private var x = 0",
            "if a == b {",
            "foo(a: 1, b: 2)",
        ],
    ),
    "zig": (
        ["x = 1;", "i += 1;", "ptr.* = 5;", "self.len = 0;", "map_index &= mask;"],
        ["var x: i32 = 0;", "const x: i32 = 0;", "_ = self;", "if (a == b)", ".{ .a = 1 }"],
    ),
    "javascript": (
        [
            "x = 1;",
            "this.parser = parser;",
            "obj.count += 1;",
            "arr[i] = v;",
            "n++;",
            "list.push(x);",
            "this.setState({ a: 1 });",
            "module.exports = f;",
        ],
        [
            "let first = items;",
            "var second = items;",
            "const x = 1;",
            "const te = this.elements;",
            "this.register(fn);",
            "if (a === b) {",
            "<Foo bar={x} />",
            "const f = (x) => x + 1;",
        ],
    ),
    "typescript": (
        ["x = 1;", "ctx.contextualType = Type.v128;", "count++;", "myMap.set(1, 2);", "myRef.current = value;"],
        [
            "let x = 1;",
            "const x: number = 1;",
            'this.error("x");',
            "let module = this.module;",
            "type X = { a: number };",
            "if (a == b) {",
        ],
    ),
    "java": (
        [
            "this.count = 5;",
            "result = convert(result);",
            "i++;",
            "list.add(x);",
            "map.put(k, v);",
            "counter.incrementAndGet();",
        ],
        [
            "volatile int held;",
            "AtomicInteger counter;",
            "private final AtomicBoolean used = new AtomicBoolean();",
            "public void setResourceLoader(ResourceLoader r) {",
            "@Setter",
            "int x = 5;",
            "if (a == b)",
            "x -> x + 1",
        ],
    ),
    "csharp": (
        [
            "myField = 5;",
            "_termState = saveTerm;",
            "x = a << 2;",
            "list.Add(x);",
            "Mutate(ref items);",
            "Mutate(out items);",
            "count++;",
        ],
        [
            "int x = 5;",
            "var x = 5;",
            "public int X { get; set; }",
            "volatile int held;",
            "void F(ref int x, out int y) {",
            "F(out var result);",
            "oldSolution =>",
            "if (x == 5)",
        ],
    ),
    "dart": (
        ["_hasBeenAnnotated = true;", "index -= 1;", "list.add(1);", "setState(() {});", "notifyListeners();"],
        ['final note = "text";', "var x = 1;", "int x = 1;", "list.length;", "if (a == b)"],
    ),
    "groovy": (
        ["count = count + 1", "x = 5", "versionCode = 1", "list.add(x)", "n++"],
        ["def x = 5", "String s = 'x'", "count == expected", "@Setter", "x =~ /re/"],
    ),
    "lua": (
        ["x = 5", "counter = 1", "count = count + 1", "_G.x = nil", "t.field = 1", "table.insert(t, v)"],
        ["local a = {}", "local count = 0", "if x == 5 then", "  entry_type = core.MENU_ENTRY,", "table.concat(t)"],
    ),
    "perl": (
        [
            "push @arr, 1;",
            "push(@stack, $items);",
            "pop(@stack);",
            "$x = 1;",
            "$h{a} = 1;",
            "$obj->{name} = 'x';",
            "$n++;",
            "delete $h{a};",
        ],
        [
            'my $note = "text";',
            "my $self = shift;",
            "my ($items) = @_;",
            "our $VERSION = '1';",
            "if ($x == 1) { }",
            'DelCheck => q{"Can\'t delete"},',
        ],
    ),
    "php": (
        ["$x = 5;", "$this->count = 1;", "$tax_query[] = array();", "$n++;", "array_push($a, 1);"],
        ["global $wpdb;", "if ($a == $b)", "$a === $b", "foreach ($arr as $k => $v)", "function f(&$x) {"],
    ),
    "ruby": (
        [
            "@x = 1",
            "@@count += 1",
            "arr.push(1)",
            "items.pop",
            "arr << x",
            'list << "s"',
            "hash.merge!(other)",
            "@memo ||= compute",
        ],
        ["class << self", "def delete", "<<~EOS", "x = 1", "arr.length"],
    ),
    "haskell": (
        ["modifyIORef ref (+1)", "writeIORef ref 0", "writeTVar tv x", "putMVar mv x", "modify (+1)"],
        [
            "counter :: IORef Int",
            "region :: IORef Int",
            "x <- readIORef ref",
            "d <- defaultUserDataDir",
            "newtype App = App (StateT S IO ())",
            "modifyIORefs",
        ],
    ),
    "python": (
        ["self.value = 1", "items.append(1)", "global counter"],
        ["print(self.value)", "x == 1"],
    ),
    # --- corollary 4: a token another rule owns is not a second signal ----------------
    "dockerfile": (
        ["RUN export COUNTER=1", 'export NOTE="text"'],
        ["ENV REGION=1", "ENV HOME_ZONE 2", "ARG SHAPE"],
    ),
    "matlab": (
        ["x = 5;", "data(1) = value;", "s.a.b = 5;"],
        ["clear scratch", "clearvars leftover", "if x == 1"],
    ),
    "m4": (
        ["pushdef([foo], [bar])", "m4_append([NOTE], [x])"],
        ["popdef([foo])", "m4_popdef([foo])", "AC_SUBST(FOO)"],
    ),
    "apex": (
        ["insert acc;", "update accounts;", "counter = 1;", "count++;", "acct.Description += 'x';", "list.add(x);"],
        ["delete acc;", "undelete acc;", "conn.clear();", "Integer x = 5;", "System.debug('hi');", "if (a == b)"],
    ),
    "sqlite": (
        [
            "UPDATE users SET status = 'inactive' WHERE id = 1;",
            "ALTER TABLE t RENAME TO u;",
            "REPLACE INTO t VALUES (1);",
            "INSERT INTO t VALUES (1) ON CONFLICT DO UPDATE SET x = 1;",
        ],
        [
            "SELECT * FROM users;",
            "project TEXT NOT NULL REFERENCES projects(project) ON UPDATE CASCADE,",
            "CREATE TABLE t (x SET);",
        ],
    ),
    # --- fallback family / anchoring fixes -------------------------------------------
    "cobol": (
        ["MOVE X TO Y.", "COMPUTE COUNTER-B = 2.", "ADD 1 TO X.", "STRING A DELIMITED BY SIZE INTO B."],
        ["END-STRING", "END-ADD.", "END-COMPUTE", "REPLACE ==A== BY ==B==.", "IF X > 0"],
    ),
    "assembly": (
        ["\txchg eax, ebx", "\tinc eax", "loop1: dec ecx", "    xadd [mem], eax"],
        ['.include "cpm65.inc"', "include 'LIB\\FASMARM.INC'", "\tmov eax, ebx"],
    ),
    "ada": (
        ["X := 5;", "Count := 1;", "Rec.Field := 2;", "Arr (I) := 3;"],
        ["X : Integer := 5;", "X : constant Integer := 5;", "X = 5", 'Note : String := "text";'],
    ),
    "fortran": (
        ["X = 1", "myvar = 5", "mystruct%field = 1", "      COUNTER = 1", "DO I = 1, N", "10    X = 2"],
        ["INTEGER :: X = 1", "CALL foo(x)", "KIND = 5", "LEN = 10", "      CALL foo(UNIT = 10)"],
    ),
    "abap": (
        [
            "MOVE lv_a TO lv_b.",
            "lv_note = 'text'.",
            "rv_bool = abap_true.",
            "lr_item = get_item( iv_path ).",
            "<ls_step>-flag = abap_false.",
        ],
        [
            "DATA lv_x TYPE i.",
            "DATA(lv_x) = get( ).",
            "IF lv_a = lv_b.",
            "    iv_path = lv_path",
            "    ii_log  = ii_log ).",
            "WHERE field = value",
        ],
    ),
    "shell": (
        ["x=5", "x+=1", "let x=1", "arr[0]=1"],
        ["declare x=1", "echo x", "echo x+=1", '[ "$a" == "$b" ]'],
    ),
    "yacc": (
        ["x = 5;", "$$ = $1;", "counter++;"],
        ["if (x == 5) { }", "char *ret = malloc(n);", "%define api.pure full"],
    ),
    "solidity": (
        ["balances[msg.sender] = amount;", "stack.push(items);", "count++;", "total += 1;"],
        [
            "payable(items);",
            "balances[msg.sender] == amount;",
            "uint256 proposalId = getProposalId(x);",
            "mapping(address account => bool) hasRole;",
        ],
    ),
    "scheme": (
        ["(set! x 5)", "(vector-set! v 0 2)", "(set-box! b 1)"],
        ["(+ x 1)", "(set-car! p 1)", "(define x 1)"],
    ),
}

# corollary 4: one statement is one hit
COUNTS = [
    ("sqlite", "UPDATE users SET status = 'inactive' WHERE id = 1;", 1),
    ("sqlite", "ALTER TABLE new_changes RENAME TO changes;", 1),
    ("go", "s = append(s, x)", 1),
    ("go", "for i = 0; i < n; i++ {", 1),  # go's paren-less for header is not a statement start; the `i++` is
    ("c", "for (i = 0; i < n; i++) {", 2),
    ("csharp", "Reduce(ref a, ref b, ref c);", 3),
    ("perl", "my $self = shift;", 0),
    ("dockerfile", "ENV REGION=1\nENV HOME_ZONE=2\nRUN export COUNTER=1", 1),
]

PAYLOADS = [
    "a" * 100000 + " =",
    "x = 1,\n" * 20000,
    "(" * 60000,
    "[" * 60000,
    "." * 60000,
    "-" * 100000,
    "a." * 50000,
    "$a" + "{x}" * 20000 + " =",
    "\t" * 50000 + "inc",
]


@pytest.mark.parametrize("lang", sorted(CASES))
def test_state_mutation_contract_positive_and_negative(lang):
    rule = _rule(lang)
    positives, negatives = CASES[lang]
    for text in positives:
        assert rule.search(text), f"{lang}: contract positive did not match: {text!r}"
    for text in negatives:
        hits = [m.group(0) for m in rule.finditer(text)]
        assert not hits, f"{lang}: contract negative matched {hits!r} in {text!r}"


@pytest.mark.parametrize("lang,text,expected", COUNTS)
def test_state_mutation_one_statement_is_one_hit(lang, text, expected):
    assert len(_rule(lang).findall(text)) == expected


@pytest.mark.parametrize("lang", sorted(CASES))
def test_state_mutation_contract_rules_are_redos_immune(lang):
    rule = _rule(lang)
    for payload in PAYLOADS:
        assert_redos_immune(rule, payload, timeout_sec=3.0)
