"""#9338: Shell keyword-family validity on the pinned crucible. Five families used to match a bare word anywhere (an argument,
a prose line, `read`, `return N`, `kill`, a pipe, a comparison); each now counts the construct its contract names, at command
position: `exit` (panics_and_aborts), a clock read (time_date_logic), a console `echo` (debug_prints), arithmetic bit
operators (bitwise_ops), and a file or network move (io)."""

import pytest

from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
_RULES = LANGUAGE_DEFINITIONS["shell"]["rules"]


def _fires(family: str, src: str) -> bool:
    return bool(_RULES[family].search(_PRISM.split_streams(src, "shell")["code_stream"]))


POSITIVE = {
    "panics_and_aborts": [
        "exit 1",
        "  exit",
        "cmd || exit 2",
        "if bad; then exit 3; fi",
        "case $a in x) exit 1;; esac",
    ],
    "time_date_logic": [
        "date +%s",
        "now=$(date -u)",
        "t0=`date +%s`",
        "/bin/date -u +%Y",
        "time ./run",
        "echo $EPOCHSECONDS",
        "uptime",
    ],
    "debug_prints": [
        "echo x",
        'printf "%s\\n" "$a"',
        "echo x >&2",
        "echo x 2>/dev/null",
        "echo x > /dev/stderr",
        "ok && echo y",
    ],
    "bitwise_ops": [
        "x=$((a<<2))",
        "(( m = a & 0xff ))",
        "y=$(( a | b ))",
        "z=$(( a ^ b ))",
        "let r=a>>1",
        "x=$(( ~a ))",
    ],
    "io": [
        "cp a b",
        "cat f",
        "mkdir -p d",
        "curl -s u",
        "read line",
        "echo x > f",
        "echo x >> f",
        "sort < f",
        "sudo tee /etc/x",
    ],
}

NEGATIVE = {
    "panics_and_aborts": ["return 1", "kill $pid", "abort", "echo exit now", "exit_code=1", "# exit", "cmd --exit"],
    "time_date_logic": ["sleep 1", "echo date", "update=1", "date=1", "foo --date x", "times=3", "time.sleep(1)"],
    "debug_prints": [
        "read x",
        "echo x | tr a b",
        "v=$(echo x)",
        "echo x > f",
        "echo x >> f",
        "printf x | cat",
        "cmd echo x",
    ],
    "bitwise_ops": ["a && b", "a || b", "a | b", "cat <<EOF", "cmd &", "x=$((a+b))", "(( a > b ))", "echo $((a&&b))"],
    "io": [
        "a | b",
        "[ $a -gt $b ]",
        "echo x >&2",
        "echo x > /dev/null",
        "sort <<EOF",
        "sort <<< $x",
        "cmd 2>&1",
        "cmd 2>err",
        "x=<(cmd)",
        "grep a b",
        "echo cat",
    ],
}


@pytest.mark.parametrize(("family", "src"), [(f, s) for f, ss in POSITIVE.items() for s in ss])
def test_the_named_construct_counts(family, src):
    assert _fires(family, src), (family, src)


@pytest.mark.parametrize(("family", "src"), [(f, s) for f, ss in NEGATIVE.items() for s in ss])
def test_the_false_positive_forms_do_not_count(family, src):
    assert not _fires(family, src), (family, src)


def test_a_continuation_line_is_an_argument_not_a_command():
    assert not _fires("time_date_logic", 'atf_check -o "inline:x" \\\n\tdate -r f +%s')
    assert _fires("time_date_logic", "atf_check -o x\ndate -r f +%s")
