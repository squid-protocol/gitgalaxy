"""Go keyword-family rules after the #8863 validity pass: bitwise_ops, time_date_logic, io and doc count what their contracts name."""

import pytest

from gitgalaxy.standards.language_standards.languages import go as go_lang


def _rule(key):
    for obj in vars(go_lang).values():
        if isinstance(obj, dict):
            for v in [obj, *[x for x in obj.values() if isinstance(x, dict)]]:
                if key in v and "thread_sleeps" in v:
                    return v[key]
    raise AssertionError(f"go {key} rule not found")


POSITIVE = {
    "bitwise_ops": [
        "x := a & b",
        "x := a | b",
        "x := a&mask",
        "x := a|b",
        "flags |= FlagA",
        "flags &= mask",
        "if (v & 1) != 0 {",
        "if f(x) | g(y) {",
        "x = a << 2",
        "x = a &^ b",
        "m := ^uint32(0)",
    ],
    "time_date_logic": ["d := time.Duration(n) * time.Second", "t := time.Now()", "time.Since(t)"],
    "io": [
        "f, err := os.Open(p)",
        "io.Copy(w, r)",
        "b, _ := io.ReadAll(r)",
        "w := bufio.NewWriter(f)",
        "r := bufio.NewReader(c)",
    ],
    "doc": [
        "// Serve accepts connections.",
        "// handlePanic ensures that we print",
        "//\tindented text",
        "// Package http provides",
    ],
}
NEGATIVE = {
    "bitwise_ops": [
        "p := &T{}",
        "return &T{}",
        "f(a, &b)",
        "x = &y",
        "if a && b {",
        "if a || b {",
        "case a || b:",
        "x := <-ch",
        "ok = a == &b",
    ],
    "time_date_logic": ["timeout time.Duration", "func f(d time.Duration) error {", "time.Sleep(d)"],
    "io": [
        "func (r *R) ReadFrom(src io.Reader) error {",
        "w *bufio.Writer",
        "func f(w io.Writer) {",
        '"net/http"',
        '"database/sql"',
    ],
    "doc": ["\t// a note inside a body", "//go:build linux", "//nolint:errcheck", "x := 1 // trailing", "var y = 2"],
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


def test_bitwise_rule_is_linear_on_adversarial_input():
    rule = _rule("bitwise_ops")
    payload = "a" + " " * 50000 + "&" + " " * 50000 + "\n" + "|" * 50000
    rule.search(payload)  # bounded quantifiers: must return (the test harness timeout is the fuse)
