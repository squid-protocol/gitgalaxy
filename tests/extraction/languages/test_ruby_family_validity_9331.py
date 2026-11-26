"""Ruby keyword-family rules after the family-validity pass (#9331, part of #8863).

Each family has lines it must count (the operative form) and lines it must not (the construct the old rule confused it with).
"""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

RULES = LANGUAGE_DEFINITIONS["ruby"]["rules"]

CASES = [
    # (rule, counted, not counted)
    (
        "debug_prints",
        ["puts x", "puts(x)", "p obj", "pp(h)", "warn 'x'", "$stderr.puts msg", "printf('%d', n)"],
        ["items.map { |p| p.name }", "logger.warn 'x'", "def puts(*args)", "x = p", "path = a.print_name"],
    ),
    (
        "regex_execution",
        [
            "name =~ /ab/",
            "s.gsub(/a/, 'b')",
            "if x !~ y",
            "Regexp.union(a, b)",
            "return /ab+/",
            "x = %r{a/b}",
            "ok = (/ab/)",
        ],
        ["a / b", "x = 6 / 3", "puts 'hello'"],
    ),
    (
        "time_date_logic",
        [
            "Time.now",
            "Time.at(epoch)",
            "Date.today",
            "t.strftime('%Y')",
            "Process.clock_gettime(Process::CLOCK_MONOTONIC)",
        ],
        ["sleep 5", "timestamp = epoch", "sleeper"],
    ),
    (
        "io",
        [
            "File.read(path)",
            "File.open(p, 'w')",
            "Dir.glob('*.rb')",
            "FileUtils.mkdir_p(d)",
            "path.read",
            "pathname.mkpath",
            "open('f')",
            "Net::HTTP.get(u)",
        ],
        [
            "File::SEPARATOR",
            "File.join(a, b)",
            "File.basename(p)",
            "list.find { |x| x }",
            "h.update(a: 1)",
            "Model.where(a: 1)",
            "def open?",
        ],
    ),
    (
        "bitwise_ops",
        ["a ^ b", "flags & MASK", "flags | MASK", "x = 1 << n", "mask <<= 2", "y = ~x", "h >> 3"],
        [
            "/^abc/",
            "[^a-z]",
            "<<~EOS",
            "list.each { |x| x }",
            "a && b",
            "a || b",
            "arr.map(&:to_s)",
            "out << 'x'",
            "list.select(&:ok?)",
        ],
    ),
]


def _ids():
    for rule, yes, no in CASES:
        for line in yes:
            yield pytest.param(rule, line, True, id=f"{rule}-counts-{line[:24]}")
        for line in no:
            yield pytest.param(rule, line, False, id=f"{rule}-skips-{line[:24]}")


@pytest.mark.parametrize(("rule", "line", "expected"), list(_ids()))
def test_family_rule_counts_the_operative_form_only(rule, line, expected):
    assert bool(RULES[rule].search(line)) is expected, f"ruby {rule!r} on {line!r}"
