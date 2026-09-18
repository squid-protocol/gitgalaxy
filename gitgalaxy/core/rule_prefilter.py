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
  repeats, negative lookarounds, backrefs, anchors) contribute nothing; they
  only terminate the literal run being accumulated. POSITIVE lookarounds are
  harvested (#3072, deferred from #3070): `(?=X)`/`(?<=X)` assert that X
  matches, so X's required text must occur in the haystack even though the
  match itself does not consume it.
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

# On 3.11+ the sre internals live as re submodules, already loaded by re's
# own __init__ -- reach them as attributes (getattr, because on <=3.10 the
# missing attribute raises AttributeError, which a `from re import ...`
# ImportError guard would miss). CodeQL also dislikes mixing `import re` with
# `from re import ...` in one module.
_sre_parser: Any = getattr(re, "_parser", None)
if _sre_parser is None:  # pragma: no cover -- exercised only on <=3.10
    try:
        import sre_parse as _sre_parser  # type: ignore[no-redef]
    except ImportError:
        _sre_parser = None

_sre_constants: Any = getattr(re, "_constants", None)
if _sre_constants is None:  # pragma: no cover -- exercised only on <=3.10
    try:
        import sre_constants as _sre_constants  # type: ignore[no-redef]
    except ImportError:
        _sre_constants = None

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
    _ASSERT = _C.ASSERT
    _BARREN_OPS = frozenset(
        op
        for op in (
            _C.NOT_LITERAL,
            _C.ANY,
            _C.IN,
            _C.AT,
            _C.GROUPREF,
            _C.GROUPREF_EXISTS,
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
_EXTRA_CASES: "dict[int, list[int]]" = getattr(getattr(re, "_casefix", None), "_EXTRA_CASES", {})


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


def _pick_most_selective(candidates: list[_Candidate]) -> Optional[_Candidate]:
    """Longest minimum literal first, then fewest alternatives.

    The per-line gates (#3072) invert _pick_best's priorities: a line-gate
    literal is probed against an ~80-char line inside one C-speed candidate
    regex, so scan count is nearly free -- what matters is how many lines
    SURVIVE. Under _pick_best, cpp state_mutation's container-mutator branch
    bottoms out at the 1-char run `.` (fewest alternatives), which nearly
    every code line contains; this policy picks the 11 method-name literals
    instead. Every candidate is independently sound, so this too is pure
    policy, not correctness.
    """
    if not candidates:
        return None
    return min(candidates, key=lambda c: (-min(len(lit) for lit in c[0]), len(c[0])))


def _walk_seq(seq: Any, ci: bool, picker: Any = _pick_best) -> list[_Candidate]:
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
                best = picker(_walk_seq(branch, ci, picker))
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
            candidates.extend(_walk_seq(sub, sub_ci, picker))
        elif op is _MAX_REPEAT or op is _MIN_REPEAT or (_POSSESSIVE_REPEAT is not None and op is _POSSESSIVE_REPEAT):
            rmin, _rmax, sub = av
            # `X{n,m}` with n >= 1 must match X at least once, so X's
            # requirements hold. n == 0 (`?`, `*`) requires nothing.
            if rmin >= 1:
                candidates.extend(_walk_seq(sub, ci, picker))
        elif _ATOMIC_GROUP is not None and op is _ATOMIC_GROUP:
            candidates.extend(_walk_seq(av, ci, picker))
        elif op is _ASSERT:
            # Positive lookaround (#3070's deferred item): `(?=X)`/`(?<=X)`
            # asserts that X matches, so X's required text must occur in the
            # haystack and gates the segment exactly like consumed text.
            # CAUTION: the harvested literal is required *near* the match, not
            # necessarily *inside* the match span -- sound for whole-segment
            # gates; sound for per-line gates only because
            # pattern_is_line_local also walks ASSERT contents, proving the
            # lookaround text cannot leave the match's own line. ASSERT_NOT
            # stays barren: `(?!X)` forbids text, requiring nothing.
            _direction, sub = av
            candidates.extend(_walk_seq(sub, ci, picker))
        else:
            raise _Ungateable(str(op))
    _flush()
    return candidates


def derive_literal_gate(
    pattern: Any, max_literals: int = 80, min_literal_len: int = 2, prefer_selective: bool = False
) -> "Optional[Gate]":
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
    `prefer_selective`: which candidate-selection policy to use (pure policy, not
    correctness -- every candidate is independently sound). Default False =
    `_pick_best` (fewest alternatives), matching the coding-rule gates. True =
    `_pick_most_selective` (longest minimum literal); it rescues patterns whose
    top-level alternation branches each carry a strong keyword literal *plus* a
    1-char run like `'('`: `_pick_best` picks the `'('` and the length floor
    then drops the whole gate, whereas the selective picker keeps the keyword.
    This is what lets the security THREAT_SIGNATURES gate (#3173).
    """
    if _sre_parser is None or _C is None:  # pragma: no cover -- stdlib privates moved
        return None
    picker = _pick_most_selective if prefer_selective else _pick_best
    try:
        source = pattern.pattern
        flags = pattern.flags
        if not isinstance(source, str) or flags & re.LOCALE:
            return None
        candidates = _walk_seq(_sre_parser.parse(source, flags), bool(flags & re.IGNORECASE), picker)
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

    best = picker(viable)
    if best is None:
        return None
    literals, needs_casefold = best
    return tuple(sorted(literals, key=lambda lit: (len(lit), lit))), needs_casefold


# ==============================================================================
# Per-line gating (#3072)
# ==============================================================================
#
# The whole-segment gate above cannot help the per-file most expensive rules:
# their patterns bottom out in operators every file contains (state_mutation's
# `=`/`++`/`--`). #3072 generalizes #3063's `'=' in line` var-decl gate to
# them: a rule whose pattern provably (a) never consumes a newline and (b)
# requires one of a small literal set *on the match's own line* can be
# evaluated per run-of-surviving-lines instead of over the whole segment.
# Eligibility is machine-checked per pattern (pattern_is_line_local), never
# hand-argued per language: a future rule edit that reintroduces `\s*` makes
# build_line_gate return None and the rule silently runs ungated -- a lost
# optimization, never a wrong result.

# AT codes that keep a pattern line-local. `^`/`$` parse to
# AT_BEGINNING/AT_END regardless of flags (MULTILINE is applied at compile
# time), so they are only admitted when the pattern carries re.M -- under
# re.M their window semantics are exactly their global semantics (verified:
# `^` at pos checks the real preceding char; `$` at endpos == `$` before the
# `\n` that endpos points at). Without re.M, or for \A/\Z (AT_*_STRING),
# window edges would create match sites global evaluation does not have.
if _C is not None:
    _LINE_SAFE_AT_ALWAYS = frozenset((_C.AT_BOUNDARY, _C.AT_NON_BOUNDARY))
    _LINE_SAFE_AT_MULTILINE = frozenset((_C.AT_BEGINNING, _C.AT_END))
    # Character categories partitioned by whether they can match '\n'. A
    # category outside both sets (locale variants, future additions) refuses
    # the pattern.
    _CATEGORY_MATCHES_NL = frozenset(
        cat
        for cat in (
            getattr(_C, "CATEGORY_SPACE", None),
            getattr(_C, "CATEGORY_UNI_SPACE", None),
            getattr(_C, "CATEGORY_NOT_WORD", None),
            getattr(_C, "CATEGORY_UNI_NOT_WORD", None),
            getattr(_C, "CATEGORY_NOT_DIGIT", None),
            getattr(_C, "CATEGORY_UNI_NOT_DIGIT", None),
        )
        if cat is not None
    )
    _CATEGORY_NEVER_NL = frozenset(
        cat
        for cat in (
            getattr(_C, "CATEGORY_DIGIT", None),
            getattr(_C, "CATEGORY_UNI_DIGIT", None),
            getattr(_C, "CATEGORY_WORD", None),
            getattr(_C, "CATEGORY_UNI_WORD", None),
            getattr(_C, "CATEGORY_NOT_SPACE", None),
            getattr(_C, "CATEGORY_UNI_NOT_SPACE", None),
        )
        if cat is not None
    )

_NL = 0x0A


class _NotLineLocal(Exception):
    """Raised on any construct that could consume '\\n' or anchor unsafely."""


def _in_set_can_match_nl(items: Any) -> bool:
    """Can this IN character set match '\\n'? Unknown items raise."""
    negated = False
    covers_nl = False
    for op, av in items:
        if op is _C.NEGATE:
            negated = True
        elif op is _LITERAL:
            covers_nl |= av == _NL
        elif op is _C.RANGE:
            lo, hi = av
            covers_nl |= lo <= _NL <= hi
        elif op is _C.CATEGORY:
            if av in _CATEGORY_MATCHES_NL:
                covers_nl = True
            elif av not in _CATEGORY_NEVER_NL:
                raise _NotLineLocal(str(av))
        else:
            raise _NotLineLocal(str(op))
    # `[^...]` matches '\n' unless the listed items cover it; `[...]` matches
    # '\n' only if they do.
    return not covers_nl if negated else covers_nl


def _walk_line_local(seq: Any, multiline: bool, dotall: bool) -> None:
    """Whitelist walk proving no node of `seq` can consume or anchor past a
    line boundary. Raises _NotLineLocal on the first counterexample or on any
    node kind this walk was not written against."""
    for op, av in seq:
        if op is _LITERAL:
            if av == _NL:
                raise _NotLineLocal("literal newline")
        elif op is _C.NOT_LITERAL:
            # `[^X]` for a single char: consumes anything BUT X -- line-local
            # only when X is '\n' itself.
            if av != _NL:
                raise _NotLineLocal("negated non-newline literal")
        elif op is _C.IN:
            if _in_set_can_match_nl(av):
                raise _NotLineLocal("class matches newline")
        elif op is _C.ANY:
            if dotall:
                raise _NotLineLocal("dotall '.'")
        elif op is _C.AT:
            if av in _LINE_SAFE_AT_ALWAYS:
                continue
            if multiline and av in _LINE_SAFE_AT_MULTILINE:
                continue
            raise _NotLineLocal(str(av))
        elif op is _BRANCH:
            _, branches = av
            for branch in branches:
                _walk_line_local(branch, multiline, dotall)
        elif op is _SUBPATTERN:
            _group, add_flags, del_flags, sub = av
            sub_multiline = (multiline or bool(add_flags & re.M)) and not (del_flags & re.M)
            sub_dotall = (dotall or bool(add_flags & re.S)) and not (del_flags & re.S)
            _walk_line_local(sub, sub_multiline, sub_dotall)
        elif op is _MAX_REPEAT or op is _MIN_REPEAT or (_POSSESSIVE_REPEAT is not None and op is _POSSESSIVE_REPEAT):
            _rmin, _rmax, sub = av
            # Even a {0,n} repeat must be \n-free: when present it consumes.
            _walk_line_local(sub, multiline, dotall)
        elif _ATOMIC_GROUP is not None and op is _ATOMIC_GROUP:
            _walk_line_local(av, multiline, dotall)
        elif op is _ASSERT or op is _C.ASSERT_NOT:
            # Lookaround contents must ALSO be \n-free -- in both polarities.
            # A \n-free lookaround evaluated anywhere inside a match can only
            # ever examine characters of that match's own line (its text
            # cannot cross the bounding newlines), and the evaluation window
            # always extends to the line's real end -- so windowed and global
            # evaluation agree. A lookaround that could match '\n' would let
            # the two diverge in BOTH directions: a negative lookahead whose
            # forbidden text lies beyond the window would falsely accept, a
            # positive one would falsely reject.
            _direction, sub = av
            _walk_line_local(sub, multiline, dotall)
        else:
            # GROUPREF included: a backref to \n-free text is itself \n-free,
            # but no shipped rule needs the argument -- refuse instead.
            raise _NotLineLocal(str(op))


def pattern_is_line_local(pattern: Any) -> bool:
    """True iff no match of `pattern` can ever contain '\\n' AND every anchor
    keeps its meaning when evaluated inside a [line_start, line_end) window
    of the full haystack (re.M `^`/`$`, `\\b`/`\\B`).

    False is always safe -- the caller runs the rule ungated. Any parse
    surprise or unknown construct resolves to False, mirroring
    derive_literal_gate's whitelist ethos.
    """
    if _sre_parser is None or _C is None:  # pragma: no cover -- stdlib privates moved
        return False
    try:
        source = pattern.pattern
        flags = pattern.flags
        if not isinstance(source, str) or flags & re.LOCALE:
            return False
        _walk_line_local(
            _sre_parser.parse(source, flags),
            multiline=bool(flags & re.M),
            dotall=bool(flags & re.S),
        )
    except _NotLineLocal:
        return False
    except Exception:
        # Defensive: same contract as derive_literal_gate -- degrade to
        # "ungated", never crash the scan.
        return False
    return True


def derive_line_literals(pattern: Any, max_literals: int = 80) -> "Optional[tuple[str, ...]]":
    """The per-line analogue of derive_literal_gate: a one-of literal set such
    that a line containing none of them cannot contain a match start.

    Differences from the segment gate, all forced by line semantics:
    - selectivity-first policy (_pick_most_selective): the literals are probed
      by one compiled candidate regex per segment, so set width is nearly
      free, while every surviving line costs a Python-level window; prefer
      rare literals over few literals.
    - min_literal_len drops to 1: `=` is a useless *segment* gate (every file
      contains one) but the whole point of a *line* gate (most lines don't).
    - case-insensitive candidates are refused outright: fold_haystack() is not
      length-preserving (U+0130 folds to two chars), so offsets into a folded
      haystack are not offsets into the real one, and the line windows must be
      real offsets.

    Only sound when pattern_is_line_local(pattern) also holds -- that walk is
    what proves ASSERT-harvested literals (required *near* the match) cannot
    sit on a different line than the match itself.
    """
    if _sre_parser is None or _C is None:  # pragma: no cover -- stdlib privates moved
        return None
    try:
        source = pattern.pattern
        flags = pattern.flags
        if not isinstance(source, str) or flags & (re.LOCALE | re.IGNORECASE):
            return None
        candidates = _walk_seq(_sre_parser.parse(source, flags), False, _pick_most_selective)
    except _Ungateable:
        return None
    except Exception:
        return None
    viable: list[_Candidate] = [
        (literals, ci) for literals, ci in candidates if not ci and len(literals) <= max_literals
    ]
    best = _pick_most_selective(viable)
    if best is None:
        return None
    return tuple(sorted(best[0], key=lambda lit: (len(lit), lit)))


def build_line_gate(pattern: Any) -> "Optional[re.Pattern[str]]":
    """Compile the candidate-line scanner for a rule, or None if ineligible.

    The scanner is `(?m)^[^\\n]*?(?:lit|...)[^\\n]*$`: one C-speed pass over
    the segment that yields exactly one match per line containing a required
    literal, whose span IS the line's [start, content_end) window -- `^` only
    ever matches at line starts, the lazy prefix stops at the first literal,
    and `[^\\n]*$` runs to the character before the terminating `\\n` (or to
    end-of-text for an unterminated last line). Consumers get the window
    bounds straight off the match with no newline-table bisect.
    """
    if not pattern_is_line_local(pattern):
        return None
    literals = derive_line_literals(pattern)
    if not literals:
        return None
    # Shortest-first ordering (from derive_line_literals) doubles as the
    # alternation order: for these operator-class gates the short literals
    # are the statistically common ones, so the engine's per-position
    # alternation attempt usually succeeds on its first branch.
    alternation = "|".join(re.escape(lit) for lit in literals)
    return re.compile(f"(?m)^[^\\n]*?(?:{alternation})[^\\n]*$")


def line_gated_finditer(pattern: Any, line_gate: "re.Pattern[str]", text: str) -> "list[re.Match[str]]":
    """`list(pattern.finditer(text))`, computed per run of surviving lines.

    Equivalence argument (each leg verified empirically in the #3072 unit and
    corpus-parity suites; preconditions established at cache build):

    PRE-1  pattern_is_line_local(pattern): no node consumes '\\n' (lookaround
           contents included) and anchors are window-stable (re.M `^`/`$`,
           `\\b`/`\\B`).
    PRE-2  line_gate marks exactly the lines containing a literal required on
           any match's own line (derive_line_literals); its match spans are
           whole [line_start, content_end) windows.

    1. Every match of `pattern` lies within one line (PRE-1) and that line
       survives (PRE-2), so every match lies inside some run of consecutive
       surviving lines.
    2. At any position both evaluations attempt, window semantics equal
       global semantics: runs start at true line starts (`^` checks the real
       preceding character through pos); `\\b`/lookbehind read real
       characters before pos (pos does not truncate); run ends sit at a real
       `\\n` offset or len(text), where `$`-at-endpos equals `$`-before-`\\n`
       and \\n-free lookaheads can never need a character at or past the
       `\\n` (PRE-1 applies inside lookarounds, both polarities).
    3. Positions only global evaluation attempts lie on non-surviving lines
       or at `\\n` itself; by (1) no match can start there, and failed
       attempts carry no engine state.
    4. Within a run, finditer IS the global algorithm (leftmost match, resume
       at its end). Across runs: a match ends on its own line, strictly
       before the next run's start, so per-run scans can neither skip nor
       double-count. Order and non-overlap follow.
    5. Zero-width matches cannot exist: every match consumes a required
       literal of length >= 1, so the scan always advances.
    """
    matches: list[re.Match[str]] = []
    run_start = -1
    run_end = -1
    for candidate in line_gate.finditer(text):
        line_start = candidate.start()
        if run_start < 0:
            run_start = line_start
        elif line_start != run_end + 1:
            # Non-adjacent survivor: flush the current run, start a new one.
            matches.extend(pattern.finditer(text, run_start, run_end))
            run_start = line_start
        run_end = candidate.end()
    if run_start >= 0:
        matches.extend(pattern.finditer(text, run_start, run_end))
    return matches
