"""
Regression tests for Python call-graph comparison ledger cells:
- Nested `class Model(BaseModel):` inside a function body is not a call to `Model`.
- Nested `def`/`async def` with a multi-line bracketed return annotation keeps its
  full body span, attributing its calls to the nested unit instead of the outer one.
- Cross-newline `(a, b) = ...` following an identifier or `False`/`True`/`None` on
  a preceding line is not a call.
"""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _functions(code: str) -> dict[str, dict]:
    units = StructuralExtractor("python", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {u["name"]: u for u in units}


def test_nested_class_header_is_not_a_call():
    code = (
        "def test_model():\n"
        "    class EmbeddedModel(BaseModel):\n"
        "        x: int\n"
        "\n"
        "    class Model(BaseModel):\n"
        "        item: EmbeddedModel\n"
        "\n"
        "    return EmbeddedModel(x=1)\n"
    )
    calls = _functions(code)["test_model"]["calls_out_to"]
    assert "Model" not in calls
    assert "EmbeddedModel" in calls


def test_multiline_return_annotation_preserves_nested_function_span():
    code = (
        "async def app(scope):\n"
        "    async def _sse_producer_cm() -> AsyncIterator[\n"
        "        ObjectReceiveStream[bytes]\n"
        "    ]:\n"
        "        async with anyio.create_task_group() as tg:\n"
        "            tg.start_soon(worker)\n"
        "            yield stream\n"
        "    return await run_app(scope)\n"
    )
    funcs = _functions(code)
    assert "_sse_producer_cm" in funcs
    inner = funcs["_sse_producer_cm"]
    outer = funcs["app"]
    assert inner["start_line"] == 2
    assert inner["end_line"] >= 7
    assert "create_task_group" in inner["calls_out_to"]
    assert "start_soon" in inner["calls_out_to"]
    assert "create_task_group" not in outer["calls_out_to"]
    assert "start_soon" not in outer["calls_out_to"]
    assert "run_app" in outer["calls_out_to"]


def test_cross_newline_tuple_unpack_is_not_a_call():
    code = (
        "def unpack(flag, a, b):\n"
        "    if flag:\n"
        "        x = False\n"
        "\n"
        "        (l, rl) = (a, b)\n"
        "    else:\n"
        "        m1\n"
        "        (d1, d2) = (a, b)\n"
        "    return helper(\n"
        "        a,\n"
        "        b,\n"
        "    )\n"
    )
    calls = _functions(code)["unpack"]["calls_out_to"]
    assert "False" not in calls
    assert "m1" not in calls
    assert "helper" in calls


def test_python_qualifiers_remain_populated():
    code = "def run(client):\n    return client.fetch(\n        1,\n    )\n"
    fn = _functions(code)["run"]
    assert "fetch" in fn["calls_out_to"]
    assert fn.get("calls_out_qualifiers", {}).get("fetch") == ["client"]
