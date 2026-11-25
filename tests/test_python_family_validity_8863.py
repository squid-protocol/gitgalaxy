"""Python keyword-family rules after the #8863 validity pass: each family counts what its contract names."""

import pytest

from gitgalaxy.standards.language_standards.languages import python as py_lang


def _rule(key):
    for obj in vars(py_lang).values():
        if isinstance(obj, dict):
            for v in [obj, *[x for x in obj.values() if isinstance(x, dict)]]:
                if key in v and "telemetry" in v:
                    return v[key]
    raise AssertionError(f"python {key} rule not found")


POSITIVE = {
    "high_risk_execution": ["exit(1)", "sys.exit(2)"],
    "telemetry": ["self.log.info('x')", "self._log.warning('x')", "LOG.debug('x')", "logger.error('x')"],
    "thread_sleeps": ["time.sleep(1)", "await anyio.sleep(1)", "sleep(0.5)", "asyncio.sleep(1)"],
    "time_date_logic": [
        "timezone.utcnow()",
        "dt_util.now()",
        "t = gmtime(x)",
        "d.isoformat()",
        "time.time()",
    ],
    "sync_locks": ["lock = threading.Lock()", "self.acquire()", "self.release()", "cond = Condition()"],
    "io": ["open(p)", "f.read(4)", "out.write(b)", "p.mkdir()", "requests.get(u)", "sys.stdout"],
    "concurrency": ["async def f():", "await x", "asyncio.run(m())"],
    "comprehensions": ["[x for x in y]", "(a for a, b in z)", "map(f, xs)", "reduce(f, xs)"],
    "bitwise_ops": ["x = a | b", "m |= 3", "y = a & mask", "z = a << 2"],
}
NEGATIVE = {
    "high_risk_execution": ["self.exit(1)", "platform.system()"],
    "thread_sleeps": ["x = sleeper"],
    "time_date_logic": ["time.sleep(1)", "parts = time.split()"],
    "sync_locks": ["class Event(BaseModel):", "x.release(code)", 'log.warn("Bus Lock Detected")'],
    "io": ["self.open = True", "pool['open']", "self.requests = []", "self.requests[-1].x", "self.socket = s"],
    "comprehensions": ['log("for the schedule runtime")', 'error(pos, "for-from loop (x)")'],
    "bitwise_ops": [
        "def f(a: int | str) -> None:",
        "    a: A | B,",
        "    | Foo = Default(x),",
        "def f() -> X | Y:",
        "x: int | None = None",
        'get("/?a=1&b=2")',
        'code.putln("&%s")',
        ">>> print(x)",
    ],
}


@pytest.mark.parametrize(
    ("key", "line"), [(k, line) for k, lines in POSITIVE.items() for line in lines], ids=lambda v: str(v)[:30]
)
def test_contract_forms_count(key, line):
    assert _rule(key).search(line)


@pytest.mark.parametrize(
    ("key", "line"), [(k, line) for k, lines in NEGATIVE.items() for line in lines], ids=lambda v: str(v)[:30]
)
def test_other_constructs_do_not_count(key, line):
    assert not _rule(key).search(line)


def test_embedded_python_log_receiver_counts():
    from gitgalaxy.standards.language_standards.languages import embedded_python as emb

    rx = emb.DEFINITION["rules"]["telemetry"]
    assert rx.search('log.info("ACT", "x")') and rx.search("self._log.warn(m)")
    assert not rx.search("catalog.info = 1")
