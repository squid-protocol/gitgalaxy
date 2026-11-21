"""scripts/indexnow_submit.py: wiki file -> published URL mapping and key discovery."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "indexnow_submit", ROOT / "scripts" / "indexnow_submit.py"
)
ix = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ix)


@pytest.mark.parametrize(
    ("path", "url"),
    [
        ("docs/wiki/index.md", ix.SITE),
        ("docs/wiki/cookbook/index.md", ix.SITE + "cookbook/"),
        (
            "docs/wiki/01-02-galaxyscope-cli-reference.md",
            ix.SITE + "01-02-galaxyscope-cli-reference/",
        ),
        ("docs/wiki/cookbook/A&B.md", ix.SITE + "cookbook/A%26B/"),
        ("docs/wiki/assets/x.png", None),
        ("README.md", None),
    ],
)
def test_page_url(path, url):
    assert ix.page_url(path) == url


def test_exactly_one_committed_key_file_matches_its_name():
    key = ix.find_key(ROOT / "docs" / "wiki")
    assert len(key) >= 8
