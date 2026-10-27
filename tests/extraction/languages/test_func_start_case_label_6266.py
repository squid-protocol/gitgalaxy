"""
#6266: a `case T(x):` label before a braced block is a statement, not a function definition named `T`.

edge-classic `case uint32_t(kTextureEnvironmentSkipRGB):\n  if (enable)\n  {` read as a function `uint32_t`, which cut
`EnableCustomEnvironment` short (a missed `TextureEnvironmentMode` call) and made every `uint32_t(..)` cast a false edge.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LABELS = ["case uint32_t(kSkip):", "case MAKE(1, 2):", "case Kind(A)", "case (int)(x):"]


def _fn(label: str) -> str:
    return f"""
static void Enable(int env, bool enable)
{{
    switch (env)
    {{
    {label}
        if (enable)
        {{
            Mode(GL_COMBINE);
        }}
        break;
    }}
}}
"""


@pytest.mark.parametrize("lang", ["c", "cpp"])
@pytest.mark.parametrize("label", _LABELS)
def test_case_label_is_not_a_function(lang, label):
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(_fn(label), "")["functions"]
    assert [f["name"] for f in functions] == ["Enable"]
    assert "Mode" in functions[0]["calls_out_to"]
