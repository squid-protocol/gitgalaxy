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
The `high_risk_execution` contract (#2878, docs/high_risk_execution_rule_contract.md),
held across every edited corpus language in one place.

    A site that hands control out of the program's own semantics -- it ends or
    halts the process, runs text or another program as code, loads or rewrites
    executable code at run time, destroys a whole store the program does not
    own, or steps outside the runtime's protections -- in the primitive's own
    invocation or statement form.

The per-language strict suites keep their one positive/negative pair per
signal; this module pins the contract's corollaries -- exactly the shapes the
audit found the old rules disagreeing on:

  C1 five families, one owner each: (a) termination and traps, (b) running
     text or another program, (c) loading or rewriting code, (d) whole-store
     destruction, (e) protection escape. A form invisible to one language's
     rule but counted by its siblings joins (python `sys.exit`, go `panic(`,
     php `eval(`/`exit`, fortran `STOP`, c `exit(`).
  C2 the site is the invocation: a bound alias, a type or property reference,
     a landing point (`setjmp`) or a bare identifier is not one. Where an
     ordinary identifier can carry the name the rule anchors on the form
     (cpp/c/perl/php call parens, css `expression(`/`behavior:`, the js
     assignment sink and statement `debugger`, zig `panic(` not `.panic`,
     cobol/tcl hyphen guards, groovy's literal receiver); where it cannot and
     the crucible measures no collision the bare name is allowed (python
     `eval`, rust `panic!`, solidity `selfdestruct`).
  C3 a jump is nobody's signal: `goto`/`GO TO` leave csharp and fortran (as in
     c/go/perl/php); non-local abandonment (`longjmp`, `RETURN n`, `exit to
     top`) and control rewriting (`ALTER`, `ASSIGN`) stay.
  C4 deletion below the store is cleanup's question (#2843): one file, record
     or table (`os.remove`, `delete file`, `file delete -force`, `DELETE FROM`,
     `rm -rf <path>`) is not this signal; the root, a filesystem, a database,
     a table's contents or a contract is (`rm -rf /`, `mkfs`, `DROP DATABASE`,
     `TRUNCATE`, `emptyRecycleBin`, `selfdestruct`). The four shell-carrying
     languages agree on root-only.
  C5 not danger: debug or dialog output (`trace`, `alert`, `answer`), memory
     primitives (`memcpy`), workspace resets (`clear all`), a property that
     records an exit code, a compatibility pragma, a hard-coded ID, `undelete`.
  C6 one verified owner: apex `Database.query` is safety_bypasses' alone and
     `emptyRecycleBin` is this signal's alone (cleanup released it); `eval` in
     matlab/ruby/shell/tcl stays safety_bypasses' by ledger until that
     contract is stated (#2879).

Each language lists (positives, negatives). A positive must match at least
once; a negative must not match at all. `COUNTS` pins one-site-one-hit
shapes. `DUALS` pins tokens that fire a different signal, never this one.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strict_harness import assert_redos_immune  # type: ignore


def _rule(lang, signal="high_risk_execution"):
    return LANGUAGE_DEFINITIONS[lang]["rules"][signal]


# lang -> (positives, negatives)
CASES = {
    # --- C2: the site is the invocation --------------------------------------------
    "cpp": (
        ["exit(1);", "abort();", "system(cmd);", "std::terminate();", "longjmp(buf, 1);", "quick_exit(0);"],
        [
            "bool exit = false;",
            "exit = true;",
            "return exit;",
            "memcpy(dst, src, n);",
            "memset(p, 0, n);",
            "setjmp(buf)",
        ],
    ),
    "c": (
        ["system(0);", "fork();", "execvp(argv[0], argv);", "exit(1);", "abort();", "longjmp(env, 1);"],
        ['printf("Load system defaults");', "int exit_code = 0;", "setjmp(env)"],
    ),
    "perl": (
        ["system($cmd);", 'system "ls";', "exec @args;", "exit;", "exit 1;", "qx($cmd);", "my $out = `ls -la`;"],
        ["the current login system allows", "system's standard libraries", "my $x = $`;"],
    ),
    "php": (
        ["exec($cmd);", "passthru($cmd);", "eval($code);", "exit;", "exit(1);", "die('x');", "$out = `ls`;"],
        ["'SELECT COUNT(*) as `cnt` FROM `%s`'", "$x = $die;"],
    ),
    "groovy": (
        [
            '"ls".execute()',
            "['ls', '-l'].execute()",
            "System.exit(1)",
            "new GroovyShell().evaluate(src)",
            "Eval.me(src)",
        ],
        ["void execute() {", "api.getContent(id).execute().body()", "sql.execute('drop table x')"],
    ),
    "zig": (
        ['@panic("TODO");', "std.process.exit(1);", 'std.debug.panic("x", .{});', 'panic("stop");'],
        [
            "try sema.resolve(src, .panic);",
            "panic,",
            '.@"panic.sentinelMismatch",',
            "pub fn panic(msg: []const u8) noreturn {",
        ],
    ),
    "csharp": (
        ["Environment.Exit(1);", "Environment.FailFast(msg);", "Process.Start(cmd);", "Thread.Abort();"],
        ["goto done;", "var @goto = token;"],
    ),
    "cobol": (
        ["STOP RUN.", "ALTER DISPATCH-PARA TO PROCEED TO PROBE-BRANCH.", "CANCEL HELPER-MODULE."],
        ["ALTER-TEST-INIT.", "BEGIN-ALTER-PARAGRAPH.", "CANCEL-FLAG PIC X."],
    ),
    "tcl": (
        ["exec $cmd", "exit 1", "exit"],
        ["ports_deactivate_no-exec", "file delete -force $tmp"],
    ),
    "css": (
        ["x: expression(1);", "behavior: url(a.htc);", "-ms-filter: 'x';"],
        ["scroll-behavior: smooth;", "overscroll-behavior: none;", "--bs-behavior: 1;"],
    ),
    "javascript": (
        [
            "eval(code);",
            "el.innerHTML = html;",
            "el.innerHTML += html;",
            "document.write(html);",
            "debugger;",
            "process.exit(1);",
            "execSync(cmd);",
            "new Function(body)",
        ],
        [
            "export { Debugger } from './debugger';",
            "const html = el.innerHTML;",
            "async innerHTML(progress) {",
            "el.innerHTML === x",
            "alert('x');",
        ],
    ),
    "typescript": (
        ["eval(code);", "el.outerHTML = html;", "document.write(html);", "debugger;", "process.exit(1);"],
        ["import { Debugger } from './debugger';", "const html = el.outerHTML;", "alert('x');"],
    ),
    "java": (
        [
            "new ProcessBuilder(cmd);",
            "System.exit(1);",
            "Runtime.getRuntime().exec(cmd);",
            "Runtime.getRuntime().halt(1);",
        ],
        ["ProcessBuilder builder;", "Runtime.getRuntime().availableProcessors();"],
    ),
    "kotlin": (
        ["exitProcess(1)", "System.exit(1)", "Runtime.getRuntime().exec(cmd)"],
        ["Runtime.getRuntime().availableProcessors()", "Runtime.getRuntime().freeMemory()"],
    ),
    "dart": (
        ["exit(1);", "Process.killPid(pid);"],
        ["exitCode = 1;", "exitCode;"],
    ),
    # --- C1: the family's own forms join -------------------------------------------
    "python": (
        [
            "eval(code)",
            "exec(code)",
            "sys.exit(1)",
            "os._exit(1)",
            "os.abort()",
            "os.execvp(p, args)",
            "subprocess.run(cmd, shell=True)",
        ],
        ["sys.argv", "os.path.join(a, b)"],
    ),
    "embedded_python": (
        ["machine.reset()", "sys.exit(1)", "os._exit(1)", "eval(code)"],
        ["machine.Pin(2)"],
    ),
    "go": (
        ['panic("x")', "os.Exit(1)", 'log.Fatalf("x")', "exec.Command(name)", "syscall.Exec(p, a, e)"],
        ["recover()", "err != nil"],
    ),
    "fortran": (
        [
            "STOP",
            "ERROR STOP 1",
            "CALL EXIT(1)",
            "CALL SYSTEM('ls')",
            "CALL EXECUTE_COMMAND_LINE('ls')",
            "ASSIGN 100 TO LABEL",
            "RETURN 1",
        ],
        ["GOTO 100", "GO TO 100", "X = 1"],
    ),
    "rust": (
        ["panic!()", "unreachable!()", "todo!()", "process::exit(1);", "abort();", 'Command::new("ls")'],
        ["x.unwrap_or(0)", "let stop = 1;"],
    ),
    "haskell": (
        ["exitFailure", "exitWith (ExitFailure 1)", 'die "x"', 'error "unreachable"'],
        ['trace "x" y', "traceShow x y", "Debug.Trace.trace"],
    ),
    "objective-c": (
        ["exit(0);", "abort();", 'system("ls");', "[NSTask new]"],
        ["int system_id = 1;"],
    ),
    "solidity": (
        ["selfdestruct(payable(owner));", "target.delegatecall(data);"],
        ["require(x > 0);"],
    ),
    "sqlite": (
        ["DROP DATABASE foo;", ".shell ls", ".exit", "SELECT load_extension('x');"],
        ["PRAGMA legacy_alter_table=1;", "DROP TABLE t;", "DELETE FROM t;"],
    ),
    # --- C4: deletion below the store is cleanup's --------------------------------
    "shell": (
        [
            "rm -rf /",
            'rm -rf "/"',
            "rm -fr /*",
            "sudo apt install x",
            "mkfs.ext4 /dev/sda",
            "kill $pid",
            "kill -9 $pid",
            "chmod 777 x",
        ],
        [
            "rm -rf /tmp/build",
            'rm -rf "${dir}"',
            "rm -rf /usr/local/x",
            "kill -0 $pid",
            "kill -l",
            "--sudo-service-user",
        ],
    ),
    "makefile": (
        ["\trm -rf /", "\tsudo make install", "\tkill -9 $$PID", "\tkill $$PID"],
        ["\trm -rf $(BUILD)", "\trm -rf build/", "\tkill -0 $$PID"],
    ),
    "dockerfile": (
        ["RUN rm -rf /", "RUN eval $x", "RUN exec $x"],
        ["RUN rm -rf /var/lib/apt/lists/*", "RUN rm -rf $TMP"],
    ),
    "yaml": (
        ["run: rm -rf /", "eval :"],
        ["run: rm -rf build/", "run: rm -rf /home/runner/work"],
    ),
    "lua": (
        ["os.execute(cmd)", "os.exit(1)", "load(code)", "dofile(path)", "io.popen(cmd)"],
        ["os.remove(path)", "os.rename(a, b)"],
    ),
    "livecode": (
        ["do tScript", "quit", "exit to top", "get shell(tCommand)"],
        ["answer pPayload", 'ask "name?"', "delete file tPath", "delete folder tPath"],
    ),
    "abap": (
        ["TRUNCATE.", "SYSTEM-CALL x.", "GENERATE SUBROUTINE POOL t NAME p."],
        ["DELETE FROM ztab."],
    ),
    "apex": (
        ["Database.emptyRecycleBin(ids);", "System.abortJob(jobId);"],
        ["delete records;", "undelete records;", "String rid = '001000000000abc';", "Database.query(q);"],
    ),
    # --- C5: not danger --------------------------------------------------------------
    "matlab": (
        ["system('ls')", "dos('dir')", "exit", "keyboard"],
        ["clear all", "clc"],
    ),
}

COUNTS = [
    ("cpp", "exit = true; exit(1);", 1),
    ("c", 'printf("system defaults"); system(cmd);', 1),
    ("javascript", "el.innerHTML = x; const y = el.innerHTML;", 1),
    ("javascript", "debugger;\ndebugger;", 2),
    ("cobol", "ALTER-TEST-INIT.\n    ALTER A TO PROCEED TO B.", 1),
    ("php", "'`cnt` FROM `%s`'; $x = `ls`;", 1),
    ("ruby", "return if %w[x].include?($`)\n  a\n  b `ls`", 1),
    ("shell", "rm -rf / && rm -rf /tmp/x", 1),
    ("zig", 'pub fn panic(x: u8) void {}\npanic("x");', 1),
    ("groovy", 'api.get().execute().body(); "ls".execute()', 1),
]

# (lang, text, other_signal): a token the #2878 audit verified belongs to
# another signal alone -- it must never fire high_risk_execution.
DUALS = [
    ("apex", "Database.query(q)", "safety_bypasses"),
    ("matlab", "clear all", "cleanup"),
    ("sqlite", "DROP TABLE t;", "cleanup"),
    ("sqlite", "DELETE FROM t;", "cleanup"),
    ("yaml", "run: rm -rf build/", "cleanup"),
    ("csharp", "goto done;", None),
    ("fortran", "GOTO 100", None),
    ("haskell", 'trace "x" y', None),
    ("livecode", 'answer "hello"', None),
]


def test_apex_empty_recycle_bin_has_one_owner():
    """C6: the token left cleanup's rule; this signal owns it alone."""
    assert not _rule("apex", "cleanup").search("emptyRecycleBin(ids)")
    assert _rule("apex").search("emptyRecycleBin(ids)")


PAYLOADS = [
    "exit" + " " * 50000 + "(",
    "exit " * 20000,
    "system" + " " * 50000 + "(",
    "system " * 20000,
    "`" + "a" * 100000,
    "`" + "a" * 50000 + "\n" + "`" * 100,
    "$" + "`" * 50000,
    "rm -rf " * 20000,
    "rm" + " " * 50000 + "-rf /",
    "kill " * 20000,
    "kill" + " " * 50000 + "-0",
    "panic" + " " * 50000 + "(",
    "panic(" * 20000,
    "debugger" * 20000,
    ";" * 50000 + "debugger",
    ".innerHTML" + " " * 50000 + "=",
    ".innerHTML=" * 20000,
    "expression" + " " * 50000 + "(",
    "behavior" + " " * 50000 + ":",
    "scroll-behavior:" * 20000,
    "ALTER-" * 20000,
    "STOP" + " " * 50000 + "RUN",
    "no-exec-" * 20000,
    '".execute' + " " * 50000 + "(",
    "new" + " " * 50000 + "ProcessBuilder",
    "Runtime.getRuntime()." * 10000,
    "CALL " * 20000 + "EXIT",
    "EXECUTE_COMMAND_LINE" + " " * 50000 + "(",
    "error" + " " * 50000 + '"',
    "%x" * 20000,
    "\\" + "'" * 50000,
]


@pytest.mark.parametrize("lang", sorted(CASES))
def test_high_risk_execution_contract_positive_and_negative(lang):
    rule = _rule(lang)
    positives, negatives = CASES[lang]
    for text in positives:
        assert rule.search(text), f"{lang}: contract positive did not match: {text!r}"
    for text in negatives:
        hits = [m.group(0) for m in rule.finditer(text)]
        assert not hits, f"{lang}: contract negative matched {hits!r} in {text!r}"


@pytest.mark.parametrize("lang,text,expected", COUNTS)
def test_high_risk_execution_one_site_is_one_hit(lang, text, expected):
    hits = [m.group(0) for m in _rule(lang).finditer(text)]
    assert len(hits) == expected, f"{lang}: expected {expected} hits, got {hits!r}"


@pytest.mark.parametrize("lang,text,other_signal", DUALS)
def test_high_risk_execution_never_fires_on_another_owners_token(lang, text, other_signal):
    """C3/C4/C5/C6: a token verified to belong to another signal, or to no
    signal, must never fire high_risk_execution."""
    hits = [m.group(0) for m in _rule(lang).finditer(text)]
    assert not hits, f"{lang}: high_risk_execution fired on {text!r}: {hits!r}"
    if other_signal is not None:
        assert _rule(lang, other_signal).search(text), f"{lang}: expected {other_signal!r} to own {text!r}"


def test_high_risk_execution_markdown_has_no_rule():
    """Absence: markdown has no executable surface; the rule stays unset."""
    assert LANGUAGE_DEFINITIONS["markdown"]["rules"].get("high_risk_execution") is None


@pytest.mark.parametrize("lang", sorted(CASES))
def test_high_risk_execution_contract_rules_are_redos_immune(lang):
    rule = _rule(lang)
    for payload in PAYLOADS:
        assert_redos_immune(rule, payload, timeout_sec=3.0)
