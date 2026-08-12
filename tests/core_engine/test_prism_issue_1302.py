from gitgalaxy.core.prism import Prism

LANG_DEFS = {
    "scala": {"lexical_family": "recursive_block"},
    "rust": {"lexical_family": "recursive_block"},
    "haskell": {"lexical_family": "recursive_block_haskell"},
    "scheme": {"lexical_family": "recursive_block_lisp"},
}

CONFIG = {
    "lexical_families": {
        "recursive_block": {"delimiters": ["//", "/*", "*/"]},
        "recursive_block_haskell": {"delimiters": ["--", "{-", "-}"]},
        "recursive_block_lisp": {"delimiters": [";", "#|", "|#"]},
    }
}


def test_issue_1302_comment_apostrophe_does_not_swallow_scala_code():
    """
    Regression test for #1302: `_strip_nested_comments` (used for scala/rust/
    swift via "recursive_block") used to shield an unbounded `'...'` span, so
    a lone apostrophe inside a `//` comment ("it's") paired with whatever `'`
    came next -- far later in the file -- and masked everything in between,
    silently dropping real functions from the code stream.
    """
    prism = Prism(CONFIG, LANG_DEFS)

    code = """
class Test {
  // Only record it if it's unset.
  def firstMethod(): Unit = {
    println("first")
  }

  def secondMethod(): Unit = {
    println("second")
  }
}
"""

    result = prism.split_streams(code, "scala")

    assert "secondMethod" in result["code_stream"], "Code after comment apostrophe was swallowed!"  # noqa: S101
    assert "firstMethod" in result["code_stream"]  # noqa: S101


def test_issue_1302_scala_symbol_literal_does_not_swallow_code():
    """Scala Symbol literals ('foo, no closing quote) are a second unpaired-apostrophe source."""
    prism = Prism(CONFIG, LANG_DEFS)

    code = """
object Test {
  val sym = 'foo

  def realMethod(): Unit = {
    println("still here")
  }
}
"""

    result = prism.split_streams(code, "scala")

    assert "realMethod" in result["code_stream"]  # noqa: S101


def test_issue_1302_haskell_trailing_apostrophe_identifiers_do_not_swallow_code():
    """Haskell's idiomatic trailing-apostrophe identifiers (x', map') are the third source."""
    prism = Prism(CONFIG, LANG_DEFS)

    code = """
firstFn :: Int -> Int
firstFn x' = x' + 1

secondFn :: Int -> Int
secondFn y' = y' * 2
"""

    result = prism.split_streams(code, "haskell")

    assert "secondFn" in result["code_stream"]  # noqa: S101


def test_issue_1302_real_char_literal_still_shielded():
    """The bound must not break real short char literals -- they should still be masked/restored intact."""
    prism = Prism(CONFIG, LANG_DEFS)

    code = """
object Test {
  val c = 'a'
  val nl = '\\n'

  def realMethod(): Unit = {
    println("still here")
  }
}
"""

    result = prism.split_streams(code, "scala")

    assert "'a'" in result["code_stream"]  # noqa: S101
    assert "realMethod" in result["code_stream"]  # noqa: S101


def test_issue_1302_nested_block_comments_still_peel_correctly():
    """The bounded-shield fix must not regress genuine nested block-comment stripping."""
    prism = Prism(CONFIG, LANG_DEFS)

    code = """
/* outer /* inner */ still outer */
def realMethod(): Unit = {
  println("still here")
}
"""

    result = prism.split_streams(code, "scala")

    assert "outer" not in result["code_stream"]  # noqa: S101
    assert "inner" not in result["code_stream"]  # noqa: S101
    assert "realMethod" in result["code_stream"]  # noqa: S101


def test_issue_1302_stray_unpaired_backtick_in_comment_does_not_swallow_code():
    """
    Regression test for the backtick variant of #1302: a single stray, unpaired
    backtick inside an ordinary comment (a real-world typo -- confirmed on a live
    Kafka corpus file) used to pair with the next unrelated backtick anywhere later
    in the file, masking everything in between as one giant fake "string".
    """
    prism = Prism(CONFIG, LANG_DEFS)

    code = """
class Test {
  // 'protected` to allow override for testing
  def firstMethod(): Unit = {
    println("first")
  }

  // synchronized on `counts`
  def secondMethod(): Unit = {
    println("second")
  }
}
"""

    result = prism.split_streams(code, "scala")

    assert "firstMethod" in result["code_stream"]  # noqa: S101
    assert "secondMethod" in result["code_stream"]  # noqa: S101


def test_issue_1302_real_backtick_identifier_still_shielded():
    """The backtick bound must not break real short backtick-quoted identifiers."""
    prism = Prism(CONFIG, LANG_DEFS)

    code = """
class Test {
  def `should handle edge cases`(): Unit = {
    println("first")
  }

  def realMethod(): Unit = {
    println("still here")
  }
}
"""

    result = prism.split_streams(code, "scala")

    assert "`should handle edge cases`" in result["code_stream"]  # noqa: S101
    assert "realMethod" in result["code_stream"]  # noqa: S101
