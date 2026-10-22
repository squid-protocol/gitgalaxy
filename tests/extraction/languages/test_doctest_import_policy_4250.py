"""
#4250 (policy, decided): a doctest `>>> import X` / `... import X` line is NOT an import.

The python import-pack rules are anchored on a statement start (line start or `;`), so a
REPL prompt prefix keeps a docstring example from counting. This matches the general
python `import` rule (#2875 contract C5, `docs/import_rule_contract.md`), which already
lists the doctest line as a non-hit. Every rule built by `_py_package_import` is pinned
together: the five AI/ML rules (#4137, #4150) and their builder siblings (#4238).
"""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards import _shared_patterns as sp

# (pattern, a package it names)
_RULES = [
    ("PY_LLM_API", "openai"),
    ("PY_LLM_ORCHESTRATOR", "langchain_core"),
    ("PY_LLM_ORCHESTRATOR", "llama_index"),
    ("PY_LLM_VECTOR_STORE", "chromadb"),
    ("PY_ML_TRADITIONAL", "sklearn"),
    ("PY_DL_FRAMEWORKS", "torch"),
    ("PY_HARDWARE_BRIDGE", "serialport"),
    ("PY_CRYPTOGRAPHY", "hashlib"),
]

_DOCTEST_SHAPES = [
    ">>> import {p}",
    "    >>> import {p}",
    ">>> import {p} as m",
    ">>> from {p} import x",
    "    >>> from {p}.sub import x",
    "... import {p}",
    "    ... from {p} import x",
]

_STATEMENT_SHAPES = [
    "import {p}",
    "    import {p}",
    "from {p} import x",
    "x = 1; import {p}",
]


@pytest.mark.parametrize("name,pkg", _RULES)
@pytest.mark.parametrize("shape", _DOCTEST_SHAPES)
def test_doctest_prompt_import_does_not_count(name, pkg, shape):
    line = shape.format(p=pkg)
    assert not getattr(sp, name).search(line), line


@pytest.mark.parametrize("name,pkg", _RULES)
@pytest.mark.parametrize("shape", _STATEMENT_SHAPES)
def test_same_import_at_statement_start_counts(name, pkg, shape):
    # guards the test above against passing vacuously (wrong package name, wrong shape)
    line = shape.format(p=pkg)
    assert getattr(sp, name).search(line), line


@pytest.mark.parametrize("name,pkg", _RULES)
def test_doctest_block_in_docstring_text_counts_zero(name, pkg):
    text = f'    """Example.\n\n    >>> import {pkg}\n    >>> from {pkg} import x\n    ... import {pkg}\n    """\n'
    assert not getattr(sp, name).search(text)


def test_python_rules_are_the_pinned_patterns():
    rules = LANGUAGE_DEFINITIONS["python"]["rules"]
    for key, name in [
        ("llm_api", "PY_LLM_API"),
        ("llm_orchestrator", "PY_LLM_ORCHESTRATOR"),
        ("llm_vector_store", "PY_LLM_VECTOR_STORE"),
        ("ml_traditional", "PY_ML_TRADITIONAL"),
        ("dl_frameworks", "PY_DL_FRAMEWORKS"),
    ]:
        assert rules[key] is getattr(sp, name), key
