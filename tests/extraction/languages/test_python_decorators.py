"""
Decorator edges (Python): `decorated_by` / `decorated_by_qualifiers`.

A decorator's wrapper runs around every call to the function it decorates, so the
detector records, per function, the decorators applied to it, as callee names with their
receiver chains (`@app.post(...)` -> "post" via "app"). The resolver links them like
calls, as fcall_data kind 'decorator'.
"""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _decorators(code: str, lang: str = "python") -> dict[str, tuple]:
    out = {}
    for f in StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]:
        if not f.get("is_synthetic_slice"):
            out[f["name"]] = (f.get("decorated_by"), f.get("decorated_by_qualifiers"))
    return out


def test_factory_bare_and_stacked_decorators():
    code = (
        "@app.post(\n    '/items(',\n    response_model=Item,\n)\n@retry(3)\n"
        "def create_item(item):\n    return save(item)\n"
    )
    assert _decorators(code)["create_item"] == (["post", "retry"], {"post": ["app"], "retry": [""]})


def test_methods_async_and_comments_between():
    code = (
        "class S3Hook:\n"
        "    @provide_bucket_name\n    @unify_bucket_name_and_key\n    def get_key(self, key):\n        return 1\n"
        "\n    x = 1\n    def plain(self):\n        pass\n"
        "\n    # a note\n    @functools.cache\n    async def fetch(self):\n        pass\n"
    )
    got = _decorators(code)
    assert got["get_key"][0] == ["provide_bucket_name", "unify_bucket_name_and_key"]
    assert got["plain"] == ([], {})
    assert got["fetch"] == (["cache"], {"cache": ["functools"]})


def test_a_decorator_of_another_statement_is_not_taken():
    # `x = 1` sits between the decorator block and this def: no decorators
    code = "@deco\ndef a():\n    pass\n\nx = 1\ndef b():\n    pass\n"
    got = _decorators(code)
    assert got["a"][0] == ["deco"]
    assert got["b"][0] == []


def test_languages_without_the_flag_record_nothing():
    code = "@Component({})\nclass A {\n  run() {\n    go();\n  }\n}\n"
    for name, (decorated, _) in _decorators(code, "typescript").items():
        assert not decorated, name
