# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#4108 slice 11: probe of "Public API Declared Near Raw DB Sink" (`sec_amplified_sql_injection`).

The signal needs an `api` hit in the same function as a `db_hooks` hit, so a handler the `api` rule never sees
(underscore-named route handler, Express route registration, unexported Go HTTP handler) reads 0. Near-miss controls
must stay at zero, and a ReDoS control.
"""

import time

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

FIRES = {
    "py_route_private_handler": ("python", '@app.route("/u")\ndef _get(r):\n    pass\n'),
    "py_patch_decorator": ("python", '@app.patch("/u")\ndef _get(r):\n    pass\n'),
    "py_blueprint_object": ("python", '@bp.route("/u")\ndef _get(r):\n    pass\n'),
    "py_nested_object": ("python", '@api.v1.post("/u")\ndef _get(r):\n    pass\n'),
    "js_express_get": ("javascript", "app.get('/u', (req, res) => {\n});\n"),
    "js_router_post_template": ("javascript", "router.post(`/u`, handler);\n"),
    "ts_express_get": ("typescript", "app.get('/u', (req, res) => {\n});\n"),
    "ts_fastify_delete": ("typescript", 'fastify.delete("/u", h);\n'),
    "go_unexported_handler": ("go", "func getUser(w http.ResponseWriter, r *http.Request) {\n}\n"),
    "go_gin_handler": ("go", "func getUser(c *gin.Context) {\n}\n"),
    "go_method_handler": ("go", "func (s *S) getUser(w http.ResponseWriter, r *http.Request) {\n}\n"),
}
QUIET = {
    "py_private_def": ("python", "def _helper(x):\n    pass\n"),
    "py_property_setter": ("python", "@x.setter\ndef _v(self, v):\n    pass\n"),
    "py_get_not_decorator": ("python", "y = d.get('a')\n"),
    "py_commented": ("python", '# @app.route("/u")\n'),
    "js_map_get": ("javascript", "const v = cache.get('k');\n"),
    "js_app_get_setting": ("javascript", "const v = app.get(key);\n"),
    "ts_other_receiver": ("typescript", "const v = store.get('k');\n"),
    "go_unexported_plain": ("go", "func helper(x int) int {\n\treturn x\n}\n"),
    "go_call_not_decl": ("go", "\thttp.HandleFunc(\"/u\", getUser)\n"),
}


def _count(lang, text):
    counts, *_ = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).coding_analysis([(lang, text, 0)])
    return counts["api"]


@pytest.mark.parametrize("lang,text", list(FIRES.values()), ids=list(FIRES))
def test_missed_handler_forms_fire(lang, text):
    assert _count(lang, text) >= 1, text


@pytest.mark.parametrize("lang,text", list(QUIET.values()), ids=list(QUIET))
def test_near_misses_stay_quiet(lang, text):
    assert _count(lang, text) == 0, text


def test_redos_immune():
    cases = {
        "python": "@a" + ".b" * 4000 + " " * 5000 + "\n",
        "javascript": "app.get" + " " * 6000 + "x\n",
        "go": "func " + "a" * 6000 + " (" + "(" * 3000 + "\n",
    }
    for lang, text in cases.items():
        t = time.perf_counter()
        _count(lang, text)
        assert time.perf_counter() - t < 5
