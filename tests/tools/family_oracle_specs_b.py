"""Tree-sitter oracle specs for Ruby, PHP, Lua and shell (bash), batch B of the keyword-family validity tool (#8863).

Import this module after `family_oracle` / `family_oracle_ts` are on sys.path; it fills `family_oracle_ts.SPECS` and registers a
`BOracle` for each language so `family_oracle.score(db, src, "ruby")` works unchanged. `Spec` itself is the repository class: nothing
here edits it. What the repository `TreeSitterOracle` cannot express (receiver-aware callee matching, per-language operator and
statement rules, per-language doc and parameter reading) lives in `BOracle`, a subclass that overrides `index` and `count`.

Callee patterns (see `match`): "puts" = receiverless call (or Kernel.puts); "File.read" = exact receiver.method (namespace prefixes ok);
"Time." = any method on that receiver; "*.read" = that method on any receiver. Names are lowercased for PHP (case-insensitive language).
Every callee list is the author's reading of the family contract in gitgalaxy/standards/signal_contracts.py, justified per line.
"""

from __future__ import annotations

import collections
import re

import family_oracle_ts as fts
from family_oracle_ts import Spec, TreeSitterOracle, _fs, _text

# --------------------------------------------------------------------------------------------------------------------------
# Ruby (grammar: ruby). Functions: method, singleton_method. Calls: `call` (receiver/method fields).
# --------------------------------------------------------------------------------------------------------------------------
_RUBY_CALLS = {
    # Kernel#puts/print/p/pp/printf/putc write to stdout, warn to stderr: ad-hoc console output. $stdout/$stderr/STDOUT/STDERR are the console
    # objects themselves (a writer variable such as `io.puts` is NOT listed: that is a writer, not the console).
    "print": (
        "puts",
        "print",
        "p",
        "pp",
        "printf",
        "putc",
        "warn",
        "$stdout.puts",
        "$stdout.print",
        "$stdout.printf",
        "$stdout.write",
        "$stderr.puts",
        "$stderr.print",
        "$stderr.printf",
        "$stderr.write",
        "STDOUT.puts",
        "STDOUT.print",
        "STDOUT.printf",
        "STDOUT.write",
        "STDERR.puts",
        "STDERR.print",
        "STDERR.printf",
        "STDERR.write",
    ),
    # Kernel#sleep is the only core sleep. Timeout.timeout is a deadline, not a delay (not listed).
    "sleep": ("sleep",),
    # =~ and !~ are binary nodes, a regex literal is its own node type; here: Regexp constructors and Regexp/String/MatchData#match(?).
    "regex": ("Regexp.new", "Regexp.compile", "Regexp.union", "*.match", "*.match?"),
    # Time/Date/DateTime are the stdlib calendar classes (any call on them: now, at, parse, mktime, strptime, today, new ...);
    # strftime/iso8601/httpdate/rfc2822/xmlschema are the formatting calls; Process.clock_gettime is the monotonic clock; Benchmark times blocks.
    "time": (
        "Time.",
        "Date.",
        "DateTime.",
        "Process.clock_gettime",
        "Benchmark.",
        "*.strftime",
        "*.iso8601",
        "*.httpdate",
        "*.rfc2822",
        "*.xmlschema",
    ),
    # File/IO/Dir/FileUtils/Tempfile are the stdlib file facilities; Net::HTTP/Socket/TCPSocket/TCPServer/UDPSocket/URI.open the network;
    # Kernel#open/gets/readlines/readline read; read/write/readlines/binread/binwrite/open on any receiver (Pathname, IO, File) are data movement.
    # Excluded: File.exist?/File.join/File.basename (metadata and path string work, not data movement), close (cleanup's).
    "io": (
        "File.read",
        "File.write",
        "File.open",
        "File.binread",
        "File.binwrite",
        "File.readlines",
        "File.foreach",
        "File.delete",
        "File.unlink",
        "File.rename",
        "File.new",
        "File.copy_stream",
        "File.symlink",
        "File.chmod",
        "File.truncate",
        "IO.",
        "Dir.glob",
        "Dir.entries",
        "Dir.children",
        "Dir.each_child",
        "Dir.mkdir",
        "Dir.rmdir",
        "Dir.foreach",
        "Dir.[]",
        "FileUtils.",
        "Tempfile.",
        "Net::HTTP.",
        "Socket.",
        "TCPSocket.",
        "TCPServer.",
        "UDPSocket.",
        "UNIXSocket.",
        "URI.open",
        "open",
        "gets",
        "readlines",
        "readline",
        "*.read",
        "*.write",
        "*.readlines",
        "*.binread",
        "*.binwrite",
        "*.open",
        "*.mkpath",
        "*.rmtree",
        "*.readpartial",
    ),
    # raise/fail raise; throw is non-local exit; exit/exit!/abort end the process (Kernel and Process forms).
    "bailout": ("raise", "fail", "throw", "exit", "exit!", "abort", "Process.exit", "Process.exit!", "Process.abort"),
}

# --------------------------------------------------------------------------------------------------------------------------
# PHP (grammar: php). Functions: function_definition, method_declaration. Names are lowercased.
# --------------------------------------------------------------------------------------------------------------------------
_PHP_CALLS = {
    # var_dump/print_r/var_export/debug_zval_dump/printf/vprintf are stdout dumps; `echo` and `print` are statement nodes (print_node_types).
    # print_r/var_export with a true 2nd argument return a string and are excluded in BOracle._php_returns_string.
    "print": ("var_dump", "print_r", "var_export", "debug_zval_dump", "printf", "vprintf"),
    # sleep family of core PHP.
    "sleep": ("sleep", "usleep", "time_nanosleep", "time_sleep_until"),
    # PCRE preg_* evaluate; mb_ereg* are the multibyte regex functions. preg_quote only escapes (not listed).
    "regex": (
        "preg_match",
        "preg_match_all",
        "preg_replace",
        "preg_replace_callback",
        "preg_replace_callback_array",
        "preg_split",
        "preg_grep",
        "mb_ereg",
        "mb_eregi",
        "mb_ereg_replace",
        "mb_eregi_replace",
        "mb_split",
        "mb_ereg_match",
    ),
    # Core clock/calendar functions, plus the DateTime family constructed with `new` or a static call (datetime::createfromformat).
    "time": (
        "time",
        "date",
        "gmdate",
        "mktime",
        "gmmktime",
        "strtotime",
        "microtime",
        "hrtime",
        "idate",
        "getdate",
        "localtime",
        "checkdate",
        "strftime",
        "gmstrftime",
        "date_default_timezone_set",
        "date_default_timezone_get",
        "date_create",
        "date_create_immutable",
        "date_diff",
        "date_add",
        "date_sub",
        "date_parse",
        "date_parse_from_format",
        "date_format",
        "date_interval_create_from_date_string",
        "timezone_open",
        "datetime",
        "datetimeimmutable",
        "dateinterval",
        "datetimezone",
        "dateperiod",
        "datetime.",
        "datetimeimmutable.",
        "dateinterval.",
        "datetimezone.",
    ),
    # Core file, stream, socket and curl functions move data to/from the outside; mysqli/PDO/pg are external data stores.
    # Excluded: fclose (cleanup's), file_exists/is_file/is_dir (metadata), include/require (import's), header (response metadata).
    "io": (
        "file_get_contents",
        "file_put_contents",
        "fopen",
        "fread",
        "fwrite",
        "fputs",
        "fgets",
        "fgetc",
        "fgetcsv",
        "fputcsv",
        "fscanf",
        "file",
        "readfile",
        "fpassthru",
        "unlink",
        "rename",
        "copy",
        "mkdir",
        "rmdir",
        "touch",
        "tempnam",
        "tmpfile",
        "scandir",
        "glob",
        "opendir",
        "readdir",
        "fsockopen",
        "pfsockopen",
        "stream_socket_client",
        "stream_socket_server",
        "stream_get_contents",
        "curl_exec",
        "move_uploaded_file",
        "readline",
        "mysqli_connect",
        "mysqli_query",
        "pg_connect",
        "pg_query",
        "pdo",
        "mysqli",
    ),
    # die()/exit() end the process (die is a function node, exit an exit_statement); throw is a throw_expression node.
    "bailout": ("die", "exit"),
}

# --------------------------------------------------------------------------------------------------------------------------
# Lua (grammar: lua). Functions: function_declaration (name field), function_definition bound to a name. Calls: function_call.
# --------------------------------------------------------------------------------------------------------------------------
_LUA_CALLS = {
    # print and io.write go to the default output; io.stdout/io.stderr:write are the console handles.
    "print": ("print", "io.write", "io.stdout.write", "io.stderr.write"),
    # Lua's standard library has no sleep; these are the near-universal host-library names (LuaSocket, OpenResty, luaposix).
    # loader.delay(us) is the FreeBSD boot-loader Lua API's blocking delay; os.execute("sleep N") is handled in BOracle.
    "sleep": (
        "socket.sleep",
        "ngx.sleep",
        "posix.sleep",
        "posix.usleep",
        "posix.unistd.sleep",
        "posix.unistd.usleep",
        "loader.delay",
    ),
    # Lua patterns are not POSIX regular expressions; string.find/match/gmatch/gsub are the pattern-matching operators (the closest analogue),
    # lrexlib (rex_pcre / rex.) and the `re` module are real regex. Method-form :find is scored only with a string-literal first argument.
    "regex": (
        "string.find",
        "string.match",
        "string.gmatch",
        "string.gsub",
        "*.match",
        "*.gmatch",
        "*.gsub",
        "rex_pcre.",
        "rex_posix.",
        "rex.",
        "re.match",
        "re.find",
        "re.gsub",
    ),
    # os.time/date/clock/difftime are the entire standard clock and calendar library.
    "time": ("os.time", "os.date", "os.clock", "os.difftime"),
    # io.open/lines/read/input/output/popen/tmpfile open streams; os.remove/rename/tmpname touch files; file handles are read/written with
    # :read/:write/:lines/:seek. `require`/`dofile` are imports (not listed), io.write is the console (print above).
    "io": (
        "io.open",
        "io.lines",
        "io.read",
        "io.input",
        "io.output",
        "io.popen",
        "io.tmpfile",
        "os.remove",
        "os.rename",
        "os.tmpname",
        "loadfile",
        "*.read",
        "*.write",
        "*.lines",
        "*.seek",
    ),
    # error() raises; os.exit ends the process. assert is a conditional check (not listed).
    "bailout": ("error", "os.exit"),
}

# --------------------------------------------------------------------------------------------------------------------------
# Shell (grammar: bash). Functions: function_definition. Calls: `command` nodes (command_name word); callee = basename of the command word.
# --------------------------------------------------------------------------------------------------------------------------
_SH_CALLS = {
    # echo/printf (and print in ksh/zsh) write to the terminal; BOracle drops them when piped on, captured in $(...) or redirected to a file.
    "print": ("echo", "printf", "print"),
    # The only sleeping commands: sleep(1) and the obsolete usleep.
    "sleep": ("sleep", "usleep"),
    # grep family / sed / awk evaluate regular expressions; `[[ x =~ re ]]` is a binary_expression handled in BOracle. fgrep and grep -F are
    # fixed-string but share the command, so they are not separated.
    "regex": ("grep", "egrep", "sed", "awk", "gawk", "mawk", "rg", "pcregrep"),
    # date prints/formats clocks, time (keyword/command) measures, hwclock/uptime/cal read the clock; $EPOCHSECONDS-style variables in BOracle.
    "time": ("date", "time", "hwclock", "uptime", "cal"),
    # Commands whose job is moving file/network data: cat cp mv rm rmdir mkdir touch ln tee dd (files), curl wget scp rsync nc ncat (network),
    # read/mapfile/readarray read stdin or fds, mktemp creates a file. File redirections (> >> <) are added in BOracle.
    "io": (
        "cat",
        "cp",
        "mv",
        "rm",
        "rmdir",
        "mkdir",
        "touch",
        "ln",
        "tee",
        "dd",
        "curl",
        "wget",
        "scp",
        "rsync",
        "nc",
        "ncat",
        "read",
        "mapfile",
        "readarray",
        "mktemp",
    ),
    # exit ends the shell process. return only leaves the function; kill/die are not language constructs.
    "bailout": ("exit",),
}

_RUBY = Spec(
    "ruby",
    (".rb", ".rake", ".gemspec", ".ru"),
    _fs("method", "singleton_method"),
    _fs("block", "do_block", "lambda"),
    # arms: if/unless/elsif/while/until/for/when/in_clause/ternary/modifiers; `else` handled in BOracle (arm of if/case only);
    # rescue/ensure are handlers, excluded by branch_rule_contract.md corollary 1.
    _fs(
        "if",
        "unless",
        "elsif",
        "while",
        "until",
        "for",
        "when",
        "in_clause",
        "conditional",
        "if_modifier",
        "unless_modifier",
        "while_modifier",
        "until_modifier",
    ),
    _fs(),
    _fs("call"),
    _RUBY_CALLS,
    regex_node_types=_fs("regex"),
    skip_families=_fs("struct_decorators"),  # Ruby has no annotation/attribute syntax on declarations
)
_PHP = Spec(
    "php",
    (".php", ".inc", ".phtml"),
    _fs("function_definition", "method_declaration"),
    _fs("anonymous_function", "arrow_function"),
    _fs(
        "if_statement",
        "else_if_clause",
        "else_clause",
        "for_statement",
        "foreach_statement",
        "while_statement",
        "do_statement",
        "case_statement",
        "default_statement",
        "match_conditional_expression",
        "match_default_expression",
        "conditional_expression",
    ),
    _fs("throw_expression", "exit_statement"),
    _fs(
        "function_call_expression",
        "member_call_expression",
        "nullsafe_member_call_expression",
        "scoped_call_expression",
        "object_creation_expression",
    ),
    _PHP_CALLS,
)
_LUA = Spec(
    "lua",
    (".lua",),
    _fs("function_declaration"),
    _fs("function_definition"),
    _fs("if_statement", "elseif_statement", "else_statement", "for_statement", "while_statement", "repeat_statement"),
    _fs(),
    _fs("function_call"),
    _LUA_CALLS,
    skip_families=_fs(
        "struct_decorators"
    ),  # Lua has no annotation syntax (LuaCATS ---@ lines are doc comments, scored as doc)
)
_SH = Spec(
    "bash",
    (".sh", ".bash", ".ksh", ".zsh"),
    _fs("function_definition"),
    _fs(),
    _fs(
        "if_statement",
        "elif_clause",
        "else_clause",
        "for_statement",
        "c_style_for_statement",
        "while_statement",
        "case_item",
        "ternary_expression",
    ),
    _fs(),
    _fs("command"),
    _SH_CALLS,
    # Shell has no anonymous callables, no annotation syntax and no doc convention in the language (a comment block above a function is a
    # comment; shdoc-style tags are a third-party generator, not scored).
    skip_families=_fs("struct_closures", "struct_decorators", "is_documented"),
)

# --------------------------------------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------------------------------------
_SIMPLE_RECV = {
    "ruby": {
        "constant",
        "scope_resolution",
        "identifier",
        "instance_variable",
        "class_variable",
        "global_variable",
        "self",
    },
    "php": {"variable_name", "name", "qualified_name", "relative_scope"},
    "lua": {"identifier", "dot_index_expression"},
}
_SH_SKIP_PREFIX = {"sudo", "command", "builtin", "nohup", "env", "nice", "exec", "xargs", "time"}
_SH_TIME_VARS = {"EPOCHSECONDS", "EPOCHREALTIME", "SECONDS"}
_SH_STD_DEV = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty", "/dev/stdin", "/dev/fd"}


def match(recv: str | None, name: str, pats: tuple[str, ...]) -> str | None:
    r = (recv or "").lstrip(".")
    for p in pats:
        if p.startswith("*."):
            if recv is not None and name == p[2:]:
                return p
        elif p.endswith("."):
            c = p[:-1]
            if recv is not None and (r == c or r.endswith("." + c)):
                return p
        elif "." in p:
            c, m = p.rsplit(".", 1)
            if name == m and recv is not None and (r == c or r.endswith("." + c)):
                return p
        elif name == p and (recv is None or recv == "Kernel"):
            return p
    return None


def _op(node) -> str:
    o = node.child_by_field_name("operator")
    if o is not None:
        return _text(o)
    for c in node.children:
        if not c.is_named:
            return c.type
    return ""


def _recv_text(lang: str, rn) -> str:
    if rn is None:
        return None  # type: ignore[return-value]
    t = _text(rn).replace("::", ".").replace("->", ".").replace("?.", ".").replace(":", ".")
    if rn.type in _SIMPLE_RECV[lang]:
        t = "".join(t.split())
        return t.lstrip("\\.").replace("\\", ".")
    return "()"


def _contiguous_comments(node, comment_types=("comment",)) -> list:
    """Comment nodes directly above `node` with no blank line between them, nearest first."""
    out = []
    prev = node.prev_sibling
    want = node.start_point[0] - 1
    while prev is not None and prev.type in comment_types and prev.end_point[0] >= want:
        out.append(prev)
        want = prev.start_point[0] - 1
        prev = prev.prev_sibling
    return out


class BOracle(TreeSitterOracle):
    """Per-language oracle for ruby / php / lua / bash."""

    def __init__(self, spec: Spec) -> None:
        super().__init__(spec)
        self.lang = spec.ts_name
        self.stmt_parents = {
            "ruby": {
                "body_statement",
                "block_body",
                "program",
                "then",
                "else",
                "do",
                "begin",
                "ensure",
                "rescue",
                "when",
                "elsif",
                "if",
                "unless",
            },
        }.get(self.lang, set())

    # ---------------------------------------------------------------- index
    def _names(self, node) -> list[str]:
        t = node.type
        nm = node.child_by_field_name("name")
        s = _text(nm)
        if not s:
            return []
        if self.lang == "ruby":
            names = [s]
            obj = node.child_by_field_name("object")
            if t == "singleton_method":
                names += ["self." + s, _text(obj) + "." + s]
            return names
        if self.lang == "lua":
            seg = re.split(r"[.:]", s)[-1]
            return list({s, seg, s.replace(":", ".")})
        return [s]

    def index(self, text: str) -> dict:
        import tree_sitter_language_pack

        if self._parser is None:
            self._parser = tree_sitter_language_pack.get_parser(self.spec.ts_name)
        root = self._parser.parse(text.encode("utf-8", "surrogateescape")).root_node
        index: dict = {}
        stack = [root]
        while stack:
            node = stack.pop()
            if node.type in self.spec.func_types:
                lines = {node.start_point[0] + 1}
                nm = node.child_by_field_name("name")
                if nm is not None:
                    lines.add(nm.start_point[0] + 1)
                for c in _contiguous_comments(node):  # a scan may key a function by its doc-comment's first line
                    lines.add(c.start_point[0] + 1)
                for name in self._names(node):
                    for ln in lines:
                        index.setdefault((name, ln), node)
            elif self.lang == "lua" and node.type == "function_definition":
                bound, bound_lines = self._lua_bound(node)
                for nm2 in {bound, re.split(r"[.:]", bound)[-1]} if bound else ():
                    for ln in bound_lines:
                        index.setdefault((nm2, ln), node)
            stack.extend(node.children)
        return index

    def _lua_bound(self, node) -> tuple[str, list[int]]:
        """`M.f = function() end`, `local f = function`, `{ f = function }`: the name a function literal is bound to."""
        e = node.parent  # expression_list
        p = e.parent if e is not None else None
        name = ""
        if p is not None and p.type == "assignment_statement" and e.type == "expression_list":
            vl = next((c for c in p.children if c.type == "variable_list"), None)
            if vl is not None and vl.named_child_count == 1:
                name = _text(vl.named_children[0])
        elif e is not None and e.type == "field":
            name = _text(e.child_by_field_name("name"))
            p = e
        if not name or p is None:
            return "", []
        lines = sorted(
            {
                node.start_point[0] + 1,
                p.start_point[0] + 1,
                (p.parent.start_point[0] + 1) if p.parent is not None else 1,
            }
        )
        return name, lines

    # ---------------------------------------------------------------- parameters, docs
    def _args(self, fn) -> int:
        if self.lang == "bash":
            return self._sh_args(fn)
        params = fn.child_by_field_name("parameters")
        if params is None:
            return 0
        return sum(1 for c in params.named_children if "comment" not in c.type)

    def _sh_args(self, fn) -> int:
        """Shell has no parameter list: the documented stand-in is the highest positional reference ($1..$n, ${n}) or $@ $* $# (args_rule_contract.md)."""
        best = 0
        stack = [fn.child_by_field_name("body") or fn]
        while stack:
            n = stack.pop()
            if n.type == "function_definition" and n is not fn:
                continue  # an inner function's positionals are its own
            stack.extend(n.children)
            if n.type == "variable_name" and n.text.isdigit() and n.text != b"0":
                best = max(best, int(n.text))
            elif n.type == "special_variable_name" and n.text in (b"@", b"*", b"#"):
                best = max(best, 1)
        return best

    def _documented(self, fn) -> bool:
        com = _contiguous_comments(fn)
        if not com:
            return False
        if self.lang == "php":
            return _text(com[0]).lstrip().startswith("/**")  # PHPDoc
        if self.lang == "lua":
            # LuaDoc / LDoc / LuaCATS: a `---` line (or `--[[--` block) in the comment block directly above
            return any(_text(c).lstrip().startswith(("---", "--[[--")) for c in com)
        if self.lang == "ruby":
            # YARD and RDoc: the comment block directly above `def` documents it (RDoc takes any such block; magic and linter comments are not docs)
            real = [
                c
                for c in com
                if not re.match(r"#\s*(rubocop:|typed:|frozen_string_literal|encoding:|sorbet:|:nodoc:)", _text(c))
            ]
            return bool(real)
        return False

    # ---------------------------------------------------------------- callee extraction
    def _callee(self, node) -> tuple[str | None, str] | None:
        t, lang = node.type, self.lang
        if lang == "ruby":
            m = node.child_by_field_name("method")
            if m is None:
                return None
            r = node.child_by_field_name("receiver")
            return (_recv_text(lang, r) if r is not None else None, _text(m))
        if lang == "php":
            if t == "function_call_expression":
                f = node.child_by_field_name("function")
                if f is None or f.type not in ("name", "qualified_name"):
                    return None
                return None, re.split(r"\\", _text(f))[-1].lower()
            if t in ("member_call_expression", "nullsafe_member_call_expression"):
                o, nm = node.child_by_field_name("object"), node.child_by_field_name("name")
                return _recv_text(lang, o).lower(), _text(nm).lower()
            if t == "scoped_call_expression":
                s, nm = node.child_by_field_name("scope"), node.child_by_field_name("name")
                return re.split(r"\\", _text(s))[-1].lower(), _text(nm).lower()
            if t == "object_creation_expression":
                for c in node.named_children:
                    if c.type in ("name", "qualified_name"):
                        return None, re.split(r"\\", _text(c))[-1].lower()
            return None
        if lang == "lua":
            f = node.child_by_field_name("name")
            if f is None:
                return None
            if f.type == "identifier":
                return None, _text(f)
            if f.type == "dot_index_expression":
                return _recv_text(lang, f.child_by_field_name("table")), _text(f.child_by_field_name("field"))
            if f.type == "method_index_expression":
                return _recv_text(lang, f.child_by_field_name("table")), _text(f.child_by_field_name("method"))
            return None
        if lang == "bash":
            cn = node.child_by_field_name("name")
            if cn is None:
                return None
            words = [cn] + [c for c in node.named_children if c is not cn and c.type == "word"]
            i = 0
            nm = _text(words[0]).rsplit("/", 1)[-1]
            while nm in _SH_SKIP_PREFIX and nm not in ("time",) and i + 1 < len(words):
                i += 1
                nm = _text(words[i]).rsplit("/", 1)[-1]
            return None, nm
        return None

    # ---------------------------------------------------------------- shell redirect and pipeline context
    def _sh_console_ok(self, cmd) -> bool:
        """echo/printf is console output unless piped on, captured, or written to a file (that is data flow, not a debug print)."""
        p = cmd.parent
        while p is not None and p.type in ("redirected_statement", "pipeline", "negated_command", "list"):
            if p.type == "pipeline" and cmd is not p.named_children[-1]:
                return False
            if p.type == "redirected_statement":
                for r in p.children:
                    if r.type == "file_redirect" and self._sh_file_dest(r) is not None:
                        return False
                    if r.type == "heredoc_redirect":
                        return False
            cmd, p = p, p.parent
        a = cmd.parent
        while a is not None:
            if a.type in ("command_substitution", "process_substitution"):
                return False
            if a.type == "function_definition":
                break
            a = a.parent
        return True

    def _sh_file_dest(self, r) -> str | None:
        """The file a file_redirect reads or writes, or None for fd duplication, stderr redirection and the standard devices."""
        op = _op(r)
        dest = next(
            (
                c
                for c in r.named_children
                if c.type in ("word", "string", "concatenation", "simple_expansion", "expansion")
            ),
            None,
        )
        if dest is None or ">&" in op or "<&" in op:
            return None
        fd = next((c for c in r.named_children if c.type == "file_descriptor"), None)
        if fd is not None and _text(fd) == "2":
            return None
        d = _text(dest).strip("\"'")
        if d in _SH_STD_DEV or d.startswith("/dev/fd"):
            return None
        return d

    # ---------------------------------------------------------------- count
    def _is_stmt_append(self, node) -> bool:
        """Ruby `a << x` / `a << x << y` used as a statement: the array/string append idiom, whose value is discarded (a shift would be pointless)."""
        n = node
        while (
            n.parent is not None
            and n.parent.type == "binary"
            and _op(n.parent) == "<<"
            and n.parent.child_by_field_name("left") is n
        ):
            n = n.parent
        return n.parent is not None and n.parent.type in self.stmt_parents

    def count(self, fn):
        spec, lang = self.spec, self.lang
        n: collections.Counter = collections.Counter()
        tokens: dict = collections.defaultdict(collections.Counter)

        def add(key: str, tok: str | None = None) -> None:
            n[key] += 1
            if tok:
                tokens[key][tok] += 1

        stack = list(fn.children)
        while stack:
            node = stack.pop()
            stack.extend(node.children)
            if not node.is_named:
                continue
            t = node.type
            if t in spec.branch_types:
                add("branch", t)
            if t in spec.closure_types and not (
                lang == "ruby" and t == "block" and node.parent is not None and node.parent.type == "lambda"
            ):
                add(
                    "closures", t
                )  # a `->(x) { }` literal is one closure: its `lambda` node, not also its `block` child
            if t in spec.throw_types:
                add("bailout", t)
            if t in spec.regex_node_types:
                add("regex", "regex-literal")
            # ---- operators
            op = ""
            if t in (
                "binary",
                "binary_expression",
                "operator_assignment",
                "augmented_assignment_expression",
                "boolean_operator",
            ) or (t == "unary" or t in ("unary_expression", "unary_op_expression")):
                op = _op(node)
            if t in ("binary", "binary_expression"):
                if op in ("&&", "||", "and", "or"):
                    add("branch", op)
                elif lang == "php" and op == "??":
                    add("branch", op)  # value-selection operator: counts per branch_rule_contract.md ("stay dual")
                if (
                    op in ("<<", ">>", "^", "&", "|")
                    or (lang == "lua" and op == "~")
                    or (lang == "bash" and op in ("<<=", ">>=", "^=", "&=", "|="))
                ):
                    skip = False
                    if lang == "ruby" and op == "<<":
                        l, r = node.child_by_field_name("left"), node.child_by_field_name("right")
                        lit = (
                            "string",
                            "array",
                            "hash",
                            "symbol",
                            "heredoc_beginning",
                            "bare_string",
                            "interpolation",
                            "string_array",
                        )
                        skip = (
                            (l is not None and l.type in lit)
                            or (r is not None and r.type in lit)
                            or self._is_stmt_append(node)
                        )
                    if not skip:
                        add("bitwise", op)
                if lang == "ruby" and op in ("=~", "!~"):
                    add("regex", op)
                if lang == "bash" and op == "=~":
                    add("regex", op)
            elif t in ("operator_assignment", "augmented_assignment_expression"):
                if op in ("<<=", ">>=", "^=", "&=", "|="):
                    add("bitwise", op)
                elif (op in ("||=", "&&=") and lang == "ruby") or (op == "??=" and lang == "php"):
                    add("branch", op)
            elif t in ("unary", "unary_expression", "unary_op_expression") and op == "~":
                add("bitwise", "~")
            # ---- shell specifics
            if lang == "bash":
                if t == "list":
                    for c in node.children:
                        if not c.is_named and c.type in ("&&", "||"):
                            add("branch", c.type)
                elif t == "file_redirect" and self._sh_file_dest(node) is not None:
                    add("io", "redirect")
                elif (
                    t == "variable_name"
                    and node.text.decode() in _SH_TIME_VARS
                    and node.parent is not None
                    and node.parent.type in ("simple_expansion", "expansion")
                ):
                    add("time", node.text.decode())
            # ---- ruby else arms
            if (
                lang == "ruby"
                and t == "else"
                and node.parent is not None
                and node.parent.type in ("if", "unless", "elsif", "case", "case_match")
            ):
                add("branch", "else")
            # ---- php statement nodes
            if lang == "php":
                if t in ("echo_statement", "print_intrinsic"):
                    add("print", t)
                if t == "unary_op_expression":
                    pass
            # ---- calls
            if t in spec.call_types:
                ce = self._callee(node)
                if ce is None:
                    continue
                recv, name = ce
                printed = False
                if lang == "bash" and name in ("echo", "printf", "print") and not self._sh_console_ok(node):
                    pass
                else:
                    hit = match(recv, name, spec.calls.get("print", ()))
                    if hit and not (
                        lang == "php" and name in ("print_r", "var_export") and self._php_returns_string(node)
                    ):
                        add("print", hit)
                        printed = True
                for key, pats in spec.calls.items():
                    if key == "print" or (key == "io" and printed):
                        continue
                    hit = match(recv, name, pats)
                    if not hit:
                        continue
                    if lang == "lua" and hit == "*.find":
                        continue
                    if (
                        lang == "ruby"
                        and key == "io"
                        and hit in ("*.read", "*.write", "*.open")
                        and recv in ("$stdout", "$stderr", "STDOUT", "STDERR")
                    ):
                        continue
                    add(key, hit)
                if lang == "lua" and recv == "os" and name == "execute":
                    args = node.child_by_field_name("arguments")
                    if (
                        args is not None
                        and args.named_children
                        and re.match(r"""["']\s*(sleep|usleep)\b""", _text(args.named_children[0]))
                    ):
                        add("sleep", 'os.execute("sleep")')
                if lang == "lua" and recv is not None and name == "find":
                    args = node.child_by_field_name("arguments")
                    if args is not None and args.named_children and args.named_children[0].type == "string":
                        add("regex", ":find")
        n["args"] = self._args(fn)
        if lang == "php":
            deco = [c for c in fn.children if c.type == "attribute_list"]
            cnt = sum(1 for d in deco for a in _walk(d) if a.type == "attribute")
            if cnt:
                n["decorators"] = cnt
                tokens["decorators"]["#["] += cnt
        if "is_documented" not in spec.skip_families:
            n["doc"] = 1 if self._documented(fn) else 0
        return n, tokens

    @staticmethod
    def _php_returns_string(node) -> bool:
        args = node.child_by_field_name("arguments")
        if args is None or len(args.named_children) < 2:
            return False
        return _text(args.named_children[1]).strip().lower() in ("true", "argument:true", "return: true")


def _walk(node):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(n.children)


SPECS: dict[str, Spec] = {"ruby": _RUBY, "php": _PHP, "lua": _LUA, "bash": _SH}


def register() -> None:
    for lang, spec in SPECS.items():
        fts.SPECS[lang] = spec
        fts._ORACLES[lang] = BOracle(spec)
    fts.SPECS["shell"], fts._ORACLES["shell"] = SPECS["bash"], fts._ORACLES["bash"]
