"""Swift `closures`, `decorators` and `thread_sleeps` read their contracts (#8863 red cells)."""

import pytest

from gitgalaxy.standards.language_standards.languages import swift as swift_lang


def _rule(name):
    for obj in vars(swift_lang).values():
        if isinstance(obj, dict) and name in obj and "thread_sleeps" in obj:
            return obj[name]
        if isinstance(obj, dict):
            for v in obj.values():
                if isinstance(v, dict) and name in v and "thread_sleeps" in v:
                    return v[name]
    raise AssertionError(f"swift {name} rule not found")


@pytest.mark.parametrize(
    "src",
    [
        "{ result in print(result) }",
        "{ [weak self] data in self?.use(data) }",
        "{ [self] in run() }",
        "{ (a: Int, b: Int) -> Int in a + b }",
        "{ x -> Int in x + 1 }",
        "items.map { $0 * 2 }",
        "{\n    $0.finish()\n}",
    ],
)
def test_closures_counts_anonymous_callables(src):
    assert _rule("closures").search(src)


@pytest.mark.parametrize("src", ["if x { return }", "func f() { run() }", "let d = [1: 2]", "$0"])
def test_closures_ignores_blocks(src):
    assert not _rule("closures").search(src)


@pytest.mark.parametrize(
    "src", ["@available(iOS 15, *)", "@discardableResult", "public @MainActor func f()", "@Sendable func g()"]
)
def test_decorators_counts_declaration_attributes(src):
    assert _rule("decorators").search(src)


@pytest.mark.parametrize(
    "src",
    [
        "func f(done: @escaping () -> Void)",
        "func f(x: @autoclosure () -> Int)",
        "var h: (queue: Q, handler: @Sendable (Int) -> Void)?",
        "func f(c: @escaping @Sendable () -> Void)",
        "var all: [@Sendable () -> Void] = []",
        "// see RFC @ https://example.com",
    ],
)
def test_decorators_ignores_type_attributes(src):
    assert not _rule("decorators").search(src)


@pytest.mark.parametrize(
    "src",
    [
        "sleep(1)",
        "usleep(500)",
        "try await Task.sleep(nanoseconds: 1)",
        "q.asyncAfter(deadline: .now())",
        "Timer.scheduledTimer(withTimeInterval: 1",
    ],
)
def test_thread_sleeps_counts_blocking_calls(src):
    assert _rule("thread_sleeps").search(src)


@pytest.mark.parametrize("src", ["retry(withDelay: result.delay)", "let delay = 3", "sleepyHead = true"])
def test_thread_sleeps_ignores_non_calls(src):
    assert not _rule("thread_sleeps").search(src)
