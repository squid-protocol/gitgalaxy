"""#8161 (Y1): a module-level instance (`app = App()`) types its name in every function of the file, also when
no module-level statement calls a method on it (decorators and calls all inside test functions)."""

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

FRAMEWORK = (
    "class App:\n"
    "    def route(self, path):\n        def deco(fn):\n            return fn\n        return deco\n\n"
    "    def run(self):\n        return 1\n\n\n"
    "class Router:\n"
    "    def route(self, path):\n        def deco(fn):\n            return fn\n        return deco\n\n"
    "    def run(self):\n        return 2\n"
)
VIEWS = (
    "from web.framework import App\n\n"
    "app = App()\n"
    "count: int = 0\n\n\n"
    "def test_nested_decorated():\n"
    '    @app.route("/")\n'
    "    def handler():\n        return 1\n\n"
    "    return handler\n\n\n"
    "def test_nested_call():\n"
    "    def inner():\n        return app.run()\n\n"
    "    return inner()\n"
)


def _sites():
    files = []
    for path, code in (("web/framework.py", FRAMEWORK), ("web/test_views.py", VIEWS)):
        parsed = StructuralExtractor("python", LANGUAGE_DEFINITIONS).splice(code, "")
        files.append(
            {"path": path, "lang_id": "python", "functions": parsed["functions"], "classes": parsed["classes"]}
        )
    sites, _ = resolve_calls(files, [{"src": "web/test_views.py", "dst": "web/framework.py"}])
    return files, {(s["kind"], s["src_name"], s["callee"]): (s["step"], s["dst_line"]) for s in sites}


def test_module_unit_types_every_module_binding():
    files, _ = _sites()
    module = next(fn for fn in files[1]["functions"] if fn["name"] == "__global_context__")
    assert module["calls_out_receiver_types"]["app"] == "App"


def test_functions_see_the_module_instance_type():
    _, sites = _sites()
    assert sites[("decorator", "handler", "route")] == ("typed", 2)  # App.route, not Router.route
    assert sites[("call", "inner", "run")] == ("typed", 7)
