"""#3798: a `use A::B;` inside POD or after `__END__` / `__DATA__` is documentation, not an import."""

import time

import pytest

from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANG = LANGUAGE_DEFINITIONS["perl"]
_REGEX = _LANG["rules"]["_dependency_capture"]


def _imports(src: str) -> set[str]:
    return extract_raw_imports(_REGEX, src, _LANG)


_REAL = "use Real::Before;\n"
_AFTER = "use Real::After;\n"


@pytest.mark.parametrize(
    "opener",
    ["=pod", "=head1 SYNOPSIS", "=head2 X", "=item foo", "=over 4", "=begin text", "=for comment", "=encoding utf8"],
)
def test_use_inside_a_closed_pod_block_is_no_import(opener):
    src = f"{_REAL}\n{opener}\n\n  use Doc::Only;\n  require Doc::Required;\n  no Doc::Never;\n\n=cut\n\n{_AFTER}"
    assert _imports(src) == {"Real::Before", "Real::After"}


def test_unterminated_pod_runs_to_eof():
    # perl reads POD to `=cut` or EOF: a use line below an unterminated opener is documentation (#6572)
    src = f"{_REAL}=head1 NAME\nuse Doc::Mid;\n=head2 MORE\nuse Doc::Tail;\n"
    assert _imports(src) == {"Real::Before"}


@pytest.mark.parametrize("body_lines", [100, 2000, 5000])
def test_use_in_pod_longer_than_the_prism_bound_is_no_import(body_lines):
    # 2000+ lines is past Prism's 15000-char POD bound: the tail `use` must still be blanked (#6572)
    src = f"{_REAL}=head1 NAME\n" + "some prose line here\n" * body_lines + f"  use Doc::Late;\n\n=cut\n{_AFTER}"
    assert _imports(src) == {"Real::Before", "Real::After"}


def test_crlf_pod_block_is_no_import():
    assert _imports("=pod\r\n  use Doc::One;\r\n=cut\r\nuse Code::One;\r\n") == {"Code::One"}


def test_a_second_opener_inside_pod_does_not_end_it():
    src = "=head1 A\n  use Doc::One;\n=head2 B\n  use Doc::Two;\n=cut\nuse Code::One;\n"
    assert _imports(src) == {"Code::One"}


def test_many_openers_without_cut_stay_linear():
    t0 = time.perf_counter()
    got = _imports("=head1 N\n=head2 M\n" * 40000 + "use Never::Seen;\n")
    assert time.perf_counter() - t0 < 5
    assert got == set()


def test_pod_at_file_start_and_two_blocks():
    src = "=head1 A\n\nuse One::Doc;\n\n=cut\n\nuse Code::One;\n\n=pod\n\nuse Two::Doc;\n\n=cut\n\nuse Code::Two;\n"
    assert _imports(src) == {"Code::One", "Code::Two"}


@pytest.mark.parametrize("marker", ["__END__", "__DATA__"])
def test_everything_after_end_marker_is_no_import(marker):
    src = f"{_REAL}\n{marker}\nuse Data::Text;\n\n=head1 X\n\nuse Pod::Text;\n"
    assert _imports(src) == {"Real::Before"}


def test_equals_and_cut_not_at_line_start_are_code():
    src = "my $x\n  =head1;\nuse Code::Kept;\n  =cut\nuse Code::Also;\n"
    assert _imports(src) == {"Code::Kept", "Code::Also"}


def test_end_marker_must_be_its_own_token():
    # `__END__X` is not the marker; an identifier that merely starts with it stays code
    assert _imports("use Real::One;\n__ENDING__\nuse Real::Two;\n") == {"Real::One", "Real::Two"}


def test_long_unterminated_pod_is_bounded():
    src = "=head1 NAME\n" + "use Pad::Line;\n" * 40000
    t0 = time.perf_counter()
    got = _imports(src)
    assert time.perf_counter() - t0 < 5
    assert got == set()  # the whole tail is POD


def test_plack_shaped_module_pod_synopsis_and_trailing_pod_are_no_import():
    # #6572: a Plack middleware file: code, a long POD SYNOPSIS with indented `use` samples, `=cut`-less trailing POD
    src = (
        "package Plack::Middleware::Sample;\nuse strict;\nuse parent qw(Plack::Middleware);\n\n1;\n\n__END__\n\n"
        "=head1 SYNOPSIS\n\n  use Plack::Builder;\n  builder { enable 'Sample' };\n\n"
        + "=head1 DESCRIPTION\n\n"
        + "prose line\n" * 3000
        + "\n  use Doc::Tail;\n"
    )
    assert _imports(src) == {"strict", "parent"}
