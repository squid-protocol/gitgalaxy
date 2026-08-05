"""markdown strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore


# ==============================================================================
# MARKDOWN: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #597)
# ==============================================================================
MARKDOWN_RULES = LANGUAGE_DEFINITIONS["markdown"]["rules"]

_MARKDOWN_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("lit_code_blocks", "```python\ndef hello():\n    print('hi')\n```", "    ```python\nindented code block\n    ```"),
    ("lit_diagrams", "```mermaid\ngraph TD;\n    A-->B;\n```", "```python\nprint('not a diagram')\n```"),
    ("lit_headers", "# Main Architecture Title", "####### Not a valid Markdown header"),
    ("lit_links", "[GitGalaxy](https://github.com/squid-protocol/gitgalaxy)", "(https://github.com/without-brackets)"),
]


@pytest.mark.parametrize("signature,positive,negative", _MARKDOWN_SIMPLE_CASES)
def test_markdown_signature_positive_and_negative(signature, positive, negative):
    pattern = MARKDOWN_RULES[signature]
    assert pattern is not None, f"markdown's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"markdown {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"markdown {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_markdown_lit_links_nested_delimiter_regression():
    r"""
    Regression test for Issue #597 (Rule 11 nested-delimiter defect):
    1. `lit_links`'s URL portion previously used `[^)]+`, which stopped at the
       first closing parenthesis when encountering URLs containing internal
       parens (e.g., Wikipedia disambiguation links like `[Foo](http://.../Bar_(baz))`).
       This caused the matched string to silently truncate before the URL's final `)`.
    2. `lit_links`'s link text portion previously used `[^\]]+`, which broke on
       one-level nested brackets in link text (e.g., `[badge [v1.0]](https://...)`).
    """
    pattern = MARKDOWN_RULES["lit_links"]

    # 1. Wikipedia-style disambiguation URL with internal parentheses
    wiki_link = "See [Foo (bar)](https://en.wikipedia.org/wiki/Foo_(bar)) for details."
    m = pattern.search(wiki_link)
    assert m is not None, "Failed to match Wikipedia-style link with internal parens"
    assert m.group(0) == "[Foo (bar)](https://en.wikipedia.org/wiki/Foo_(bar))", (
        f"Link match was truncated: {m.group(0)!r}"
    )

    # 2. Nested brackets in link text
    nested_bracket_link = "Check out [release [v2.0]](https://github.com/org/repo/releases/v2.0) now."
    m_bracket = pattern.search(nested_bracket_link)
    assert m_bracket is not None, "Failed to match link with nested brackets in text"
    assert m_bracket.group(0) == "[release [v2.0]](https://github.com/org/repo/releases/v2.0)"


def test_markdown_lit_code_blocks_formatting_and_indentation_regression():
    """
    Regression test for `lit_code_blocks`. Uses single-line opening-fence-only
    snippets (not multi-line blocks with a closing fence) -- the old regex
    `^[a-zA-Z0-9]*$` couldn't match a non-alphanumeric *opening* fence line,
    but a multi-line snippet's bare closing ` ``` ` line incidentally
    satisfies it anyway (zero alphanumeric chars after the backticks still
    matches `[a-zA-Z0-9]*`), which would make a whole-snippet `.search()`
    silently pass against the unfixed regex too. Testing the opening fence
    line in isolation is the only way these assertions actually discriminate
    old vs. new behavior.
    1. Previously `^[a-zA-Z0-9]*$` failed to match language info strings with non-alphanumeric
       characters such as `c++`, `c#`, `objective-c`, `shell-script`.
    2. Failed to match info strings with parameters or titles (e.g., ` ```python title="app.py" `).
    3. Failed to match 4+ backtick fences (` ```` ````).
    4. Required strict 0-3 space indentation handling (4 spaces turn a fence into literal code in CommonMark).
    """
    pattern = MARKDOWN_RULES["lit_code_blocks"]

    # Non-alphanumeric language info strings (opening fence line only)
    assert pattern.search("```c++")
    assert pattern.search("```c#")
    assert pattern.search("```objective-c")
    assert pattern.search("```shell-script")

    # Code fence with attributes / title (opening fence line only)
    assert pattern.search('```python title="main.py" hl_lines="1-3"')

    # 4+ backticks (opening fence line only)
    assert pattern.search("````python")

    # Indentation: 0-3 spaces allowed, 4 spaces excluded (opening fence line only)
    assert pattern.search("   ```python")
    assert not pattern.search("    ```python"), (
        "lit_code_blocks matched a 4-space indented code fence (which is literal code text in CommonMark)"
    )


def test_markdown_lit_diagrams_case_insensitivity_and_indentation_regression():
    """
    Regression test for `lit_diagrams`:
    1. Previously `^(?:mermaid|plantuml)$` failed on capitalized diagram tags (`Mermaid`, `PlantUML`, `MERMAID`).
    2. Failed on diagram fences with titles or parameters (e.g., ` ```mermaid title="Architecture" `).
    3. Excludes 4-space indented blocks.
    """
    pattern = MARKDOWN_RULES["lit_diagrams"]

    assert pattern.search("```Mermaid\ngraph TD;\n    A-->B;\n```")
    assert pattern.search("```PlantUML\n@startuml\n@enduml\n```")
    assert pattern.search('```MERMAID title="Flow"\ngraph LR;\n```')

    assert pattern.search("  ```mermaid\n2-space indent\n  ```")
    assert not pattern.search("    ```mermaid\n4-space indent\n    ```")


def test_markdown_lit_headers_multiline_and_boundary_regression():
    r"""
    Regression test for `lit_headers`. The one genuine bug: previously
    `^#{1,6}\s+` in `re.M` mode matched newlines (`\s` includes `\n`), so a
    standalone `#` at end of line plus the following line's leading
    whitespace got consumed as the required `\s+`, falsely classifying a
    bare trailing `#` as a header (Rule 5 violation). Fixed by requiring
    `[ \t]+` instead of `\s+`.

    The 7+-hash, `#123`, and `#hashtag` exclusions below were already
    correctly handled by the original regex (the `{1,6}` quantifier and the
    required `\s+`/`[ \t]+` after it already excluded them) -- they're kept
    here as forward-looking correctness coverage, not because they were
    ever broken, so a future change to the quantifier bounds can't
    regress them silently. The `#\n` case and the second genuine bug below
    (indented headers) are the true regressions against the pre-fix regex.

    The second genuine bug: the pre-fix regex had no leading-indentation
    tolerance at all, so a 1-3 space indented header (legal in CommonMark)
    never matched -- `^#{1,6}` requires `#` at the true line start, and any
    leading space there fails the anchor. The fixed regex adds `[ \t]{0,3}`
    to correctly include 1-3 space indents while still excluding 4-space
    (which CommonMark treats as literal text, not a header) -- both old and
    new regex already excluded the 4-space case, for the same structural
    reason, so that specific assertion is pre-existing-correct coverage,
    not a regression guard either.
    """
    pattern = MARKDOWN_RULES["lit_headers"]

    # Indentation regression: 1-3 space indented headers now correctly
    # match (previously excluded entirely -- see docstring).
    assert pattern.search("# Level 1 Header")
    assert pattern.search("   ### Level 3 Header (3-space indent)")

    # The actual regression: standalone `#` at line end no longer leaks across
    # the newline into the next line's content.
    assert not pattern.search("#\nStandalone hash followed by newline"), (
        "lit_headers matched #\\n across line boundary (Rule 5 multiline \\s+ defect)"
    )

    # Pre-existing correct exclusions (not regressions -- see docstring), kept
    # as forward-looking coverage.
    assert not pattern.search("####### 7 Hashes"), "lit_headers matched 7 hashes"
    assert not pattern.search("#123"), "lit_headers matched an issue reference #123"
    assert not pattern.search("#hashtag"), "lit_headers matched a hashtag #hashtag"

    # Pre-existing correct exclusion (not a regression -- see docstring):
    # 4-space indented lines are literal text in CommonMark, not headers,
    # and both old and new regex already excluded them.
    assert not pattern.search("    # Indented 4 spaces"), "lit_headers matched a 4-space indented header"


def test_markdown_redos_immunity():
    """
    Verifies ReDoS immunity for all Markdown rules under pathological unclosed payloads.
    """
    assert_redos_immune(MARKDOWN_RULES["lit_links"], "[" * 20000, timeout_sec=3.0)
    assert_redos_immune(MARKDOWN_RULES["lit_links"], "[link](" * 20000, timeout_sec=3.0)
    assert_redos_immune(MARKDOWN_RULES["lit_code_blocks"], "`" * 20000, timeout_sec=3.0)
    assert_redos_immune(MARKDOWN_RULES["lit_diagrams"], "`" * 20000, timeout_sec=3.0)
    assert_redos_immune(MARKDOWN_RULES["lit_headers"], "#" * 20000, timeout_sec=3.0)


def test_markdown_ambiguity_sweep_intentional_overlaps():
    """
    Ambiguity Sweep Report for Markdown:
    1. `lit_diagrams` <-> `lit_code_blocks`:
       A diagram fence (e.g. ` ```mermaid `) matches BOTH `lit_diagrams` AND `lit_code_blocks`.
       Conclusion: This is EXPECTED and CORRECT. A diagram block in Markdown is a specialized subtype of
       fenced code block. GitGalaxy's structural analysis engine counts signatures independently as
       multi-metric frequency features, not as a mutually-exclusive tokenizer.
    2. `lit_code_blocks` / `lit_diagrams` <-> `lit_links`:
       A Markdown link written inside a code block (e.g. ` ```python\n# See [Doc](http://example.com)\n``` `)
       will trigger `lit_links` when the file is scanned.
       Conclusion: This is EXPECTED and CORRECT. GitGalaxy signatures measure absolute structural feature
       density across documents without running heavy lexical context scoping.
    """
    code_blocks = MARKDOWN_RULES["lit_code_blocks"]
    diagrams = MARKDOWN_RULES["lit_diagrams"]
    links = MARKDOWN_RULES["lit_links"]

    diagram_snippet = "```mermaid\ngraph TD;\n    A-->B;\n```"
    assert diagrams.search(diagram_snippet), "lit_diagrams should match diagram block"
    assert code_blocks.search(diagram_snippet), (
        "lit_code_blocks should ALSO match diagram block (intentional double-classification)"
    )

    code_with_link = "```markdown\nCheck out [GitGalaxy](https://github.com/org/repo)\n```"
    assert code_blocks.search(code_with_link)
    assert links.search(code_with_link), (
        "lit_links should match link inside code block (intentional independent multi-metric scanning)"
    )


def test_markdown_adversarial_edge_cases():
    """
    Adversarial edge-case sweep for Markdown signatures:
    1. lit_links: Query parameters, fragment anchors, complex parens, space exclusions.
    2. lit_code_blocks: Info strings with leading spaces, attribute params, inline backticks exclusion.
    3. lit_diagrams: Case variations, title attributes, non-diagram exclusions.
    4. lit_headers: Closed ATX headers, 0-3 space indentation, issue/hashtag exclusions.
    """
    links = MARKDOWN_RULES["lit_links"]
    code_blocks = MARKDOWN_RULES["lit_code_blocks"]
    diagrams = MARKDOWN_RULES["lit_diagrams"]
    headers = MARKDOWN_RULES["lit_headers"]

    # --- 1. lit_links ---
    # URL with query parameters & anchor fragment
    m1 = links.search("[API Query](https://api.example.com/v1/search?q=git&lang=py#results)")
    assert m1 is not None and m1.group(0) == "[API Query](https://api.example.com/v1/search?q=git&lang=py#results)"

    # URL with balanced internal query parens
    m2 = links.search("[Spec](https://example.org/path?filter=(type:alert))")
    assert m2 is not None and m2.group(0) == "[Spec](https://example.org/path?filter=(type:alert))"

    # Link with 1-level nested brackets in text (Rule 11 standard boundary)
    m3 = links.search("[badge [v1.0]](https://example.com)")
    assert m3 is not None and m3.group(0) == "[badge [v1.0]](https://example.com)"

    # Exclusions
    assert not links.search("[unclosed link](http://example.com"), "matched unclosed URL paren"
    assert not links.search("[spaced link] (http://example.com)"), "matched link with space before URL paren"

    # --- 2. lit_code_blocks ---
    assert code_blocks.search("```   python"), "failed on fence with spaces before info string"
    assert code_blocks.search("```bash exec=true env=prod"), "failed on fence with parameters"
    assert not code_blocks.search("   `inline_code`"), "matched inline single-backtick code"
    assert not code_blocks.search("    ```python"), "matched 4-space indented code block"

    # --- 3. lit_diagrams ---
    assert diagrams.search('```PlantUML title="Architecture"'), "failed on PlantUML with title attribute"
    assert diagrams.search("```Mermaid"), "failed on capitalized Mermaid"
    assert not diagrams.search("```python\nprint('hi')\n```"), "matched python code block as diagram"

    # --- 4. lit_headers ---
    assert headers.search("# Header 1"), "failed level 1 header"
    assert headers.search("###### Header 6"), "failed level 6 header"
    assert headers.search("  ### Closed Header ###"), "failed closed ATX header"
    assert not headers.search("####### Header 7"), "matched 7-hash non-header"
    assert not headers.search("#12345"), "matched issue number #12345"
    assert not headers.search("#hashtag"), "matched hashtag #hashtag"
    assert not headers.search("#\nBare hash followed by line break"), "matched bare # across line break"
