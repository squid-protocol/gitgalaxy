"""
#3914: `re` for the language modules, with `compile` deferred until a pattern is used.

The registry holds ~2,200 compiled rules across every language, and importing it compiled all of
them -- 2.3 s of the 3.6 s `import gitgalaxy.galaxyscope` -- although a scan uses the rules of the
languages it meets. Every process that scans paid it, and under the `spawn` start method (Windows,
macOS) every extraction worker paid it twice: once importing, once unpickling its config, since a
pickled pattern is recompiled from its source.

The language modules import this module as `re`. Everything but `compile` is the real `re`; `compile`
returns a `LazyPattern`, which holds its source and flags and compiles on first use. It is a
duck-typed `re.Pattern`:

- `.pattern` never compiles (the literal prefilters and the ReDoS fuzzers read it for every rule);
- `.flags` compiles first, because the real value includes the flags written inline, `(?i)`, and
  `re.UNICODE`, which only the compiler works out;
- any matching method (`search`, `finditer`, ...) compiles once, then delegates;
- it pickles as (source, flags) -- a spawned worker compiles only what it uses -- and `copy` /
  `deepcopy` return it, as they return a compiled pattern;
- it equals, and hashes as, the compiled pattern.

`isinstance(p, re.Pattern)` is False for it. The detector materialises its language's rules into
real patterns when it is built (`materialize`), so the per-file hot path runs on real patterns with no
proxy call in between.
"""

from __future__ import annotations

import re as _re
from typing import Any, cast


class LazyPattern:
    __slots__ = ("_compiled", "_flags", "pattern")

    def __init__(self, pattern: Any, flags: int = 0) -> None:
        self.pattern = pattern
        self._flags = int(flags)
        self._compiled: _re.Pattern | None = None

    def compiled(self) -> _re.Pattern:
        c = self._compiled
        if c is None:
            c = self._compiled = _re.compile(self.pattern, self._flags)
        return c

    @property
    def flags(self) -> int:
        return self.compiled().flags

    def __getattr__(self, name: str) -> Any:  # search, match, finditer, groups, groupindex, ...
        return getattr(self.compiled(), name)

    def __reduce__(self) -> Any:
        return (LazyPattern, (self.pattern, self._flags))

    def __copy__(self) -> LazyPattern:
        return self

    def __deepcopy__(self, memo: Any) -> LazyPattern:
        return self

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LazyPattern):
            other = other.compiled()
        return self.compiled() == other

    def __hash__(self) -> int:
        return hash(self.compiled())

    def __repr__(self) -> str:
        return repr(self.compiled())


def compile(pattern: Any, flags: int = 0) -> _re.Pattern[str]:  # noqa: A001 -- stands in for re.compile
    if isinstance(pattern, (_re.Pattern, LazyPattern)):
        return cast(Any, pattern)  # re.compile returns a compiled pattern as it is
    return cast(Any, LazyPattern(pattern, flags))


def is_pattern(value: Any) -> bool:
    """A regex rule, compiled or not yet -- the check a registry audit means by `isinstance(p, re.Pattern)`."""
    return isinstance(value, (_re.Pattern, LazyPattern))


def materialize(value: Any) -> Any:
    """`value` with every LazyPattern in it compiled -- a pattern, or a dict / list / tuple of them.
    A value holding none is returned as the same object, so a caller can tell nothing changed."""
    if isinstance(value, LazyPattern):
        return value.compiled()
    if isinstance(value, (dict, list, tuple)):
        items = list(value.values() if isinstance(value, dict) else value)
        done = [materialize(v) for v in items]
        if all(a is b for a, b in zip(items, done, strict=True)):
            return value
        if isinstance(value, dict):
            return dict(zip(value.keys(), done, strict=True))
        return type(value)(done) if isinstance(value, list) else tuple(done)
    return value


def __getattr__(name: str) -> Any:  # everything else is the real `re`: flags, escape, sub, ...
    return getattr(_re, name)
