"""#5876: a `.h` is objective-c only when its own text carries ObjC syntax; `.m` neighbours alone never decide it."""

import pytest

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

OBJC_IFACE = "#import <Foundation/Foundation.h>\n\n@interface Widget : NSObject\n- (void)reset;\n@end\n"
OBJC_FORWARD = "@class Widget;\n\nvoid widget_register(Widget *w);\n"
OBJC_IMPL = "#import <Foundation/Foundation.h>\n\n@implementation Widget\n- (void)reset {\n}\n@end\n"
PLAIN_C = "#ifndef GLUE_H\n#define GLUE_H\n\nvoid *glue_create(float size, int weight);\nint glue_count(void);\n\n#endif\n"
# the C++ guard Doomsday-style bridge headers carry
EXTERN_C = "#ifdef __cplusplus\nextern \"C\" {\n#endif\n\nvoid *bridge_font(float size);\n\n#ifdef __cplusplus\n}\n#endif\n"


def _lang(root, name, ext_tally):
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    path = root / name
    lang, _, proof = detector.focus(path, path.read_text(), ext_tally=ext_tally)
    return lang, proof


def _tree(tmp_path, files):
    tally = {}
    for name, text in files.items():
        (tmp_path / name).write_text(text)
        suffix = "." + name.rsplit(".", 1)[1]
        tally[suffix] = tally.get(suffix, 0) + 1
        tally[name.lower()] = 1
    return tally


@pytest.mark.parametrize("body", [PLAIN_C, EXTERN_C])
def test_header_without_objc_syntax_is_not_objc_beside_m_files(tmp_path, body):
    """Same-stem `.m` (the sibling anchor) and a folder of proven ObjC `.h` files (the sibling vote) are both name evidence."""
    files = {"glue.h": body, "glue.m": "int glue_count(void) { return 0; }\n"}
    for i in range(3):
        files[f"view{i}.h"] = OBJC_IFACE
        files[f"view{i}.m"] = OBJC_IMPL
    lang, proof = _lang(tmp_path, "glue.h", _tree(tmp_path, files))
    assert lang != "objective-c", proof


def test_headerless_neighbourhood_without_same_stem_m_is_not_objc(tmp_path):
    files = {"plain.h": PLAIN_C}
    for i in range(3):
        files[f"view{i}.h"] = OBJC_IFACE
        files[f"view{i}.m"] = OBJC_IMPL
    lang, proof = _lang(tmp_path, "plain.h", _tree(tmp_path, files))
    assert lang != "objective-c", proof


@pytest.mark.parametrize("body", [OBJC_IFACE, OBJC_FORWARD])
def test_header_with_objc_syntax_stays_objc_beside_same_stem_m(tmp_path, body):
    files = {"widget.h": body, "widget.m": OBJC_IMPL}
    lang, _ = _lang(tmp_path, "widget.h", _tree(tmp_path, files))
    assert lang == "objective-c"
