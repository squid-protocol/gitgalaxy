"""#8161 (J2): an ambiguous `overload` row's guess is an overload the call's argument count fits (it was the
class's first overload, whatever its arity), and the row joins the FILE graph: every candidate overload is in
that file, on one class, so only which overload is unknown. It still never joins the function graph."""

from gitgalaxy.core.call_resolver import CONFIDENT_RESOLUTIONS, confident_file_pairs, resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

ARRAYS = (
    "package p;\n"
    "public class ArrayU {\n"
    "    public static int indexOf(int[] a, int v, int from) { return from; }\n"  # 3
    "    public static int indexOf(int[] a, int v) { return 0; }\n"  # 4
    "    public static int indexOf(long[] a, long v) { return 1; }\n"  # 5
    "}\n"
)
CLIENT = (
    "package p;\n"
    "public class Client {\n"
    "    boolean contains(int[] array, int v) { return ArrayU.indexOf(array, v) >= 0; }\n"
    "}\n"
)


def _sites():
    files = []
    for path, code in (("src/p/ArrayU.java", ARRAYS), ("src/p/Client.java", CLIENT)):
        parsed = StructuralExtractor("java", LANGUAGE_DEFINITIONS).splice(code, "")
        files.append({"path": path, "lang_id": "java", "functions": parsed["functions"], "classes": parsed["classes"]})
    sites, _ = resolve_calls(files)
    return [s for s in sites if s["callee"] == "indexOf"]


def test_overload_guess_has_the_calls_argument_count():
    (row,) = _sites()
    assert row["step"] == "overload"
    assert row["resolution"] not in CONFIDENT_RESOLUTIONS
    assert row["dst_line"] in (4, 5)  # a 2-parameter overload, never the 3-parameter one at line 3


def test_overload_row_joins_the_file_graph():
    assert confident_file_pairs(_sites()) == {("src/p/Client.java", "src/p/ArrayU.java"): 1}
