"""C keyword-family rules after the #8863 / #9334 validity pass: bitwise_ops, debug_prints, panics_and_aborts count what their contracts name."""

import sys
import textwrap
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards.languages import c as c_lang

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import family_oracle_ts


def _rule(key):
    for obj in vars(c_lang).values():
        if isinstance(obj, dict):
            for v in [obj, *[x for x in obj.values() if isinstance(x, dict)]]:
                if key in v and "thread_sleeps" in v:
                    return v[key]
    raise AssertionError(f"c {key} rule not found")


POSITIVE = {
    "bitwise_ops": [
        "x = a & b;",
        "y = flags|MASK;",
        "if ((a) & 1)",
        "z = v[i]&0xff;",
        "x = 0xFF & y;",
        "m = (a)|(b);",
        "x = f(a) | g(b);",
        "n = a ^ b;",
        "n = ~a;",
        "n = a << 3;",
        "a &= 3;",
        "a |= 3;",
    ],
    "debug_prints": [
        'printf("x\\n");',
        'fprintf(stderr, "x");',
        'fprintf (stdout, "x");',
        'fputs("x", stdout);',
        "putc(c, stderr);",
        'puts("x");',
        'perror("open");',
    ],
    "time_date_logic": [
        "t = time(NULL);",
        "time_t t = time(0);",
        "m = gmtime(&t);",
        "gmtime_r(&t, &tm);",
        "strptime(s, fmt, &tm);",
        "t = timegm(&tm);",
        "s = ctime(&t);",
        "asctime (&tm);",
        "clock_gettime(CLOCK_MONOTONIC, &ts);",
        "strftime(buf, n, fmt, tm);",
    ],
    "panics_and_aborts": [
        "abort();",
        "exit(1);",
        "    exit (EXIT_FAILURE);",
        "_exit(2);",
        "_Exit(3);",
        "quick_exit(0);",
        "if (bad) exit(1);",
    ],
}

NEGATIVE = {
    "bitwise_ops": [
        "return &x;",
        "f(a, &b);",
        "p = &q;",
        "if (a && b)",
        "if (a || b)",
        "x = (char *)&y;",
        "int *p = &arr[0];",
        "sizeof &x;",
        "x = *p;",
    ],
    "debug_prints": [
        'fprintf(out, "x");',
        'fprintf (f,"%s ",name);',
        "fputs(s, fp);",
        'snprintf(buf, n, "x");',
        'sprintf(buf, "x");',
        "fputc(c, out);",
    ],
    "time_date_logic": [
        "time_t t;",
        "(time_t)expire < now",
        "x = (time_t) y;",
        "le->ctime = now;",
        "a->ctime - b->ctime",
        "p->time(1);",
        "mstime_t now = f();",
        "my_time(1);",
        "uptime(x);",
    ],
    "panics_and_aborts": [
        "f->fb_exit = exit;",
        "jump_target_label exit, void *datum)",
        'scheme_addto_prim_instance("abort-current-continuation", p);',
        "ota_mgr.abort();",
        "p->exit(1);",
        "my_exit(1);",
        "return -1;",
    ],
}


@pytest.mark.parametrize(
    ("key", "line"), [(k, line) for k, lines in POSITIVE.items() for line in lines], ids=lambda v: str(v)[:30]
)
def test_contract_forms_count(key, line):
    assert _rule(key).search(line)


@pytest.mark.parametrize(
    ("key", "line"), [(k, line) for k, lines in NEGATIVE.items() for line in lines], ids=lambda v: str(v)[:30]
)
def test_other_constructs_do_not_count(key, line):
    assert not _rule(key).search(line)


def test_bitwise_rule_is_linear_on_adversarial_input():
    rule = _rule("bitwise_ops")
    payload = "a" + " " * 50000 + "&" + " " * 50000 + "\n" + "|" * 50000 + "\n" + "] " * 20000 + "a " * 20000
    rule.search(payload)  # bounded quantifiers: must return (the test harness timeout is the fuse)


def _count(src, name, key):
    oracle = family_oracle_ts.get_oracle("c")
    index = oracle.index(textwrap.dedent(src))
    node = next(n for (nm, _line), n in index.items() if nm == name)
    return oracle.count(node)[0].get(key, 0)


@pytest.mark.parametrize(
    "call", ['fputs("x", fp);', "fputc(c, fp);", "stat(p, &st);", "rename(a, b);", "getline(&l, &n, fp);"]
)
def test_oracle_reads_the_stream_and_filesystem_calls_as_io(call):
    assert _count(f"void f(void) {{ {call} }}\n", "f", "io") == 1
    assert _count("void f(void) { g(); }\n", "f", "io") == 0
