"""#5465: DOOM-ecosystem extensions that were dropped as unsupported now route to a language."""

import pytest

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

CPP_SKETCH = "#include <Arduino.h>\nvoid setup() {\n  Serial.begin(9600);\n}\nvoid loop() {\n  delay(10);\n}\n"
GLSL_FRAG = "#version 330\nin vec2 vTexCoord;\nout vec4 FragColor;\nvoid main() {\n  FragColor = vec4(vTexCoord, 0.0, 1.0);\n}\n"
GLSL_VERT = "#version 330\nin vec4 aPosition;\nvoid main() {\n  gl_Position = aPosition;\n}\n"
CMAKE = "cmake_minimum_required(VERSION 3.10)\nfunction(add_thing name)\n  message(STATUS ${name})\nendfunction()\n"


@pytest.mark.parametrize(
    ("path", "content", "expected"),
    [
        ("sketch/raycaster.ino", CPP_SKETCH, "cpp"),
        ("sketch/main.pde", CPP_SKETCH, "cpp"),
        ("shaders/glsl/main.fp", GLSL_FRAG, "glsl"),
        ("shaders/glsl/main.vp", GLSL_VERT, "glsl"),
        ("cmake/FindSDL2.cmake", CMAKE, "plaintext"),
        ("CMakeLists.txt", CMAKE, "plaintext"),  # the .cmake decision stays consistent with this
    ],
)
def test_extension_routes(path, content, expected):
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    lang, _, _ = detector.focus(path, content)
    assert lang == expected
