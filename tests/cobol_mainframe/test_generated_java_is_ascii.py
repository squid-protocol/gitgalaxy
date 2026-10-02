"""Generated Java must be pure ASCII (non-ASCII characters as \\uXXXX escapes).

javac reads source in the platform encoding unless told otherwise -- cp1252 on
Windows -- so a raw U+00FF in the CICS runtime's char literal broke every CICS
port's compile there ("unclosed character literal"). A \\uXXXX escape means the
same character to javac on every platform. This walks every Java template the
cobol_to_java forges emit."""

import importlib
import pkgutil

import pytest

import gitgalaxy.tools.cobol_to_java as forges


def _java_templates():
    for info in pkgutil.walk_packages(forges.__path__, forges.__name__ + "."):
        try:
            mod = importlib.import_module(info.name)
        except Exception:  # noqa: BLE001 -- optional-dependency modules are not templates
            continue
        for name, value in vars(mod).items():
            if (
                isinstance(value, str)
                and len(value) > 200
                and ("package __PACKAGE__" in value or "public class " in value)
            ):
                yield f"{info.name}.{name}", value


TEMPLATES = dict(_java_templates())


def test_templates_found():
    assert "gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge.CICS_TASK_JAVA" in TEMPLATES


@pytest.mark.parametrize("name", sorted(TEMPLATES))
def test_java_template_is_ascii(name):
    bad = [(n, line.strip()) for n, line in enumerate(TEMPLATES[name].splitlines(), 1) if not line.isascii()]
    assert not bad, f"{name}: non-ASCII at {bad[:3]} -- write it as a \\uXXXX escape"
