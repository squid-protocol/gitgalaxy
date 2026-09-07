# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

from typing import Any, TypedDict

# #2549: the tail of a markup OPEN TAG, from the end of a handshake trigger
# (`<script` / `<style`) through its closing `>`. A handshake entry that
# declares it says "this opening delimiter is HOST syntax": the tag stays in
# the host document's segment and only the payload after `>` is handed to the
# embedded language. Without it html's own `func_start` rule -- whose only
# anchor IS the `<script`/`<style` tag -- could never fire end to end, because
# the splitter handed the tag itself to JavaScript/CSS before html's rules ran
# (every corpus html file recorded `func_start = 0` against 9 raw matches).
#
# The three alternatives are disjoint on their first character, so the star can
# never re-partition a prefix: linear time, no backtracking ambiguity, and an
# attribute value holding a `>` (`<script data-tpl="a>b">`) does not cut the tag
# short. An unterminated tag simply fails to match, and the caller falls back to
# the pre-#2549 split point.
MARKUP_OPEN_TAG_TAIL = r"""(?:"[^"]*"|'[^']*'|[^>"'])*>"""


class LensConfig(TypedDict):
    # LENS_CONFIG's mixed set/dict/list values were widening to
    # Collection[object] under mypy, so every .get()/.items() call on it
    # throughout language_lens.py errored (#431). HANDSHAKE_REGISTRY's
    # inner dicts stay Dict[str, Any] rather than their own TypedDict --
    # "pair" is None for two of the three current entries and a tuple for
    # the third, and nothing here needs to type-check their contents,
    # only LENS_CONFIG's own top-level shape.
    COLLISION_FREQUENCIES: set[str]
    PROSE_ANCHORS: set[str]
    DISQUALIFIERS: dict[str, str]
    HANDSHAKE_REGISTRY: list[dict[str, Any]]
    THRESHOLDS: dict[str, float]


LENS_CONFIG: LensConfig = {
    "COLLISION_FREQUENCIES": {".inc", ".h", ".py", ".cshtml", ".c", ".y", ".m"},
    "PROSE_ANCHORS": {
        "README",
        "LICENSE",
        "LICENCE",
        "CONTRIBUTING",
        "CHANGELOG",
        "AUTHORS",
        "INSTALL",
        "NOTICE",
        "COPYING",
        "TODO",
        "FAQ",
        "NOTES",
        "CREDITS",
        "HISTORY",
        "MANIFEST",
        "FILES",
        "FILES2",
        "ACKNOWLEDGEMENTS",
        "AGREEMENT",
        "CONTRIBUTORS",
        "HACKING",
        "HACKERS",
        "AUTHOR",
        "CHANGES",
        "NEWS",
        "RELEASE_NOTES",
        "RELEASENOTES",
        "UPGRADE",
        "UPGRADING",
        "VERSION",
        "BUGS",
        "FEATURES",
        "ARCHITECTURE",
        "DESIGN",
        "GUIDE",
        "USAGE",
        "TUTORIAL",
        "DOCS",
        "CODE_OF_CONDUCT",
        "SECURITY",
        "SUPPORT",
        "COPYRIGHT",
        "PATENTS",
        "LEGAL",
        "THANKS",
        "OWNERS",
        "CODEOWNERS",
        "MAINTAINERS",
        "POSTAMBLE",
        "README_BUFRLIB",
    },
    "DISQUALIFIERS": {
        "single_line_only": r"(?:^\s*using\s+namespace\b|^\s*public\s+(?:class|interface)\b|<\?php)",
        "column_sensitive": r"(?:^\s*(?:import|export)\s+\{|<html\b|<\?php|^\s*namespace\s+\w+)",
        "c_style_comment": r"(?:<\?php|^\s*IDENTIFICATION\s*DIVISION\.)",
        "recursive_c_style": r"(?:<\?php|<html\b|^\s*IDENTIFICATION\s*DIVISION\.)",
        "multi_style_dash": r"(?:^\s*public\s+class\b|<\?php|<html\b)",
        "embedded_syntax": r"^\s*IDENTIFICATION\s*DIVISION\.",
    },
    "HANDSHAKE_REGISTRY": [
        {
            "trigger": r"^[ \t]*<script\b",
            "end": r"</script>",
            "target": "javascript",
            "pair": None,
            # #2549: `<script ...>` is html, only its body is JavaScript.
            "open_delimiter": MARKUP_OPEN_TAG_TAIL,
        },
        {
            "trigger": r"^[ \t]*<style\b",
            "end": r"</style>",
            "target": "css",
            "pair": None,
            # #2549: `<style ...>` is html, only its body is CSS.
            "open_delimiter": MARKUP_OPEN_TAG_TAIL,
        },
        {
            # #1198: same drift #1183 fixed for <script>/<style> -- this
            # was still unanchored, so a bare "asm!(" substring anywhere in
            # a file (e.g. a Python string literal like 'asm!("nop")' in a
            # Rust structural-signature test fixture) falsely triggered the
            # embedded-language handshake and misrouted the rest of the
            # file to assembly's rules. Line-anchoring it like the other
            # two entries means real inline-asm usage (always its own
            # statement, optionally indented) still matches while fixture
            # data describing it as a string does not.
            "trigger": r"^[ \t]*(?:asm!\s*\(|__asm__)",
            "end": r"\)",
            "target": "assembly",
            "pair": ("(", ")"),
        },
    ],
    "THRESHOLDS": {
        "INTENSITY_FLOOR": 0.78,
        "FLOOR_TIER_4": 0.92,
        "PROSE_CONFIDENCE": 0.95,
        "MIN_OUTLIER_MARGIN": 1.15,
        "PROSE_BASELINE_SIGNAL": 3.0,
        "HANDSHAKE_LOOKAHEAD_LIMIT": 50000,
        "ECOSYSTEM_DOMINANCE_MIN": 0.70,
        "TIER_4_MIN_LINES": 100,
        "TIER_4_OUTLIER_MARGIN": 1.3,
    },
}
