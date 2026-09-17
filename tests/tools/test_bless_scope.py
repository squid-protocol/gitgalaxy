import json
import sys
import tempfile
from pathlib import Path
import pytest
from io import StringIO

# Add tests/ dir to sys.path so we can import golden_diff
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import golden_diff as gd

# Also we need to import bless_scope, which is in tests/tools
import bless_scope


def test_deep_compare_string_compatibility():
    old = {"A": {"B": 1}}
    new = {"A": {"B": 2}}
    diffs = gd.deep_compare(old, new)
    
    assert len(diffs) == 1
    diff = diffs[0]
    
    # Check that it's a real string and join works
    assert isinstance(diff, str)
    joined = "\n".join(diffs)
    assert joined == "⚠️ MISMATCH at /A/B: Expected 1, Got 2"
    
    # Check exact text matches what it should be
    assert str(diff) == "⚠️ MISMATCH at /A/B: Expected 1, Got 2"


def test_deep_compare_with_slash_in_key():
    old = {"Section 1": {"Sub": {"I/O & Config Routines Files": 1}}}
    new = {"Section 1": {"Sub": {"I/O & Config Routines Files": 2}}}
    
    diffs = gd.deep_compare(old, new)
    assert len(diffs) == 1
    diff = diffs[0]
    
    assert hasattr(diff, "segments")
    assert diff.segments == ("Section 1", "Sub", "I/O & Config Routines Files")
    assert diff.segments[-1] == "I/O & Config Routines Files"
    assert diff.kind == "mismatch"


def test_bless_scope_bucketing(monkeypatch):
    old_data = {
        "Section 1": {
            "Sub": {
                "I/O & Config Routines Files": 1,
                "Normal Key": 1,
                "Extra": 1
            }
        },
        "Section 2": {
            "Missing": 1
        }
    }
    new_data = {
        "Section 1": {
            "Sub": {
                "I/O & Config Routines Files": 2,
                "Normal Key": 1,
                "New Key": 2
            }
        },
        "Section 2": {
        }
    }
    
    with tempfile.NamedTemporaryFile("w", delete=False) as f_old, \
         tempfile.NamedTemporaryFile("w", delete=False) as f_new:
        json.dump(old_data, f_old)
        json.dump(new_data, f_new)
        f_old_name = f_old.name
        f_new_name = f_new.name

    out = StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    
    try:
        bless_scope.main([f_old_name, f_new_name])
    finally:
        Path(f_old_name).unlink()
        Path(f_new_name).unlink()

    output = out.getvalue()
    
    # Ensure there's no "?" bucket
    assert "? " not in output
    assert "(unparsed)" not in output
    
    # Ensure "I/O & Config Routines Files" is bucketed exactly
    assert "I/O & Config Routines Files" in output
    
    # Ensure Extra and Missing keys are attributed to their sections
    assert "Section 1" in output
    assert "Section 2" in output
