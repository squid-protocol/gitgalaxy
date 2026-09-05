"""#2769: the `PATH_MODIFIERS` multiplier table in `analysis_lens.py`.

These multipliers are applied by `galaxyscope.py`'s `mod_regex.search(search_path)`
against a POSIX-normalized RELATIVE path, first match wins. A mistake in one of
them is invisible -- there is no error, just a silently wrong mass -- and it
scales to every file of the affected shape in every scan.
"""

import re

from gitgalaxy.standards.analysis_lens import PATH_MODIFIERS


def _entries():
    """Every (category, regex, multiplier) triple in the table."""
    for category, mods in PATH_MODIFIERS.items():
        for regex, multiplier in mods:
            yield category, regex, multiplier


def test_asset_dampener_is_scoped_to_asset_directories():
    """The bug: the extension alternation was missing its group, so `|` bound at
    the TOP level and the second alternative was a bare `tsx?$` -- unanchored to
    any directory. Every path ending in `ts`/`tsx` took the 0.1 dampener, so
    every TypeScript file in every scan carried one tenth of its real
    `structural_mass`, and a mixed .js/.ts repo mid-migration ranked its
    migrated files last.
    """
    mass = PATH_MODIFIERS["Structural Mass"]
    asset = next(r for r, _ in mass if "icons?" in r.pattern)

    # Still catches what the token list says it is for: code inside an asset dir.
    for path in ("assets/foo.js", "icons/a.jsx", "src/assets/c.tsx", "app/logos/b.ts"):
        assert asset.search(path), f"{path} is an asset-directory file and must still be dampened"

    # And nothing else. These are the shapes the top-level `|` used to swallow.
    for path in (
        "src/app/service.ts",
        "components/Button.tsx",
        "src/types.d.ts",
        "scripts/run_tests",
        "lib/constants",
    ):
        assert not asset.search(path), f"{path} is not an asset -- it must not take the 0.1 dampener"


def _top_level_alternatives(pattern):
    """Split `pattern` on `|` at nesting depth 0, respecting escapes."""
    out, depth, cur, i = [], 0, "", 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\":
            cur += pattern[i : i + 2]
            i += 2
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "|" and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    out.append(cur)
    return out


def test_every_path_modifier_alternative_is_anchored():
    r"""#2769's real regression guard, and the invariant the bug violated.

    A top-level `|` in a path pattern is legal and often intended -- "X inside a
    directory, OR Y anywhere" (a `.snap` or `.ipynb` file genuinely counts
    wherever it sits). What made the asset entry a bug was not the alternation
    but that its stray alternative, a bare `tsx?$`, was anchored to NOTHING: no
    directory, no escaped extension dot, no word boundary. It therefore matched
    any path merely ENDING in the letters `ts` -- every TypeScript file in every
    scan, plus `.mts`, `.d.ts`, and extensionless names like `scripts/run_tests`.

    So require of every alternative what distinguishes all fifteen deliberate
    ones from that: it must scope itself with a `/`, an escaped `\.` before an
    extension, or a `\b`. This catches the bug's shape without outlawing the
    legitimate pattern it hid inside.
    """
    for category, regex, multiplier in _entries():
        for alt in _top_level_alternatives(regex.pattern):
            assert "/" in alt or "\\." in alt or "\\b" in alt, (
                f"{category}: alternative {alt!r} in {regex.pattern!r} (x{multiplier}) is anchored to "
                "nothing -- it matches on a bare substring. This is #2769's shape: did an extension "
                "alternation lose its group?"
            )


def test_path_modifiers_do_not_match_an_unremarkable_path():
    """A pattern that matches everything is indistinguishable from a correct one
    until someone reads the output. No entry may claim a plain source file that
    sits in no special directory and carries no special name.
    """
    for category, regex, multiplier in _entries():
        assert not regex.search("project/widget.py"), (
            f"{category}: {regex.pattern!r} (x{multiplier}) matches an unremarkable source path"
        )
