"""#4733: the Db2 image a Db2 case runs its SQL on is pinned by digest (like the GnuCOBOL oracle, #4309), the pin is
written down in docs/language_status/oracle_assumptions.md, and a Db2 case's recorded oracle names it."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_db2 as db2  # noqa: E402
import equivalence_oracle as eo  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DIGEST = re.compile(r"@(sha256:[0-9a-f]{64})$")


def test_the_db2_image_is_pinned_by_digest_not_a_tag():
    assert db2.pinned_by_digest(db2.IMAGE), f"{db2.IMAGE} must be name@sha256:<digest>"
    assert ":latest" not in db2.IMAGE


def test_a_tag_is_not_a_pin():
    assert not db2.pinned_by_digest("icr.io/db2_community/db2:latest")
    assert not db2.pinned_by_digest("icr.io/db2_community/db2:12.1.0.0")
    assert not db2.pinned_by_digest("icr.io/db2_community/db2@sha256:abc")


def test_the_pinned_digest_is_written_in_the_oracle_assumptions():
    text = (REPO / "docs" / "language_status" / "oracle_assumptions.md").read_text(encoding="utf-8")
    digest = DIGEST.search(db2.IMAGE).group(1)
    assert digest in text, "docs/language_status/oracle_assumptions.md must name the pinned Db2 image digest"


def test_every_container_start_uses_the_pinned_image():
    src = (REPO / "tests" / "tools" / "equivalence_db2.py").read_text(encoding="utf-8")
    assert "db2:latest" not in src.replace("`:latest`", "")


def test_a_db2_cases_oracle_records_the_db2_image(monkeypatch):
    monkeypatch.setattr(eo, "checked", lambda image=eo.IMAGE: {"image": {"name": image}, "matches_pin": True})
    fp = eo.for_case({"db2": {"ddl": []}})
    assert fp["db2"] == {"image": db2.IMAGE, "pinned_by_digest": True}
    assert "db2" not in eo.for_case({})


def test_the_combined_register_page_is_current():
    """#4788: oracle_assumptions.md is generated from docs/language_status/register/ (register.py render)."""
    import register  # tests/tools/register.py

    assert register.check() == []
