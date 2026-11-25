"""Go `thread_sleeps` counts the timer constructors the contract names as timed waits (#8868)."""

import pytest

from gitgalaxy.standards.language_standards.languages import go as go_lang


def _rule():
    for obj in vars(go_lang).values():
        if isinstance(obj, dict):
            for v in obj.values():
                if isinstance(v, dict) and "thread_sleeps" in v and "time_date_logic" in v:
                    return v["thread_sleeps"]
            if "thread_sleeps" in obj and "time_date_logic" in obj:
                return obj["thread_sleeps"]
    raise AssertionError("go thread_sleeps rule not found")


@pytest.mark.parametrize(
    "line",
    [
        "time.Sleep(d)",
        "<-time.After(d)",
        "time.AfterFunc(d, f)",
        "t := time.NewTicker(d)",
        "time.NewTimer(d)",
        "<-time.Tick(d)",
    ],
)
def test_timed_waits_count(line):
    assert _rule().search(line)


@pytest.mark.parametrize("line", ["time.Now()", "time.Since(t)", "time.Unix(0, 0)"])
def test_clock_reads_are_not_sleeps(line):
    assert not _rule().search(line)
