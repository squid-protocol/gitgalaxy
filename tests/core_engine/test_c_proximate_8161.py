"""#8161 (C5): in C, the nearest-path pick among several definitions of a name is confident (`proximate`):
it almost always is the variant in the caller's own platform directory (363 of 363 picks agreed with
libclang over 5 repos). Every other language keeps it as the ambiguous `nearest` guess."""

import pytest

from gitgalaxy.core.call_resolver import CONFIDENT_RESOLUTIONS, RESOLUTION_OF_STEP, confident_file_pairs, resolve_calls


def _fn(name: str, line: int, calls: list[str] | None = None) -> dict:
    return {
        "name": name,
        "start_line": line,
        "loc": 3,
        "calls_out_to": calls or [],
        "calls_out_qualifiers": {c: [""] for c in calls or []},
    }


def _files(lang: str, ext: str) -> list[dict]:
    return [
        {"path": f"src/unix/aix.{ext}", "lang_id": lang, "functions": [_fn("uv_init", 1, ["uv_mutex_lock"])]},
        {"path": f"src/unix/thread.{ext}", "lang_id": lang, "functions": [_fn("uv_mutex_lock", 10)]},
        {"path": f"src/win/thread.{ext}", "lang_id": lang, "functions": [_fn("uv_mutex_lock", 20)]},
    ]


def test_c_nearest_platform_variant_is_confident():
    sites, _ = resolve_calls(_files("c", "c"))
    (row,) = [s for s in sites if s["callee"] == "uv_mutex_lock"]
    assert (row["step"], row["dst_path"]) == ("proximate", "src/unix/thread.c")
    assert row["resolution"] in CONFIDENT_RESOLUTIONS
    assert confident_file_pairs(sites) == {("src/unix/aix.c", "src/unix/thread.c"): 1}


@pytest.mark.parametrize("lang,ext", [("cpp", "cpp"), ("python", "py")])
def test_other_languages_keep_the_nearest_guess_ambiguous(lang, ext):
    sites, _ = resolve_calls(_files(lang, ext))
    (row,) = [s for s in sites if s["callee"] == "uv_mutex_lock"]
    assert RESOLUTION_OF_STEP[row["step"]] not in CONFIDENT_RESOLUTIONS
