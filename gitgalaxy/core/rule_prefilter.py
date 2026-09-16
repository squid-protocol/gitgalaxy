# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at [https://polyformproject.org/licenses/noncommercial/1.0.0/](https://polyformproject.org/licenses/noncommercial/1.0.0/)
# ==============================================================================
"""
Required-literal prefilter derivation for the coding_analysis rule pass (#3069).

`derive_literal_gate(pattern)` inspects a compiled rule regex and returns a
"one-of" literal gate: a set of plain substrings such that *if none of them
occur in a segment, the regex cannot match that segment*. coding_analysis can
then gate each rule's full-segment `finditer` sweep behind a handful of
C-speed `str in str` membership checks -- the generalization of #3063's
`'=' in line` var-decl gate to the whole ~40-rule pass.

The gate is strictly ONE-SIDED: a passing gate proves nothing (the regex still
runs), and a rejecting gate must be *provably* equivalent to zero matches.
Everything in this module is therefore biased toward returning None ("no gate,
run the rule as today") rather than toward cleverness:

- The AST walk is an opcode WHITELIST. Any node kind this module was not
  written against -- including whatever a future Python adds -- aborts the
  whole derivation. A blacklist would silently mis-gate new constructs.
- Constructs that consume no fixed text (character classes, `.`, bounded-zero
  repeats, lookarounds, backrefs, anchors) contribute nothing; they only
  terminate the literal run being accumulated. Positive lookaheads DO imply
  required text, but harvesting them is deliberately deferred -- the rules
  that motivate #3069 gate fine without it.
- Case-insensitive literals are matched against a `fold_haystack()`-folded
  haystack and are only emitted when pure ASCII. `casefold()` (not `lower()`)
  because re's IGNORECASE folds LONG S (U+017F) onto 's' and the KELVIN
  SIGN (U+212A) onto 'k', and only casefold maps both haystack chars onto
  the ASCII literal.
  casefold alone is still not enough -- see fold_haystack for the two
  Turkish-i repairs. Non-ASCII literals are dropped outright rather than
  reasoning about full-vs-simple folding asymmetries ('ß'/'ẞ').
- A scoped `(?i:...)` conservatively widens the WHOLE gate to
  case-insensitive. Folding a case-sensitive literal is sound -- it can only
  make the gate pass more often, never reject a real match.

`re._parser` (3.11+) with an `sre_parse` fallback (<=3.10; also the escape
hatch if the private module moves again) -- both produce the same node shapes.
If neither import works, every derivation returns None and the engine simply
runs ungated, byte-identical to pre-#3069 behavior.
"""

import re
from typing import Any, Optional

try:
    from re import _parser as _sre_parser  # type: ignore[attr-defined]  # Python 3.11+
except ImportError:  # pragma: no cover -- exercised only on <=3.10
    try:
        import sre_parse as _sre_parser  # type: ignore[no-redef]
    except ImportError:
        _sre_parser = None  # type: ignore[assignment]

try:
    from re import _constants as _sre_constants  # type: ignore[attr-defined]  # Python 3.11+
except ImportError:  # pragma: no cover -- exercised only on <=3.10
    try:
        import sre_constants as _sre_constants  # type: ignore[no-redef]
    except ImportError:
        _sre_constants = None  # type: ignore[assignment]

# A gate is (literals, needs_casefold): literals ordered shortest-first so the
# common case -- a hot rule whose gate passes -- short-circuits `any()` on the
# cheapest (and statistically most frequent) substring probe.
Gate = tuple[tuple[str, ...], bool]

# Opcodes that consume no derivable fixed text. They contribute nothing to the
# gate and merely break the current literal run. ATOMIC_GROUP/POSSESSIVE_REPEAT
# only exist on 3.11+; getattr keeps the 3.9/3.10 import path alive.
_C = _sre_constants
if _C is not None:
    _LITERAL = _C.LITERAL
    _BRANCH = _C.BRANCH
    _SUBPATTERN = _C.SUBPATTERN
    _MAX_REPEAT = _C.MAX_REPEAT
    _MIN_REPEAT = _C.MIN_REPEAT
    _POSSESSIVE_REPEAT = getattr(_C, "POSSESSIVE_REPEAT", None)
    _ATOMIC_GROUP = getattr(_C, "ATOMIC_GROUP", None)
    _BARREN_OPS = frozenset(
        op
        for op in (
            _C.NOT_LITERAL,
            _C.ANY,
            _C.IN,
            _C.AT,
            _C.GROUPREF,
            _C.GROUPREF_EXISTS,
            _C.ASSERT,
            _C.ASSERT_NOT,
            getattr(_C, "FAILURE", None),
        )
        if op is not None
    )


# sre's own extra case-equivalence table (re._casefix, 3.11+): the pairs
# IGNORECASE honors beyond simple per-char tolower (dotless i, long s, Kelvin
# sign, the Greek symbol letters, the historic Cyrillic letterforms, ...).
# _ci_literal_is_foldsafe enumerates a literal char's case class through it.
# Missing on <=3.10 (sre_compile._equivalences has the same data but a less
# convenient shape) -- fall back to an empty table, which makes the safety
# check refuse every non-ASCII literal, i.e. exactly the old conservative
# behavior.
try:
    from re import _casefix  # type: ignore[attr-defined]

    _EXTRA_CASES: "dict[int, list[int]]" = _casefix._EXTRA_CASES
except ImportError:  # pragma: no cover -- exercised only on <=3.10
    _EXTRA_CASES = {}


def _ci_literal_is_foldsafe(lit: str) -> bool:
    """Can this casefolded literal be matched against fold_haystack() output?

    Per char c, the danger is a haystack character X that IGNORECASE treats as
    equivalent to c but whose casefold is NOT exactly c -- then a real match
    in the original text has no contiguous c in the folded haystack and the
    gate would falsely reject (the dotted-capital-I failure mode). ASCII chars
    are safe by construction: casefold restores every ASCII case class except
    the two Turkish-i forms, which fold_haystack repairs explicitly. For a
    non-ASCII c we enumerate its case class -- itself, its single-char
    uppercase, and sre's extra-case equivalents (transitively, one hop) -- and
    demand every member casefold back to exactly c. Chars whose uppercase
    expands (the 'ß' -> 'SS' family) are refused outright: their class isn't
    enumerable this way. The only class member this enumeration cannot see is
    one reachable solely through a multi-char lower() -- U+0130 is the sole
    such character in Unicode, it lands in the ASCII 'i' class, and
    fold_haystack already repairs it.

    This is what lets the multilingual TODO/FIXME debt rules gate: their
    Cyrillic entries fold 1:1 and pass; a hypothetical 'ß' entry would refuse
    the candidate, never mis-gate it.
    """
    for ch in lit:
        if ch.isascii():
            continue
        upper = ch.upper()
        if len(upper) != 1:
            return False
        variants = {ch, upper}
        for v in tuple(variants):
            variants.update(chr(cp) for cp in _EXTRA_CASES.get(ord(v), ()))
        if any(v.casefold() != ch for v in variants):
            return False
    return True


def fold_haystack(text: str) -> str:
    """Fold a haystack for matching against a case-insensitive gate.

    `casefold()` plus the two repairs the unit suite's Unicode adversarials
    demand. re's IGNORECASE equates ASCII 'i' with BOTH Turkish i forms --
    dotted capital I (U+0130, via simple tolower) and dotless small i
    (U+0131, via sre's _equivalences charset expansion) -- but casefold
    maps U+0130 to 'i'+U+0307 (a combining dot that breaks literal
    contiguity, so 'istanbul' is NOT a substring of the casefolded
    'ISTANBUL'-with-dotted-I) and leaves U+0131 untouched. Both rewrites only ever edit non-ASCII characters, so no
    ASCII-literal occurrence can be destroyed: the repairs may widen the
    gate (false accept -- harmless), never narrow it.
    """
    return text.casefold().replace("i\u0307", "i").replace("\u0131", "i")


class _Ungateable(Exception):
    """Raised on any AST node outside the whitelist: the rule runs ungated."""


# A candidate is one independently-sound "one-of" requirement discovered in the
# tree: (set of literals, any-of-them-derived-under-IGNORECASE). Concatenation
# yields many candidates (each literal run is separately required); the caller
# picks the best one at the end.
_Candidate = tuple[frozenset[str], bool]


def _pick_best(candidates: list[_Candidate]) -> Optional[_Candidate]:
    """Fewest alternatives first (fewer haystack scans), then longest minimum
    literal (rarer substring => more rejections). Every candidate is
    independently sound, so this is pure policy, not correctness."""
    if not candidates:
        return None
    return min(candidates, key=lambda c: (len(c[0]), -min(len(lit) for lit in c[0])))


def _walk_seq(seq: Any, ci: bool) -> list[_Candidate]:
    """Collect every candidate requirement in a concatenation sequence.

    A match of the sequence matches every node in order, so each completed
    literal run and each fully-covered BRANCH is a valid gate on its own.
    """
    candidates: list[_Candidate] = []
    run: list[str] = []

    def _flush() -> None:
        if run:
            candidates.append((frozenset(("".join(run),)), ci))
            run.clear()

    for op, av in seq:
        if op is _LITERAL:
            run.append(chr(av))
            continue
        _flush()
        if op in _BARREN_OPS:
            continue
        if op is _BRANCH:
            # One-of across alternatives: every branch must contribute a
            # requirement or the node contributes nothing (an empty branch in
            # `(foo|)` can match zero text, so nothing inside the group is
            # required -- but sibling nodes outside it still gate).
            _, branches = av
            merged: set[str] = set()
            merged_ci = False
            for branch in branches:
                best = _pick_best(_walk_seq(branch, ci))
                if best is None:
                    break
                merged |= best[0]
                merged_ci |= best[1]
            else:
                if merged:
                    candidates.append((frozenset(merged), merged_ci))
        elif op is _SUBPATTERN:
            _group, add_flags, del_flags, sub = av
            sub_ci = (ci or bool(add_flags & re.IGNORECASE)) and not (del_flags & re.IGNORECASE)
            candidates.extend(_walk_seq(sub, sub_ci))
        elif op is _MAX_REPEAT or op is _MIN_REPEAT or (_POSSESSIVE_REPEAT is not None and op is _POSSESSIVE_REPEAT):
            rmin, _rmax, sub = av
            # `X{n,m}` with n >= 1 must match X at least once, so X's
            # requirements hold. n == 0 (`?`, `*`) requires nothing.
            if rmin >= 1:
                candidates.extend(_walk_seq(sub, ci))
        elif _ATOMIC_GROUP is not None and op is _ATOMIC_GROUP:
            candidates.extend(_walk_seq(av, ci))
        else:
            raise _Ungateable(str(op))
    _flush()
    return candidates


def derive_literal_gate(pattern: Any, max_literals: int = 80, min_literal_len: int = 2) -> "Optional[Gate]":
    """Derive a one-of literal gate for a compiled rule regex, or None.

    Invariant (the only property callers may rely on): if the gate is not None
    and none of its literals occur in a haystack -- matched against
    `haystack.casefold()` when the second element is True -- then
    `pattern.finditer(haystack)` yields no matches.

    None means "no safe gate found"; the caller must run the rule unfiltered.
    Any internal surprise (unknown opcode, parse failure, exotic flags)
    resolves to None, never to a wrong gate.

    `max_literals`: a one-of set wider than this is refused -- each literal is
    a (short-circuited) C-level scan of the segment. The cap sits above the
    widest useful ruleset gate measured (the multilingual TODO/FIXME debt
    rules derive 40-70 alternatives, and gating those is a measured ~20% of
    the whole C rule pass on a large header): ~70 substring probes over even
    a 1MB segment cost single-digit ms against the hundreds of ms their
    backtracking sweeps cost, and on gate-pass files `any()` short-circuits
    long before the full set is probed.
    `min_literal_len`: sets whose rarest member is shorter than this are
    refused -- ~500 rules bottom out at a bare `'('` or `'#'`, which nearly
    every file contains, so the gate would be pure overhead.
    """
    if _sre_parser is None or _C is None:  # pragma: no cover -- stdlib privates moved
        return None
    try:
        source = pattern.pattern
        flags = pattern.flags
        if not isinstance(source, str) or flags & re.LOCALE:
            return None
        candidates = _walk_seq(_sre_parser.parse(source, flags), bool(flags & re.IGNORECASE))
    except _Ungateable:
        return None
    except Exception:
        # Defensive: a derivation bug must degrade to "ungated", never crash
        # the scan or (worse) mis-gate. The unit suite's live-ruleset property
        # test keeps this branch honest.
        return None

    viable: list[_Candidate] = []
    for literals, needs_casefold in candidates:
        # The length floor is an ASCII-only policy: a 1-char ASCII gate ('(',
        # '#', '=') is present in nearly every file and pure overhead, but a
        # single CJK/Arabic char (the multilingual debt rules' '坑', 'مؤقت'
        # entries) is a high-information probe worth keeping.
        if len(literals) > max_literals or any(len(lit) < min_literal_len and lit.isascii() for lit in literals):
            continue
        if needs_casefold:
            folded = frozenset(lit.casefold() for lit in literals)
            if not all(_ci_literal_is_foldsafe(lit) for lit in folded):
                continue
            literals = folded
        viable.append((literals, needs_casefold))

    best = _pick_best(viable)
    if best is None:
        return None
    literals, needs_casefold = best
    return tuple(sorted(literals, key=lambda lit: (len(lit), lit))), needs_casefold
