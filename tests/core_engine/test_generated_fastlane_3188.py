"""Generated-file fast lane (#3188): a large bare-directive table skips the detector and Security Lens."""

import logging
from unittest.mock import mock_open, patch

import pytest

from gitgalaxy.core.generated_fastlane import MIN_BYTES, clean_directive_table_scan
from gitgalaxy.security.security_lens import SecurityLens


def _table(n: int = 12000) -> str:
    lines = ["#ifndef __AVAILABILITY_INTERNAL__", "#define __AVAILABILITY_INTERNAL__", "#include <stdint.h>"]
    for i in range(n):
        lines.append(f"#if __MAC_OS_X_VERSION_MIN_REQUIRED < {1000 + i}")
        lines.append(
            f"    #define __AVAILABILITY_INTERNAL__MAC_10_{i} __attribute__((availability(macosx,introduced={i})))"
        )
        lines.append("#endif")
    lines.append("#endif")
    return "\n".join(lines) + "\n"


_LENS = SecurityLens()


def _scan(text: str, lang: str = "c"):
    return clean_directive_table_scan(text, lang, len(text.encode()), _LENS)


def _gate(text: str, lang: str = "c") -> bool:
    return _scan(text, lang) is not None


def test_fast_scan_equals_the_whole_file_scan():
    # The lane's whole claim: what the worker uses in place of the full lens is what the full lens returns.
    text = _table(6000)
    fast = _scan(text)
    full = _LENS.scan_content(text, code_stream=text, prose=False)
    assert fast is not None
    for key in ("counts", "snippets", "sites", "positions"):
        assert fast.get(key, {}) == full.get(key, {}), key


@pytest.mark.parametrize(
    "extra",
    [
        "#define VIA(c) os.system(c)\n",
        "#define RUN(c) system(c)\n",
        "#define EXEC(c) eval(c)\n",
    ],
)
def test_a_shape_the_lens_flags_keeps_the_full_lane(extra):
    full = _LENS.scan_content(extra, code_stream=extra, prose=False)
    text = extra + _table(6000)
    assert any(full["counts"].values()), "premise: the lens flags this shape"
    assert not _gate(text)


def test_non_ascii_keeps_the_full_lane():
    assert not _gate(_table() + "#define \u00e9 1\n")


def test_diverse_directives_are_not_a_repetitive_table():
    # Every line a different shape (no digits to normalise): a hand-written table, so the full lane runs.
    import itertools
    import string

    names = ("".join(p) for p in itertools.product(string.ascii_lowercase, repeat=4))
    text = "".join(f"#define NAME_{n} value_{n}\n" for n in itertools.islice(names, 12000))
    assert len(text) > MIN_BYTES
    assert not _gate(text)


def test_big_directive_table_passes_for_every_preprocessor_dialect():
    text = _table()
    assert len(text) > MIN_BYTES
    for lang in ("c", "cpp", "objective-c"):
        assert _gate(text, lang)


def test_other_languages_never_pass():
    for lang in ("python", "shell", "ruby", "plaintext"):
        assert not _gate(_table(), lang)


def test_small_file_stays_on_the_full_lane():
    text = _table(20)
    assert len(text) < MIN_BYTES
    assert not _gate(text)


def test_empty_and_blank_files():
    assert clean_directive_table_scan("", "c", MIN_BYTES, _LENS) is None
    assert clean_directive_table_scan("\n  \n" * 10, "c", MIN_BYTES, _LENS) is None


@pytest.mark.parametrize(
    "tail",
    [
        "int add(int a, int b) { return a + b; }\n",
        'const char *key = "AKIAIOSFODNN7EXAMPLE";\n',
        "static int x = 3;\n",
    ],
)
def test_real_code_lines_beyond_the_slack_fail(tail):
    # Code lines amounting to more than 5% of the file keep it on the full lane.
    assert not _gate(_table() + tail * 3000)


def test_quote_brace_semicolon_continuation_directives_do_not_count():
    # A macro that holds a string, a body or a continuation is real content, not a bare table line.
    for line in ('#define KEY "secret"\n', "#define F(x) { x; }\n", "#define A 1;\n", "#define B \\\n"):
        assert not _gate(line * 20000), line


def test_hand_written_macro_header_with_bodies_is_not_fast_laned():
    body = "#define M(x) do { f(x); } while (0)\nstatic inline int g(int a) {\n  return a;\n}\n"
    assert not _gate(body * 8000)


def test_pathological_long_line_is_linear():
    # A single huge line must not trigger backtracking (possessive match).
    assert not _gate("#define X " + "a" * 400_000 + '"\n')


# --- worker integration -------------------------------------------------------------------------------


@patch("gitgalaxy.galaxyscope.ApertureFilter")
@patch("gitgalaxy.galaxyscope.Prism")
@patch("gitgalaxy.galaxyscope.LanguageDetector")
@patch("gitgalaxy.galaxyscope.SecurityLens")
@patch("gitgalaxy.galaxyscope.Path.is_file", return_value=True)
@pytest.mark.parametrize("generated", [True, False])
def test_worker_skips_detector_and_security_only_for_a_table(
    _is_file, MockSec, MockDet, MockPrism, MockAperture, generated
):
    from gitgalaxy.galaxyscope import _init_worker, _process_file_worker

    text = _table() if generated else _table() + "int f(void) { return 1; }\n" * 4000
    MockAperture.return_value.evaluate_path_integrity.return_value = (True, len(text), "Passed")
    MockAperture.return_value.is_in_scope.return_value = {
        "is_in_scope": True,
        "reason": None,
        "total_loc": text.count("\n"),
        "size_bytes": len(text),
    }
    MockDet.return_value.inspect.return_value = {"lang_id": "c", "intensity": 0.9, "lock_tier": 1, "source_proof": "t"}
    MockPrism.return_value.split_streams.return_value = {
        "code_stream": text,
        "comment_stream": "",
        "coding_loc": 1,
        "doc_loc": 0,
    }
    MockSec.return_value.scan_content.return_value = {"counts": {}, "snippets": {}}
    config = {
        "LANGUAGE_DEFINITIONS": {"c": {"extensions": [".h"], "rules": {}}},
        "APERTURE_CONFIG": {},
        "PARANOID_MODE": False,
    }
    _init_worker(".", config, {".h": 1}, logging.INFO, {"inc/a.h"}, {"a"})

    with patch("builtins.open", mock_open(read_data=text.encode())):
        result = _process_file_worker("inc/a.h")

    assert result["status"] == "success"
    assert result["data"]["lang_id"] == "c"
    assert not result["data"]["is_minified"]
    if generated:
        assert result["data"]["fast_lane"] == "directive_table"
        # The lens ran once, over the distinct-shape sample only, not the whole file.
        MockSec.return_value.scan_content.assert_called_once()
        assert len(MockSec.return_value.scan_content.call_args.args[0]) < len(text) // 10
    else:
        assert "fast_lane" not in result["data"]
        MockSec.return_value.scan_content.assert_called_once()
