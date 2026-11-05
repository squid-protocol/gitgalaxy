"""#6572: `q{}` / `qq{}` bodies are Perl CODE strings (eval'd RawConv/Condition), so their `require` lines stay imports.

Blanking multi-line q/qq bodies for import capture was tried and refused: ExifTool.pm loads
`Image::ExifTool::Geotag` / `ICC_Profile` only from `RawConv => q{ require ...; }` blocks, and the crucible golden lost
those edges. This pins the behaviour so the next attempt weighs that trade.
"""

import pytest

from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANG = LANGUAGE_DEFINITIONS["perl"]
_REGEX = _LANG["rules"]["_dependency_capture"]


def _imports(src: str) -> set[str]:
    return extract_raw_imports(_REGEX, src, _LANG)


@pytest.mark.parametrize("opener", ["q{", "qq{"])
def test_require_inside_an_eval_string_body_is_still_an_import(opener):
    src = f"my %t = (RawConv => {opener}\n    require Some::Lazy;\n    Some::Lazy::go($val);\n}});\n"
    assert "Some::Lazy" in _imports(src)


def test_heredoc_body_is_still_blanked():
    src = "use Real::One;\nprint <<EOT;\n  use Doc::Only;\nEOT\n"
    assert _imports(src) == {"Real::One"}
