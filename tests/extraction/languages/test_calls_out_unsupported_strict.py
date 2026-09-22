from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# Epic #3264 Phase 3 Batch 1 (#3283): data/markup/config languages must declare
# intentional blindness instead of running the C-style regex over non-code
# content (css captured url()/expression(); the rest was pure noise).
DEMOTED_LANGUAGES = (
    "json",
    "csv",
    "css",
    "plaintext",
    "pbtxt",
    "xml",
    "proto",
    "td",
    "blp",
    "csd",
    "nix",
)

# Languages that were already intentionally blind before Phase 3; pinned here so
# a future re-enable is a deliberate act with a rosetta rebless, not a drive-by.
ALWAYS_UNSUPPORTED_LANGUAGES = (
    "shell",
    "dockerfile",
    "sqlite",
    "html",
    "yaml",
    "markdown",
    "bms",
)


def test_demoted_languages_declare_calls_out_unsupported():
    for lang in DEMOTED_LANGUAGES + ALWAYS_UNSUPPORTED_LANGUAGES:
        assert LANGUAGE_DEFINITIONS[lang]["rules"]["calls_out"] is None, (
            f"{lang} must map calls_out to CALLS_OUT_UNSUPPORTED (None); "
            "re-enabling extraction requires a real paradigm + rosetta rebless"
        )
