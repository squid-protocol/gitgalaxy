"""The register audit (#4702): an entry that claims a match names an IBM document or declares the difference."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import register


def _audit_with(monkeypatch, tmp_path, entries):
    for i, (status, body) in entries.items():
        meta = dict.fromkeys(register.KEYS, "") | {"id": i, "family": i[0], "status": status}
        (tmp_path / f"{i}.md").write_text(register.format_entry(meta, body), encoding="utf-8")
    monkeypatch.setattr(register, "REG", tmp_path)
    return register.audit()


def test_audit_flags_only_uncited_claims(monkeypatch, tmp_path):
    found = _audit_with(
        monkeypatch,
        tmp_path,
        {
            "C1": ("ASSUMED", "- believed to match"),
            "C2": ("MATCHED", "- IBM (Enterprise COBOL for z/OS 6.4 Language Reference, SC27-8713-03) says so"),
            "C3": ("ASSUMED", "- **Where they differ.** the oracle pads"),
            "C4": ("", "- nothing"),
            "C5": ("REFUSED", "- IBM is silent"),
        },
    )
    assert [i for i, _, _ in found] == ["C1", "C4"]


def test_audit_problems_name_new_and_fixed(monkeypatch):
    monkeypatch.setattr(register, "UNCITED_BASELINE", frozenset({"A1", "B2"}))
    base = sorted(register.UNCITED_BASELINE)
    found = [(i, "ASSUMED", "no") for i in base[1:]] + [("Z99", "ASSUMED", "no")]
    problems = register.audit_problems(found)
    assert any(p.startswith("Z99:") for p in problems)
    assert any(p.startswith(base[0] + ":") and "now cited" in p for p in problems)


def test_the_real_register_matches_the_baseline():
    assert register.audit_problems(register.audit()) == []


def test_strict_tier_needs_a_number_a_difference_or_stated_silence(monkeypatch, tmp_path):
    _audit_with(
        monkeypatch,
        tmp_path,
        {
            "C1": ("ASSUMED", "- see the Language Reference"),
            "C2": ("MATCHED", "- Enterprise COBOL 6.4 Language Reference, SC27-8713-03, says so"),
            "C3": ("ASSUMED", "- **Where they differ.** the oracle pads"),
            "C4": ("ASSUMED", "- IBM is silent here"),
            "C5": ("REFUSED", "- nothing"),
        },
    )
    assert register.audit_strict() == ["C1"]


def test_strict_problems_name_new_and_fixed(monkeypatch, tmp_path):
    _audit_with(monkeypatch, tmp_path, {"C1": ("ASSUMED", "- Language Reference"), "C2": ("MATCHED", "- SC27-8713-03")})
    monkeypatch.setattr(register, "STRICT_BASELINE", frozenset({"C2"}))
    problems = register.audit_problems([])
    assert any(p.startswith("C1:") for p in problems)
    assert any(p.startswith("C2:") and "STRICT_BASELINE" in p for p in problems)


def test_the_baseline_is_empty():
    assert not register.UNCITED_BASELINE
