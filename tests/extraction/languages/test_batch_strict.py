"""batch strict structural-signature coverage."""

import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune


def test_batch_calls_out_strict():
    batch = LANGUAGE_DEFINITIONS["batch"]
    calls_out = batch["rules"]["calls_out"]

    # 1. Positives
    assert calls_out.findall("call :label") == ["label"]
    assert calls_out.findall("  call prog") == ["prog"]
    assert calls_out.findall("call :my-sub.routine") == ["my-sub.routine"]

    # 2. Negatives
    assert calls_out.findall("goto :label") == []
    assert calls_out.findall("echo call me") == []

    # 3. Capture groups
    assert calls_out.groups == 1

    # 4. ReDoS immunity
    payload1 = "call " + "a" * 100000
    payload2 = "\n" * 100000 + "call"
    assert_redos_immune(calls_out, payload1)
    assert_redos_immune(calls_out, payload2)
