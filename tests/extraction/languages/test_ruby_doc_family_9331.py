"""#9331: Ruby `is_documented` (the `doc` family): the comment block directly above a `def`, past a Sorbet `sig`, documents it.

Not documentation: a bare `sig`, `# :nodoc:`, magic and linter comments, a neighbour's comment, a blank-line gap.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


def _docs(src: str) -> dict[str, bool]:
    st = _PRISM.split_streams(src, "ruby")
    out = StructuralExtractor("ruby", LANGUAGE_DEFINITIONS).splice(
        code_stream=st["code_stream"],
        comment_stream=st["comment_stream"],
        raw_content=src,
        positional_comment_stream=_PRISM.split_positional_comment_stream(src, "ruby"),
    )
    return {f["name"]: bool(f.get("is_documented")) for f in out["functions"]}


SRC = """
class Foo
  # Plain RDoc prose.
  def rdoc
    1
  end

  # @return [Integer] a YARD tag
  def yard
    1
  end

  # Documented above a one-line sig.
  sig { returns(Integer) }
  def sorbet_line
    1
  end

  # Documented above a multi-line sig.
  sig do
    params(a: Integer)
      .returns(Integer)
  end
  def sorbet_block(a)
    a
  end

  sig { returns(Integer) }
  def bare_sig
    1
  end

  def nodoc # :nodoc:
    1
  end

  # typed: true
  # rubocop:disable Metrics
  def magic_only
    1
  end

  # Detached by a blank line.

  def gap
    1
  end

  def no_comment_here
    1
  end
end
"""


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("rdoc", True),
        ("yard", True),
        ("sorbet_line", True),
        ("sorbet_block", True),
        ("bare_sig", False),
        ("nodoc", False),
        ("magic_only", False),
        ("gap", False),
        ("no_comment_here", False),
    ],
)
def test_ruby_is_documented(name, expected):
    assert _docs(SRC)[name] is expected, name


def test_a_neighbours_tag_does_not_document_the_next_method():
    src = "# @return [Integer] one\ndef a\n  1\nend\n\ndef b\n  2\nend\n"
    docs = _docs(src)
    assert docs["a"] is True
    assert docs["b"] is False
