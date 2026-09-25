"""GitGalaxy's own YAML reader (gitgalaxy/standards/yaml_reader.py, #3613): the
configuration subset it reads, the YAML 1.2 core schema it resolves scalars with, and
the constructs it refuses. Where PyYAML happens to be installed it is used as an
independent oracle on the supported subset (it is not a runtime dependency)."""

import pytest

from gitgalaxy.standards.yaml_reader import YamlError, load_yaml

SUBSET = """\
---
# a comment line
project:
  package: com.acme.app   # a trailing comment
  version: 1.0.0-SNAPSHOT
  empty:
  none: ~
java:
  version: 21
  ratio: 0.5
  exp: 1e3
  on: true
  off: FALSE
strings:
  url: jdbc:postgresql://localhost:5432/db
  quoted: "x: y # not a comment"
  single: 'it''s'
  escaped: "tab\\tend \\"q\\""
  hash_in_word: a#b
lists:
  flow: [1, two, "3", true, null, ]
  empty_flow: []
  block:
    - x
    - 2
    - k: v
      k2: [a]
    -
      nested: 1
    - - a
      - b
"""


def test_the_supported_subset():
    assert load_yaml(SUBSET) == {
        "project": {"package": "com.acme.app", "version": "1.0.0-SNAPSHOT", "empty": None, "none": None},
        "java": {"version": 21, "ratio": 0.5, "exp": 1000.0, "on": True, "off": False},
        "strings": {
            "url": "jdbc:postgresql://localhost:5432/db",
            "quoted": "x: y # not a comment",
            "single": "it's",
            "escaped": 'tab\tend "q"',
            "hash_in_word": "a#b",
        },
        "lists": {
            "flow": [1, "two", "3", True, None],
            "empty_flow": [],
            "block": ["x", 2, {"k": "v", "k2": ["a"]}, {"nested": 1}, ["a", "b"]],
        },
    }


def test_matches_pyyaml_on_the_subset():
    yaml = pytest.importorskip("yaml")
    # Leave out what YAML 1.1 (PyYAML) reads differently from 1.2: keys `on` / `off` (booleans in
    # 1.1) and `1e3` (a string in 1.1, which wants a dot); test_the_yaml_1_2_core_schema pins those.
    shared = "\n".join(ln for ln in SUBSET.splitlines() if not ln.strip().startswith(("on:", "off:", "exp:")))
    assert load_yaml(shared) == yaml.safe_load(shared)


def test_the_yaml_1_2_core_schema():
    # PyYAML (YAML 1.1) reads these as True / 15; the 1.2 core schema does not.
    assert load_yaml("a: yes\nb: no\nc: on\nd: 017\ne: '017'") == {
        "a": "yes",
        "b": "no",
        "c": "on",
        "d": 17,
        "e": "017",
    }
    assert load_yaml("on: true\noff: 1\nexp: 1e3") == {"on": True, "off": 1, "exp": 1000.0}
    assert load_yaml("") is None
    assert load_yaml("# only a comment\n") is None
    assert load_yaml("- 1\n- 2\n") == [1, 2]


@pytest.mark.parametrize(
    "text, message",
    [
        ("a: &x 1", "anchors"),
        ("a: *x", "aliases"),
        ("a: !!str 1", "tags"),
        ("a: |\n  text", "block scalars"),
        ("a: >\n  text", "block scalars"),
        ("a: {b: 1}", "flow mappings"),
        ("a: [1, [2]]", "nested flow"),
        ("a: 1\na: 2", "duplicate key"),
        ("a:\n\tb: 1", "tabs"),
        ("a: 1\n---\nb: 2", "multiple documents"),
        ("a: b: c", "quote it"),
        ("a: 'open", "unterminated"),
        ('a: "bad \\q"', "unsupported escape"),
        ("- a\nb: 1", "expected a `- ` sequence item"),
        ("a: 1\n  b: 2", "unexpected indentation"),
        ("? complex\n", "complex keys"),
    ],
)
def test_outside_the_subset_is_an_error_naming_the_line(text, message):
    with pytest.raises(YamlError, match=message) as err:
        load_yaml(text)
    assert "line " in str(err.value)
