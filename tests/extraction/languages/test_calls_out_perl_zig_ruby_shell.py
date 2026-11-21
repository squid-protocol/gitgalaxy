"""
Regression tests for Perl, Zig, Ruby, and Shell call-graph accuracy improvements:
- Perl: `undef` is a special form (undef_expression), not a call (154 FPs).
- Zig: `@import("std")` is a builtin invocation (62 FNs); `volatile(...)` is not a call (10 FPs).
- Ruby: `obj.class` (Object#class) and `require "x"` (Kernel#require) are method calls.
- Shell: heredoc bodies and `EOF` terminators are blanked, not scanned as commands (38+ FPs).
"""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _calls(lang: str, code: str, fn_name: str) -> list[str]:
    units = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(u for u in units if u["name"].split("::")[-1].split(".")[-1] == fn_name)["calls_out_to"]


def test_perl_undef_is_not_a_call():
    code = "sub run {\n    my $x = undef;\n    undef($x);\n    helper($x);\n}\n"
    calls = _calls("perl", code, "run")
    assert "undef" not in calls
    assert "helper" in calls


def test_zig_import_builtin_kept_and_volatile_dropped():
    code = 'fn run() void {\n    const std = @import("std");\n    const p = volatile(x);\n    std.debug.print("hi", .{});\n}\n'
    calls = _calls("zig", code, "run")
    assert "import" in calls
    assert "print" in calls
    assert "volatile" not in calls


def test_ruby_class_and_require_are_calls():
    code = 'def run(obj)\n  require "json"\n  obj.class\n  helper(obj)\nend\n'
    calls = _calls("ruby", code, "run")
    assert "class" in calls
    assert "require" in calls
    assert "helper" in calls


def test_shell_heredoc_body_and_terminator_are_not_commands():
    code = "run() {\n    cat <<'EOF'\nfake_cmd_in_heredoc\nEOF\n    real_helper \"$1\"\n}\n"
    calls = _calls("shell", code, "run")
    assert "cat" in calls
    assert "real_helper" in calls
    assert "EOF" not in calls
    assert "fake_cmd_in_heredoc" not in calls
