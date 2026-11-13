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


BSON = (
    "namespace N\n{\n    public class BsonReader\n    {\n        private BinaryReader _reader;\n"
    "        public byte ReadByte()\n        {\n            return _reader.ReadByte();\n        }\n"
    '        public bool Space(char c)\n        {\n            return char.IsWhiteSpace(c) && StringUtils.IsWhiteSpace("x");\n        }\n'
    "    }\n"
    "    public static class StringUtils\n    {\n"
    "        public static bool IsWhiteSpace(string s)\n        {\n            return s.Length == 0;\n        }\n"
    "        public static byte ReadByte(this BinaryReader r)\n        {\n            return 0;\n        }\n    }\n}\n"
)


def test_a_library_typed_receiver_reaches_no_same_named_repo_method():
    p = _parse(BSON)
    sites, _ = resolve_calls(
        [{"path": "src/Bson.cs", "lang_id": "csharp", "functions": p["functions"], "classes": p["classes"]}]
    )
    got = {
        (s["src_name"].rsplit(".", 1)[-1], s["callee"], s["qualifier"], s["dst_line"]) for s in sites if s["dst_line"]
    }
    # `_reader` is a BinaryReader: BsonReader.ReadByte is no candidate, the extension method on BinaryReader is
    assert {(src, callee, line) for src, callee, _, line in got if callee == "ReadByte"} == {
        ("ReadByte", "ReadByte", 21)
    }
    # `char.IsWhiteSpace` is the library's; `StringUtils.IsWhiteSpace` the repo's
    assert {(q, line) for src, callee, q, line in got if callee == "IsWhiteSpace"} == {("StringUtils", 17)}
