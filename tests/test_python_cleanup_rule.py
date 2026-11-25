"""Python `cleanup` rule reads the whole #8862 contract: teardown regions and `del`, not only call forms."""

import pytest

from gitgalaxy.standards.language_standards.languages import python as py_lang


def _rule():
    for obj in vars(py_lang).values():
        if isinstance(obj, dict) and "cleanup" in obj and "telemetry" in obj:
            return obj["cleanup"]
        if isinstance(obj, dict):
            for v in obj.values():
                if isinstance(v, dict) and "cleanup" in v and "telemetry" in v:
                    return v["cleanup"]
    raise AssertionError("python cleanup rule not found")


@pytest.mark.parametrize(
    "line",
    [
        "with open(p) as f:",
        "with lock:",
        "    finally:",
        "del cache[key]",
        "shutil.rmtree(tmp)",
        "path.unlink()",
        "conn.close()",
    ],
)
def test_cleanup_forms_count(line):
    assert _rule().search(line)


@pytest.mark.parametrize("line", ["def close(self):", "return without delay", "# deal with the rest of it"])
def test_non_cleanup_text_does_not(line):
    assert not _rule().search(line)
