"""gitgalaxy#8863: the Java keyword families count the construct their contract names (closures, bitwise, regex, time)."""

from __future__ import annotations

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS as LD


def _hits(rule: str, text: str) -> list[str]:
    return [m.group(0).strip() for m in LD["java"]["rules"][rule].finditer(text)]


@pytest.mark.parametrize(
    "text",
    [
        "list.forEach(x -> use(x));",
        "Runnable r = () -> run();",
        "map.computeIfAbsent(k, (a) -> new ArrayList<>());",
        "return x -> x + 1;",
        "    y -> y * 2)",
        "foo(a, (b, c) -> b + c);",
    ],
)
def test_a_lambda_is_a_closure(text):
    assert len(_hits("closures", text)) == 1


@pytest.mark.parametrize(
    "text",
    [
        "return this::shouldExclude;",
        "list.stream().map(Foo::bar).toList();",
        "Supplier<X> s = X::new;",
        "case FOO -> run();",
        "    case A, B -> run();",
        "default -> throw new IllegalStateException();",
        '@Contract("_, _, true -> !null")',
        "@Contract(pure = true)",
    ],
)
def test_a_method_reference_switch_arm_or_annotation_string_is_not_a_closure(text):
    assert _hits("closures", text) == []


@pytest.mark.parametrize(
    "text",
    [
        "int m = flags | MASK;",
        "mods |= Opcodes.ACC_STATIC;",
        "x = (a & b) ^ c;",
        "int v = bits & 0xFF;",
        "int v = mask(x) | Flag.A;",
    ],
)
def test_a_bitwise_and_or_between_operands_counts(text):
    assert _hits("bitwise_ops", text)


@pytest.mark.parametrize(
    "text",
    [
        "if (a && b || c) {}",
        "} catch (IOException | SQLException e) {",
        "} catch (IOException | SQLException | RuntimeException e) {",
        "<T extends Comparable<T> & Serializable> void f() {}",
        "class A<T extends B & C> {}",
        "Map<String, List<X>> m;",
    ],
)
def test_logical_operators_multi_catch_and_generic_bounds_are_not_bitwise(text):
    assert _hits("bitwise_ops", text) == []


def test_regex_counts_pattern_entry_points_only():
    assert _hits("regex_execution", 'Pattern p = Pattern.compile("a+");') == ["Pattern.compile"]
    assert _hits("regex_execution", 'Pattern.matches("a", s);') == ["Pattern.matches"]
    assert _hits("regex_execution", "if (ClassNameFilter.MISSING.matches(name, loader)) {}") == []
    assert _hits("regex_execution", 'Pattern.quote("a.b");') == []
    assert _hits("regex_execution", "if (name.matches(re)) {}") == ["name.matches("]


@pytest.mark.parametrize(
    "text",
    [
        "long t = System.currentTimeMillis();",
        "Instant now = Instant.now();",
        "Duration d = Duration.ofSeconds(3);",
        "Date d = new Date();",
        "LocalDate.parse(s);",
        "ChronoUnit.DAYS.between(a, b);",
        "Calendar c = Calendar.getInstance();",
        "DateTimeFormatter.ISO_DATE.format(t);",
    ],
)
def test_a_clock_calendar_or_duration_call_is_time(text):
    assert _hits("time_date_logic", text)


@pytest.mark.parametrize(
    "text",
    [
        "private Integer getSeconds(Duration cachePeriod) {",
        "Duration timeout = cfg.getTimeout();",
        "public Property<Duration> getTimeout() {",
    ],
)
def test_a_duration_type_name_alone_is_not_time(text):
    assert _hits("time_date_logic", text) == []
