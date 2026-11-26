"""Lua keyword-family rules after the #8863 / #9339 validity pass: bitwise_ops, thread_sleeps, io and regex_execution count what their contracts name."""

import pytest

from gitgalaxy.standards.language_standards.languages import lua as lua_lang


def _rule(key):
    for obj in vars(lua_lang).values():
        if isinstance(obj, dict):
            for v in [obj, *[x for x in obj.values() if isinstance(x, dict)]]:
                if key in v and "thread_sleeps" in v:
                    return v[key]
    raise AssertionError(f"lua {key} rule not found")


POSITIVE = {
    "bitwise_ops": [
        "x = a & b",
        "x = a|3",
        "x = a << 3",
        "x = a >> 1",
        "x = a ~ b",
        "return ~a",
        "n = lnum & (~(-1 << 8))",
    ],
    "thread_sleeps": [
        "loader.delay(100)",
        "socket.sleep(0.5)",
        "ngx.sleep(1)",
        "posix.sleep(2)",
        "posix.usleep(500)",
        "posix.unistd.usleep(5)",
        "task.wait(1)",
    ],
    "io": [
        "local f = io.open(p)",
        "local t = io.tmpfile()",
        "local s = f:read('*a')",
        "f:write(data)",
        "for l in f:lines() do",
        "f:seek('set', 0)",
    ],
    "regex_execution": [
        "local m = s:match('%d+')",
        "for w in s:gmatch('%a+') do",
        "s = s:gsub('a', 'b')",
        "local i = s:find('x')",
        'local i = path:find("/", 1, true)',
        "string.match(s, p)",
    ],
}
NEGATIVE = {
    "bitwise_ops": [
        "x = a ^ 2",
        "x = 2^30",
        "if a ~= b then",
        'print(">>> closing state <<<")',
        'local t = {"&", "|", "<<", ">>"}',
        'string.gsub(cfg, "\\n", "|")',
    ],
    "thread_sleeps": ["local s = sleep_time", "os.time()"],
    "io": ["io.stdout:write(x)", "io.stderr:write(x)", "os.remove(p)", "os.tmpname()", "x = pandoc.read(s)"],
    "regex_execution": ["local i = s:find(needle)", "t:insert(x)", "local g = matcher(s)"],
}


@pytest.mark.parametrize(
    ("key", "line"), [(k, line) for k, lines in POSITIVE.items() for line in lines], ids=lambda v: str(v)[:30]
)
def test_contract_forms_count(key, line):
    assert _rule(key).search(line)


@pytest.mark.parametrize(
    ("key", "line"), [(k, line) for k, lines in NEGATIVE.items() for line in lines], ids=lambda v: str(v)[:30]
)
def test_false_positive_forms_do_not_count(key, line):
    assert not _rule(key).search(line)
