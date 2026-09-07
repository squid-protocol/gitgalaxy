"""#2549: the markup handshake's OPEN TAG belongs to the host document.

Before this, both partitioners (`Prism._partition_embedded_languages` for the
comment/code streams and `StructuralExtractor._partition_segments` for the
signal counts) handed the whole `<script ...> ... </script>` element to the
embedded language, tag included. html's `func_start` rule -- whose only anchor
IS that tag -- therefore matched the raw file and could never fire once the
splitter had run: every corpus html file recorded `func_start = 0` against nine
raw matches, and the rule passed its direct-detector unit tests while being dead
in every real scan.

The payload still goes to the embedded lens; only the opening delimiter moves.
"""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _prism() -> Prism:
    return Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


def _detector_segments(source: str, lang: str = "html") -> list[tuple[str, str, int]]:
    return StructuralExtractor(lang, LANGUAGE_DEFINITIONS)._partition_segments(source, lang)


SRC = "<html><body>\n<script>var x = 1;</script>\n</body></html>\n"


def test_open_tag_stays_with_the_host():
    segments = [(lang, text) for lang, text, _ in _detector_segments(SRC)]

    assert segments == [
        ("html", "<html><body>\n<script>"),
        ("javascript", "var x = 1;</script>"),
        ("html", "\n</body></html>\n"),
    ]


def test_both_partitioners_move_the_same_boundary():
    """The two are parallel implementations of one rule and must not drift.

    Compared on a source whose trigger sits at offset 0 because Prism compiles
    the trigger with `re.I` only, where the detector adds `re.M` -- so a
    mid-file `^`-anchored trigger reaches only one of them. That asymmetry
    predates #2549 and is deliberately left alone here: Prism's partition only
    chooses which comment family strips which segment, and moving it is a
    corpus-wide change with nothing to do with this rule's reachability.
    """
    src = "<script>var x = 1;</script>\n<p>after</p>\n"

    prism_segments = _prism()._partition_embedded_languages(src, "html")
    detector_segments = [(lang, text) for lang, text, _ in _detector_segments(src)]

    assert prism_segments == detector_segments
    assert prism_segments[0] == ("html", "<script>")


def test_style_open_tag_stays_with_the_host():
    src = "<html><body>\n<style>body{color:red}</style>\n</body></html>\n"
    segments = _detector_segments(src)

    assert segments[0][1].endswith("<style>")
    assert segments[1][:2] == ("css", "body{color:red}</style>")


def test_attribute_value_holding_a_gt_does_not_cut_the_tag_short():
    """`MARKUP_OPEN_TAG_TAIL` skips quoted attribute values, so the boundary is
    the tag's own `>`, not the first `>` byte after the trigger."""
    src = '<html>\n<script data-tpl="a>b" defer>var x = 1;</script>\n'
    segments = _detector_segments(src)

    assert segments[0][1].endswith('<script data-tpl="a>b" defer>')
    assert segments[1][:2] == ("javascript", "var x = 1;</script>")


def test_unterminated_open_tag_falls_back_to_the_pre_2549_boundary():
    """No `>` anywhere: the tag cannot be resolved, so the embedded segment
    starts at the trigger exactly as it did before -- never mid-attribute."""
    src = "<html>\n<script defer\n"
    segments = _detector_segments(src)

    assert segments[0][:2] == ("html", "<html>\n")
    assert segments[1][:2] == ("javascript", "<script defer\n")


def test_paired_bracket_handshake_is_unchanged():
    """`asm!(` declares no open delimiter: `_find_balanced_end` counts depth from
    the opening bracket, so that bracket has to stay inside the asm segment."""
    src = 'fn main() {\n    asm!("nop");\n}\n'
    segments = [(lang, text) for lang, text, _ in _detector_segments(src, "rust")]

    assert ("assembly", '    asm!("nop")') in segments


def test_func_start_is_reachable_end_to_end():
    """The issue's own micro-repro, through the full per-file pipeline."""
    extractor = StructuralExtractor("html", LANGUAGE_DEFINITIONS)

    assert extractor.splice("<html>\n<script>var x = 1;</script>\n", "")["equations"]["func_start"] == 1
    assert extractor.splice("<html>\n<script></script>\n", "")["equations"]["func_start"] == 1
    assert extractor.splice("<html>\n<style>body{color:red}</style>\n", "")["equations"]["func_start"] == 1


def test_script_body_still_reaches_the_javascript_lens():
    """Only the tag moved: the body's own functions are still JavaScript's, and
    still land on the html file's row."""
    src = "<html>\n<script>\nfunction boot() { return 1; }\n</script>\n"
    result = StructuralExtractor("html", LANGUAGE_DEFINITIONS).splice(src, "")

    assert [f["name"] for f in result["functions"]] == ["boot"]
    # 1 for html's own `<script` tag, 1 for JavaScript's `function boot`.
    assert result["equations"]["func_start"] == 2


def test_non_executable_script_type_still_raises_no_signal():
    """#2492's negative lookahead now runs where it always meant to: the tag is
    finally in html's own segment, and a `type` the browser never executes must
    still not count as an executable block."""
    src = '<html>\n<script type="text/template">\n  <p>{{ name }}</p>\n</script>\n'
    result = StructuralExtractor("html", LANGUAGE_DEFINITIONS).splice(src, "")

    assert result["equations"]["func_start"] == 0
