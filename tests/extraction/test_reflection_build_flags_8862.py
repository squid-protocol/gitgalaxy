"""reflection_metaprogramming: dart `reflect` is a call, dockerfile counts only ONBUILD (#8862)."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

SITES = {
    "dart": ("var m = reflect(obj);", "import 'dart:mirrors';", "noSuchMethod(inv);", "reflectClass(Foo);"),
    "dockerfile": ("ONBUILD RUN make", "  onbuild COPY . /app"),
}
NOT_SITES = {
    "dart": ('var s = "reflect on this";', "// we reflect the value", "var reflected = 1;"),
    "dockerfile": (
        "RUN --mount=type=cache,target=/c pip install x",
        "RUN --mount=type=secret,id=s cat /run/secrets/s",
        "FROM --platform=linux/amd64 ubuntu",
        "RUN <<EOF\necho hi\nEOF",
    ),
}


def _cases(table):
    return [(lang, text) for lang, texts in table.items() for text in texts]


@pytest.mark.parametrize(("lang", "text"), _cases(SITES))
def test_a_reflection_site_still_counts(lang, text):
    assert LANGUAGE_DEFINITIONS[lang]["rules"]["reflection_metaprogramming"].search(text)


@pytest.mark.parametrize(("lang", "text"), _cases(NOT_SITES))
def test_a_word_or_build_option_is_not_a_site(lang, text):
    assert not LANGUAGE_DEFINITIONS[lang]["rules"]["reflection_metaprogramming"].search(text)
