"""#9330: Kotlin keyword-family validity on the pinned crucible: `closures` (a lambda opens at its `{`, with or without a
named parameter) and `doc` (a KDoc block documents the declaration directly below it, not a function further down)."""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
_CLOSURES = LANGUAGE_DEFINITIONS["kotlin"]["rules"]["closures"]


def _fires(src: str) -> bool:
    return bool(_CLOSURES.search(_PRISM.split_streams(src, "kotlin")["code_stream"]))


@pytest.mark.parametrize(
    "src",
    [
        "val a = xs.map { x -> x + 1 }",
        "val a = xs.map { it.call }",
        "val b = runBlocking {\n    work()\n}",
        "xs.also {\n    log(it)\n}",
        "val c by lazy {\n    build()\n}",
        "synchronized(this) {\n    count++\n}",
        'check(ok) { "message" }',
        "with(config) {\n    apply()\n}",
        "fun t() = runBlocking {\n    go()\n}",
        "val ctx = runApplication<Config> {\n    setEnv(e)\n}",
    ],
)
def test_lambda_forms_count(src):
    assert _fires(src), src


@pytest.mark.parametrize(
    "src",
    [
        "fun f(a: Int): Int {\n    return a\n}",
        "fun f(a: Int): Converter.Factory {\n    return g()\n}",
        "fun Type.name(vararg t: KClass<*>): Type.Augmented {\n    return this\n}",
        "class Foo(val a: Int) : Base(a) {\n    val x = 1\n}",
        "class Foo : Bar {\n    val x = 1\n}",
        "val o = object : Runnable {\n    override fun run() {}\n}",
        "if (a > 1) {\n    go()\n}",
        "} else {\n    stop()\n}",
        "try {\n    go()\n} finally {\n    stop()\n}",
        "when (x) {\n    is Foo -> a()\n    else -> b()\n}",
        "for (i in xs) {\n    go(i)\n}",
        "private fun promote(\n    a: Int,\n) {\n    go()\n}",
        "class Holder {\n    init {\n        go()\n    }\n    companion object {\n        const val A = 1\n    }\n}",
    ],
)
def test_declaration_and_control_blocks_do_not_count(src):
    assert not _fires(src), src


def _docs(src: str) -> dict[str, bool]:
    st = _PRISM.split_streams(src, "kotlin")
    out = StructuralExtractor("kotlin", LANGUAGE_DEFINITIONS).splice(
        code_stream=st["code_stream"],
        comment_stream=st["comment_stream"],
        raw_content=src,
        positional_comment_stream=_PRISM.split_positional_comment_stream(src, "kotlin"),
    )
    return {f["name"]: bool(f.get("is_documented")) for f in out["functions"]}


_CLASS = """
/**
 * The class doc.
 * @author someone
 */
class Foo {

    private var context = Ctx()

    @AfterEach
    fun cleanUp() {
        context.close()
    }

    /** A property doc. */
    private val q = 1

    constructor(e: Int?) : this() {
        this.e = e
    }

    /** Documented. */
    @Synchronized
    fun documented() = 1

    /**
     * Documented, blank line between.
     */

    fun spaced() = 2

    // a line comment
    fun bare() = 3
}
"""


def test_doc_belongs_to_the_declaration_directly_below():
    docs = _docs(_CLASS)
    assert docs["cleanUp"] is False  # the class KDoc is not its doc
    assert docs["constructor"] is False  # nor is the property KDoc above it
    assert docs["documented"] is True  # annotation between doc and fun is fine
    assert docs["spaced"] is True
    assert docs["bare"] is False


def test_file_header_doc_above_an_import_still_documents():
    src = "/** @param a probe */\n// note\nimport a.b\n\nfun entry(a: Int): Int {\n    return a\n}\n"
    assert _docs(src)["entry"] is True


# ---- the five okhttp-measured cells (exploratory; the pinned crucible has no cases for them) ----


def _rule_fires(family: str, src: str) -> bool:
    return bool(
        LANGUAGE_DEFINITIONS["kotlin"]["rules"][family].search(_PRISM.split_streams(src, "kotlin")["code_stream"])
    )


_FAMILY_CASES = {
    "time_date_logic": (
        [
            "val t = System.nanoTime()",
            "val d = Duration.ofSeconds(1)",
            "val m = unit.toMillis(5)",
            "val w = 5.seconds",
            "val c = Calendar.getInstance()",
            "val f = SimpleDateFormat(p)",
            "measureTimeMillis { go() }",
        ],
        ["val s = Thread.currentThread()", "val timeout = 5", "val d = DateUtils.x()", "val n = nanoTimeLabel"],
    ),
    "io": (
        [
            "val f = File(path)",
            "val s = url.openStream()",
            "val r = socket.inputStream",
            "file.appendText(x)",
            "val l = readLine()",
            "Files.readAllBytes(p)",
        ],
        [
            "fun f(file: File): Int",
            "import java.io.File",
            "val c: HttpURLConnection? = null",
            "val s = x.inputStreamName",
        ],
    ),
    "panics_and_aborts": (
        ["throw IllegalStateException()", 'TODO("later")', 'error("bad")', "exitProcess(1)", "System.exit(2)"],
        ["return null", "return -1", 'log.error("x")', "val e = errorCount", "assertEquals(a, b)"],
    ),
    "bitwise_ops": (
        ["val a = x and 0xff", "val b = x or y", "val c = x shl 8", "val d = x.inv()", "val e = a xor b"],
        ["val a = Foo(and = 1)", "// a or b\nval x = 1", "val c = x && y"],
    ),
    "regex_execution": (
        [
            "val r = Regex(p)",
            "val r = s.toRegex()",
            "val m = Pattern.compile(p)",
            "val m = r.matchEntire(s)",
            "val m = p.matcher(s)",
        ],
        ["val m = xs.find { it > 1 }", "val ok = s.matches(p)", "val r = RegexUtils.compile(p)"],
    ),
}


@pytest.mark.parametrize("family", sorted(_FAMILY_CASES))
def test_okhttp_family_rules_count_the_named_construct(family):
    yes, no = _FAMILY_CASES[family]
    for src in yes:
        assert _rule_fires(family, src), (family, src)
    for src in no:
        assert not _rule_fires(family, src), (family, src)
