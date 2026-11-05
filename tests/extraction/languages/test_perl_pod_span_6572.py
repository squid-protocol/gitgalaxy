"""#6572: perl reads POD to `=cut` or EOF however long; the doc rule and Prism's POD mirror must not cut at 15000 chars."""

import time

import pytest

from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_DOC = LANGUAGE_DEFINITIONS["perl"]["rules"]["doc"]
_PROSE = "some prose line here\n"


def _block(lines: int, opener: str = "=head1 NAME") -> str:
    return f"{opener}\n\n" + _PROSE * lines + "\n=cut\n"


@pytest.mark.parametrize("lines", [1, 100, 2000, 5000])
def test_one_pod_block_counts_one_doc_whatever_its_length(lines):
    assert len(_DOC.findall("use A;\n" + _block(lines) + "use B;\n")) == 1


def test_two_blocks_count_two():
    assert len(_DOC.findall(_block(2000) + "my $x;\n" + _block(10, "=pod"))) == 2


def test_unterminated_opener_runs_to_eof_once():
    assert len(_DOC.findall("=head1 NAME\n" + _PROSE * 2000 + "=head2 MORE\n" + _PROSE)) == 1


def test_prism_span_covers_a_pod_block_past_the_old_bound():
    src = "my $a = 1;\n" + _block(2000) + "my $b = 2;\n"
    surface = Prism._PERL_POD_SPAN
    m = surface.search(src)
    assert m and m.group(0).rstrip().endswith("=cut")
    assert len(m.group(0)) > 15000


def test_many_openers_without_cut_is_linear():
    src = "=head1 X\nfoo\n" * 20000
    t = time.perf_counter()
    _DOC.findall(src)
    Prism._PERL_POD_SPAN.findall(src)
    assert time.perf_counter() - t < 2
