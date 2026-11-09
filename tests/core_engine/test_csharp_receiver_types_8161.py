"""#8161 (PR 5, X3 for C#): a receiver's declared type (`JsonWriter writer`, `var w = new JTokenWriter()`, a field)
picks its class's method: `writer.WriteStartArray()` is JsonWriter's, not the same-named override in a subclass the
caller's file happens to be near (Newtonsoft.Json vs scip-dotnet)."""

from gitgalaxy.core import overload_types as O
from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _parse(code: str) -> dict:
    return StructuralExtractor("csharp", LANGUAGE_DEFINITIONS).splice(code, "")


WRITER = "namespace N\n{\n    public abstract class JsonWriter\n    {\n        public virtual void WriteStartArray()\n        {\n        }\n    }\n}\n"
TOKEN = (
    "namespace N\n{\n    public class JTokenWriter : JsonWriter\n    {\n"
    "        public override void WriteStartArray()\n        {\n        }\n    }\n}\n"
)
ARRAY = (
    "namespace N\n{\n    public class JArray\n    {\n"
    "        private JsonWriter _out;\n"
    "        public void WriteTo(JsonWriter writer)\n        {\n            writer.WriteStartArray();\n        }\n"
    "        public void Copy()\n        {\n            var w = new JTokenWriter();\n            w.WriteStartArray();\n"
    "        }\n"
    "        public void Flush()\n        {\n            _out.WriteStartArray();\n        }\n    }\n}\n"
)


def test_declared_receiver_types():
    text = "void F(JsonWriter writer, int n, decimal? d) { var w = new JTokenWriter(); string[] xs = null; }"
    got = O.receiver_types(text, {"writer", "w", "n", "d", "xs", "this._out", "_out"}, {"_out": "JsonWriter"}, "csharp")
    assert got == {
        "writer": "JsonWriter",
        "w": "JTokenWriter",
        "n": "",
        "d": "",
        "xs": "",
        "this._out": "JsonWriter",
        "_out": "JsonWriter",
    }


def test_a_typed_receiver_reaches_its_class_method():
    files = {"src/JsonWriter.cs": WRITER, "src/JTokenWriter.cs": TOKEN, "src/JArray.cs": ARRAY}
    parsed = []
    for path, code in files.items():
        p = _parse(code)
        parsed.append({"path": path, "lang_id": "csharp", "functions": p["functions"], "classes": p["classes"]})
    sites, _ = resolve_calls(parsed)
    got = sorted(
        (s["src_name"].rsplit(".", 1)[-1], s["step"], s["dst_path"]) for s in sites if s["callee"] == "WriteStartArray"
    )
    assert got == [
        ("Copy", "typed", "src/JTokenWriter.cs"),  # `var w = new JTokenWriter()`
        ("Flush", "typed", "src/JsonWriter.cs"),  # a field
        ("WriteTo", "typed", "src/JsonWriter.cs"),  # a parameter
    ]
