"""Scala keyword-family validity (#9332, part of #8863): `closures` and `bitwise_ops` count only their own construct.

Second slice: `debug_prints` and `io` stop over-counting; `thread_sleeps`, `time_date_logic` and `regex_execution` see the
call forms they missed (the unpinned kafka cells).

`closures` counted every `=>` (a `case` match arm, a function-type arrow) and `_` in a pattern; `bitwise_ops` counted `|` in a
pattern alternative, a `stripMargin` bar and text such as `[a|b]`.
"""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_RULES = LANGUAGE_DEFINITIONS["scala"]["rules"]


def _count(rule: str, src: str) -> int:
    return len(_RULES[rule].findall(src))


@pytest.mark.parametrize(
    "src",
    [
        "val f = (x: Int) => x + 1",
        "xs.map(x => x * 2)",
        "xs.foreach { x =>\n  println(x)\n}",
        "xs.map(_.name)",
        "xs.map(_ + 1)",
        "f(_, 2)",
        "xs.collect { case Some(v) => v }",
        "val g = () => 42",
    ],
)
def test_closures_counts_an_anonymous_function(src):
    assert _count("closures", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        "x match {\n  case Some(v) => v\n  case None => 0\n}",
        "  case NonFatal(_) => null",
        "  case _ =>\n    fail()",
        "def foreach(record: Map[String, Any])(f: Any => Unit): Unit = ()",
        "  callback: ((Errors, Guard)) => Unit,",
        "  isStray: Log => Boolean): Log = {",
        "type Handler = Int => Unit",
    ],
)
def test_closures_ignores_match_arms_and_function_types(src):
    assert _count("closures", src) == 0


@pytest.mark.parametrize(
    "src",
    [
        "val b = bytes(i) & 0xF",
        "val hi = (n >> 8) & 0xFF",
        "val m = a ^ b",
        "val s = a << 2",
        "val c = ~mask",
        "val o = flags | other",
        "  case x if x == A | x == B => 1",
    ],
)
def test_bitwise_counts_an_operator_between_values(src):
    assert _count("bitwise_ops", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        "  case Errors.A | Errors.B =>\n    fail()",
        "  case Errors.A |\n       Errors.B =>",
        "  case e @ (_: IllegalStateException | _: IOException) =>",
        '      |          05  A PIC X\n      |""".stripMargin',
        's" buffer [actual|requested]: [$a|$b]"',
        "val ok = a && b || c",
        "p ~ q",
    ],
)
def test_bitwise_ignores_patterns_text_and_combinators(src):
    assert _count("bitwise_ops", src) == 0


@pytest.mark.parametrize(
    "src",
    [
        'println("x")',
        'print("x")',
        'printf("%d", n)',
        'Console.err.println("x")',
        "System.out.println(x)",
        "System.err.printf(f, x)",
    ],
)
def test_debug_prints_counts_a_console_call(src):
    assert _count("debug_prints", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        "writer.print(x)",
        "out.println(line)",
        "def print(x: Int): Unit = ()",
        "xs.foreach(println)",
        "val sprint = 1",
    ],
)
def test_debug_prints_ignores_writers_and_declarations(src):
    assert _count("debug_prints", src) == 0


@pytest.mark.parametrize(
    "src",
    [
        'Source.fromFile("a")',
        "Files.write(p, bytes)",
        "new FileWriter(f)",
        "new java.io.FileInputStream(f)",
        "new ServerSocket(9)",
        "dir.listFiles()",
        "val l = readLine()",
        "Http().singleRequest(r)",
    ],
)
def test_io_counts_a_file_or_network_call(src):
    assert _count("io", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        "def f(file: java.io.File): Int = 1",
        "val b: java.nio.ByteBuffer = x",
        "val s = SocketServerConfigs.LISTENERS_CONFIG",
        "val src = Source.single(1)",
        "val h: HttpResponse = r",
    ],
)
def test_io_ignores_type_and_package_names(src):
    assert _count("io", src) == 0


@pytest.mark.parametrize(
    "src",
    ["Thread.sleep(10)", "time.sleep(10)", "TimeUnit.SECONDS.sleep(1)", "Await.result(f, 1.second)", "delay(5)"],
)
def test_thread_sleeps_counts_any_receiver(src):
    assert _count("thread_sleeps", src) >= 1


@pytest.mark.parametrize("src", ["val sleeping = true", "def sleepMs = 5", "val s = sleeper"])
def test_thread_sleeps_ignores_names(src):
    assert _count("thread_sleeps", src) == 0


@pytest.mark.parametrize(
    "src",
    [
        "Instant.now()",
        "System.nanoTime()",
        "Duration.ofMillis(5)",
        "LocalDateTime.now",
        "d.toMillis",
        "val t = 5.seconds",
        "Deadline.now",
        "new Date()",
    ],
)
def test_time_date_logic_counts_a_clock_or_duration(src):
    assert _count("time_date_logic", src) >= 1


@pytest.mark.parametrize("src", ["val seconds = 5", "val x = 1.5", "val period = 3", "def millis(x: Int) = x"])
def test_time_date_logic_ignores_plain_names_and_numbers(src):
    assert _count("time_date_logic", src) == 0


@pytest.mark.parametrize(
    "src",
    ["Pattern.compile(p)", "Pattern.matches(p, s)", "p.matcher(s)", "r.findFirstMatchIn(s)", "r.replaceFirstIn(s, x)"],
)
def test_regex_execution_counts_a_regex_call(src):
    assert _count("regex_execution", src) >= 1


@pytest.mark.parametrize("src", ["val pattern = 3", "val m = matcher", "def compile(x: Int) = x"])
def test_regex_execution_ignores_names(src):
    assert _count("regex_execution", src) == 0
