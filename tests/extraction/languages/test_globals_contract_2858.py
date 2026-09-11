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
The `globals` contract (#2858, docs/globals_rule_contract.md), held across
every corpus language in one place.

    One hit is a declaration of a binding with program lifetime -- file,
    module, class-static or process scope -- or a read or write of the
    process's ambient environment through its named handle, in a form an
    ordinary identifier cannot match.

The per-language strict suites keep their one positive/negative pair per
signal; this module pins the contract's corollaries -- exactly the shapes the
46-language audit found the old rules disagreeing on:

  C1 scope, not mutability: a program-scope constant counts (constness is
     immutability_locks' axis, #2772); a function-local binding never does --
     c's any-indentation `T x = v` counted every local with an initializer
     (2,771 crucible hits), lua's `arg` matched `local arg`, rust's
     `'static mut` was a lifetime, kotlin's bare `object` an anonymous
     object expression
  C2 a declaration or the ambient handle, not a reference: `CAF BIT14` is a
     reference to a constant; `os.environ`, `$PATH`, `getEnv`, `sy-subrc`
     are the named process-state handles
  C3 the ambiguity anchor: an everyday word fires only in its global form --
     shell's env names behind `$`/`${`/`NAME=` (the bare `TERM` in
     `trap : TERM` is a signal name), swift's `.shared`/`.default` behind a
     dot (bare `default` is a switch case), cobol's `COMMON` outside a
     hyphenated identifier, perl's `$$` not followed by a deref name,
     typescript's `globalThis.` (bare `global`/`self` are local names)
  C4 linkage and region headers are not state: a storage-class keyword on a
     prototype (`static void f();`, `extern "C"`), fortran `EXTERNAL`, an
     assembly `.data` section switch (#2805's WORKING-STORAGE shape)
  C5 one owner: process control through the ambient class is
     high_risk_execution's (`Environment.Exit`); `locals()` is nobody's
     global; the deliberate duals (kotlin `object`, fortran `COMMON`,
     jcl `SET`) are recorded, not retired
  C6 stated absence: html and markdown record None

Each language lists (positives, negatives). A positive must match at least
once; a negative must not match at all. `COUNTS` pins one-declaration-one-hit
shapes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strict_harness import assert_redos_immune  # type: ignore


def _rule(lang, signal="globals"):
    return LANGUAGE_DEFINITIONS[lang]["rules"][signal]


# lang -> (positives, negatives)
CASES = {
    # --- C1: scope, not mutability; a local never counts --------------------------
    "c": (
        [
            "int shared_region = 1;",
            "static const byte ops[6 + 6] = {",
            "extern int region;",
            "FILE *out;",
            "    static int counter = 0;",
            "struct config cfg;",
        ],
        [
            "    PyThreadState *tstate = _PyThreadState_GET();",
            "    int x = 5;",
            "static void helper(void);",
            "    static void helper(void) {",
            "int main(void) {",
            "typedef struct foo foo_t;",
        ],
    ),
    "cpp": (
        [
            "static const Type valid[] = {",
            "extern int region;",
            "thread_local int home;",
            "    static bool initialized = false;",
            "inline constexpr int N = 5;",
            "static HashMap<String, int> progress_total_steps;",
        ],
        [
            "static void _bind_methods();",
            'extern "C" {',
            "static_assert(sizeof(int) == 4);",
            "static inline void f() {",
            "auto y = static_cast<int>(x);",
        ],
    ),
    "objective-c": (
        ['static NSString *const kKey = @"k";', "extern HyperAccess * HTAccMgr;", "[NXApp mainWindow]"],
        ["extern char * WWW_nameOfFile(const char * name);", "static void foo(void);"],
    ),
    "rust": (
        [
            "static mut COUNTER: u32 = 0;",
            "const LIMIT: usize = 16;",
            'pub(crate) static NAME: &str = "x";',
            "let source_path = std::env::args().nth(1);",
            'env::var("HOME")',
        ],
        ["a: &'static mut A,", "const _: () = {", "const fn foo() -> u32 {", 'let x: &\'static str = "a";'],
    ),
    "go": (
        [
            "var gcphase uint32",
            "const gcBgMarkWorkerNodeRedZoneSize = 16",
            "var copyBufPool = sync.Pool{}",
            'os.Getenv("GOGC")',
            'os.LookupEnv("X")',
        ],
        # #2859: the middle arm now over-matches indented identifier lines on
        # purpose -- the `go_declaration_group` scope filter (exercised in
        # test_go_strict.py: a function-local reads 0, a group member reads N)
        # is what tells a body local from a group member. The bare-regex
        # negatives here are the column-0 non-declarations it still rejects.
        ["func main() {", "package main", 'import "os"'],
    ),
    "python": (
        ["    global state", 'os.environ["X"]', "sys.modules", 'globals()["f"]'],
        ["locals()", "global_config = 1", "    globalize(x)"],
    ),
    "embedded_python": (["global wdt", "sys.argv"], ["locals()", "global_x = 1"]),
    "fortran": (
        ["COMMON /SHARED/ REGION", "LOGICAL, SAVE :: done = .FALSE.", "      DATA sat85 /0.0235755574/"],
        ["LOGICAL, EXTERNAL :: wrf_dm_on_monitor", "      EXTERNAL HELPER", "DATA_X = 1"],
    ),
    "kotlin": (
        ["object Region {}", "actual object OkHttp {", "companion object {", "const val MAX = 1"],
        ["val r = object : Runnable {", "objectify(x)"],
    ),
    "lua": (
        ["return _G, arg, env", "_G.x = nil", "X = true", "local arg = arg or ARG"],
        ["local arg = {...}", "t.arg = 1", "arg = 1"],
    ),
    # --- C2: a declaration or the ambient handle, not a reference ----------------
    # #2859: `NAME ERASE` (erasable allocation) is the unambiguous shared-state
    # declaration; the flagword reference stays. Bare `COMMON` was a routine
    # label (`TCF COMMON`), now rejected; the `EQUALS`/`=` equate binds a fixed
    # value (a constant reference, C2 -- and a rosetta decoy), so it is not one.
    "agc_assembly": (
        ["ADS\tFLAGWRD7", "DSPCOUNT\tERASE"],
        ["CAF\tBIT14", "CS\tBIT10", "\tTCF\tCOMMON", "COMMON\t\tTC\tPHASCHNG", "SBIT1\t\tEQUALS\tBIT1", "CNTRCON\t\t=\tOCT50"],
    ),
    "haskell": (
        ["region :: IORef Int\nregion = unsafePerformIO (newIORef 0)", 'home <- getEnv "HOME"', "args <- getArgs"],
        ["x :: IORef Int", "let y = 5"],
    ),
    "perl": (
        ["print $$;", "$ENV{PATH}", "local $_;", "our @ISA = qw();", "if ($@) { die $@; }"],
        ["$$options{$param} = 1;", "my $x = $$self{OPTIONS};", "$_[2] = 1;"],
    ),
    # --- C3: the ambiguity anchor --------------------------------------------------
    "shell": (
        [': "$PATH"', "echo ${HOME}/x", "PATH=/usr/bin", 'export PATH="$PWD/bin"'],
        [
            "trap : TERM",
            'trap "" INT TERM QUIT',
            "# HOME verification",
            'echo "etcd must be in your PATH"',
            "sudo_path=${sudo_path#PATH=}",
        ],
    ),
    "swift": (
        [
            "UserDefaults.standard",
            "fileManager: FileManager = .default,",
            "UIApplication.shared",
            "static let shared = Foo()",
            "ProcessInfo.processInfo",
        ],
        ["default:", "case .default:", "let x = shared", "defaultValue = 5", "let store = standard"],
    ),
    "livecode": (
        ["global gRegion", 'if the platform is "win32" then', "put $ENV into tEnv", "the environment"],
        ["return it", "if it is empty then", "put 1 into x"],
    ),
    "cobol": (
        ["77 REGION-ITEM PIC 9 GLOBAL.", "01  EXTERNAL-DATA IS EXTERNAL."],
        ["GO TO COMMON-RETURN", "MOVE DB2-POLICY-COMMON TO CA-POLICY-COMMON", "10  COMMON-8-BIN PIC 9(8) BINARY."],
    ),
    "typescript": (
        [
            "window.setTimeout(f)",
            "process.env.CI",
            "globalThis.fetch",
            "document.createElement('a')",
            "import.meta.env.MODE",
        ],
        ["global.set(CommonFlags.Errored)", "const URL = self.URL || self.webkitURL;", "let global = <Global>element;"],
    ),
    "javascript": (
        ["window.setTimeout(f)", "process.env.CI", "globalThis.fetch", "navigator.userAgent"],
        ["global.set(CommonFlags.Errored)", "const self = this; self.x = 1;"],
    ),
    # --- C4: linkage and region headers are not state -----------------------------
    "assembly": (
        [
            "buf: resd 4",
            'msg db "x"',
            'helloworld:\t.ascii "Hello"',
            ".comm\t__blst_platform_cap,4",
            "next: .word 0",
            'msg:\n    .asciz "x"',  # #2859: label on its own line, directive on the next
            "FB_STRUCT:\n\tdw 5",
        ],
        [
            "\t.data",
            "section .data",
            "section .bss",
            "\tmov byte [rax], 1",
            "    dq expect",
            "    resb 1",
            "loop:\n    mov eax, 1",  # #2859: a label followed by an instruction is not storage
        ],
    ),
    # --- C5: one owner -------------------------------------------------------------
    "csharp": (
        [
            'Environment.GetEnvironmentVariable("PATH")',
            "Environment.MachineName;",
            "var region = ConfigurationManager;",
            "public static readonly int MAX = 1;",
            # #2859 (C1): any class-static field, not just public SCREAMING_CASE.
            "private static readonly SyntaxTree Dummy = new DummySyntaxTree();",
            "static int counter;",
        ],
        [
            "Environment.Exit(payload);",
            "Environment.FailFast(msg);",
            "static void Helper() {",  # a method is not a field
            "public static int Count { get; }",  # an auto-property is not a field
        ],
    ),
    # #2859 (C1): a class-static field is a program-scope binding whatever its
    # visibility; the `[=;]` terminator keeps methods and initializer blocks out.
    "java": (
        [
            "private static final Logger LOG = LoggerFactory.getLogger();",
            "static int counter;",
            "public static final String NAME = \"x\";",
            "private static final ThreadLocal<Hook> hook = new ThreadLocal<>();",
        ],
        ["static void helper() {", "static {", "int local = 5;"],
    ),
    # #2859 (C1): `static var` (mutable class-static) and column-0 `late final`.
    "dart": (
        ["static final int MAX = 1;", "static const x = 1;", "static var counter = 0;", "late final config = load();"],
        ["    var local = 5;", "int add(int a) => a;", "    late final x = 1;"],
    ),
    # #2859: `global NAME…` is the statement; `$global` is a variable read.
    "tcl": (
        ["global TRG", "global macports::registry.format", "::env(PATH)", "upvar #0 the_array arr"],
        ["set x $global", "if {$global} {}"],
    ),
}

# (lang, text, expected hits): one declaration is one hit; distinct named
# handles on one line are distinct hits (shell's `export PATH="$PWD/bin:$PATH"`
# writes PATH and reads PWD and PATH -- three couplings, three hits).
COUNTS = [
    ("cpp", "static thread_local int x = 0;", 1),
    ("cpp", "static inline constexpr int N = 5;", 1),
    ("c", "static const byte ops[6 + 6] = {", 1),
    ("c", "int x, y;", 1),
    ("rust", "static mut COUNTER: u32 = 0;", 1),
    ("swift", "let store = UserDefaults.standard", 1),
    ("cobol", "01  EXTERNAL-DATA IS EXTERNAL.", 1),
    ("perl", "$$compKeys{$_} or $$compKeys{$_} = [ ];", 2),
    ("shell", 'export PATH="$PWD/bin:$PATH"', 3),
    (
        "shell",
        'probe_globals() {\n    : "$1"\n    : "$PATH"\n    : "$HOME"\n}\nprobe_safety() {\n    trap : TERM\n}',
        2,
    ),
    ("csharp", "public static int ProbeRisk(int payload) {\n    Environment.Exit(payload);\n    return payload;\n}", 0),
    ("java", "private static final Logger LOG = getLog();", 1),  # #2859: one class-static field, one hit
    ("csharp", "private static readonly SyntaxTree Dummy = new();", 1),  # #2859
    ("agc_assembly", "DSPCOUNT\tERASE", 1),  # #2859: one erasable allocation, one hit
    ("assembly", 'msg:\n    .asciz "x"', 1),  # #2859: the two-line labeled-storage form is one hit
]

PAYLOADS = [
    "a" * 100000 + " = 1;",
    "static " * 20000,
    "static " + "a" * 100000 + "(",
    "extern " + "a b " * 30000,
    "\t" * 50000 + "static int x;",
    "the " * 20000,
    "$$" * 30000,
    "$" + "{" * 30000 + "PATH",
    "export " * 20000 + "PATH=",
    "label: " * 20000 + ".byte",
    "a" * 100000 + " db 1",
    "const " * 20000 + "X:",
    "global " * 20000,
    "object " * 20000,
    "." * 50000 + "default",
    "-COMMON" * 20000,
    "arg " * 30000,
    "var " * 20000 + "x",
]


@pytest.mark.parametrize("lang", sorted(CASES))
def test_globals_contract_positive_and_negative(lang):
    rule = _rule(lang)
    positives, negatives = CASES[lang]
    for text in positives:
        assert rule.search(text), f"{lang}: contract positive did not match: {text!r}"
    for text in negatives:
        hits = [m.group(0) for m in rule.finditer(text)]
        assert not hits, f"{lang}: contract negative matched {hits!r} in {text!r}"


@pytest.mark.parametrize("lang,text,expected", COUNTS)
def test_globals_one_declaration_is_one_hit(lang, text, expected):
    hits = [m.group(0) for m in _rule(lang).finditer(text)]
    assert len(hits) == expected, f"{lang}: expected {expected} hits, got {hits!r}"


def test_globals_one_owner_for_the_retired_duals():
    """C5: the token globals stopped counting is still its owner's hit (mass
    conserved, #2765's shape): csharp's process exit is high_risk_execution's,
    shell's trap handler is safety's, fortran's EXTERNAL and livecode's `it`
    are nobody's global."""
    assert _rule("csharp", "high_risk_execution").search("Environment.Exit(payload);")
    assert not _rule("csharp").search("Environment.Exit(payload);")
    assert _rule("shell", "safety").search("trap : TERM")
    assert not _rule("shell").search("trap : TERM")
    assert not _rule("fortran").search("      EXTERNAL HELPER")
    assert not _rule("livecode").search("return it")


def test_globals_deliberate_duals_are_kept():
    """C5: a token that is genuinely two constructs at once stays in both
    rules -- the fortran-COMMON shape (#2856's reading), not the io/branch
    one-owner case."""
    assert _rule("kotlin").search("object Region {}") and _rule("kotlin", "class_start").search("object Region {}")
    assert _rule("fortran").search("COMMON /SHARED/ REGION") and _rule("fortran", "safety_bypasses").search(
        "COMMON /SHARED/ REGION"
    )
    assert _rule("jcl").search("//SET1 SET COUNTER=1") and _rule("jcl", "state_mutation").search("//SET1 SET COUNTER=1")


def test_globals_region_headers_are_not_state():
    """C4: a region header opens the area globals live in; it is not a
    global (#2805 dropped cobol's WORKING-STORAGE SECTION; #2858 drops
    assembly's section switch)."""
    assert not _rule("cobol").search("WORKING-STORAGE SECTION.")
    assert not _rule("assembly").search("section .data")
    assert not _rule("assembly").search("\t.bss")


def test_globals_stated_absence_rows_carry_no_rule():
    """C6: html and markdown have no scoped-vs-global morphology (ledger
    html-2578-declarative-globals-state-mutation-morphology,
    markdown-lit-plane-morphology); the rule stays None."""
    assert LANGUAGE_DEFINITIONS["html"]["rules"].get("globals") is None
    assert LANGUAGE_DEFINITIONS["markdown"]["rules"].get("globals") is None


@pytest.mark.parametrize("lang", sorted(CASES))
def test_globals_contract_rules_are_redos_immune(lang):
    rule = _rule(lang)
    for payload in PAYLOADS:
        assert_redos_immune(rule, payload, timeout_sec=3.0)
